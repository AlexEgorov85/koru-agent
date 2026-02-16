#!/usr/bin/env python3
"""
Тестирование новых компонентов системы.
"""
import asyncio
import tempfile
from pathlib import Path
import yaml

from core.config.registry_loader import RegistryLoader
from core.infrastructure.storage.file_system_data_source import FileSystemDataSource
from core.application.data_repository import DataRepository
from core.models.data.prompt import Prompt, PromptStatus, ComponentType
from core.models.data.contract import Contract, ContractDirection


def test_basic_functionality():
    """Тест основной функциональности новых компонентов"""
    print("=== Тест основной функциональности ===\n")
    
    # Создаём временную директорию
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        
        # Создаём структуру директорий
        (tmp_path / "prompts" / "skills").mkdir(parents=True)
        (tmp_path / "contracts" / "skills" / "planning").mkdir(parents=True)
        
        # Создаём тестовый промпт
        prompt_file = tmp_path / "prompts" / "skills" / "planning.create_plan_v1.0.0.yaml"
        prompt_file.write_text("""
capability: "planning.create_plan"
version: "v1.0.0"
status: "active"
component_type: "skill"
content: "Создай план для цели: {goal}"
variables:
  - name: "goal"
    description: "Целевая задача"
    required: true
metadata: {}
""")
        
        # Создаём тестовый контракт
        contract_file = tmp_path / "contracts" / "skills" / "planning" / "planning.create_plan_input_v1.0.0.yaml"
        contract_file.write_text("""
capability: "planning.create_plan"
version: "v1.0.0"
status: "active"
component_type: "skill"
direction: "input"
schema_data:
  type: "object"
  properties:
    goal:
      type: "string"
      description: "Целевая задача"
  required:
    - "goal"
description: "Входной контракт для планирования"
""")
        
        # Создаём реестр с типами компонентов
        registry_file = tmp_path / "registry.yaml"
        registry_file.write_text("""
profile: "prod"
capability_types:
  planning.create_plan: "skill"
active_prompts:
  planning.create_plan: "v1.0.0"
active_contracts:
  planning.create_plan.input: "v1.0.0"
""")
        
        # Тестируем загрузку
        print("1. Загрузка реестра...")
        registry_loader = RegistryLoader(registry_file)
        registry_config = registry_loader.load(profile="prod")
        print(f"   ✓ Загружено типов компонентов: {len(registry_config.capability_types)}")
        
        # Тестируем источник данных
        print("\n2. Тестирование FileSystemDataSource...")
        ds = FileSystemDataSource(tmp_path, registry_config)
        
        # Загрузка конкретного промпта
        prompt = asyncio.run(ds.load_prompt("planning.create_plan", "v1.0.0"))
        assert isinstance(prompt, Prompt)
        assert prompt.capability == "planning.create_plan"
        assert prompt.component_type == ComponentType.SKILL
        print(f"   ✓ Промпт загружен: {prompt.capability} (тип: {prompt.component_type.value})")
        
        # Загрузка контракта
        contract = asyncio.run(ds.load_contract("planning.create_plan", "v1.0.0", "input"))
        assert isinstance(contract, Contract)
        assert contract.capability == "planning.create_plan"
        assert contract.direction == ContractDirection.INPUT
        print(f"   ✓ Контракт загружен: {contract.capability} ({contract.direction.value})")
        
        # Тестируем репозиторий
        print("\n3. Тестирование DataRepository...")
        repo = DataRepository(ds, profile="prod")
        
        from core.config.app_config import AppConfig
        app_config = AppConfig(
            prompt_versions={"planning.create_plan": "v1.0.0"},
            input_contract_versions={"planning.create_plan.input": "v1.0.0"}
        )
        
        success = asyncio.run(repo.initialize(app_config))
        assert success, "Репозиторий должен инициализироваться успешно"
        print("   ✓ DataRepository инициализирован успешно")
        
        # Проверка получения объектов
        retrieved_prompt = repo.get_prompt("planning.create_plan", "v1.0.0")
        assert isinstance(retrieved_prompt, Prompt)
        print(f"   ✓ Промпт получен из репозитория: {retrieved_prompt.capability}")
        
        retrieved_contract = repo.get_contract("planning.create_plan", "v1.0.0", "input")
        assert isinstance(retrieved_contract, Contract)
        print(f"   ✓ Контракт получен из репозитория: {retrieved_contract.capability}")
        
        # Проверка схемы
        schema_cls = repo.get_contract_schema("planning.create_plan", "v1.0.0", "input")
        print(f"   ✓ Схема скомпилирована: {schema_cls.__name__}")
        
        # Тест валидации
        try:
            schema_cls.model_validate({"goal": "Тестовая цель"})
            print("   ✓ Валидация данных прошла успешно")
        except Exception as e:
            print(f"   ✗ Ошибка валидации: {e}")
            raise
        
        # Тест рендеринга
        rendered = retrieved_prompt.render(goal="Тестовая цель")
        assert "Тестовая цель" in rendered
        print(f"   ✓ Рендеринг промпта успешен: {rendered[:50]}...")
        
        print("\n✓ Все тесты основной функциональности пройдены!")


def test_validation_errors():
    """Тест обработки ошибок валидации"""
    print("\n=== Тест обработки ошибок ===")
    
    # Создаём временную директорию
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        
        # Создаём структуру директорий
        (tmp_path / "prompts" / "skills").mkdir(parents=True)
        
        # Файл промпта БЕЗ объявления типа в реестре
        prompt_file = tmp_path / "prompts" / "skills" / "test.missing_type_v1.0.0.yaml"
        prompt_file.write_text("""
capability: "test.missing_type"
version: "v1.0.0"
status: "active"
component_type: "skill"
content: "Тестовый промпт"
variables: []
""")
        
        # Реестр БЕЗ объявления типа для этого capability
        registry_file = tmp_path / "registry.yaml"
        registry_file.write_text("""
profile: "prod"
capability_types: {}  # ← Пусто!
active_prompts:
  test.missing_type: "v1.0.0"
""")
        
        # Инициализация
        registry_loader = RegistryLoader(registry_file)
        registry_config = registry_loader.load(profile="prod")
        
        ds = FileSystemDataSource(tmp_path, registry_config)
        repo = DataRepository(ds, profile="prod")
        
        from core.config.app_config import AppConfig
        app_config = AppConfig(prompt_versions={"test.missing_type": "v1.0.0"})
        
        # Инициализация должна провалиться с ЧЁТКОЙ ошибкой
        async def run_init():
            return await repo.initialize(app_config)
        
        success = asyncio.run(run_init())
        assert not success, "Инициализация должна провалиться"
        report = repo.get_validation_report()
        assert "не объявлен в конфигурации" in report.lower()
        print("✓ Валидация корректно обнаружила отсутствие типа компонента")


if __name__ == "__main__":
    test_basic_functionality()
    test_validation_errors()
    print("\n🎉 Все тесты пройдены успешно!")