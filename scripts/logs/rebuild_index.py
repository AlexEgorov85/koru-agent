#!/usr/bin/env python3
"""
Перестроить индекс логов.

USAGE:
    python scripts/logs/rebuild_index.py
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
    get_log_indexer,
    shutdown_logging_system,
)


async def main():
    """Основная функция."""
    parser = argparse.ArgumentParser(description="Перестроение индекса логов")
    parser.add_argument("--verbose", action="store_true", help="Подробный вывод")
    
    args = parser.parse_args()
    
    print("🔄 Перестроение индекса логов...\n")
    
    # Инициализация системы логирования
    await init_logging_system()
    
    try:
        indexer = get_log_indexer()
        
        start_time = datetime.now()
        
        # Перестроение индекса
        count = await indexer.rebuild_index()
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        print(f"✅ Индекс перестроен!")
        print(f"   Сессий проиндексировано: {count}")
        print(f"   Агентов проиндексировано: {indexer.agents_count}")
        print(f"   Время выполнения: {duration:.2f} сек")
        
        if args.verbose:
            print("\n📊 Детали:")
            print(f"   Sessions index: {indexer.sessions_count} записей")
            print(f"   Agents index:   {indexer.agents_count} записей")
            
            # Показываем последние 5 сессий
            latest = await indexer.get_latest_session()
            if latest:
                print(f"\n📁 Последняя сессия:")
                print(f"   ID:        {latest.session_id}")
                print(f"   Agent:     {latest.agent_id or 'N/A'}")
                print(f"   Timestamp: {latest.timestamp}")
                print(f"   Goal:      {latest.goal or 'N/A'}")
        
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
