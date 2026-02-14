import yaml
import os
from pathlib import Path

def check_yaml_file(filepath):
    """Проверяет синтаксис YAML файла"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        print(f"OK: {filepath}")
        return True
    except Exception as e:
        print(f"ERROR: {filepath} - {e}")
        return False

def check_all_yaml_files(root_dir):
    """Проверяет все YAML файлы в директории"""
    root_path = Path(root_dir)
    yaml_files = list(root_path.rglob("*.yaml")) + list(root_path.rglob("*.yml"))
    
    total = len(yaml_files)
    success = 0
    
    for yaml_file in yaml_files:
        if check_yaml_file(yaml_file):
            success += 1
    
    print(f"\nChecked {total} files, successful: {success}, errors: {total - success}")
    return total == success

if __name__ == "__main__":
    # Проверяем файлы в data/prompts и data/contracts
    print("Checking files in data/prompts:")
    success1 = check_all_yaml_files("data/prompts")
    
    print("\nChecking files in data/contracts:")
    success2 = check_all_yaml_files("data/contracts")
    
    print(f"\nOverall result: {'All files are correct' if success1 and success2 else 'There are errors in files'}")