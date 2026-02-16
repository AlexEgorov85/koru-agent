#!/usr/bin/env python3
"""
Скрипт для исправления файлов сокращенных имен, чтобы они соответствовали новой архитектуре.
"""
import yaml
from pathlib import Path

def fix_short_name_files():
    """Исправление файлов сокращенных имен для соответствия новой архитектуре."""
    
    data_dir = Path("data")
    
    # Сначала загрузим registry для получения информации о типах
    registry_path = Path("registry.yaml")
    with open(registry_path, 'r', encoding='utf-8') as f:
        registry_data = yaml.safe_load(f)
    
    capability_types = registry_data.get('capability_types', {})
    
    print(f"[INFO] Загружено {len(capability_types)} типов capability из registry.yaml")
    
    # Найдем все файлы с сокращенными именами (без точки в capability)
    # и исправим их, чтобы capability соответствовал формату category.name
    
    # Обработка файлов промптов
    for prompt_file in data_dir.rglob("prompts/*/*/*.yaml"):
        if prompt_file.is_file():
            with open(prompt_file, 'r', encoding='utf-8') as f:
                content = yaml.safe_load(f)
            
            if content and 'capability' in content:
                capability = content['capability']
                
                # Проверим, содержит ли capability точку
                if '.' not in capability:
                    # Это сокращенное имя, нужно определить полное имя
                    # Определим тип компонента из пути или из registry
                    parent_dir_name = prompt_file.parent.name  # имя подкаталога capability_base
                    
                    # Попробуем найти подходящее полное имя в registry
                    full_capability = None
                    for reg_cap in capability_types.keys():
                        if reg_cap.startswith(f"{capability}.") or reg_cap.startswith(f"{parent_dir_name}."):
                            full_capability = reg_cap
                            break
                    
                    if not full_capability:
                        # Если не найдено, используем формат {parent_dir_name}.{capability}
                        full_capability = f"{parent_dir_name}.{capability}"
                        print(f"[INFO] Используем гипотезу: {capability} -> {full_capability}")
                    
                    # Обновим capability в файле
                    original_capability = content['capability']
                    content['capability'] = full_capability
                    
                    # Сохраним файл
                    with open(prompt_file, 'w', encoding='utf-8') as f:
                        yaml.dump(content, f, default_flow_style=False, allow_unicode=True, indent=2)
                    
                    print(f"[FIXED] Промпт {original_capability} -> {full_capability} в {prompt_file}")
    
    # Обработка файлов контрактов
    for contract_file in data_dir.rglob("contracts/*/*/*.yaml"):
        if contract_file.is_file():
            with open(contract_file, 'r', encoding='utf-8') as f:
                content = yaml.safe_load(f)
            
            if content and 'capability' in content:
                capability = content['capability']
                
                # Проверим, содержит ли capability точку
                if '.' not in capability:
                    # Это сокращенное имя, нужно определить полное имя
                    parent_dir_name = contract_file.parent.name  # имя подкаталога capability_base
                    
                    # Попробуем найти подходящее полное имя в registry
                    full_capability = None
                    for reg_cap in capability_types.keys():
                        if reg_cap.startswith(f"{capability}.") or reg_cap.startswith(f"{parent_dir_name}."):
                            full_capability = reg_cap
                            break
                    
                    if not full_capability:
                        # Если не найдено, используем формат {parent_dir_name}.{capability}
                        full_capability = f"{parent_dir_name}.{capability}"
                        print(f"[INFO] Используем гипотезу: {capability} -> {full_capability}")
                    
                    # Обновим capability в файле
                    original_capability = content['capability']
                    content['capability'] = full_capability
                    
                    # Сохраним файл
                    with open(contract_file, 'w', encoding='utf-8') as f:
                        yaml.dump(content, f, default_flow_style=False, allow_unicode=True, indent=2)
                    
                    print(f"[FIXED] Контракт {original_capability} -> {full_capability} в {contract_file}")
    
    print("[SUCCESS] Исправление файлов сокращенных имен завершено!")


def verify_fixes():
    """Проверка исправлений."""
    data_dir = Path("data")
    
    print("\n[INFO] Проверка исправлений:")
    
    # Проверим несколько файлов
    test_files = [
        "data/prompts/skill/planning/planning_v1.0.0.yaml",
        "data/contracts/skill/planning/planning_input_v1.0.0.yaml",
        "data/contracts/skill/planning/planning_output_v1.0.0.yaml",
        "data/prompts/tool/book_library/book_library_v1.0.0.yaml",
        "data/contracts/tool/book_library/book_library_input_v1.0.0.yaml",
        "data/contracts/tool/book_library/book_library_output_v1.0.0.yaml"
    ]
    
    for file_path in test_files:
        path = Path(file_path)
        if path.exists():
            with open(path, 'r', encoding='utf-8') as f:
                content = yaml.safe_load(f)
            
            capability = content.get('capability', 'NOT_FOUND')
            has_dot = '.' in capability
            status = "[SUCCESS]" if has_dot else "[ERROR - no dot]"
            print(f"  {status} {file_path}: capability='{capability}' (has_dot={has_dot})")
        else:
            print(f"  [MISSING] {file_path}")


if __name__ == "__main__":
    print("Начинаем исправление файлов сокращенных имен...")
    fix_short_name_files()
    verify_fixes()
    print("\n[SUCCESS] Исправление файлов завершено!")