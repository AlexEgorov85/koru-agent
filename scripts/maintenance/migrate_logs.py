#!/usr/bin/env python
"""
Скрипт миграции логов из старой структуры в новую.

МИГРАЦИЯ:
- data/logs/by_agent/* → logs/sessions/
- data/logs/by_capability/* → logs/sessions/
- logs/archive/* → logs/sessions/ (если нужно)

ИСПОЛЬЗОВАНИЕ:
```bash
python scripts/maintenance/migrate_logs.py --dry-run
python scripts/maintenance/migrate_logs.py --migrate
```
"""
import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any


def find_old_logs(base_dir: Path = None) -> List[Path]:
    """
    Поиск старых логов для миграции.
    
    ARGS:
    - base_dir: Базовая директория (по умолчанию project root)
    
    RETURNS:
    - Список путей к старым логам
    """
    if base_dir is None:
        base_dir = Path(__file__).parent.parent.parent
    
    old_dirs = [
        base_dir / "data" / "logs" / "by_agent",
        base_dir / "data" / "logs" / "by_capability",
        base_dir / "data" / "logs" / "all",
    ]
    
    old_logs = []
    for old_dir in old_dirs:
        if old_dir.exists():
            old_logs.extend(old_dir.rglob("*.json"))
            old_logs.extend(old_dir.rglob("*.jsonl"))
    
    return old_logs


def parse_session_from_path(path: Path) -> Dict[str, str]:
    """
    Извлечение информации о сессии из пути.
    
    ARGS:
    - path: Путь к файлу лога
    
    RETURNS:
    - Dict с session_id, agent_id, date
    """
    parts = path.parts
    
    # data/logs/by_agent/{agent_id}/{session_id}/logs.json
    if "by_agent" in parts:
        idx = parts.index("by_agent")
        if idx + 2 < len(parts):
            return {
                "agent_id": parts[idx + 1],
                "session_id": parts[idx + 2],
                "type": "by_agent"
            }
    
    # data/logs/by_capability/{capability}/{session_id}/logs.json
    if "by_capability" in parts:
        idx = parts.index("by_capability")
        if idx + 2 < len(parts):
            return {
                "capability": parts[idx + 1],
                "session_id": parts[idx + 2],
                "type": "by_capability"
            }
    
    return {"type": "unknown"}


def migrate_log_file(
    src: Path,
    dest_dir: Path,
    session_info: Dict[str, str],
    dry_run: bool = True
) -> bool:
    """
    Миграция одного файла лога.
    
    ARGS:
    - src: Исходный файл
    - dest_dir: Целевая директория
    - session_info: Информация о сессии
    - dry_run: Сухой запуск (без записи)
    
    RETURNS:
    - True если успешно
    """
    # Создаём имя папки с датой
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    session_id = session_info.get("session_id", "unknown")
    agent_id = session_info.get("agent_id", "unknown")
    
    # Новая структура: logs/sessions/{date}_{time}_{session_id}/
    dest_session_dir = dest_dir / f"{timestamp}_{session_id}"
    
    if dry_run:
        print(f"  [DRY-RUN] {src} → {dest_session_dir}/migrated_{src.name}")
        return True
    
    try:
        dest_session_dir.mkdir(parents=True, exist_ok=True)
        
        # Копируем файл с новым именем
        dest_file = dest_session_dir / f"migrated_{src.name}"
        shutil.copy2(src, dest_file)
        
        # Добавляем метаданные миграции
        metadata = {
            "migrated_at": datetime.now().isoformat(),
            "original_path": str(src),
            "session_info": session_info,
        }
        
        metadata_file = dest_session_dir / "migration_metadata.json"
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        
        return True
        
    except Exception as e:
        print(f"  ❌ Ошибка миграции {src}: {e}")
        return False


def migrate_logs(
    dry_run: bool = True,
    base_dir: Path = None
) -> Dict[str, Any]:
    """
    Основная функция миграции.
    
    ARGS:
    - dry_run: Сухой запуск
    - base_dir: Базовая директория
    
    RETURNS:
    - Статистика миграции
    """
    if base_dir is None:
        base_dir = Path(__file__).parent.parent.parent
    
    dest_dir = base_dir / "logs" / "sessions" / "migrated"
    
    print("=" * 60)
    print("🔄 Миграция логов в новую структуру")
    print("=" * 60)
    
    if dry_run:
        print("⚠️  РЕЖИМ DRY-RUN (без записи)")
    print()
    
    # Поиск старых логов
    old_logs = find_old_logs(base_dir)
    print(f"📁 Найдено старых логов: {len(old_logs)}")
    
    if not old_logs:
        print("✅ Старые логи не найдены. Миграция не требуется.")
        return {"success": True, "migrated": 0, "failed": 0}
    
    # Миграция
    stats = {
        "success": True,
        "migrated": 0,
        "failed": 0,
        "by_type": {}
    }
    
    for log_file in old_logs:
        session_info = parse_session_from_path(log_file)
        log_type = session_info.get("type", "unknown")
        
        if log_type not in stats["by_type"]:
            stats["by_type"][log_type] = 0
        
        print(f"📄 {log_file}")
        print(f"   Тип: {log_type}, Сессия: {session_info.get('session_id', 'N/A')}")
        
        if migrate_log_file(log_file, dest_dir, session_info, dry_run):
            stats["migrated"] += 1
            stats["by_type"][log_type] += 1
        else:
            stats["failed"] += 1
    
    # Вывод статистики
    print()
    print("=" * 60)
    print("📊 Статистика миграции:")
    print(f"   Успешно: {stats['migrated']}")
    print(f"   Ошибки: {stats['failed']}")
    print(f"   По типам: {stats['by_type']}")
    print("=" * 60)
    
    if not dry_run and stats["migrated"] > 0:
        print()
        print("✅ Миграция завершена!")
        print(f"   Новые логи: {dest_dir}")
        print()
        print("⚠️  ВАЖНО: Проверьте новые логи перед удалением старых!")
    
    return stats


def cleanup_old_logs(dry_run: bool = True, base_dir: Path = None) -> int:
    """
    Очистка старых директорий после миграции.
    
    ARGS:
    - dry_run: Сухой запуск
    - base_dir: Базовая директория
    
    RETURNS:
    - Количество удалённых файлов
    """
    if base_dir is None:
        base_dir = Path(__file__).parent.parent.parent
    
    old_dirs = [
        base_dir / "data" / "logs",
    ]
    
    deleted = 0
    
    print()
    print("=" * 60)
    print("🧹 Очистка старых директорий")
    print("=" * 60)
    
    for old_dir in old_dirs:
        if not old_dir.exists():
            continue
        
        if dry_run:
            print(f"  [DRY-RUN] Удалить: {old_dir}")
        else:
            try:
                shutil.rmtree(old_dir)
                print(f"  ✅ Удалено: {old_dir}")
                deleted += 1
            except Exception as e:
                print(f"  ❌ Ошибка удаления {old_dir}: {e}")
    
    return deleted


def main():
    """Точка входа."""
    parser = argparse.ArgumentParser(
        description="Миграция логов в новую структуру"
    )
    parser.add_argument(
        "--migrate",
        action="store_true",
        help="Выполнить миграцию (без этого флага — только сухой запуск)"
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Очистить старые директории после миграции"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Сухой запуск (по умолчанию)"
    )
    
    args = parser.parse_args()
    
    dry_run = not args.migrate
    
    # Миграция
    stats = migrate_logs(dry_run=dry_run)
    
    # Очистка
    if args.cleanup and not dry_run and stats["migrated"] > 0:
        cleanup_old_logs(dry_run=False)
    elif args.cleanup and dry_run:
        cleanup_old_logs(dry_run=True)


if __name__ == "__main__":
    main()
