#!/usr/bin/env python3
"""
Проверка размера логов.

USAGE:
    python scripts/logs/check_log_size.py
"""
import sys
import asyncio
import argparse
from pathlib import Path
from datetime import datetime

# Добавляем корень проекта в path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from core.infrastructure.logging import (
    init_logging_system,
    get_log_rotator,
    shutdown_logging_system,
)


def format_size(size_bytes: int) -> str:
    """Форматирование размера."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.2f} TB"


async def main():
    """Основная функция."""
    parser = argparse.ArgumentParser(description="Проверка размера логов")
    parser.add_argument("--json", action="store_true", help="Вывод в JSON формате")
    
    args = parser.parse_args()
    
    # Инициализация системы логирования
    await init_logging_system()
    
    try:
        rotator = get_log_rotator()
        stats = await rotator.get_log_statistics()
        
        if args.json:
            import json
            print(json.dumps(stats, indent=2, default=str))
        else:
            print("📊 Статистика использования дискового пространства\n")
            
            print("📁 Active логи (текущий день):")
            print(f"   Файлов: {stats['active']['files']}")
            print(f"   Размер: {format_size(stats['active']['size_bytes'])}")
            print()
            
            print("📁 Archive логи:")
            print(f"   Файлов: {stats['archive']['files']}")
            print(f"   Размер: {format_size(stats['archive']['size_bytes'])}")
            
            # Детализация по месяцам
            if stats['archive']['by_month']:
                print("\n   По месяцам:")
                for month, month_stats in sorted(
                    stats['archive']['by_month'].items(),
                    key=lambda x: x[0],
                    reverse=True
                )[:10]:  # Последние 10 месяцев
                    print(f"   {month}: {month_stats['files']} файлов, "
                          f"{format_size(month_stats['size_bytes'])}")
                
                if len(stats['archive']['by_month']) > 10:
                    print(f"   ... и ещё {len(stats['archive']['by_month']) - 10} месяцев")
            print()
            
            print("📁 Indexed (индексы):")
            print(f"   Файлов: {stats['indexed']['files']}")
            print(f"   Размер: {format_size(stats['indexed']['size_bytes'])}")
            print()
            
            print("=" * 50)
            print(f"💾 ОБЩИЙ РАЗМЕР: {format_size(stats['total_size_bytes'])}")
            
            # Проверка лимитов
            config = rotator.config
            if stats['active']['size_mb'] > config.retention.max_size_mb:
                print(f"\n⚠️  ПРЕДУПРЕЖДЕНИЕ: Active логи превышают лимит "
                      f"({stats['active']['size_mb']:.1f} MB > {config.retention.max_size_mb} MB)")
        
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
