import sys
import asyncio
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)

sys.path.insert(0, r'c:/Users/Алексей/Documents/WORK/Agent_v5')

from core.config.models import SystemConfig
from core.infrastructure.context.infrastructure_context import InfrastructureContext
from core.application.context.application_context import ApplicationContext
from core.config.app_config import AppConfig

async def test():
    print("Создание SystemConfig...")
    config = SystemConfig(data_dir=r'c:/Users/Алексей/Documents/WORK/Agent_v5/data')
    
    print("Создание InfrastructureContext...")
    infra = InfrastructureContext(config)
    
    print("Инициализация InfrastructureContext...")
    await infra.initialize()
    print("InfrastructureContext инициализирован")
    
    print("Создание AppConfig из реестра...")
    app_config = AppConfig.from_registry(profile='prod')
    print(f"AppConfig создан: {app_config.config_id}")
    
    print("Создание ApplicationContext...")
    app_context = ApplicationContext(infra, app_config, profile='prod')
    
    print("Инициализация ApplicationContext...")
    success = await app_context.initialize()
    if success:
        print('ApplicationContext успешно инициализирован!')
        
        # Проверяем prompt_service
        from core.application.context.application_context import ComponentType
        prompt_service = app_context.components.get(ComponentType.SERVICE, 'prompt_service')
        if prompt_service:
            print('✓ prompt_service найден в компонентах')
            print(f'  Тип: {type(prompt_service).__name__}')
            print(f'  Инициализирован: {getattr(prompt_service, '_initialized', False)}')
        else:
            print('✗ prompt_service НЕ найден в компонентах')
            
            # Выведем все сервисы
            all_services = list(app_context.components.all_of_type(ComponentType.SERVICE))
            print(f'Все зарегистрированные сервисы: {[s.name for s in all_services]}')
    else:
        print('ApplicationContext не удалось инициализировать')
    
    print("Завершение InfrastructureContext...")
    await infra.shutdown()
    print("Инфраструктура завершена")

if __name__ == "__main__":
    print("Запуск теста...")
    asyncio.run(test())
    print("Тест завершен")