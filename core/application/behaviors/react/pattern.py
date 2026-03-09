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
from core.application.agent.components.action_executor import ExecutionContext


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
        
        LLMOrchestrator обеспечивает:
        - Retry при ошибках парсинга
        - Валидацию через JSON Schema
        - Трассировку вызовов
        - Метрики и мониторинг
        
        Возвращает orchestrator если доступен, иначе None.
        """
        if self.application_context and hasattr(self.application_context, 'llm_orchestrator'):
            return self.application_context.llm_orchestrator
        return None
    
    @property
    def llm(self):
        """
        DEPRECATED: Прямой доступ к LLM провайдеру.
        Используйте llm_orchestrator для генерации с валидацией и retry.

        Возвращает LLM провайдер если доступен, иначе None.
        """
        import warnings
        warnings.warn(
            "llm (LLMInterface) deprecated. Используйте llm_orchestrator для генерации с валидацией и retry.",
            DeprecationWarning,
            stacklevel=2
        )

        # ✅ ИСПРАВЛЕНО: Используем llm_orchestrator вместо прямого доступа
        orchestrator = self.llm_orchestrator
        if orchestrator and hasattr(orchestrator, 'provider'):
            return orchestrator.provider
        return None

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
            # response может быть LLMResponse или StructuredLLMResponse
            finish_reason = None
            if hasattr(response, 'raw_response') and response.raw_response:
                # StructuredLLMResponse
                finish_reason = response.raw_response.finish_reason
            elif hasattr(response, 'finish_reason'):
                # LLMResponse
                finish_reason = response.finish_reason
            
            if finish_reason == "error":
                error_msg = "Неизвестная ошибка LLM"
                # Получаем metadata
                metadata = None
                if hasattr(response, 'raw_response') and response.raw_response:
                    metadata = response.raw_response.metadata
                elif hasattr(response, 'metadata'):
                    metadata = response.metadata
                    
                if metadata:
                    if isinstance(metadata, dict):
                        error_msg = metadata.get('error', error_msg)
                    elif isinstance(metadata, str):
                        error_msg = metadata

                # Логируем ошибку
                await self._log("error", f"LLM вызов через оркестратор вернул ошибку: {error_msg}")

                # Оркестратор уже опубликовал событие об ошибке
                return False, None, error_msg
            
            # Успешный ответ
            await self._log("info", f"LLM вызов через оркестратор завершён успешно")

            # Возвращаем StructuredLLMResponse объект (не dict!)
            # response уже имеет: .parsed_content, .raw_response, .success, .validation_errors
            return True, response, ""
            
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
            if self.application_context and hasattr(self.application_context, 'infrastructure_context'):
                from core.infrastructure.logging import EventBusLogger
                self.event_bus_logger = EventBusLogger(
                    event_bus=self.application_context.infrastructure_context.event_bus,
                    session_id="system",
                    agent_id="system",
                    component="react_pattern.think"
                )

        if self.event_bus_logger:
            log_method = getattr(self.event_bus_logger, level, None)
            if log_method:
                await log_method(message, **extra_data)

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
            # behavior.react.think.system → system_prompts['behavior.react.think']
            if 'behavior.react.think' in self.system_prompts:
                system_prompt_obj = self.system_prompts['behavior.react.think']
                if hasattr(system_prompt_obj, 'content') and system_prompt_obj.content:
                    self.system_prompt_template = system_prompt_obj.content

            # user_prompts содержит {base_capability: Prompt}
            # behavior.react.think.user → user_prompts['behavior.react.think']
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
                if "behavior.react.think.user" in self.prompts:
                    prompt_obj = self.prompts["behavior.react.think.user"]
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

            # Логирование что найдено
            if self.event_bus_logger:
                self.event_bus_logger.info_sync(f"[ReAct] system_prompts: {list(self.system_prompts.keys()) if hasattr(self, 'system_prompts') and self.system_prompts else 'None'}")
                self.event_bus_logger.info_sync(f"[ReAct] user_prompts: {list(self.user_prompts.keys()) if hasattr(self, 'user_prompts') and self.user_prompts else 'None'}")
                self.event_bus_logger.info_sync(f"[ReAct] prompts: {list(self.prompts.keys()) if hasattr(self, 'prompts') and self.prompts else 'None'}")
                self.event_bus_logger.info_sync(f"[ReAct] system_prompt_template загружен: {self.system_prompt_template is not None}")
                self.event_bus_logger.info_sync(f"[ReAct] reasoning_prompt_template загружен: {self.reasoning_prompt_template is not None}")

            # === ДОБАВЛЕНИЕ JSON СХЕМЫ В СИСТЕМНЫЙ ПРОМПТ ===
            # Если схема загружена, добавляем её в системный промпт
            if self.reasoning_schema and self.system_prompt_template:
                self.system_prompt_template = self._inject_schema_into_system_prompt(
                    self.system_prompt_template,
                    self.reasoning_schema
                )

            return True
        except Exception as e:
            self.event_bus_logger.error_sync(f"Ошибка загрузки reasoning ресурсов: {e}")
            return False

    def _inject_schema_into_system_prompt(self, system_prompt: str, schema: dict) -> str:
        """
        Добавляет JSON схему в системный промпт.

        ПАРАМЕТРЫ:
        - system_prompt: исходный системный промпт
        - schema: JSON схема из контракта

        ВОЗВРАЩАЕТ:
        - str: системный промпт с добавленной схемой
        """
        import json

        # Проверяем есть ли уже схема в промпте (ищем маркер "JSON СХЕМА ОТВЕТА")
        if 'JSON СХЕМА ОТВЕТА' in system_prompt or 'JSON SCHEMA' in system_prompt.upper():
            # Схема уже есть, не добавляем
            return system_prompt

        # Генерируем JSON схему для промпта
        schema_json = json.dumps(schema, indent=2, ensure_ascii=False)

        # Получаем обязательные поля
        required = schema.get('required', [])
        if not required:
            # Если required пустой, берем ключевые поля
            required = ['thought', 'decision', 'confidence', 'stop_condition']

        # Добавляем схему в конец системного промпта
        return f"""{system_prompt}

=== JSON СХЕМА ОТВЕТА ===
Ты ДОЛЖЕН вернуть JSON следующей структуры:

```json
{schema_json}
```

ОБЯЗАТЕЛЬНЫЕ ПОЛЯ: {', '.join(required)}

ВАЖНО: Верни ТОЛЬКО JSON без дополнительных пояснений. НЕ повторяй шаблон {{\"next_action\": \"string\", \"parameters\": \"object\"}} — это только пример формата."""

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
            "step_history": self._build_step_history(last_steps),
            "observation": self._extract_last_observation(last_steps),
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
            # КРИТИЧЕСКАЯ ОШИБКА: промпт не загружен
            error_msg = (
                "reasoning_prompt_template не загружен! "
                "Промпт должен быть загружен при инициализации из PromptService. "
                "Проверьте наличие промпта behavior.react.think в реестре."
            )
            self.event_bus_logger.error_sync(error_msg)
            raise RuntimeError(error_msg)

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

        # Примечание: Список инструментов добавляется отдельно через {available_tools}
        return "\n".join(parts)

    def _build_step_history(self, last_steps: list) -> str:
        """
        Формирует читаемую историю шагов для промпта.
        
        ПАРАМЕТРЫ:
        - last_steps: список шагов из context_analysis
        
        ВОЗВРАЩАЕТ:
        - str: отформатированная история шагов
        """
        if not last_steps:
            return "Шаги не выполнены"
        
        step_lines = []
        for i, step in enumerate(last_steps[-3:], 1):
            if isinstance(step, dict):
                capability = step.get('capability', 'unknown')
                summary = step.get('summary', '')
                obs = step.get('observation', '')
                
                step_text = f"{capability}: {summary}"
                if obs:
                    step_text += f" → {obs[:100]}"
                step_lines.append(f"{i}. {step_text}")
            else:
                step_lines.append(f"{i}. {step}")
        
        return "\n".join(step_lines)

    def _extract_last_observation(self, last_steps: list) -> str:
        """
        Извлекает последнее наблюдение из истории шагов.
        
        ПАРАМЕТРЫ:
        - last_steps: список шагов из context_analysis
        
        ВОЗВРАЩАЕТ:
        - str: последнее наблюдение или "Нет наблюдений"
        """
        if not last_steps:
            return "Нет наблюдений"
        
        # Ищем observation в последнем шаге
        last_step = last_steps[-1]
        if isinstance(last_step, dict):
            obs = last_step.get('observation', '')
            if obs:
                return obs
        
        # Если observation нет в явном виде, пробуем извлечь из summary
        summary = last_step.get('summary', '') if isinstance(last_step, dict) else str(last_step)
        return summary if summary else "Нет наблюдений"

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
                schema_obj = self.schema_validator.get_capability_schema(name)
                # Конвертируем CapabilitySchema в dict если нужно
                if schema_obj and hasattr(schema_obj, 'to_dict'):
                    params_schema = schema_obj.to_dict()
                else:
                    params_schema = schema_obj

            # Формируем строку инструмента
            line = f"- {name}: {description}"

            # Добавляем параметры если есть схема
            if params_schema:
                params_list = []
                # Проверяем что params_schema это dict перед вызовом .items()
                if isinstance(params_schema, dict):
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

        # Выполняем анализ контекста сессии (возвращает ContextAnalysis объект)
        analysis_obj = analyze_context(session_context)

        # Преобразуем в dict для обратной совместимости
        # В будущем можно вернуть ContextAnalysis напрямую
        analysis = {
            "goal": analysis_obj.goal,
            "last_steps": analysis_obj.last_steps,
            "progress": analysis_obj.progress,
            "current_step": analysis_obj.current_step,
            "execution_time_seconds": analysis_obj.execution_time_seconds,
            "last_activity": analysis_obj.last_activity,
            "no_progress_steps": analysis_obj.no_progress_steps,
            "consecutive_errors": analysis_obj.consecutive_errors,
            "summary": analysis_obj.summary,
        }

        # Добавляем информацию о доступных capability
        # Фильтрация только по supported_strategies (без хардкода навыков)
        analysis["available_capabilities"] = self._filter_capabilities(
            available_capabilities
        )

        await self._log("debug", f"[ReAct] analyze_context: after filtering available_capabilities count={len(analysis['available_capabilities'])}")

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

                # Проверяем тип схемы
                if hasattr(schema, 'to_dict'):
                    # CapabilitySchema объект (из schema_validator.py)
                    to_dict_result = schema.to_dict()
                    # Проверяем что результат это dict
                    if isinstance(to_dict_result, dict):
                        params_schema = to_dict_result
                    else:
                        self.event_bus_logger.debug_sync(f"⚠️ to_dict() вернул не dict для {cap.name}: {type(to_dict_result)}")
                        params_schema = {}
                elif hasattr(schema, 'model_json_schema'):
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
                    # Проверяем что properties это dict, а не CapabilitySchema
                    if isinstance(properties, dict):
                        for prop_name, prop_info in properties.items():
                            params_schema[prop_name] = {
                                'type': prop_info.get('type', 'string') if isinstance(prop_info, dict) else 'string',
                                'required': prop_name in required
                            }
                    else:
                        self.event_bus_logger.debug_sync(f"⚠️ properties не dict для {cap.name}: {type(properties)}")
                else:
                    # Неизвестный тип схемы
                    self.event_bus_logger.debug_sync(f"⚠️ Неизвестный тип схемы для {cap.name}: {type(schema)}")
                    self.event_bus_logger.debug_sync(f"  schema attributes: {dir(schema)}")

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
        
        await self._log("info", f"generate_decision: context_analysis.last_steps={len(context_analysis.get('last_steps', []))}")

        try:
            # 1. Структурированное рассуждение через LLM
            reasoning_result = await self._perform_structured_reasoning(
                session_context=session_context,
                context_analysis=context_analysis,
                available_capabilities=available_capabilities
            )
            # Логирование результата рассуждения
            print(f"🔵 [generate_decision] reasoning_result тип={type(reasoning_result).__name__}", flush=True)
            if hasattr(reasoning_result, 'to_dict'):
                d = reasoning_result.to_dict()
                print(f"🔵 [generate_decision] to_dict() decision={d.get('decision')}", flush=True)
                print(f"🔵 [generate_decision] to_dict() stop_condition={d.get('stop_condition')}", flush=True)
            elif isinstance(reasoning_result, dict):
                print(f"🔵 [generate_decision] reasoning_result.decision={reasoning_result.get('decision', {})}", flush=True)
                print(f"🔵 [generate_decision] reasoning_result.stop_condition={reasoning_result.get('stop_condition', False)}", flush=True)

            # 2. Принятие решения на основе рассуждения
            decision = await self._make_decision_from_reasoning(
                session_context=session_context,
                reasoning_result=reasoning_result,
                available_capabilities=available_capabilities  # КРИТИЧНО: передаём available_capabilities
            )

            print(f"🔵 [generate_decision] decision от _make_decision_from_reasoning: action={decision.action.value}, capability_name={decision.capability_name}", flush=True)

            # Логирование финального решения
            await self._log("info", f"generate_decision: decision получен",
                           action=decision.action.value,
                           capability_name=decision.capability_name)

            await self._log("info", f"  decision.action={decision.action}, decision.capability_name={decision.capability_name}")

            # 3. Сброс счётчика ошибок при успешном решении
            self.error_count = 0

            print(f"🔵 [generate_decision] Возвращаем decision: action={decision.action.value}, capability_name={decision.capability_name}", flush=True)

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
        """
        Выполняет структурированное рассуждение через LLM.

        АРХИТЕКТУРА:
        1. Проверка загрузки ресурсов
        2. Рендеринг промпта
        3. Вызов LLM через LLMOrchestrator (structured output)
        4. Возврат распарсенного результата
        """
        # === 1. ПРОВЕРКА ЗАГРУЗКИ РЕСУРСОВ ===
        if not self._load_reasoning_resources():
            await self._log("warning", "Промпт не загружен, используем fallback")
            return self._create_fallback_reasoning(
                context_analysis=context_analysis,
                available_capabilities=available_capabilities,
                reason="prompt_not_loaded"
            )

        # === 2. ПОДГОТОВКА ЗАПРОСА ===
        reasoning_prompt = self._render_reasoning_prompt(
            context_analysis=context_analysis,
            available_capabilities=available_capabilities
        )

        # === 3. ПОЛУЧЕНИЕ LLM ПРОВАЙДЕРА ===
        # ✅ ИСПРАВЛЕНО: Используем llm_orchestrator вместо прямого доступа к infrastructure_context
        llm_provider = None
        orchestrator = self.llm_orchestrator
        if orchestrator and hasattr(orchestrator, 'provider'):
            llm_provider = orchestrator.provider
        
        # Fallback: получаем из application_context если orchestrator недоступен
        if not llm_provider and self.application_context and hasattr(self.application_context, 'infrastructure_context'):
            llm_provider = self.application_context.infrastructure_context.get_provider("default_llm")

        if not llm_provider:
            await self._log("warning", "LLM провайдер недоступен, используем fallback")
            return self._create_fallback_reasoning(
                context_analysis=context_analysis,
                available_capabilities=available_capabilities,
                reason="llm_provider_not_available"
            )

        # === 4. ВЫЗОВ LLM ЧЕРЕЗ ORCHESTRATOR ===
        llm_request = LLMRequest(
            prompt=reasoning_prompt,
            system_prompt=self.system_prompt_template,
            temperature=0.3,
            max_tokens=1000,
            structured_output=StructuredOutputConfig(
                output_model="ReasoningResult",
                schema_def=self.reasoning_schema,
                max_retries=3,
                strict_mode=False
            )
        )

        # Устанавливаем контекст для логирования
        if hasattr(llm_provider, 'set_call_context'):
            current_agent_id = getattr(session_context, 'agent_id', 'system') if session_context else 'system'
            # ✅ ИСПРАВЛЕНО: Используем event_bus из infrastructure_context через orchestrator
            event_bus = None
            if orchestrator and hasattr(orchestrator, 'event_bus'):
                event_bus = orchestrator.event_bus
            elif self.application_context and hasattr(self.application_context, 'infrastructure_context'):
                event_bus = self.application_context.infrastructure_context.event_bus
            
            llm_provider.set_call_context(
                event_bus=event_bus,
                session_id=getattr(session_context, 'session_id', 'unknown'),
                agent_id=current_agent_id,
                component="react_pattern",
                phase="think"
            )

        # Получаем цель из session_context
        goal_value = session_context.get_goal() if session_context else "unknown"
        
        await self._log("info", f"Запуск рассуждения ReAct | Цель: {goal_value}")
        await self._log("info", f"Длина промпта: {len(reasoning_prompt)} символов")

        # === 4. ВЫПОЛНЕНИЕ ЧЕРЕЗ ORCHESTRATOR ===
        llm_timeout = getattr(llm_provider, 'timeout_seconds', 120.0)
        
        success, response, error = await self._execute_llm_with_orchestrator(
            llm_request=llm_request,
            llm_provider=llm_provider,
            timeout=llm_timeout,
            session_context=session_context
        )

        # === 5. ОБРАБОТКА ОТВЕТА ===
        if not success:
            await self._log("error", f"LLM вызов не удался: {error}")
            return self._create_fallback_reasoning(
                context_analysis=context_analysis,
                available_capabilities=available_capabilities,
                reason=f"llm_call_failed:{error}"
            )

        # === 6. ИЗВЛЕЧЕНИЕ РЕЗУЛЬТАТА ===
        # response — это StructuredLLMResponse объект
        await self._log("info", f"=== ИЗВЛЕЧЕНИЕ РЕЗУЛЬТАТА ===")
        await self._log("info", f"Тип response: {type(response).__name__}")
        await self._log("info", f"response.parsed_content: {response.parsed_content is not None}")
        await self._log("info", f"response.raw_response: {response.raw_response is not None}")

        if response.raw_response and hasattr(response.raw_response, 'content'):
            await self._log("info", f"response.raw_response.content[:200]: {str(response.raw_response.content)[:200]}")

        result = None

        # Проверяем что это StructuredLLMResponse
        if hasattr(response, 'parsed_content') and hasattr(response, 'raw_response'):
            # ✅ ИСПРАВЛЕНО: Сохраняем Pydantic модель вместо dict
            # validate_reasoning_result примет модель и сконвертирует при необходимости
            if response.parsed_content:
                result = response.parsed_content  # ← Pydantic модель, не dict!
                await self._log("info", f"✅ Извлечено из parsed_content (Pydantic модель типа {type(result).__name__})")
            elif response.raw_response:
                # Fallback: пробуем распарсить raw_response.content
                await self._log("warning", "parsed_content пуст, пробуем распарсить raw_response")
                content_val = response.raw_response.content
                if isinstance(content_val, str):
                    try:
                        result = json.loads(content_val)
                        await self._log("info", f"✅ Распарсено из raw_response.content")
                    except (json.JSONDecodeError, ValueError) as e:
                        await self._log("error", f"LLM вернул невалидный JSON: {content_val[:200]}...")
                else:
                    result = content_val
            else:
                await self._log("error", "StructuredLLMResponse пуст (нет parsed_content или raw_response)")
        elif hasattr(response, 'content'):
            # Fallback для простого LLMResponse
            await self._log("warning", "response — простой LLMResponse, пробуем распарсить content")
            content_val = response.content
            if isinstance(content_val, str):
                try:
                    result = json.loads(content_val)
                except (json.JSONDecodeError, ValueError):
                    await self._log("warning", f"LLM вернул невалидный JSON: {content_val[:200]}...")
            else:
                result = content_val
        else:
            await self._log("error", f"Неизвестный тип response: {type(response).__name__}")
            result = response

        if result is None:
            await self._log("error", "LLM вернул пустой результат")
            return self._create_fallback_reasoning(
                context_analysis=context_analysis,
                available_capabilities=available_capabilities,
                reason="empty_response"
            )

        # === 7. ВАЛИДАЦИЯ РЕЗУЛЬТАТА ===
        await self._log("info", f"=== ВАЛИДАЦИЯ РЕЗУЛЬТАТА LLM ===")
        await self._log("info", f"Перед валидацией: тип result={type(result).__name__}")

        # validate_reasoning_result теперь возвращает ReasoningResult объект
        reasoning_result = validate_reasoning_result(result)
        
        await self._log("info", f"После валидации: тип reasoning_result={type(reasoning_result).__name__}")
        if hasattr(reasoning_result, 'to_dict'):
            reasoning_dict = reasoning_result.to_dict()
            await self._log("info", f"reasoning_result.to_dict(): {reasoning_dict}")
        elif isinstance(reasoning_result, dict):
            await self._log("info", f"reasoning_result (dict): {reasoning_result}")
        
        # Добавляем available_capabilities в объект
        reasoning_result.available_capabilities = available_capabilities
        
        # Логируем через атрибуты объекта
        await self._log("info", f"thought={reasoning_result.thought[:50]}...")
        if reasoning_result.decision:
            await self._log("info", f"decision.next_action={reasoning_result.decision.next_action}")
            await self._log("info", f"decision.reasoning={reasoning_result.decision.reasoning}")
        
        print(f"🔵 [_perform_structured_reasoning] Возвращаем: type={type(reasoning_result).__name__}", flush=True)
        if hasattr(reasoning_result, 'decision'):
            print(f"🔵 [_perform_structured_reasoning] reasoning_result.decision={reasoning_result.decision}", flush=True)
            if hasattr(reasoning_result.decision, 'next_action'):
                print(f"🔵 [_perform_structured_reasoning] decision.next_action={reasoning_result.decision.next_action}", flush=True)
        print(f"🔵 [_perform_structured_reasoning] reasoning_result.stop_condition={reasoning_result.stop_condition}", flush=True)

        return reasoning_result

    def _create_fallback_reasoning(
        self,
        context_analysis: Dict[str, Any],
        available_capabilities: List[Capability],
        reason: str
    ) -> Dict[str, Any]:
        """Создает fallback результат рассуждения."""
        fallback_capability = "final_answer.generate"
        if available_capabilities:
            fallback_capability = (
                available_capabilities[0].name if hasattr(available_capabilities[0], 'name')
                else "final_answer.generate"
            )

        return {
            "analysis": {
                "current_situation": f"Fallback: {reason}",
                "progress_assessment": "Неизвестно",
                "confidence": 0.3,
                "errors_detected": True,
                "consecutive_errors": getattr(self, 'error_count', 0) + 1,
                "execution_time": context_analysis.get("execution_time_seconds", 0),
                "no_progress_steps": context_analysis.get("no_progress_steps", 0)
            },
            "decision": {
                "next_action": fallback_capability,
                "reasoning": f"fallback после ошибки: {reason}",
                "parameters": {"query": context_analysis.get("goal", "Продолжить")},
                "expected_outcome": "Неизвестно"
            },
            "available_capabilities": available_capabilities,
            "confidence": 0.1,
            "stop_condition": False,
            "stop_reason": "fallback",
            "alternative_actions": [],
            "thought": f"Fallback из-за: {reason}"
        }

    def _find_capability(
        self,
        available_capabilities: List[Capability],
        capability_name: str
    ) -> Optional[Capability]:
        """Поиск capability по имени в списке доступных.

        Поддерживает поиск по префиксу: если LLM возвращает 'book_library.execute_script',
        а capability записано как 'book_library', будет найдено по префиксу.
        """
        # Логирование начала поиска
        print(f"🔍 [_find_capability] поиск '{capability_name}' среди {len(available_capabilities)} доступных", flush=True)
        if self.event_bus_logger:
            self.event_bus_logger.debug_sync(f"[ReAct] _find_capability: поиск '{capability_name}' среди {len(available_capabilities)} доступных")
        else:
            print(f"⚠️ [_find_capability] event_bus_logger не инициализирован", flush=True)

        # 1. Прямое совпадение по имени
        for cap in available_capabilities:
            if cap.name == capability_name:
                print(f"✅ [_find_capability] найдено по прямому совпадению '{cap.name}'", flush=True)
                self.event_bus_logger.debug_sync(f"[ReAct] _find_capability: найдено по прямому совпадению '{cap.name}'")
                return cap

        # 2. Если capability_name содержит '.', извлекаем префикс и ищем по нему
        if '.' in capability_name:
            prefix = capability_name.split('.')[0]
            print(f"🔍 [_find_capability] извлечён префикс '{prefix}' из '{capability_name}'", flush=True)
            self.event_bus_logger.debug_sync(f"[ReAct] _find_capability: извлечён префикс '{prefix}' из '{capability_name}'")

            # Поиск по префиксу (точное совпадение с именем capability)
            for cap in available_capabilities:
                if cap.name == prefix:
                    print(f"✅ [_find_capability] найдено по префиксу (имя) '{cap.name}'", flush=True)
                    self.event_bus_logger.debug_sync(f"[ReAct] _find_capability: найдено по префиксу (имя) '{cap.name}'")
                    return cap

                # Проверка атрибута skill_name если он есть
                if hasattr(cap, 'skill_name') and cap.skill_name:
                    if cap.skill_name == prefix:
                        print(f"✅ [_find_capability] найдено по префиксу (skill_name) '{cap.skill_name}'", flush=True)
                        self.event_bus_logger.debug_sync(f"[ReAct] _find_capability: найдено по префиксу (skill_name) '{cap.skill_name}'")
                        return cap
                    # Также проверяем префикс skill_name
                    if '.' in cap.skill_name and cap.skill_name.split('.')[0] == prefix:
                        print(f"✅ [_find_capability] найдено по префиксу skill_name '{cap.skill_name}'", flush=True)
                        self.event_bus_logger.debug_sync(f"[ReAct] _find_capability: найдено по префиксу skill_name '{cap.skill_name}'")
                        return cap

        # 3. Частичное совпадение (для совместимости)
        for cap in available_capabilities:
            if capability_name.lower() in cap.name.lower():
                print(f"✅ [_find_capability] найдено по частичному совпадению '{cap.name}'", flush=True)
                self.event_bus_logger.debug_sync(f"[ReAct] _find_capability: найдено по частичному совпадению '{cap.name}'")
                return cap

        # 4. Поиск по supported_strategies
        for cap in available_capabilities:
            if any(s.lower() == "react" for s in (cap.supported_strategies or [])):
                if hasattr(cap, 'skill_name') and cap.skill_name:
                    if capability_name.lower() in cap.skill_name.lower():
                        self.event_bus_logger.debug_sync(f"[ReAct] _find_capability: найдено по supported_strategies и skill_name '{cap.skill_name}'")
                        return cap

        # Не найдено
        self.event_bus_logger.warning_sync(f"[ReAct] _find_capability: НЕ найдено '{capability_name}' среди доступных capability")
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
        reasoning_result,  # ReasoningResult объект (или dict для обратной совместимости)
        available_capabilities: List[Capability]
    ) -> BehaviorDecision:
        """Принимает решение о следующем действии на основе анализа контекста."""

        try:
            # Проверяем тип reasoning_result
            # Может быть ReasoningResult (новый путь) или dict (старый путь)
            print(f"🔵 [_make_decision] reasoning_result type={type(reasoning_result).__name__}", flush=True)
            
            if hasattr(reasoning_result, 'to_dict'):
                # ReasoningResult объект — конвертируем в dict для обратной совместимости
                print(f"🔵 [_make_decision] Вызываем to_dict()...", flush=True)
                reasoning_dict = reasoning_result.to_dict()
                print(f"🔵 [_make_decision] reasoning_dict keys={list(reasoning_dict.keys())}", flush=True)
                print(f"🔵 [_make_decision] reasoning_dict.decision={reasoning_dict.get('decision')}", flush=True)
                print(f"🔵 [_make_decision] reasoning_dict.stop_condition={reasoning_dict.get('stop_condition')}", flush=True)
            elif isinstance(reasoning_result, dict):
                # dict — используем напрямую (старый путь)
                print(f"🔵 [_make_decision] Используем dict напрямую", flush=True)
                reasoning_dict = reasoning_result
            else:
                print(f"❌ [_make_decision] Неверный тип: {type(reasoning_result).__name__}", flush=True)
                await self._log("error", f"_make_decision_from_reasoning: reasoning_result имеет неверный тип",
                               actual_type=type(reasoning_result).__name__,
                               actual_value=str(reasoning_result)[:500] if reasoning_result else None)
                return BehaviorDecision(
                    action=BehaviorDecisionType.RETRY,
                    reason=f"invalid_reasoning_result_type:{type(reasoning_result).__name__}"
                )

            # 1. Проверка условия остановки (согласно контракту behavior.react.think)
            stop_condition = reasoning_dict.get("stop_condition", False)
            await self._log("info", f"_make_decision_from_reasoning: stop_condition={stop_condition}")
            await self._log("info", f"_make_decision_from_reasoning: reasoning_dict keys={list(reasoning_dict.keys()) if isinstance(reasoning_dict, dict) else 'not dict'}")
            
            if stop_condition:
                await self._log("warning", f"STOP condition detected: {reasoning_dict.get('stop_reason', 'goal_achieved')}")
                return BehaviorDecision(
                    action=BehaviorDecisionType.STOP,
                    reason=reasoning_dict.get("stop_reason", "goal_achieved")
                )

            # 2. Извлечение capability_name из decision.next_action
            decision_dict = reasoning_dict.get("decision", {})
            await self._log("info", f"_make_decision_from_reasoning: decision_dict={decision_dict}")

            # ПРОВЕРКА: decision тоже должен быть dict
            if not isinstance(decision_dict, dict):
                await self._log("error", f"_make_decision_from_reasoning: decision имеет неверный тип",
                               actual_type=type(decision_dict).__name__,
                               decision_value=str(decision_dict)[:200] if decision_dict else None)
                decision_dict = {}
            
            capability_name = decision_dict.get("next_action")
            
            # Fallback: проверяем recommended_action (для упрощённой логики без LLM)
            if not capability_name:
                recommended_action = reasoning_dict.get("recommended_action", {})
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
            parameters = decision_dict.get("parameters", {})
            validated_params = self._validate_parameters(capability, parameters)
            
            # 5. Возвращаем решение с ЗАПОЛНЕННЫМ capability_name
            print(f"✅ [_make_decision] Возвращаем BehaviorDecision: action={BehaviorDecisionType.ACT.value}, capability_name={capability_name}", flush=True)
            return BehaviorDecision(
                action=BehaviorDecisionType.ACT,
                capability_name=capability_name,  # ОБЯЗАТЕЛЬНО должно быть заполнено
                parameters=validated_params,
                reason=decision_dict.get("reasoning", "capability_execution")
            )

        except Exception as e:
            print(f"❌ [_make_decision] Исключение: {e}", flush=True)
            await self._log("error", f"_make_decision_from_reasoning: ошибка",
                           error=str(e),
                           exc_info=True)
            raise

    def _build_rollback_decision(self, session_context, reasoning_result: Dict[str, Any]) -> BehaviorDecision:
        """Создает решение для отката."""
        # В ��овой схеме нет rollback_steps, используем stop_condition
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
                "input": reasoning_result.get("analysis", {}).get("current_state", "Продолжить выполнение задачи"),
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
            # ✅ ИСПРАВЛЕНО: Используем значение по умолчанию вместо session_context.get_goal()
            validated_params = {"input": "Продолжить выполнение задачи"}
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
                # ✅ ИСПРАВЛЕНО: Используем значение по умолчанию вместо session_context.get_goal()
                return BehaviorDecision(
                    action=BehaviorDecisionType.ACT,
                    capability_name=cap.name,
                    parameters={
                        "input": "Продолжить выполнение задачи",
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
