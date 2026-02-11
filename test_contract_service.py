#!/usr/bin/env python3
"""
Тест для проверки работы обновленного ContractService
"""
import tempfile
import os
from pathlib import Path
import yaml
import asyncio

# Добавляем путь к проекту
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.infrastructure.service.contract_service import ContractService


class MockSystemContext:
    """Мок системного контекста для тестирования"""

    def __init__(self, data_dir):
        self.config = MockConfig(data_dir)


class MockConfig:
    """Мок конфигурации"""

    def __init__(self, data_dir):
        self.data_dir = data_dir


async def test_contract_service():
    """Тест работы ContractService с YAML-контрактами"""
    print("Создание временной директории...")

    with tempfile.TemporaryDirectory() as temp_dir:
        print(f"Временная директория: {temp_dir}")

        # Создаем структуру каталогов для контрактов
        contracts_dir = Path(temp_dir) / "contracts" / "skills" / "planning"
        contracts_dir.mkdir(parents=True, exist_ok=True)
        print(f"Создана директория для контрактов: {contracts_dir}")

        # Создаем файл контракта
        contract_file = contracts_dir / "planning_create_plan_input_v1.0.0.yaml"
        contract_data = {
            "version": "1.0.0",
            "contract_type": "input",
            "skill": "planning",
            "capability": "planning.create_plan",
            "schema": {
                "type": "object",
                "required": ["goal"],
                "properties": {
                    "goal": {"type": "string", "minLength": 5},  # теперь minLength 5
                    "max_steps": {"type": "integer", "default": 999}
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
        success = await contract_service.initialize()
        print(f"Инициализация успешна: {success}")

        # Проверяем, что файл существует
        print(f"Файл существует: {contract_file.exists()}")

        # Проверяем, что директория существует
        skill_dir = Path(temp_dir) / "contracts" / "skills" / "planning"
        print(f"Директория навыка существует: {skill_dir.exists()}")

        # Проверяем содержимое директории
        files_in_dir = list(skill_dir.glob("*"))
        print(f"Файлы в директории: {files_in_dir}")

        # Тестируем загрузку конкретной версии
        print("\nПопытка загрузить схему для версии 1.0.0...")
        schema = await contract_service.get_contract_schema("planning.create_plan", version="1.0.0")
        print(f"Полученная схема: {schema}")

        if schema and "properties" in schema and "goal" in schema["properties"]:
            goal_schema = schema["properties"]["goal"]
            print(f"minLength в схеме: {goal_schema.get('minLength')}")
        else:
            print("Свойства не найдены в схеме")

        # Тестируем валидацию
        print("\nПопытка валидации с корректными данными...")
        validation_result = await contract_service.validate(
            capability_name="planning.create_plan",
            data={"goal": "valid_goal", "max_steps": 123},
            version="1.0.0"
        )
        print(f"Результат валидации: {validation_result}")

        print("\nПопытка валидации с некорректными данными...")
        validation_result_invalid = await contract_service.validate(
            capability_name="planning.create_plan",
            data={"goal": "sho"},  # слишком короткий goal (меньше minLength=5)
            version="1.0.0"
        )
        print(f"Результат валидации (некорректные данные): {validation_result_invalid}")

        # Тестируем получение Pydantic модели из схемы
        print("\nПопытка получить Pydantic модель из схемы...")
        try:
            model = await contract_service.get_pydantic_model("planning.create_plan", version="1.0.0")
            if model:
                print(f"Pydantic модель создана: {model}")
                # Попробуем создать экземпляр
                instance = model(goal="valid goal", max_steps=5)
                print(f"Экземпляр модели: {instance}")
            else:
                print("Pydantic модель не создана")
        except Exception as e:
            print(f"Ошибка при создании Pydantic модели: {e}")


if __name__ == "__main__":
    asyncio.run(test_contract_service())