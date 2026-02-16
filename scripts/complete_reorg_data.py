#!/usr/bin/env python3
"""
Скрипт для полной реорганизации папки data в соответствии с новой архитектурой.
"""
import os
import shutil
from pathlib import Path
import yaml
import re

def organize_data_folder_completely():
    """Полная реорганизация папки data в соответствии с новой архитектурой."""
    
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
                
                # В каждом подкаталоге создаем подкаталоги для capability_base
                for capability, comp_type in capability_types.items():
                    if comp_type == subdir:
                        cap_parts = capability.split('.')
                        if len(cap_parts) >= 2:
                            cap_main = cap_parts[0]
                            (parent_path / subdir / cap_main).mkdir(exist_ok=True)
    
    print("[INFO] Создана новая структура папок")
    
    # Функция для перемещения файлов промптов
    def move_prompt_files():
        """Перемещение файлов промптов в новую структуру."""
        prompts_dir = data_dir / "prompts"
        
        # Сканируем все подпапки (включая старые)
        for old_type_dir in prompts_dir.iterdir():
            if old_type_dir.is_dir() and old_type_dir.name in ['skill', 'tool', 'service', 'behavior']:
                continue  # Это уже новая структура
            
            if old_type_dir.is_dir():
                print(f"[INFO] Обработка старой папки промптов: {old_type_dir}")
                
                for capability_dir in old_type_dir.iterdir():
                    if capability_dir.is_dir():
                        for file_path in capability_dir.rglob("*.yaml"):
                            if file_path.is_file():
                                # Попробуем прочитать файл, чтобы получить capability из его содержимого
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
                                                
                                                # Копируем файл в новое место
                                                new_path = new_dir / file_path.name
                                                
                                                # Если файл уже существует, проверим его содержимое
                                                if new_path.exists():
                                                    with open(new_path, 'r', encoding='utf-8') as f:
                                                        existing_content = yaml.safe_load(f)
                                                    
                                                    if existing_content.get('version') == content.get('version'):
                                                        print(f"[INFO] Файл уже существует с той же версией: {new_path}")
                                                        continue
                                                
                                                shutil.copy2(str(file_path), str(new_path))
                                                print(f"[INFO] Скопирован промпт {file_capability} в {new_path}")
                                            else:
                                                print(f"[WARN] Неверный формат capability: {file_capability}")
                                        else:
                                            print(f"[WARN] Capability {file_capability} не найден в registry, пропускаем файл: {file_path}")
                                    else:
                                        print(f"[WARN] Не найдено поле capability в файле: {file_path}")
                                        
                                except Exception as e:
                                    print(f"[ERROR] Ошибка чтения файла {file_path}: {e}")
    
    # Функция для перемещения файлов контрактов
    def move_contract_files():
        """Перемещение файлов контрактов в новую структуру."""
        contracts_dir = data_dir / "contracts"
        
        # Сканируем все подпапки (включая старые)
        for old_type_dir in contracts_dir.iterdir():
            if old_type_dir.is_dir() and old_type_dir.name in ['skill', 'tool', 'service', 'behavior']:
                continue  # Это уже новая структура
            
            if old_type_dir.is_dir():
                print(f"[INFO] Обработка старой папки контрактов: {old_type_dir}")
                
                for capability_dir in old_type_dir.iterdir():
                    if capability_dir.is_dir():
                        for file_path in capability_dir.rglob("*.yaml"):
                            if file_path.is_file():
                                # Попробуем прочитать файл, чтобы получить capability из его содержимого
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
                                                
                                                # Копируем файл в новое место
                                                new_path = new_dir / file_path.name
                                                
                                                # Если файл уже существует, проверим его содержимое
                                                if new_path.exists():
                                                    with open(new_path, 'r', encoding='utf-8') as f:
                                                        existing_content = yaml.safe_load(f)
                                                    
                                                    if (existing_content.get('version') == content.get('version') and 
                                                        existing_content.get('direction') == content.get('direction')):
                                                        print(f"[INFO] Файл контракта уже существует с теми же параметрами: {new_path}")
                                                        continue
                                                
                                                shutil.copy2(str(file_path), str(new_path))
                                                print(f"[INFO] Скопирован контракт {file_capability} в {new_path}")
                                            else:
                                                print(f"[WARN] Неверный формат capability: {file_capability}")
                                        else:
                                            print(f"[WARN] Capability {file_capability} не найден в registry, пропускаем файл: {file_path}")
                                    else:
                                        print(f"[WARN] Не найдено поле capability в файле контракта: {file_path}")
                                        
                                except Exception as e:
                                    print(f"[ERROR] Ошибка чтения файла контракта {file_path}: {e}")
    
    # Выполняем перемещение файлов
    print("[INFO] Начинаем перемещение файлов промптов в новую структуру...")
    move_prompt_files()
    
    print("[INFO] Начинаем перемещение файлов контрактов в новую структуру...")
    move_contract_files()
    
    print("[SUCCESS] Полная реорганизация папки data завершена!")


def verify_new_structure():
    """Проверка новой структуры папок."""
    data_dir = Path("data")
    
    print("\n[INFO] Проверка новой структуры папок:")
    
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
                            for i, file in enumerate(files[:3]):  # Показываем первые 3 файла
                                print(f"        - {file.name}")
                            if len(files) > 3:
                                print(f"        ... и еще {len(files) - 3} файлов")


if __name__ == "__main__":
    print("Начинаем полную реорганизацию папки data...")
    organize_data_folder_completely()
    verify_new_structure()
    print("\n[SUCCESS] Полная реорганизация папки data завершена!")