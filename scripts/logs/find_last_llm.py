#!/usr/bin/env python3
"""
Найти последний LLM вызов сессии.

USAGE:
    python scripts/logs/find_last_llm.py --session-id abc123
    python scripts/logs/find_last_llm.py --session-id abc123 --phase think
"""
import sys
import asyncio
import argparse
import json
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
    parser = argparse.ArgumentParser(description="Поиск последнего LLM вызова")
    
    parser.add_argument("--session-id", type=str, required=True, help="ID сессии")
    parser.add_argument("--phase", type=str, choices=["think", "act", "observe"],
                        help="Фильтр по фазе")
    parser.add_argument("--type", type=str, choices=["prompt", "response", "all"],
                        default="all", help="Тип вызова")
    parser.add_argument("--full", action="store_true", help="Показать полный текст")
    
    args = parser.parse_args()
    
    print(f"🔍 Поиск LLM вызова для сессии: {args.session_id}\n")
    
    # Инициализация системы логирования
    await init_logging_system()
    
    try:
        search = get_log_search()
        
        if args.type == "all":
            # Все LLM вызовы
            calls = await search.get_session_llm_calls(args.session_id)
            
            if not calls:
                print(f"❌ LLM вызовы не найдены")
                return 1
            
            print(f"✅ Найдено LLM вызовов: {len(calls)}\n")
            
            # Группировка по типу
            prompts = [c for c in calls if c.get('type') == 'llm_prompt']
            responses = [c for c in calls if c.get('type') == 'llm_response']
            
            print(f"   Промптов:   {len(prompts)}")
            print(f"   Ответов:    {len(responses)}")
            print()
            
            # Показываем последние 5 пар
            for i in range(max(len(prompts), len(responses)) - 5, max(len(prompts), len(responses))):
                if i < len(prompts):
                    prompt = prompts[i]
                    print(f"📝 Промпт {i+1}:")
                    print(f"   Component: {prompt.get('component', 'N/A')}")
                    print(f"   Phase:     {prompt.get('phase', 'N/A')}")
                    print(f"   Timestamp: {prompt.get('timestamp', 'N/A')}")
                    if args.full:
                        system = prompt.get('system_prompt', '')[:500]
                        print(f"   System:    {system}...")
                    print()
                
                if i < len(responses):
                    response = responses[i]
                    print(f"💬 Ответ {i+1}:")
                    print(f"   Component: {response.get('component', 'N/A')}")
                    print(f"   Phase:     {response.get('phase', 'N/A')}")
                    print(f"   Timestamp: {response.get('timestamp', 'N/A')}")
                    if args.full:
                        resp = response.get('response', '')[:500]
                        print(f"   Response:  {resp}...")
                    print()
        
        else:
            # Последний вызов
            call = await search.get_last_llm_call(args.session_id, phase=args.phase)
            
            if not call:
                print(f"❌ LLM вызов не найден")
                return 1
            
            call_type = call.get('type', 'unknown')
            emoji = "📝" if call_type == 'llm_prompt' else "💬"
            
            print(f"{emoji} LLM {'промпт' if call_type == 'llm_prompt' else 'ответ'}:")
            print(f"   Session ID: {call.get('session_id', 'N/A')}")
            print(f"   Component:  {call.get('component', 'N/A')}")
            print(f"   Phase:      {call.get('phase', 'N/A')}")
            print(f"   Timestamp:  {call.get('timestamp', 'N/A')}")
            
            if call_type == 'llm_prompt':
                print(f"   Goal:       {call.get('goal', 'N/A')}")
                print(f"   Length:     {call.get('prompt_length', 'N/A')} chars")
                
                if args.full:
                    system = call.get('system_prompt', '')
                    user = call.get('user_prompt', '')
                    print(f"\n   System Prompt ({len(system)} chars):")
                    print(f"   {'-'*60}")
                    print(f"   {system[:1000]}{'...' if len(system) > 1000 else ''}")
                    print(f"   {'-'*60}")
                    print(f"\n   User Prompt ({len(user)} chars):")
                    print(f"   {'-'*60}")
                    print(f"   {user[:1000]}{'...' if len(user) > 1000 else ''}")
                    print(f"   {'-'*60}")
            
            elif call_type == 'llm_response':
                print(f"   Tokens:     {call.get('tokens', 'N/A')}")
                print(f"   Latency:    {call.get('latency_ms', 'N/A')} ms")
                
                if args.full:
                    response = call.get('response', '')
                    print(f"\n   Response:")
                    print(f"   {'-'*60}")
                    try:
                        # Попытка красивого вывода JSON
                        resp_data = json.loads(response)
                        print(f"   {json.dumps(resp_data, ensure_ascii=False, indent=2)[:2000]}")
                    except json.JSONDecodeError:
                        print(f"   {response[:2000]}")
                    print(f"   {'-'*60}")
        
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
