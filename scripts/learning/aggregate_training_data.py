#!/usr/bin/env python3
"""
Агрегация логов в формат для обучения.

Запуск:
    python scripts/learning/aggregate_training_data.py --output data/learning/dataset.json

Агрегирует:
- positive_examples: успешные шаги с high quality score (>0.8)
- negative_examples: ошибки и low quality score
- benchmark_results: результаты бенчмарков
"""
import argparse
import asyncio
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any

# Добавляем корень проекта в path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.infrastructure.log_storage import FileSystemLogStorage
from core.benchmarks.benchmark_models import LogType


async def aggregate_logs(
    days: int = 7,
    output_file: str = 'data/learning/dataset.json'
) -> Dict[str, Any]:
    """
    Агрегация логов за последние N дней.
    
    ARGS:
    - days: период агрегации в днях
    - output_file: путь к выходному файлу
    
    RETURNS:
    - Dict[str, Any]: агрегированный датасет
    """
    storage = FileSystemLogStorage(base_dir=Path('data/logs'))
    cutoff = datetime.now() - timedelta(days=days)
    
    print(f"[INFO] Агрегация логов за последние {days} дней...")
    print(f"[INFO] Период: {cutoff.isoformat()} - {datetime.now().isoformat()}")
    
    # 1. Собрать capability_selection логи
    selection_logs = []
    capabilities = await storage.get_capabilities()
    print(f"[INFO] Найдено capabilities: {len(capabilities)}")
    
    for cap in capabilities:
        logs = await storage.get_by_capability(cap, log_type='capability_selection', limit=1000)
        for log in logs:
            if log.timestamp >= cutoff:
                selection_logs.append(log)
    
    print(f"[INFO] Найдено capability_selection логов: {len(selection_logs)}")
    
    # 2. Собрать error логи
    error_logs = []
    for cap in capabilities:
        logs = await storage.get_by_capability(cap, log_type='error', limit=1000)
        for log in logs:
            if log.timestamp >= cutoff:
                error_logs.append(log)
    
    print(f"[INFO] Найдено error логов: {len(error_logs)}")
    
    # 3. Собрать benchmark логи
    benchmark_logs = []
    logs = await storage.get_by_capability('benchmark', log_type='benchmark', limit=1000)
    for log in logs:
        if log.timestamp >= cutoff:
            benchmark_logs.append(log)
    
    print(f"[INFO] Найдено benchmark логов: {len(benchmark_logs)}")
    
    # 4. Создать датасет
    training_dataset = {
        'generated_at': datetime.now().isoformat(),
        'time_range': {
            'from': cutoff.isoformat(),
            'to': datetime.now().isoformat()
        },
        'statistics': {
            'total_selection_logs': len(selection_logs),
            'total_error_logs': len(error_logs),
            'total_benchmark_logs': len(benchmark_logs),
            'capabilities': capabilities
        },
        'positive_examples': [],
        'negative_examples': [],
        'benchmark_results': []
    }
    
    # Positive examples (успешные шаги с quality score > 0.8)
    for log in selection_logs:
        quality_score = log.data.get('step_quality_score') or log.step_quality_score
        if quality_score and quality_score > 0.8:
            training_dataset['positive_examples'].append({
                'context': log.data.get('reasoning', ''),
                'available_capabilities': (
                    log.data.get('execution_context', {}).get('available_capabilities', [])
                    if log.data.get('execution_context')
                    else []
                ),
                'selected_capability': log.data.get('capability', '') or log.capability,
                'pattern': log.data.get('pattern_id', ''),
                'quality_score': quality_score,
                'timestamp': log.timestamp.isoformat(),
                'session_id': log.session_id,
                'agent_id': log.agent_id
            })
    
    print(f"[INFO] Positive examples: {len(training_dataset['positive_examples'])}")
    
    # Negative examples (ошибки)
    for log in error_logs:
        training_dataset['negative_examples'].append({
            'capability': log.data.get('capability', '') or log.capability,
            'error_type': log.data.get('error_type', ''),
            'error_message': log.data.get('error_message', ''),
            'context': log.data.get('execution_context', {}),
            'timestamp': log.timestamp.isoformat(),
            'session_id': log.session_id,
            'agent_id': log.agent_id
        })
    
    print(f"[INFO] Negative examples: {len(training_dataset['negative_examples'])}")
    
    # Benchmark results
    for log in benchmark_logs:
        training_dataset['benchmark_results'].append({
            'scenario_id': log.data.get('scenario_id', ''),
            'capability': log.data.get('capability', '') or log.capability,
            'version': log.data.get('version', ''),
            'success': log.data.get('success', False),
            'overall_score': log.data.get('overall_score', 0),
            'metrics': log.data.get('metrics', {}),
            'timestamp': log.timestamp.isoformat(),
            'session_id': log.session_id
        })
    
    print(f"[INFO] Benchmark results: {len(training_dataset['benchmark_results'])}")
    
    # 5. Сохранить
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(training_dataset, f, indent=2, ensure_ascii=False)
    
    print(f"\n[OK] Датасет сохранён: {output_path}")
    print(f"    Positive examples: {len(training_dataset['positive_examples'])}")
    print(f"    Negative examples: {len(training_dataset['negative_examples'])}")
    print(f"    Benchmark results: {len(training_dataset['benchmark_results'])}")
    
    return training_dataset


def main():
    parser = argparse.ArgumentParser(
        description='Агрегация логов для обучения',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        '--days',
        type=int,
        default=7,
        help='Период агрегации (дни)'
    )
    parser.add_argument(
        '--output',
        type=str,
        default='data/learning/dataset.json',
        help='Выходной файл'
    )
    args = parser.parse_args()
    
    try:
        asyncio.run(aggregate_logs(days=args.days, output_file=args.output))
    except Exception as e:
        print(f"[ERROR] Ошибка агрегации: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
