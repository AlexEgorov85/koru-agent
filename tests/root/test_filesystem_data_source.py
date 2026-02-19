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
from core.models.data.prompt import Prompt, PromptStatus, ComponentType
from core.models.data.contract import Contract, ContractDirection


@pytest.fixture
def temp_dir():
    """Фикстура для создания временной директории"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield Path(tmp_dir)


@pytest.fixture
def registry_config():
    """Фикстура для создания стандартной конфигурации реестра"""
    return RegistryConfig(
        profile="dev",
        capability_types={
            "test.skill": "skill"
        }
    )


@pytest.fixture
def initialized_ds(temp_dir, registry_config):
    """Фикстура для создания и инициализации FileSystemDataSource"""
    ds = FileSystemDataSource(temp_dir, registry_config)
    ds.initialize()
    return ds


class TestFileSystemDataSourceInitialize:
    """Тесты инициализации FileSystemDataSource"""

    def test_empty_directory_initialize(self, temp_dir, registry_config):
        """Тест 1: Пустая директория → initialize() → успешно"""
        ds = FileSystemDataSource(temp_dir, registry_config)
        ds.initialize()

        # Проверяем, что директории созданы
        assert ds.prompts_dir.exists()
        assert ds.contracts_dir.exists()


class TestFileSystemDataSourceLoadPrompts:
    """Тесты загрузки промптов"""

    def test_single_valid_prompt(self, temp_dir, registry_config):
        """Тест 2: Один корректный prompt → успешно"""
        # Создаем директорию для промптов
        prompts_dir = temp_dir / "prompts" / "skill" / "test"
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

        ds = FileSystemDataSource(temp_dir, registry_config)
        ds.initialize()

        # Проверяем, что промпт загружен
        prompts = ds.load_all_prompts()
        assert len(prompts) == 1
        assert prompts[0].capability == "test.skill"
        assert prompts[0].version == "v1.0.0"

    def test_corrupted_json_fails(self, temp_dir, registry_config):
        """Тест 3: Один повреждённый JSON → initialize() падает"""
        # Создаем директорию для промптов
        prompts_dir = temp_dir / "prompts" / "skill" / "test"
        prompts_dir.mkdir(parents=True)

        # Создаем поврежденный файл промпта
        prompt_file = prompts_dir / "test.skill_v1.0.0.json"
        with open(prompt_file, 'w', encoding='utf-8') as f:
            f.write("{ invalid json ")  # intentionally broken JSON

        ds = FileSystemDataSource(temp_dir, registry_config)

        # Проверяем, что initialize падает
        with pytest.raises(ValueError):
            ds.initialize()

    def test_invalid_prompt_fails(self, temp_dir, registry_config):
        """Тест 4: Один невалидный Prompt → initialize() падает"""
        # Создаем директорию для промптов
        prompts_dir = temp_dir / "prompts" / "skill" / "test"
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

        ds = FileSystemDataSource(temp_dir, registry_config)

        # Проверяем, что initialize падает
        with pytest.raises(ValueError):
            ds.initialize()


class TestFileSystemDataSourceSavePrompt:
    """Тесты сохранения промптов"""

    def test_add_new_prompt(self, initialized_ds):
        """Тест 5: Добавление нового prompt → успешно"""
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
        initialized_ds.save_prompt(new_prompt)

        # Проверяем, что промпт доступен
        prompts = initialized_ds.load_all_prompts()
        assert len(prompts) == 1
        assert prompts[0].capability == "test.skill"

    def test_duplicate_prompt_error(self, initialized_ds):
        """Тест 6: Добавление duplicate → ошибка"""
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

        initialized_ds.save_prompt(prompt1)

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
            initialized_ds.save_prompt(prompt2)


class TestFileSystemDataSourceDeletePrompt:
    """Тесты удаления промптов"""

    def test_delete_prompt(self, initialized_ds):
        """Тест 7: Удаление prompt → успешно"""
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

        initialized_ds.save_prompt(prompt)

        # Проверяем, что промпт добавлен
        prompts = initialized_ds.load_all_prompts()
        assert len(prompts) == 1

        # Удаляем промпт
        prompt_key = f"{prompt.capability}:{prompt.version}"
        initialized_ds.delete_prompt(prompt_key)

        # Проверяем, что промпт удален
        prompts = initialized_ds.load_all_prompts()
        assert len(prompts) == 0

    def test_delete_nonexistent_prompt(self, initialized_ds):
        """Тест 8: Повторное удаление → ошибка"""
        # Пытаемся удалить несуществующий промпт
        with pytest.raises(ValueError):
            initialized_ds.delete_prompt("non.existent:v1.0.0")
