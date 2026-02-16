"""
Тестовый сценарий проверки FileSystemDataSource
"""
import tempfile
import shutil
from pathlib import Path
import json
import pytest
from core.infrastructure.storage.file_system_data_source import FileSystemDataSource
from core.config.models import RegistryConfig
from core.models.prompt import Prompt, PromptStatus, ComponentType
from core.models.contract import Contract, ContractDirection


def test_empty_directory_initialize():
    """Тест 1: Пустая директория → initialize() → успешно"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        base_dir = Path(tmp_dir)
        registry_config = RegistryConfig(
            profile="dev",
            capability_types={
                "test.prompt": "skill"
            }
        )
        
        ds = FileSystemDataSource(base_dir, registry_config)
        ds.initialize()
        
        # Проверяем, что директории созданы
        assert ds.prompts_dir.exists()
        assert ds.contracts_dir.exists()


def test_single_valid_prompt():
    """Тест 2: Один корректный prompt → успешно"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        base_dir = Path(tmp_dir)
        registry_config = RegistryConfig(
            profile="dev",
            capability_types={
                "test.skill": "skill"
            }
        )
        
        # Создаем директорию для промптов
        prompts_dir = base_dir / "prompts" / "skill" / "test"
        prompts_dir.mkdir(parents=True)
        
        # Создаем корректный файл промпта
        prompt_data = {
            "capability": "test.skill",
            "version": "v1.0.0",
            "status": "active",
            "component_type": "skill",
            "content": "This is a test prompt with variable {var1}",
            "variables": [
                {
                    "name": "var1",
                    "description": "Test variable",
                    "required": True
                }
            ]
        }
        
        prompt_file = prompts_dir / "test.skill_v1.0.0.json"
        with open(prompt_file, 'w', encoding='utf-8') as f:
            json.dump(prompt_data, f, ensure_ascii=False, indent=2)
        
        ds = FileSystemDataSource(base_dir, registry_config)
        ds.initialize()
        
        # Проверяем, что промпт загружен
        prompts = ds.load_all_prompts()
        assert len(prompts) == 1
        assert prompts[0].capability == "test.skill"
        assert prompts[0].version == "v1.0.0"


def test_corrupted_json_fails():
    """Тест 3: Один повреждённый JSON → initialize() падает"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        base_dir = Path(tmp_dir)
        registry_config = RegistryConfig(
            profile="dev",
            capability_types={
                "test.skill": "skill"
            }
        )
        
        # Создаем директорию для промптов
        prompts_dir = base_dir / "prompts" / "skill" / "test"
        prompts_dir.mkdir(parents=True)
        
        # Создаем поврежденный файл промпта
        prompt_file = prompts_dir / "test.skill_v1.0.0.json"
        with open(prompt_file, 'w', encoding='utf-8') as f:
            f.write("{ invalid json ")  # intentionally broken JSON
        
        ds = FileSystemDataSource(base_dir, registry_config)
        
        # Проверяем, что initialize падает
        with pytest.raises(ValueError):
            ds.initialize()


def test_invalid_prompt_fails():
    """Тест 4: Один невалидный Prompt → initialize() падает"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        base_dir = Path(tmp_dir)
        registry_config = RegistryConfig(
            profile="dev",
            capability_types={
                "test.skill": "skill"
            }
        )
        
        # Создаем директорию для промптов
        prompts_dir = base_dir / "prompts" / "skill" / "test"
        prompts_dir.mkdir(parents=True)
        
        # Создаем невалидный файл промпта (короткое содержание)
        prompt_data = {
            "capability": "test.skill",
            "version": "v1.0.0",
            "status": "active",
            "component_type": "skill",
            "content": "Too short",  # слишком короткое содержание
            "variables": []
        }
        
        prompt_file = prompts_dir / "test.skill_v1.0.0.json"
        with open(prompt_file, 'w', encoding='utf-8') as f:
            json.dump(prompt_data, f, ensure_ascii=False, indent=2)
        
        ds = FileSystemDataSource(base_dir, registry_config)
        
        # Проверяем, что initialize падает
        with pytest.raises(ValueError):
            ds.initialize()


def test_add_new_prompt():
    """Тест 5: Добавление нового prompt → успешно"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        base_dir = Path(tmp_dir)
        registry_config = RegistryConfig(
            profile="dev",
            capability_types={
                "test.skill": "skill"
            }
        )
        
        ds = FileSystemDataSource(base_dir, registry_config)
        ds.initialize()
        
        # Создаем новый промпт
        new_prompt = Prompt(
            capability="test.skill",
            version="v1.0.0",
            status=PromptStatus.ACTIVE,
            component_type=ComponentType.SKILL,
            content="This is a new test prompt with variable {var1}",
            variables=[
                {
                    "name": "var1",
                    "description": "Test variable",
                    "required": True
                }
            ]
        )
        
        # Сохраняем промпт
        ds.save_prompt(new_prompt)
        
        # Проверяем, что промпт доступен
        prompts = ds.load_all_prompts()
        assert len(prompts) == 1
        assert prompts[0].capability == "test.skill"


def test_duplicate_prompt_error():
    """Тест 6: Добавление duplicate → ошибка"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        base_dir = Path(tmp_dir)
        registry_config = RegistryConfig(
            profile="dev",
            capability_types={
                "test.skill": "skill"
            }
        )
        
        ds = FileSystemDataSource(base_dir, registry_config)
        ds.initialize()
        
        # Создаем и сохраняем первый промпт
        prompt1 = Prompt(
            capability="test.skill",
            version="v1.0.0",
            status=PromptStatus.ACTIVE,
            component_type=ComponentType.SKILL,
            content="This is a test prompt with variable {var1}",
            variables=[
                {
                    "name": "var1",
                    "description": "Test variable",
                    "required": True
                }
            ]
        )
        
        ds.save_prompt(prompt1)
        
        # Пытаемся сохранить второй с тем же именем
        prompt2 = Prompt(
            capability="test.skill",  # same capability
            version="v1.0.0",        # same version
            status=PromptStatus.DRAFT,
            component_type=ComponentType.SKILL,
            content="This is another test prompt",
            variables=[]
        )
        
        # Проверяем, что сохранение дубликата вызывает ошибку
        with pytest.raises(ValueError):
            ds.save_prompt(prompt2)


def test_delete_prompt():
    """Тест 7: Удаление prompt → успешно"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        base_dir = Path(tmp_dir)
        registry_config = RegistryConfig(
            profile="dev",
            capability_types={
                "test.skill": "skill"
            }
        )
        
        ds = FileSystemDataSource(base_dir, registry_config)
        ds.initialize()
        
        # Создаем и сохраняем промпт
        prompt = Prompt(
            capability="test.skill",
            version="v1.0.0",
            status=PromptStatus.ACTIVE,
            component_type=ComponentType.SKILL,
            content="This is a test prompt with variable {var1}",
            variables=[
                {
                    "name": "var1",
                    "description": "Test variable",
                    "required": True
                }
            ]
        )
        
        ds.save_prompt(prompt)
        
        # Проверяем, что промпт добавлен
        prompts = ds.load_all_prompts()
        assert len(prompts) == 1
        
        # Удаляем промпт
        prompt_key = f"{prompt.capability}:{prompt.version}"
        ds.delete_prompt(prompt_key)
        
        # Проверяем, что промпт удален
        prompts = ds.load_all_prompts()
        assert len(prompts) == 0


def test_delete_nonexistent_prompt():
    """Тест 8: Повторное удаление → ошибка"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        base_dir = Path(tmp_dir)
        registry_config = RegistryConfig(
            profile="dev",
            capability_types={
                "test.skill": "skill"
            }
        )
        
        ds = FileSystemDataSource(base_dir, registry_config)
        ds.initialize()
        
        # Пытаемся удалить несуществующий промпт
        with pytest.raises(ValueError):
            ds.delete_prompt("non.existent:v1.0.0")


if __name__ == "__main__":
    # Запуск всех тестов
    test_empty_directory_initialize()
    print("✓ Тест 1: Пустая директория → initialize() → успешно")
    
    test_single_valid_prompt()
    print("✓ Тест 2: Один корректный prompt → успешно")
    
    try:
        test_corrupted_json_fails()
        print("✗ Тест 3: Один повреждённый JSON → initialize() падает")
    except AssertionError:
        print("✓ Тест 3: Один повреждённый JSON → initialize() падает")
    
    try:
        test_invalid_prompt_fails()
        print("✗ Тест 4: Один невалидный Prompt → initialize() падает")
    except AssertionError:
        print("✓ Тест 4: Один невалидный Prompt → initialize() падает")
    
    test_add_new_prompt()
    print("✓ Тест 5: Добавление нового prompt → успешно")
    
    try:
        test_duplicate_prompt_error()
        print("✗ Тест 6: Добавление duplicate → ошибка")
    except AssertionError:
        print("✓ Тест 6: Добавление duplicate → ошибка")
    
    test_delete_prompt()
    print("✓ Тест 7: Удаление prompt → успешно")
    
    try:
        test_delete_nonexistent_prompt()
        print("✗ Тест 8: Повторное удаление → ошибка")
    except AssertionError:
        print("✓ Тест 8: Повторное удаление → ошибка")
    
    print("\nВсе тесты выполнены!")