#!/usr/bin/env python3
"""
Запуск РЕАЛЬНОГО агента на бенчмарке.

Использование:
    # Запустить все тесты из бенчмарка
    py -m scripts.cli.run_real_agent_benchmark
    
    # Запустить один тест
    py -m scripts.cli.run_real_agent_benchmark --goal "Какие книги написал Пушкин?"
"""
import asyncio
import json
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any


async def main():
    parser = argparse.ArgumentParser(description='Запуск РЕАЛЬНОГО агента на бенчмарке')
    parser.add_argument('--benchmark', '-b', type=str, 
                        default='data/benchmarks/agent_benchmark.json',
                        help='Файл бенчмарка')
    parser.add_argument('--output', '-o', type=str,
                        default='data/benchmarks/real_benchmark_results.json',
                        help='Файл для результатов')
    parser.add_argument('--goal', '-g', type=str, default=None,
                        help='Один тестовый вопрос (если не указан — запускаются все тесты из бенчмарка)')
    args = parser.parse_args()

    print("="*70)
    print("ЗАПУСК РЕАЛЬНОГО АГЕНТА НА БЕНЧМАРКЕ")
    print("="*70)
    
    # Загрузка бенчмарка
    benchmark_path = Path(args.benchmark)
    if not benchmark_path.exists():
        print(f"❌ Бенчмарк не найден: {benchmark_path}")
        print("Сначала создайте бенчмарк: py -m scripts.cli.generate_agent_benchmark")
        return

    with open(benchmark_path, 'r', encoding='utf-8') as f:
        benchmark = json.load(f)

    if args.goal:
        # Запуск одного теста
        print(f"Goal: {args.goal}")
        print(f"Mode: SINGLE TEST\n")
        test_cases = [{'input': args.goal, 'id': 'single_test', 'name': 'Single Test'}]
    else:
        # Запуск всех тестов из бенчмарка
        print(f"Benchmark: {args.benchmark}")
        print(f"Mode: FULL BENCHMARK\n")
        
        sql_tests = benchmark['levels']['sql_generation']['test_cases']
        answer_tests = benchmark['levels']['final_answer']['test_cases']
        test_cases = sql_tests[:3] + answer_tests[:3]  # Первые 3 из каждого уровня
        
        print(f"📊 Загружено тестов:")
        print(f"   SQL Generation: {len(sql_tests)} (запускаем первые 3)")
        print(f"   Final Answer: {len(answer_tests)} (запускаем первые 3)")
        print()

    from core.config import get_config
    from core.infrastructure.context.infrastructure_context import InfrastructureContext
    from core.application.context.application_context import ApplicationContext
    from core.application.agent.factory import AgentFactory
    from core.config.agent_config import AgentConfig
    
    config = get_config(profile='dev', data_dir='data')
    
    print("🔄 Инициализация инфраструктуры...")
    infra = InfrastructureContext(config)
    await infra.initialize()
    
    app = ApplicationContext(infra, config, 'dev')
    await app.initialize()
    print("✅ Инфраструктура готова\n")

    # Создание фабрики агентов
    agent_factory = AgentFactory(app)

    # Запуск тестов
    print("="*70)
    print("ЗАПУСК ТЕСТОВ")
    print("="*70)

    results = {
        'run_at': datetime.now().isoformat(),
        'benchmark': args.benchmark,
        'mode': 'single' if args.goal else 'full',
        'test_results': []
    }

    for i, test in enumerate(test_cases, 1):
        print(f"\n{'='*60}")
        print(f"ТЕСТ {i}/{len(test_cases)}: {test.get('name', test['input'][:50])}...")
        print(f"{'='*60}\n")

        # Создание и запуск агента
        agent_config = AgentConfig(max_steps=10, temperature=0.2)
        agent = await agent_factory.create_agent(goal=test['input'], config=agent_config)
        
        print("🚀 Агент запущен...\n")
        result = await agent.run(test['input'])

        # Вывод результата
        print(f"\n📊 Результат:")
        
        if hasattr(result, 'data') and result.data:
            if isinstance(result.data, dict):
                final_answer = result.data.get('final_answer', '')
                if final_answer:
                    print(f"\n{final_answer[:500]}{'...' if len(final_answer) > 500 else ''}")
            else:
                print(f"\n{result.data}")
        else:
            print(f"\n{result}")

        # Метаданные
        if hasattr(result, 'metadata'):
            print("\n📈 Метаданные:")
            if result.metadata:
                steps = result.metadata.get('total_steps') or result.metadata.get('steps_executed', 'N/A')
                errors = result.metadata.get('error_count', 0)
                print(f"  - Шагов выполнено: {steps}")
                print(f"  - Ошибок: {errors}")

        # Сохранение результата
        test_result = {
            'test_id': test.get('id', f'test_{i}'),
            'input': test['input'],
            'success': not (hasattr(result, 'error') and result.error),
            'final_answer': result.data.get('final_answer', '') if hasattr(result, 'data') and result.data else str(result),
            'metadata': result.metadata if hasattr(result, 'metadata') else {},
            'steps': result.metadata.get('total_steps', 0) if hasattr(result, 'metadata') else 0
        }
        results['test_results'].append(test_result)

    # Итоговая статистика
    print("\n" + "="*70)
    print("ИТОГОВАЯ СТАТИСТИКА")
    print("="*70)

    total = len(results['test_results'])
    successful = sum(1 for r in results['test_results'] if r['success'])
    
    print(f"\n📊 Всего тестов: {total}")
    print(f"✅ Успешных: {successful}")
    print(f"❌ Failed: {total - successful}")
    if total > 0:
        print(f"📈 Success Rate: {successful/total:.1%}")

    # Сохранение результатов
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\n💾 Результаты сохранены: {output_path}")

    await cleanup(app, infra)


async def cleanup(app, infra):
    await app.shutdown()
    await infra.shutdown()


if __name__ == '__main__':
    asyncio.run(main())
