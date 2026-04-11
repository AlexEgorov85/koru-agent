from core.agent.behaviors.base_behavior_pattern import BaseBehaviorPattern
from core.agent.behaviors.base import BehaviorDecision, BehaviorDecisionType, Decision
from core.agent.behaviors.services import FallbackStrategyService
from core.infrastructure.logging.event_types import LogEventType
from core.models.data.capability import Capability
from core.models.data.execution import ExecutionResult
from core.models.enums.common_enums import ExecutionStatus
from core.session_context.session_context import SessionContext
from typing import List, Dict, Any, Optional


class EvaluationPattern(BaseBehaviorPattern):
    """
    Паттерн оценки достижения цели.

    АРХИТЕКТУРА:
    - component_name используется для получения config из AppConfig
    - Промпты и контракты загружаются через BaseBehaviorPattern
    - pattern_id генерируется из component_name для совместимости
    - LLM вызовы через LLMOrchestrator (как в ReActPattern)
    """

    def __init__(self, component_name: str, component_config = None, application_context = None, executor = None):
        """Инициализация паттерна.

        ПАРАМЕТРЫ:
        - component_name: Имя компонента (ОБЯЗАТЕЛЬНО, например "evaluation_pattern")
        - component_config: ComponentConfig с resolved_prompts/contracts (из AppConfig)
        - application_context: Прикладной контекст
        - executor: ActionExecutor для взаимодействия
        """
        super().__init__(component_name, component_config, application_context, executor)

        # System prompt для оценки (загружается из реестра)
        self.system_prompt_template: Optional[str] = None
        self.reasoning_schema: Optional[dict] = None

    async def decide(
        self,
        session_context: SessionContext,
        available_capabilities: List[Capability]
    ) -> Decision:
        """Единственное место принятия решений."""
        context = await self.analyze_context(session_context, available_capabilities, {})
        return await self.generate_decision(session_context, available_capabilities, context)

    @property
    def llm_orchestrator(self):
        """
        Получение LLMOrchestrator из application_context.
        
        LLMOrchestrator обеспечивает:
        - Retry при ошибках парсинга
        - Валидацию через JSON Schema
        - Трассировку вызовов
        - Метрики и мониторинг
        """
        if self.application_context and hasattr(self.application_context, 'llm_orchestrator'):
            return self.application_context.llm_orchestrator
        return None

    def _log_debug(self, message: str, **kwargs):
        """Отладочное логирование."""
        self._safe_log_sync("debug", message, **kwargs)

    def _log_info(self, message: str, **kwargs):
        """Информационное логирование."""
        self._safe_log_sync("info", message, **kwargs)

    def _log_warning(self, message: str, **kwargs):
        """Предупреждение."""
        self._safe_log_sync("warning", message, **kwargs)

    def _log_error(self, message: str, **kwargs):
        """Логирование ошибки."""
        self._safe_log_sync("error", message, **kwargs)

    async def _log_self_improvement_thinking(
        self,
        phase: str,
        system_prompt: str,
        user_prompt: str,
        response: str = None,
        success: bool = True,
        error: str = None,
        **kwargs
    ):
        """Логирование размышления (запрос + ответ от LLM) для самообучения."""
        event_type = LogEventType.LLM_RESPONSE if success else LogEventType.LLM_ERROR
        status = "успешно" if success else f"ошибка: {error}"
        msg = f"[Самообучение] {phase}: {status}"
        self._log_info(msg, extra={"event_type": event_type})

    async def _load_evaluation_resources(self) -> bool:
        """Загружает system prompt для оценки из автоматически разделённых промптов.
        
        ДОБАВЛЯЕТ JSON схему из контракта в системный промпт.
        """
        try:
            # ← НОВОЕ: Используем автоматически разделённые промпты
            if 'behavior.evaluation' in self.system_prompts:
                system_prompt_obj = self.system_prompts['behavior.evaluation']
                if hasattr(system_prompt_obj, 'content') and system_prompt_obj.content:
                    self.system_prompt_template = system_prompt_obj.content

            # Fallback: ищем в prompts (для обратной совместимости)
            if not self.system_prompt_template and self.prompts:
                if "behavior.evaluation.system" in self.prompts:
                    system_prompt_obj = self.prompts["behavior.evaluation.system"]
                    if hasattr(system_prompt_obj, 'content') and system_prompt_obj.content:
                        self.system_prompt_template = system_prompt_obj.content

            # Загружаем схему из контракта
            if self.output_contracts and "behavior.evaluation" in self.output_contracts:
                schema_cls = self.output_contracts["behavior.evaluation"]
                if schema_cls and hasattr(schema_cls, 'model_json_schema'):
                    self.reasoning_schema = schema_cls.model_json_schema()

            # === ДОБАВЛЕНИЕ JSON СХЕМЫ В СИСТЕМНЫЙ ПРОМПТ ===
            if hasattr(self, 'reasoning_schema') and self.reasoning_schema and self.system_prompt_template:
                self.system_prompt_template = self._inject_schema_into_system_prompt(
                    self.system_prompt_template,
                    self.reasoning_schema
                )

            return self.system_prompt_template is not None
        except Exception as e:
            self._log_error(f"Ошибка загрузки system prompt: {e}", exc_info=True)
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
        
        # Проверяем есть ли уже схема в промпте
        if 'JSON' in system_prompt.upper() and 'SCHEMA' in system_prompt.upper():
            return system_prompt
        
        # Генерируем JSON схему для промпта
        schema_json = json.dumps(schema, indent=2, ensure_ascii=False)
        
        # Добавляем схему в конец системного промпта
        return f"""{system_prompt}

=== JSON СХЕМА ОТВЕТА ===
Ты ДОЛЖЕН вернуть JSON следующей структуры:

```json
{schema_json}
```

ОБЯЗАТЕЛЬНЫЕ ПОЛЯ: {', '.join(schema.get('required', []))}

ВАЖНО: Верни ТОЛЬКО JSON без дополнительных пояснений."""

    async def analyze_context(
        self,
        session_context: SessionContext,
        available_capabilities: List[Capability],
        context_analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Анализ контекста без принятия решений"""
        return {
            "goal": session_context.get_goal(),
            "context_summary": session_context.get_summary(),
            "available_capabilities": available_capabilities
        }

    async def generate_decision(
        self,
        session_context: SessionContext,
        available_capabilities: List[Capability],
        context_analysis: Dict[str, Any]
    ) -> BehaviorDecision:
        """
        Оценка достижения цели через LLM.

        АРХИТЕКТУРА:
        - Использует промпт из self.prompts (загружен BaseComponent.initialize())
        - Использует output контракт из self.output_contracts
        - LLM через infrastructure_context (не session_context!)
        - JSON схема добавляется в системный промпт автоматически
        """
        # ← НОВОЕ: Загружаем system prompt если ещё не загружен
        if not self.system_prompt_template:
            await self._load_evaluation_resources()

        # Проверка что промпт загружен
        if not self.system_prompt_template:
            raise RuntimeError(
                "system_prompt_template не загружен! "
                "Промпт должен быть загружен при инициализации из PromptService."
            )
        
        # Подготовка контекста для оценки
        goal = context_analysis["goal"]
        context_summary = context_analysis["context_summary"]

        # Получение промпта из кэша BaseComponent
        prompt_obj = self.get_prompt("behavior.evaluation")
        assessment_prompt = prompt_obj.content if prompt_obj else ""

        if not assessment_prompt:
            from core.errors.exceptions import SkillExecutionError
            raise SkillExecutionError(
                f"Промпт для behavior.evaluation не загружен! Проверьте YAML в data/prompts/behavior/",
                component="evaluation_behavior"
            )

        # Заменяем переменные в промпте
        evaluation_prompt = self._render_prompt(assessment_prompt, {
            "goal": str(goal),
            "context_summary": str(context_summary)
        })

        try:
            # === РАЗВЁРНУТОЕ ЛОГИРОВАНИЕ САМООБУЧЕНИЯ ===
            # 1. Запуск размышления
            await self._log_self_improvement_thinking(
                phase="evaluation",
                system_prompt=self.system_prompt_template,
                user_prompt=evaluation_prompt,
            )

            # 2. Логирование начала оценки
            self._log_info(f"🔍 Оценка достижения цели: {goal}.")

            # Получаем LLM провайдер через executor (REFACTOR: требуется миграция на executor.execute_action)
            llm_result = await self.executor.execute_action(
                action_name="llm.generate_structured",
                parameters={
                    "prompt": evaluation_prompt,
                    "system_prompt": self.system_prompt_template,
                    "temperature": 0.3,
                    "max_tokens": 1000,
                    "structured_output": {
                        "output_model": "EvaluationResult",
                        "schema_def": output_schema,
                        "max_retries": 3,
                        "strict_mode": False
                    }
                },
                context=self.execution_context
            )
            
            # Используем результат от executor.execute_action()
            if not llm_result.status.name == "COMPLETED":
                error_msg = f"LLM evaluation failed: {llm_result.error}"
                self._log_error(error_msg)
                await self._log_self_improvement_thinking(
                    phase="evaluation",
                    system_prompt=self.system_prompt_template,
                    user_prompt=evaluation_prompt,
                    success=False,
                    error=error_msg
                )
                raise RuntimeError(error_msg)

            # Извлекаем результат
            # ✅ ИСПРАВЛЕНО: Сохраняем Pydantic модель для типизированного доступа
            result = llm_result.result
            if hasattr(result, 'parsed_content'):
                result = result.parsed_content  # ← Pydantic модель, не dict!
            elif isinstance(result, dict):
                result = result.get('parsed_content', result)

            # 3. Логирование завершения размышления с ответом
            response_text = str(result)
            await self._log_self_improvement_thinking(
                phase="evaluation",
                system_prompt=self.system_prompt_template,
                user_prompt=evaluation_prompt,
                response=response_text,
                success=True
            )

            # Логирование успешной оценки
            confidence_val = result.confidence if hasattr(result, 'confidence') else result.get('confidence', 0)
            self._log_info(f"✅ Оценка завершена: confidence={confidence_val:.2f}")

            # Принятие решения на основе оценки
            # ✅ Используем атрибуты модели вместо dict.get()
            achieved = result.achieved if hasattr(result, 'achieved') else result.get("achieved", False)
            partial_progress = result.partial_progress if hasattr(result, 'partial_progress') else result.get("partial_progress", False)
            confidence = confidence_val
            summary = result.summary if hasattr(result, 'summary') else result.get("summary", "")
            reasoning = result.reasoning if hasattr(result, 'reasoning') else result.get("reasoning", "")

            if achieved or (confidence > 0.8 and not partial_progress):
                self._log_info(f"🎯 Цель достигнута: {summary}")
                return BehaviorDecision(
                    action=BehaviorDecisionType.STOP,
                    reason=f"goal_achieved: {summary}"
                )
            elif confidence < 0.3:
                self._log_warning(f"⚠️ Низкая уверенность: {reasoning}")
                return BehaviorDecision(
                    action=BehaviorDecisionType.FAIL,
                    reason=f"low_confidence: {reasoning}"
                )
            else:
                self._log_info(f"🔄 Продолжаем выполнение: {summary}")
                return BehaviorDecision(
                    action=BehaviorDecisionType.CONTINUE,
                    reason=f"continue_execution: {summary}"
                )

        except Exception as e:
            error_msg = f"Ошибка при оценке цели: {e}"
            self._log_error(error_msg, exc_info=True)

            return BehaviorDecision(
                action=BehaviorDecisionType.FAIL,
                reason=f"evaluation_error: {str(e)}"
            )
