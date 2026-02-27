"""ReActPattern - реактивная стратегия без логики планирования.
ОСОБЕННОСТИ:
- Полный анализ текущей ситуации и прогресса
- Структурированное принятие решений
- Поддержка отката при необходимости
- ИСПОЛЬЗОВАНИЕ ТОЛЬКО capability, доступных для реактивной стратегии
- Сохранение совместимости с существующей архитектурой
- ИСПОЛЬЗОВАНИЕ PromptService и ContractService для загрузки промптов и контрактов
- НЕ ЗНАЕТ о версиях — версии управляются через ComponentConfig в ApplicationContext
"""
import json
import time
import logging
from typing import Any, Dict, List
from core.application.behaviors.base_behavior_pattern import BaseBehaviorPattern
from core.application.behaviors.base import BehaviorDecision, BehaviorDecisionType
from core.application.agent.strategies.react.schema_validator import SchemaValidator
from core.application.agent.strategies.react.utils import analyze_context
from core.models.schemas.react_models import ReasoningResult
from core.application.agent.strategies.react.validation import validate_reasoning_result
from core.retry_policy.retry_and_error_policy import RetryPolicy
from core.models.enums.common_enums import ExecutionStatus
from core.models.data.capability import Capability
from core.models.types.llm_types import LLMRequest, StructuredOutputConfig

logger = logging.getLogger(__name__)

class ReActPattern(BaseBehaviorPattern):
    """ReAct паттерн поведения без логики планирования.

    ЭТАПЫ РАБОТЫ:
    1. Анализ контекста и прогресса
    2. Получение доступных capability ТОЛЬКО для реактивной стратегии
    3. Структурированное рассуждение через LLM (с использованием PromptService и ContractService)
    4. Принятие решения на основе результатов
    5. Обработка ошибок и применение fallback

    АРХИТЕКТУРА:
    - НЕ знает о версиях промптов/контрактов
    - component_name используется для получения config из AppConfig
    - Промпты и контракты загружаются из component_config.resolved_prompts/contracts
    - pattern_id генерируется из component_name для совместимости
    """
    # pattern_id НЕ определяется — генерируется из component_name

    def __init__(self, component_name: str, component_config = None, application_context = None, executor = None):
        """Инициализация паттерна.

        ПАРАМЕТРЫ:
        - component_name: Имя компонента (ОБЯЗАТЕЛЬНО, например "react_pattern")
        - component_config: ComponentConfig с resolved_prompts/contracts (из AppConfig)
        - application_context: Прикладной контекст для доступа к компонентам
        - executor: ActionExecutor для взаимодействия (требуется BaseComponent)
        """
        super().__init__(component_name, component_config, application_context, executor)

        # Специфичные для ReAct атрибуты
        self.reasoning_schema = None  # Будет загружено из self.output_contracts
        self.reasoning_prompt_template = None  # Будет загружено из self.prompts
        self.system_prompt_template = None  # Системный промпт из self.prompts
        self.last_reasoning_time = 0.0
        self.error_count = 0
        self.max_consecutive_errors = 3
        self.schema_validator = SchemaValidator()
        self.retry_policy = RetryPolicy()

        # Примечание: Промпты и контракты загружаются через BaseComponent.initialize()
        # и доступны в self.prompts / self.output_contracts

    def _load_reasoning_resources(self) -> bool:
        """
        Загружает промпт и схему для рассуждения из кэша BaseComponent.

        ВОЗВРАЩАЕТ:
        - bool: True если успешно загружено
        """
        # Если уже загружено, ничего не делаем
        if self.reasoning_prompt_template and self.reasoning_schema:
            return True

        try:
            # Загружаем из self.prompts / self.output_contracts (уже загружены BaseComponent.initialize())
            if self.prompts:
                # Ищем промпт behavior.react.think (приоритет) или первый доступный
                if "behavior.react.think" in self.prompts:
                    prompt_obj = self.prompts["behavior.react.think"]
                    if hasattr(prompt_obj, 'content') and prompt_obj.content:
                        self.reasoning_prompt_template = prompt_obj.content
                        logger.info("Загружен промпт behavior.react.think из self.prompts")
                else:
                    # Fallback: берём первый доступный промпт
                    for cap_name, prompt_obj in self.prompts.items():
                        if hasattr(prompt_obj, 'content') and prompt_obj.content:
                            self.reasoning_prompt_template = prompt_obj.content
                            logger.info(f"Загружен промпт из self.prompts[{cap_name}] (fallback)")
                            break

            # Контракты уже загружены в self.output_contracts
            if self.output_contracts:
                # Ищем контракт behavior.react.think (приоритет) или первый доступный
                if "behavior.react.think" in self.output_contracts:
                    schema_cls = self.output_contracts["behavior.react.think"]
                    if schema_cls:
                        if hasattr(schema_cls, 'model_json_schema'):
                            self.reasoning_schema = schema_cls.model_json_schema()
                        else:
                            self.reasoning_schema = schema_cls
                        logger.info("Загружен контракт behavior.react.think из self.output_contracts")
                else:
                    # Fallback: берём первую доступную схему
                    for cap_name, schema_cls in self.output_contracts.items():
                        if schema_cls:
                            if hasattr(schema_cls, 'model_json_schema'):
                                self.reasoning_schema = schema_cls.model_json_schema()
                            else:
                                self.reasoning_schema = schema_cls
                            logger.info(f"Загружен контракт из self.output_contracts[{cap_name}] (fallback)")
                            break

            # Fallback на модель если контракт не найден
            if not self.reasoning_schema:
                logger.warning("Контракт не загружен, используем ReasoningResult.model_json_schema()")
                self.reasoning_schema = ReasoningResult.model_json_schema()

            return True
        except Exception as e:
            logger.error(f"Ошибка загрузки промпта/контракта: {e}", exc_info=True)
            return False

    def _render_reasoning_prompt(self, context_analysis: Dict[str, Any], available_capabilities: List[Dict[str, Any]]) -> str:
        """
        Рендерит шаблон промпта с подстановкой переменных.

        Использует промпт из PromptService (загружен в component_config.resolved_prompts).
        Fallback на дефолтный шаблон только если промпт не загружен.

        ПАРАМЕТРЫ:
        - context_analysis: анализ контекста
        - available_capabilities: доступные capability

        ВОЗВРАЩАЕТ:
        - str: отрендеренный промпт
        """
        goal = context_analysis.get("goal", "Неизвестная цель")
        last_steps = context_analysis.get("last_steps", [])
        no_progress_steps = context_analysis.get("no_progress_steps", 0)
        consecutive_errors = context_analysis.get("consecutive_errors", 0)

        # Формируем контекст для подстановки в шаблон
        prompt_context = {
            "input": self._build_input_context(context_analysis, available_capabilities),
            "goal": goal,
            "step_history": "\n".join([f"{i+1}. {s}" for i, s in enumerate(last_steps[-3:])]) if last_steps else "Шаги не выполнены",
            "observation": last_steps[-1] if last_steps else "Нет наблюдений",
            "available_tools": self._format_available_tools(available_capabilities),
            "no_progress_steps": no_progress_steps,
            "consecutive_errors": consecutive_errors
        }

        if self.reasoning_prompt_template:
            # Рендерим шаблон из PromptService
            rendered = self.reasoning_prompt_template
            for key, value in prompt_context.items():
                rendered = rendered.replace(f"{{{key}}}", str(value))
            return rendered
        else:
            # Fallback: минимальный шаблон (только если промпт не загружен из registry)
            logger.warning("reasoning_prompt_template не загружен, используем минимальный fallback")
            return self._build_minimal_fallback_prompt(prompt_context)

    def _build_input_context(self, context_analysis: Dict[str, Any], available_capabilities: List[Dict[str, Any]]) -> str:
        """
        Формирует {input} секцию для промпта.

        ПАРАМЕТРЫ:
        - context_analysis: анализ контекста
        - available_capabilities: доступные capability

        ВОЗВРАЩАЕТ:
        - str: контекст для {input}
        """
        goal = context_analysis.get("goal", "Неизвестная цель")
        last_steps = context_analysis.get("last_steps", [])
        
        parts = [
            f"ЦЕЛЬ: {goal}",
            f"Шагов выполнено: {len(last_steps)}",
            f"Шагов без прогресса: {context_analysis.get('no_progress_steps', 0)}",
            f"Ошибок подряд: {context_analysis.get('consecutive_errors', 0)}"
        ]
        
        if last_steps:
            parts.append("\nПОСЛЕДНИЕ ШАГИ:")
            for i, step in enumerate(last_steps[-3:], 1):
                parts.append(f"  {i}. {step}")
        
        parts.append("\nДОСТУПНЫЕ ИНСТРУМЕНТЫ:")
        for cap in available_capabilities:
            parts.append(f"  - {cap['name']}: {cap['description']}")

        return "\n".join(parts)

    def _format_available_tools(self, available_capabilities: List[Dict[str, Any]]) -> str:
        """
        Форматирует список доступных инструментов с параметрами.

        ПАРАМЕТРЫ:
        - available_capabilities: список capability

        ВОЗВРАЩАЕТ:
        - str: отформатированный список инструментов с параметрами
        """
        lines = []
        for cap in available_capabilities:
            name = cap.get('name', 'unknown')
            description = cap.get('description', 'Нет описания')
            
            # Получаем схему параметров из schema_validator
            params_schema = None
            if hasattr(self, 'schema_validator') and self.schema_validator:
                params_schema = self.schema_validator.get_capability_schema(name)
            
            # Формируем строку инструмента
            line = f"- {name}: {description}"
            
            # Добавляем параметры если есть схема
            if params_schema:
                params_list = []
                for param_name, param_info in params_schema.items():
                    param_type = param_info.get('type', 'string') if isinstance(param_info, dict) else 'string'
                    required = param_info.get('required', False) if isinstance(param_info, dict) else False
                    req_mark = "(required)" if required else "(optional)"
                    params_list.append(f"{param_name}: {param_type} {req_mark}")
                
                if params_list:
                    line += "\n    Параметры:"
                    for p in params_list:
                        line += f"\n      - {p}"
            
            lines.append(line)
        
        return "\n".join(lines)

    def _build_minimal_fallback_prompt(self, prompt_context: Dict[str, Any]) -> str:
        """
        Минимальный fallback промпт (только если промпт не загружен из registry).

        ПАРАМЕТРЫ:
        - prompt_context: контекст для подстановки

        ВОЗВРАЩАЕТ:
        - str: минимальный промпт для рассуждения
        """
        return f"""ЦЕЛЬ: {prompt_context.get('goal', 'Неизвестная цель')}

КОНТЕКСТ:
{prompt_context.get('input', '')}

Верни решение в формате JSON:
{{
  "thought": "Рассуждение о ситуации",
  "analysis": {{
    "progress": "Прогресс к цели",
    "current_state": "Текущее состояние",
    "issues": []
  }},
  "decision": {{
    "next_action": "Имя capability",
    "reasoning": "Обоснование",
    "parameters": {{}},
    "expected_outcome": "Ожидаемый результат"
  }},
  "confidence": 0.5,
  "stop_condition": false
}}"""

    def _get_default_system_prompt(self) -> str:
        """
        Возвращает системный промпт по умолчанию (fallback).

        ВОЗВРАЩАЕТ:
        - str: системный промпт
        """
        return """Ты — модуль рассуждения (THINK) в архитектуре ReAct (Reasoning and Acting).
Твоя задача — анализировать текущую ситуацию и принимать решения о следующих действиях.

Ты должен:
1. Оценить текущую ситуацию и прогресс к цели
2. Выбрать следующее действие из доступных инструментов
3. Обосновать свой выбор
4. Проверить безопасность и корректность действий

Отвечай ТОЛЬКО в формате JSON согласно схеме."""

    async def analyze_context(
        self,
        session_context: 'SessionContext',
        available_capabilities: List[Capability],
        context_analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Анализ контекста без принятия решений"""
        logger.error(f"analyze_context: received available_capabilities count={len(available_capabilities)}, names={[c.name for c in available_capabilities]}")

        # Если available_capabilities пустой, получаем их из ApplicationContext
        if not available_capabilities and self.application_context:
            logger.error("analyze_context: available_capabilities пуст, получаем из ApplicationContext")
            available_capabilities = self.application_context.get_all_capabilities()
            logger.error(f"analyze_context: получено {len(available_capabilities)} capability из ApplicationContext")

        # Регистрируем схемы для всех capability в SchemaValidator
        self._register_capability_schemas(available_capabilities)

        # Выполняем анализ контекста сессии
        analysis = analyze_context(session_context)

        # Добавляем информацию о доступных capability
        analysis["available_capabilities"] = self._filter_capabilities(
            available_capabilities,
            required_skills=["book_library", "sql_query", "generic"]
        )

        logger.error(f"analyze_context: after filtering available_capabilities count={len(analysis['available_capabilities'])}, names={[c.name for c in analysis['available_capabilities']]}")

        # Добавляем информацию о прогрессе
        # В новой архитектуре используем атрибуты или возвращаем 0, если метод не существует
        analysis["no_progress_steps"] = getattr(session_context, 'no_progress_steps', 0)
        analysis["consecutive_errors"] = getattr(session_context, 'consecutive_errors', 0)

        return analysis

    def _register_capability_schemas(self, available_capabilities: List[Capability]):
        """
        Регистрирует схемы входных параметров для всех capability в SchemaValidator.

        Схемы берутся из input_contracts кэша компонента.

        ARGS:
        - available_capabilities: список capability для регистрации
        """
        if not self.application_context:
            logger.warning("_register_capability_schemas: application_context не доступен")
            return

        logger.info(f"=== РЕГИСТРАЦИЯ СХЕМ ===")
        logger.info(f"Всего capability: {len(available_capabilities)}")
        
        # Получаем все input схемы из контекста
        for cap in available_capabilities:
            # Пытаемся получить схему из input_contracts кэша
            # Формат ключа: capability_name (например, "book_library.execute_script")
            schema = None
            
            # Проверяем, есть ли схема в кэше input_contracts
            if hasattr(self, 'input_contracts') and cap.name in self.input_contracts:
                schema = self.input_contracts[cap.name]
                logger.info(f"Найдена схема в input_contracts для {cap.name}")
            elif self.application_context.use_data_repository and self.application_context.data_repository:
                # Пытаемся получить схему из DataRepository
                try:
                    # Получаем версию контракта из meta capability
                    contract_version = cap.meta.get('contract_version', 'v1.0.0')
                    logger.debug(f"Загрузка схемы для {cap.name} (версия: {contract_version})...")
                    schema = self.application_context.data_repository.get_contract_schema(
                        cap.name, 
                        contract_version, 
                        "input"
                    )
                    logger.info(f"Загружена схема из DataRepository для {cap.name}")
                except Exception as e:
                    logger.debug(f"Не удалось получить схему для {cap.name}: {e}")
            
            # Если схема найдена, регистрируем её в SchemaValidator
            if schema:
                # Преобразуем схему в словарь параметров
                # Ожидаем формат: {"input": {"type": "string", "required": True}}
                params_schema = {}
                if hasattr(schema, 'model_json_schema'):
                    # Pydantic модель
                    schema_dict = schema.model_json_schema()
                    properties = schema_dict.get('properties', {})
                    required = schema_dict.get('required', [])
                    for prop_name, prop_info in properties.items():
                        params_schema[prop_name] = {
                            'type': prop_info.get('type', 'string'),
                            'required': prop_name in required
                        }
                elif isinstance(schema, dict):
                    # Словарь schema_data из YAML контракта
                    properties = schema.get('properties', {})
                    required = schema.get('required', [])
                    for prop_name, prop_info in properties.items():
                        params_schema[prop_name] = {
                            'type': prop_info.get('type', 'string') if isinstance(prop_info, dict) else 'string',
                            'required': prop_name in required
                        }
                
                if params_schema:
                    self.schema_validator.register_capability_schema(cap.name, params_schema)
                    logger.info(f"✅ Зарегистрирована схема для {cap.name}: {params_schema}")
                else:
                    logger.debug(f"ℹ️ Схема для {cap.name} не имеет параметров (нормально для capability без входных данных)")
            else:
                logger.debug(f"Схема не найдена для {cap.name}, будет использоваться дефолтная")

    async def generate_decision(
        self,
        session_context: 'SessionContext',
        available_capabilities: List[Capability],
        context_analysis: Dict[str, Any]
    ) -> BehaviorDecision:
        """Генерация решения на основе анализа"""
        try:
            # Структурированное рассуждение
            reasoning_result = await self._perform_structured_reasoning(
                session_context=session_context,
                context_analysis=context_analysis,
                available_capabilities=context_analysis["available_capabilities"]
            )

            # Принятие решения
            decision = await self._make_decision_from_reasoning(
                session_context=session_context,
                reasoning_result=reasoning_result
            )

            # Сброс счетчика ошибок при успешном решении
            self.error_count = 0
            return decision

        except Exception as e:
            logger.error(f"Критическая ошибка в ReActPattern: {str(e)}", exc_info=True)
            self.error_count += 1

            # Fallback при множественных ошибках
            if self.error_count >= self.max_consecutive_errors:
                logger.warning("Достигнут лимит ошибок, переключаемся на fallback паттерн")
                return BehaviorDecision(
                    action=BehaviorDecisionType.SWITCH,
                    next_pattern="fallback.v1.0.0",
                    reason=f"too_many_errors_{self.error_count}"
                )

            # Базовый fallback
            return await self._create_fallback_decision(
                session_context=session_context,
                reason=f"critical_error_{str(e)}"
            )

    async def _perform_structured_reasoning(
        self,
        session_context,
        context_analysis: Dict[str, Any],
        available_capabilities: List[Capability]
    ) -> Dict[str, Any]:
        """Выполняет структурированное рассуждение через LLM."""
        logger.error(f"_perform_structured_reasoning: received available_capabilities count={len(available_capabilities)}")

        # Загружаем промпт и контракт из кэша BaseComponent
        self._load_reasoning_resources()

        # Преобразование capability в нужный формат для промпта
        formatted_capabilities = []
        for cap in available_capabilities:
            formatted_capabilities.append({
                'name': cap.name,
                'description': cap.description or 'Без описания',
                'parameters_schema': getattr(cap, 'parameters_schema', {}) or {}
            })

        # Рендерим промпт из шаблона (загружен из PromptService/ComponentConfig)
        reasoning_prompt = self._render_reasoning_prompt(
            context_analysis=context_analysis,
            available_capabilities=formatted_capabilities
        )

        start_time = time.time()

        try:
            # Генерация структурированного ответа через LLM
            # Получаем LLM провайдер через ApplicationContext
            llm_provider = None

            # Пытаемся получить через application_context
            if self.application_context:
                llm_provider = self.application_context.get_provider("default_llm")

            if llm_provider is None:
                # Fallback: создаем упрощенную версию рассуждения
                logger.warning("LLM провайдер недоступен, используем упрощенную логику рассуждения")
                return {
                    "analysis": {
                        "current_situation": "LLM провайдер недоступен",
                        "progress_assessment": "Неизвестно",
                        "confidence": 0.5,
                        "errors_detected": False,
                        "consecutive_errors": self.error_count,
                        "execution_time": context_analysis.get("execution_time_seconds", 0),
                        "no_progress_steps": context_analysis.get("no_progress_steps", 0)
                    },
                    "recommended_action": {
                        "action_type": "execute_capability",
                        "capability_name": "book_library.search_books",  # Используем доступную capability
                        "parameters": {"input": session_context.get_goal() or "Продолжить выполнение задачи"},
                        "reasoning": "LLM недоступен, используем fallback"
                    },
                    "available_capabilities": available_capabilities,  # ← Добавляем доступные capability
                    "needs_rollback": False
                }

            # Создаем LLMRequest для структурированного вывода
            # Системный промпт загружается из component_config.resolved_prompts
            system_prompt = self.system_prompt_template or self._get_default_system_prompt()
            
            llm_request = LLMRequest(
                prompt=reasoning_prompt,
                system_prompt=system_prompt,
                temperature=0.3,
                max_tokens=1000,
                structured_output=StructuredOutputConfig(
                    output_model="ReasoningResult",
                    schema_def=self.reasoning_schema,
                    max_retries=3,
                    strict_mode=False
                )
            )

            # === ПУБЛИКАЦИЯ СОБЫТИЯ: СГЕНЕРИРОВАН ПРОМПТ ===
            if self.application_context and hasattr(self.application_context, 'infrastructure_context'):
                from core.infrastructure.event_bus.event_bus import Event, EventType
                
                # Получаем agent_id из session_context или application_context
                agent_id = getattr(session_context, 'agent_id', 'unknown')
                if agent_id == 'unknown' and hasattr(self.application_context, 'id'):
                    agent_id = self.application_context.id

                await self.application_context.infrastructure_context.event_bus.publish(
                    event=EventType.LLM_PROMPT_GENERATED,
                    data={
                        "agent_id": agent_id,
                        "component": "react_pattern",
                        "phase": "think",
                        "system_prompt": llm_request.system_prompt,
                        "user_prompt": reasoning_prompt,
                        "prompt_length": len(reasoning_prompt),
                        "temperature": llm_request.temperature,
                        "max_tokens": llm_request.max_tokens,
                        "session_id": getattr(session_context, 'session_id', 'unknown'),
                        "goal": session_context.get_goal() if session_context else 'unknown'
                    },
                    source="react_pattern.think",
                    correlation_id=getattr(session_context, 'session_id', '')
                )

            response = await llm_provider.generate_structured(llm_request)

            # === ПУБЛИКАЦИЯ СОБЫТИЯ: ПОЛУЧЕН ОТВЕТ ===
            if self.application_context and hasattr(self.application_context, 'infrastructure_context'):
                from core.infrastructure.event_bus.event_bus import Event, EventType

                # Получаем agent_id из session_context или application_context
                agent_id = getattr(session_context, 'agent_id', 'unknown')
                if agent_id == 'unknown' and hasattr(self.application_context, 'id'):
                    agent_id = self.application_context.id

                # Обработка ответа
                if isinstance(response, dict) and 'raw_response' in response:
                    result = response['raw_response']
                    response_format = "dict.raw_response"
                elif hasattr(response, 'content'):
                    result = response.content
                    response_format = "object.content"
                else:
                    result = response
                    response_format = type(response).__name__

                await self.application_context.infrastructure_context.event_bus.publish(
                    event=EventType.LLM_RESPONSE_RECEIVED,
                    data={
                        "agent_id": agent_id,
                        "component": "react_pattern",
                        "phase": "think",
                        "response_format": response_format,
                        "response": result,
                        "session_id": getattr(session_context, 'session_id', 'unknown'),
                        "goal": session_context.get_goal() if session_context else 'unknown'
                    },
                    source="react_pattern.think",
                    correlation_id=getattr(session_context, 'session_id', '')
                )
            else:
                # Fallback для обработки ответа если EventBus недоступен
                if isinstance(response, dict) and 'raw_response' in response:
                    result = response['raw_response']
                elif hasattr(response, 'content'):
                    result = response.content
                else:
                    result = response
                
            reasoning_result = validate_reasoning_result(result)

            # Добавляем available_capabilities в результат для последующего использования
            reasoning_result['available_capabilities'] = available_capabilities

            self.last_reasoning_time = time.time() - start_time
            logger.debug(f"Структурированное рассуждение выполнено за {self.last_reasoning_time:.2f} секунд")
            return reasoning_result
        except Exception as e:
            logger.error(f"Ошибка в процессе рассуждения: {str(e)}", exc_info=True)

            # Попытка fallback рассуждения с упрощенной схемой
            if self.error_count < self.max_consecutive_errors:
                logger.info("Попытка упрощенного рассуждения после ошибки")
                return {
                    "analysis": {
                        "current_situation": "Ошибка в основном процессе рассуждения",
                        "progress_assessment": "Неизвестно",
                        "confidence": 0.3,
                        "errors_detected": True,
                        "consecutive_errors": self.error_count + 1,
                        "execution_time": context_analysis.get("execution_time_seconds", 0),
                        "no_progress_steps": context_analysis.get("no_progress_steps", 0)
                    },
                    "recommended_action": {
                        "action_type": "execute_capability",
                        "capability_name": "book_library.search_books",  # Используем доступную capability
                        "parameters": {"input": session_context.get_goal() or "Продолжить выполнение задачи"},
                        "reasoning": f"fallback после ошибки: {str(e)}"
                    },
                    "available_capabilities": available_capabilities,  # ← Передаем доступные capability
                    "needs_rollback": False
                }
            else:
                raise

    async def _make_decision_from_reasoning(
        self,
        session_context,
        reasoning_result: Dict[str, Any]
    ) -> BehaviorDecision:
        """Принимает решение о следующем действии на основе анализа контекста."""
        try:
            # Проверка условия остановки (согласно контракту behavior.react.think)
            if reasoning_result.get("stop_condition", False):
                return BehaviorDecision(
                    action=BehaviorDecisionType.STOP,
                    reason=reasoning_result.get("stop_reason", "goal_achieved")
                )

            # По умолчанию - выполнение capability из decision.next_action
            return self._build_capability_decision(session_context, reasoning_result)

        except Exception as e:
            logger.error(f"Ошибка при построении решения из рассуждения: {str(e)}", exc_info=True)
            raise

    def _build_rollback_decision(self, session_context, reasoning_result: Dict[str, Any]) -> BehaviorDecision:
        """Создает решение для отката."""
        # В новой схеме нет rollback_steps, используем stop_condition
        reason = reasoning_result.get("stop_reason", "rollback_requested")

        # Используем generic.execute как fallback для отката
        available_caps = reasoning_result.get("available_capabilities", [])

        capability = None
        for cap in available_caps:
            if cap.name == "generic.execute":
                capability = cap
                break

        if not capability:
            for cap in available_caps:
                if any(s.lower() == "react" for s in cap.supported_strategies or []):
                    capability = cap
                    break

        if not capability:
            return BehaviorDecision(
                action=BehaviorDecisionType.STOP,
                reason="no_capability_for_rollback"
            )

        return BehaviorDecision(
            action=BehaviorDecisionType.ACT,
            capability_name="generic.execute",
            parameters={
                "input": reasoning_result.get("analysis", {}).get("current_state", session_context.get_goal()),
                "context": f"Откат из-за: {reason}"
            },
            reason=f"rollback_{reason}"
        )

    def _build_capability_decision(self, session_context, reasoning_result: Dict[str, Any]) -> BehaviorDecision:
        """Создает решение для выполнения capability."""
        # Согласно контракту: decision.next_action = capability_name
        decision = reasoning_result.get("decision", {})
        capability_name = decision.get("next_action") or "generic.execute"
        parameters = decision.get("parameters", {})
        reasoning = decision.get("reasoning", "capability_execution")

        # Вместо прямого доступа к runtime.system, используем переданные capability
        available_caps = reasoning_result.get("available_capabilities", [])
        
        logger.error(f"_build_capability_decision: available_capabilities count={len(available_caps)}, names={[c.name for c in available_caps]}, requested capability_name={capability_name}")

        capability = None
        for cap in available_caps:
            if cap.name == capability_name and any(s.lower() == "react" for s in cap.supported_strategies or []):
                capability = cap
                break

        if not capability:
            # Если указанная capability недоступна, ищем первую доступную
            for cap in available_caps:
                if any(s.lower() == "react" for s in cap.supported_strategies or []):
                    capability = cap
                    capability_name = cap.name
                    logger.warning(f"Capability '{decision.get('capability_name')}' не найдена или недоступна, используем альтернативу: {cap.name}")
                    break

        if not capability:
            logger.error(f"_build_capability_decision: НЕТ ДОСТУПНЫХ CAPABILITY. available_caps={[c.name for c in available_caps]}")
            raise ValueError(f"Нет доступных capability для выполнения действия")

        # Валидация и корректировка параметров
        logger.info(f"=== ВАЛИДАЦИЯ ПАРАМЕТРОВ ===")
        logger.info(f"capability: {capability.name}")
        logger.info(f"raw_params: {parameters}")
        
        validated_params = self.schema_validator.validate_parameters(
            capability=capability,
            raw_params=parameters,
            context=json.dumps({
                "goal": reasoning_result.get("analysis", {}).get("current_situation", ""),
                "progress": reasoning_result.get("analysis", {}).get("progress_assessment", "")
            })
            # system_context больше не передается, так как мы изолированы
        )

        logger.info(f"validated_params: {validated_params}")
        
        if not validated_params:
            # Попытка создать минимально необходимые параметры
            validated_params = {"input": session_context.get_goal() or "Продолжить выполнение задачи"}
            logger.warning(f"Параметры не прошли валидацию, используем минимальный набор: {validated_params}")
        else:
            logger.info(f"✅ Параметры успешно валидированы")

        logger.info(f"=== РЕШЕНИЕ ===")
        logger.info(f"action: {BehaviorDecisionType.ACT}")
        logger.info(f"capability_name: {capability_name}")
        logger.info(f"parameters: {validated_params}")
        logger.info(f"reason: {reasoning}")

        return BehaviorDecision(
            action=BehaviorDecisionType.ACT,
            capability_name=capability_name,
            parameters=validated_params,
            reason=reasoning
        )

    async def _create_fallback_decision(self, session_context, reason: str) -> BehaviorDecision:
        """Создает fallback-решение при ошибках."""
        # Вместо прямого доступа к runtime.system, полагаемся на переданные capability
        # В новой архитектуре получаем capability из другого источника
        available_caps = []  # Возвращаем пустой список, так как в session_context нет такого метода
        
        for cap in available_caps:
            if any(s.lower() == "react" for s in cap.supported_strategies or []):
                return BehaviorDecision(
                    action=BehaviorDecisionType.ACT,
                    capability_name=cap.name,
                    parameters={
                        "input": session_context.get_goal() or "Продолжить выполнение задачи",
                        "context": reason
                    },
                    reason=f"fallback_{reason}"
                )

        # Критический fallback - остановка
        logger.critical("Нет доступных capability для реактивной стратегии. Принудительная остановка.")
        return BehaviorDecision(
            action=BehaviorDecisionType.STOP,
            reason=f"emergency_stop_no_capabilities_{reason}"
        )