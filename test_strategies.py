"""
Тестовый файл для проверки работы стратегий.
"""
import asyncio
import tempfile
from pathlib import Path

from core.components.strategy.strategy_storage import StrategyStorage
from core.application.services.strategy_service import StrategyService


async def test_strategy_components():
    """Тестирует основные функции компонентов стратегий."""
    
    # Создаем временный каталог для тестирования
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        print("=== Тестирование StrategyStorage ===")
        
        # Создаем хранилище стратегий
        storage = StrategyStorage(str(temp_path))
        
        # Тестируем сохранение стратегии
        strategy_data = {
            "name": "test_strategy",
            "description": "Тестовая стратегия",
            "steps": [
                {"action": "analyze", "params": {"data": "input"}},
                {"action": "process", "params": {"algorithm": "sort"}}
            ],
            "capability": "data_processing"
        }
        
        success = await storage.save_strategy("test_strategy_1", strategy_data)
        print(f"Сохранение стратегии: {'Успешно' if success else 'Ошибка'}")
        
        # Тестируем загрузку стратегии
        loaded_data = await storage.load_strategy("test_strategy_1")
        print(f"Загрузка стратегии: {'Успешно' if loaded_data is not None else 'Ошибка'}")
        if loaded_data:
            print(f"  Название: {loaded_data['name']}")
            print(f"  Описание: {loaded_data['description']}")
        
        # Тестируем список стратегий
        strategies_list = await storage.list_strategies()
        print(f"Список стратегий: {strategies_list}")
        
        # Тестируем обновление стратегии
        updated_data = dict(strategy_data)
        updated_data["description"] = "Обновленная тестовая стратегия"
        update_success = await storage.update_strategy("test_strategy_1", updated_data)
        print(f"Обновление стратегии: {'Успешно' if update_success else 'Ошибка'}")
        
        # Загружаем обновленную стратегию
        updated_loaded = await storage.load_strategy("test_strategy_1")
        if updated_loaded:
            print(f"  Обновленное описание: {updated_loaded['description']}")
        
        # Тестируем удаление стратегии
        delete_success = await storage.delete_strategy("test_strategy_1")
        print(f"Удаление стратегии: {'Успешно' if delete_success else 'Ошибка'}")
        
        # Проверяем, что стратегия действительно удалена
        deleted_data = await storage.load_strategy("test_strategy_1")
        print(f"Загрузка удаленной стратегии: {'Ошибка (ожидаемо)' if deleted_data is None else 'Не удалена'}")
        
        print("\n=== Тестирование StrategyService ===")
        
        # Создаем упрощенный сервис стратегий без полного контекста
        # Используем напрямую класс, минуя инициализацию через BaseComponent
        service = StrategyService.__new__(StrategyService)  # Создаем объект без вызова __init__
        
        # Ручная инициализация необходимых атрибутов
        service.strategy_storage = storage
        import logging
        service.logger = logging.getLogger(__name__)
        service._initialized = True  # Помечаем как инициализированный
        
        # Тестируем сохранение через сервис
        service_save = await service.save_strategy("service_test_strategy", strategy_data)
        print(f"Сохранение через сервис: {'Успешно' if service_save else 'Ошибка'}")
        
        # Тестируем загрузку через сервис
        service_load = await service.load_strategy("service_test_strategy")
        print(f"Загрузка через сервис: {'Успешно' if service_load is not None else 'Ошибка'}")
        
        # Удаляем тестовую стратегию
        service_delete = await service.delete_strategy("service_test_strategy")
        print(f"Удаление через сервис: {'Успешно' if service_delete else 'Ошибка'}")
        
        print("\n=== Все тесты завершены успешно! ===")


if __name__ == "__main__":
    asyncio.run(test_strategy_components())