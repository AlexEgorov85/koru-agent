#!/usr/bin/env python3
"""
CLI скрипт для запуска оптимизации промптов на новой архитектуре v2.

Использует компоненты:
- TraceCollector → PatternAnalyzer → PromptResponseAnalyzer → RootCauseAnalyzer → 
  ExampleExtractor → BenchmarkRunner → Evaluator → PromptGenerator → 
  VersionManager → SafetyLayer → OptimizationOrchestrator

ИСПОЛЬЗОВАНИЕ:
    python scripts/cli/run_optimization.py --capability <capability> --mode accuracy
    python scripts/cli/run_optimization.py --capability <capability> --dry-run --verbose
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
        description='Запуск оптимизации промптов (новая архитектура)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:
  %(prog)s --capability vector_books.search --mode accuracy
  %(prog)s --capability vector_books.search --mode accuracy --target-accuracy 0.95
  %(prog)s --capability vector_books.search --list-capabilities
  %(prog)s --capability vector_books.search --dry-run  # Тест без реальных изменений
        """
    )

    parser.add_argument(
        '-c', '--capability',
        type=str,
        required=False,
        help='Название способности для оптимизации (например, vector_books.search)'
    )

    parser.add_argument(
        '--list-capabilities',
        action='store_true',
        help='Список доступных способностей для оптимизации'
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
        '--min-improvement',
        type=float,
        default=0.05,
        help='Минимальное улучшение для продолжения (по умолчанию: 0.05)'
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
        '--dry-run',
        action='store_true',
        help='Тестовый запуск без реальных изменений'
    )

    parser.add_argument(
        '--session-log',
        type=str,
        help='Путь к файлу session.jsonl для анализа и оптимизации на основе лога'
    )

    parser.add_argument(
        '--analyze-only',
        action='store_true',
        help='Только анализ лога без запуска оптимизации'
    )

    return parser.parse_args()


def list_capabilities(data_dir: Path) -> list:
    """
    Получение списка доступных способностей.

    ARGS:
        data_dir: директория с данными

    RETURNS:
        list: список способностей
    """
    capabilities = []

    # Поиск в prompts
    prompts_dir = data_dir / 'prompts' / 'skill'
    if prompts_dir.exists():
        for item in prompts_dir.iterdir():
            if item.is_dir():
                # Проверяем есть ли промпты
                prompt_files = list(item.glob('*.yaml')) + list(item.glob('*.json'))
                if prompt_files:
                    capabilities.append(item.name)

    # Поиск в metrics
    metrics_dir = data_dir / 'metrics'
    if metrics_dir.exists():
        for item in metrics_dir.iterdir():
            if item.is_dir() and item.name not in capabilities:
                capabilities.append(item.name)

    return sorted(set(capabilities))


async def run_optimization_v2(
    capability: str,
    mode: str,
    target_accuracy: float,
    max_iterations: int,
    min_improvement: float,
    dry_run: bool = False,
    verbose: bool = False
) -> dict:
    """
    Запуск цикла оптимизации на новой архитектуре.

    ARGS:
        capability: название способности
        mode: режим оптимизации
        target_accuracy: целевая точность
        max_iterations: максимальное количество итераций
        min_improvement: минимальное улучшение
        dry_run: тестовый запуск
        verbose: подробный вывод

    RETURNS:
        dict: результаты оптимизации
    """
    print(f"\n{'='*60}")
    print(f"Оптимизация v2: {capability}")
    print(f"{'='*60}")
    print(f"Режим: {mode}")
    print(f"Целевая точность: {target_accuracy}")
    print(f"Максимум итераций: {max_iterations}")
    print(f"Минимальное улучшение: {min_improvement:.1%}")
    print(f"Dry run: {dry_run}")
    print(f"{'='*60}\n")

    try:
        # Импорты новой архитектуры
        from core.config import get_config
        from core.infrastructure_context.infrastructure_context import InfrastructureContext
        from core.application_context.application_context import ApplicationContext
        from core.infrastructure.event_bus.unified_event_bus import UnifiedEventBus
        from core.services.benchmarks.benchmark_models import OptimizationMode, FailureAnalysis

        from core.agent.components.optimization import (
            Evaluator,
            PromptGenerator,
            VersionManager,
            SafetyLayer,
            OptimizationOrchestrator,
            TraceCollector,
            PatternAnalyzer,
            PromptResponseAnalyzer,
            RootCauseAnalyzer,
            ExampleExtractor,
        )
        from core.services.benchmarks.benchmark_runner import BenchmarkRunner, BenchmarkRunConfig
        from core.agent.components.optimization.trace_collector import TraceCollectionConfig
        from core.agent.components.optimization.evaluator import EvaluationConfig
        from core.agent.components.optimization.prompt_generator import GenerationConfig
        from core.agent.components.optimization.safety_layer import SafetyConfig
        from core.agent.components.optimization.orchestrator import OrchestratorV2Config

        # Загрузка конфигурации
        config = get_config(profile='dev', data_dir='data')
        data_dir = Path(config.data_dir)

        # Инициализация инфраструктуры
        print("🔄 Инициализация инфраструктуры...")
        infra_context = InfrastructureContext(config)
        await infra_context.initialize()

        # Создание application context
        app_context = ApplicationContext(
            infrastructure_context=infra_context,
            config=config,
            profile='sandbox'
        )
        await app_context.initialize()
        print("✅ Инфраструктура готова\n")

        # Создание event bus
        event_bus = infra_context.event_bus

        # === СОЗДАНИЕ КОМПОНЕНТОВ ===
        print("🔧 Создание компонентов оптимизации...\n")

        # 1. TraceCollector
        from core.agent.components.optimization.trace_handler import TraceHandler
        from core.agent.components.optimization.trace_collector import TraceCollector, TraceCollectionConfig

        trace_handler = TraceHandler(
            session_handler=infra_context.session_handler,
            logs_dir="data/logs"
        )
        trace_collector = TraceCollector(
            trace_handler=trace_handler,
            config=TraceCollectionConfig()
        )
        print("  ✅ TraceCollector")

        # 2. BenchmarkRunner
        benchmark_config = BenchmarkRunConfig(
            temperature=0.0,  # Фиксированная для воспроизводимости
            seed=42,
            max_retries=3,
            timeout_seconds=60
        )

        # Callback для выполнения промптов
        async def executor_callback(input_text: str, version_id: str) -> dict:
            """Выполнение промпта через LLM"""
            # TODO: Реальная интеграция с LLM
            return {
                'success': True,
                'output': f'Mock output for {input_text[:50]}',
                'execution_time_ms': 100,
                'tokens_used': 50
            }

        benchmark_runner = BenchmarkRunner(
            event_bus=event_bus,
            executor_callback=executor_callback,
            config=benchmark_config
        )
        print("  ✅ BenchmarkRunner")

        # 4. Evaluator
        evaluation_config = EvaluationConfig(
            success_rate_weight=0.4,
            execution_success_weight=0.3,
            sql_validity_weight=0.2,
            latency_weight=0.1,
            min_success_rate=0.8,
            max_latency_ms=1000.0
        )
        evaluator = Evaluator(event_bus=event_bus, config=evaluation_config)
        print("  ✅ Evaluator")

        # 5. PromptGenerator
        generation_config = GenerationConfig(
            temperature=0.7,
            max_tokens=4000,
            top_p=0.9,
            diversity_threshold=0.3,
            max_candidates=3
        )
        prompt_generator = PromptGenerator(
            event_bus=event_bus,
            config=generation_config
        )
        print("  ✅ PromptGenerator")

        # 6. VersionManager
        version_manager = VersionManager(event_bus=event_bus)
        print("  ✅ VersionManager")

        # 7. SafetyLayer
        safety_config = SafetyConfig(
            max_success_rate_degradation=0.05,
            max_error_rate_increase=0.05,
            max_latency_increase_factor=1.5,
            min_acceptable_score=0.6,
            check_sql_injection=True,
            check_empty_result=True
        )
        safety_layer = SafetyLayer(event_bus=event_bus, config=safety_config)
        print("  ✅ SafetyLayer")

        # 3. PatternAnalyzer
        pattern_analyzer = PatternAnalyzer()
        print("  ✅ PatternAnalyzer")

        # 4. PromptResponseAnalyzer
        prompt_analyzer = PromptResponseAnalyzer()
        print("  ✅ PromptResponseAnalyzer")

        # 5. RootCauseAnalyzer
        root_cause_analyzer = RootCauseAnalyzer()
        print("  ✅ RootCauseAnalyzer")

        # 6. ExampleExtractor
        example_extractor = ExampleExtractor()
        print("  ✅ ExampleExtractor\n")

        # 7. OptimizationOrchestrator
        orchestrator_config = OrchestratorV2Config(
            max_iterations=max_iterations,
            target_accuracy=target_accuracy,
            min_improvement=min_improvement,
            timeout_seconds=600,
            max_examples=5,
            max_error_examples=3
        )
        orchestrator = OptimizationOrchestrator(
            trace_collector=trace_collector,
            pattern_analyzer=pattern_analyzer,
            prompt_analyzer=prompt_analyzer,
            root_cause_analyzer=root_cause_analyzer,
            example_extractor=example_extractor,
            benchmark_runner=benchmark_runner,
            evaluator=evaluator,
            prompt_generator=prompt_generator,
            version_manager=version_manager,
            safety_layer=safety_layer,
            event_bus=event_bus,
            config=orchestrator_config
        )
        orchestrator.set_executor_callback(executor_callback)

        # === ЗАПУСК ОПТИМИЗАЦИИ ===
        print("🚀 Запуск оптимизации...\n")

        # Определение режима
        mode_map = {
            'accuracy': OptimizationMode.ACCURACY,
            'speed': OptimizationMode.SPEED,
            'tokens': OptimizationMode.TOKENS,
            'balanced': OptimizationMode.BALANCED
        }
        optimization_mode = mode_map.get(mode, OptimizationMode.ACCURACY)

        if dry_run:
            print("⚠️  DRY RUN: Тестовый запуск без реальных изменений\n")

            # Тестирование TraceCollector
            print("📊 Тестирование TraceCollector...")
            traces = await trace_collector.collect_traces(capability)
            print(f"  Trace найдено: {len(traces)}")
            if traces:
                success_count = sum(1 for t in traces if t.get('success', False))
                print(f"  Успешных: {success_count}")
                print(f"  Ошибок: {len(traces) - success_count}\n")

            # Тестирование PatternAnalyzer
            print("📋 Тестирование PatternAnalyzer...")
            patterns = pattern_analyzer.analyze(traces)
            print(f"  Паттернов найдено: {len(patterns)}\n")

            # Тестирование PromptResponseAnalyzer
            print("🔍 Тестирование PromptResponseAnalyzer...")
            prompt_issues = prompt_analyzer.analyze_prompts(traces)
            print(f"  Проблем с промптами: {len(prompt_issues)}\n")

            # Тестирование RootCauseAnalyzer
            print("🎯 Тестирование RootCauseAnalyzer...")
            root_causes = root_cause_analyzer.analyze(
                patterns=patterns,
                prompt_issues=prompt_issues,
                response_issues=[]
            )
            print(f"  Корневых причин: {len(root_causes)}\n")

            # Тестирование ExampleExtractor
            print("📚 Тестирование ExampleExtractor...")
            examples, error_examples = example_extractor.extract_few_shot_examples(
                traces=traces,
                capability=capability,
                num_good=3,
                num_bad=2
            )
            print(f"  Примеров извлечено: {len(examples) + len(error_examples)}\n")

            result = {
                'capability': capability,
                'mode': mode,
                'timestamp': datetime.now().isoformat(),
                'status': 'dry_run',
                'traces_count': len(traces),
                'patterns_count': len(patterns),
                'prompt_issues_count': len(prompt_issues),
                'root_causes_count': len(root_causes),
                'examples_count': len(examples)
            }
        else:
            # Реальный запуск
            result = await orchestrator.optimize(
                capability=capability,
                mode=optimization_mode
            )

            if result is None:
                print("❌ Оптимизация не была запущена")
                return {
                    'capability': capability,
                    'mode': mode,
                    'timestamp': datetime.now().isoformat(),
                    'status': 'not_started',
                    'reason': 'Optimization not needed or not possible'
                }

            # Форматирование результатов
            result = {
                'capability': capability,
                'mode': mode,
                'timestamp': result.timestamp.isoformat(),
                'status': 'completed',
                'from_version': result.from_version,
                'to_version': result.to_version,
                'iterations': result.iterations,
                'target_achieved': result.target_achieved,
                'initial_metrics': result.initial_metrics,
                'final_metrics': result.final_metrics,
                'improvements': result.improvements
            }

        # Вывод результатов
        print(f"\n{'='*60}")
        print(f"Результаты оптимизации")
        print(f"{'='*60}")

        if dry_run:
            print(f"Статус: 🔹 Dry run завершён")
            print(f"Trace найдено: {result.get('traces_count', 0)}")
            print(f"Паттернов: {result.get('patterns_count', 0)}")
            print(f"Проблем с промптами: {result.get('prompt_issues_count', 0)}")
            print(f"Корневых причин: {result.get('root_causes_count', 0)}")
            print(f"Примеров: {result.get('examples_count', 0)}")
        else:
            status_icon = '✅' if result.get('target_achieved') else '⚠️'
            print(f"Статус: {status_icon} {'Успешно' if result.get('target_achieved') else 'Частично'}")
            print(f"Итераций: {result.get('iterations', 0)}")
            print(f"Версия: {result.get('from_version')} → {result.get('to_version')}")

            if result.get('initial_metrics') and result.get('final_metrics'):
                print(f"\nНачальные метрики:")
                for metric, value in result['initial_metrics'].items():
                    print(f"  {metric}: {value:.3f}" if isinstance(value, float) else f"  {metric}: {value}")

                print(f"\nКонечные метрики:")
                for metric, value in result['final_metrics'].items():
                    print(f"  {metric}: {value:.3f}" if isinstance(value, float) else f"  {metric}: {value}")

                if result.get('improvements'):
                    print(f"\nУлучшения:")
                    for metric, improvement in result['improvements'].items():
                        sign = '+' if improvement > 0 else ''
                        print(f"  {metric}: {sign}{improvement:.1f}%")

        print(f"\n{'='*60}\n")

        if verbose:
            print("Полные результаты:")
            print(json.dumps(result, indent=2, ensure_ascii=False))

        return result

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


async def analyze_session_log(log_path: str, verbose: bool = False):
    """
    Анализ лога сессии и генерация рекомендаций по оптимизации.
    
    ARGS:
        log_path: путь к session.jsonl
        verbose: подробный вывод
    
    RETURNS:
        dict: результат анализа
    """
    print("\n" + "="*60)
    print("Session Log Analyzer")
    print("="*60)
    
    try:
        from core.agent.components.optimization.session_log_parser import SessionLogParser
        from core.agent.components.optimization.prompt_analyzer import analyze_prompts_from_session
        
        parser = SessionLogParser()
        session = parser.parse_file(Path(log_path))
        session_report = parser.generate_analysis_report(session)
        prompt_report = analyze_prompts_from_session(session_report)
        
        print(f"\n[ANALYSIS] ANALIZ SESII")
        print("="*60)
        print(f"Path: {log_path}")
        print(f"Duration: {session_report['summary']['duration_seconds']:.1f} sec")
        print(f"LLM calls: {session_report['summary']['total_llm_calls']}")
        print(f"Actions: {session_report['summary']['total_actions']}")
        print(f"Failed actions: {session_report['summary']['actions_with_errors']}")
        
        if session_report['goals']:
            print(f"\n[G] Goals ({len(session_report['goals'])}):")
            for i, goal in enumerate(session_report['goals'][:3], 1):
                print(f"  {i}. {goal[:80]}...")
        
        print(f"\n[P] Patterns:")
        for pattern, count in session_report['patterns'].items():
            print(f"  - {pattern}: {count}")
        
        if session_report['failed_actions']:
            print(f"\n[!] Errors ({len(session_report['failed_actions'])}):")
            for err in session_report['failed_actions'][:5]:
                print(f"  - [{err['action']}] {err.get('error', 'N/A')[:60]}...")
        
        # Вывод конкретных рекомендаций по промптам
        if prompt_report['issues']:
            print(f"\n[PROMPT ISSUES] Found {len(prompt_report['issues'])} prompt issues:")
            for issue in prompt_report['issues']:
                print(f"\n  [{issue['severity'].upper()}] {issue['type']}")
                print(f"  File: {issue['file']}")
                print(f"  Section: {issue['section']}")
                print(f"  Problem: {issue['description'][:80]}...")
                if issue['suggested_fix']:
                    print(f"\n  Suggested fix:")
                    for line in issue['suggested_fix'].split('\n')[:8]:
                        print(f"    {line}")
        
        if verbose:
            print(f"\n[F] Session report:")
            print(json.dumps(session_report, indent=2, ensure_ascii=False))
            print(f"\n[F] Prompt report:")
            print(json.dumps(prompt_report, indent=2, ensure_ascii=False))
        
        # Объединяем результаты
        result = {
            'session': session_report,
            'prompts': prompt_report,
        }
        
        return result
        
    except Exception as e:
        print(f"\n[!] Analysis error: {e}")
        import traceback
        traceback.print_exc()
        return {'status': 'failed', 'error': str(e)}
        
        return report
        
    except Exception as e:
        print(f"\n[!] Analysis error: {e}")
        import traceback
        traceback.print_exc()
        return {'status': 'failed', 'error': str(e)}


async def main():
    """Основная функция"""
    args = parse_args()

    print("\n" + "="*60)
    print("Optimization CLI v2 - Новая архитектура")
    print("="*60)

    # Загрузка конфигурации для получения data_dir
    try:
        from core.config import get_config
        config = get_config(profile='dev', data_dir='data')
        data_dir = Path(config.data_dir)
    except Exception:
        data_dir = Path('data')

    # Анализ лога сессии
    if args.session_log:
        result = await analyze_session_log(args.session_log, args.verbose)
        
        if args.output:
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            print(f"\n✅ Результаты сохранены в {args.output}")
        
        if args.analyze_only:
            sys.exit(0)
        
        # Если указана capability, продолжаем оптимизацию
        if not args.capability:
            sys.exit(0)
    
    # Список способностей
    if args.list_capabilities:
        capabilities = list_capabilities(data_dir)
        print(f"\nДоступные способности ({len(capabilities)}):")
        for cap in capabilities:
            print(f"  - {cap}")
        print()
        sys.exit(0)

    # Проверка capability
    if not args.capability:
        print("❌ Укажите --capability, --list-capabilities или --session-log")
        sys.exit(1)

    print(f"Конфигурация: registry.yaml")
    print(f"Data dir: {data_dir}")
    print(f"Capability: {args.capability}")
    print(f"Режим: {args.mode}")
    print(f"Целевая точность: {args.target_accuracy}")

    try:
        result = await run_optimization_v2(
            capability=args.capability,
            mode=args.mode,
            target_accuracy=args.target_accuracy,
            max_iterations=args.max_iterations,
            min_improvement=args.min_improvement,
            dry_run=args.dry_run,
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
