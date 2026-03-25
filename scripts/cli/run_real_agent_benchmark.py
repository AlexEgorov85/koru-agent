#!/usr/bin/env python3
"""
Запуск РЕАЛЬНОГО агента на бенчмарке.

Использование:
    py -m scripts.cli.run_real_agent_benchmark
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
    parser.add_argument('--goal', '-g', type=str,
                        default='Какие книги написал Пушкин?',
                        help='Тестовый вопрос для агента')
    args = parser.parse_args()

    print("="*70)
    print("ЗАПУСК РЕАЛЬНОГО АГЕНТА НА БЕНЧМАРКЕ")
    print("="*70)
    print(f"Goal: {args.goal}")
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

    print("="*70)
    print("ЗАПУСК АГЕНТА")
    print("="*70)
    print(f"Вопрос: {args.goal}\n")

    # Создание и запуск агента
    agent_config = AgentConfig(max_steps=10, temperature=0.2)
    agent = await agent_factory.create_agent(goal=args.goal, config=agent_config)
    
    print("🚀 Агент запущен...\n")
    
    result = await agent.run(args.goal)

    # Вывод результата
    print("\n" + "="*70)
    print("РЕЗУЛЬТАТ АГЕНТА")
    print("="*70)

    if hasattr(result, 'data') and result.data:
        if isinstance(result.data, dict):
            final_answer = result.data.get('final_answer', '')
            if final_answer:
                print(f"\n{final_answer}")
            else:
                print(f"\n{result.data}")
        else:
            print(f"\n{result.data}")
    else:
        print(f"\n{result}")

    # Метаданные
    if hasattr(result, 'metadata'):
        print("\n" + "-"*60)
        print("Метаданные:")
        if result.metadata:
            steps = result.metadata.get('total_steps') or result.metadata.get('steps_executed', 'N/A')
            errors = result.metadata.get('error_count', 0)
            print(f"  - Шагов выполнено: {steps}")
            print(f"  - Ошибок: {errors}")

    print("="*60)

    # Сохранение результатов
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    benchmark_result = {
        'run_at': datetime.now().isoformat(),
        'goal': args.goal,
        'result': {
            'success': not (hasattr(result, 'error') and result.error),
            'final_answer': result.data.get('final_answer', '') if hasattr(result, 'data') and result.data else str(result),
            'metadata': result.metadata if hasattr(result, 'metadata') else {}
        }
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(benchmark_result, f, indent=2, ensure_ascii=False)

    print(f"\n💾 Результаты сохранены: {output_path}")

    await cleanup(app, infra)


async def cleanup(app, infra):
    await app.shutdown()
    await infra.shutdown()


if __name__ == '__main__':
    asyncio.run(main())
