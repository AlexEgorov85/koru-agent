#!/usr/bin/env python3
"""
Миграция старых логов в новую структуру.

Перемещает логи из старой структуры:
  logs/sessions/{timestamp}_{session_id}.log
  logs/llm_calls/{session_id}_{ts}_{component}_{phase}.log

В новую структуру:
  logs/archive/YYYY/MM/sessions/{timestamp}_{session_id}.log
  logs/archive/YYYY/MM/llm/{date}_session_{id}.jsonl

USAGE:
    python scripts/logs/migrate_old_logs.py
    python scripts/logs/migrate_old_logs.py --dry-run
"""
import sys
import asyncio
import argparse
import json
import re
import shutil
from pathlib import Path
from datetime import datetime

# Добавляем корень проекта в path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


def parse_old_session_filename(filename: str) -> dict:
    """
    Парсинг имени файла старой сессии.
    
    Формат: {timestamp}_{session_id}.log
    Пример: 2026-02-27_15-30-45_015135fc-9196-4aaf-9ebf-5f76133ca0e8.log
    
    RETURNS:
        Dict с timestamp и session_id
    """
    match = re.match(r'(\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2})_(.+)\.log', filename)
    if match:
        return {
            'timestamp': match.group(1),
            'session_id': match.group(2),
        }
    return None


def parse_old_llm_filename(filename: str) -> dict:
    """
    Парсинг имени файла старого LLM лога.
    
    Формат: {session_id}_{timestamp}_{component}_{phase}.log
    Пример: abc123_20260227_081444_272_react_pattern_think.log
    
    RETURNS:
        Dict с session_id, timestamp, component, phase
    """
    match = re.match(r'(.+)_(\d{8}_\d{6}_\d+)_(.+?)_(\w+)\.log', filename)
    if match:
        # Преобразование timestamp в читаемый формат
        ts = match.group(2)
        try:
            dt = datetime.strptime(ts[:15], '%Y%m%d_%H%M%S')
            formatted_ts = dt.strftime('%Y-%m-%d_%H-%M-%S')
        except ValueError:
            formatted_ts = ts
        
        return {
            'session_id': match.group(1),
            'timestamp': formatted_ts,
            'component': match.group(3),
            'phase': match.group(4),
        }
    return None


async def migrate_session_logs(dry_run: bool = False) -> tuple:
    """
    Миграция логов сессий.
    
    RETURNS:
        (migrated_count, total_count)
    """
    old_sessions_dir = Path('logs/sessions')
    
    if not old_sessions_dir.exists():
        print("⚠️  Директория logs/sessions не найдена")
        return (0, 0)
    
    migrated = 0
    total = 0
    
    for log_file in old_sessions_dir.glob('*.log'):
        total += 1
        
        parsed = parse_old_session_filename(log_file.name)
        if not parsed:
            print(f"⚠️  Не удалось распарсить имя файла: {log_file.name}")
            continue
        
        # Определение целевой директории
        try:
            dt = datetime.strptime(parsed['timestamp'], '%Y-%m-%d_%H-%M-%S')
            year = dt.year
            month = dt.month
        except ValueError:
            # Если не удалось распарсить дату, используем текущую
            now = datetime.now()
            year = now.year
            month = now.month
        
        target_dir = Path('logs/archive') / str(year) / f'{month:02d}' / 'sessions'
        target_path = target_dir / log_file.name
        
        if dry_run:
            print(f"  [DRY-RUN] {log_file} → {target_path}")
            migrated += 1
        else:
            try:
                target_dir.mkdir(parents=True, exist_ok=True)
                shutil.move(str(log_file), str(target_path))
                print(f"  ✅ {log_file.name} → {target_path}")
                migrated += 1
            except Exception as e:
                print(f"  ❌ Ошибка перемещения {log_file.name}: {e}")
    
    return (migrated, total)


async def migrate_llm_logs(dry_run: bool = False) -> tuple:
    """
    Миграция LLM логов.
    
    Агрегирует логи по сессиям и датам.
    
    RETURNS:
        (migrated_count, total_count)
    """
    old_llm_dir = Path('logs/llm_calls')
    
    if not old_llm_dir.exists():
        print("⚠️  Директория logs/llm_calls не найдена")
        return (0, 0)
    
    # Группировка файлов по сессиям и датам
    session_files = {}
    
    for log_file in old_llm_dir.glob('*.log'):
        parsed = parse_old_llm_filename(log_file.name)
        if not parsed:
            print(f"⚠️  Не удалось распарсить имя файла: {log_file.name}")
            continue
        
        # Определение даты
        try:
            dt = datetime.strptime(parsed['timestamp'], '%Y-%m-%d_%H-%M-%S')
            date_str = dt.strftime('%Y-%m-%d')
            year = dt.year
            month = dt.month
        except ValueError:
            now = datetime.now()
            date_str = now.strftime('%Y-%m-%d')
            year = now.year
            month = now.month
        
        key = (parsed['session_id'], date_str, year, month)
        
        if key not in session_files:
            session_files[key] = []
        session_files[key].append(log_file)
    
    # Миграция
    migrated = 0
    total = len(list(old_llm_dir.glob('*.log')))
    
    for (session_id, date_str, year, month), files in session_files.items():
        target_dir = Path('logs/archive') / str(year) / f'{month:02d}' / 'llm'
        target_filename = f"{date_str}_session_{session_id}.jsonl"
        target_path = target_dir / target_filename
        
        if dry_run:
            print(f"  [DRY-RUN] {len(files)} файлов → {target_path}")
            migrated += len(files)
        else:
            try:
                target_dir.mkdir(parents=True, exist_ok=True)
                
                # Агрегация файлов в один JSONL
                with open(target_path, 'a', encoding='utf-8') as outfile:
                    for log_file in files:
                        # Чтение содержимого
                        with open(log_file, 'r', encoding='utf-8') as infile:
                            content = infile.read()
                        
                        # Преобразование в JSONL формат
                        event_data = {
                            'type': 'llm_call_migrated',
                            'session_id': session_id,
                            'source_file': log_file.name,
                            'content': content,
                            'migrated_at': datetime.now().isoformat() + 'Z',
                        }
                        
                        outfile.write(json.dumps(event_data, ensure_ascii=False, default=str) + '\n')
                
                print(f"  ✅ {len(files)} файлов → {target_path}")
                migrated += len(files)
                
            except Exception as e:
                print(f"  ❌ Ошибка миграции {session_id}: {e}")
    
    return (migrated, total)


async def cleanup_empty_dirs():
    """Очистка пустых директорий."""
    old_dirs = ['logs/sessions', 'logs/llm_calls']
    
    for dir_path in old_dirs:
        path = Path(dir_path)
        if path.exists():
            try:
                # Проверка на пустоту
                if not any(path.iterdir()):
                    path.rmdir()
                    print(f"  🗑️  Удалена пустая директория: {dir_path}")
            except OSError:
                pass


async def main():
    """Основная функция."""
    parser = argparse.ArgumentParser(description="Миграция старых логов")
    parser.add_argument("--dry-run", action="store_true",
                        help="Не перемещать, только показать что будет перемещено")
    
    args = parser.parse_args()
    
    print("🔄 Миграция старых логов в новую структуру\n")
    
    if args.dry_run:
        print("⚠️  РЕЖИМ DRY-RUN: файлы не будут перемещены\n")
    
    # Создание целевых директорий
    if not args.dry_run:
        Path('logs/archive').mkdir(parents=True, exist_ok=True)
        Path('logs/indexed').mkdir(parents=True, exist_ok=True)
        Path('logs/config').mkdir(parents=True, exist_ok=True)
    
    # Миграция сессий
    print("📁 Миграция логов сессий...")
    session_migrated, session_total = await migrate_session_logs(args.dry_run)
    print(f"   Перемещено: {session_migrated}/{session_total}\n")
    
    # Миграция LLM логов
    print("📞 Миграция LLM логов...")
    llm_migrated, llm_total = await migrate_llm_logs(args.dry_run)
    print(f"   Перемещено: {llm_migrated}/{llm_total}\n")
    
    # Очистка пустых директорий
    if not args.dry_run:
        print("🧹 Очистка пустых директорий...")
        await cleanup_empty_dirs()
    
    # Итог
    print("=" * 50)
    print(f"✅ Миграция завершена!")
    print(f"   Сессии:  {session_migrated}/{session_total}")
    print(f"   LLM:     {llm_migrated}/{llm_total}")
    print(f"   Всего:   {session_migrated + llm_migrated}/{session_total + llm_total}")
    
    if not args.dry_run:
        print("\n💡 Рекомендуется перестроить индекс:")
        print("   python scripts/logs/rebuild_index.py")
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
