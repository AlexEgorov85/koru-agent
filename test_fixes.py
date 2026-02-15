#!/usr/bin/env python3
"""
Тестирование исправлений для регистрации инструментов и навыков
"""
import asyncio
import sys
import os

# Добавляем путь к проекту
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from core.application.context.application_context import ApplicationContext
from core.config.app_config import AppConfig
from core.infrastructure.context.infrastructure_context import InfrastructureContext
from core.config.config_loader import ConfigLoader


async def test_component_registration():
    """Тестирование регистрации компонентов"""
    print("=== Тестирование регистрации компонентов ===")
    
    # Загружаем системную конфигурацию
    config_loader = ConfigLoader(profile="dev", config_dir="core/config/defaults")
    system_config = config_loader.load()
    
    # Создаем инфраструктурный контекст
    infra_context = InfrastructureContext(config=system_config)
    
    # Инициализируем инфраструктуру
    await infra_context.initialize()
    
    print("Инфраструктурный контекст создан и инициализирован")
    
    # Создаем конфигурацию приложения из реестра
    app_config = AppConfig.from_registry(profile="sandbox")
    
    print(f"Конфигурация приложения загружена:")
    print(f"  - Навыки: {list(app_config.skill_configs.keys())}")
    print(f"  - Инструменты: {list(app_config.tool_configs.keys())}")
    print(f"  - Сервисы: {list(app_config.service_configs.keys())}")
    
    # Создаем прикладной контекст
    app_context = ApplicationContext(
        infrastructure_context=infra_context,
        config=app_config,
        profile="sandbox"
    )
    
    # Включаем отладку
    import logging
    logging.basicConfig(level=logging.DEBUG)
    
    print("Попытка инициализации прикладного контекста...")
    
    # Инициализируем прикладной контекст
    success = await app_context.initialize()
    
    if success:
        print("+ Прикладной контекст успешно инициализирован")
        
        # Проверяем зарегистрированные компоненты
        skills = app_context.components.all_of_type(app_context.ComponentType.SKILL)
        tools = app_context.components.all_of_type(app_context.ComponentType.TOOL)
        services = app_context.components.all_of_type(app_context.ComponentType.SERVICE)
        
        print(f"  - Зарегистрированные навыки: {[skill.name for skill in skills]}")
        print(f"  - Зарегистрированные инструменты: {[tool.name for tool in tools]}")
        print(f"  - Зарегистрированные сервисы: {[service.name for service in services]}")
        
        # Проверяем конкретные навыки
        planning_skill = app_context.get_skill("planning")
        book_library_skill = app_context.get_skill("book_library")
        
        if planning_skill:
            print(f"+ Навык планирования найден: {planning_skill.name}")
        else:
            print("- Навык планирования НЕ найден")
            
        if book_library_skill:
            print(f"+ Навык библиотеки книг найден: {book_library_skill.name}")
        else:
            print("- Навык библиотеки книг НЕ найден")
            
        # Проверяем конкретные инструменты
        sql_tool = app_context.get_tool("sql_tool")
        file_tool = app_context.get_tool("file_tool")
        
        if sql_tool:
            print(f"+ SQL инструмент найден: {sql_tool.name}")
        else:
            print("- SQL инструмент НЕ найден")
            
        if file_tool:
            print(f"+ File инструмент найден: {file_tool.name}")
        else:
            print("- File инструмент НЕ найден")
    else:
        print("- Ошибка инициализации прикладного контекста")
    
    # Завершаем работу инфраструктурного контекста
    await infra_context.shutdown()
    
    print("=== Тестирование завершено ===")


if __name__ == "__main__":
    asyncio.run(test_component_registration())