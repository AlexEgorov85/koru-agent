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
from core.models.data.capability import Capability
from core.models.types.llm_types import LLMRequest, StructuredOutputConfig, LLMResponse
from core.models.errors import InfrastructureError
from core.application.agent.components.action_executor import ExecutionContext


# ============================================================================
# СПЕЦИФИЧНЫЕ СЕРВИСЫ ДЛЯ REACTPATTERN
# ============================================================================

class FallbackStrategyService:
    """Стратегии fallback для ReActPattern."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {"max_retries": 3, "default_pattern": "fallback.v1.0.0", "emergency_stop": True}
    
    def create_retry(self, reason: str, max_retries: Optional[int] = None) -> BehaviorDecision:
        """Создаёт решение для повторной попытки."""
        return BehaviorDecision(action=BehaviorDecisionType.RETRY, reason=reason, confidence=0.5)
    
    def create_switch(self, next_pattern: str, reason: str) -> BehaviorDecision:
        """Создаёт решение для переключения паттерна."""
        return BehaviorDecision(action=BehaviorDecisionType.SWITCH, next_pattern=next_pattern, reason=reason, confidence=0.7)
    
    def create_stop(self, reason: str, final_answer: Optional[str] = None) -> BehaviorDecision:
        """Создаёт решение для остановки."""
        return BehaviorDecision(action=BehaviorDecisionType.STOP, reason=reason, confidence=0.9)
    
    def create_error(self, reason: str, available_capabilities: List[Capability]) -> BehaviorDecision:
        """Создаёт решение при ошибке."""
        if available_capabilities:
            cap = available_capabilities[0]
            return BehaviorDecision(
                action=BehaviorDecisionType.ACT,
                capability_name=cap.name,
                parameters={"input": "Продолжить выполнение задачи", "context": reason},
                reason=f"fallback_{reason}",
                confidence=0.3
            )
        return BehaviorDecision(action=BehaviorDecisionType.STOP, reason=f"emergency_stop_no_capabilities_{reason}", confidence=0.1)
    
    def create_reasoning_fallback(self, context_analysis: Dict[str, Any], available_capabilities: List[Capability], reason: str) -> Dict[str, Any]:
        """Создаёт fallback-результат рассуждения."""
        fallback_capability = available_capabilities[0].name if available_capabilities else "final_answer.generate"
        return {
            "analysis": {
                "current_situation": f"Fallback: {reason}",
                "progress_assessment": "Неизвестно",
                "confidence": 0.3,
                "errors_detected": True,
                "consecutive_errors": context_analysis.get("consecutive_errors", 0) + 1,
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
        """Инициализация паттерна."""
        super().__init__(component_name, component_config, application_context, executor)

        # Специфичные для ReAct атрибуты
        self.reasoning_schema = None
        self.reasoning_prompt_template = None
        self.system_prompt_template = None
        self.last_reasoning_time = 0.0
        self.error_count = 0
        self.max_consecutive_errors = 3
        self.schema_validator = SchemaValidator()

        # === СПЕЦИФИЧНЫЕ СЕРВИСЫ ReAct ===
        self.fallback_strategy = FallbackStrategyService()

        # EventBusLogger
        self.event_bus_logger = None

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
        
        КРИТИЧНЫЕ РЕСУРСЫ:
        - system_prompt_template: системный промпт для рассуждения
        - reasoning_prompt_template: пользовательский промпт для рассуждения
        - reasoning_schema: JSON схема для валидации ответа LLM
        
        ВОЗВРАЩАЕТ:
        - bool: True если все критические ресурсы загружены
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

            # === КРИТИЧНАЯ ВАЛИДАЦИЯ РЕСУРСОВ ===
            # Проверяем что все критические ресурсы загружены
            missing_resources = []
            
            if not self.system_prompt_template:
                missing_resources.append("system_prompt_template")
            
            if not self.reasoning_prompt_template:
                missing_resources.append("reasoning_prompt_template")
            
            if not self.reasoning_schema:
                missing_resources.append("reasoning_schema")
            
            # Логирование что найдено
            if self.event_bus_logger:
                self.event_bus_logger.info_sync(f"[ReAct] === ЗАГРУЗКА РЕСУРСОВ ===")
                self.event_bus_logger.info_sync(f"[ReAct] system_prompts: {list(self.system_prompts.keys()) if hasattr(self, 'system_prompts') and self.system_prompts else 'None'}")
                self.event_bus_logger.info_sync(f"[ReAct] user_prompts: {list(self.user_prompts.keys()) if hasattr(self, 'user_prompts') and self.user_prompts else 'None'}")
                self.event_bus_logger.info_sync(f"[ReAct] prompts: {list(self.prompts.keys()) if hasattr(self, 'prompts') and self.prompts else 'None'}")
                self.event_bus_logger.info_sync(f"[ReAct] system_prompt_template загружен: {self.system_prompt_template is not None}")
                self.event_bus_logger.info_sync(f"[ReAct] reasoning_prompt_template загружен: {self.reasoning_prompt_template is not None}")
                self.event_bus_logger.info_sync(f"[ReAct] reasoning_schema загружена: {self.reasoning_schema is not None}")
                
                if missing_resources:
                    self.event_bus_logger.warning_sync(f"[ReAct] Отсутствуют ресурсы: {missing_resources}")

            # Если отсутствуют критические ресурсы — возвращаем False
            # (не используем fallback, чтобы явно сигнализировать об ошибке инициализации)
            if missing_resources:
                self.event_bus_logger.error_sync(
                    f"[ReAct] КРИТИЧНО: Отсутствуют критические ресурсы: {missing_resources}. "
                    f"ReAct паттерн не может работать без промптов и схемы."
                )
                return False

            return True
        except Exception as e:
            self.event_bus_logger.error_sync(f"Ошибка загрузки reasoning ресурсов: {e}")
            return False

    def _render_reasoning_prompt(
        self,
        context_analysis: Dict[str, Any],
        available_capabilities: List[Capability],
        session_context=None
    ) -> str:
        """
        Рендерит шаблон промпта с подстановкой переменных через PromptBuilderService.
        """
        if not self.reasoning_prompt_template:
            error_msg = (
                "reasoning_prompt_template не загружен! "
                "Промпт должен быть загружен при инициализации из PromptService."
            )
            # Используем безопасный доступ к event_bus_logger
            if self.event_bus_logger:
                self.event_bus_logger.error_sync(error_msg)
            else:
                # Fallback: print если logger ещё не инициализирован
                print(f"❌ [ReAct] {error_msg}", flush=True)
            raise RuntimeError(error_msg)

        # Делегируем сервису с передачей session_context
        return self.prompt_builder.build_reasoning_prompt(
            context_analysis=context_analysis,
            available_capabilities=available_capabilities,
            templates={"system": self.system_prompt_template, "user": self.reasoning_prompt_template},
            schema_validator=self.schema_validator,
            session_context=session_context
        )

    # === МЕТОДЫ ДЕЛЕГИРОВАНЫ PromptBuilderService ===
    # _build_input_context, _build_step_history, _extract_last_observation, _format_available_tools
    # теперь находятся в PromptBuilderService и вызываются через self.prompt_builder

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

        # Регистрируем схемы через CapabilityResolverService
        self.capability_resolver.register_capability_schemas(
            available_capabilities=available_capabilities,
            schema_validator=self.schema_validator,
            input_contracts=getattr(self, 'input_contracts', {}),
            data_repository=getattr(self.application_context, 'data_repository', None) if self.application_context else None
        )

        # Выполняем анализ контекста сессии
        analysis_obj = analyze_context(session_context)

        # Преобразуем в dict для обратной совместимости
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

        # Фильтрация capability через CapabilityResolverService
        filtered_caps = self.capability_resolver.filter_capabilities(available_capabilities, self.pattern_id)
        filtered_caps = self.capability_resolver.exclude_capability(filtered_caps, "final_answer.generate")

        analysis["available_capabilities"] = filtered_caps

        await self._log("debug", f"[ReAct] analyze_context: after filtering available_capabilities count={len(analysis['available_capabilities'])}")

        return analysis

    # === МЕТОД ДЕЛЕГИРОВАН CapabilityResolverService ===
    # _register_capability_schemas теперь в self.capability_resolver.register_capability_schemas

    async def generate_decision(
        self,
        session_context: 'SessionContext',
        available_capabilities: List[Capability],
        context_analysis: Dict[str, Any],
        execution_context=None
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
                available_capabilities=available_capabilities,
                execution_context=execution_context
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
                reason=f"critical_error:{str(e)}",
                available_capabilities=available_capabilities
            )

    async def _perform_structured_reasoning(
        self,
        session_context,
        context_analysis: Dict[str, Any],
        available_capabilities: List[Capability],
        execution_context=None
    ) -> ReasoningResult:
        """
        Выполняет структурированное рассуждение через LLM.

        АРХИТЕКТУРА:
        1. Проверка загрузки ресурсов
        2. Рендеринг промпта
        3. Вызов LLM через LLMOrchestrator (structured output)
        4. Валидация и возврат ReasoningResult
        """
        # === 1. ПРОВЕРКА ЗАГРУЗКИ РЕСУРСОВ ===
        if not self._load_reasoning_resources():
            await self._log("warning", "Промпт не загружен, используем fallback")
            return self.fallback_strategy.create_reasoning_fallback(
                context_analysis=context_analysis,
                available_capabilities=available_capabilities,
                reason="prompt_not_loaded"
            )

        # === 2. ПОДГОТОВКА ЗАПРОСА ===
        reasoning_prompt = self._render_reasoning_prompt(
            context_analysis=context_analysis,
            available_capabilities=available_capabilities,
            session_context=session_context
        )

        # === 3. ВЫЗОВ LLM ЧЕРЕЗ EXECUTOR ===
        # Получаем LLM результат через executor
        llm_result = await self.executor.execute_action(
            action_name="llm.generate_structured",
            parameters={
                "prompt": reasoning_prompt,
                "system_prompt": self.system_prompt_template,
                "temperature": 0.3,
                "max_tokens": 1000,
                "structured_output": {
                    "output_model": "ReasoningResult",
                    "schema_def": self.reasoning_schema,
                    "max_retries": 3,
                    "strict_mode": False
                }
            },
            context=execution_context
        )

        if not llm_result.status.name == "COMPLETED":
            await self._log("warning", f"LLM вызов не удался: {llm_result.error}, используем fallback")
            return self.fallback_strategy.create_reasoning_fallback(
                context_analysis=context_analysis,
                available_capabilities=available_capabilities,
                reason="llm_call_failed"
            )

        # Извлекаем результат
        result = llm_result.result
        if hasattr(result, 'parsed_content'):
            reasoning_result = result.parsed_content
        elif isinstance(result, dict):
            reasoning_result = result.get('parsed_content', result)
        else:
            reasoning_result = result

        # Получаем цель из session_context
        goal_value = session_context.get_goal() if session_context else "unknown"

        await self._log("info", f"Запуск рассуждения ReAct | Цель: {goal_value}")
        await self._log("info", f"Длина промпта: {len(reasoning_prompt)} символов")

        # === 4. ВАЛИДАЦИЯ И ВОЗВРАТ РЕЗУЛЬТАТА ===
        # validate_reasoning_result принимает StructuredLLMResponse напрямую
        reasoning_result.available_capabilities = available_capabilities

        return reasoning_result

    # === МЕТОДЫ ДЕЛЕГИРОВАНЫ CapabilityResolverService ===
    # _find_capability и _validate_parameters теперь в self.capability_resolver

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

            # ОСОБЫЙ СЛУЧАЙ: stop_condition=True но next_action='final_answer.generate'
            # Это значит LLM хочет вызвать final_answer перед остановкой
            if stop_condition and capability_name == "final_answer.generate":
                await self._log("info", "STOP + final_answer.generate — вызываем final_answer")
                # Возвращаем ACT для вызова final_answer
                parameters = decision_dict.get("parameters", {})
                # Создаём фейковый capability для валидации
                final_answer_cap = type('Capability', (), {'name': 'final_answer.generate', 'input_schema': {}})()
                validated_params = self.capability_resolver.validate_parameters(
                    final_answer_cap,
                    parameters,
                    self.schema_validator,
                    reasoning_dict
                )
                # КРИТИЧНО: Помечаем как финальное решение
                return BehaviorDecision(
                    action=BehaviorDecisionType.ACT,
                    capability_name="final_answer.generate",
                    parameters=validated_params,
                    reason="final_answer_before_stop",
                    is_final=True  # ← Явно помечаем что это финальный шаг
                )

            if stop_condition:
                await self._log("warning", f"STOP condition detected: {reasoning_dict.get('stop_reason', 'goal_achieved')}")
                # Если stop_condition=True, но capability_name не final_answer.generate,
                # всё равно вызываем final_answer.generate для формирования ответа
                if capability_name and capability_name != "final_answer.generate":
                    await self._log("info", "STOP без final_answer — добавляем вызов final_answer.generate")
                    return BehaviorDecision(
                        action=BehaviorDecisionType.ACT,
                        capability_name="final_answer.generate",
                        parameters={"input": f"Цель достигнута: {reasoning_dict.get('stop_reason', 'goal_achieved')}"},
                        reason="final_answer_on_stop",
                        is_final=True  # ← Явно помечаем что это финальный шаг
                    )
                    
                return BehaviorDecision(
                    action=BehaviorDecisionType.STOP,
                    reason=reasoning_dict.get("stop_reason", "goal_achieved")
                )

            # КРИТИЧЕСКАЯ ПРОВЕРКА: capability_name должен быть указан
            if not capability_name:
                await self._log("error", "LLM не ��ернул next_action в decision",
                               reasoning_result=reasoning_result)
                return BehaviorDecision(
                    action=BehaviorDecisionType.RETRY,
                    reason="LLM не вернул корре��т��ое действие"
                )
            
            # 3. Поиск capability через сервис
            capability = self.capability_resolver.find_capability(available_capabilities, capability_name)
            
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
            validated_params = self.capability_resolver.validate_parameters(capability, parameters, self.schema_validator, reasoning_dict)

            # 5. Возвращаем решение с ЗАПОЛНЕННЫМ capability_name
            print(f"✅ [_make_decision] Возвращаем BehaviorDecision: action={BehaviorDecisionType.ACT.value}, capability_name={capability_name}", flush=True)
            
            # КРИТИЧНО: Помечаем final_answer.generate как финальный шаг
            is_final = (capability_name == "final_answer.generate")
            
            return BehaviorDecision(
                action=BehaviorDecisionType.ACT,
                capability_name=capability_name,  # ОБЯЗАТЕЛЬНО должно быть заполнено
                parameters=validated_params,
                reason=decision_dict.get("reasoning", "capability_execution"),
                is_final=is_final  # ← Помечаем финальный шаг
            )

        except Exception as e:
            print(f"❌ [_make_decision] Исключение: {e}", flush=True)
            await self._log("error", f"_make_decision_from_reasoning: ошибка",
                           error=str(e),
                           exc_info=True)
            raise

    async def _create_fallback_decision(
        self,
        session_context,
        reason: str,
        available_capabilities: List[Capability]
    ) -> BehaviorDecision:
        """Создает fallback-решение при ошибках через FallbackStrategyService."""
        return self.fallback_strategy.create_error(reason, available_capabilities)