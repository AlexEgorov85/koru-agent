#!/usr/bin/env python3
"""
Скрипт для перемещения существующих файлов в правильные папки в соответствии с новой архитектурой.
"""
import os
import shutil
from pathlib import Path
import yaml
import re

def move_existing_files_to_new_structure():
    """Перемещение существующих файлов в правильные папки."""
    
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
    
    # Словарь соответствия старых имен новым
    # Например: 'create_plan' -> 'planning.create_plan'
    capability_mapping = {}
    
    for cap in capability_types.keys():
        parts = cap.split('.')
        if len(parts) >= 2:
            main_part = parts[0]
            sub_part = parts[1]
            # Добавляем варианты соответствия
            capability_mapping[sub_part] = cap  # например 'create_plan' -> 'planning.create_plan'
            capability_mapping[f"{main_part}_{sub_part}"] = cap  # например 'planning_create_plan' -> 'planning.create_plan'
    
    print(f"[INFO] Создано {len(capability_mapping)} соответствий capability")
    
    # Функция для перемещения файлов промптов
    def move_prompt_files():
        """Перемещение файлов промптов из старой структуры в новую."""
        prompts_dir = data_dir / "prompts"
        
        # Сканируем старую структуру
        for old_type_dir in prompts_dir.iterdir():
            if old_type_dir.is_dir() and old_type_dir.name in ['skills', 'tools', 'services', 'behaviors', 'strategies']:
                continue  # Это уже новая структура
            
            if old_type_dir.is_dir():
                for capability_dir in old_type_dir.iterdir():
                    if capability_dir.is_dir():
                        for file_path in capability_dir.rglob("*.yaml"):
                            if file_path.is_file():
                                filename = file_path.name
                                
                                # Извлекаем имя capability из имени файла
                                match = re.match(r'(.+)_v\d+\.\d+\.\d+\.yaml', filename)
                                if match:
                                    file_capability = match.group(1)
                                    
                                    # Проверяем, есть ли такое соответствие
                                    target_capability = None
                                    if file_capability in capability_mapping:
                                        target_capability = capability_mapping[file_capability]
                                    else:
                                        # Проверим, может быть это полное имя
                                        if file_capability in capability_types:
                                            target_capability = file_capability
                                    
                                    if target_capability and target_capability in capability_types:
                                        target_type = capability_types[target_capability]
                                        
                                        # Разбиваем target_capability на части
                                        cap_parts = target_capability.split('.')
                                        if len(cap_parts) >= 2:
                                            cap_main = cap_parts[0]
                                            
                                            # Создаем новую структуру
                                            new_dir = prompts_dir / target_type / cap_main
                                            new_dir.mkdir(parents=True, exist_ok=True)
                                            
                                            # Формируем новое имя файла
                                            new_filename = f"{target_capability}_{filename.split('_', 1)[1]}"  # берем часть после первого _
                                            new_path = new_dir / new_filename
                                            
                                            # Перемещаем файл
                                            shutil.move(str(file_path), str(new_path))
                                            print(f"[INFO] Перемещен промпт {file_capability} -> {target_capability} в {new_path}")
                                        else:
                                            print(f"[WARN] Неверный формат capability: {target_capability}")
                                    else:
                                        print(f"[WARN] Не найдено соответствие для файла: {file_path} (capability: {file_capability})")
    
    # Функция для перемещения файлов контрактов
    def move_contract_files():
        """Перемещение файлов контрактов из старой структуры в новую."""
        contracts_dir = data_dir / "contracts"
        
        # Сканируем старую структуру
        for old_type_dir in contracts_dir.iterdir():
            if old_type_dir.is_dir() and old_type_dir.name in ['skills', 'tools', 'services', 'behaviors']:
                continue  # Это уже новая структура
            
            if old_type_dir.is_dir():
                for capability_dir in old_type_dir.iterdir():
                    if capability_dir.is_dir():
                        for file_path in capability_dir.rglob("*.yaml"):
                            if file_path.is_file():
                                filename = file_path.name
                                
                                # Извлекаем имя capability из имени файла
                                # Формат может быть: {capability}_{direction}_v{version}.yaml или {name}_v{version}_{direction}.yaml
                                match = re.match(r'(.+)_(input|output)_v\d+\.\d+\.\d+\.yaml', filename)
                                if not match:
                                    match = re.match(r'(.+)_v\d+\.\d+\.\d+_(input|output)\.yaml', filename)
                                
                                if match:
                                    file_capability = match.group(1)
                                    direction = match.group(2)
                                    
                                    # Проверяем, есть ли такое соответствие
                                    target_capability = None
                                    if file_capability in capability_mapping:
                                        target_capability = capability_mapping[file_capability]
                                    else:
                                        # Проверим, может быть это полное имя
                                        if file_capability in capability_types:
                                            target_capability = file_capability
                                    
                                    if target_capability and target_capability in capability_types:
                                        target_type = capability_types[target_capability]
                                        
                                        # Разбиваем target_capability на части
                                        cap_parts = target_capability.split('.')
                                        if len(cap_parts) >= 2:
                                            cap_main = cap_parts[0]
                                            
                                            # Создаем новую структуру
                                            new_dir = contracts_dir / target_type / cap_main
                                            new_dir.mkdir(parents=True, exist_ok=True)
                                            
                                            # Формируем новое имя файла
                                            new_filename = f"{target_capability}_{direction}_v{filename.split('v')[1]}"  # берем версию из оригинального имени
                                            new_path = new_dir / new_filename
                                            
                                            # Перемещаем файл
                                            shutil.move(str(file_path), str(new_path))
                                            print(f"[INFO] Перемещен контракт {file_capability} -> {target_capability} в {new_path}")
                                        else:
                                            print(f"[WARN] Неверный формат capability: {target_capability}")
                                    else:
                                        print(f"[WARN] Не найдено соответствие для файла: {file_path} (capability: {file_capability})")
    
    # Выполняем перемещение файлов
    print("[INFO] Начинаем перемещение файлов промптов из старой структуры...")
    move_prompt_files()
    
    print("[INFO] Начинаем перемещение файлов контрактов из старой структуры...")
    move_contract_files()
    
    print("[SUCCESS] Перемещение файлов из старой структуры завершено!")


def cleanup_empty_dirs():
    """Удаление пустых директорий после перемещения."""
    data_dir = Path("data")
    
    def remove_empty_dirs(path):
        for item in path.iterdir():
            if item.is_dir():
                remove_empty_dirs(item)
        
        # Удаляем директорию, если она пуста
        try:
            path.rmdir()
            print(f"[INFO] Удалена пустая директория: {path}")
        except OSError:
            # Директория не пуста, пропускаем
            pass
    
    # Удаляем пустые директории в prompts
    prompts_dir = data_dir / "prompts"
    if prompts_dir.exists():
        remove_empty_dirs(prompts_dir)
    
    # Удаляем пустые директории в contracts
    contracts_dir = data_dir / "contracts"
    if contracts_dir.exists():
        remove_empty_dirs(contracts_dir)


if __name__ == "__main__":
    print("Начинаем перемещение файлов в новую структуру...")
    move_existing_files_to_new_structure()
    print("\nОчищаем пустые директории...")
    cleanup_empty_dirs()
    print("\n[SUCCESS] Перемещение файлов в новую структуру завершено!")