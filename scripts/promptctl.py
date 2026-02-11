#!/usr/bin/env python3
"""
CLI-утилита для управления промптами
"""

import argparse
import sys
from pathlib import Path
from datetime import datetime, timezone
import json

# Добавляем путь к корню проекта для импорта модулей
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.models.prompt import Prompt, PromptStatus, PromptMetadata
from core.models.prompt_serialization import PromptSerializer
from core.infrastructure.registry.prompt_registry import PromptRegistry


def create_prompt(args):
    """Создает новый промпт-черновик"""
    print(f"Создание нового промпта: {args.capability} версии {args.version}")
    
    # Определяем шаблон содержимого
    content_templates = {
        "planning": """# Планирование задачи

Вы - помощник по планированию задач. Ваша цель - помочь пользователю разбить сложную задачу на подзадачи.

## Контекст:
{{ context }}

## Задача:
{{ task }}

## Требования:
{{ requirements }}

## Результат:
""",
        "analysis": """# Анализ информации

Вы - аналитический помощник. Ваша цель - проанализировать предоставленную информацию и предоставить структурированный обзор.

## Данные для анализа:
{{ data }}

## Критерии анализа:
{{ criteria }}

## Результат анализа:
""",
        "default": """# {{ title }}

{{ description }}

## Входные данные:
{% for var in input_vars %}
- {{ var }}
{% endfor %}

## Результат:
"""
    }
    
    template = content_templates.get(args.template, content_templates["default"])
    
    # Создаем метаданные
    metadata = PromptMetadata(
        version=args.version,
        skill=args.capability.split('.')[0] if '.' in args.capability else 'general',
        capability=args.capability,
        strategy=None,
        role="system",
        language="ru",
        tags=[args.template] if args.template else ["general"],
        variables=["title", "description", "input_vars"] if args.template == "default" else [],
        status=PromptStatus.DRAFT,
        quality_metrics={},
        author=args.author,
        changelog=[f"Создан {datetime.now(timezone.utc).isoformat()}"]
    )
    
    # Создаем промпт
    prompt = Prompt(
        metadata=metadata,
        content=template
    )
    
    # Сохраняем промпт
    base_path = Path("prompts")
    file_path = PromptSerializer.to_file(prompt, base_path)
    
    print(f"Промпт создан: {file_path}")
    return True


def promote_prompt(args):
    """Промоутит промпт в активный статус"""
    print(f"Продвижение промпта: {args.capability} версии {args.version}")
    
    # Загружаем промпт
    registry = PromptRegistry(Path("prompts") / "registry.yaml")
    prompt = registry.get_prompt_by_capability_and_version(args.capability, args.version)
    
    if not prompt:
        print(f"Ошибка: Промпт {args.capability} версии {args.version} не найден")
        return False
    
    # Обновляем статус
    prompt.metadata.status = PromptStatus.ACTIVE
    prompt.metadata.updated_at = datetime.now(timezone.utc)
    prompt.metadata.changelog.append(f"Продвинут в активные {datetime.now(timezone.utc).isoformat()}")
    
    # Обновляем реестр
    success = registry.promote(prompt)
    
    if success:
        print(f"Промпт {args.capability} версии {args.version} успешно продвинут в активные")
    else:
        print(f"Ошибка при продвижении промпта {args.capability} версии {args.version}")
    
    return success


def archive_prompt(args):
    """Архивирует промпт"""
    print(f"Архивация промпта: {args.capability} версии {args.version}")
    
    # Загружаем реестр
    registry = PromptRegistry(Path("prompts") / "registry.yaml")
    
    # Архивируем промпт
    success = registry.archive(args.capability, args.version, args.reason)
    
    if success:
        print(f"Промпт {args.capability} версии {args.version} успешно архивирован")
    else:
        print(f"Ошибка при архивации промпта {args.capability} версии {args.version}")
    
    return success


def show_status(args):
    """Показывает статус всех промптов"""
    print("Статус промптов:")
    
    # Загружаем реестр
    registry = PromptRegistry(Path("prompts") / "registry.yaml")
    
    print("\nАктивные промпты:")
    for capability, entry in registry.active_prompts.items():
        print(f"  - {capability}: {entry.version} ({entry.status.value}) - {entry.file_path}")
    
    print("\nАрхивные промпты:")
    for (capability, version), entry in registry.archived_prompts.items():
        print(f"  - {capability}: {version} ({entry.status.value}) - {entry.file_path}")


def main():
    parser = argparse.ArgumentParser(description="CLI-утилита для управления промптами")
    subparsers = parser.add_subparsers(dest="command", help="Доступные команды")
    
    # Команда create
    create_parser = subparsers.add_parser("create", help="Создать новый промпт-черновик")
    create_parser.add_argument("--capability", required=True, help="Название возможности (например, planning.create_plan)")
    create_parser.add_argument("--version", required=True, help="Версия промпта (например, v1.0.0)")
    create_parser.add_argument("--template", default="default", choices=["planning", "analysis", "default"], help="Шаблон для промпта")
    create_parser.add_argument("--author", required=True, help="Автор промпта")
    
    # Команда promote
    promote_parser = subparsers.add_parser("promote", help="Продвинуть промпт в активный статус")
    promote_parser.add_argument("--capability", required=True, help="Название возможности")
    promote_parser.add_argument("--version", required=True, help="Версия промпта")
    
    # Команда archive
    archive_parser = subparsers.add_parser("archive", help="Архивировать промпт")
    archive_parser.add_argument("--capability", required=True, help="Название возможности")
    archive_parser.add_argument("--version", required=True, help="Версия промпта")
    archive_parser.add_argument("--reason", default="", help="Причина архивации")
    
    # Команда status
    status_parser = subparsers.add_parser("status", help="Показать статус всех промптов")
    
    args = parser.parse_args()
    
    if args.command == "create":
        success = create_prompt(args)
    elif args.command == "promote":
        success = promote_prompt(args)
    elif args.command == "archive":
        success = archive_prompt(args)
    elif args.command == "status":
        show_status(args)
    else:
        parser.print_help()
        sys.exit(1)
    
    if not success and args.command in ["create", "promote", "archive"]:
        sys.exit(1)


if __name__ == "__main__":
    main()