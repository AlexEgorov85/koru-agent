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