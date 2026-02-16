#!/usr/bin/env python3
"""
Простой тест для проверки работы ContractService
"""
import tempfile
import os
from pathlib import Path
import yaml
import asyncio

# Добавляем путь к проекту
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.application.services.contract_service import ContractService
from core.models.data.capability import Capability


class MockSystemContext:
    """Мок системного контекста для тестирования"""
    
    def __init__(self, data_dir):
        self.config = MockConfig(data_dir)
        self.capabilities = {
            "test.skill.action": Capability(
                name="test.skill.action",
                description="Test capability",
                parameters_schema={
                    "type": "object",
                    "required": ["param1"],
                    "properties": {
                        "param1": {"type": "string", "minLength": 3},
                        "param2": {"type": "integer", "default": 42}
                    }
                },
                skill_name="TestSkill",
                supported_strategies=["react"]
            )
        }
    
    def get_capability(self, name):
        return self.capabilities.get(name)


class MockConfig:
    """Мок конфигурации"""
    
    def __init__(self, data_dir):
        self.data_dir = data_dir


async def test_simple():
    """Простой тест"""
    print("Создание временной директории...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        print(f"Временная директория: {temp_dir}")
        
        # Создаем структуру каталогов для контрактов
        contracts_dir = Path(temp_dir) / "contracts" / "skills" / "test"
        contracts_dir.mkdir(parents=True, exist_ok=True)
        print(f"Создана директория для контрактов: {contracts_dir}")
        
        # Создаем файл контракта
        contract_file = contracts_dir / "test_skill_action_input_v1.0.0.yaml"
        contract_data = {
            "version": "1.0.0",
            "contract_type": "capability_input",
            "skill": "test",
            "capability": "test.skill.action",
            "schema": {
                "type": "object",
                "required": ["param1"],
                "properties": {
                    "param1": {"type": "string", "minLength": 5},  # теперь minLength 5
                    "param2": {"type": "integer", "default": 999}
                }
            }
        }
        
        with open(contract_file, 'w', encoding='utf-8') as f:
            yaml.dump(contract_data, f, default_flow_style=False, allow_unicode=True)
        
        print(f"Создан файл контракта: {contract_file}")
        print(f"Содержимое файла:")
        with open(contract_file, 'r', encoding='utf-8') as f:
            print(f.read())
        
        # Создаем экземпляр системного контекста
        mock_system_context = MockSystemContext(temp_dir)
        
        # Создаем экземпляр ContractService
        contract_service = ContractService(mock_system_context)
        
        # Инициализируем сервис
        success = await contract_services.initialize()
        print(f"Инициализация успешна: {success}")
        
        # Проверяем, что файл существует
        print(f"Файл существует: {contract_file.exists()}")
        
        # Проверяем, что директория существует
        skill_dir = Path(temp_dir) / "contracts" / "skills" / "test"
        print(f"Директория навыка существует: {skill_dir.exists()}")
        
        # Проверяем содержимое директории
        files_in_dir = list(skill_dir.glob("*"))
        print(f"Файлы в директории: {files_in_dir}")
        
        # Тестируем загрузку конкретной версии
        print("\nПопытка загрузить схему для версии 1.0.0...")
        schema = await contract_services.get_contract_schema("test.skill.action", version="1.0.0")
        print(f"Полученная схема: {schema}")
        
        if schema and "properties" in schema and "param1" in schema["properties"]:
            param1_schema = schema["properties"]["param1"]
            print(f"minLength в схеме: {param1_schema.get('minLength')}")
        else:
            print("Свойства не найдены в схеме")
        
        # Тестируем валидацию
        print("\nПопытка валидации...")
        validation_result = await contract_services.validate(
            capability_name="test.skill.action",
            data={"param1": "valid_str", "param2": 123},
            version="1.0.0"
        )
        print(f"Результат валидации: {validation_result}")


if __name__ == "__main__":
    asyncio.run(test_simple())