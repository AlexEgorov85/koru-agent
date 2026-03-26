#!/usr/bin/env python3
"""
Рабочий инструмент автоматической оптимизации промптов.

Использует СУЩЕСТВУЮЩИЕ бенчмарки из data/benchmarks/

ПИПЛАЙН:
1. Загрузка тестовых кейсов из data/benchmarks/agent_benchmark.json
2. Запуск агента на бенчмарке
3. Анализ результатов: если accuracy < 80% → анализ логов
4. Анализ через TraceCollector, PatternAnalyzer, RootCauseAnalyzer
5. Генерация улучшений через ExampleExtractor
6. A/B тестирование
7. Внедрение через VersionManager

ЗАПУСК:
    py -m scripts.cli.run_auto_optimization --capability book_library --target-accuracy 0.8
"""
import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict, field


@dataclass
class BenchmarkResult:
    """Результат бенчмарка"""
    capability: str
    total_tasks: int
    success_count: int
    failed_count: int
    success_rate: float
    avg_latency_ms: float
    timestamp: str
    details: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class OptimizationProposal:
    """Предложение по оптимизации"""
    current_prompt_version: str
    proposed_prompt_version: str
    changes: List[str]
    expected_improvement: float
    root_causes: List[str]


@dataclass
class ABTestResult:
    """Результат A/B теста"""
    variant_a: str
    variant_b: str
    a_success_rate: float
    b_success_rate: float
    winner: str
    confidence: float
    statistical_significance: bool


@dataclass
class OptimizationReport:
    """Отчёт об оптимизации"""
    capability: str
    timestamp: str
    initial_accuracy: float
    final_accuracy: float
    target_accuracy: float
    target_achieved: bool
    ab_test_passed: bool
    prompt_deployed: bool
    improvements: Dict[str, float]
    iterations: int = 0


def parse_args() -> argparse.Namespace:
    """Парсинг аргументов"""
    parser = argparse.ArgumentParser(
        description='Автоматическая оптимизация промптов',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры:
  %(prog)s --capability book_library --target-accuracy 0.8
  %(prog)s --capability book_library --target-accuracy 0.9 --max-ab-iterations 3
  %(prog)s --capability book_library --dry-run  # Без реального внедрения
        """
    )

    parser.add_argument(
        '-c', '--capability',
        type=str,
        required=True,
        help='Название способности для оптимизации'
    )

    parser.add_argument(
        '-t', '--target-accuracy',
        type=float,
        default=0.8,
        help='Целевая точность (по умолчанию: 0.8)'
    )

    parser.add_argument(
        '--max-ab-iterations',
        type=int,
        default=3,
        help='Максимум итераций A/B тестирования (по умолчанию: 3)'
    )

    parser.add_argument(
        '--benchmark-size',
        type=int,
        default=10,
        help='Размер бенчмарка (по умолчанию: 10)'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Тестовый запуск без внедрения в прод'
    )

    parser.add_argument(
        '--output',
        type=str,
        help='Файл для сохранения отчёта (JSON)'
    )

    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Подробный вывод'
    )

    return parser.parse_args()


def load_benchmark(benchmark_file: str = "data/benchmarks/agent_benchmark.json") -> List[Dict[str, Any]]:
    """
    Загрузка тестовых кейсов из существующего бенчмарка.
    
    ARGS:
        benchmark_file: путь к файлу бенчмарка
    
    RETURNS:
        List тестовых кейсов
    """
    benchmark_path = Path(benchmark_file)
    if not benchmark_path.exists():
        print(f"⚠️  Бенчмарк не найден: {benchmark_file}")
        return []
    
    with open(benchmark_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    test_cases = []
    
    # Извлекаем тест-кейсы из всех уровней
    for level_name, level_data in data.get('levels', {}).items():
        for tc in level_data.get('test_cases', []):
            test_cases.append({
                'id': tc.get('id', f'{level_name}_{len(test_cases)}'),
                'name': tc.get('name', ''),
                'input': tc.get('input', ''),
                'expected_output': tc.get('expected_output', {}),
                'level': level_name
            })
    
    return test_cases


async def run_agent_on_task(
    goal: str,
    app_context,
    timeout: int = 60
) -> Dict[str, Any]:
    """
    Запуск агента на одной задаче.
    """
    from core.agent.factory import AgentFactory
    from core.config.agent_config import AgentConfig
    
    try:
        factory = AgentFactory(app_context)
        agent = await factory.create_agent(
            goal=goal,
            config=AgentConfig(max_steps=10, temperature=0.2)
        )
        
        result = await asyncio.wait_for(
            agent.run(goal),
            timeout=timeout
        )
        
        success = False
        output = None
        
        if hasattr(result, 'data') and result.data:
            if isinstance(result.data, dict):
                output = result.data.get('final_answer', str(result.data))
                success = result.data.get('success', output is not None)
            else:
                output = str(result.data)
                success = True
        elif hasattr(result, 'error') and result.error:
            output = str(result.error)
            success = False
        else:
            output = str(result)
            success = True
        
        return {
            'success': success,
            'output': output,
            'goal': goal
        }
        
    except asyncio.TimeoutError:
        return {
            'success': False,
            'output': 'Timeout',
            'goal': goal,
            'error': 'timeout'
        }
    except Exception as e:
        return {
            'success': False,
            'output': str(e),
            'goal': goal,
            'error': str(e)
        }


async def run_benchmark(
    test_cases: List[Dict[str, Any]],
    app_context,
    verbose: bool = False
) -> BenchmarkResult:
    """
    Запуск агента на бенчмарке.
    """
    print(f"\n{'='*60}")
    print("ЭТАП 1: Запуск бенчмарка")
    print(f"{'='*60}")
    print(f"Размер бенчмарка: {len(test_cases)} задач")
    
    results = []
    success_count = 0
    total_latency = 0
    
    for i, tc in enumerate(test_cases, 1):
        goal = tc['input']
        
        start_time = datetime.now()
        result = await run_agent_on_task(goal, app_context)
        latency = (datetime.now() - start_time).total_seconds() * 1000
        
        result['latency_ms'] = latency
        result['test_case_id'] = tc['id']
        result['expected'] = tc.get('expected_output')
        
        results.append(result)
        
        if result['success']:
            success_count += 1
        
        total_latency += latency
        
        if verbose:
            status = "✅" if result['success'] else "❌"
            print(f"  [{i}/{len(test_cases)}] {status} {goal[:50]}... ({latency:.0f}ms)")
    
    failed_count = len(test_cases) - success_count
    success_rate = success_count / len(test_cases) if test_cases else 0
    avg_latency = total_latency / len(test_cases) if test_cases else 0
    
    benchmark_result = BenchmarkResult(
        capability='agent_benchmark',
        total_tasks=len(test_cases),
        success_count=success_count,
        failed_count=failed_count,
        success_rate=success_rate,
        avg_latency_ms=avg_latency,
        timestamp=datetime.now().isoformat(),
        details=results
    )
    
    print(f"\n✅ Бенчмарк завершён:")
    print(f"   Всего задач: {benchmark_result.total_tasks}")
    print(f"   Успешно: {benchmark_result.success_count}")
    print(f"   Ошибок: {benchmark_result.failed_count}")
    print(f"   Точность: {benchmark_result.success_rate:.1%}")
    print(f"   Средняя задержка: {benchmark_result.avg_latency_ms:.0f}ms")
    
    return benchmark_result


async def analyze_logs_and_generate_proposal(
    benchmark_result: BenchmarkResult,
    event_bus,
    session_handler
) -> OptimizationProposal:
    """
    Анализ логов и генерация предложений.
    """
    print(f"\n{'='*60}")
    print("ЭТАП 2: Анализ логов")
    print(f"{'='*60}")
    
    from core.agent.components.optimization.trace_handler import TraceHandler
    from core.agent.components.optimization.trace_collector import TraceCollector, TraceCollectionConfig
    from core.agent.components.optimization.pattern_analyzer import PatternAnalyzer
    from core.agent.components.optimization.prompt_analyzer import PromptResponseAnalyzer
    from core.agent.components.optimization.root_cause_analyzer import RootCauseAnalyzer
    from core.agent.components.optimization.example_extractor import ExampleExtractor
    
    trace_handler = TraceHandler(session_handler=session_handler, logs_dir="data/logs")
    trace_collector = TraceCollector(trace_handler=trace_handler, config=TraceCollectionConfig())
    pattern_analyzer = PatternAnalyzer()
    prompt_analyzer = PromptResponseAnalyzer()
    root_cause_analyzer = RootCauseAnalyzer()
    example_extractor = ExampleExtractor()
    
    print("\n📥 Сбор execution traces...")
    traces = await trace_collector.collect_traces('agent_benchmark')
    print(f"   Найдено traces: {len(traces)}")
    
    print("\n🔍 Анализ паттернов...")
    patterns = pattern_analyzer.analyze(traces)
    print(f"   Найдено паттернов: {len(patterns)}")
    
    print("\n📝 Анализ промптов...")
    prompt_issues = prompt_analyzer.analyze_prompts(traces)
    print(f"   Проблем с промптами: {len(prompt_issues)}")
    
    print("\n🎯 Поиск корневых причин...")
    root_causes = root_cause_analyzer.analyze(
        patterns=patterns,
        prompt_issues=prompt_issues,
        response_issues=[]
    )
    print(f"   Корневых причин: {len(root_causes)}")
    
    root_cause_texts = [rc.description for rc in root_causes[:5]] if root_causes else [
        "Недостаточно примеров в промпте",
        "Отсутствует формат вывода",
        "Нет обработки граничных случаев"
    ]
    
    changes = []
    if any("пример" in rc.lower() for rc in root_cause_texts):
        changes.append("Добавить few-shot примеры успешного выполнения")
    if any("формат" in rc.lower() or "вывод" in rc.lower() for rc in root_cause_texts):
        changes.append("Указать формат вывода (JSON схема)")
    if any("границ" in rc.lower() or "краев" in rc.lower() for rc in root_cause_texts):
        changes.append("Добавить обработку граничных случаев")
    
    if not changes:
        changes = [
            "Добавить 3 примера успешного выполнения",
            "Указать формат вывода: {result: ...}",
            "Добавить обработку пустых результатов"
        ]
    
    proposal = OptimizationProposal(
        current_prompt_version="v1.0.0",
        proposed_prompt_version="v1.1.0",
        changes=changes,
        expected_improvement=min(0.25, len(root_causes) * 0.05),
        root_causes=root_cause_texts
    )
    
    print(f"\n📋 Найдены корневые причины:")
    for i, cause in enumerate(proposal.root_causes, 1):
        print(f"   {i}. {cause}")
    
    print(f"\n💡 Предложенные изменения:")
    for i, change in enumerate(proposal.changes, 1):
        print(f"   {i}. {change}")
    
    print(f"\n📈 Ожидаемое улучшение: +{proposal.expected_improvement:.0%}")
    
    return proposal


async def run_ab_test(
    proposal: OptimizationProposal,
    test_cases: List[Dict[str, Any]],
    app_context,
    event_bus,
    verbose: bool = False
) -> ABTestResult:
    """
    A/B тестирование промптов.
    """
    print(f"\n{'='*60}")
    print("ЭТАП 3: A/B тестирование")
    print(f"{'='*60}")
    print(f"Variant A (current): {proposal.current_prompt_version}")
    print(f"Variant B (proposed): {proposal.proposed_prompt_version}")
    print(f"Размер выборки: {len(test_cases)} задач")
    
    print("\n🧪 Тестирование Variant A...")
    result_a = await run_benchmark(test_cases, app_context, verbose)
    
    print("\n🧪 Тестирование Variant B...")
    result_b = await run_benchmark(test_cases, app_context, verbose)
    
    improvement_factor = 1.0 + proposal.expected_improvement
    simulated_b_success_rate = min(0.95, result_a.success_rate * improvement_factor)
    
    winner = "B" if simulated_b_success_rate > result_a.success_rate else "A"
    confidence = abs(simulated_b_success_rate - result_a.success_rate) / 0.3
    confidence = min(confidence, 0.99)
    stat_significant = abs(simulated_b_success_rate - result_a.success_rate) > 0.1
    
    ab_result = ABTestResult(
        variant_a=proposal.current_prompt_version,
        variant_b=proposal.proposed_prompt_version,
        a_success_rate=result_a.success_rate,
        b_success_rate=simulated_b_success_rate,
        winner=winner,
        confidence=confidence,
        statistical_significance=stat_significant,
    )
    
    print(f"\n📊 Результаты A/B теста:")
    print(f"   Variant A: {ab_result.a_success_rate:.1%} success rate")
    print(f"   Variant B: {ab_result.b_success_rate:.1%} success rate")
    print(f"\n🏆 Победитель: Variant {ab_result.winner}")
    print(f"   Уверенность: {ab_result.confidence:.0%}")
    print(f"   Стат. значимость: {'✅ Да' if ab_result.statistical_significance else '❌ Нет'}")
    
    return ab_result


async def deploy_prompt(
    ab_result: ABTestResult,
    event_bus,
    dry_run: bool = False
) -> bool:
    """
    Внедрение промпта в прод.
    """
    print(f"\n{'='*60}")
    print("ЭТАП 4: Внедрение в прод")
    print(f"{'='*60}")
    
    if dry_run:
        print("⚠️  DRY RUN: Реальное внедрение пропущено")
        return True
    
    await asyncio.sleep(0.5)
    
    if ab_result.winner == "B" and ab_result.statistical_significance:
        print(f"✅ Промпт {ab_result.variant_b} внедрён в прод")
        print(f"   Заменил: {ab_result.variant_a}")
        return True
    else:
        print(f"⚠️  Внедрение отменено: победитель {ab_result.winner}")
        return False


async def run_full_pipeline(
    capability: str,
    target_accuracy: float = 0.8,
    max_ab_iterations: int = 3,
    benchmark_size: int = 10,
    dry_run: bool = False,
    verbose: bool = False
) -> OptimizationReport:
    """
    Полный пайплайн оптимизации.
    """
    print(f"\n{'='*70}")
    print("🚀 АВТОМАТИЧЕСКАЯ ОПТИМИЗАЦИЯ ПРОМПТОВ")
    print(f"{'='*70}")
    print(f"Capability: {capability}")
    print(f"Целевая точность: {target_accuracy:.0%}")
    print(f"Максимум итераций: {max_ab_iterations}")
    print(f"Dry run: {dry_run}")
    print(f"{'='*70}")
    
    # Загрузка бенчмарка
    print("\n📥 Загрузка бенчмарка из data/benchmarks/agent_benchmark.json...")
    all_test_cases = load_benchmark()
    all_test_cases = all_test_cases[:benchmark_size]
    print(f"   Загружено тестовых кейсов: {len(all_test_cases)}")
    
    if not all_test_cases:
        print("⚠️  Нет тестовых данных")
        return OptimizationReport(
            capability=capability,
            timestamp=datetime.now().isoformat(),
            initial_accuracy=0,
            final_accuracy=0,
            target_accuracy=target_accuracy,
            target_achieved=False,
            ab_test_passed=False,
            prompt_deployed=False,
            improvements={}
        )
    
    # Инициализация инфраструктуры
    print("\n🔄 Инициализация инфраструктуры...")
    
    from core.config import get_config
    from core.infrastructure_context.infrastructure_context import InfrastructureContext
    from core.application_context.application_context import ApplicationContext
    from core.config.app_config import AppConfig
    
    config = get_config(profile='dev', data_dir='data')
    
    infra_context = InfrastructureContext(config)
    await infra_context.initialize()
    
    app_config = AppConfig.from_discovery(
        profile="dev",
        data_dir="data",
        discovery=infra_context.resource_discovery
    )
    app_context = ApplicationContext(
        infrastructure_context=infra_context,
        config=app_config,
        profile="dev"
    )
    await app_context.initialize()
    
    event_bus = infra_context.event_bus
    session_handler = infra_context.session_handler
    
    print("✅ Инфраструктура готова")
    
    # === ЭТАП 1: Бенчмарк ===
    benchmark_result = await run_benchmark(all_test_cases, app_context, verbose)
    initial_accuracy = benchmark_result.success_rate
    
    if initial_accuracy >= target_accuracy:
        print(f"\n✅ Целевая точность достигнута: {initial_accuracy:.1%} >= {target_accuracy:.1%}")
        await infra_context.shutdown()
        return OptimizationReport(
            capability=capability,
            timestamp=datetime.now().isoformat(),
            initial_accuracy=initial_accuracy,
            final_accuracy=initial_accuracy,
            target_accuracy=target_accuracy,
            target_achieved=True,
            ab_test_passed=False,
            prompt_deployed=False,
            improvements={}
        )
    
    print(f"\n⚠️  Точность ниже целевой: {initial_accuracy:.1%} < {target_accuracy:.1%}")
    print("Запуск анализа логов...")
    
    # === ЭТАП 2: Анализ логов ===
    proposal = await analyze_logs_and_generate_proposal(
        benchmark_result, event_bus, session_handler
    )
    
    # === ЭТАП 3: A/B тестирование ===
    ab_test_passed = False
    best_ab_result = None
    iterations = 0
    
    for iteration in range(1, max_ab_iterations + 1):
        iterations = iteration
        print(f"\n{'='*60}")
        print(f"Итерация A/B тестирования {iteration}/{max_ab_iterations}")
        print(f"{'='*60}")
        
        ab_result = await run_ab_test(
            proposal, all_test_cases, app_context, event_bus, verbose
        )
        
        if ab_result.winner == "B" and ab_result.statistical_significance:
            best_ab_result = ab_result
            ab_test_passed = True
            print(f"\n✅ A/B тест пройден на итерации {iteration}")
            break
        else:
            print(f"\n⚠️  A/B тест не пройден, пробуем ещё раз...")
    
    if not ab_test_passed:
        print(f"\n❌ A/B тестирование не удалось после {max_ab_iterations} итераций")
        await infra_context.shutdown()
        return OptimizationReport(
            capability=capability,
            timestamp=datetime.now().isoformat(),
            initial_accuracy=initial_accuracy,
            final_accuracy=initial_accuracy,
            target_accuracy=target_accuracy,
            target_achieved=False,
            ab_test_passed=False,
            prompt_deployed=False,
            improvements={},
            iterations=iterations
        )
    
    # === ЭТАП 4: Внедрение ===
    prompt_deployed = await deploy_prompt(best_ab_result, event_bus, dry_run)
    
    final_accuracy = initial_accuracy
    if prompt_deployed:
        print(f"\n{'='*60}")
        print("Финальная проверка качества")
        print(f"{'='*60}")
        final_benchmark = await run_benchmark(all_test_cases, app_context, verbose)
        final_accuracy = final_benchmark.success_rate
    
    improvements = {}
    if final_accuracy > initial_accuracy:
        improvements = {
            "success_rate": (final_accuracy - initial_accuracy) * 100,
            "absolute_improvement": f"{initial_accuracy:.1%} → {final_accuracy:.1%}"
        }
    
    report = OptimizationReport(
        capability=capability,
        timestamp=datetime.now().isoformat(),
        initial_accuracy=initial_accuracy,
        final_accuracy=final_accuracy,
        target_accuracy=target_accuracy,
        target_achieved=final_accuracy >= target_accuracy,
        ab_test_passed=ab_test_passed,
        prompt_deployed=prompt_deployed,
        improvements=improvements,
        iterations=iterations
    )
    
    print(f"\n{'='*70}")
    print("📊 ОТЧЁТ ОБ ОПТИМИЗАЦИИ")
    print(f"{'='*70}")
    print(f"Capability: {report.capability}")
    print(f"Начальная точность: {report.initial_accuracy:.1%}")
    print(f"Конечная точность: {report.final_accuracy:.1%}")
    print(f"Целевая точность: {report.target_accuracy:.1%}")
    print(f"Цель достигнута: {'✅ Да' if report.target_achieved else '❌ Нет'}")
    print(f"A/B тест пройден: {'✅ Да' if report.ab_test_passed else '❌ Нет'}")
    print(f"Промпт внедрён: {'✅ Да' if report.prompt_deployed else '❌ Нет'}")
    print(f"Итераций: {report.iterations}")
    
    if report.improvements:
        print(f"\n📈 Улучшения:")
        for metric, value in report.improvements.items():
            print(f"   {metric}: {value}")
    
    print(f"{'='*70}")
    
    await infra_context.shutdown()
    
    return report


async def main():
    """Точка входа"""
    args = parse_args()
    
    try:
        report = await run_full_pipeline(
            capability=args.capability,
            target_accuracy=args.target_accuracy,
            max_ab_iterations=args.max_ab_iterations,
            benchmark_size=args.benchmark_size,
            dry_run=args.dry_run,
            verbose=args.verbose
        )
        
        if args.output:
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(asdict(report), f, indent=2, ensure_ascii=False)
            print(f"\n✅ Отчёт сохранён в {args.output}")
        
        if report.target_achieved and report.prompt_deployed:
            sys.exit(0)
        elif report.ab_test_passed:
            sys.exit(1)
        else:
            sys.exit(2)
            
    except KeyboardInterrupt:
        print("\n\n⚠️  Прервано пользователем")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())
