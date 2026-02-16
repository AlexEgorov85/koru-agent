#!/usr/bin/env python3
"""
Скрипт для обновления registry.yaml с добавлением всех capability_types на основе файлов в системе.
"""
import yaml
from pathlib import Path
import re

def update_registry_with_all_capability_types():
    """Обновление registry.yaml с добавлением всех capability_types на основе файлов."""
    
    # Загрузка текущего registry.yaml
    registry_path = Path("registry.yaml")
    if not registry_path.exists():
        print(f"[ERROR] Файл {registry_path} не найден!")
        return
    
    with open(registry_path, 'r', encoding='utf-8') as f:
        registry_data = yaml.safe_load(f)
    
    print("[INFO] Загружен текущий registry.yaml")
    
    # Создание маппинга capability -> тип на основе файлов в системе
    capability_types = registry_data.get('capability_types', {})
    
    # Эвристика для определения типов
    heuristic_map = {
        'planning.': 'skill',
        'analysis.': 'skill',
        'reasoning.': 'skill',
        'sql_generation.': 'tool',
        'file_tool.': 'tool',
        'book_library.': 'skill',
        'llm.': 'service',
        'embedding.': 'service',
        'react.': 'behavior',
        'planning_pattern.': 'behavior',
        'behavior.': 'behavior'
    }
    
    # Сканируем директорию data для поиска файлов
    data_dir = Path("data")
    if data_dir.exists():
        # Сканируем промпты
        prompts_dir = data_dir / "prompts"
        if prompts_dir.exists():
            for type_dir in prompts_dir.iterdir():
                if type_dir.is_dir():
                    for file_path in type_dir.rglob("*.yaml"):
                        # Парсим имя файла: {capability}_v{version}.yaml
                        match = re.match(r'^(.+)_v(\d+\.\d+\.\d+)\.yaml$', file_path.name)
                        if match:
                            capability = match.group(1)
                            if capability not in capability_types:
                                # Применяем эвристику
                                matched = False
                                for prefix, comp_type in heuristic_map.items():
                                    if capability.startswith(prefix):
                                        capability_types[capability] = comp_type
                                        matched = True
                                        print(f"[INFO] Добавлен capability '{capability}' как тип '{comp_type}' (по эвристике)")
                                        break
                                if not matched:
                                    # Не удалось определить — помечаем как 'skill' по умолчанию
                                    capability_types[capability] = 'skill'
                                    print(f"[WARN] Добавлен capability '{capability}' как тип 'skill' (по умолчанию)")
        
        # Сканируем контракты
        contracts_dir = data_dir / "contracts"
        if contracts_dir.exists():
            for type_dir in contracts_dir.iterdir():
                if type_dir.is_dir():
                    for file_path in type_dir.rglob("*.yaml"):
                        # Парсим имя файла: {capability}_{direction}_v{version}.yaml
                        match = re.match(r'^(.+)_([a-z]+)_v(\d+\.\d+\.\d+)\.yaml$', file_path.name)
                        if match:
                            capability = match.group(1)
                            if capability not in capability_types:
                                # Применяем эвристику
                                matched = False
                                for prefix, comp_type in heuristic_map.items():
                                    if capability.startswith(prefix):
                                        capability_types[capability] = comp_type
                                        matched = True
                                        print(f"[INFO] Добавлен capability '{capability}' как тип '{comp_type}' (по эвристике)")
                                        break
                                if not matched:
                                    # Не удалось определить — помечаем как 'skill' по умолчанию
                                    capability_types[capability] = 'skill'
                                    print(f"[WARN] Добавлен capability '{capability}' как тип 'skill' (по умолчанию)")
    
    # Также собираем capability из компонентных конфигураций
    sections = ['services', 'skills', 'tools', 'strategies', 'behaviors']
    for section in sections:
        if section in registry_data:
            for comp_name, comp_config in registry_data[section].items():
                if isinstance(comp_config, dict):
                    # Собираем capability из prompt_versions
                    for cap in comp_config.get('prompt_versions', {}).keys():
                        if cap not in capability_types:
                            # Применяем эвристику
                            matched = False
                            for prefix, comp_type in heuristic_map.items():
                                if cap.startswith(prefix):
                                    capability_types[cap] = comp_type
                                    matched = True
                                    print(f"[INFO] Добавлен capability '{cap}' как тип '{comp_type}' (из компонента {section}.{comp_name})")
                                    break
                            if not matched:
                                # Не удалось определить — помечаем как 'skill' по умолчанию
                                capability_types[cap] = 'skill'
                                print(f"[WARN] Добавлен capability '{cap}' как тип 'skill' (из компонента {section}.{comp_name})")

                    # Собираем capability из input_contract_versions
                    for cap_dir in comp_config.get('input_contract_versions', {}).keys():
                        cap = cap_dir.rsplit('.', 1)[0]
                        if cap not in capability_types:
                            # Применяем эвристику
                            matched = False
                            for prefix, comp_type in heuristic_map.items():
                                if cap.startswith(prefix):
                                    capability_types[cap] = comp_type
                                    matched = True
                                    print(f"[INFO] Добавлен capability '{cap}' как тип '{comp_type}' (из входного контракта компонента {section}.{comp_name})")
                                    break
                            if not matched:
                                # Не удалось определить — помечаем как 'skill' по умолчанию
                                capability_types[cap] = 'skill'
                                print(f"[WARN] Добавлен capability '{cap}' как тип 'skill' (из входного контракта компонента {section}.{comp_name})")

                    # Собираем capability из output_contract_versions
                    for cap_dir in comp_config.get('output_contract_versions', {}).keys():
                        cap = cap_dir.rsplit('.', 1)[0]
                        if cap not in capability_types:
                            # Применяем эвристику
                            matched = False
                            for prefix, comp_type in heuristic_map.items():
                                if cap.startswith(prefix):
                                    capability_types[cap] = comp_type
                                    matched = True
                                    print(f"[INFO] Добавлен capability '{cap}' как тип '{comp_type}' (из выходного контракта компонента {section}.{comp_name})")
                                    break
                            if not matched:
                                # Не удалось определить — помечаем как 'skill' по умолчанию
                                capability_types[cap] = 'skill'
                                print(f"[WARN] Добавлен capability '{cap}' как тип 'skill' (из выходного контракта компонента {section}.{comp_name})")

    # Обновляем capability_types в registry_data
    registry_data['capability_types'] = capability_types
    
    # Сохраняем обновленный registry.yaml
    backup_path = Path("registry.yaml.backup2")
    import shutil
    shutil.copy2(registry_path, backup_path)
    print(f"[INFO] Создана резервная копия: {backup_path}")
    
    with open(registry_path, 'w', encoding='utf-8') as f:
        yaml.dump(registry_data, f, default_flow_style=False, allow_unicode=True, indent=2)
    
    print(f"[INFO] Обновлен {registry_path}")
    print(f"[INFO] Всего типов компонентов: {len(capability_types)}")
    
    print("\n[INFO] Некоторые из добавленных типов:")
    count = 0
    for cap, typ in sorted(capability_types.items()):
        if count < 10:  # Показываем первые 10
            print(f"  {cap}: {typ}")
            count += 1
        else:
            break
    if len(capability_types) > 10:
        print(f"  ... и еще {len(capability_types) - 10}")


if __name__ == "__main__":
    update_registry_with_all_capability_types()
    print("\n[SUCCESS] Регистр обновлен со всеми найденными capability_types!")