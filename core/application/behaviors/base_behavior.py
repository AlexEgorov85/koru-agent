"""
Базовый класс для поведенческих паттернов (Behavior Patterns).

АРХИТЕКТУРА:
- Наследуется от BaseComponent для единого интерфейса инициализации
- Поддержка изолированных кэшей для промтов и контрактов
- Взаимодействие ТОЛЬКО через ActionExecutor
- Обязательная инициализация через ComponentConfig
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, TYPE_CHECKING
from core.components.base_component import BaseComponent
from core.config.component_config import ComponentConfig


if TYPE_CHECKING:
    from core.application.context.application_context import ApplicationContext
    from core.application.agent.components.action_executor import ActionExecutor


class BehaviorInput(ABC):
    """Абстрактный класс для входных данных поведенческого паттерна."""
    pass


class BehaviorOutput(ABC):
    """Абстрактный класс для выходных данных поведенческого паттерна."""
    pass


# ============================================================================
# КОНКРЕТНЫЕ КЛАССЫ ВХОДА/ВЫХОДА ДЛЯ ПАТТЕРНОВ (для совместимости с тестами)
# ============================================================================

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


class PlanningInput(BehaviorInput):
    """Входные данные для Planning паттерна."""
    def __init__(self, goal: str, context: Dict[str, Any] = None, available_tools: list = None, constraints: list = None):
        self.goal = goal
        self.context = context or {}
        self.available_tools = available_tools or []
        self.constraints = constraints or []


class PlanningOutput(BehaviorOutput):
    """Выходные данные для Planning паттерна."""
    def __init__(self, plan: list = None, decomposition_reasoning: str = None, sequence_reasoning: str = None, is_complete: bool = False):
        self.plan = plan or []
        self.decomposition_reasoning = decomposition_reasoning
        self.sequence_reasoning = sequence_reasoning
        self.is_complete = is_complete


class BaseBehavior(BaseComponent):
    """
    БАЗОВЫЙ КЛАСС ДЛЯ ПОВЕДЕНИЧЕСКИХ ПАТТЕРНОВ.

    ГАРАНТИИ:
    - Предзагрузка → кэш → выполнение без обращений к хранилищу
    - Четкое разделение ответственностей: декларация ≠ данные ≠ реализация
    - Обязательная инициализация через ComponentConfig
    - Изолированные кэши для каждого экземпляра
    - Взаимодействие ТОЛЬКО через ActionExecutor
    """

    @property
    @abstractmethod
    def description(self) -> str:
        """
        Человекочитаемое описание поведенческого паттерна.
        """
        pass

    def __init__(
        self,
        name: str,
        application_context: 'ApplicationContext',
        component_config: Optional[ComponentConfig] = None,
        executor: 'ActionExecutor' = None,
        **kwargs
    ):
        """
        Инициализация базового поведенческого паттерна.

        ARGS:
        - name: имя поведенческого паттерна
        - application_context: прикладной контекст для доступа к ресурсам
        - component_config: конфигурация компонента с версиями промтов/контрактов
        - executor: ActionExecutor для взаимодействия между компонентами
        - **kwargs: дополнительные параметры
        """
        # Вызов родительского конструктора
        super().__init__(name, application_context, component_config=component_config, executor=executor, **kwargs)

        # Сохраняем executor как атрибут
        self.executor = executor

        # Сохраняем дополнительные параметры
        self.config = kwargs.get('config', {})

    def get_cached_prompt_safe(self, capability_name: str) -> str:
        """
        Безопасное получение промта из кэша.

        ARGS:
        - capability_name: имя capability для получения промта

        RETURNS:
        - str: текст промта или пустая строка если не найден
        """
        self._ensure_initialized()
        return self.prompts.get(capability_name, "")

    def get_cached_input_contract_safe(self, capability_name: str) -> Dict:
        """
        Безопасное получение входного контракта из кэша.

        ARGS:
        - capability_name: имя capability для получения входного контракта

        RETURNS:
        - Dict: схема контракта или пустой словарь если не найден
        """
        self._ensure_initialized()
        return self.input_contracts.get(capability_name, {})

    def get_cached_output_contract_safe(self, capability_name: str) -> Dict:
        """
        Безопасное получение выходного контракта из кэша.

        ARGS:
        - capability_name: имя capability для получения выходного контракта

        RETURNS:
        - Dict: схема контракта или пустой словарь если не найден
        """
        self._ensure_initialized()
        return self.output_contracts.get(capability_name, {})

    def _get_event_type_for_success(self) -> 'EventType':
        """Возвращает тип события для успешного выполнения поведенческого паттерна."""
        # Для поведенческих паттернов нет специального события
        from core.infrastructure.event_bus.event_bus import EventType
        return EventType.AGENT_STARTED

    @abstractmethod
    async def execute(self, input_data: BehaviorInput) -> BehaviorOutput:
        """
        Выполнение поведенческого паттерна с четким контрактом входа/выхода.

        ARGS:
        - input_data: входные данные для поведенческого паттерна

        RETURNS:
        - BehaviorOutput: выходные данные поведенческого паттерна
        """
        pass

    async def shutdown(self) -> None:
        """
        Корректное завершение работы поведенческого паттерна.
        """
        # Базовая реализация - ничего не делаем
        pass