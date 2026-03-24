#!/usr/bin/env python3
"""
Автоматическая оптимизация промптов через LLM + A/B тестирование.

ПОЛНЫЙ ЦИКЛ:
1. Анализ логов → 2. LLM генерация → 3. A/B тест → 4. Продвижение версии

Использование:
    py scripts/cli/auto_optimize.py --capability final_answer.generate
"""
import asyncio
import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Optional


async def main():
    parser = argparse.ArgumentParser(description='Автоматическая оптимизация промптов')
    parser.add_argument('--capability', '-c', type=str, required=True,
                        help='Название способности для оптимизации')
    parser.add_argument('--focus', '-f', type=str, default='error_handling',
                        choices=['error_handling', 'clarity', 'examples', 'constraints'],
                        help='Фокус улучшения')
    parser.add_argument('--dry-run', action='store_true',
                        help='Тестовый режим без сохранения')
    args = parser.parse_args()

    print("="*70)
    print("АВТОМАТИЧЕСКАЯ ОПТИМИЗАЦИЯ ПРОМПТОВ")
    print("="*70)
    print(f"Capability: {args.capability}")
    print(f"Focus: {args.focus}")
    print(f"Dry run: {args.dry_run}")
    print()

    # === ИНИЦИАЛИЗАЦИЯ ===
    from core.config import get_config
    from core.infrastructure.context.infrastructure_context import InfrastructureContext
    from core.application.context.application_context import ApplicationContext
    from core.application.components.optimization import (
        TraceHandler, TraceCollector,
        PatternAnalyzer, PromptResponseAnalyzer, RootCauseAnalyzer,
        PromptImprover, ABTester, VersionPromoter
    )

    config = get_config(profile='dev', data_dir='data')
    
    print("🔄 Инициализация инфраструктуры...")
    infra = InfrastructureContext(config)
    await infra.initialize()
    
    app = ApplicationContext(infra, config, 'dev')
    await app.initialize()
    print("✅ Инфраструктура готова\n")

    # === ЭТАП 1: АНАЛИЗ ===
    print("="*70)
    print("ЭТАП 1: АНАЛИЗ ЛОГОВ")
    print("="*70)

    trace_handler = TraceHandler(infra.session_handler, str(Path('data/logs')))
    trace_collector = TraceCollector(trace_handler)
    
    traces = await trace_collector.collect_traces(args.capability)
    print(f"📊 Найдено traces: {len(traces)}")

    if not traces:
        print("❌ Нет данных для анализа")
        await cleanup(app, infra)
        return

    pattern_analyzer = PatternAnalyzer()
    patterns = pattern_analyzer.analyze(traces)
    print(f"📊 Найдено паттернов: {len(patterns)}")

    prompt_analyzer = PromptResponseAnalyzer()
    prompt_issues = prompt_analyzer.analyze_prompts(traces)
    print(f"📊 Проблем промптов: {len(prompt_issues)}")

    root_cause_analyzer = RootCauseAnalyzer()
    root_causes = root_cause_analyzer.analyze(patterns, prompt_issues, [])
    print(f"📊 Корневых причин: {len(root_causes)}")

    if not root_causes:
        print("✅ Проблем не найдено, оптимизация не требуется")
        await cleanup(app, infra)
        return

    # === ЭТАП 2: LLM ГЕНЕРАЦИЯ ===
    print("\n" + "="*70)
    print("ЭТАП 2: LLM ГЕНЕРАЦИЯ УЛУЧШЕНИЙ")
    print("="*70)

    # Загрузка текущего промпта
    from core.infrastructure.storage.file_system_data_source import FileSystemDataSource
    data_source = FileSystemDataSource(Path('data'))
    
    # Получение активной версии
    versions = await data_source.list_prompts(args.capability)
    if not versions:
        print(f"❌ Промпты для {args.capability} не найдены")
        await cleanup(app, infra)
        return

    # Берём последнюю версию
    current_version = versions[-1]
    current_prompt = await data_source.load_prompt(args.capability, current_version)
    
    print(f"📄 Текущая версия: {current_prompt.version}")

    # Генерация улучшения
    improver = PromptImprover(infra.llm_provider)
    
    improvement = await improver.improve(
        prompt=current_prompt,
        root_causes=[rc.to_dict() for rc in root_causes],
        improvement_focus=args.focus
    )

    print(f"✨ Улучшение сгенерировано:")
    print(f"   Тип: {improvement.improvement_type}")
    print(f"   Уверенность LLM: {improvement.confidence:.1%}")
    print(f"   Изменения: {', '.join(improvement.changes_made[:3])}")

    if args.dry_run:
        print("\n⚠️  DRY RUN: Сохранение пропущено")
        print(f"\n📄 Улучшенный промпт:\n{improvement.improved_prompt[:500]}...")
        await cleanup(app, infra)
        return

    # === ЭТАП 3: A/B ТЕСТИРОВАНИЕ ===
    print("\n" + "="*70)
    print("ЭТАП 3: A/B ТЕСТИРОВАНИЕ")
    print("="*70)

    # Создание новой версии
    from core.models.data.prompt import Prompt
    new_version_id = improver.generate_version_id(current_prompt, improvement)
    
    new_prompt = Prompt(
        capability=current_prompt.capability,
        version=new_version_id,
        content=improvement.improved_prompt,
        variables=current_prompt.variables,
        status='candidate',
        component_type=current_prompt.component_type
    )

    # Mock executor для A/B теста
    async def mock_executor(input_text: str, version_id: str) -> dict:
        # В реальности здесь был бы вызов LLM с разным промптом
        return {
            'success': True,
            'execution_time_ms': 100,
            'tokens_used': 50
        }

    # A/B тест
    tester = ABTester(mock_executor)
    
    # Mock тестовых данных
    test_data = [{'input': f'Test {i}'} for i in range(3)]
    
    ab_result = await tester.run_test(current_prompt, new_prompt, test_data)
    
    print(f"📊 Результаты A/B теста:")
    print(ab_result.details)
    print(f"\n🏆 Победитель: {ab_result.winner}")
    print(f"📈 Статистическая значимость: {ab_result.statistically_significant}")

    if ab_result.winner != 'B':
        print("\n❌ Новая версия не лучше, отмена")
        await cleanup(app, infra)
        return

    # === ЭТАП 4: ПРОДВИЖЕНИЕ ===
    print("\n" + "="*70)
    print("ЭТАП 4: ПРОДВИЖЕНИЕ ВЕРСИИ")
    print("="*70)

    promoter = VersionPromoter(data_source, Path('data/prompts'))
    
    success = await promoter.promote(
        prompt=new_prompt,
        reason=f"Auto-optimized: {args.focus}",
        metrics=ab_result.metrics_b,
        ab_test_result={
            'winner': ab_result.winner,
            'improvements': ab_result.improvements,
            'details': ab_result.details
        }
    )

    if success:
        print(f"✅ Версия {new_prompt.version} сохранена")
        print(f"📄 Файл: data/prompts/{args.capability.replace('.', '/')}/{new_prompt.version}.yaml")
    else:
        print(f"❌ Ошибка сохранения версии")

    # === ИТОГ ===
    print("\n" + "="*70)
    print("ИТОГ")
    print("="*70)

    report = {
        'timestamp': datetime.now().isoformat(),
        'capability': args.capability,
        'focus': args.focus,
        'from_version': current_prompt.version,
        'to_version': new_prompt.version if success else None,
        'root_causes_found': len(root_causes),
        'ab_test_winner': ab_result.winner,
        'improvements': ab_result.improvements,
        'success': success
    }

    # Сохранение отчёта
    report_file = Path('data/auto_optimization_report.json')
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"💾 Отчёт: {report_file}")
    print(json.dumps(report, indent=2, ensure_ascii=False))

    await cleanup(app, infra)


async def cleanup(app, infra):
    await app.shutdown()
    await infra.shutdown()


if __name__ == '__main__':
    asyncio.run(main())
