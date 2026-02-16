#!/usr/bin/env python3
"""
Диагностический скрипт для проверки загрузки зависимостей компонентов
"""
import asyncio
import sys
import os
import logging

# Настройка логирования для максимальной диагностики
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Добавляем путь к проекту
sys.path.insert(0, r'c:\Users\Алексей\Documents\WORK\Agent_v5')

import sys
from pathlib import Path
# Добавляем путь к проекту
sys.path.insert(0, str(Path(__file__).parent))

from core.config.models import SystemConfig
from core.infrastructure.context.infrastructure_context import InfrastructureContext
from core.application.context.application_context import ApplicationContext
from core.config.app_config import AppConfig


async def main():
    print("=== Диагностика загрузки зависимостей компонентов ===")
    
    # Создаем системную конфигурацию
    config = SystemConfig(data_dir=r"c:\Users\Алексей\Documents\WORK\Agent_v5\data")
    
    # Создаем инфраструктурный контекст
    print("Создание InfrastructureContext...")
    infra = InfrastructureContext(config)
    
    try:
        print("Инициализация InfrastructureContext...")
        await infra.initialize()
        print("InfrastructureContext успешно инициализирован")
    except Exception as e:
        print(f"Ошибка инициализации InfrastructureContext: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Создаем AppConfig из реестра
    print("Создание AppConfig из реестра...")
    try:
        app_config = AppConfig.from_registry(profile="prod")
        print(f"AppConfig создан: {app_config.config_id}")
        print(f"Конфигурации сервисов: {list(app_config.service_configs.keys())}")
    except Exception as e:
        print(f"Ошибка создания AppConfig: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Создаем ApplicationContext
    print("Создание ApplicationContext...")
    app_context = ApplicationContext(
        infrastructure_context=infra,
        config=app_config,
        profile="prod"
    )
    
    # Включаем максимально подробное логирование
    logger = logging.getLogger('core.application.context.application_context')
    logger.setLevel(logging.DEBUG)
    
    print("Инициализация ApplicationContext...")
    try:
        success = await app_context.initialize()
        if success:
            print("ApplicationContext успешно инициализирован!")
            
            # Проверяем, есть ли prompt_service среди зарегистрированных компонентов
            from core.application.context.application_context import ComponentType
            prompt_service = app_context.components.get(ComponentType.SERVICE, "prompt_service")
            if prompt_service:
                print("✓ prompt_service найден в зарегистрированных компонентах")
                print(f"  Тип: {type(prompt_service)}")
                print(f"  Инициализирован: {getattr(prompt_service, '_initialized', 'N/A')}")
            else:
                print("✗ prompt_service НЕ найден в зарегистрированных компонентах")
                
                # Выведем все зарегистрированные сервисы
                all_services = list(app_context.components.all_of_type(ComponentType.SERVICE))
                print(f"Все зарегистрированные сервисы: {[s.name for s in all_services]}")
            
            # Проверим table_description_service
            table_service = app_context.components.get(ComponentType.SERVICE, "table_description_service")
            if table_service:
                print("✓ table_description_service найден в зарегистрированных компонентах")
                print(f"  Тип: {type(table_service)}")
                print(f"  Инициализирован: {getattr(table_service, '_initialized', 'N/A')}")
            else:
                print("✗ table_description_service НЕ найден в зарегистрированных компонентах")
                
                # Выведем все зарегистрированные сервисы
                all_services = list(app_context.components.all_of_type(ComponentType.SERVICE))
                print(f"Все зарегистрированные сервисы: {[s.name for s in all_services]}")
                
        else:
            print("❌ ApplicationContext не удалось инициализировать")
    except Exception as e:
        print(f"❌ Ошибка инициализации ApplicationContext: {e}")
        import traceback
        traceback.print_exc()
    
    # Завершаем работу
    try:
        await infra.shutdown()
        print("Инфраструктура завершена")
    except Exception as e:
        print(f"Ошибка завершения инфраструктуры: {e}")


if __name__ == "__main__":
    asyncio.run(main())