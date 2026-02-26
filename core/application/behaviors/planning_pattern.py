"""
Planning паттерн поведения.

РЕАЛИЗУЕТ:
- Декомпозицию сложных целей на подзадачи
- Последовательное упорядочивание подзадач
- Учет зависимостей между подзадачами
"""
from typing import Dict, Any, Optional, List
from core.application.behaviors.base_behavior import BaseBehavior, BehaviorInput, BehaviorOutput


class PlanningInput(BehaviorInput):
    """Входные данные для Planning паттерна."""
    def __init__(self, goal: str, context: Dict[str, Any] = None, available_tools: List[str] = None, constraints: List[str] = None):
        self.goal = goal
        self.context = context or {}
        self.available_tools = available_tools or []
        self.constraints = constraints or []


class PlanningOutput(BehaviorOutput):
    """Выходные данные для Planning паттерна."""
    def __init__(self, plan: List[Dict[str, Any]], decomposition_reasoning: str = None, sequence_reasoning: str = None, is_complete: bool = False):
        self.plan = plan  # Список подзадач с указанием порядка и зависимостей
        self.decomposition_reasoning = decomposition_reasoning
        self.sequence_reasoning = sequence_reasoning
        self.is_complete = is_complete


class PlanningPattern(BaseBehavior):
    """Реализация Planning паттерна поведения."""

    @property
    def description(self) -> str:
        return "Planning паттерн: декомпозиция целей и упорядочивание подзадач"

    def __init__(self, name: str, application_context: 'ApplicationContext', component_config: Optional['ComponentConfig'] = None, executor=None, **kwargs):
        super().__init__(name, application_context, component_config=component_config, executor=executor, **kwargs)

    async def initialize(self) -> bool:
        """Инициализация паттерна поведения."""
        # Вызываем родительскую инициализацию для правильной установки флага _initialized
        result = await super().initialize()
        return result

    async def execute(self, input_data: PlanningInput) -> PlanningOutput:
        """
        Выполнение планирования: декомпозиция цели и упорядочивание подзадач.

        ARGS:
        - input_data: PlanningInput с целью, контекстом, доступными инструментами и ограничениями

        RETURNS:
        - PlanningOutput: план с подзадачами, обоснованиями и флагом завершения
        """
        # Получаем промпты для различных этапов планирования
        decompose_prompt = self.get_cached_prompt_safe("behavior.planning.decompose")
        sequence_prompt = self.get_cached_prompt_safe("behavior.planning.sequence")

        # Получаем контракты для валидации
        decompose_input_contract = self.get_cached_input_contract_safe("behavior.planning.decompose")
        decompose_output_contract = self.get_cached_output_contract_safe("behavior.planning.decompose")
        sequence_input_contract = self.get_cached_input_contract_safe("behavior.planning.sequence")
        sequence_output_contract = self.get_cached_output_contract_safe("behavior.planning.sequence")

        # В реальной реализации здесь будет логика планирования:
        # 1. Декомпозиция цели на подзадачи
        subtasks = [
            {
                "id": "step_1",
                "description": f"Анализ цели: {input_data.goal}",
                "required_tools": [],
                "dependencies": []
            },
            {
                "id": "step_2", 
                "description": "Поиск необходимых ресурсов для достижения цели",
                "required_tools": input_data.available_tools,
                "dependencies": ["step_1"]
            },
            {
                "id": "step_3",
                "description": "Выполнение действий для достижения цели",
                "required_tools": input_data.available_tools,
                "dependencies": ["step_2"]
            },
            {
                "id": "step_4",
                "description": "Проверка достижения цели",
                "required_tools": [],
                "dependencies": ["step_3"]
            }
        ]

        # 2. Определение последовательности выполнения
        sequence = ["step_1", "step_2", "step_3", "step_4"]

        # Обоснования
        decomposition_reasoning = f"Цель '{input_data.goal}' была разбита на 4 логические подзадачи, каждая из которых зависит от предыдущей."
        sequence_reasoning = "Подзадачи упорядочены по причинно-следственной связи: сначала анализ, затем поиск ресурсов, затем выполнение, затем проверка."

        # Формируем план как последовательность подзадач
        plan = []
        for step_id in sequence:
            for subtask in subtasks:
                if subtask["id"] == step_id:
                    plan.append(subtask)
                    break

        return PlanningOutput(
            plan=plan,
            decomposition_reasoning=decomposition_reasoning,
            sequence_reasoning=sequence_reasoning,
            is_complete=False  # В реальном сценарии это определяется по достижению цели
        )

    async def shutdown(self) -> None:
        """Корректное завершение работы паттерна поведения."""
        pass