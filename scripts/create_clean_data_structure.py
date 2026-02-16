#!/usr/bin/env python3
"""
Скрипт для создания правильной структуры папки data с нуля.
"""
import os
import shutil
from pathlib import Path
import yaml
import re

def create_clean_data_structure():
    """Создание чистой структуры папки data."""
    
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
    
    # Создаем новую чистую структуру папок
    new_structure = {
        'prompts': ['skill', 'tool', 'service', 'behavior'],
        'contracts': ['skill', 'tool', 'service', 'behavior']
    }
    
    # Удаляем все содержимое в prompts и contracts
    for parent_dir in ['prompts', 'contracts']:
        parent_path = data_dir / parent_dir
        if parent_path.exists():
            print(f"[INFO] Очищаем папку {parent_path}")
            import shutil
            shutil.rmtree(parent_path)
        
        # Создаем заново
        parent_path.mkdir(exist_ok=True)
        for subdir in new_structure[parent_dir]:
            (parent_path / subdir).mkdir(exist_ok=True)
    
    print("[INFO] Создана чистая структура папок")
    
    # Теперь создадим правильные подкаталоги для каждого capability
    for capability, comp_type in capability_types.items():
        cap_parts = capability.split('.')
        if len(cap_parts) >= 2:
            cap_main = cap_parts[0]  # например, "planning" из "planning.create_plan"
            
            # Создаем подкаталоги в обеих папках
            for parent_dir in ['prompts', 'contracts']:
                type_path = data_dir / parent_dir / comp_type
                cap_path = type_path / cap_main
                cap_path.mkdir(exist_ok=True)
    
    print("[INFO] Созданы подкаталоги для всех capability")
    
    # Теперь скопируем существующие файлы в правильные места
    def copy_existing_files():
        """Копирование существующих файлов в правильные места."""
        # Сначала найдем все YAML файлы в старых структурах
        all_yaml_files = []
        
        for root, dirs, files in os.walk(data_dir):
            for file in files:
                if file.endswith('.yaml') and not any(x in str(root) for x in ['__pycache__', '.git']):
                    file_path = Path(root) / file
                    all_yaml_files.append(file_path)
        
        print(f"[INFO] Найдено {len(all_yaml_files)} YAML файлов для обработки")
        
        copied_files = 0
        for file_path in all_yaml_files:
            try:
                # Проверим, находится ли файл в одном из новых типов папок
                parts = str(file_path.relative_to(data_dir)).split('/')
                if len(parts) >= 3 and parts[1] in ['skill', 'tool', 'service', 'behavior']:
                    # Это уже в новой структуре, пропускаем
                    continue
                
                # Прочитаем файл, чтобы получить capability
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = yaml.safe_load(f)
                
                if content and 'capability' in content:
                    file_capability = content['capability']
                    
                    if file_capability in capability_types:
                        comp_type = capability_types[file_capability]
                        
                        # Определяем, это промпт или контракт
                        parent_dir = None
                        if 'content' in content:
                            parent_dir = 'prompts'
                        elif 'schema_data' in content:
                            parent_dir = 'contracts'
                        
                        if parent_dir:
                            cap_parts = file_capability.split('.')
                            if len(cap_parts) >= 2:
                                cap_main = cap_parts[0]
                                
                                # Определяем новое имя файла
                                version = content.get('version', 'v1.0.0')
                                if parent_dir == 'prompts':
                                    new_filename = f"{file_capability}_{version}.yaml"
                                else:  # contracts
                                    direction = content.get('direction', 'input')
                                    new_filename = f"{file_capability}_{direction}_{version}.yaml"
                                
                                # Создаем путь к новому файлу
                                new_path = data_dir / parent_dir / comp_type / cap_main / new_filename
                                
                                # Копируем файл, если он не существует
                                if not new_path.exists():
                                    new_path.parent.mkdir(parents=True, exist_ok=True)
                                    shutil.copy2(str(file_path), str(new_path))
                                    print(f"[INFO] Скопирован {parent_dir[:-1]} {file_capability} в {new_path}")
                                    copied_files += 1
                                else:
                                    print(f"[INFO] Файл уже существует: {new_path}")
                    else:
                        print(f"[WARN] Capability {file_capability} не найден в registry, пропускаем файл: {file_path}")
                else:
                    print(f"[WARN] Не найдено поле capability в файле: {file_path}")
                    
            except Exception as e:
                print(f"[ERROR] Ошибка обработки файла {file_path}: {e}")
        
        print(f"[INFO] Скопировано {copied_files} файлов в правильные места")
    
    copy_existing_files()
    
    print("[SUCCESS] Создание чистой структуры папки data завершено!")


def verify_new_clean_structure():
    """Проверка новой чистой структуры папок."""
    data_dir = Path("data")
    
    print("\n[INFO] Проверка новой чистой структуры папок:")
    
    for parent_dir in ['prompts', 'contracts']:
        parent_path = data_dir / parent_dir
        if parent_path.exists():
            print(f"\n  {parent_dir}/:")
            for type_dir in parent_path.iterdir():
                if type_dir.is_dir():
                    print(f"    {type_dir.name}/:")
                    cap_dirs = list(type_dir.iterdir())
                    if cap_dirs:
                        for cap_dir in cap_dirs:
                            if cap_dir.is_dir():
                                files = list(cap_dir.glob("*.yaml"))
                                if files:  # Показываем только папки с файлами
                                    print(f"      {cap_dir.name}/: {len(files)} файлов")
                                    for i, file in enumerate(files[:5]):  # Показываем первые 5 файлов
                                        print(f"        - {file.name}")
                                    if len(files) > 5:
                                        print(f"        ... и еще {len(files) - 5} файлов")
                    else:
                        print(f"      (пусто)")


if __name__ == "__main__":
    print("Начинаем создание чистой структуры папки data...")
    create_clean_data_structure()
    verify_new_clean_structure()
    print("\n[SUCCESS] Создание чистой структуры папки data завершено!")