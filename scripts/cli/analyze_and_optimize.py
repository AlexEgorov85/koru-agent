#!/usr/bin/env python3
"""
Автономный запуск сервиса оптимизации v2.

Анализирует логи, находит проблемы, генерирует рекомендации.

Использование:
    py scripts/cli/analyze_and_optimize.py
"""
import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List


async def main():
    """Автономный запуск оптимизации"""
    
    print("="*70)
    print("СЕРВИС ОПТИМИЗАЦИИ V2 — АВТОНОМНЫЙ ЗАПУСК")
    print("="*70)
    print(f"Время запуска: {datetime.now().isoformat()}")
    
    # === ИНИЦИАЛИЗАЦИЯ ===
    from core.config import get_config
    from core.infrastructure.context.infrastructure_context import InfrastructureContext
    from core.application.context.application_context import ApplicationContext
    from core.application.components.optimization import (
        TraceHandler, TraceCollector,
        PatternAnalyzer, PromptResponseAnalyzer, RootCauseAnalyzer,
        ExampleExtractor,
        OptimizationOrchestrator,
        ScenarioBuilder, BenchmarkRunner, Evaluator,
        PromptGenerator, VersionManager, SafetyLayer
    )
    
    config = get_config(profile='dev', data_dir='data')
    data_dir = Path(config.data_dir)
    
    print(f"\n📂 Data directory: {data_dir}")
    
    # Инициализация инфраструктуры
    print("\n🔄 Инициализация инфраструктуры...")
    infra = InfrastructureContext(config)
    await infra.initialize()
    
    app = ApplicationContext(infrastructure_context=infra, config=config, profile='dev')
    await app.initialize()
    
    print("✅ Инфраструктура готова")
    
    # === СОЗДАНИЕ КОМПОНЕНТОВ ===
    print("\n🔧 Создание компонентов...")
    
    event_bus = infra.event_bus
    
    # Mock executor для тестирования
    async def mock_executor(input_text: str, version_id: str) -> dict:
        return {
            'success': True,
            'output': f'Mock: {input_text[:30]}...',
            'execution_time_ms': 100,
            'tokens_used': 50
        }
    
    trace_handler = TraceHandler(
        session_handler=infra.session_handler,
        logs_dir=str(data_dir / 'logs')
    )
    trace_collector = TraceCollector(trace_handler)
    pattern_analyzer = PatternAnalyzer()
    prompt_analyzer = PromptResponseAnalyzer()
    root_cause_analyzer = RootCauseAnalyzer()
    example_extractor = ExampleExtractor()
    
    scenario_builder = ScenarioBuilder()
    benchmark_runner = BenchmarkRunner(event_bus, mock_executor)
    evaluator = Evaluator(event_bus)
    prompt_generator = PromptGenerator(event_bus)
    version_manager = VersionManager(event_bus)
    safety_layer = SafetyLayer(event_bus)
    
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
    
    print("✅ Компоненты созданы")
    
    # === АНАЛИЗ ЛОГОВ ===
    print("\n" + "="*70)
    print("ЭТАП 1: АНАЛИЗ ЛОГОВ")
    print("="*70)
    
    sessions_dir = data_dir / 'logs' / 'sessions'
    sessions = sorted(sessions_dir.iterdir(), reverse=True)[:10] if sessions_dir.exists() else []
    
    print(f"\n📊 Найдено сессий: {len(sessions)}")
    
    # Сбор traces
    all_traces = []
    for session in sessions:
        trace = await trace_handler.get_execution_trace(session.name)
        if trace and trace.step_count > 0:
            all_traces.append(trace)
            print(f"  ✅ {session.name}: {trace.step_count} шагов, success={trace.success}")
    
    print(f"\n📈 Всего traces с шагами: {len(all_traces)}")
    
    if not all_traces:
        print("\n⚠️  Не найдено traces с шагами. Завершение.")
        await cleanup(app, infra)
        return
    
    # === АНАЛИЗ ПАТТЕРНОВ ===
    print("\n" + "="*70)
    print("ЭТАП 2: АНАЛИЗ ПАТТЕРНОВ")
    print("="*70)
    
    patterns = pattern_analyzer.analyze(all_traces)
    pattern_stats = pattern_analyzer.get_pattern_stats(patterns)
    
    print(f"\n📊 Найдено паттернов: {pattern_stats['total_patterns']}")
    
    if patterns:
        print("\n🔍 Обнаруженные паттерны:")
        for i, pattern in enumerate(patterns, 1):
            print(f"\n  {i}. {pattern.type.value}")
            print(f"     Описание: {pattern.description[:80]}...")
            print(f"     Частота: {pattern.frequency}")
            print(f"     Серьёзность: {pattern.severity}")
            print(f"     Затронутые capability: {pattern.affected_capabilities}")
            print(f"     Рекомендация: {pattern.recommendation[:60]}...")
    
    # === АНАЛИЗ ПРОМПТОВ И ОТВЕТОВ ===
    print("\n" + "="*70)
    print("ЭТАП 3: АНАЛИЗ ПРОМПТОВ И ОТВЕТОВ")
    print("="*70)
    
    prompt_issues = prompt_analyzer.analyze_prompts(all_traces)
    response_issues = prompt_analyzer.analyze_responses(all_traces)
    analysis_stats = prompt_analyzer.get_analysis_stats(prompt_issues, response_issues)
    
    print(f"\n📊 Проблем промптов: {analysis_stats['total_prompt_issues']}")
    print(f"📊 Проблем ответов: {analysis_stats['total_response_issues']}")
    print(f"📊 Критических/высоких: {analysis_stats['critical_high_count']}")
    
    if prompt_issues:
        print("\n⚠️  Проблемы промптов:")
        for issue in prompt_issues[:3]:
            print(f"\n  • {issue.issue_type}")
            print(f"    Capability: {issue.capability}")
            print(f"    Описание: {issue.description[:60]}...")
            print(f"    Решение: {issue.suggestion[:60]}...")
    
    if response_issues:
        print("\n⚠️  Проблемы ответов:")
        for issue in response_issues[:3]:
            print(f"\n  • {issue.issue_type}")
            print(f"    Capability: {issue.capability}")
            print(f"    Описание: {issue.description[:60]}...")
    
    # === ПОИСК КОРНЕВЫХ ПРИЧИН ===
    print("\n" + "="*70)
    print("ЭТАП 4: ПОИСК КОРНЕВЫХ ПРИЧИН")
    print("="*70)
    
    root_causes = root_cause_analyzer.analyze(patterns, prompt_issues, response_issues)
    cause_stats = root_cause_analyzer.get_root_cause_stats(root_causes)
    
    print(f"\n📊 Найдено корневых причин: {cause_stats['total_root_causes']}")
    print(f"📊 Критических/высоких: {cause_stats['critical_high_count']}")
    
    if root_causes:
        print("\n🎯 Топ корневых причин:")
        for i, rc in enumerate(root_causes[:5], 1):
            print(f"\n  {i}. {rc.problem[:60]}...")
            print(f"     Причина: {rc.cause[:60]}...")
            print(f"     Решение: {rc.fix[:60]}...")
            print(f"     Приоритет: {rc.priority.value}")
            if rc.affected_capabilities:
                print(f"     Capability: {rc.affected_capabilities[0]}")
    
    # === ИЗВЛЕЧЕНИЕ ПРИМЕРОВ ===
    print("\n" + "="*70)
    print("ЭТАП 5: ИЗВЛЕЧЕНИЕ ПРИМЕРОВ")
    print("="*70)
    
    # Сбор всех capability
    all_capabilities = set()
    for trace in all_traces:
        all_capabilities.update(trace.get_capabilities_used())
    
    print(f"\n📊 Найдено capability: {len(all_capabilities)}")
    print(f"   Список: {', '.join(all_capabilities)}")
    
    # Извлечение примеров для каждого capability
    examples_by_capability = {}
    for capability in all_capabilities:
        good, bad = example_extractor.extract_few_shot_examples(
            all_traces,
            capability=capability,
            num_good=3,
            num_bad=2
        )
        examples_by_capability[capability] = {'good': len(good), 'bad': len(bad)}
        
        if good:
            print(f"\n  ✅ {capability}: {len(good)} хороших примеров")
            for ex in good[:1]:
                print(f"     Пример: steps={ex.steps}, time={ex.time_ms/1000:.1f}s")
    
    # === ГЕНЕРАЦИЯ РЕКОМЕНДАЦИЙ ===
    print("\n" + "="*70)
    print("ЭТАП 6: ГЕНЕРАЦИЯ РЕКОМЕНДАЦИЙ")
    print("="*70)
    
    recommendations = root_cause_analyzer.get_fix_recommendations(root_causes, limit=10)
    
    print(f"\n📋 Сгенерировано рекомендаций: {len(recommendations)}")
    
    if recommendations:
        print("\n🎯 Топ рекомендаций по исправлению:")
        for i, rec in enumerate(recommendations[:5], 1):
            print(f"\n  {i}. [{rec['priority'].upper()}] {rec['capability']}")
            print(f"     Проблема: {rec['problem'][:60]}...")
            print(f"     Решение: {rec['fix']}")
    
    # === ИТОГОВЫЙ ОТЧЁТ ===
    print("\n" + "="*70)
    print("ИТОГОВЫЙ ОТЧЁТ")
    print("="*70)
    
    report = {
        'timestamp': datetime.now().isoformat(),
        'sessions_analyzed': len(sessions),
        'traces_with_steps': len(all_traces),
        'total_steps': sum(t.step_count for t in all_traces),
        'patterns': {
            'total': pattern_stats['total_patterns'],
            'by_severity': pattern_stats.get('by_severity', {}),
            'types': [p.type.value for p in patterns]
        },
        'issues': {
            'prompt_issues': analysis_stats['total_prompt_issues'],
            'response_issues': analysis_stats['total_response_issues'],
            'critical_high': analysis_stats['critical_high_count']
        },
        'root_causes': {
            'total': cause_stats['total_root_causes'],
            'critical_high': cause_stats['critical_high_count']
        },
        'examples': examples_by_capability,
        'recommendations_count': len(recommendations)
    }
    
    print("\n" + json.dumps(report, indent=2, ensure_ascii=False))
    
    # Сохранение отчёта
    report_file = data_dir / 'optimization_report.json'
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 Отчёт сохранён: {report_file}")
    
    # === АНАЛИЗ ОШИБОК ===
    print("\n" + "="*70)
    print("АНАЛИЗ ОШИБОК")
    print("="*70)
    
    errors_found = []
    
    # Проверка на критические проблемы
    if cause_stats['critical_high_count'] > 0:
        errors_found.append({
            'type': 'CRITICAL_ROOT_CAUSES',
            'count': cause_stats['critical_high_count'],
            'message': f"Найдено {cause_stats['critical_high_count']} критических/высоких проблем"
        })
    
    # Проверка на повторяющиеся ошибки
    repeated_patterns = [p for p in patterns if p.type.value == 'repeated_retry' and p.frequency > 2]
    if repeated_patterns:
        errors_found.append({
            'type': 'REPEATED_RETRIES',
            'count': len(repeated_patterns),
            'message': f"Обнаружены повторяющиеся retry ({sum(p.frequency for p in repeated_patterns)} раз)"
        })
    
    # Проверка на циклические зависимости
    circular = [p for p in patterns if p.type.value == 'circular_dependency']
    if circular:
        errors_found.append({
            'type': 'CIRCULAR_DEPENDENCY',
            'count': len(circular),
            'message': "Обнаружены циклические вызовы способностей"
        })
    
    # Проверка на проблемы с ответами
    incomplete = [i for i in response_issues if i.issue_type == 'incomplete']
    if incomplete:
        errors_found.append({
            'type': 'INCOMPLETE_RESPONSES',
            'count': len(incomplete),
            'message': f"Найдено {len(incomplete)} неполных ответов LLM"
        })
    
    if errors_found:
        print(f"\n❌ Найдено проблем: {len(errors_found)}")
        for err in errors_found:
            print(f"\n  ⚠️  {err['type']}")
            print(f"     Количество: {err['count']}")
            print(f"     Описание: {err['message']}")
    else:
        print("\n✅ Критических ошибок не найдено")
    
    # === ЗАВЕРШЕНИЕ ===
    print("\n" + "="*70)
    print("ЗАВЕРШЕНИЕ")
    print("="*70)
    
    await cleanup(app, infra)
    
    print("\n✅ Анализ завершён успешно!")
    print(f"\n📊 Итого:")
    print(f"   - Проанализировано сессий: {len(sessions)}")
    print(f"   - Найдено traces: {len(all_traces)}")
    print(f"   - Найдено паттернов: {pattern_stats['total_patterns']}")
    print(f"   - Найдено проблем: {analysis_stats['total_prompt_issues'] + analysis_stats['total_response_issues']}")
    print(f"   - Найдено причин: {cause_stats['total_root_causes']}")
    print(f"   - Сгенерировано рекомендаций: {len(recommendations)}")
    print(f"   - Найдено ошибок: {len(errors_found)}")


async def cleanup(app, infra):
    """Завершение работы"""
    await app.shutdown()
    await infra.shutdown()


if __name__ == '__main__':
    asyncio.run(main())
