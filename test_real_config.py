#!/usr/bin/env python3
"""
Тестирование ApplicationContext с реальной конфигурацией из реестра
"""

import asyncio
import sys
import os

# Добавляем путь к проекту
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.application.context.application_context import ApplicationContext
from core.config.app_config import AppConfig


async def test_real_registry_config():
    """Тестируем с реальной конфигурацией из реестра"""
    print("=== Тестирование с реальной конфигурацией из реестра ===")
    
    # Попробуем создать конфигурацию из реестра
    try:
        app_config = AppConfig.from_registry(profile="prod")
        print(f"Конфигурация загружена: {app_config.config_id}")
        print(f"Количество версий промптов: {len(app_config.prompt_versions)}")
        print(f"Количество версий входных контрактов: {len(app_config.input_contract_versions)}")
        print(f"Количество версий выходных контрактов: {len(app_config.output_contract_versions)}")
        print(f"Количество конфигураций сервисов: {len(app_config.service_configs)}")
        
        # Проверим, есть ли в конфигурации table_description_service
        if app_config.service_configs:
            print(f"Сервисы в конфигурации: {list(app_config.service_configs.keys())}")
        
    except FileNotFoundError:
        print("Файл реестра не найден, создаем минимальную конфигурацию")
        app_config = AppConfig(
            config_id="fallback_config",
            prompt_versions={},
            input_contract_versions={},
            output_contract_versions={},
            service_configs={}
        )
    except Exception as e:
        print(f"Ошибка загрузки конфигурации из реестра: {e}")
        # Создаем fallback конфигурацию
        app_config = AppConfig(
            config_id="fallback_config",
            prompt_versions={},
            input_contract_versions={},
            output_contract_versions={},
            service_configs={}
        )
    
    # Создаем фейковый инфраструктурный контекст
    class FakeInfraContext:
        def __init__(self):
            self.id = "fake_infra_context"
            
        def get_prompt_storage(self):
            # Создаем фейковое хранилище
            class FakeStorage:
                async def exists(self, capability, version):
                    return True  # Предполагаем, что все версии существуют
                
                async def load(self, capability, version):
                    # Создаем фейковый объект промпта
                    class FakePrompt:
                        def __init__(self):
                            class Metadata:
                                class Status:
                                    value = "active"
                                status = Status()
                            self.metadata = Metadata()
                            self.content = f"Fake prompt for {capability} v{version}"
                    return FakePrompt()
            
            return FakeStorage()
            
        def get_contract_storage(self):
            # Создаем фейковое хранилище контрактов
            class FakeContractStorage:
                async def exists(self, capability, version, direction):
                    return True  # Предполагаем, что все версии существуют
                
                async def load(self, capability, version, direction):
                    # Создаем фейковый объект контракта
                    class FakeContract:
                        def __init__(self):
                            self.schema_data = {"type": "object", "properties": {}}
                    return FakeContract()
            
            return FakeContractStorage()
    
    fake_infra = FakeInfraContext()
    
    # Создаем прикладной контекст
    app_context = ApplicationContext(
        infrastructure_context=fake_infra,
        config=app_config,
        profile="prod"
    )
    
    print("Прикладной контекст создан")
    
    # Попробуем инициализировать
    try:
        success = await app_context.initialize()
        print(f"Инициализация успешна: {success}")
        
        if success:
            print(f"Количество компонентов: {len(app_context.components.all_components())}")
            from core.application.context.application_context import ComponentType
            services = app_context.components.all_of_type(ComponentType.SERVICE)
            print(f"Количество сервисов: {len(services)}")
            
            # Выведем имена всех зарегистрированных сервисов
            for service in services:
                print(f"  - {service.name}")
        
    except Exception as e:
        print(f"Ошибка инициализации: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """Основная функция тестирования"""
    print("Тестирование ApplicationContext с реальной конфигурацией из реестра")
    
    await test_real_registry_config()
    
    print("\n[SUCCESS] Тестирование завершено!")


if __name__ == "__main__":
    asyncio.run(main())