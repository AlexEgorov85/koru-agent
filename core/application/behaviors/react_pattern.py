"""
ReAct (Reasoning and Acting) паттерн поведения.

РЕАЛИЗУЕТ:
- Reasoning: генерация мыслей/планов на основе контекста
- Acting: выполнение действий через доступные инструменты
- Observing: анализ результатов действий и обновление контекста
"""
from typing import Dict, Any, Optional
from core.application.behaviors.base_behavior import BaseBehavior, BehaviorInput, BehaviorOutput


class ReActInput(BehaviorInput):
    """Входные данные для ReAct паттерна."""
    def __init__(self, goal: str, context: Dict[str, Any] = None, history: list = None, available_tools: list = None):
        self.goal = goal
        self.context = context or {}
        self.history = history or []
        self.available_tools = available_tools or []


class ReActOutput(BehaviorOutput):
    """Выходные данные для ReAct паттерна."""
    def __init__(self, thought: str = None, action: Dict[str, Any] = None, observation: str = None, is_final: bool = False, updated_context: Dict[str, Any] = None):
        self.thought = thought
        self.action = action
        self.observation = observation
        self.is_final = is_final
        self.updated_context = updated_context or {}


class ReActPattern(BaseBehavior):
    """Реализация ReAct (Reasoning and Acting) паттерна поведения."""

    @property
    def description(self) -> str:
        return "ReAct (Reasoning and Acting) паттерн: цикл размышлений-действий-наблюдений"

    def __init__(self, name: str, application_context: 'ApplicationContext', component_config: Optional['ComponentConfig'] = None, executor=None, **kwargs):
        super().__init__(name, application_context, component_config=component_config, executor=executor, **kwargs)

    async def initialize(self) -> bool:
        """Инициализация паттерна поведения."""
        # Вызываем родительскую инициализацию для правильной установки флага _initialized
        result = await super().initialize()
        return result

    async def execute(self, input_data: ReActInput) -> ReActOutput:
        """
        Выполнение одного шага ReAct цикла.

        ARGS:
        - input_data: ReActInput с целью, контекстом, историей и доступными инструментами

        RETURNS:
        - ReActOutput: мысль, действие, наблюдение, флаг завершения и обновленный контекст
        """
        # Получаем промпты для различных этапов ReAct
        think_prompt = self.get_cached_prompt_safe("behavior.react.think")
        act_prompt = self.get_cached_prompt_safe("behavior.react.act")
        observe_prompt = self.get_cached_prompt_safe("behavior.react.observe")

        # Получаем контракты для валидации
        think_input_contract = self.get_cached_input_contract_safe("behavior.react.think")
        think_output_contract = self.get_cached_output_contract_safe("behavior.react.think")
        act_input_contract = self.get_cached_input_contract_safe("behavior.react.act")
        act_output_contract = self.get_cached_output_contract_safe("behavior.react.act")

        # В реальной реализации здесь будет логика ReAct:
        # 1. Reasoning - генерация мысли на основе цели и контекста
        thought = f"Анализирую цель: {input_data.goal}. Оцениваю текущий контекст и определяю следующий шаг."

        # 2. Acting - выбор действия на основе мысли и доступных инструментов
        action = {
            "tool": "search", 
            "parameters": {
                "query": input_data.goal,
                "context": input_data.context
            }
        }

        # 3. Observing - подготовка к анализу результата действия
        observation = "Ожидаю результат выполнения действия для анализа"

        # Обновляем контекст
        updated_context = input_data.context.copy()
        updated_context['last_action'] = action
        updated_context['last_thought'] = thought

        return ReActOutput(
            thought=thought,
            action=action,
            observation=observation,
            is_final=False,  # В реальном сценарии это определяется по достижению цели
            updated_context=updated_context
        )

    async def shutdown(self) -> None:
        """Корректное завершение работы паттерна поведения."""
        pass