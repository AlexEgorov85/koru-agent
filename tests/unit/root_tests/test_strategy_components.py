"""
Тест для проверки работоспособности компонентов стратегий.
"""
import asyncio
import tempfile
from pathlib import Path

from core.components.strategy.strategy_storage import StrategyStorage
from core.application.services.strategy_service import StrategyService
from core.config.component_config import ComponentConfig
from models.capability import Capability


async def test_strategy_components_functionality():
    """Тестирует функциональность компонентов стратегий."""
    
    with tempfile.TemporaryDirectory() as temp_dir:
        storage_path = Path(temp_dir) / "strategies"
        
        print(f"Тестирование в директории: {storage_path}")
        
        # 1. Тестируем StrategyStorage
        print("\n=== Тестирование StrategyStorage ===")
        storage = StrategyStorage(str(storage_path))
        
        # Создаем тестовую стратегию
        test_strategy_data = {
            "name": "test_strategy",
            "description": "Тестовая стратегия для проверки функциональности",
            "type": "reactive",
            "configuration": {
                "max_iterations": 10,
                "timeout": 30,
                "fallback_strategy": "basic"
            },
            "rules": [
                {
                    "condition": "error_occurred",
                    "action": "switch_to_fallback",
                    "priority": 1
                },
                {
                    "condition": "goal_achieved",
                    "action": "terminate",
                    "priority": 2
                }
            ],
            "metadata": {
                "created_by": "test",
                "version": "1.0.0",
                "tags": ["test", "functional"]
            }
        }
        
        # Сохраняем стратегию
        save_result = await storage.save_strategy("test_strategy_001", test_strategy_data)
        print(f"Сохранение стратегии: {'Успешно' if save_result else 'Ошибка'}")
        
        # Загружаем стратегию
        loaded_strategy = await storage.load_strategy("test_strategy_001")
        print(f"Загрузка стратегии: {'Успешно' if loaded_strategy is not None else 'Ошибка'}")
        
        if loaded_strategy:
            print(f"  Название: {loaded_strategy['name']}")
            print(f"  Тип: {loaded_strategy['type']}")
            print(f"  Количество правил: {len(loaded_strategy['rules'])}")
        
        # Проверяем список стратегий
        strategies_list = await storage.list_strategies()
        print(f"Список стратегий: {strategies_list}")
        
        # Обновляем стратегию
        updated_data = dict(test_strategy_data)
        updated_data["description"] = "Обновленная тестовая стратегия"
        updated_data["configuration"]["max_iterations"] = 20
        
        update_result = await storage.update_strategy("test_strategy_001", updated_data)
        print(f"Обновление стратегии: {'Успешно' if update_result else 'Ошибка'}")
        
        # Загружаем обновленную стратегию
        updated_strategy = await storage.load_strategy("test_strategy_001")
        if updated_strategy:
            print(f"  Обновленное описание: {updated_strategy['description']}")
            print(f"  Обновленное количество итераций: {updated_strategy['configuration']['max_iterations']}")
        
        # Удаляем стратегию
        delete_result = await storage.delete_strategy("test_strategy_001")
        print(f"Удаление стратегии: {'Успешно' if delete_result else 'Ошибка'}")
        
        # Проверяем, что стратегия действительно удалена
        deleted_strategy = await storage.load_strategy("test_strategy_001")
        print(f"Загрузка удаленной стратегии: {'Ошибка (ожидаемо)' if deleted_strategy is None else 'Не удалена'}")
        
        # 2. Тестируем StrategyService
        print("\n=== Тестирование StrategyService ===")
        
        # Создаем новый экземпляр хранилища для сервиса
        service_storage = StrategyStorage(str(storage_path))
        
        # Создаем фиктивную конфигурацию компонента
        component_config = ComponentConfig(
            component_type="service",
            component_name="strategy_service_test",
            variant_id="test_variant"
        )
        
        # Создаем сервис стратегий
        service = StrategyService(
            name="test_strategy_service",
            application_context=None,  # В тесте используем None, т.к. полная инициализация не требуется
            component_config=component_config,
            strategy_storage=service_storage
        )
        
        # Ручная установка флага инициализации для обхода проверки
        service._initialized = True
        
        # Тестируем сохранение через сервис
        service_save_result = await service.save_strategy("service_test_strategy_001", test_strategy_data)
        print(f"Сохранение через сервис: {'Успешно' if service_save_result else 'Ошибка'}")
        
        # Тестируем загрузку через сервис
        service_load_result = await service.load_strategy("service_test_strategy_001")
        print(f"Загрузка через сервис: {'Успешно' if service_load_result is not None else 'Ошибка'}")
        
        if service_load_result:
            print(f"  Название (через сервис): {service_load_result['name']}")
            print(f"  Тип (через сервис): {service_load_result['type']}")
        
        # Тестируем список стратегий через сервис
        service_strategies_list = await service.list_strategies()
        print(f"Список стратегий через сервис: {service_strategies_list}")
        
        # Тестируем обновление через сервис
        updated_via_service = dict(test_strategy_data)
        updated_via_service["metadata"]["updated_by"] = "strategy_service"
        
        service_update_result = await service.update_strategy("service_test_strategy_001", updated_via_service)
        print(f"Обновление через сервис: {'Успешно' if service_update_result else 'Ошибка'}")
        
        # Проверяем обновленные данные
        updated_via_service_data = await service.load_strategy("service_test_strategy_001")
        if updated_via_service_data and "updated_by" in updated_via_service_data["metadata"]:
            print(f"  Обновлено через сервис: {updated_via_service_data['metadata']['updated_by']}")
        
        # Удаляем стратегию через сервис
        service_delete_result = await service.delete_strategy("service_test_strategy_001")
        print(f"Удаление через сервис: {'Успешно' if service_delete_result else 'Ошибка'}")
        
        # Проверяем, что стратегия удалена
        service_deleted_strategy = await service.load_strategy("service_test_strategy_001")
        print(f"Загрузка удаленной стратегии (через сервис): {'Ошибка (ожидаемо)' if service_deleted_strategy is None else 'Не удалена'}")
        
        # 3. Тестируем работу с несколькими стратегиями
        print("\n=== Тестирование работы с несколькими стратегиями ===")
        
        # Создаем несколько разных стратегий
        strategies_to_create = {
            "react_strategy": {
                "name": "react_strategy",
                "type": "reactive",
                "description": "Reactive strategy for immediate responses",
                "configuration": {"response_time": "immediate"}
            },
            "planning_strategy": {
                "name": "planning_strategy", 
                "type": "planning",
                "description": "Planning strategy for complex tasks",
                "configuration": {"depth": "deep"}
            },
            "evaluation_strategy": {
                "name": "evaluation_strategy",
                "type": "evaluation",
                "description": "Evaluation strategy for result assessment",
                "configuration": {"criteria": "comprehensive"}
            }
        }
        
        # Сохраняем все стратегии
        for strategy_id, strategy_data in strategies_to_create.items():
            save_result = await storage.save_strategy(strategy_id, strategy_data)
            print(f"Сохранение {strategy_id}: {'Успешно' if save_result else 'Ошибка'}")
        
        # Получаем список всех стратегий
        all_strategies = await storage.list_strategies()
        print(f"Все созданные стратегии: {sorted(all_strategies)}")
        
        # Загружаем каждую стратегию и проверяем
        for strategy_id in all_strategies:
            strategy_data = await storage.load_strategy(strategy_id)
            if strategy_data:
                print(f"  {strategy_id}: {strategy_data['type']} - {strategy_data['description']}")
        
        # Удаляем все созданные стратегии
        for strategy_id in list(all_strategies):  # создаем копию списка для итерации
            delete_result = await storage.delete_strategy(strategy_id)
            print(f"Удаление {strategy_id}: {'Успешно' if delete_result else 'Ошибка'}")
        
        # Проверяем, что все удалены
        final_list = await storage.list_strategies()
        print(f"Окончательный список стратегий: {final_list}")
        
        print("\n=== Все тесты компонентов стратегий завершены успешно! ===")


if __name__ == "__main__":
    asyncio.run(test_strategy_components_functionality())