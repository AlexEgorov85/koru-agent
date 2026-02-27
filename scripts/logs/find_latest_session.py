#!/usr/bin/env python3
"""
Найти последнюю сессию.

USAGE:
    python scripts/logs/find_latest_session.py
    
OUTPUT:
    Путь к файлу последней сессии + статистика
"""
import sys
import asyncio
from pathlib import Path

# Добавляем корень проекта в path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from core.infrastructure.logging import (
    init_logging_system,
    get_log_search,
    shutdown_logging_system,
)


async def main():
    """Основная функция."""
    print("🔍 Поиск последней сессии...\n")
    
    # Инициализация системы логирования
    await init_logging_system()
    
    try:
        search = get_log_search()
        
        # Получение последней сессии
        session = await search.get_latest_session()
        
        if not session:
            print("❌ Сессии не найдены")
            return 1
        
        print(f"✅ Последняя сессия найдена:")
        print(f"   Session ID: {session.session_id}")
        print(f"   Agent ID:   {session.agent_id}")
        print(f"   Timestamp:  {session.timestamp}")
        print(f"   Goal:       {session.goal or 'N/A'}")
        print(f"   Status:     {session.status or 'unknown'}")
        print(f"   Steps:      {session.steps or 'N/A'}")
        print(f"   Total Time: {session.total_time_ms or 'N/A'} ms")
        print(f"\n📁 Путь к файлу:")
        print(f"   {session.path}")
        
        # Получение логов сессии
        logs = await search.get_session_logs(session.session_id)
        if logs:
            print(f"\n📊 Записей в логе: {len(logs)}")
        
        # Получение LLM вызовов
        llm_calls = await search.get_session_llm_calls(session.session_id)
        if llm_calls:
            print(f"📞 LLM вызовов: {len(llm_calls)}")
        
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
