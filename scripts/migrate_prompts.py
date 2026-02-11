#!/usr/bin/env python3
"""
Скрипт миграции существующих промптов к новой объектной модели
"""

import os
import sys
from pathlib import Path
import yaml
from datetime import datetime
import hashlib

# Добавляем путь к корню проекта для импорта модулей
sys.path.insert(0, str(Path(__file__).parent))

from core.models.prompt import Prompt, PromptStatus, PromptMetadata
from core.models.prompt_serialization import PromptSerializer
from core.infrastructure.registry.prompt_registry import PromptRegistry


def get_existing_prompts(prompts_dir: Path):
    """Находит все существующие промпты в директории"""
    prompts = []
    
    for file_path in prompts_dir.rglob("*.yaml"):
        if file_path.name == "metadata.yaml" or file_path.name == "registry.yaml":
            continue
            
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
                
            if data and 'capability' in data:
                prompts.append((file_path, data))
        except Exception as e:
            print(f"Ошибка при чтении файла {file_path}: {e}")
    
    return prompts


def determine_status_from_path(file_path: Path) -> PromptStatus:
    """Определяет статус промпта на основе пути файла"""
    path_str = str(file_path)
    
    # Если файл в папке archived/ → ARCHIVED
    if '/archived/' in path_str or '\\archived\\' in path_str:
        return PromptStatus.ARCHIVED
    
    # Если имя содержит _draft → DRAFT
    if '_draft' in path_str.lower():
        return PromptStatus.DRAFT
    
    # По умолчанию - ACTIVE
    return PromptStatus.ACTIVE


def migrate_prompt(file_path: Path, data: dict, backup_dir: Path):
    """Мигрирует один промпт к новой модели"""
    capability = data.get('capability', 'unknown')
    version = data.get('version', '1.0.0')
    
    print(f"Миграция промпта: {capability} (файл: {file_path})")
    
    # Создаем бэкап оригинального файла
    relative_path = file_path.relative_to(Path('.'))
    backup_path = backup_dir / relative_path
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(file_path, 'r', encoding='utf-8') as src:
        original_content = src.read()
    
    with open(backup_path, 'w', encoding='utf-8') as dst:
        dst.write(original_content)
    
    print(f"  - Создан бэкап: {backup_path}")
    
    # Определяем статус на основе пути
    status = determine_status_from_path(file_path)
    
    # Извлекаем переменные из контента, если они не определены
    content = data.get('content', '')
    existing_vars = data.get('variables', [])
    
    if not existing_vars:
        # Извлекаем переменные из контента
        extracted_vars = PromptSerializer.extract_variables_from_content(content)
        print(f"  - Извлечено переменных из контента: {extracted_vars}")
    else:
        extracted_vars = existing_vars
    
    # Определяем skill из пути
    path_parts = file_path.parts
    skill = 'unknown'
    if 'skills' in path_parts:
        skills_idx = path_parts.index('skills')
        if skills_idx + 1 < len(path_parts):
            skill = path_parts[skills_idx + 1]
    
    # Создаем метаданные для нового формата
    metadata = {
        'version': version,
        'skill': skill,
        'capability': capability,
        'strategy': data.get('strategy'),
        'role': data.get('role', 'system'),
        'language': data.get('language', 'ru'),
        'tags': data.get('tags', []),
        'variables': extracted_vars,
        'status': status,
        'quality_metrics': data.get('quality_metrics'),
        'created_at': datetime.utcnow(),
        'updated_at': datetime.utcnow(),
        'author': data.get('author', 'migration_script'),
        'changelog': [f"Миграция из старого формата {datetime.utcnow().isoformat()}", 
                      f"Исходный файл: {file_path}"]
    }
    
    # Создаем новый объект Prompt
    try:
        prompt = Prompt(
            metadata=PromptMetadata(**metadata),
            content=content
        )
        
        # Сохраняем в новый формат
        new_file_path = PromptSerializer.to_file(prompt, file_path.parent.parent)  # Сохраняем в ту же общую директорию
        
        print(f"  - Промпт успешно мигрирован: {new_file_path}")
        return prompt
    except Exception as e:
        print(f"  - Ошибка при создании нового объекта промпта: {e}")
        # Восстанавливаем из бэкапа
        with open(backup_path, 'r', encoding='utf-8') as src:
            restored_content = src.read()
        
        with open(file_path, 'w', encoding='utf-8') as dst:
            dst.write(restored_content)
        
        print(f"  - Файл восстановлен из бэкапа")
        return None


def update_registry_with_migrated_prompts(registry: PromptRegistry, migrated_prompts):
    """Обновляет реестр с мигрированными промптами"""
    print("Обновление реестра с мигрированными промптами...")
    
    # Пересканируем директорию, чтобы обновить реестр
    registry.scan_directory(Path("prompts"))
    
    print("Реестр успешно обновлен")


def main():
    print("=== Скрипт миграции промптов к новой объектной модели ===")
    
    # Проверяем, существует ли директория с промптами
    prompts_dir = Path("prompts")
    if not prompts_dir.exists():
        print(f"Директория {prompts_dir} не найдена!")
        return 1
    
    # Создаем директорию для бэкапов
    backup_dir = Path("backup_prompts_migration") / datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    backup_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"Директория для бэкапов: {backup_dir}")
    
    # Находим все существующие промпты
    print("Поиск существующих промптов...")
    existing_prompts = get_existing_prompts(prompts_dir)
    
    print(f"Найдено {len(existing_prompts)} промптов для миграции")
    
    if not existing_prompts:
        print("Не найдено промптов для миграции. Завершение.")
        return 0
    
    # Подтверждение миграции
    response = input(f"Начать миграцию {len(existing_prompts)} промптов? (y/N): ")
    if response.lower() != 'y':
        print("Миграция отменена.")
        return 0
    
    # Мигрируем промпты
    migrated_count = 0
    failed_count = 0
    migrated_prompts = []
    
    for file_path, data in existing_prompts:
        prompt = migrate_prompt(file_path, data, backup_dir)
        if prompt:
            migrated_count += 1
            migrated_prompts.append(prompt)
        else:
            failed_count += 1
    
    print(f"\nМиграция завершена:")
    print(f"  - Успешно мигрировано: {migrated_count}")
    print(f"  - Ошибок: {failed_count}")
    
    # Обновляем реестр
    print("\nОбновление реестра...")
    registry = PromptRegistry(Path("prompts") / "registry.yaml")
    update_registry_with_migrated_prompts(registry, migrated_prompts)
    
    # Создаем отчет о миграции
    report_path = backup_dir / "migration_report.txt"
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(f"Отчет о миграции промптов\n")
        f.write(f"Дата: {datetime.utcnow().isoformat()}\n")
        f.write(f"Всего обработано: {len(existing_prompts)}\n")
        f.write(f"Успешно мигрировано: {migrated_count}\n")
        f.write(f"Ошибок: {failed_count}\n\n")
        
        f.write("Мигрированные промпты:\n")
        for file_path, data in existing_prompts:
            capability = data.get('capability', 'unknown')
            version = data.get('version', 'unknown')
            f.write(f"  - {capability} (v{version}): {file_path}\n")
    
    print(f"Отчет о миграции сохранен: {report_path}")
    
    if failed_count == 0:
        print("\n✅ Все промпты успешно мигрированы!")
        print(f"Бэкапы сохранены в: {backup_dir}")
        return 0
    else:
        print(f"\n⚠️  Завершено с ошибками. {failed_count} промптов не удалось смигрировать.")
        print(f"Бэкапы сохранены в: {backup_dir}")
        return 1


if __name__ == "__main__":
    sys.exit(main())