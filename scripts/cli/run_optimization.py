#!/usr/bin/env python3
"""
CLI скрипт для запуска оптимизации промптов и контрактов.

ИСПОЛЬЗОВАНИЕ:
    python scripts/cli/run_optimization.py --capability <capability> --mode accuracy
    python scripts/cli/run_optimization.py --capability <capability> --target-accuracy 0.95

АРГУМЕНТЫ:
    --capability, -c        Название способности для оптимизации
    --mode, -m              Режим оптимизации (accuracy/speed/tokens/balanced)
    --target-accuracy, -t   Целевая точность (по умолчанию: 0.9)
    --max-iterations        Максимальное количество итераций (по умолчанию: 5)
    --output, -o            Файл для вывода результатов (JSON)
    --verbose               Подробный вывод
"""
import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional


def parse_args() -> argparse.Namespace:
    """Парсинг аргументов командной строки"""
    parser = argparse.ArgumentParser(
        description='Запуск оптимизации промптов и контрактов',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:
  %(prog)s -c planning.create_plan -m accuracy
  %(prog)s -c planning.create_plan -m accuracy -t 0.95
  %(prog)s -c planning.create_plan -m balanced --max-iterations 10
  %(prog)s -c planning.create_plan -m accuracy -o optimization_results.json
        """
    )

    parser.add_argument(
        '-c', '--capability',
        type=str,
        required=True,
        help='Название способности для оптимизации (например, planning.create_plan)'
    )

    parser.add_argument(
        '-m', '--mode',
        type=str,
        choices=['accuracy', 'speed', 'tokens', 'balanced'],
        default='accuracy',
        help='Режим оптимизации (по умолчанию: accuracy)'
    )

    parser.add_argument(
        '-t', '--target-accuracy',
        type=float,
        default=0.9,
        help='Целевая точность (по умолчанию: 0.9)'
    )

    parser.add_argument(
        '--max-iterations',
        type=int,
        default=5,
        help='Максимальное количество итераций (по умолчанию: 5)'
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


async def run_optimization(
    capability: str,
    mode: str,
    target_accuracy: float,
    max_iterations: int,
    verbose: bool = False
) -> dict:
    """
    Запуск цикла оптимизации.

    ARGS:
        capability: название способности
        mode: режим оптимизации
        target_accuracy: целевая точность
        max_iterations: максимальное количество итераций
        verbose: подробный вывод

    RETURNS:
        dict: результаты оптимизации
    """
    print(f"\n{'='*60}")
    print(f"Оптимизация: {capability}")
    print(f"{'='*60}")
    print(f"Режим: {mode}")
    print(f"Целевая точность: {target_accuracy}")
    print(f"Максимум итераций: {max_iterations}")
    print(f"{'='*60}\n")

    # Импорты внутри async функции
    from core.config.app_config import AppConfig
    from core.infrastructure.context.infrastructure_context import InfrastructureContext
    from core.application.context.application_context import ApplicationContext
    from core.application.services.optimization_service import OptimizationService, OptimizationConfig
    from core.application.services.benchmark_service import BenchmarkService
    from core.application.services.accuracy_evaluator import AccuracyEvaluatorService
    from core.application.services.prompt_contract_generator import PromptContractGenerator
    from core.infrastructure.metrics_storage import FileSystemMetricsStorage
    from core.infrastructure.log_storage import FileSystemLogStorage
    from core.infrastructure.event_bus.event_bus import get_event_bus
    from core.models.data.benchmark import OptimizationMode, TargetMetric

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
        log_storage = FileSystemLogStorage()
        metrics_collector = infra_context.metrics_collector
        log_collector = infra_context.log_collector
        accuracy_evaluator = AccuracyEvaluatorService()
        event_bus = get_event_bus()

        # Создание benchmark service
        benchmark_service = BenchmarkService(
            metrics_collector=metrics_collector,
            accuracy_evaluator=accuracy_evaluator,
            event_bus=event_bus
        )

        # Создание prompt generator
        data_dir = Path(config.data_dir)
        prompt_generator = PromptContractGenerator(
            llm_provider=None,  # TODO: получить из infra_context
            data_source=None,  # TODO: получить из app_context
            data_dir=data_dir
        )

        # Создание optimization service
        opt_config = OptimizationConfig(
            max_iterations=max_iterations,
            target_accuracy=target_accuracy,
            min_improvement=0.05,
            timeout_seconds=600
        )

        optimization_service = OptimizationService(
            benchmark_service=benchmark_service,
            prompt_generator=prompt_generator,
            metrics_collector=metrics_collector,
            log_collector=log_collector,
            event_bus=event_bus,
            config=opt_config
        )

        # Определение режима оптимизации
        mode_map = {
            'accuracy': OptimizationMode.ACCURACY,
            'speed': OptimizationMode.SPEED,
            'tokens': OptimizationMode.TOKENS,
            'balanced': OptimizationMode.BALANCED
        }
        optimization_mode = mode_map.get(mode, OptimizationMode.ACCURACY)

        # Определение целевых метрик
        target_metrics = [
            TargetMetric(
                name='accuracy',
                target_value=target_accuracy
            )
        ]

        # Запуск цикла оптимизации
        print(f"\n🚀 Запуск цикла оптимизации...\n")

        result = await optimization_service.start_optimization_cycle(
            capability=capability,
            mode=optimization_mode,
            target_metrics=target_metrics
        )

        if result is None:
            print("❌ Оптимизация не была запущена (возможно не выполнена проверка необходимости)")
            return {
                'capability': capability,
                'mode': mode,
                'timestamp': datetime.now().isoformat(),
                'status': 'not_started',
                'reason': 'Optimization not needed or not possible'
            }

        # Форматирование результатов
        optimization_result = {
            'capability': capability,
            'mode': mode,
            'timestamp': datetime.now().isoformat(),
            'status': 'completed',
            'from_version': result.from_version,
            'to_version': result.to_version,
            'iterations': result.iterations,
            'target_achieved': result.target_achieved,
            'initial_metrics': result.initial_metrics,
            'final_metrics': result.final_metrics,
            'improvements': result.improvements,
            'recommendations': result.recommendations
        }

        # Вывод результатов
        print(f"\n{'='*60}")
        print(f"Результаты оптимизации")
        print(f"{'='*60}")
        print(f"Статус: {'✅ Успешно' if result.target_achieved else '⚠️  Частично'}")
        print(f"Итераций выполнено: {result.iterations}")
        print(f"Версия: {result.from_version} → {result.to_version}")

        if result.initial_metrics and result.final_metrics:
            print(f"\nНачальные метрики:")
            for metric, value in result.initial_metrics.items():
                print(f"  {metric}: {value:.3f}" if isinstance(value, float) else f"  {metric}: {value}")

            print(f"\nКонечные метрики:")
            for metric, value in result.final_metrics.items():
                print(f"  {metric}: {value:.3f}" if isinstance(value, float) else f"  {metric}: {value}")

            if result.improvements:
                print(f"\nУлучшения:")
                for metric, improvement in result.improvements.items():
                    sign = '+' if improvement > 0 else ''
                    print(f"  {metric}: {sign}{improvement:.1f}%")

        if result.recommendations:
            print(f"\nРекомендации:")
            for rec in result.recommendations:
                print(f"  • {rec}")

        print(f"\n{'='*60}\n")

        if verbose:
            print("Полные результаты:")
            print(json.dumps(optimization_result, indent=2, ensure_ascii=False))

        return optimization_result

    except Exception as e:
        print(f"\n❌ Ошибка выполнения оптимизации: {e}")
        if verbose:
            import traceback
            traceback.print_exc()

        return {
            'capability': capability,
            'mode': mode,
            'timestamp': datetime.now().isoformat(),
            'status': 'failed',
            'error': str(e)
        }


async def main():
    """Основная функция"""
    args = parse_args()

    print("\n" + "="*60)
    print("Optimization CLI - Оптимизация промптов и контрактов")
    print("="*60)
    print(f"Конфигурация: {args.config}")
    print(f"Capability: {args.capability}")
    print(f"Режим: {args.mode}")
    print(f"Целевая точность: {args.target_accuracy}")

    try:
        result = await run_optimization(
            capability=args.capability,
            mode=args.mode,
            target_accuracy=args.target_accuracy,
            max_iterations=args.max_iterations,
            verbose=args.verbose
        )

        # Сохранение результатов в файл
        if args.output:
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            print(f"\n✅ Результаты сохранены в {args.output}")

        # Выход с кодом ошибки если оптимизация не удалась
        if result.get('status') == 'failed':
            sys.exit(1)

        if result.get('status') == 'not_started':
            sys.exit(2)

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
