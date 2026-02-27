#!/usr/bin/env python3
"""
Автоматическая очистка старых логов.

Запуск (cron):
    0 2 * * * python scripts/maintenance/cleanup_logs.py --days 30

Очищает:
- Логи старше N дней из data/logs/
- Метрики старше N дней из data/metrics/
- Старые сессии из logs/sessions/
"""
import argparse
import asyncio
import sys
import os
from datetime import datetime, timedelta
from pathlib import Path

# Добавляем корень проекта в path
sys.path.insert(0, str(Path(__file__).parent.parent))


async def cleanup_logs(days: int = 30):
    """
    Очистка логов старше N дней.
    
    ARGS:
    - days: хранить логи за N дней
    """
    from core.infrastructure.log_storage import FileSystemLogStorage
    from core.infrastructure.metrics_storage import FileSystemMetricsStorage
    
    cutoff = datetime.now() - timedelta(days=days)
    
    print(f"[INFO] Очистка логов старше {days} дней...")
    print(f"[INFO] Дата отсечения: {cutoff.isoformat()}")
    
    # Очистка логов
    print("\n[INFO] Очистка логов...")
    log_storage = FileSystemLogStorage(base_dir=Path('data/logs'))
    deleted_logs = await log_storage.clear_old(cutoff)
    print(f"[OK] Удалено логов: {deleted_logs}")
    
    # Очистка метрик
    print("\n[INFO] Очистка метрик...")
    metrics_storage = FileSystemMetricsStorage(base_dir=Path('data/metrics'))
    deleted_metrics = await metrics_storage.clear_old(cutoff)
    print(f"[OK] Удалено метрик: {deleted_metrics}")
    
    # Очистка сессий
    print("\n[INFO] Очистка старых сессий...")
    sessions_dir = Path('logs/sessions')
    if sessions_dir.exists():
        session_files = list(sessions_dir.glob('*.log'))
        deleted_sessions = 0
        for file_path in session_files:
            try:
                # Получаем дату из имени файла или по времени модификации
                file_mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                if file_mtime < cutoff:
                    file_path.unlink()
                    deleted_sessions += 1
            except (OSError, ValueError) as e:
                print(f"[WARN] Не удалось обработать {file_path}: {e}")
        
        print(f"[OK] Удалено сессий: {deleted_sessions}")
    
    # Очистка LLM вызовов
    print("\n[INFO] Очистка старых LLM вызовов...")
    llm_calls_dir = Path('logs/llm_calls')
    if llm_calls_dir.exists():
        llm_files = list(llm_calls_dir.glob('*.log'))
        deleted_llm = 0
        for file_path in llm_files:
            try:
                file_mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                if file_mtime < cutoff:
                    file_path.unlink()
                    deleted_llm += 1
            except (OSError, ValueError) as e:
                print(f"[WARN] Не удалось обработать {file_path}: {e}")
        
        print(f"[OK] Удалено LLM вызовов: {deleted_llm}")
    
    print(f"\n[OK] Очистка завершена (старше {days} дней)")
    print(f"    Всего удалено записей: {deleted_logs + deleted_metrics}")
    print(f"    Всего удалено файлов: {deleted_sessions + deleted_llm}")


def main():
    parser = argparse.ArgumentParser(
        description='Очистка старых логов',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        '--days',
        type=int,
        default=30,
        help='Хранить логи за N дней'
    )
    args = parser.parse_args()
    
    try:
        asyncio.run(cleanup_logs(days=args.days))
    except Exception as e:
        print(f"[ERROR] Ошибка очистки: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
