#!/usr/bin/env python3
"""
CLI скрипт для запуска бенчмарков.

ИСПОЛЬЗОВАНИЕ:
    python scripts/cli/run_benchmark.py --capability <capability> --version <version>
    python scripts/cli/run_benchmark.py --capability <capability> --compare v1.0.0 v2.0.0

АРГУМЕНТЫ:
    --capability, -c    Название способности для бенчмарка
    --version, -v       Версия для тестирования
    --compare           Сравнить две версии
    --output, -o        Файл для вывода результатов (JSON)
    --verbose           Подробный вывод
"""
import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional


def parse_args() -> argparse.Namespace:
    """Парсинг аргументов командной строки"""
    parser = argparse.ArgumentParser(
        description='Запуск бенчмарков для оценки качества агента',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:
  %(prog)s -c planning.create_plan -v v1.0.0
  %(prog)s -c planning.create_plan --compare v1.0.0 v2.0.0
  %(prog)s -c planning.create_plan -v v1.0.0 -o results.json
        """
    )

    parser.add_argument(
        '-c', '--capability',
        type=str,
        required=True,
        help='Название способности для бенчмарка (например, planning.create_plan)'
    )

    parser.add_argument(
        '-v', '--version',
        type=str,
        help='Версия для тестирования (например, v1.0.0)'
    )

    parser.add_argument(
        '--compare',
        nargs=2,
        metavar=('VERSION_A', 'VERSION_B'),
        help='Сравнить две версии (например, v1.0.0 v2.0.0)'
    )

    parser.add_argument(
        '-o', '--output',
        type=str,
        help='Файл для вывода результатов в формате JSON'
    )

    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Подробный вывод результатов'
    )

    parser.add_argument(
        '--config',
        type=str,
        default='registry.yaml',
        help='Путь к файлу конфигурации (по умолчанию: registry.yaml)'
    )

    return parser.parse_args()


async def run_single_benchmark(
    capability: str,
    version: str,
    verbose: bool = False
) -> dict:
    """
    Запуск одиночного бенчмарка.

    ARGS:
        capability: название способности
        version: версия для тестирования
        verbose: подробный вывод

    RETURNS:
        dict: результаты бенчмарка
    """
    print(f"\n{'='*60}")
    print(f"Бенчмарк: {capability}@{version}")
    print(f"{'='*60}\n")

    # Импорты внутри async функции для избежания circular imports
    from core.config.app_config import AppConfig
    from core.infrastructure_context.infrastructure_context import InfrastructureContext
    from core.application_context.application_context import ApplicationContext
    from core.services.benchmark_service import BenchmarkService
    from core.services.accuracy_evaluator import AccuracyEvaluatorService
    from core.infrastructure.metrics_storage import FileSystemMetricsStorage
    from core.infrastructure.event_bus import get_event_bus

    try:
        # Загрузка конфигурации
        config = AppConfig.load_from_file(Path('registry.yaml'))

        # Инициализация инфраструктуры
        infra_context = InfrastructureContext(config)
        await infra_context.initialize()

        # Создание application context
        app_context = ApplicationContext(
            infrastructure_context=infra_context,
            config=config,
            profile='sandbox'
        )
        await app_context.initialize()

        # Создание сервисов
        metrics_storage = FileSystemMetricsStorage()
        metrics_collector = infra_context.metrics_collector
        accuracy_evaluator = AccuracyEvaluatorService()
        event_bus = get_event_bus()

        benchmark_service = BenchmarkService(
            metrics_collector=metrics_collector,
            accuracy_evaluator=accuracy_evaluator,
            event_bus=event_bus
        )

        # Создание тестовых сценариев (заглушка)
        from core.services.benchmarks.benchmark_models import BenchmarkScenario, ExpectedOutput, EvaluationCriterion, EvaluationType

        scenarios = [
            BenchmarkScenario(
                id=f'{capability}_test_1',
                name=f'Test scenario 1 for {capability}',
                description='Basic functionality test',
                goal='Test goal for benchmark',
                expected_output=ExpectedOutput(
                    content='Expected output',
                    criteria=[
                        EvaluationCriterion(
                            name='accuracy',
                            evaluation_type=EvaluationType.EXACT_MATCH,
                            threshold=0.8
                        )
                    ]
                ),
                criteria=[
                    EvaluationCriterion(
                        name='accuracy',
                        evaluation_type=EvaluationType.EXACT_MATCH,
                        threshold=0.8
                    )
                ]
            )
        ]

        # Запуск бенчмарка
        print(f"Запуск бенчмарка для {len(scenarios)} сценариев...\n")

        results = []
        for scenario in scenarios:
            result = await benchmark_service.run_benchmark(
                scenario=scenario,
                version=version
            )
            results.append({
                'scenario_id': result.scenario_id,
                'success': result.success,
                'overall_score': result.overall_score,
                'execution_time_ms': result.execution_time_ms,
                'tokens_used': result.tokens_used,
                'error': result.error
            })

            if verbose:
                print(f"  Сценарий: {result.scenario_id}")
                print(f"    Успех: {result.success}")
                print(f"    Оценка: {result.overall_score:.2f}")
                print(f"    Время: {result.execution_time_ms:.1f} мс")
                print(f"    Токены: {result.tokens_used}")
                if result.error:
                    print(f"    Ошибка: {result.error}")
                print()

        # Агрегация результатов
        total_runs = len(results)
        successful_runs = sum(1 for r in results if r['success'])
        avg_score = sum(r['overall_score'] for r in results) / total_runs if total_runs > 0 else 0
        avg_time = sum(r['execution_time_ms'] for r in results) / total_runs if total_runs > 0 else 0

        benchmark_result = {
            'capability': capability,
            'version': version,
            'timestamp': datetime.now().isoformat(),
            'total_scenarios': total_runs,
            'successful_scenarios': successful_runs,
            'success_rate': successful_runs / total_runs if total_runs > 0 else 0,
            'average_score': avg_score,
            'average_execution_time_ms': avg_time,
            'scenarios': results
        }

        # Вывод результатов
        print(f"\n{'='*60}")
        print(f"Результаты бенчмарка: {capability}@{version}")
        print(f"{'='*60}")
        print(f"Всего сценариев: {total_runs}")
        print(f"Успешных: {successful_runs} ({benchmark_result['success_rate']*100:.1f}%)")
        print(f"Средняя оценка: {avg_score:.2f}")
        print(f"Среднее время: {avg_time:.1f} мс")
        print(f"{'='*60}\n")

        return benchmark_result

    except Exception as e:
        print(f"\n❌ Ошибка выполнения бенчмарка: {e}")
        if verbose:
            import traceback
            traceback.print_exc()

        return {
            'capability': capability,
            'version': version,
            'timestamp': datetime.now().isoformat(),
            'error': str(e)
        }


async def run_comparison(
    capability: str,
    version_a: str,
    version_b: str,
    verbose: bool = False
) -> dict:
    """
    Сравнение двух версий.

    ARGS:
        capability: название способности
        version_a: первая версия
        version_b: вторая версия
        verbose: подробный вывод

    RETURNS:
        dict: результаты сравнения
    """
    print(f"\n{'='*60}")
    print(f"Сравнение версий: {capability}")
    print(f"  Версия A: {version_a}")
    print(f"  Версия B: {version_b}")
    print(f"{'='*60}\n")

    # Запуск бенчмарков для обеих версий
    result_a = await run_single_benchmark(capability, version_a, verbose=False)
    result_b = await run_single_benchmark(capability, version_b, verbose=False)

    # Сравнение метрик
    comparison = {
        'capability': capability,
        'version_a': version_a,
        'version_b': version_b,
        'timestamp': datetime.now().isoformat(),
        'metrics_a': {
            'success_rate': result_a.get('success_rate', 0),
            'average_score': result_a.get('average_score', 0),
            'average_execution_time_ms': result_a.get('average_execution_time_ms', 0)
        },
        'metrics_b': {
            'success_rate': result_b.get('success_rate', 0),
            'average_score': result_b.get('average_score', 0),
            'average_execution_time_ms': result_b.get('average_execution_time_ms', 0)
        }
    }

    # Расчёт улучшений
    if result_a.get('average_score', 0) > 0:
        score_improvement = (
            (result_b.get('average_score', 0) - result_a.get('average_score', 0))
            / result_a.get('average_score', 0)
        ) * 100
    else:
        score_improvement = 0

    comparison['improvements'] = {
        'score_change_percent': score_improvement,
        'winner': version_b if score_improvement > 0 else version_a if score_improvement < 0 else 'tie'
    }

    # Вывод результатов сравнения
    print(f"\n{'='*60}")
    print(f"Результаты сравнения")
    print(f"{'='*60}")
    print(f"\n{version_a}:")
    print(f"  Успешность: {comparison['metrics_a']['success_rate']*100:.1f}%")
    print(f"  Оценка: {comparison['metrics_a']['average_score']:.2f}")
    print(f"  Время: {comparison['metrics_a']['average_execution_time_ms']:.1f} мс")

    print(f"\n{version_b}:")
    print(f"  Успешность: {comparison['metrics_b']['success_rate']*100:.1f}%")
    print(f"  Оценка: {comparison['metrics_b']['average_score']:.2f}")
    print(f"  Время: {comparison['metrics_b']['average_execution_time_ms']:.1f} мс")

    print(f"\n📊 Изменение оценки: {score_improvement:+.1f}%")
    print(f"🏆 Победитель: {comparison['improvements']['winner']}")
    print(f"{'='*60}\n")

    if verbose:
        print("Детальные результаты:")
        print(f"  Версия A: {json.dumps(result_a, indent=2)}")
        print(f"  Версия B: {json.dumps(result_b, indent=2)}")

    return comparison


async def main():
    """Основная функция"""
    args = parse_args()

    print("\n" + "="*60)
    print("Benchmark CLI - Оценка качества агента")
    print("="*60)
    print(f"Конфигурация: {args.config}")
    print(f"Capability: {args.capability}")

    try:
        if args.compare:
            # Режим сравнения версий
            version_a, version_b = args.compare
            result = await run_comparison(
                args.capability,
                version_a,
                version_b,
                args.verbose
            )
        elif args.version:
            # Режим одиночного бенчмарка
            result = await run_single_benchmark(
                args.capability,
                args.version,
                args.verbose
            )
        else:
            print("\n❌ Ошибка: Необходимо указать --version или --compare")
            sys.exit(1)

        # Сохранение результатов в файл
        if args.output:
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            print(f"\n✅ Результаты сохранены в {args.output}")

        # Выход с кодом ошибки если бенчмарк не удался
        if 'error' in result and 'scenarios' not in result:
            sys.exit(1)

        if result.get('success_rate', 1) < 0.5:
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n\n⚠️  Прервано пользователем")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())
