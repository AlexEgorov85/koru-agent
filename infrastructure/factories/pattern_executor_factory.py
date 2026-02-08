"""
Фабрика для создания исполнителей паттернов.
"""
from typing import Optional
from domain.abstractions.pattern_executor import IPatternExecutor
from domain.abstractions.event_types import IEventPublisher
from infrastructure.services.prompt_renderer.prompt_renderer import PromptRenderer
from infrastructure.adapters.pattern_executor import PatternExecutor


class PatternExecutorFactory:
    """
    Фабрика исполнителей паттернов - создает экземпляры исполнителей с инъекцией зависимостей.

    ОТВЕТСТВЕННОСТЬ:
    - Создание исполнителей паттернов с нужными зависимостями
    - Инъекция рендерера промтов, провайдера LLM и других компонентов
    """

    @staticmethod
    def create_pattern_executor(
        prompt_renderer: PromptRenderer,
        llm_provider: Any = None,
        event_publisher: Optional[IEventPublisher] = None,
        snapshot_manager = None
    ) -> IPatternExecutor:
        """
        Создание исполнителя паттернов с инъекцией зависимостей.

        ПАРАМЕТРЫ:
        - prompt_renderer: Рендерер промтов
        - llm_provider: Провайдер LLM
        - event_publisher: Паблишер событий
        - snapshot_manager: Менеджер снапшотов

        ВОЗВРАЩАЕТ:
        - Экземпляр исполнителя паттернов с инъекцией зависимостей
        """
        return PatternExecutor(
            prompt_renderer=prompt_renderer,
            llm_provider=llm_provider,
            event_publisher=event_publisher,
            snapshot_manager=snapshot_manager
        )