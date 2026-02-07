"""
Фабрика для создания шлюзов выполнения.
"""
from typing import Optional
from domain.abstractions.system.i_skill_registry import ISkillRegistry
from domain.abstractions.event_types import IEventPublisher
from domain.abstractions.gateways.i_execution_gateway import IExecutionGateway
from application.gateways.execution.execution_gateway import ExecutionGateway


class ExecutionGatewayFactory:
    """
    Фабрика шлюзов выполнения - создает экземпляры шлюзов с инъекцией зависимостей.

    ОТВЕТСТВЕННОСТЬ:
    - Создание шлюзов выполнения с нужными зависимостями
    - Инъекция реестра навыков, шины событий и других компонентов
    """

    @staticmethod
    def create_execution_gateway(
        skill_registry: ISkillRegistry,
        event_publisher: Optional[IEventPublisher] = None,
        prompt_renderer = None
    ) -> IExecutionGateway:
        """
        Создание шлюза выполнения с инъекцией зависимостей.

        ПАРАМЕТРЫ:
        - skill_registry: Реестр навыков
        - event_publisher: Паблишер событий
        - prompt_renderer: Рендерер промтов (опционально)

        ВОЗВРАЩАЕТ:
        - Экземпляр шлюза выполнения с инъекцией зависимостей
        """
        return ExecutionGateway(
            skill_registry=skill_registry,
            prompt_renderer=prompt_renderer,
            event_publisher=event_publisher
        )