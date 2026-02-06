"""Глобальные фикстуры pytest"""
import pytest
from tests.fixtures.factories import CodeUnitFactory, ProjectStructureFactory, ContextItemFactory


@pytest.fixture
def sample_code_unit():
    """Фикстура для тестового CodeUnit"""
    return CodeUnitFactory.create_sample_code_unit()


@pytest.fixture
def sample_project_structure():
    """Фикстура для тестовой ProjectStructure"""
    return ProjectStructureFactory.create_sample_project_structure()


@pytest.fixture
def complex_project_structure():
    """Фикстура для сложной ProjectStructure"""
    return ProjectStructureFactory.create_complex_project_structure()


@pytest.fixture
def sample_context_item():
    """Фикстура для тестового ContextItem"""
    return ContextItemFactory.create_sample_context_item()


@pytest.fixture
def multiple_code_units():
    """Фикстура для нескольких CodeUnit"""
    return CodeUnitFactory.create_multiple_code_units()


@pytest.fixture
def multiple_context_items():
    """Фикстура для нескольких ContextItem"""
    return ContextItemFactory.create_multiple_context_items()


@pytest.fixture
def temp_test_directory(tmp_path):
    """Фикстура для временной директории тестов"""
    # Создаем временную директорию для тестов
    test_dir = tmp_path / "test_project"
    test_dir.mkdir()
    
    # Создаем тестовые файлы
    (test_dir / "main.py").write_text("def main(): pass")
    (test_dir / "utils.py").write_text("def helper(): pass")
    
    # Создаем поддиректорию
    subdir = test_dir / "subdir"
    subdir.mkdir()
    (subdir / "module.py").write_text("class TestClass: pass")
    
    return test_dir


@pytest.fixture
def test_config():
    """Фикстура для тестовой конфигурации"""
    return {
        "test_setting": "test_value",
        "debug": True,
        "timeout": 30
    }


@pytest.fixture
def sample_filesystem_structure():
    """Фикстура для тестовой файловой структуры"""
    return {
        "files": [
            "src/main.py",
            "src/utils/helpers.py",
            "src/models/user.py",
            "tests/test_main.py",
            "tests/test_utils.py"
        ],
        "directories": [
            "src",
            "src/utils",
            "src/models",
            "tests"
        ]
    }


@pytest.fixture(autouse=True)
async def clean_prompt_cache():
    """Очистка кэша перед каждым тестом"""
    from application.services.cached_prompt_repository import CachedPromptRepository
    # Очищаем кэши всех экземпляров перед тестом
    CachedPromptRepository.clear_all_caches()
    yield
    # Повторная очистка после теста
    CachedPromptRepository.clear_all_caches()
