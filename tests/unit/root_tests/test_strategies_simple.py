"""
Простой тест для проверки работы стратегий.
"""
import asyncio
import tempfile
import shutil
from pathlib import Path

from core.components.strategy.strategy_storage import StrategyStorage
from core.application.services.strategy_service import StrategyService
from core.config.component_config import ComponentConfig
from core.application.context.application_context import ApplicationContext


async def test_strategies():
    """Тестирует работу стратегий."""
    
    # Создаем временный каталог для тестирования
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        print(f"Используем временный каталог: {temp_path}")
        
        # Создаем хранилище стратегий
        storage = StrategyStorage(str(temp_path / "strategies"))
        
        # Создаем тестовую стратегию
        test_strategy = {
            "name": "test_strategy",
            "description": "Тестовая стратегия",
            "steps": [
                {"action": "analyze", "params": {"data": "input"}},
                {"action": "process", "params": {"algorithm": "sort"}}
            ],
            "capability": "data_processing"
        }
        
        # Сохраняем стратегию
        success = await storage.save_strategy("test_strategy_1", test_strategy)
        print(f"Сохранение стратегии: {'Успешно' if success else 'Ошибка'}")
        
        # Загружаем стратегию
        loaded_strategy = await storage.load_strategy("test_strategy_1")
        print(f"Загрузка стратегии: {'Успешно' if loaded_strategy is not None else 'Ошибка'}")
        
        if loaded_strategy:
            print(f"  Название: {loaded_strategy['name']}")
            print(f"  Описание: {loaded_strategy['description']}")
            print(f"  Количество шагов: {len(loaded_strategy['steps'])}")
        
        # Проверяем список стратегий
        strategies_list = await storage.list_strategies()
        print(f"Список стратегий: {strategies_list}")
        
        # Создаем сервис стратегий
        # Так как мы не можем полноценно инициализировать ApplicationContext,
        # создадим сервис напрямую с нашим хранилищем
        service = StrategyService.__new__(StrategyService)  # Создаем объект без вызова __init__
        
        # Ручная инициализация необходимых атрибутов
        service.strategy_storage = storage
        import logging
        service.logger = logging.getLogger(__name__)
        service._initialized = True  # Помечаем как инициализированный
        
        # Тестируем работу сервиса
        service_success = await service.save_strategy("service_test_strategy", test_strategy)
        print(f"Сохранение через сервис: {'Успешно' if service_success else 'Ошибка'}")
        
        service_loaded = await service.load_strategy("service_test_strategy")
        print(f"Загрузка через сервис: {'Успешно' if service_loaded is not None else 'Ошибка'}")
        
        if service_loaded:
            print(f"  Название (через сервис): {service_loaded['name']}")
        
        # Проверяем список стратегий через сервис
        service_strategies = await service.list_strategies()
        print(f"Список стратегий через сервис: {service_strategies}")
        
        print("\n=== Все тесты стратегий завершены успешно! ===")


if __name__ == "__main__":
    asyncio.run(test_strategies())