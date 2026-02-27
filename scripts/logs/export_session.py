#!/usr/bin/env python3
"""
Экспорт сессии в JSON.

USAGE:
    python scripts/logs/export_session.py --session-id abc123
    python scripts/logs/export_session.py --session-id abc123 --output session.json
    python scripts/logs/export_session.py --session-id abc123 --format text
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


async def main():
    """Основная функция."""
    parser = argparse.ArgumentParser(description="Экспорт сессии в файл")
    
    parser.add_argument("--session-id", type=str, required=True, help="ID сессии")
    parser.add_argument("--output", type=str, help="Путь для экспорта")
    parser.add_argument("--format", type=str, choices=["json", "text"],
                        default="json", help="Формат экспорта")
    parser.add_argument("--include-llm", action="store_true",
                        help="Включить LLM вызовы")
    
    args = parser.parse_args()
    
    print(f"📤 Экспорт сессии: {args.session_id}\n")
    
    # Инициализация системы логирования
    await init_logging_system()
    
    try:
        search = get_log_search()
        
        # Проверка существования сессии
        session = await search.find_session(args.session_id)
        
        if not session:
            print(f"❌ Сессия {args.session_id} не найдена")
            return 1
        
        print(f"✅ Сессия найдена:")
        print(f"   Agent:     {session.agent_id or 'N/A'}")
        print(f"   Timestamp: {session.timestamp}")
        print(f"   Goal:      {session.goal or 'N/A'}")
        print(f"   Status:    {session.status or 'unknown'}")
        print()
        
        # Получение логов
        logs = await search.get_session_logs(args.session_id)
        
        if not logs:
            print(f"❌ Логи сессии не найдены")
            return 1
        
        print(f"📊 Записей в логе: {len(logs)}")
        
        # Получение LLM вызовов
        llm_calls = []
        if args.include_llm:
            llm_calls = await search.get_session_llm_calls(args.session_id)
            print(f"📞 LLM вызовов: {len(llm_calls)}")
        
        # Формирование экспорта
        export_data = {
            'session_id': args.session_id,
            'agent_id': session.agent_id,
            'goal': session.goal,
            'status': session.status,
            'steps': session.steps,
            'total_time_ms': session.total_time_ms,
            'timestamp': session.timestamp,
            'exported_at': datetime.now().isoformat(),
            'logs': logs,
        }
        
        if args.include_llm:
            export_data['llm_calls'] = llm_calls
        
        # Определение пути экспорта
        if args.output:
            output_path = Path(args.output)
        else:
            output_path = Path(f"session_{args.session_id}_export.{args.format}")
        
        # Экспорт
        print(f"\n💾 Экспорт в {output_path}...")
        
        if args.format == "json":
            import json
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2, default=str)
        else:
            # Текстовый формат
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(f"Session: {args.session_id}\n")
                f.write(f"Agent:   {session.agent_id or 'N/A'}\n")
                f.write(f"Goal:    {session.goal or 'N/A'}\n")
                f.write(f"Status:  {session.status or 'unknown'}\n")
                f.write(f"Steps:   {session.steps or 'N/A'}\n")
                f.write(f"Time:    {session.total_time_ms or 'N/A'} ms\n")
                f.write("=" * 80 + "\n\n")
                
                for log_entry in logs:
                    if 'raw' in log_entry:
                        f.write(log_entry['raw'] + '\n')
                    else:
                        import json
                        f.write(json.dumps(log_entry, ensure_ascii=False, default=str) + '\n')
        
        print(f"✅ Экспорт завершён!")
        print(f"   Файл: {output_path.absolute()}")
        print(f"   Размер: {output_path.stat().st_size} байт")
        
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
