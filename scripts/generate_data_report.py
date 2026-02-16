#!/usr/bin/env python3
"""
Полный отчет по всем файлам в папке data.
"""
import os
from pathlib import Path
import yaml

def generate_full_report():
    """Генерация полного отчета по файлам в папке data."""
    
    data_dir = Path("data")
    if not data_dir.exists():
        print(f"[ERROR] Папка {data_dir} не найдена!")
        return
    
    print("=" * 80)
    print("ПОЛНЫЙ ОТЧЕТ ПО ФАЙЛАМ В ПАПКЕ DATA")
    print("=" * 80)
    
    total_files = 0
    prompt_files = 0
    contract_files = 0
    valid_files = 0
    invalid_files = 0
    
    # Рекурсивно пройдемся по всем файлам
    for root, dirs, files in os.walk(data_dir):
        level = root.replace(str(data_dir), '').count(os.sep)
        indent = ' ' * 2 * level
        print(f"{indent}{Path(root).name}/")
        
        subindent = ' ' * 2 * (level + 1)
        
        for file in files:
            if file.endswith('.yaml'):
                file_path = Path(root) / file
                total_files += 1
                
                # Определим тип файла
                is_prompt = 'prompt' in str(file_path).lower()
                is_contract = 'contract' in str(file_path).lower() or 'input' in file.lower() or 'output' in file.lower()
                
                if is_prompt:
                    prompt_files += 1
                    file_type = "PROMPT"
                elif is_contract:
                    contract_files += 1
                    file_type = "CONTRACT"
                else:
                    file_type = "OTHER"
                
                # Проверим валидность YAML
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = yaml.safe_load(f)
                    
                    # Проверим наличие обязательных полей
                    required_fields_present = True
                    errors = []
                    
                    if file_type == "PROMPT":
                        required_fields = ['capability', 'version', 'status', 'component_type', 'content']
                        for field in required_fields:
                            if field not in content:
                                required_fields_present = False
                                errors.append(f"Отсутствует поле: {field}")
                        
                        # Проверим формат capability
                        if 'capability' in content:
                            cap = content['capability']
                            if '.' not in cap:
                                required_fields_present = False
                                errors.append(f"Capability '{cap}' не содержит точки (должен быть в формате category.name)")
                    
                    elif file_type == "CONTRACT":
                        required_fields = ['capability', 'version', 'status', 'component_type', 'direction']
                        for field in required_fields:
                            if field not in content:
                                required_fields_present = False
                                errors.append(f"Отсутствует поле: {field}")
                        
                        # Проверим формат capability
                        if 'capability' in content:
                            cap = content['capability']
                            if '.' not in cap:
                                required_fields_present = False
                                errors.append(f"Capability '{cap}' не содержит точки (должен быть в формате category.name)")
                    
                    if required_fields_present:
                        valid_files += 1
                        status = "[VALID]"
                    else:
                        invalid_files += 1
                        status = f"[INVALID: {', '.join(errors)}]"
                    
                except Exception as e:
                    invalid_files += 1
                    status = f"[ERROR: {str(e)}]"
                
                print(f"{subindent}- {file} [{file_type}] {status}")
                
                # Если файл валидный, покажем основную информацию
                if 'content' in locals() and required_fields_present:
                    if file_type == "PROMPT" and 'capability' in content:
                        print(f"{subindent}    capability: {content['capability']}")
                        print(f"{subindent}    version: {content.get('version', 'N/A')}")
                        print(f"{subindent}    type: {content.get('component_type', 'N/A')}")
                    elif file_type == "CONTRACT" and 'capability' in content:
                        print(f"{subindent}    capability: {content['capability']}")
                        print(f"{subindent}    version: {content.get('version', 'N/A')}")
                        print(f"{subindent}    type: {content.get('component_type', 'N/A')}")
                        print(f"{subindent}    direction: {content.get('direction', 'N/A')}")
    
    print("\n" + "=" * 80)
    print("СТАТИСТИКА")
    print("=" * 80)
    print(f"Всего файлов: {total_files}")
    print(f"Файлов промптов: {prompt_files}")
    print(f"Файлов контрактов: {contract_files}")
    print(f"Валидных файлов: {valid_files}")
    print(f"Невалидных файлов: {invalid_files}")
    print(f"Процент валидности: {valid_files/total_files*100:.1f}% если total_files > 0" if total_files > 0 else "Нет файлов для расчета")
    
    print("\n" + "=" * 80)
    print("СВОДКА ПО ТИПАМ КОМПОНЕНТОВ")
    print("=" * 80)
    
    # Подсчитаем файлы по типам компонентов
    component_counts = {}
    for root, dirs, files in os.walk(data_dir):
        for file in files:
            if file.endswith('.yaml'):
                file_path = Path(root) / file
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = yaml.safe_load(f)
                    
                    if 'component_type' in content:
                        comp_type = content['component_type']
                        component_counts[comp_type] = component_counts.get(comp_type, 0) + 1
                except:
                    pass  # Файл не валидный YAML
    
    for comp_type, count in component_counts.items():
        print(f"{comp_type}: {count} файлов")


if __name__ == "__main__":
    generate_full_report()