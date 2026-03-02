"""
Скрипт для замены from_registry() на from_discovery() во всех тестах.
"""
import re
from pathlib import Path

ROOT = Path(__file__).parent.parent

# Паттерны для замены
REPLACEMENTS = [
    # AppConfig.from_registry(profile="prod") -> AppConfig.from_discovery(profile="prod")
    (r'AppConfig\.from_registry\(profile="prod"\)', 'AppConfig.from_discovery(profile="prod", data_dir="data")'),
    (r"AppConfig\.from_registry\(profile='prod'\)", 'AppConfig.from_discovery(profile="prod", data_dir="data")'),
    
    # AppConfig.from_registry(profile="sandbox") -> AppConfig.from_discovery(profile="sandbox")
    (r'AppConfig\.from_registry\(profile="sandbox"\)', 'AppConfig.from_discovery(profile="sandbox", data_dir="data")'),
    (r"AppConfig\.from_registry\(profile='sandbox'\)", 'AppConfig.from_discovery(profile="sandbox", data_dir="data")'),
    
    # AppConfig.from_registry(profile="test") -> AppConfig.from_discovery(profile="sandbox")
    (r'AppConfig\.from_registry\(profile="test"\)', 'AppConfig.from_discovery(profile="sandbox", data_dir="data")'),
    (r"AppConfig\.from_registry\(profile='test'\)", 'AppConfig.from_discovery(profile="sandbox", data_dir="data")'),
    
    # AppConfig.from_registry(profile="prod", registry_path="registry.yaml") -> AppConfig.from_discovery(profile="prod")
    (r'AppConfig\.from_registry\(profile="prod", registry_path="registry\.yaml"\)', 'AppConfig.from_discovery(profile="prod", data_dir="data")'),
    (r"AppConfig\.from_registry\(profile='prod', registry_path='registry\.yaml'\)", 'AppConfig.from_discovery(profile="prod", data_dir="data")'),
    
    # AppConfig.from_registry(profile="prod", registry_path="...") -> AppConfig.from_discovery(profile="prod")
    (r'AppConfig\.from_registry\(profile="prod", registry_path="[^"]+"\)', 'AppConfig.from_discovery(profile="prod", data_dir="data")'),
    (r"AppConfig\.from_registry\(profile='prod', registry_path='[^']+'\)", 'AppConfig.from_discovery(profile="prod", data_dir="data")'),
]

def replace_in_file(file_path: Path) -> int:
    """Замена в одном файле. Возвращает количество замен."""
    try:
        content = file_path.read_text(encoding='utf-8')
        original = content
        
        for pattern, replacement in REPLACEMENTS:
            content = re.sub(pattern, replacement, content)
        
        if content != original:
            file_path.write_text(content, encoding='utf-8')
            return content.count('from_discovery') - original.count('from_discovery')
        return 0
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return 0

def main():
    """Основная функция."""
    # Поиск всех Python файлов в tests/
    test_files = list((ROOT / 'tests').rglob('*.py'))
    
    total_replacements = 0
    modified_files = []
    
    for file_path in test_files:
        # Пропускаем __pycache__ и .pyc файлы
        if '__pycache__' in str(file_path) or file_path.suffix != '.py':
            continue
            
        replacements = replace_in_file(file_path)
        if replacements > 0:
            modified_files.append((file_path, replacements))
            total_replacements += replacements
    
    print(f"Modified {len(modified_files)} files with {total_replacements} total replacements:")
    for file_path, count in modified_files:
        print(f"  - {file_path.relative_to(ROOT)} ({count} replacements)")

if __name__ == '__main__':
    main()
