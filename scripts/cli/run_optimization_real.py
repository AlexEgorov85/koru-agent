#!/usr/bin/env python3
"""
Запуск оптимизации v2 на реальных логах.

Использование:
    py -m scripts.cli.run_optimization_real
"""
import asyncio
import json
from datetime import datetime
from pathlib import Path


async def main():
    """Запуск оптимизации на реальных логах"""
    
    print("="*60)
    print("Оптимизация v2 — запуск на реальных логах")
    print("="*60)
    
    # Импорты
    from core.config import get_config
    from core.infrastructure.context.infrastructure_context import InfrastructureContext
    from core.application.context.application_context import ApplicationContext
    from core.application.components.optimization import (
        TraceHandler,
        TraceCollector,
        PatternAnalyzer,
        PromptResponseAnalyzer,
        RootCauseAnalyzer,
        ExampleExtractor,
        DatasetBuilder,
        OptimizationOrchestrator,
        ScenarioBuilder,
        BenchmarkRunner,
        Evaluator,
        PromptGenerator,
        VersionManager,
        SafetyLayer,
    )
    
    # Загрузка конфигурации
    config = get_config(profile='dev', data_dir='data')
    data_dir = Path(config.data_dir)
    
    print(f"\nData directory: {data_dir}")
    
    # Инициализация инфраструктуры
    print("\n🔄 Инициализация инфраструктуры...")
    infra_context = InfrastructureContext(config)
    await infra_context.initialize()
    
    print("✅ InfrastructureContext инициализирован")
    
    # Создание application context
    app_context = ApplicationContext(
        infrastructure_context=infra_context,
        config=config,
        profile='dev'
    )
    await app_context.initialize()
    
    print("✅ ApplicationContext инициализирован")
    
    # === СОЗДАНИЕ КОМПОНЕНТОВ ===
    print("\n🔧 Создание компонентов оптимизации...")
    
    event_bus = infra_context.event_bus
    
    # 1. TraceHandler
    trace_handler = TraceHandler(
        session_handler=infra_context.session_handler,
        logs_dir=str(data_dir / 'logs')
    )
    print("  ✅ TraceHandler")
    
    # 2. TraceCollector
    trace_collector = TraceCollector(trace_handler)
    print("  ✅ TraceCollector")
    
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
    print("  ✅ ExampleExtractor")
    
    # 7. DatasetBuilder
    dataset_builder = DatasetBuilder(trace_collector, event_bus)
    print("  ✅ DatasetBuilder")
    
    # 8. ScenarioBuilder
    scenario_builder = ScenarioBuilder()
    print("  ✅ ScenarioBuilder")
    
    # 9. BenchmarkRunner
    async def mock_executor(input_text: str, version_id: str) -> dict:
        """Mock executor для тестирования"""
        return {
            'success': True,
            'output': f'Mock output for {input_text[:50]}',
            'execution_time_ms': 100,
            'tokens_used': 50
        }
    
    benchmark_runner = BenchmarkRunner(
        event_bus=event_bus,
        executor_callback=mock_executor
    )
    print("  ✅ BenchmarkRunner")
    
    # 10. Evaluator
    evaluator = Evaluator(event_bus=event_bus)
    print("  ✅ Evaluator")
    
    # 11. PromptGenerator
    prompt_generator = PromptGenerator(event_bus=event_bus)
    print("  ✅ PromptGenerator")
    
    # 12. VersionManager
    version_manager = VersionManager(event_bus=event_bus)
    print("  ✅ VersionManager")
    
    # 13. SafetyLayer
    safety_layer = SafetyLayer(event_bus=event_bus)
    print("  ✅ SafetyLayer")
    
    # 14. OptimizationOrchestrator
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
        event_bus=event_bus
    )
    orchestrator.set_executor_callback(mock_executor)
    print("  ✅ OptimizationOrchestrator")
    
    # === АНАЛИЗ ДОСТУПНЫХ ЛОГОВ ===
    print("\n📊 Анализ доступных сессий...")
    
    sessions_dir = data_dir / 'logs' / 'sessions'
    if sessions_dir.exists():
        sessions = sorted(sessions_dir.iterdir(), reverse=True)
        print(f"  Найдено сессий: {len(sessions)}")
        
        # Показываем последние 5
        print("\n  Последние 5 сессий:")
        for session in sessions[:5]:
            print(f"    - {session.name}")
    else:
        print("  ❌ Директория с сессиями не найдена")
        return
    
    # === ТЕСТИРОВАНИЕ НА РЕАЛЬНЫХ ДАННЫХ ===
    print("\n" + "="*60)
    print("ТЕСТИРОВАНИЕ НА РЕАЛЬНЫХ ДАННЫХ")
    print("="*60)
    
    # Тест 1: Сбор traces
    print("\n📋 ТЕСТ 1: Сбор execution traces...")
    
    # Попробуем собрать traces для всех сессий
    all_traces = []
    for session in sessions[:10]:  # Берём последние 10 сессий
        trace = await trace_handler.get_execution_trace(session.name)
        if trace:
            all_traces.append(trace)
            print(f"  ✅ {session.name}: {trace.step_count} шагов, success={trace.success}")
    
    print(f"\n  Всего собрано traces: {len(all_traces)}")
    
    if not all_traces:
        print("\n  ⚠️  Не удалось собрать traces из логов")
        print("  Возможно логи имеют другой формат")
        return
    
    # Тест 2: Анализ паттернов
    print("\n📋 ТЕСТ 2: Анализ паттернов...")
    patterns = pattern_analyzer.analyze(all_traces)
    pattern_stats = pattern_analyzer.get_pattern_stats(patterns)
    print(f"  Найдено паттернов: {pattern_stats['total_patterns']}")
    
    if patterns:
        print("\n  Обнаруженные паттерны:")
        for pattern in patterns[:5]:
            print(f"    - {pattern.type.value}: {pattern.description[:60]}...")
            print(f"      Частота: {pattern.frequency}, Серьёзность: {pattern.severity}")
    
    # Тест 3: Анализ промптов и ответов
    print("\n📋 ТЕСТ 3: Анализ промптов и ответов...")
    prompt_issues = prompt_analyzer.analyze_prompts(all_traces)
    response_issues = prompt_analyzer.analyze_responses(all_traces)
    analysis_stats = prompt_analyzer.get_analysis_stats(prompt_issues, response_issues)
    
    print(f"  Проблем промптов: {analysis_stats['total_prompt_issues']}")
    print(f"  Проблем ответов: {analysis_stats['total_response_issues']}")
    
    # Тест 4: Поиск корневых причин
    print("\n📋 ТЕСТ 4: Поиск корневых причин...")
    root_causes = root_cause_analyzer.analyze(patterns, prompt_issues, response_issues)
    cause_stats = root_cause_analyzer.get_root_cause_stats(root_causes)
    
    print(f"  Найдено корневых причин: {cause_stats['total_root_causes']}")
    
    if root_causes:
        print("\n  Топ корневых причин:")
        for rc in root_causes[:5]:
            print(f"    - {rc.problem[:50]}...")
            print(f"      Причина: {rc.cause[:50]}...")
            print(f"      Решение: {rc.fix[:50]}...")
            print(f"      Приоритет: {rc.priority.value}")
    
    # Тест 5: Извлечение примеров
    print("\n📋 ТЕСТ 5: Извлечение примеров...")
    
    # Собираем все capability из traces
    all_capabilities = set()
    for trace in all_traces:
        all_capabilities.update(trace.get_capabilities_used())
    
    print(f"  Найдено capability: {len(all_capabilities)}")
    
    # Для каждого capability извлекаем примеры
    for capability in list(all_capabilities)[:3]:  # Берём первые 3
        print(f"\n  Capability: {capability}")
        
        good_examples, error_examples = example_extractor.extract_few_shot_examples(
            all_traces,
            capability=capability,
            num_good=2,
            num_bad=1
        )
        
        print(f"    Хороших примеров: {len(good_examples)}")
        print(f"    Примеров ошибок: {len(error_examples)}")
        
        if good_examples:
            print(f"    Пример хорошего:")
            print(f"      Input: {good_examples[0].input[:50]}...")
            print(f"      Steps: {good_examples[0].steps}, Time: {good_examples[0].time_ms/1000:.1f}s")
    
    # Тест 6: DatasetBuilder
    print("\n📋 ТЕСТ 6: DatasetBuilder...")
    
    # Создаём mock dataset из traces
    from core.models.data.benchmark import BenchmarkDataset, OptimizationSample
    import uuid
    
    dataset = BenchmarkDataset(
        id=str(uuid.uuid4()),
        capability="test_capability"
    )
    
    for trace in all_traces[:10]:
        sample = OptimizationSample(
            id=trace.session_id,
            input=trace.goal,
            context={
                'steps': trace.step_count,
                'total_time_ms': trace.total_time_ms,
                'capabilities_used': trace.get_capabilities_used()
            },
            actual_output=trace.final_answer,
            success=trace.success,
            error=trace.error
        )
        dataset.add_sample(sample)
    
    print(f"  Создан датасет: {dataset.size} образцов")
    print(f"  Failure rate: {dataset.failure_rate:.1%}")
    
    # === ИТОГОВЫЙ ОТЧЁТ ===
    print("\n" + "="*60)
    print("ИТОГОВЫЙ ОТЧЁТ")
    print("="*60)
    
    report = {
        'timestamp': datetime.now().isoformat(),
        'sessions_analyzed': len(sessions[:10]),
        'traces_collected': len(all_traces),
        'patterns_found': pattern_stats['total_patterns'],
        'prompt_issues': analysis_stats['total_prompt_issues'],
        'response_issues': analysis_stats['total_response_issues'],
        'root_causes': cause_stats['total_root_causes'],
        'capabilities_found': len(all_capabilities),
        'dataset_samples': dataset.size
    }
    
    print(json.dumps(report, indent=2, ensure_ascii=False))
    
    print("\n✅ Тестирование завершено успешно!")
    print("\nДля полноценной оптимизации используйте:")
    print("  orchestrator.optimize(capability='your_capability')")
    
    # Завершение
    await app_context.shutdown()
    await infra_context.shutdown()


if __name__ == '__main__':
    asyncio.run(main())
