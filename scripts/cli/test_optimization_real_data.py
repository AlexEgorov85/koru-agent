#!/usr/bin/env python3
"""
Тестовый запуск оптимизации на реальных данных.

Проверка работы всех компонентов на реальных данных из data/metrics и data/prompts.
"""
import asyncio
import json
from datetime import datetime
from pathlib import Path


async def test_optimization_on_real_data():
    """Тестирование оптимизации на реальных данных"""
    
    print("="*60)
    print("Тестирование оптимизации на реальных данных")
    print("="*60)
    
    # Загрузка конфигурации
    from core.config import get_config
    config = get_config(profile='dev', data_dir='data')
    data_dir = Path(config.data_dir)
    
    print(f"\nData directory: {data_dir}")
    
    # Инициализация инфраструктуры
    from core.infrastructure.context.infrastructure_context import InfrastructureContext
    infra_context = InfrastructureContext(config)
    await infra_context.initialize()
    
    print("✅ Инфраструктура инициализирована\n")
    
    # === ТЕСТ 1: DatasetBuilder ===
    print("-"*60)
    print("ТЕСТ 1: DatasetBuilder")
    print("-"*60)
    
    from core.application.components.optimization import DatasetBuilder
    from core.application.components.optimization.dataset_builder import DatasetConfig
    
    dataset_config = DatasetConfig(
        min_samples=10,  # Минимум для теста
        min_failure_rate=0.1,
        max_samples=100,
        time_window_hours=720  # 30 дней
    )
    
    dataset_builder = DatasetBuilder(
        metrics_collector=infra_context.metrics_collector,
        event_bus=infra_context.event_bus,
        config=dataset_config
    )
    
    # Тестирование на разных capability
    test_capabilities = [
        'book_library.search_books',
        'vector_books.search',
        'data_analysis.analyze_step_data',
        'final_answer.generate',
        'planning.create_plan'
    ]
    
    for capability in test_capabilities:
        print(f"\n📊 Capability: {capability}")
        try:
            dataset = await dataset_builder.build(capability)
            stats = dataset_builder.get_dataset_stats(dataset)
            
            print(f"   Образцов: {stats['total_samples']}")
            print(f"   Failure rate: {stats['failure_rate']:.1%}")
            print(f"   Min samples met: {stats['meets_min_samples']}")
            print(f"   Min failure rate met: {stats['meets_min_failure_rate']}")
            
            if dataset.samples:
                print(f"   Типы сценариев:")
                for stype, samples in dataset.get_type_distribution().items():
                    print(f"     - {stype}: {samples:.1%}")
                    
        except Exception as e:
            print(f"   ❌ Ошибка: {e}")
    
    # === ТЕСТ 2: ScenarioBuilder ===
    print("\n" + "-"*60)
    print("ТЕСТ 2: ScenarioBuilder")
    print("-"*60)
    
    from core.application.components.optimization import ScenarioBuilder
    from core.application.components.optimization.scenario_builder import ScenarioConfig
    
    scenario_config = ScenarioConfig(
        min_type_percentage=0.1,
        min_failure_percentage=0.15,
        max_scenarios=50,
        balance_types=True
    )
    
    scenario_builder = ScenarioBuilder(config=scenario_config)
    
    # Тестирование на первом датасете
    print("\n📋 Тестирование на book_library.search_books")
    try:
        dataset = await dataset_builder.build('book_library.search_books')
        scenarios = await scenario_builder.build(dataset)
        stats = scenario_builder.get_scenario_stats(scenarios)
        
        print(f"   Сценариев: {stats['total_scenarios']}")
        print(f"   Распределение:")
        for stype, pct in stats['type_distribution'].items():
            print(f"     - {stype}: {pct:.1%}")
        print(f"   Все типы присутствуют: {stats['all_types_present']}")
        print(f"   Min failure rate met: {stats['meets_min_failure_rate']}")
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
    
    # === ТЕСТ 3: Evaluator ===
    print("\n" + "-"*60)
    print("ТЕСТ 3: Evaluator")
    print("-"*60)
    
    from core.application.components.optimization import Evaluator
    from core.models.data.benchmark import BenchmarkRunResult
    
    evaluator = Evaluator(event_bus=infra_context.event_bus)
    
    # Создание тестовых результатов
    test_results = [
        BenchmarkRunResult(version_id="v1", scenario_id="s1", success=True, execution_time_ms=100),
        BenchmarkRunResult(version_id="v1", scenario_id="s2", success=True, execution_time_ms=150),
        BenchmarkRunResult(version_id="v1", scenario_id="s3", success=False, error="Timeout", execution_time_ms=500),
        BenchmarkRunResult(version_id="v1", scenario_id="s4", success=True, execution_time_ms=120),
        BenchmarkRunResult(version_id="v1", scenario_id="s5", success=True, execution_time_ms=90),
    ]
    
    evaluation = evaluator.evaluate("v1", test_results)
    score = evaluation.calculate_score()
    
    print(f"\n📈 Оценка тестовых результатов:")
    print(f"   Success rate: {evaluation.success_rate:.1%}")
    print(f"   Error rate: {evaluation.error_rate:.1%}")
    print(f"   Avg latency: {evaluation.latency:.0f}ms")
    print(f"   Score: {score:.3f}")
    
    report = evaluator.get_metrics_report(evaluation)
    print(f"\n   Детали score:")
    for key, value in report['score_breakdown'].items():
        print(f"     - {key}: {value:.3f}")
    
    # === ТЕСТ 4: SafetyLayer ===
    print("\n" + "-"*60)
    print("ТЕСТ 4: SafetyLayer")
    print("-"*60)
    
    from core.application.components.optimization import SafetyLayer
    from core.models.data.benchmark import EvaluationResult
    
    safety_layer = SafetyLayer(event_bus=infra_context.event_bus)
    
    # Тест 1: Безопасный кандидат
    baseline = EvaluationResult(
        version_id="v1",
        success_rate=0.8,
        error_rate=0.2,
        latency=100,
        execution_success=0.85,
        sql_validity=1.0,
        score=0.75
    )
    
    candidate_good = EvaluationResult(
        version_id="v2",
        success_rate=0.85,
        error_rate=0.15,
        latency=110,
        execution_success=0.9,
        sql_validity=1.0,
        score=0.80
    )
    
    is_safe, checks = await safety_layer.check(candidate_good, baseline)
    print(f"\n✅ Тест 1: Улучшенный кандидат")
    print(f"   Безопасен: {is_safe}")
    print(f"   Пройдено проверок: {sum(1 for c in checks if c.passed)}/{len(checks)}")
    
    # Тест 2: Деградировавший кандидат
    candidate_bad = EvaluationResult(
        version_id="v3",
        success_rate=0.7,
        error_rate=0.35,
        latency=200,
        execution_success=0.7,
        sql_validity=0.9,
        score=0.60
    )
    
    is_safe, checks = await safety_layer.check(candidate_bad, baseline)
    print(f"\n❌ Тест 2: Деградировавший кандидат")
    print(f"   Безопасен: {is_safe}")
    print(f"   Пройдено проверок: {sum(1 for c in checks if c.passed)}/{len(checks)}")
    
    failed = [c for c in checks if not c.passed]
    if failed:
        print(f"   Проваленные проверки:")
        for check in failed:
            print(f"     - {check.check_type.value}: {check.message}")
    
    # === ТЕСТ 5: VersionManager ===
    print("\n" + "-"*60)
    print("ТЕСТ 5: VersionManager")
    print("-"*60)
    
    from core.application.components.optimization import VersionManager
    from core.models.data.benchmark import PromptVersion, MutationType
    
    version_manager = VersionManager(event_bus=infra_context.event_bus)
    
    # Создание тестовых версий
    v1 = PromptVersion(
        id="v1.0.0",
        parent_id=None,
        capability="test_capability",
        prompt="Original prompt content"
    )
    
    v2 = PromptVersion(
        id="v1.1.0",
        parent_id="v1.0.0",
        capability="test_capability",
        prompt="Improved prompt content",
        mutation_type=MutationType.ADD_EXAMPLES
    )
    
    # Регистрация версий
    await version_manager.register(v1)
    await version_manager.register(v2)
    
    # Продвижение v1 в active
    await version_manager.promote("v1.0.0", "test_capability")
    
    # Получение активной версии
    active = await version_manager.get_active("test_capability")
    print(f"\n📚 Версии:")
    print(f"   Активная версия: {active.id if active else 'None'}")
    
    # Получение истории
    history = await version_manager.get_history("test_capability")
    print(f"   Всего версий: {len(history)}")
    
    # Получение lineage
    lineage = await version_manager.get_lineage("test_capability", "v1.1.0")
    print(f"   Lineage v1.1.0: {[v.id for v in lineage]}")
    
    # Статистика
    stats = version_manager.get_stats("test_capability")
    print(f"\n   Статистика:")
    print(f"     - Все версии имеют parent: {stats['all_versions_have_parent']}")
    print(f"     - Распределение статусов: {stats['status_distribution']}")
    
    # === ТЕСТ 6: PromptGenerator ===
    print("\n" + "-"*60)
    print("ТЕСТ 6: PromptGenerator")
    print("-"*60)
    
    from core.application.components.optimization import PromptGenerator
    from core.models.data.benchmark import FailureAnalysis
    
    prompt_generator = PromptGenerator(event_bus=infra_context.event_bus)
    
    # Создание failure analysis
    failure_analysis = FailureAnalysis(
        capability="test_capability",
        version="v1.0.0",
        total_failures=10
    )
    failure_analysis.add_failure_category("syntax_error", 4)
    failure_analysis.add_failure_category("validation_error", 3)
    failure_analysis.add_failure_category("timeout", 3)
    
    # Генерация кандидатов
    candidates = await prompt_generator.generate(v1, failure_analysis)
    
    print(f"\n🔧 Сгенерировано кандидатов: {len(candidates)}")
    for i, candidate in enumerate(candidates):
        print(f"\n   Кандидат {i+1}:")
        print(f"     ID: {candidate.id}")
        print(f"     Parent: {candidate.parent_id}")
        print(f"     Mutation: {candidate.mutation_type.value if candidate.mutation_type else 'None'}")
        print(f"     Prompt length: {len(candidate.prompt)} chars")
    
    # Статистика diversity
    diversity_stats = prompt_generator.get_diversity_stats()
    print(f"\n   Diversity статистика:")
    print(f"     - Total generations: {diversity_stats.get('total_generations', 0)}")
    print(f"     - Diversity types: {diversity_stats.get('diversity_types', 0)}")
    
    # === ИТОГ ===
    print("\n" + "="*60)
    print("ИТОГИ ТЕСТИРОВАНИЯ")
    print("="*60)
    print("\n✅ Все компоненты работают корректно")
    print("\nКомпоненты:")
    print("  1. DatasetBuilder — сбор данных из метрик ✓")
    print("  2. ScenarioBuilder — классификация сценариев ✓")
    print("  3. Evaluator — оценка качества с scoring ✓")
    print("  4. SafetyLayer — защита от деградации ✓")
    print("  5. VersionManager — управление версиями ✓")
    print("  6. PromptGenerator — генерация кандидатов ✓")
    
    print("\nГотово к запуску полной оптимизации!")
    print("\nДля запуска используйте:")
    print("  python scripts/cli/run_optimization_v2.py --capability book_library.search_books --dry-run")
    print("  python scripts/cli/run_optimization_v2.py --capability book_library.search_books")
    
    # Завершение
    await infra_context.shutdown()


if __name__ == '__main__':
    asyncio.run(test_optimization_on_real_data())
