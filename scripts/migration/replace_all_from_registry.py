"""
Скрипт для замены from_registry() на from_discovery() во всех Python файлах.
"""
import re
from pathlib import Path

ROOT = Path(r'c:\Users\Алексей\Documents\WORK\Agent_v5')

def replace_in_file(file_path: Path) -> int:
    """Замена в одном файле. Возвращает количество замен."""
    try:
        content = file_path.read_text(encoding='utf-8')
        original = content
        
        # Замена from_registry на from_discovery
        replacements = [
            # profile="prod"
            (r'from_registry\(profile="prod"\)', 'from_discovery(profile="prod", data_dir="data")'),
            (r"from_registry\(profile='prod'\)", 'from_discovery(profile="prod", data_dir="data")'),
            
            # profile="sandbox"
            (r'from_registry\(profile="sandbox"\)', 'from_discovery(profile="sandbox", data_dir="data")'),
            (r"from_registry\(profile='sandbox'\)", 'from_discovery(profile="sandbox", data_dir="data")'),
            
            # profile="test" -> sandbox
            (r'from_registry\(profile="test"\)', 'from_discovery(profile="sandbox", data_dir="data")'),
            (r"from_registry\(profile='test'\)", 'from_discovery(profile="sandbox", data_dir="data")'),
            
            # С указанием registry_path
            (r'from_registry\(profile="prod", registry_path="[^"]+"\)', 'from_discovery(profile="prod", data_dir="data")'),
            (r"from_registry\(profile='prod', registry_path='[^']+'\)", 'from_discovery(profile="prod", data_dir="data")'),
            (r'from_registry\(profile="sandbox", registry_path="[^"]+"\)', 'from_discovery(profile="sandbox", data_dir="data")'),
            (r"from_registry\(profile='sandbox', registry_path='[^']+'\)", 'from_discovery(profile="sandbox", data_dir="data")'),
        ]
        
        for pattern, replacement in replacements:
            content = re.sub(pattern, replacement, content)
        
        if content != original:
            file_path.write_text(content, encoding='utf-8')
            return original.count('from_registry') - content.count('from_registry')
        return 0
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return 0

def main():
    """Основная функция."""
    directories = ['tests', 'benchmarks']
    
    total_replacements = 0
    modified_files = []
    
    for dir_name in directories:
        dir_path = ROOT / dir_name
        if not dir_path.exists():
            continue
            
        python_files = list(dir_path.rglob('*.py'))
        
        for file_path in python_files:
            # Пропускаем __pycache__ и уже обработанные файлы
            if '__pycache__' in str(file_path):
                continue
            
            # Пропускаем скрипты миграции
            if 'migration' in str(file_path):
                continue
                
            replacements = replace_in_file(file_path)
            if replacements > 0:
                modified_files.append((file_path.relative_to(ROOT), replacements))
                total_replacements += replacements
    
    print(f"Modified {len(modified_files)} files with {total_replacements} total replacements:")
    for file_path, count in modified_files:
        print(f"  - {file_path} ({count} replacements)")
    
    # Проверка что осталось
    remaining = []
    for dir_name in directories:
        dir_path = ROOT / dir_name
        if not dir_path.exists():
            continue
        for file_path in dir_path.rglob('*.py'):
            if '__pycache__' in str(file_path) or 'migration' in str(file_path):
                continue
            try:
                content = file_path.read_text(encoding='utf-8')
                if 'from_registry' in content:
                    remaining.append(file_path.relative_to(ROOT))
            except:
                pass
    
    if remaining:
        print(f"\nFiles still using from_registry ({len(remaining)}):")
        for f in remaining:
            print(f"  - {f}")
    else:
        print("\n✅ All files updated! No more from_registry calls.")

if __name__ == '__main__':
    main()
