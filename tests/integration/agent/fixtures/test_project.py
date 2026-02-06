import tempfile
from pathlib import Path

def create_test_project_structure() -> Path:
    """Создаёт временную структуру проекта для анализа."""
    base_path = Path(tempfile.mkdtemp(prefix="test_agent_project_"))
    
    # Создаём файлы для анализа
    (base_path / "main.py").write_text("def main():\n    pass\n")
    (base_path / "utils.py").write_text("def helper():\n    return 42\n")
    (base_path / "config.json").write_text('{"debug": true}')
    (base_path / "data").mkdir()
    (base_path / "data" / "sample.txt").write_text("test data")
    
    return base_path

def cleanup_test_project(path: Path):
    """Очистка временной структуры."""
    import shutil
    shutil.rmtree(path, ignore_errors=True)