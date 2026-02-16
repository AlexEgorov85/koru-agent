#!/usr/bin/env python3
"""
Скрипт для очистки и правильной организации папки data.
"""
import os
import shutil
from pathlib import Path
import yaml
import re

def clean_and_organize_data_folder():
    """Очистка и правильная организация папки data."""
    
    data_dir = Path("data")
    if not data_dir.exists():
        print(f"[ERROR] Папка {data_dir} не найдена!")
        return
    
    # Загрузим registry.yaml для получения информации о типах
    registry_path = Path("registry.yaml")
    if not registry_path.exists():
        print(f"[ERROR] Файл {registry_path} не найден!")
        return
    
    with open(registry_path, 'r', encoding='utf-8') as f:
        registry_data = yaml.safe_load(f)
    
    capability_types = registry_data.get('capability_types', {})
    
    print(f"[INFO] Загружено {len(capability_types)} типов capability из registry.yaml")
    
    # Создаем новую структуру папок
    new_structure = {
        'prompts': ['skill', 'tool', 'service', 'behavior'],
        'contracts': ['skill', 'tool', 'service', 'behavior']
    }
    
    for parent_dir, subdirs in new_structure.items():
        parent_path = data_dir / parent_dir
        if parent_path.exists():
            for subdir in subdirs:
                # Создаем подкаталоги для каждого типа
                (parent_path / subdir).mkdir(exist_ok=True)
    
    print("[INFO] Создана новая структура папок")
    
    # Функция для правильного размещения файлов промптов
    def organize_prompt_files():
        """Правильное размещение файлов промптов."""
        prompts_dir = data_dir / "prompts"
        
        # Сначала удалим старые структуры (skills, tools и т.д.)
        old_dirs = ['skills', 'tools', 'services', 'behaviors', 'strategies']
        for old_dir in old_dirs:
            old_path = prompts_dir / old_dir
            if old_path.exists() and old_path.is_dir():
                print(f"[INFO] Удаление старой папки: {old_path}")
                import shutil
                shutil.rmtree(old_path)
        
        # Теперь обработаем все оставшиеся файлы
        for item in prompts_dir.iterdir():
            if item.is_dir() and item.name not in ['skill', 'tool', 'service', 'behavior']:
                # Это подпапка с capability, переместим файлы из нее
                for capability_dir in item.iterdir():
                    if capability_dir.is_dir():
                        for file_path in capability_dir.rglob("*.yaml"):
                            if file_path.is_file():
                                # Прочитаем файл, чтобы получить capability
                                try:
                                    with open(file_path, 'r', encoding='utf-8') as f:
                                        content = yaml.safe_load(f)
                                    
                                    if content and 'capability' in content:
                                        file_capability = content['capability']
                                        
                                        if file_capability in capability_types:
                                            target_type = capability_types[file_capability]
                                            
                                            # Разбиваем file_capability на части
                                            cap_parts = file_capability.split('.')
                                            if len(cap_parts) >= 2:
                                                cap_main = cap_parts[0]
                                                
                                                # Создаем новую структуру
                                                new_dir = prompts_dir / target_type / cap_main
                                                new_dir.mkdir(parents=True, exist_ok=True)
                                                
                                                # Формируем новое имя файла
                                                version = content.get('version', 'v1.0.0')
                                                new_filename = f"{file_capability}_{version}.yaml"
                                                new_path = new_dir / new_filename
                                                
                                                # Копируем файл в новое место
                                                if not new_path.exists():
                                                    shutil.copy2(str(file_path), str(new_path))
                                                    print(f"[INFO] Перемещен промпт {file_capability} в {new_path}")
                                                else:
                                                    # Проверим, может быть это дубликат
                                                    with open(new_path, 'r', encoding='utf-8') as f:
                                                        existing_content = yaml.safe_load(f)
                                                    
                                                    if existing_content.get('version') == content.get('version'):
                                                        print(f"[INFO] Файл уже существует с той же версией: {new_path}")
                                                    else:
                                                        print(f"[WARN] Файл уже существует с другой версией: {new_path}")
                                            else:
                                                print(f"[WARN] Неверный формат capability: {file_capability}")
                                        else:
                                            print(f"[WARN] Capability {file_capability} не найден в registry, пропускаем файл: {file_path}")
                                    else:
                                        print(f"[WARN] Не найдено поле capability в файле: {file_path}")
                                        
                                except Exception as e:
                                    print(f"[ERROR] Ошибка чтения файла {file_path}: {e}")
    
    # Функция для правильного размещения файлов контрактов
    def organize_contract_files():
        """Правильное размещение файлов контрактов."""
        contracts_dir = data_dir / "contracts"
        
        # Сначала удалим старые структуры (skills, tools и т.д.)
        old_dirs = ['skills', 'tools', 'services', 'behaviors']
        for old_dir in old_dirs:
            old_path = contracts_dir / old_dir
            if old_path.exists() and old_path.is_dir():
                print(f"[INFO] Удаление старой папки: {old_path}")
                import shutil
                shutil.rmtree(old_path)
        
        # Теперь обработаем все оставшиеся файлы
        for item in contracts_dir.iterdir():
            if item.is_dir() and item.name not in ['skill', 'tool', 'service', 'behavior']:
                # Это подпапка с capability, переместим файлы из нее
                for capability_dir in item.iterdir():
                    if capability_dir.is_dir():
                        for file_path in capability_dir.rglob("*.yaml"):
                            if file_path.is_file():
                                # Прочитаем файл, чтобы получить capability
                                try:
                                    with open(file_path, 'r', encoding='utf-8') as f:
                                        content = yaml.safe_load(f)
                                    
                                    if content and 'capability' in content:
                                        file_capability = content['capability']
                                        
                                        if file_capability in capability_types:
                                            target_type = capability_types[file_capability]
                                            
                                            # Разбиваем file_capability на части
                                            cap_parts = file_capability.split('.')
                                            if len(cap_parts) >= 2:
                                                cap_main = cap_parts[0]
                                                
                                                # Создаем новую структуру
                                                new_dir = contracts_dir / target_type / cap_main
                                                new_dir.mkdir(parents=True, exist_ok=True)
                                                
                                                # Формируем новое имя файла
                                                version = content.get('version', 'v1.0.0')
                                                direction = content.get('direction', 'input')
                                                new_filename = f"{file_capability}_{direction}_{version}.yaml"
                                                new_path = new_dir / new_filename
                                                
                                                # Копируем файл в новое место
                                                if not new_path.exists():
                                                    shutil.copy2(str(file_path), str(new_path))
                                                    print(f"[INFO] Перемещен контракт {file_capability} в {new_path}")
                                                else:
                                                    # Проверим, может быть это дубликат
                                                    with open(new_path, 'r', encoding='utf-8') as f:
                                                        existing_content = yaml.safe_load(f)
                                                    
                                                    if (existing_content.get('version') == content.get('version') and
                                                        existing_content.get('direction') == content.get('direction')):
                                                        print(f"[INFO] Файл контракта уже существует с теми же параметрами: {new_path}")
                                                    else:
                                                        print(f"[WARN] Файл контракта уже существует с другими параметрами: {new_path}")
                                            else:
                                                print(f"[WARN] Неверный формат capability: {file_capability}")
                                        else:
                                            print(f"[WARN] Capability {file_capability} не найден в registry, пропускаем файл: {file_path}")
                                    else:
                                        print(f"[WARN] Не найдено поле capability в файле контракта: {file_path}")
                                        
                                except Exception as e:
                                    print(f"[ERROR] Ошибка чтения файла контракта {file_path}: {e}")
    
    # Выполняем организацию файлов
    print("[INFO] Начинаем правильную организацию файлов промптов...")
    organize_prompt_files()
    
    print("[INFO] Начинаем правильную организацию файлов контрактов...")
    organize_contract_files()
    
    print("[SUCCESS] Очистка и организация папки data завершена!")


def verify_clean_structure():
    """Проверка чистой структуры папок."""
    data_dir = Path("data")
    
    print("\n[INFO] Проверка чистой структуры папок:")
    
    for parent_dir in ['prompts', 'contracts']:
        parent_path = data_dir / parent_dir
        if parent_path.exists():
            print(f"\n  {parent_dir}/:")
            for type_dir in parent_path.iterdir():
                if type_dir.is_dir():
                    print(f"    {type_dir.name}/:")
                    for cap_dir in type_dir.iterdir():
                        if cap_dir.is_dir():
                            files = list(cap_dir.glob("*.yaml"))
                            print(f"      {cap_dir.name}/: {len(files)} файлов")
                            for i, file in enumerate(files[:5]):  # Показываем первые 5 файлов
                                print(f"        - {file.name}")
                            if len(files) > 5:
                                print(f"        ... и еще {len(files) - 5} файлов")


if __name__ == "__main__":
    print("Начинаем очистку и правильную организацию папки data...")
    clean_and_organize_data_folder()
    verify_clean_structure()
    print("\n[SUCCESS] Очистка и организация папки data завершена!")