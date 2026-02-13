#!/usr/bin/env python3
"""
Тестирование сервисов из core\application\services
"""
import sys
import asyncio
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent))

async def test_services():
    print("=== Testing Services ===")
    
    # Тестируем импорт
    try:
        from core.application.services.base_service import BaseService, ServiceInput, ServiceOutput
        print("[OK] BaseService imported successfully")
    except ImportError as e:
        print(f"[ERROR] Failed to import BaseService: {e}")
        return
    
    # Тестируем каждый сервис
    services_to_test = [
        ("PromptService", "core.application.services.prompt_service"),
        ("ContractService", "core.application.services.contract_service"),
        ("TableDescriptionService", "core.application.services.table_description_service"),
        ("SQLValidatorService", "core.application.services.sql_validator.service"),
        ("SQLGenerationService", "core.application.services.sql_generation.service"),
        ("SQLQueryService", "core.application.services.sql_query.service")
    ]
    
    imported_services = {}
    
    for service_name, module_path in services_to_test:
        try:
            module = __import__(module_path, fromlist=[service_name])
            service_class = getattr(module, service_name)
            
            # Проверяем наследование
            if issubclass(service_class, BaseService):
                print(f"[OK] {service_name} imported and inherits from BaseService")
                imported_services[service_name] = service_class
            else:
                print(f"[ERROR] {service_name} does not inherit from BaseService")
                
        except ImportError as e:
            print(f"[ERROR] Failed to import {service_name}: {e}")
        except Exception as e:
            print(f"[ERROR] Error checking {service_name}: {e}")
    
    print(f"\nSuccessfully imported services: {len(imported_services)}/{len(services_to_test)}")
    
    # Проверим зависимости каждого сервиса
    print("\n=== Dependencies Check ===")
    for service_name, service_class in imported_services.items():
        if hasattr(service_class, 'DEPENDENCIES'):
            deps = service_class.DEPENDENCIES
            print(f"{service_name}.DEPENDENCIES = {deps}")
        else:
            print(f"{service_name} does not have DEPENDENCIES attribute")
    
    # Проверим наличие обязательных методов
    print("\n=== Required Methods Check ===")
    required_methods = ['execute', 'initialize', 'shutdown']
    for service_name, service_class in imported_services.items():
        missing_methods = []
        for method in required_methods:
            if not hasattr(service_class, method):
                missing_methods.append(method)
        
        if missing_methods:
            print(f"[ERROR] {service_name} missing methods: {missing_methods}")
        else:
            print(f"[OK] {service_name} has all required methods")
    
    print("\n=== Completed ===")

if __name__ == "__main__":
    asyncio.run(test_services())