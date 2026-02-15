import asyncio
import sys
import os
from pathlib import Path

# Добавляем корневую директорию проекта в путь Python
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.config.config_loader import ConfigLoader
from core.infrastructure.context.infrastructure_context import InfrastructureContext
from core.application.context.application_context import ApplicationContext
from core.config.agent_config import AgentConfig
from core.config.app_config import AppConfig
from core.application.context.application_context import ComponentType


async def main():
    # 1. Поднимаем инфраструктурный контекст
    # Загрузка конфигурации из dev.yaml
    config_loader = ConfigLoader()
    config = config_loader.load()  # Загрузит dev.yaml по умолчанию
    # Создание инфраструктурного контекста с загруженной конфигурацией
    infra = InfrastructureContext(config)

    print("Инициализация инфраструктурного контекста с параметрами из dev.yaml...")
    await infra.initialize()
    print("Инфраструктурный контекст успешно инициализирован!")

    # 2. Создаём контекст
    ctx1 = ApplicationContext(
        infrastructure_context=infra,
        config=AppConfig.from_registry(profile="prod"),
        profile='prod'
    )
    await ctx1.initialize()

    # 3. Получаем сервис sql_query_service
    sql_query_service = ctx1.components.get(ComponentType.SERVICE, 'sql_query_service')
    if sql_query_service:
        print("Сервис sql_query_service:", sql_query_service.__dict__)
    else:
        print("Сервис sql_query_service не найден или равен None")

    # 4. Получаем инструмент sql_tool
    sql_tool = ctx1.components.get(ComponentType.TOOL, 'sql_tool')
    if sql_tool:
        print("Инструмент sql_tool:", sql_tool.__dict__)
    else:
        print("Инструмент sql_tool не найден или равен None")


if __name__ == "__main__":
    asyncio.run(main())