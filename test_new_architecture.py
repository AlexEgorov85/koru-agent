#!/usr/bin/env python3
"""
Тестирование новой архитектуры с зависимостями.
"""

import sys
import os
sys.path.insert(0, os.path.abspath('.'))

def test_base_service_dependencies():
    """Тестирование базового класса сервиса с зависимостями."""
    print("Тестируем базовый класс сервиса с зависимостями...")
    
    from core.infrastructure.services.base_service import BaseService
    from core.config.component_config import ComponentConfig
    from core.errors.architecture_violation import ArchitectureViolationError
    
    # Проверим, что DEPENDENCIES объявлен как ClassVar
    print(f"BaseService.DEPENDENCIES: {BaseService.DEPENDENCIES}")
    
    # Создадим mock системного контекста
    class MockSystemContext:
        def __init__(self):
            self.logger = __import__('logging').getLogger(__name__)
        
        async def get_service(self, name):
            return None  # Пока возвращаем None для теста
    
    # Создадим тестовый компонент конфигурации
    component_config = ComponentConfig(
        variant_id="test_service",
        prompt_versions={},
        input_contract_versions={},
        output_contract_versions={}
    )
    
    # Создадим конкретную реализацию для тестирования
    from core.infrastructure.services.base_service import ServiceInput, ServiceOutput
    
    class ConcreteTestService(BaseService):
        @property
        def description(self):
            return "Test service for dependency testing"
        
        async def execute(self, input_data: ServiceInput) -> ServiceOutput:
            return ServiceOutput()
    
    # Создадим экземпляр сервиса
    try:
        service = ConcreteTestService(
            name="test_service",
            system_context=MockSystemContext(),
            component_config=component_config
        )
        print(f"+ BaseService создан успешно: {service.name}")
        print(f"  - Имя: {service.name}")
        print(f"  - Зависимости: {service.DEPENDENCIES}")
        print(f"  - Инициализирован: {service._initialized}")
        return True
    except Exception as e:
        print(f"- Ошибка создания BaseService: {e}")
        return False

def test_table_description_service():
    """Тестирование сервиса описания таблицы."""
    print("\nТестируем TableDescriptionService...")
    
    from core.infrastructure.services.table_description_service import TableDescriptionService
    from core.config.component_config import ComponentConfig
    
    class MockSystemContext:
        def __init__(self):
            self.logger = __import__('logging').getLogger(__name__)
        
        async def get_service(self, name):
            return None
    
    component_config = ComponentConfig(
        variant_id="table_test",
        prompt_versions={},
        input_contract_versions={},
        output_contract_versions={}
    )
    
    try:
        service = TableDescriptionService(
            system_context=MockSystemContext(),
            component_config=component_config
        )
        print(f"+ TableDescriptionService создан успешно: {service.name}")
        print(f"  - Имя: {service.name}")
        print(f"  - Зависимости: {service.DEPENDENCIES}")
        return True
    except Exception as e:
        print(f"- Ошибка создания TableDescriptionService: {e}")
        return False

def test_sql_generation_service():
    """Тестирование сервиса генерации SQL."""
    print("\nТестируем SQLGenerationService...")
    
    from core.infrastructure.services.sql_generation.service import SQLGenerationService
    from core.config.component_config import ComponentConfig
    
    class MockSystemContext:
        def __init__(self):
            self.logger = __import__('logging').getLogger(__name__)
        
        async def get_service(self, name):
            return None
    
    component_config = ComponentConfig(
        variant_id="sql_gen_test",
        prompt_versions={},
        input_contract_versions={},
        output_contract_versions={}
    )
    
    try:
        service = SQLGenerationService(
            system_context=MockSystemContext(),
            component_config=component_config
        )
        print(f"+ SQLGenerationService создан успешно: {service.name}")
        print(f"  - Имя: {service.name}")
        print(f"  - Зависимости: {service.DEPENDENCIES}")
        return True
    except Exception as e:
        print(f"- Ошибка создания SQLGenerationService: {e}")
        return False

def test_dependency_resolver():
    """Тестирование резолвера зависимостей."""
    print("\nТестируем DependencyResolver...")
    
    try:
        from core.system_context.dependency_resolver import DependencyResolver, ServiceDescriptor
        from core.infrastructure.services.table_description_service import TableDescriptionService
        from core.infrastructure.services.sql_generation.service import SQLGenerationService
        
        # Создаем дескрипторы для тестирования
        descriptors = {
            "table_service": ServiceDescriptor("table_service", TableDescriptionService),
            "sql_gen_service": ServiceDescriptor("sql_gen_service", SQLGenerationService),
        }
        
        print(f"+ Созданы дескрипторы: {list(descriptors.keys())}")
        print(f"  - table_service.dependencies: {TableDescriptionService.DEPENDENCIES}")
        print(f"  - sql_gen_service.dependencies: {SQLGenerationService.DEPENDENCIES}")
        
        return True
    except Exception as e:
        print(f"- Ошибка при тестировании DependencyResolver: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Основная функция тестирования."""
    print("=== Тестирование новой архитектуры с зависимостями ===\n")
    
    tests = [
        test_base_service_dependencies,
        test_table_description_service,
        test_sql_generation_service,
        test_dependency_resolver,
    ]
    
    results = []
    for test_func in tests:
        try:
            result = test_func()
            results.append(result)
        except Exception as e:
            print(f"✗ Ошибка выполнения теста {test_func.__name__}: {e}")
            results.append(False)
    
    print(f"\n=== Результаты ===")
    passed = sum(results)
    total = len(results)
    print(f"Пройдено: {passed}/{total}")
    
    if passed == total:
        print("SUCCESS: Все тесты пройдены! Новая архитектура работает корректно.")
        return True
    else:
        print("FAILURE: Есть ошибки в новой архитектуре.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)