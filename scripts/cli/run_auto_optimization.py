#!/usr/bin/env python3
"""
Автоматическая оптимизация промптов с A/B тестированием.

ПИПЛАЙН:
1. Запуск агента на бенчмарке
2. Анализ результатов выполнения
3. Если качество < 80% → запуск анализа логов
4. Предложение по улучшению промптов
5. A/B тестирование промптов
6. Внедрение промпта в прод (если успешен)

ИСПОЛЬЗОВАНИЕ:
    py -m scripts.cli.run_auto_optimization --capability book_library --target-accuracy 0.8
"""
import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict

from core.benchmarks.benchmark_models import OptimizationMode


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


def parse_args() -> argparse.Namespace:
    """Парсинг аргументов"""
    parser = argparse.ArgumentParser(
        description='Автоматическая оптимизация промптов с A/B тестированием',
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
        default=20,
        help='Размер бенчмарка (по умолчанию: 20)'
    )

    parser.add_argument(
        '--ab-test-size',
        type=int,
        default=10,
        help='Размер выборки для A/B теста (по умолчанию: 10)'
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


async def run_benchmark(
    capability: str,
    benchmark_size: int = 20
) -> BenchmarkResult:
    """
    ЭТАП 1: Запуск агента на бенчмарке.
    
    ARGS:
        capability: название способности
        benchmark_size: количество тестовых задач
    
    RETURNS:
        BenchmarkResult: результаты бенчмарка
    """
    print(f"\n{'='*60}")
    print("ЭТАП 1: Запуск бенчмарка")
    print(f"{'='*60}")
    print(f"Capability: {capability}")
    print(f"Размер бенчмарка: {benchmark_size} задач")
    
    # TODO: Интеграция с реальным бенчмарком
    # Пока используем mock данные
    await asyncio.sleep(1)  # Имитация работы
    
    # Mock результаты (для демонстрации)
    import random
    success_count = random.randint(12, 18)  # 60-90% success rate
    failed_count = benchmark_size - success_count
    success_rate = success_count / benchmark_size
    avg_latency = random.uniform(200, 500)
    
    result = BenchmarkResult(
        capability=capability,
        total_tasks=benchmark_size,
        success_count=success_count,
        failed_count=failed_count,
        success_rate=success_rate,
        avg_latency_ms=avg_latency,
        timestamp=datetime.now().isoformat()
    )
    
    print(f"\n✅ Бенчмарк завершён:")
    print(f"   Всего задач: {result.total_tasks}")
    print(f"   Успешно: {result.success_count}")
    print(f"   Ошибок: {result.failed_count}")
    print(f"   Точность: {result.success_rate:.1%}")
    print(f"   Средняя задержка: {result.avg_latency_ms:.0f}ms")
    
    return result


async def analyze_logs(
    capability: str,
    benchmark_result: BenchmarkResult
) -> OptimizationProposal:
    """
    ЭТАП 2: Анализ логов и генерация предложений.
    
    ARGS:
        capability: название способности
        benchmark_result: результаты бенчмарка
    
    RETURNS:
        OptimizationProposal: предложение по оптимизации
    """
    print(f"\n{'='*60}")
    print("ЭТАП 2: Анализ логов")
    print(f"{'='*60}")
    
    # TODO: Интеграция с TraceCollector, PatternAnalyzer, RootCauseAnalyzer
    await asyncio.sleep(1)  # Имитация анализа
    
    # Mock анализ
    root_causes = [
        "Промпт не содержит few-shot примеров",
        "Отсутствует формат вывода JSON",
        "Нет обработки граничных случаев"
    ]
    
    changes = [
        "Добавить 3 примера успешного выполнения",
        "Указать формат вывода: {books: [{title, year}]}",
        "Добавить обработку пустых результатов"
    ]
    
    proposal = OptimizationProposal(
        current_prompt_version="v1.0.0",
        proposed_prompt_version="v1.1.0",
        changes=changes,
        expected_improvement=0.15,  # Ожидаемое улучшение +15%
        root_causes=root_causes
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
    capability: str,
    proposal: OptimizationProposal,
    test_size: int = 10
) -> ABTestResult:
    """
    ЭТАП 3: A/B тестирование промптов.
    
    ARGS:
        capability: название способности
        proposal: предложение по оптимизации
        test_size: размер выборки для каждой группы
    
    RETURNS:
        ABTestResult: результаты A/B теста
    """
    print(f"\n{'='*60}")
    print("ЭТАП 3: A/B тестирование")
    print(f"{'='*60}")
    print(f"Variant A (current): {proposal.current_prompt_version}")
    print(f"Variant B (proposed): {proposal.proposed_prompt_version}")
    print(f"Размер выборки: {test_size} задач на группу")
    
    # TODO: Интеграция с ABTester
    await asyncio.sleep(1)  # Имитация теста
    
    # Mock результаты A/B теста
    import random
    a_success_rate = random.uniform(0.55, 0.70)  # Текущая версия
    b_success_rate = a_success_rate + random.uniform(0.1, 0.25)  # Новая лучше
    b_success_rate = min(b_success_rate, 0.95)
    
    winner = "B" if b_success_rate > a_success_rate else "A"
    confidence = abs(b_success_rate - a_success_rate) / 0.3  # Нормализованная уверенность
    confidence = min(confidence, 0.99)
    stat_significant = abs(b_success_rate - a_success_rate) > 0.1
    
    result = ABTestResult(
        variant_a=proposal.current_prompt_version,
        variant_b=proposal.proposed_prompt_version,
        a_success_rate=a_success_rate,
        b_success_rate=b_success_rate,
        winner=winner,
        confidence=confidence,
        statistical_significance=stat_significant
    )
    
    print(f"\n📊 Результаты A/B теста:")
    print(f"   Variant A: {result.a_success_rate:.1%} success rate")
    print(f"   Variant B: {result.b_success_rate:.1%} success rate")
    print(f"\n🏆 Победитель: Variant {result.winner}")
    print(f"   Уверенность: {result.confidence:.0%}")
    print(f"   Стат. значимость: {'✅ Да' if result.statistical_significance else '❌ Нет'}")
    
    return result


async def deploy_prompt(
    capability: str,
    ab_result: ABTestResult,
    dry_run: bool = False
) -> bool:
    """
    ЭТАП 4: Внедрение промпта в прод.
    
    ARGS:
        capability: название способности
        ab_result: результаты A/B теста
        dry_run: тестовый режим без реального внедрения
    
    RETURNS:
        bool: успешно ли внедрение
    """
    print(f"\n{'='*60}")
    print("ЭТАП 4: Внедрение в прод")
    print(f"{'='*60}")
    
    if dry_run:
        print("⚠️  DRY RUN: Реальное внедрение пропущено")
        return True
    
    # TODO: Интеграция с VersionManager для promote версии
    await asyncio.sleep(0.5)  # Имитация
    
    if ab_result.winner == "B" and ab_result.statistical_significance:
        print(f"✅ Промпт {ab_result.variant_b} внедрён в прод")
        print(f"   Заменил: {ab_result.variant_a}")
        return True
    else:
        print(f"⚠️  Внедрение отменено: победитель {ab_result.winner}, "
              f"стат. значимость: {ab_result.statistical_significance}")
        return False


async def run_full_pipeline(
    capability: str,
    target_accuracy: float = 0.8,
    max_ab_iterations: int = 3,
    benchmark_size: int = 20,
    ab_test_size: int = 10,
    dry_run: bool = False,
    verbose: bool = False
) -> OptimizationReport:
    """
    Полный пайплайн оптимизации.
    
    ЭТАПЫ:
    1. Запуск бенчмарка
    2. Если accuracy < target → анализ логов
    3. Генерация предложений
    4. A/B тестирование
    5. Внедрение в прод
    
    ARGS:
        capability: название способности
        target_accuracy: целевая точность
        max_ab_iterations: максимум итераций A/B
        benchmark_size: размер бенчмарка
        ab_test_size: размер A/B выборки
        dry_run: тестовый режим
        verbose: подробный вывод
    
    RETURNS:
        OptimizationReport: отчёт об оптимизации
    """
    print(f"\n{'='*70}")
    print("🚀 АВТОМАТИЧЕСКАЯ ОПТИМИЗАЦИЯ ПРОМПТОВ")
    print(f"{'='*70}")
    print(f"Capability: {capability}")
    print(f"Целевая точность: {target_accuracy:.0%}")
    print(f"Максимум итераций: {max_ab_iterations}")
    print(f"Dry run: {dry_run}")
    print(f"{'='*70}")
    
    initial_accuracy = 0.0
    final_accuracy = 0.0
    ab_test_passed = False
    prompt_deployed = False
    
    # === ЭТАП 1: Бенчмарк ===
    benchmark_result = await run_benchmark(capability, benchmark_size)
    initial_accuracy = benchmark_result.success_rate
    
    # Проверка: достигнута ли целевая точность?
    if initial_accuracy >= target_accuracy:
        print(f"\n✅ Целевая точность достигнута: {initial_accuracy:.1%} >= {target_accuracy:.1%}")
        print("Оптимизация не требуется")
        
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
    proposal = await analyze_logs(capability, benchmark_result)
    
    # === ЭТАП 3: A/B тестирование (до max_iterations) ===
    best_ab_result = None
    
    for iteration in range(1, max_ab_iterations + 1):
        print(f"\n{'='*60}")
        print(f"Итерация A/B тестирования {iteration}/{max_ab_iterations}")
        print(f"{'='*60}")
        
        ab_result = await run_ab_test(capability, proposal, ab_test_size)
        
        if ab_result.winner == "B" and ab_result.statistical_significance:
            best_ab_result = ab_result
            ab_test_passed = True
            print(f"\n✅ A/B тест пройден на итерации {iteration}")
            break
        else:
            print(f"\n⚠️  A/B тест не пройден, пробуем ещё раз...")
            # В реальной реализации здесь была бы генерация новой версии промпта
    
    if not ab_test_passed:
        print(f"\n❌ A/B тестирование не удалось после {max_ab_iterations} итераций")
        
        return OptimizationReport(
            capability=capability,
            timestamp=datetime.now().isoformat(),
            initial_accuracy=initial_accuracy,
            final_accuracy=initial_accuracy,
            target_accuracy=target_accuracy,
            target_achieved=False,
            ab_test_passed=False,
            prompt_deployed=False,
            improvements={}
        )
    
    # === ЭТАП 4: Внедрение в прод ===
    prompt_deployed = await deploy_prompt(capability, best_ab_result, dry_run)
    
    # Финальный бенчмарк для подтверждения
    if prompt_deployed:
        print(f"\n{'='*60}")
        print("Финальная проверка качества")
        print(f"{'='*60}")
        final_benchmark = await run_benchmark(capability, benchmark_size)
        final_accuracy = final_benchmark.success_rate
    else:
        final_accuracy = initial_accuracy
    
    # === Отчёт ===
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
        improvements=improvements
    )
    
    # Вывод отчёта
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
    
    if report.improvements:
        print(f"\n📈 Улучшения:")
        for metric, value in report.improvements.items():
            print(f"   {metric}: {value}")
    
    print(f"{'='*70}")
    
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
            ab_test_size=args.ab_test_size,
            dry_run=args.dry_run,
            verbose=args.verbose
        )
        
        # Сохранение отчёта
        if args.output:
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(asdict(report), f, indent=2, ensure_ascii=False)
            print(f"\n✅ Отчёт сохранён в {args.output}")
        
        # Exit code
        if report.target_achieved and report.prompt_deployed:
            sys.exit(0)
        elif report.ab_test_passed:
            sys.exit(1)  # Частичный успех
        else:
            sys.exit(2)  # Не удалось
            
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
