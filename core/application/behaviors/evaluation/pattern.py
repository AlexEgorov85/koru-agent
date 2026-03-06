from core.application.behaviors.base_behavior_pattern import BaseBehaviorPattern
from core.application.behaviors.base import BehaviorDecision, BehaviorDecisionType
from core.models.data.capability import Capability
from core.models.data.execution import ExecutionResult
from core.models.enums.common_enums import ExecutionStatus
from core.session_context.session_context import SessionContext
from typing import List, Dict, Any


class EvaluationPattern(BaseBehaviorPattern):
    """
    Паттерн оценки достижения цели.

    АРХИТЕКТУРА:
    - component_name используется для получения config из AppConfig
    - Промпты и контракты загружаются через BaseBehaviorPattern
    - pattern_id генерируется из component_name для совместимости
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
            self.logger.error(f"Ошибка загрузки system prompt: {e}")
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
        assessment_prompt = self.get_prompt("behavior.evaluation")

        if not assessment_prompt:
            self.logger.warning("Промпт для оценки не загружен, используем fallback")
            assessment_prompt = "Оцени достижение цели: {goal}\nКонтекст: {context_summary}"

        # Заменяем переменные в промпте
        evaluation_prompt = self._render_prompt(assessment_prompt, {
            "goal": str(goal),
            "context_summary": str(context_summary)
        })

        try:
            # LLM через infrastructure_context (ПРАВИЛЬНО)
            llm_provider = self.application_context.infrastructure_context.get_provider("default_llm")

            # Получаем output контракт из кэша BaseComponent (ПРАВИЛЬНО)
            output_schema = self.get_output_contract("behavior.evaluation")

            if not output_schema:
                self.logger.warning("Output контракт не загружен, используем fallback схему")
                from pydantic import BaseModel, Field
                from typing import Optional
                
                class EvaluationResult(BaseModel):
                    achieved: bool = Field(description="Достигнута ли цель")
                    partial_progress: bool = Field(description="Есть ли частичный прогресс")
                    confidence: float = Field(ge=0.0, le=1.0, description="Уверенность в оценке")
                    summary: str = Field(description="Краткое резюме")
                    reasoning: str = Field(description="Обоснование оценки")
                
                output_schema = EvaluationResult.model_json_schema()

            from core.models.types.llm_types import LLMRequest, StructuredOutputConfig

            # System prompt из реестра (уже загружен с JSON схемой)
            system_prompt = self.system_prompt_template

            llm_request = LLMRequest(
                prompt=evaluation_prompt,
                system_prompt=system_prompt,
                structured_output=StructuredOutputConfig(
                    output_model="EvaluationResult",
                    schema_def=output_schema
                )
            )

            # Вызов через executor (который использует orchestrator)
            result = await self.executor.execute_action(
                action_name="llm.generate_structured",
                llm_provider=llm_provider,
                parameters={
                    'prompt': evaluation_prompt,
                    'system_prompt': system_prompt,
                    'structured_output': StructuredOutputConfig(
                        output_model="EvaluationResult",
                        schema_def=output_schema
                    )
                }
            )
            
            # Проверка успеха
            if not result.get('success'):
                raise RuntimeError(f"LLM error: {result.get('error')}")
            
            response = result['data']['parsed_content']

            # Оркестратор уже опубликовал событие об успешном ответе
            # === ПРОВЕРКА НА ОШИБКУ LLM ===
            llm_response = response
            if isinstance(response, dict) and 'raw_response' in response:
                llm_response = response['raw_response']

            if getattr(llm_response, 'finish_reason', None) == 'error':
                error_msg = "Неизвестная ошибка LLM"
                if hasattr(llm_response, 'metadata') and llm_response.metadata:
                    if isinstance(llm_response.metadata, dict):
                        error_msg = llm_response.metadata.get('error', error_msg)
                    elif isinstance(llm_response.metadata, str):
                        error_msg = llm_response.metadata
                self.logger.error(f"LLM вернул ошибку при оценке: {error_msg}")

                # Оркестратор уже опубликовал событие об ошибке
                raise RuntimeError(f"Ошибка LLM при оценке: {error_msg}")

            if hasattr(llm_response, 'metadata') and llm_response.metadata and 'error' in llm_response.metadata:
                error_msg = llm_response.metadata['error']
                self.logger.error(f"LLM вернул ошибку в metadata: {error_msg}")

                # Оркестратор уже опубликовал событие об ошибке
                raise RuntimeError(f"Ошибка LLM при оценке: {error_msg}")

            # Обработка результата
            result = response.content if hasattr(response, 'content') else response
            if isinstance(result, str):
                import json
                result = json.loads(result)

            # Создание объекта оценки
            class EvaluationResult:
                def __init__(self, data):
                    self.achieved = data.get("achieved", False)
                    self.partial_progress = data.get("partial_progress", False)
                    self.confidence = data.get("confidence", 0.0)
                    self.summary = data.get("summary", "")
                    self.reasoning = data.get("reasoning", "")
                    self.refined_goal = data.get("refined_goal", goal)

            evaluation = EvaluationResult(result)

            # Принятие решения на основе оценки
            if evaluation.achieved or (evaluation.confidence > 0.8 and not evaluation.partial_progress):
                return BehaviorDecision(
                    action=BehaviorDecisionType.STOP,
                    reason=f"goal_achieved: {evaluation.summary}"
                )
            elif evaluation.confidence < 0.3:
                return BehaviorDecision(
                    action=BehaviorDecisionType.SWITCH,
                    next_pattern="fallback.v1.0.0",
                    reason=f"low_confidence: {evaluation.reasoning}"
                )
            else:
                return BehaviorDecision(
                    action=BehaviorDecisionType.CONTINUE,
                    reason=f"continue_execution: {evaluation.summary}"
                )

        except Exception as e:
            error_msg = f"Ошибка при оценке цели: {e}"
            self.logger.error(error_msg, exc_info=True)

            # Оркестратор опубликует событие при следующем вызове
            return BehaviorDecision(
                action=BehaviorDecisionType.SWITCH,
                next_pattern="fallback.v1.0.0",
                reason=f"evaluation_error: {str(e)}"
            )
