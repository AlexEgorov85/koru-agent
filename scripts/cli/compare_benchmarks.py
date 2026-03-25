#!/usr/bin/env python3
"""
Сравнение результатов бенчмарков.

Использование:
    # Сравнить два результата
    py -m scripts.cli.compare_benchmarks results1.json results2.json
    
    # Показать историю всех запусков
    py -m scripts.cli.compare_benchmarks --history
"""
import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any


def load_results(file_path: str) -> Dict[str, Any]:
    """Загрузка результатов из файла"""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def print_metrics(name: str, metrics: Dict[str, Any]):
    """Вывод метрик"""
    print(f"\n{'='*60}")
    print(f"   {name}")
    print(f"{'='*60}")
    
    print(f"\n📊 Общие метрики:")
    print(f"   Всего тестов: {metrics.get('total', 'N/A')}")
    print(f"   ✅ Успешных: {metrics.get('successful', 'N/A')}")
    print(f"   ❌ Failed: {metrics.get('failed', 'N/A')}")
    print(f"   📈 Success Rate: {metrics.get('success_rate', 0):.1f}%")
    
    print(f"\n📈 Эффективность:")
    print(f"   Среднее шагов: {metrics.get('avg_steps', 0):.2f}")
    print(f"   Efficiency Score: {metrics.get('efficiency_score', 0):.1f}/100")
    
    print(f"\n{'='*60}")
    print(f"   ОБЩАЯ ОЦЕНКА: {metrics.get('overall_score', 0):.1f}/100")
    print(f"{'='*60}")


def compare_results(results1: Dict[str, Any], results2: Dict[str, Any]):
    """Сравнение двух результатов"""
    m1 = results1.get('metrics', {})
    m2 = results2.get('metrics', {})
    
    print("\n" + "="*70)
    print("СРАВНЕНИЕ РЕЗУЛЬТАТОВ")
    print("="*70)
    
    print_metrics("Результат 1", m1)
    print_metrics("Результат 2", m2)
    
    # Разница
    print(f"\n{'='*70}")
    print("РАЗНИЦА (Результат 2 - Результат 1)")
    print("="*70)
    
    diff_success_rate = m2.get('success_rate', 0) - m1.get('success_rate', 0)
    diff_avg_steps = m2.get('avg_steps', 0) - m1.get('avg_steps', 0)
    diff_efficiency = m2.get('efficiency_score', 0) - m1.get('efficiency_score', 0)
    diff_overall = m2.get('overall_score', 0) - m1.get('overall_score', 0)
    
    # Интерпретация изменений
    def format_change(value: float, higher_is_better: bool = True) -> str:
        if abs(value) < 0.1:
            return "≈ 0 (без изменений)"
        sign = "+" if value > 0 else ""
        emoji = "📈" if (value > 0) == higher_is_better else "📉"
        return f"{emoji} {sign}{value:.1f}"
    
    print(f"\n📊 Изменения:")
    print(f"   Success Rate: {format_change(diff_success_rate)}")
    print(f"   Avg Steps: {format_change(-diff_avg_steps, False)}")  # Меньше шагов = лучше
    print(f"   Efficiency: {format_change(diff_efficiency)}")
    print(f"   Overall Score: {format_change(diff_overall)}")
    
    # Общий вывод
    print(f"\n{'='*70}")
    if diff_overall > 5:
        print("   🎉 УЛУЧШЕНИЕ! Результат 2 лучше.")
    elif diff_overall < -5:
        print("   ⚠️ УХУДШЕНИЕ! Результат 1 лучше.")
    else:
        print("   ➡️ Без значительных изменений.")
    print(f"{'='*70}")


def show_history(benchmarks_dir: str = 'data/benchmarks'):
    """Показать историю запусков"""
    benchmarks_path = Path(benchmarks_dir)
    
    if not benchmarks_path.exists():
        print(f"❌ Директория не найдена: {benchmarks_dir}")
        return
    
    # Поиск всех файлов результатов
    result_files = list(benchmarks_path.glob('*.json'))
    
    if not result_files:
        print("❌ Результаты не найдены")
        return
    
    print("\n" + "="*70)
    print("ИСТОРИЯ ЗАПУСКОВ")
    print("="*70)
    
    results = []
    for file_path in result_files:
        if 'result' in file_path.name.lower():
            try:
                data = load_results(str(file_path))
                metrics = data.get('metrics', {})
                results.append({
                    'file': file_path.name,
                    'run_at': data.get('run_at', 'Unknown'),
                    'mode': data.get('mode', 'Unknown'),
                    'overall_score': metrics.get('overall_score', 0),
                    'success_rate': metrics.get('success_rate', 0),
                    'avg_steps': metrics.get('avg_steps', 0)
                })
            except Exception as e:
                print(f"⚠️ Ошибка чтения {file_path.name}: {e}")
    
    # Сортировка по дате
    results.sort(key=lambda x: x['run_at'], reverse=True)
    
    print(f"\n📊 Найдено {len(results)} запусков:\n")
    print(f"{'Файл':<40} {'Дата':<20} {'Score':<8} {'Success':<10} {'Steps':<8}")
    print("-" * 90)
    
    for r in results:
        date_str = r['run_at'][:16].replace('T', ' ') if r['run_at'] else 'Unknown'
        print(f"{r['file']:<40} {date_str:<20} {r['overall_score']:<8.1f} {r['success_rate']:<10.1f}% {r['avg_steps']:<8.2f}")


def main():
    parser = argparse.ArgumentParser(description='Сравнение результатов бенчмарков')
    parser.add_argument('results_files', nargs='*', help='Файлы результатов для сравнения')
    parser.add_argument('--history', action='store_true', help='Показать историю запусков')
    args = parser.parse_args()
    
    if args.history:
        show_history()
        return
    
    if len(args.results_files) == 0:
        print("❌ Укажите файлы результатов")
        print("\nИспользование:")
        print("  py -m scripts.cli.compare_benchmarks results1.json results2.json")
        print("  py -m scripts.cli.compare_benchmarks --history")
        return
    
    if len(args.results_files) == 1:
        # Показать один результат
        results = load_results(args.results_files[0])
        print_metrics(args.results_files[0], results.get('metrics', {}))
    else:
        # Сравнить два результата
        results1 = load_results(args.results_files[0])
        results2 = load_results(args.results_files[1])
        compare_results(results1, results2)


if __name__ == '__main__':
    main()
