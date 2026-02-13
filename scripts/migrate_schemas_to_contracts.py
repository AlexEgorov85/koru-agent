#!/usr/bin/env python3
"""
Скрипт миграции Pydantic-схем в YAML-контракты для ContractService
"""
import sys
import os
from pathlib import Path
import importlib.util
from typing import Dict, Any, Type
from pydantic import BaseModel

# Добавляем путь к проекту
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.application.services.contract_service import ContractService
from models.capability import Capability


def find_pydantic_models_in_file(file_path: Path):
    """Находит все Pydantic-модели в файле"""
    models = {}
    
    # Загружаем модуль динамически
    spec = importlib.util.spec_from_file_location("module", file_path)
    module = importlib.util.module_from_spec(spec)
    
    try:
        spec.loader.exec_module(module)
        
        # Проходим по всем атрибутам модуля
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            
            # Проверяем, является ли атрибут Pydantic-моделью
            if (isinstance(attr, type) and 
                issubclass(attr, BaseModel) and 
                attr != BaseModel):
                models[attr_name] = attr
                
    except Exception as e:
        print(f"Ошибка при загрузке модуля {file_path}: {e}")
    
    return models


def find_all_schema_files(project_root: Path):
    """Находит все файлы schema.py в проекте"""
    schema_files = []
    
    for schema_file in project_root.rglob("schema.py"):
        schema_files.append(schema_file)
    
    return schema_files


def create_mock_system_context(data_dir: Path):
    """Создает мок системного контекста для тестирования"""
    class MockConfig:
        def __init__(self, data_dir):
            self.data_dir = data_dir
    
    class MockSystemContext:
        def __init__(self, data_dir):
            self.config = MockConfig(data_dir)
            self._capabilities = {}
        
        def get_capability(self, name):
            return self._capabilities.get(name)
        
        def list_capabilities(self):
            return list(self._capabilities.keys())
    
    return MockSystemContext(data_dir)


async def migrate_schemas_to_yaml():
    """Основная функция миграции схем в YAML"""
    print("=== Начало миграции Pydantic-схем в YAML-контракты ===")
    
    project_root = Path(__file__).parent
    data_dir = project_root / "data"
    data_dir.mkdir(exist_ok=True)
    
    # Создаем мок системного контекста
    system_context = create_mock_system_context(data_dir)
    
    # Создаем экземпляр ContractService
    contract_service = ContractService(system_context)
    
    # Инициализируем сервис
    await contract_services.initialize()
    
    # Находим все файлы schema.py
    schema_files = find_all_schema_files(project_root)
    
    print(f"Найдено {len(schema_files)} файлов схем")
    
    migration_results = []
    
    for schema_file in schema_files:
        print(f"\nОбработка файла: {schema_file}")
        
        # Находим Pydantic-модели в файле
        models = find_pydantic_models_in_file(schema_file)
        
        print(f"  Найдено {len(models)} Pydantic-моделей")
        
        for model_name, model_class in models.items():
            print(f"    - {model_name}: {model_class}")
            
            # Определяем имя capability на основе пути к файлу
            # Например: core/skills/planning/schema.py -> planning.create_plan_input
            parts = schema_file.parts
            
            # Ищем часть пути, содержащую "skills"
            skill_name = "unknown"
            capability_base = "unknown"
            
            if "skills" in parts:
                skills_idx = parts.index("skills")
                if skills_idx + 1 < len(parts):
                    skill_name = parts[skills_idx + 1]
                    capability_base = skill_name
            
            # Определяем имя capability на основе названия модели
            # Убираем суффиксы типа "Input", "Output", "Request", "Response"
            clean_model_name = model_name
            for suffix in ["Input", "Output", "Request", "Response", "Args", "Params"]:
                if clean_model_name.endswith(suffix):
                    clean_model_name = clean_model_name[:-len(suffix)]
                    break
            
            # Формируем имя capability
            capability_name = f"{capability_base}.{clean_model_name.lower()}"
            
            # Определяем направление (input/output) на основе названия модели
            direction = "input"  # по умолчанию
            if any(suffix in model_name.lower() for suffix in ["output", "response", "result"]):
                direction = "output"
            
            try:
                # Конвертируем Pydantic-модель в YAML-контракт
                result = await contract_services.convert_pydantic_to_yaml(
                    capability_name=capability_name,
                    pydantic_model=model_class,
                    version="1.0.0",
                    direction=direction
                )
                
                print(f"      ✓ Модель {model_name} -> capability {capability_name} ({direction})")
                print(f"        Файл: {result['file_path']}")
                
                migration_results.append({
                    'model_name': model_name,
                    'capability_name': capability_name,
                    'direction': direction,
                    'file_path': result['file_path'],
                    'status': 'success'
                })
                
            except Exception as e:
                print(f"      ✗ Ошибка при конвертации {model_name}: {e}")
                
                migration_results.append({
                    'model_name': model_name,
                    'capability_name': capability_name,
                    'direction': direction,
                    'file_path': None,
                    'status': 'error',
                    'error': str(e)
                })
    
    print(f"\n=== Результаты миграции ===")
    print(f"Всего обработано моделей: {len(migration_results)}")
    print(f"Успешно мигрировано: {len([r for r in migration_results if r['status'] == 'success'])}")
    print(f"С ошибками: {len([r for r in migration_results if r['status'] == 'error'])}")
    
    # Создаем отчет
    report_path = data_dir / "migration_report.txt"
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("Отчет о миграции Pydantic-схем в YAML-контракты\n")
        f.write("=" * 50 + "\n\n")
        
        for result in migration_results:
            f.write(f"Модель: {result['model_name']}\n")
            f.write(f"Capability: {result['capability_name']} ({result['direction']})\n")
            if result['status'] == 'success':
                f.write(f"Файл: {result['file_path']}\n")
                f.write("Статус: УСПЕШНО\n")
            else:
                f.write(f"Ошибка: {result.get('error', 'Неизвестная ошибка')}\n")
                f.write("Статус: ОШИБКА\n")
            f.write("-" * 30 + "\n")
    
    print(f"Отчет сохранен в: {report_path}")
    
    # Проверяем, что контракты теперь можно загружать
    print(f"\n=== Проверка загрузки контрактов ===")
    sample_capability = migration_results[0]['capability_name'] if migration_results else None
    if sample_capability:
        schema = await contract_services.get_contract_schema(sample_capability)
        if schema:
            print(f"✓ Контракт {sample_capability} успешно загружен из YAML")
            print(f"  Свойства: {list(schema.get('properties', {}).keys())}")
        else:
            print(f"✗ Контракт {sample_capability} не найден")
    
    print(f"\n=== Миграция завершена ===")
    return len([r for r in migration_results if r['status'] == 'error']) == 0


if __name__ == "__main__":
    import asyncio
    success = asyncio.run(migrate_schemas_to_yaml())
    sys.exit(0 if success else 1)