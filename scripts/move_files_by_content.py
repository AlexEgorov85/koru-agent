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
    
    # Функция для перемещения файлов промптов
    def move_prompt_files():
        """Перемещение файлов промптов из старой структуры в новую."""
        prompts_dir = data_dir / "prompts"
        
        # Сканируем старую структуру (все подпапки кроме новых типов)
        for old_type_dir in prompts_dir.iterdir():
            if old_type_dir.is_dir() and old_type_dir.name in ['skills', 'tools', 'services', 'behaviors', 'strategies']:
                continue  # Это уже новая структура
            
            if old_type_dir.is_dir():
                print(f"[INFO] Обработка папки: {old_type_dir}")
                
                for capability_dir in old_type_dir.iterdir():
                    if capability_dir.is_dir():
                        print(f"[INFO] Обработка подпапки: {capability_dir}")
                        
                        for file_path in capability_dir.rglob("*.yaml"):
                            if file_path.is_file():
                                print(f"[INFO] Обработка файла: {file_path}")
                                
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
                                                cap_sub = cap_parts[1]
                                                
                                                # Создаем новую структуру
                                                new_dir = prompts_dir / target_type / cap_main
                                                new_dir.mkdir(parents=True, exist_ok=True)
                                                
                                                # Формируем новое имя файла в формате {capability}_v{version}.yaml
                                                version = content.get('version', 'v1.0.0')
                                                new_filename = f"{file_capability}_{version}.yaml"
                                                new_path = new_dir / new_filename
                                                
                                                # Перемещаем файл
                                                if not new_path.exists():  # Не перемещаем, если файл уже существует
                                                    shutil.move(str(file_path), str(new_path))
                                                    print(f"[INFO] Перемещен промпт {file_capability} в {new_path}")
                                                else:
                                                    print(f"[INFO] Файл уже существует, пропускаем: {new_path}")
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
        """Перемещение файлов контрактов из старой структуры в новую."""
        contracts_dir = data_dir / "contracts"
        
        # Сканируем старую структуру (все подпапки кроме новых типов)
        for old_type_dir in contracts_dir.iterdir():
            if old_type_dir.is_dir() and old_type_dir.name in ['skills', 'tools', 'services', 'behaviors']:
                continue  # Это уже новая структура
            
            if old_type_dir.is_dir():
                print(f"[INFO] Обработка папки контрактов: {old_type_dir}")
                
                for capability_dir in old_type_dir.iterdir():
                    if capability_dir.is_dir():
                        print(f"[INFO] Обработка подпапки контрактов: {capability_dir}")
                        
                        for file_path in capability_dir.rglob("*.yaml"):
                            if file_path.is_file():
                                print(f"[INFO] Обработка файла контракта: {file_path}")
                                
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
                                                
                                                # Формируем новое имя файла в формате {capability}_{direction}_v{version}.yaml
                                                version = content.get('version', 'v1.0.0')
                                                direction = content.get('direction', 'input')
                                                new_filename = f"{file_capability}_{direction}_{version}.yaml"
                                                new_path = new_dir / new_filename
                                                
                                                # Перемещаем файл
                                                if not new_path.exists():  # Не перемещаем, если файл уже существует
                                                    shutil.move(str(file_path), str(new_path))
                                                    print(f"[INFO] Перемещен контракт {file_capability} в {new_path}")
                                                else:
                                                    print(f"[INFO] Файл контракта уже существует, пропускаем: {new_path}")
                                            else:
                                                print(f"[WARN] Неверный формат capability: {file_capability}")
                                        else:
                                            print(f"[WARN] Capability {file_capability} не найден в registry, пропускаем файл: {file_path}")
                                    else:
                                        print(f"[WARN] Не найдено поле capability в файле контракта: {file_path}")
                                        
                                except Exception as e:
                                    print(f"[ERROR] Ошибка чтения файла контракта {file_path}: {e}")
    
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