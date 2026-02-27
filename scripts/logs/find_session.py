#!/usr/bin/env python3
"""
Найти сессию по ID.

USAGE:
    python scripts/logs/find_session.py --session-id abc123
    python scripts/logs/find_session.py --agent-id agent_001 --latest
    python scripts/logs/find_session.py --goal "книги" --limit 5
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
    get_log_search,
    shutdown_logging_system,
)


async def find_by_session_id(search, session_id: str) -> int:
    """Поиск сессии по ID."""
    print(f"🔍 Поиск сессии: {session_id}\n")
    
    session = await search.find_session(session_id)
    
    if not session:
        print(f"❌ Сессия {session_id} не найдена")
        return 1
    
    print(f"✅ Сессия найдена:")
    print(f"   Session ID: {session.session_id}")
    print(f"   Agent ID:   {session.agent_id or 'N/A'}")
    print(f"   Timestamp:  {session.timestamp}")
    print(f"   Goal:       {session.goal or 'N/A'}")
    print(f"   Status:     {session.status or 'unknown'}")
    print(f"   Steps:      {session.steps or 'N/A'}")
    print(f"   Total Time: {session.total_time_ms or 'N/A'} ms")
    print(f"\n📁 Путь к файлу:")
    print(f"   {session.path}")
    
    # Статистика
    logs = await search.get_session_logs(session_id)
    if logs:
        print(f"\n📊 Записей в логе: {len(logs)}")
    
    llm_calls = await search.get_session_llm_calls(session_id)
    if llm_calls:
        print(f"📞 LLM вызовов: {len(llm_calls)}")
    
    return 0


async def find_by_agent_id(search, agent_id: str, latest: bool, limit: int) -> int:
    """Поиск сессий по агенту."""
    print(f"🔍 Поиск сессий агента: {agent_id}\n")
    
    sessions = await search.search_by_agent(agent_id, limit=limit)
    
    if not sessions:
        print(f"❌ Сессии агента {agent_id} не найдены")
        return 1
    
    if latest:
        # Только последняя
        session = sessions[0]
        print(f"✅ Последняя сессия агента:")
        print(f"   Session ID: {session.session_id}")
        print(f"   Timestamp:  {session.timestamp}")
        print(f"   Goal:       {session.goal or 'N/A'}")
        print(f"   Status:     {session.status or 'unknown'}")
        print(f"\n📁 Путь к файлу:")
        print(f"   {session.path}")
    else:
        # Все сессии
        print(f"✅ Найдено сессий: {len(sessions)}\n")
        
        for i, session in enumerate(sessions[:10], 1):  # Показываем первые 10
            print(f"{i}. {session.session_id}")
            print(f"   Timestamp:  {session.timestamp}")
            print(f"   Goal:       {session.goal or 'N/A'}")
            print(f"   Status:     {session.status or 'unknown'}")
            print()
        
        if len(sessions) > 10:
            print(f"... и ещё {len(sessions) - 10} сессий")
    
    return 0


async def search_by_goal(search, goal_pattern: str, limit: int) -> int:
    """Поиск сессий по goal."""
    print(f"🔍 Поиск сессий по goal: '{goal_pattern}'\n")
    
    sessions = await search.search_by_goal(goal_pattern, limit=limit)
    
    if not sessions:
        print(f"❌ Сессии с goal '{goal_pattern}' не найдены")
        return 1
    
    print(f"✅ Найдено сессий: {len(sessions)}\n")
    
    for i, session in enumerate(sessions, 1):
        print(f"{i}. {session.session_id}")
        print(f"   Agent:      {session.agent_id or 'N/A'}")
        print(f"   Timestamp:  {session.timestamp}")
        print(f"   Goal:       {session.goal or 'N/A'}")
        print(f"   Status:     {session.status or 'unknown'}")
        print()
    
    return 0


async def main():
    """Основная функция."""
    parser = argparse.ArgumentParser(description="Поиск сессии по ID")
    
    # Опции поиска
    search_group = parser.add_mutually_exclusive_group()
    search_group.add_argument("--session-id", type=str, help="ID сессии")
    search_group.add_argument("--agent-id", type=str, help="ID агента")
    search_group.add_argument("--goal", type=str, help="Паттерн для поиска в goal")
    
    # Дополнительные опции
    parser.add_argument("--latest", action="store_true", help="Показать только последнюю сессию")
    parser.add_argument("--limit", type=int, default=10, help="Максимальное количество результатов")
    parser.add_argument("--status", type=str, choices=["started", "completed", "failed"],
                        help="Фильтр по статусу")
    
    args = parser.parse_args()
    
    # Инициализация системы логирования
    await init_logging_system()
    
    try:
        search = get_log_search()
        
        if args.session_id:
            return await find_by_session_id(search, args.session_id)
        
        elif args.agent_id:
            return await find_by_agent_id(search, args.agent_id, args.latest, args.limit)
        
        elif args.goal:
            return await search_by_goal(search, args.goal, args.limit)
        
        else:
            parser.print_help()
            return 1
        
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
