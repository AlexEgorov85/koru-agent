#!/usr/bin/env python3
"""
Очистка старых логов.

USAGE:
    python scripts/logs/cleanup_old_logs.py --days 30
    python scripts/logs/cleanup_old_logs.py --days 30 --dry-run
    python scripts/logs/cleanup_old_logs.py --archive --before 2025-01-01
"""
import sys
import asyncio
import argparse
from pathlib import Path
from datetime import datetime, timedelta

# Добавляем корень проекта в path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from core.infrastructure.logging import (
    init_logging_system,
    get_log_rotator,
    shutdown_logging_system,
)


async def main():
    """Основная функция."""
    parser = argparse.ArgumentParser(description="Очистка старых логов")
    
    parser.add_argument("--days", type=int, default=30,
                        help="Удалить логи старше N дней (по умолчанию 30)")
    parser.add_argument("--before", type=str,
                        help="Удалить логи до даты (YYYY-MM-DD)")
    parser.add_argument("--archive", action="store_true",
                        help="Очистить архив (старые месяцы)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Не удалять, только показать что будет удалено")
    parser.add_argument("--compress", action="store_true",
                        help="Сжать старые архивы вместо удаления")
    
    args = parser.parse_args()
    
    print("🧹 Очистка старых логов\n")
    
    if args.dry_run:
        print("⚠️  РЕЖИМ DRY-RUN: файлы не будут удалены\n")
    
    # Инициализация системы логирования
    await init_logging_system()
    
    try:
        rotator = get_log_rotator()
        
        # Получение статистики до очистки
        print("📊 Статистика до очистки:")
        stats_before = await rotator.get_log_statistics()
        print(f"   Active:  {stats_before['active']['files']} файлов, "
              f"{stats_before['active']['size_mb']:.2f} MB")
        print(f"   Archive: {stats_before['archive']['files']} файлов, "
              f"{stats_before['archive']['size_mb']:.2f} MB")
        print(f"   Indexed: {stats_before['indexed']['files']} файлов, "
              f"{stats_before['indexed']['size_mb']:.2f} MB")
        print(f"   TOTAL:   {stats_before['total_size_mb']:.2f} MB\n")
        
        if args.compress:
            # Сжатие старых архивов
            print(f"🗜️  Сжатие архивов старше {args.days} дней...")
            compressed = await rotator.compress_old_archives(older_than_days=args.days)
            print(f"   Сжато файлов: {compressed}\n")
        
        else:
            # Очистка старых логов
            if args.before:
                # Очистка до определённой даты
                try:
                    cutoff_date = datetime.strptime(args.before, "%Y-%m-%d")
                    days_old = (datetime.now() - cutoff_date).days
                    print(f"🗑️  Удаление логов до {args.before} ({days_old} дней назад)...\n")
                except ValueError:
                    print(f"❌ Неверный формат даты. Используйте YYYY-MM-DD")
                    return 1
            else:
                # Очистка по количеству дней
                print(f"🗑️  Удаление логов старше {args.days} дней...\n")
            
            # Выполнение очистки
            result = await rotator.cleanup_old_logs(dry_run=args.dry_run)
            
            print("📊 Результаты очистки:")
            print(f"   Удалено файлов:     {result['deleted_files']}")
            print(f"   Удалено размера:    {result['deleted_size_bytes'] / (1024*1024):.2f} MB")
            
            if result['errors']:
                print(f"\n⚠️  Ошибки ({len(result['errors'])}):")
                for error in result['errors'][:5]:
                    print(f"   - {error}")
                if len(result['errors']) > 5:
                    print(f"   ... и ещё {len(result['errors']) - 5} ошибок")
        
        # Получение статистики после очистки
        print("\n📊 Статистика после очистки:")
        stats_after = await rotator.get_log_statistics()
        print(f"   Active:  {stats_after['active']['files']} файлов, "
              f"{stats_after['active']['size_mb']:.2f} MB")
        print(f"   Archive: {stats_after['archive']['files']} файлов, "
              f"{stats_after['archive']['size_mb']:.2f} MB")
        print(f"   Indexed: {stats_after['indexed']['files']} файлов, "
              f"{stats_after['indexed']['size_mb']:.2f} MB")
        print(f"   TOTAL:   {stats_after['total_size_mb']:.2f} MB")
        
        # Экономия
        saved = stats_before['total_size_mb'] - stats_after['total_size_mb']
        if saved > 0:
            print(f"\n💾 Экономия: {saved:.2f} MB")
        
        return 0
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    finally:
        await shutdown_logging_system()


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
