import pytest
import sys
import os

# Добавляем путь к проекту
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

def pytest_collection_modifyitems(config, items):
    """
    Модифицируем тесты, чтобы отметить старые как @legacy и @architecture_only
    """
    for item in items:
        # Проверяем, является ли тест старым (из старых папок)
        test_path = str(item.fspath)
        
        # Старые тесты из application/, domain/, orchestration/, system_context/
        if any(legacy_dir in test_path for legacy_dir in [
            '/application/', '\\application\\',
            '/domain/', '\\domain\\', 
            '/orchestration/', '\\orchestration\\',
            '/system_context/', '\\system_context\\'
        ]):
            # Добавляем маркеры legacy и architecture_only для старых тестов
            item.add_marker(pytest.mark.legacy)
            item.add_marker(pytest.mark.architecture_only)

# Определение всех маркеров
def pytest_configure(config):
    config.addinivalue_line(
        "markers", "behavior: marks tests as behavioral tests"
    )
    config.addinivalue_line(
        "markers", "failure: marks tests as failure scenario tests"
    )
    config.addinivalue_line(
        "markers", "legacy: marks tests as legacy tests"
    )
    config.addinivalue_line(
        "markers", "architecture_only: marks tests as architecture-only tests"
    )