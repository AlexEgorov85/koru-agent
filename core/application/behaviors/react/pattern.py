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
from datetime import datetime
from typing import Any, Dict, List, Optional
from core.application.behaviors.base_behavior_pattern import BaseBehaviorPattern
from core.application.behaviors.base import BehaviorDecision, BehaviorDecisionType
from core.application.agent.strategies.react.schema_validator import SchemaValidator
from core.application.agent.strategies.react.utils import analyze_context
from core.models.schemas.react_models import ReasoningResult
from core.application.agent.strategies.react.validation import validate_reasoning_result
from core.retry_policy.retry_and_error_policy import RetryPolicy
from core.models.data.capability import Capability
from core.models.types.llm_types import LLMRequest, StructuredOutputConfig, LLMResponse
from core.models.errors import InfrastructureError


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

    # Явная декларация зависимостей
    DEPENDENCIES = ["prompt_service", "contract_service"]

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

        # EventBusLogger для логирования через шину событий
        self.event_bus_logger = None  # Будет инициализирован когда будет доступен event_bus

        # Примечание: Промпты и контракты загружаются через BaseComponent.initialize()
        # и доступны в self.prompts / self.output_contracts

    @property
    def llm_orchestrator(self):
        """
        Получение LLMOrchestrator из application_context.
        
        Возвращает orchestrator если доступен, иначе None.
        """
        if self.application_context and hasattr(self.application_context, 'llm_orchestrator'):
            return self.application_context.llm_orchestrator
        return None

    def _init_event_bus_logger(self):
        """Инициализирует EventBusLogger когда становится доступен event_bus."""
        if self.application_context and hasattr(self.application_context, 'infrastructure_context'):
            from core.infrastructure.logging import EventBusLogger
            self.event_bus_logger = EventBusLogger(
                event_bus=self.application_context.infrastructure_context.event_bus,
                session_id="system",
                agent_id="system",
                component="react_pattern.think"
            )

    async def _execute_llm_with_orchestrator(
        self,
        llm_request: LLMRequest,
        llm_provider: Any,
        timeout: float,
        session_context: 'SessionContext'
    ) -> tuple[bool, Any, str]:
        """
        Выполнение LLM вызова через LLMOrchestrator.
        
        АРХИТЕКТУРНОЕ ПРЕИМУЩЕСТВО:
        - При таймауте не бросает исключение, а возвращает LLMResponse с error
        - Фоновый поток завершается корректно, результат не теряется
        - Метрики и мониторинг "брошенных" вызовов
        
        ПАРАМЕТРЫ:
        - llm_request: Запрос к LLM
        - llm_provider: LLM провайдер
        - timeout: Таймаут ожидания
        - session_context: Контекст сессии
        
        ВОЗВРАЩАЕТ:
        - tuple[bool, Any, str]: (успех, ответ, ошибка)
        """
        orchestrator = self.llm_orchestrator
        
        if not orchestrator:
            # Fallback: прямой вызов без оркестратора (для обратной совместимости)
            await self._log("debug", "LLMOrchestrator недоступен, используем прямой вызов")
            return False, None, "orchestrator_not_available"
        
        try:
            # Выполнение через оркестратор
            response = await orchestrator.execute(
                request=llm_request,
                timeout=timeout,
                provider=llm_provider,
                capability_name="react_pattern.think"
            )
            
            # Проверка на ошибку в ответе
            if response.finish_reason == "error":
                error_msg = "Неизвестная ошибка LLM"
                if response.metadata:
                    if isinstance(response.metadata, dict):
                        error_msg = response.metadata.get('error', error_msg)
                    elif isinstance(response.metadata, str):
                        error_msg = response.metadata
                
                # Логируем ошибку
                await self._log("error", f"LLM вызов через оркестратор вернул ошибку: {error_msg}")

                # Оркестратор уже опубликовал событие об ошибке
                return False, None, error_msg
            
            # Успешный ответ
            await self._log("info", f"LLM вызов через оркестратор завершён успешно")
            
            # Оборачиваем в формат ожидаемый _perform_structured_reasoning
            # Orchestrator возвращает LLMResponse, а нам нужно dict с raw_response
            structured_response = {
                'raw_response': response,
                'content': response.content,
                'metadata': response.metadata
            }
            
            return True, structured_response, ""
            
        except Exception as e:
            # Исключение из оркестратора (должно быть редко)
            error_msg = f"Исключение из LLMOrchestrator: {type(e).__name__}: {str(e)}"
            await self._log("error", error_msg)

            # Оркестратор уже опубликовал событие об ошибке
            return False, None, error_msg

    async def _log(self, level: str, message: str, **extra_data):
        """
        Универсальный метод логирования через EventBusLogger.

        ПАРАМЕТРЫ:
        - level: уровень логирования ('info', 'debug', 'warning', 'error')
        - message: сообщение
        - **extra_data: дополнительные данные
        """
        # Инициализируем event_bus_logger если ещё не инициализирован
        if self.event_bus_logger is None:
            self._init_event_bus_logger()

        if self.event_bus_logger:
            log_method = getattr(self.event_bus_logger, level, None)
            if log_method:
                await log_method(message, **extra_data)

    def _log_llm_trace(self, prompt: str, response: Any, context: Optional['SessionContext'] = None):
        """
        ЛОГИРОВАНИЕ ВЫЗОВА LLM ДЛЯ ОТЛАДКИ.
        
        ВЫВОДИТ:
        - PROMPT: полный текст промпта
        - RESPONSE: сырой ответ от LLM
        - PARSED DECISION: распарсенное решение
        
        ИСПОЛЬЗУЕТСЯ: только в development/debug режиме
        """
        print("\n" + "=" * 80)
        print("━━━━━━━━ LLM CALL ━━━━━━━━")
        print("=" * 80)
        
        # PROMPT
        print(f"\n📝 PROMPT ({len(prompt)} символов)\n")
        print("-" * 60)
        # Показываем первые 2000 символов промпта чтобы не засорять консоль
        prompt_preview = prompt[:2000] if len(prompt) > 2000 else prompt
        print(prompt_preview)
        if len(prompt) > 2000:
            print(f"\n... (ещё {len(prompt) - 2000} символов)")
        
        # RESPONSE
        print("\n" + "-" * 60)
        print("💬 RESPONSE\n")
        print("-" * 60)
        
        # Извлекаем сырой ответ
        if isinstance(response, dict):
            if 'raw_response' in response:
                raw = response['raw_response']
                if hasattr(raw, 'content'):
                    response_text = raw.content
                elif isinstance(raw, dict):
                    response_text = str(raw)
                else:
                    response_text = str(raw) if raw else '<пустой ответ>'
            elif 'content' in response:
                response_text = response['content']
            else:
                response_text = str(response)
        elif hasattr(response, 'content'):
            response_text = response.content
        elif hasattr(response, 'raw_response'):
            response_text = response.raw_response
        else:
            response_text = str(response) if response else '<пустой ответ>'
        
        # Показываем первые 1500 символов ответа
        response_preview = response_text[:1500] if len(response_text) > 1500 else response_text
        print(response_preview)
        if len(response_text) > 1500:
            print(f"\n... (ещё {len(response_text) - 1500} символов)")
        
        # Пытаемся распарсить решение для отображения
        print("\n" + "-" * 60)
        print("🎯 PARSED DECISION\n")
        print("-" * 60)
        
        try:
            # Пытаемся извлечь решение из response
            decision_data = None
            
            if isinstance(response, dict):
                if 'raw_response' in response and hasattr(response['raw_response'], 'model_dump'):
                    # Pydantic модель
                    decision_data = response['raw_response'].model_dump()
                elif 'parsed_content' in response:
                    decision_data = response['parsed_content']
                elif 'content' in response and isinstance(response['content'], dict):
                    decision_data = response['content']
            elif hasattr(response, 'parsed_content'):
                decision_data = response.parsed_content
            elif hasattr(response, 'model_dump'):
                decision_data = response.model_dump()
            
            if decision_data:
                # Извлекаем ключевые поля
                decision = decision_data.get('decision', {})
                action_type = decision.get('next_action', 'N/A')
                reasoning = decision.get('reasoning', 'N/A')[:200] if decision.get('reasoning') else 'N/A'
                
                print(f"action_type: {action_type}")
                print(f"reasoning: {reasoning}")
                
                # Показываем доступные capability
                if 'available_capabilities' in decision_data:
                    caps = decision_data['available_capabilities']
                    if isinstance(caps, list) and len(caps) > 0:
                        print(f"\n📦 Доступно capabilities: {len(caps)}")
                        for cap in caps[:5]:  # Показываем первые 5
                            cap_name = cap.name if hasattr(cap, 'name') else str(cap)
                            print(f"  - {cap_name}")
                        if len(caps) > 5:
                            print(f"  ... и ещё {len(caps) - 5}")
            else:
                print("Не удалось распарсить решение")
                print(f"Raw response type: {type(response)}")
                
        except Exception as e:
            print(f"⚠️ Ошибка парсинга решения: {e}")
        
        # Контекст
        if context:
            print("\n" + "-" * 60)
            print("📌 CONTEXT\n")
            print("-" * 60)
            print(f"goal: {context.get_goal() if hasattr(context, 'get_goal') else 'N/A'}")
            if hasattr(context, 'current_step'):
                print(f"step: {context.current_step}")
        
        print("\n" + "=" * 80)
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print("=" * 80 + "\n")

    def _load_reasoning_resources(self) -> bool:
        """
        Загружает system prompt для рассуждения из автоматически разделённых промптов.

        ВОЗВРАЩАЕТ:
        - bool: True если успешно загружено
        """
        # Если уже загружено, ничего не делаем
        if self.reasoning_prompt_template and self.reasoning_schema and self.system_prompt_template:
            return True

        try:
            # ← НОВОЕ: Используем автоматически разделённые промпты
            # system_prompts содержит {base_capability: Prompt}
            if 'behavior.react.think' in self.system_prompts:
                system_prompt_obj = self.system_prompts['behavior.react.think']
                if hasattr(system_prompt_obj, 'content') and system_prompt_obj.content:
                    self.system_prompt_template = system_prompt_obj.content

            # user_prompts содержит {base_capability: Prompt}
            if 'behavior.react.think' in self.user_prompts:
                user_prompt_obj = self.user_prompts['behavior.react.think']
                if hasattr(user_prompt_obj, 'content') and user_prompt_obj.content:
                    self.reasoning_prompt_template = user_prompt_obj.content

            # Fallback: ищем в prompts (для обратной совместимости)
            if not self.system_prompt_template and self.prompts:
                if "behavior.react.think.system" in self.prompts:
                    system_prompt_obj = self.prompts["behavior.react.think.system"]
                    if hasattr(system_prompt_obj, 'content') and system_prompt_obj.content:
                        self.system_prompt_template = system_prompt_obj.content

            if not self.reasoning_prompt_template and self.prompts:
                if "behavior.react.think" in self.prompts:
                    prompt_obj = self.prompts["behavior.react.think"]
                    if hasattr(prompt_obj, 'content') and prompt_obj.content:
                        self.reasoning_prompt_template = prompt_obj.content

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
                else:
                    # Fallback: берём первую доступную схему
                    for cap_name, schema_cls in self.output_contracts.items():
                        if schema_cls:
                            if hasattr(schema_cls, 'model_json_schema'):
                                self.reasoning_schema = schema_cls.model_json_schema()
                            else:
                                self.reasoning_schema = schema_cls
                            break

            # Fallback на модель если контракт не найден
            if not self.reasoning_schema:
                self.reasoning_schema = ReasoningResult.model_json_schema()

            return True
        except Exception as e:
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
            self.event_bus_logger.warning_sync("[ReAct] reasoning_prompt_template не загружен, используем минимальный fallback")
            return self._build_minimal_fallback_prompt(prompt_context)

    def _build_input_context(self, context_analysis: Dict[str, Any], available_capabilities: List[Capability]) -> str:
        """
        Формирует {input} секцию для промпта.

        ПАРАМЕТРЫ:
        - context_analysis: анализ контекста
        - available_capabilities: доступные capability (объекты Capability)

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
            # Поддержка как объектов Capability, так и словарей
            name = cap.name if hasattr(cap, 'name') else cap.get('name', 'unknown')
            desc = cap.description if hasattr(cap, 'description') else cap.get('description', 'no description')
            parts.append(f"  - {name}: {desc}")

        return "\n".join(parts)

    def _format_available_tools(self, available_capabilities: List[Capability]) -> str:
        """
        Форматирует список доступных инструментов с параметрами.

        ПАРАМЕТРЫ:
        - available_capabilities: список capability (объекты Capability)

        ВОЗВРАЩАЕТ:
        - str: отформатированный список инструментов с параметрами
        """
        lines = []
        for cap in available_capabilities:
            # Поддержка как объектов Capability, так и словарей
            name = cap.name if hasattr(cap, 'name') else cap.get('name', 'unknown')
            description = cap.description if hasattr(cap, 'description') else cap.get('description', 'no description')

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
        Используется ТОЛЬКО если system_prompt_template не загружен из реестра.

        ВОЗВРАЩАЕТ:
        - str: системный промпт
        """
        return """Ты — модуль рассуждения ReAct. Верни JSON: {"thought": "...", "decision": {"next_action": "...", "parameters": {}}, "stop_condition": false}"""

    async def analyze_context(
        self,
        session_context: 'SessionContext',
        available_capabilities: List[Capability],
        context_analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Анализ контекста без принятия решений"""
        await self._log("debug", f"[ReAct] analyze_context: received available_capabilities count={len(available_capabilities)}")

        # Если available_capabilities пустой, получаем их из ApplicationContext
        if not available_capabilities and self.application_context:
            await self._log("debug", "[ReAct] analyze_context: available_capabilities пуст, получаем из ApplicationContext")
            available_capabilities = await self.application_context.get_all_capabilities()
            await self._log("debug", f"[ReAct] analyze_context: получено {len(available_capabilities)} capability")

        # Регистрируем схемы для всех capability в SchemaValidator
        self._register_capability_schemas(available_capabilities)

        # Выполняем анализ контекста сессии
        analysis = analyze_context(session_context)

        # Добавляем информацию о доступных capability
        # Фильтрация только по supported_strategies (без хардкода навыков)
        analysis["available_capabilities"] = self._filter_capabilities(
            available_capabilities
        )

        await self._log("debug", f"[ReAct] analyze_context: after filtering available_capabilities count={len(analysis['available_capabilities'])}")

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
            self.event_bus_logger.warning_sync("[ReAct] _register_capability_schemas: application_context не доступен")
            return

        self.event_bus_logger.info_sync(f"[ReAct] === РЕГИСТРАЦИЯ СХЕМ ===")
        self.event_bus_logger.info_sync(f"[ReAct] Всего capability: {len(available_capabilities)}")

        # Получаем все input схемы из контекста
        for cap in available_capabilities:
            # Пытаемся получить схему из input_contracts кэша
            # Формат ключа: capability_name (например, "book_library.execute_script")
            schema = None

            # Проверяем, есть ли схема в кэше input_contracts
            if hasattr(self, 'input_contracts') and cap.name in self.input_contracts:
                schema = self.input_contracts[cap.name]
                self.event_bus_logger.info_sync(f"Найдена схема в input_contracts для {cap.name}")
            elif self.application_context.use_data_repository and self.application_context.data_repository:
                # Пытаемся получить схему из DataRepository
                try:
                    # Получаем версию контракта из meta capability
                    contract_version = cap.meta.get('contract_version', 'v1.0.0')
                    schema = self.application_context.data_repository.get_contract_schema(
                        cap.name,
                        contract_version,
                        "input"
                    )
                except Exception as e:
                    self.event_bus_logger.debug_sync(f"Не удалось получить схему для {cap.name}: {e}")

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
                    self.event_bus_logger.debug_sync(f"✅ Зарегистрирована схема для {cap.name}: {params_schema}")
                else:
                    self.event_bus_logger.debug_sync(f"ℹ️ Схема для {cap.name} не имеет параметров")
            else:
                self.event_bus_logger.debug_sync(f"Схема не найдена для {cap.name}")

    async def generate_decision(
        self,
        session_context: 'SessionContext',
        available_capabilities: List[Capability],
        context_analysis: Dict[str, Any]
    ) -> BehaviorDecision:
        """Генерация решения на основе анализа."""
        # Логирование начала через EventBusLogger
        await self._log("info", "generate_decision: started",
                       step=session_context.current_step if hasattr(session_context, 'current_step') else 0)

        try:
            # 1. Структурированное рассуждение через LLM
            reasoning_result = await self._perform_structured_reasoning(
                session_context=session_context,
                context_analysis=context_analysis,
                available_capabilities=available_capabilities
            )
            # Логирование результата рассуждения
            await self._log("debug", f"generate_decision: reasoning_result получен",
                           decision=reasoning_result.get('decision', {}))
            
            # 2. Принятие решения на основе рассуждения
            decision = await self._make_decision_from_reasoning(
                session_context=session_context,
                reasoning_result=reasoning_result,
                available_capabilities=available_capabilities  # КРИТИЧНО: передаём available_capabilities
            )
            
            # Логирование финального решения
            await self._log("info", f"generate_decision: decision получен",
                           action=decision.action.value,
                           capability_name=decision.capability_name)
            
            # 3. Сброс счётчика ошибок при успешном решении
            self.error_count = 0
            
            return decision
            
        except Exception as e:
            # Логирование ошибки через EventBusLogger
            await self._log("error", f"generate_decision: критическая ошибка",
                           error=str(e),
                           exc_info=True)
            
            self.error_count += 1
            
            # Fallback при множественных ошибках
            if self.error_count >= self.max_consecutive_errors:
                return BehaviorDecision(
                    action=BehaviorDecisionType.SWITCH,
                    next_pattern="fallback.v1.0.0",
                    reason=f"too_many_errors:{self.error_count}"
                )
            
            # Базовый fallback
            return await self._create_fallback_decision(
                session_context=session_context,
                reason=f"critical_error:{str(e)}"
            )

    async def _perform_structured_reasoning(
        self,
        session_context,
        context_analysis: Dict[str, Any],
        available_capabilities: List[Capability]
    ) -> Dict[str, Any]:
        """Выполняет структурированное рассуждение через LLM."""
        try:
            # Загружаем промпт и контракт из кэша BaseComponent
            load_result = self._load_reasoning_resources()

            if not load_result or not self.reasoning_prompt_template:
                # Fallback: создаем упрощенную версию рассуждения
                await self._log("warning", "Промпт не загружен, используем упрощенную логику рассуждения")
                
                # Определяем первую доступную capability
                fallback_capability = "final_answer.generate"
                if available_capabilities:
                    fallback_capability = available_capabilities[0].name if hasattr(available_capabilities[0], 'name') else list(available_capabilities[0].values())[0] if isinstance(available_capabilities[0], dict) else "final_answer.generate"

                return {
                    "analysis": {
                        "current_situation": "Промпт не загружен",
                        "progress_assessment": "Неизвестно",
                        "confidence": 0.5,
                        "errors_detected": False,
                        "consecutive_errors": self.error_count if hasattr(self, 'error_count') else 0,
                        "execution_time": context_analysis.get("execution_time_seconds", 0),
                        "no_progress_steps": context_analysis.get("no_progress_steps", 0)
                    },
                    "decision": {
                        "next_action": fallback_capability,
                        "reasoning": "Промпт недоступен, используем fallback",
                        "parameters": {"query": session_context.get_goal() if session_context else "Продолжить выполнение задачи"}
                    },
                    "available_capabilities": available_capabilities,
                    "needs_rollback": False
                }

            # Флаг для гарантии вызова LLM
            llm_was_called = False

            # Рендерим промпт из шаблона (передаём оригинальные Capability объекты)
            reasoning_prompt = self._render_reasoning_prompt(
                context_analysis=context_analysis,
                available_capabilities=available_capabilities
            )

            start_time = time.time()

            # Генерация структурированного ответа через LLM
            llm_provider = None
            if self.application_context:
                llm_provider = self.application_context.get_provider("default_llm")

            if llm_provider is None:
                # Fallback: создаем упрощенную версию рассуждения
                await self._log("warning", "LLM провайдер недоступен, используем упрощенную логику рассуждения")

                # Оркестратор опубликует событие при следующем вызове
                # Определяем первую доступную capability
                fallback_capability = "book_library.search_books"
                if available_capabilities:
                    fallback_capability = available_capabilities[0].name

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
                    "decision": {
                        "next_action": fallback_capability,
                        "reasoning": "LLM недоступен, используем fallback",
                        "parameters": {"query": session_context.get_goal() or "Продолжить выполнение задачи"}
                    },
                    "available_capabilities": available_capabilities,
                    "needs_rollback": False
                }

            # === LLM БУДЕТ ВЫЗВАН ===
            llm_was_called = True

            # Создаем LLMRequest для структурированного вывода
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

            # === УСТАНОВКА КОНТЕКСТА ВЫЗОВА В LLM ПРОВАЙДЕРЕ ===
            # correlation_id будет сгенерирован автоматически в BaseLLMProvider
            if hasattr(llm_provider, 'set_call_context'):
                # Получаем agent_id из session_context или используем значение по умолчанию
                current_agent_id = getattr(session_context, 'agent_id', 'system') if session_context else 'system'
                llm_provider.set_call_context(
                    event_bus=self.application_context.infrastructure_context.event_bus,
                    session_id=getattr(session_context, 'session_id', 'unknown'),
                    agent_id=current_agent_id,
                    component="react_pattern",
                    phase="think",
                    goal=session_context.get_goal() if session_context else 'unknown'
                )

            await self._log("info", f"🧠 Запуск рассуждения ReAct | Цель: {session_context.get_goal() if session_context else 'unknown'}")
            await self._log("info", f"Длина промпта: {len(reasoning_prompt)} символов")

            # === ВЫЗОВ LLM ЧЕРЕЗ ORCHESTRATOR (ПРЕДОЧТИТЕЛЬНО) ===
            # LLMOrchestrator обеспечивает:
            # 1. Управление таймаутами без потерь результатов
            # 2. Реестр активных вызовов с метриками
            # 3. Корректное завершение фоновых потоков
            # 4. Мониторинг "брошенных" вызовов
            
            import asyncio
            from asyncio import TimeoutError as AsyncTimeoutError
            
            llm_timeout = getattr(llm_provider, 'timeout_seconds', 120.0)
            max_retries = 3
            retry_delay = 5.0
            retry_count = 0
            response = None
            
            while retry_count < max_retries:
                # Попытка вызова через LLMOrchestrator
                orchestrator = self.llm_orchestrator
                
                if orchestrator:
                    # === ВЫЗОВ ЧЕРЕЗ ORCHESTRATOR ===
                    await self._log("info", f"[Попытка {retry_count + 1}/{max_retries}] Вызов через LLMOrchestrator с таймаутом {llm_timeout}с...")
                    
                    success, resp, error = await self._execute_llm_with_orchestrator(
                        llm_request=llm_request,
                        llm_provider=llm_provider,
                        timeout=llm_timeout,
                        session_context=session_context
                    )
                    
                    if success:
                        response = resp
                        await self._log("info", f"[Попытка {retry_count + 1}] LLM ответ получен через оркестратор")
                        break
                    else:
                        # Ошибка от оркестратора
                        retry_count += 1
                        await self._log("warning", f"[Попытка {retry_count}] Ошибка оркестратора: {error}")
                        
                        if retry_count < max_retries:
                            await self._log("info", f"Повторная попытка через {retry_delay}с...")
                            await asyncio.sleep(retry_delay)
                            retry_delay *= 1.5
                        else:
                            # === ТАЙМАУТ ПОСЛЕ ВСЕХ ПОПЫТОК ===
                            error_msg = f"LLM вызов не удался после {max_retries} попыток через оркестратор"
                            await self._log("error", error_msg)

                            # Оркестратор уже опубликовал событие о таймауте
                            # Возвращаем fallback вместо исключения
                            return {
                                "analysis": {
                                    "current_situation": f"LLM таймаут после {max_retries} попыток",
                                    "progress_assessment": "Неизвестно",
                                    "confidence": 0.3,
                                    "errors_detected": True,
                                    "consecutive_errors": self.error_count + 1,
                                    "execution_time": context_analysis.get("execution_time_seconds", 0),
                                    "no_progress_steps": context_analysis.get("no_progress_steps", 0)
                                },
                                "decision": {
                                    "next_action": "book_library.search_books",
                                    "reasoning": f"fallback после LLM таймаута",
                                    "parameters": {"query": session_context.get_goal() if session_context else "Продолжить"}
                                },
                                "available_capabilities": available_capabilities,
                                "needs_rollback": False
                            }

                else:
                    # === ORCHESTRATOR НЕ ДОСТУПЕН — КРИТИЧЕСКАЯ ОШИБКА ===
                    error_msg = "LLMOrchestrator недоступен — критическая ошибка инфраструктуры"
                    await self._log("error", error_msg)
                    
                    # Возвращаем fallback вместо попытки прямого вызова
                    return {
                        "analysis": {
                            "current_situation": "LLMOrchestrator недоступен",
                            "progress_assessment": "Неизвестно",
                            "confidence": 0.0,
                            "errors_detected": True,
                            "consecutive_errors": self.error_count + 1,
                            "execution_time": context_analysis.get("execution_time_seconds", 0),
                            "no_progress_steps": context_analysis.get("no_progress_steps", 0)
                        },
                        "decision": {
                            "next_action": "final_answer.generate",
                            "reasoning": "Инфраструктурная ошибка — используем fallback",
                            "parameters": {"query": session_context.get_goal() or "Продолжить"}
                        },
                        "available_capabilities": available_capabilities,
                        "needs_rollback": False
                    }

            # === ПРОВЕРКА НА ОШИБКУ LLM ===
            # Обрабатываем случаи когда LLM вернул ошибку (таймаут, пустой контент и т.д.)
            # Детальное логирование выполняется на уровне провайдера
            llm_response = None
            if isinstance(response, dict) and 'raw_response' in response:
                raw_resp = response['raw_response']
                if hasattr(raw_resp, 'finish_reason'):
                    llm_response = raw_resp
            elif hasattr(response, 'finish_reason'):
                llm_response = response
            elif hasattr(response, 'content') and hasattr(response, 'metadata'):
                # LLMResponse object
                llm_response = response

            if llm_response is not None:
                # Проверяем finish_reason на ошибку
                if getattr(llm_response, 'finish_reason', None) == 'error':
                    error_msg = "Неизвестная ошибка LLM"
                    if hasattr(llm_response, 'metadata') and llm_response.metadata:
                        if isinstance(llm_response.metadata, dict):
                            error_msg = llm_response.metadata.get('error', error_msg)
                        elif isinstance(llm_response.metadata, str):
                            error_msg = llm_response.metadata

                    await self._log("error", f"LLM вернул ошибку: {error_msg}")

                    # Оркестратор уже опубликовал событие об ошибке
                    # Возвращаем fallback решение
                    return {
                        "analysis": {
                            "current_situation": f"Ошибка LLM: {error_msg}",
                            "progress_assessment": "Неизвестно",
                            "confidence": 0.3,
                            "errors_detected": True,
                            "consecutive_errors": self.error_count + 1,
                            "execution_time": context_analysis.get("execution_time_seconds", 0),
                            "no_progress_steps": context_analysis.get("no_progress_steps", 0)
                        },
                        "recommended_action": {
                            "action_type": "execute_capability",
                            "capability_name": "book_library.search_books",
                            "parameters": {"input": session_context.get_goal() or "Продолжить выполнение задачи"},
                            "reasoning": f"fallback после ошибки LLM: {error_msg}"
                        },
                        "available_capabilities": available_capabilities,
                        "needs_rollback": False
                    }

                # Проверяем metadata на наличие ошибки
                if hasattr(llm_response, 'metadata') and llm_response.metadata and 'error' in llm_response.metadata:
                    error_msg = llm_response.metadata['error']
                    await self._log("error", f"LLM вернул ошибку в metadata: {error_msg}")

                    # Оркестратор уже опубликовал событие об ошибке
                    return {
                        "analysis": {
                            "current_situation": f"Ошибка LLM: {error_msg}",
                            "progress_assessment": "Неизвестно",
                            "confidence": 0.3,
                            "errors_detected": True,
                            "consecutive_errors": self.error_count + 1,
                            "execution_time": context_analysis.get("execution_time_seconds", 0),
                            "no_progress_steps": context_analysis.get("no_progress_steps", 0)
                        },
                        "recommended_action": {
                            "action_type": "execute_capability",
                            "capability_name": "book_library.search_books",
                            "parameters": {"input": session_context.get_goal() or "Продолжить выполнение задачи"},
                            "reasoning": f"fallback после ошибки LLM: {error_msg}"
                        },
                        "available_capabilities": available_capabilities,
                        "needs_rollback": False
                    }

                # Проверяем на пустой или обрезанный ответ
                content = getattr(llm_response, 'content', '')
                if not content or (isinstance(content, str) and len(content.strip()) == 0):
                    await self._log("warning", "LLM вернул пустой ответ!")

            # correlation_id больше не публикуется здесь — это делает BaseLLMProvider
            # Ответ уже опубликован в событии LLM_RESPONSE_RECEIVED с правильным correlation_id

            # === LLM TRACE: ЛОГИРОВАНИЕ ВЫЗОВА LLM ===
            self._log_llm_trace(prompt=reasoning_prompt, response=response, context=session_context)

            # Обработка ответа для валидации
            if isinstance(response, dict) and 'raw_response' in response:
                result = response['raw_response']
            elif hasattr(response, 'content'):
                result = response.content
                # Если content это строка, пробуем распарсить как JSON
                if isinstance(result, str):
                    try:
                        result = json.loads(result)
                    except (json.JSONDecodeError, ValueError):
                        await self._log("warning", f"LLM вернул невалидный JSON: {result[:200]}...")
                        # Возвращаем fallback результат
                        return {
                            "analysis": {
                                "current_situation": "Ошибка парсинга ответа LLM",
                                "progress_assessment": "Неизвестно",
                                "confidence": 0.3,
                                "errors_detected": True,
                                "consecutive_errors": self.error_count + 1,
                            },
                            "decision": {
                                "next_action": "book_library.search_books",
                                "reasoning": "fallback после ошибки парсинга JSON",
                                "parameters": {"query": session_context.get_goal() if session_context else "Продолжить"}
                            },
                            "available_capabilities": available_capabilities,
                            "needs_rollback": False
                        }
            else:
                result = response

            reasoning_result = validate_reasoning_result(result)

            # Добавляем available_capabilities в результат для последующего использования
            reasoning_result['available_capabilities'] = available_capabilities

            # Логирование результата для отладки
            await self._log("info", f"=== РЕЗУЛЬТАТ РАССУЖДЕНИЯ ===")
            await self._log("debug", f"decision: {reasoning_result.get('decision', {})}")
            await self._log("debug", f"next_action: {reasoning_result.get('decision', {}).get('next_action', 'NOT FOUND')}")
            await self._log("debug", f"parameters: {reasoning_result.get('decision', {}).get('parameters', {})}")
            await self._log("info", f"===========================")

            self.last_reasoning_time = time.time() - start_time
            await self._log("debug", f"Структурированное рассуждение выполнено за {self.last_reasoning_time:.2f} секунд")
            
            # ГАРАНТИЯ: LLM должен быть вызван
            if not llm_was_called:
                raise InfrastructureError(
                    "LLM was not called in _perform_structured_reasoning - ReAct pattern violation"
                )
            
            return reasoning_result
        except Exception as e:
            error_msg = f"Ошибка в процессе рассуждения: {str(e)}"
            await self._log("error", error_msg, exc_info=True)

            # Оркестратор опубликует событие при следующем вызове
            # Попытка fallback рассуждения с упрощенной схемо��
            if self.error_count < self.max_consecutive_errors:
                await self._log("info", "Попытка упрощенного рассуждения после ошибки")
                return {
                    "analysis": {
                        "current_situation": "Ошибка в основном процессе рассуждения",
                        "progress_assessment": "��еизвестно",
                        "confidence": 0.3,
                        "errors_detected": True,
                        "consecutive_errors": self.error_count + 1,
                        "execution_time": context_analysis.get("execution_time_seconds", 0),
                        "no_progress_steps": context_analysis.get("no_progress_steps", 0)
                    },
                    "recommended_action": {
                        "action_type": "execute_capability",
                        "capability_name": "book_library.search_books",  # Используем доступную capability
                        "parameters": {"input": session_context.get_goal() or "Пр��должить выполнение задачи"},
                        "reasoning": f"fallback после ошибки: {str(e)}"
                    },
                    "available_capabilities": available_capabilities,  # ← Передаем д��ступные capability
                    "needs_rollback": False
                }
            else:
                raise

    def _find_capability(
        self, 
        available_capabilities: List[Capability], 
        capability_name: str
    ) -> Optional[Capability]:
        """Поиск capability по имени в списке доступных."""
        
        # 1. Прямое совпадение по имени
        for cap in available_capabilities:
            if cap.name == capability_name:
                return cap
        
        # 2. Частичное совпадение (для совместимости)
        for cap in available_capabilities:
            if capability_name.lower() in cap.name.lower():
                return cap
        
        # 3. Поиск по supported_strategies
        for cap in available_capabilities:
            if any(s.lower() == "react" for s in (cap.supported_strategies or [])):
                if capability_name.lower() in cap.skill_name.lower():
                    return cap
        
        return None

    def _validate_parameters(
        self,
        capability: Capability,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Валидация параметров capability через SchemaValidator."""
        
        if not self.schema_validator:
            return parameters
        
        try:
            validated = self.schema_validator.validate_parameters(
                capability=capability,
                raw_params=parameters,
                context=json.dumps({
                    "goal": parameters.get("goal", ""),
                    "progress": parameters.get("progress", "")
                })
            )
            return validated if validated else parameters
        except Exception as e:
            # Fallback: возвращаем минимальные параметры
            self.event_bus_logger.warning_sync(f"Валидация параметров не удалась: {e}")
            return {"input": parameters.get("input", "Продолжить выполнение задачи")}

    async def _make_decision_from_reasoning(
        self,
        session_context,
        reasoning_result: Dict[str, Any],
        available_capabilities: List[Capability]  # НОВЫЙ параметр
    ) -> BehaviorDecision:
        """Принимает решение о следующем действии на основе анализа контекста."""

        try:
            # 1. Проверка условия остановки (согласно контракту behavior.react.think)
            if reasoning_result.get("stop_condition", False):
                return BehaviorDecision(
                    action=BehaviorDecisionType.STOP,
                    reason=reasoning_result.get("stop_reason", "goal_achieved")
                )

            # 2. Извлечение capability_name из decision.next_action ИЛИ recommended_action.capability_name
            decision = reasoning_result.get("decision", {})
            capability_name = decision.get("next_action")
            
            # Fallback: проверяем recommended_action (для упрощённой логики без LLM)
            if not capability_name:
                recommended_action = reasoning_result.get("recommended_action", {})
                capability_name = recommended_action.get("capability_name")

            # КРИТИЧЕСКАЯ ПРОВЕРКА: capability_name должен быть указан
            if not capability_name:
                await self._log("error", "LLM не ��ернул next_action в decision",
                               reasoning_result=reasoning_result)
                return BehaviorDecision(
                    action=BehaviorDecisionType.RETRY,
                    reason="LLM не вернул корре��т��ое действие"
                )
            
            # 3. Поиск capability в available_capabilities
            capability = self._find_capability(available_capabilities, capability_name)
            
            if not capability:
                await self._log("warning", f"Capability '{capability_name}' не найдена, используем fallback",
                               available_capabilities=[c.name for c in available_capabilities])
                
                # Fallback: используем первую доступную capability с поддержкой react
                for cap in available_capabilities:
                    if "react" in [s.lower() for s in (cap.supported_strategies or [])]:
                        capability = cap
                        capability_name = cap.name
                        break
                
                if not capability:
                    return BehaviorDecision(
                        action=BehaviorDecisionType.STOP,
                        reason="no_available_capabilities"
                    )
            
            # 4. Вали��ация и корректировка параметров через SchemaValidator
            parameters = decision.get("parameters", {})
            validated_params = self._validate_parameters(capability, parameters)
            
            # 5. Возвращаем решение с ЗАПОЛНЕННЫМ capability_name
            return BehaviorDecision(
                action=BehaviorDecisionType.ACT,
                capability_name=capability_name,  # ОБЯЗАТЕЛЬНО должно быть заполнено
                parameters=validated_params,
                reason=decision.get("reasoning", "capability_execution")
            )
            
        except Exception as e:
            await self._log("error", f"_make_decision_from_reasoning: ошибка",
                           error=str(e),
                           exc_info=True)
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
        """Создает ре��ение для выполнения capability."""
        # Согласно контракту: decision.next_action = capability_name
        decision = reasoning_result.get("decision", {})
        capability_name = decision.get("next_action") or "generic.execute"
        parameters = decision.get("parameters", {})
        reasoning = decision.get("reasoning", "capability_execution")

        # Вместо прямого доступа к runtime.system, используем переданные capability
        available_caps = reasoning_result.get("available_capabilities", [])

        self.event_bus_logger.info_sync(f"_build_capability_decision: available_capabilities count={len(available_caps)}, names={[c.name for c in available_caps]}, requested capability_name={capability_name}")

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
                    self.event_bus_logger.warning_sync(f"Capability '{decision.get('capability_name')}' не найдена или недоступна, используем альтернативу: {cap.name}")
                    break

        if not capability:
            self.event_bus_logger.error_sync(f"_build_capability_decision: НЕТ ДОСТУПНЫХ CAPABILITY. available_caps={[c.name for c in available_caps]}")
            raise ValueError(f"Нет доступных capability для выполнения действия")

        # Валидация и корректировка параметро��
        self.event_bus_logger.info_sync(f"=== ВАЛИДАЦИЯ ПАРАМЕТРОВ ===")
        self.event_bus_logger.info_sync(f"capability: {capability.name}")
        self.event_bus_logger.info_sync(f"raw_params: {parameters}")

        validated_params = self.schema_validator.validate_parameters(
            capability=capability,
            raw_params=parameters,
            context=json.dumps({
                "goal": reasoning_result.get("analysis", {}).get("current_situation", ""),
                "progress": reasoning_result.get("analysis", {}).get("progress_assessment", "")
            })
            # system_context больше не передается, так как мы изолированы
        )

        self.event_bus_logger.info_sync(f"validated_params: {validated_params}")

        if not validated_params:
            # Попытка создать минимально необходимые параметры
            validated_params = {"input": session_context.get_goal() or "Продолжить выполнение задачи"}
            self.event_bus_logger.warning_sync(f"Параметры не прошли валидацию, используем минимальный набор: {validated_params}")
        else:
            self.event_bus_logger.info_sync(f"✅ Параметры успешно валидированы")

        self.event_bus_logger.info_sync(f"=== РЕШЕНИЕ ===")
        self.event_bus_logger.info_sync(f"action: {BehaviorDecisionType.ACT}")
        self.event_bus_logger.info_sync(f"capability_name: {capability_name}")
        self.event_bus_logger.info_sync(f"parameters: {validated_params}")
        self.event_bus_logger.info_sync(f"reason: {reasoning}")

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
        available_caps = []  # Во�������вращаем п��стой список, так как в session_context нет такого метода

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
        await self._log("error", "Нет доступных capability для реактивной стратегии. Принудительная остановка.")
        return BehaviorDecision(
            action=BehaviorDecisionType.STOP,
            reason=f"emergency_stop_no_capabilities_{reason}"
        )
