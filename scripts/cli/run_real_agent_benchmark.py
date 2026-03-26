#!/usr/bin/env python3
"""
Запуск РЕАЛЬНОГО агента на бенчмарке.

Использование:
    # Запустить ВСЕ тесты из бенчмарка
    py -m scripts.cli.run_real_agent_benchmark

    # Запустить только SQL тесты
    py -m scripts.cli.run_real_agent_benchmark --level sql

    # Запустить только Final Answer тесты
    py -m scripts.cli.run_real_agent_benchmark --level answer

    # Запустить первые 5 тестов
    py -m scripts.cli.run_real_agent_benchmark --limit 5

    # Запустить один конкретный вопрос
    py -m scripts.cli.run_real_agent_benchmark -g "Какие книги написал Пушкин?"
"""
import asyncio
import json
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any

# Импорт валидатора
from core.services.benchmarks import BenchmarkValidator


async def main():
    parser = argparse.ArgumentParser(description='Запуск РЕАЛЬНОГО агента на бенчмарке')
    parser.add_argument('--benchmark', '-b', type=str, 
                        default='data/benchmarks/agent_benchmark.json',
                        help='Файл бенчмарка')
    parser.add_argument('--output', '-o', type=str,
                        default='data/benchmarks/real_benchmark_results.json',
                        help='Файл для результатов')
    parser.add_argument('--goal', '-g', type=str, default=None,
                        help='Один тестовый вопрос (если не указан — запускаются тесты из бенчмарка)')
    parser.add_argument('--limit', '-l', type=int, default=None,
                        help='Максимум тестов для запуска (по умолчанию — все тесты из бенчмарка)')
    parser.add_argument('--level', type=str, default='all', choices=['all', 'sql', 'answer'],
                        help='Какой уровень тестов запускать (all/sql/answer)')
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
        # Запуск тестов из бенчмарка
        print(f"Benchmark: {args.benchmark}")
        print(f"Mode: FULL BENCHMARK\n")

        sql_tests = benchmark['levels']['sql_generation']['test_cases']
        answer_tests = benchmark['levels']['final_answer']['test_cases']
        
        # Выбор уровня тестов
        if args.level == 'sql':
            test_cases = sql_tests
            print(f"📊 Уровень: SQL Generation")
        elif args.level == 'answer':
            test_cases = answer_tests
            print(f"📊 Уровень: Final Answer")
        else:
            test_cases = sql_tests + answer_tests
            print(f"📊 Уровни: SQL Generation + Final Answer")
        
        # Ограничение количества тестов
        if args.limit:
            test_cases = test_cases[:args.limit]
            print(f"📊 Ограничение: {args.limit} тестов\n")
        else:
            print(f"📊 Ограничение: нет (все тесты)\n")
        
        print(f"📊 Загружено тестов:")
        print(f"   SQL Generation: {len(sql_tests)}" + (f" (запускаем {args.limit})" if args.limit and args.level != 'answer' else ""))
        print(f"   Final Answer: {len(answer_tests)}" + (f" (запускаем {args.limit})" if args.limit and args.level != 'sql' else ""))
        print(f"   👉 Всего запускаем: {len(test_cases)} тестов\n")

    from core.config import get_config
    from core.infrastructure_context.infrastructure_context import InfrastructureContext
    from core.application_context.application_context import ApplicationContext
    from core.agent.factory import AgentFactory
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

    # Инициализация валидатора
    validator = BenchmarkValidator()
    print("✅ Валидатор инициализирован\n")

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
        if hasattr(result, 'metadata') and result.metadata:
            print("\n📈 Метаданные:")
            metadata = result.metadata
            if isinstance(metadata, dict):
                steps = metadata.get('total_steps') or metadata.get('steps_executed', 'N/A')
                errors = metadata.get('error_count', 0)
            else:
                steps = getattr(metadata, 'total_steps', 'N/A')
                errors = getattr(metadata, 'error_count', 0)
            print(f"  - Шагов выполнено: {steps}")
            print(f"  - Ошибок: {errors}")

        # Сохранение результата
        # Обработка результата (может быть dict, Pydantic модель или строка)
        final_answer = ''
        steps_count = 0
        success = True
        
        if hasattr(result, 'data') and result.data:
            if isinstance(result.data, dict):
                final_answer = result.data.get('final_answer', '')
                steps_count = result.metadata.get('total_steps', 0) if hasattr(result, 'metadata') else 0
            elif hasattr(result.data, '__dict__'):
                # Pydantic модель
                final_answer = getattr(result.data, 'final_answer', str(result.data))
                steps_count = getattr(result, 'metadata', {}).get('total_steps', 0) if hasattr(result, 'metadata') else 0
            else:
                final_answer = str(result.data)
        else:
            final_answer = str(result)
        
        # Проверка на ошибки
        if hasattr(result, 'error') and result.error:
            success = False

        # ВАЛИДАЦИЯ с использованием benchmark_validator
        validation_result = None
        if test.get('validation'):
            # Валидация финального ответа
            validation_result = validator.validate_final_answer(
                answer=final_answer,
                validation_rules=test.get('validation', {}),
                context={'metadata': test.get('metadata', {})},
                expected_books=test.get('expected_output', {}).get('books', [])
            )
            # Переопределяем success на основе валидации
            success = validation_result['passed']
            
            # Вывод результатов валидации
            if validation_result['passed']:
                print(f"\n    ✅ ВАЛИДАЦИЯ: PASS")
            else:
                print(f"\n    ❌ ВАЛИДАЦИЯ: FAIL - {', '.join(validation_result['errors'][:3])}")

        test_result = {
            'test_id': test.get('id', f'test_{i}'),
            'input': test['input'],
            'success': success,
            'final_answer': final_answer[:1000],  # Ограничиваем длину
            'metadata': result.metadata if hasattr(result, 'metadata') else {},
            'steps': steps_count,
            'validation': validation_result
        }
        results['test_results'].append(test_result)

    # Итоговая статистика
    print("\n" + "="*70)
    print("ИТОГОВАЯ СТАТИСТИКА")
    print("="*70)

    total = len(results['test_results'])
    successful = sum(1 for r in results['test_results'] if r['success'])
    
    # Расчёт метрик
    total_steps = sum(r.get('steps', 0) for r in results['test_results'])
    avg_steps = total_steps / successful if successful > 0 else 0
    
    # Оценка эффективности (1 шаг = идеально, >3 шагов = много)
    efficiency_score = max(0, 100 - (avg_steps - 1) * 20) if avg_steps > 0 else 0
    
    # Оценка успешности
    success_rate = (successful / total * 100) if total > 0 else 0
    
    # Общая оценка (0-100)
    overall_score = (success_rate * 0.7 + efficiency_score * 0.3)
    
    # Интерпретация
    if overall_score >= 90:
        grade = "ОТЛИЧНО"
        emoji = "🏆"
    elif overall_score >= 75:
        grade = "ХОРОШО"
        emoji = "✅"
    elif overall_score >= 50:
        grade = "УДОВЛЕТВОРИТЕЛЬНО"
        emoji = "⚠️"
    else:
        grade = "ТРЕБУЕТ УЛУЧШЕНИЙ"
        emoji = "❌"
    
    print(f"\n📊 Общие метрики:")
    print(f"   Всего тестов: {total}")
    print(f"   ✅ Успешных: {successful}")
    print(f"   ❌ Failed: {total - successful}")
    print(f"   📈 Success Rate: {success_rate:.1f}%")
    
    if successful > 0:
        print(f"\n📈 Эффективность:")
        print(f"   Всего шагов: {total_steps}")
        print(f"   Среднее шагов на тест: {avg_steps:.2f}")
        print(f"   Efficiency Score: {efficiency_score:.1f}/100")
    
    print(f"\n{'='*60}")
    print(f"   ОБЩАЯ ОЦЕНКА: {overall_score:.1f}/100 {emoji} {grade}")
    print(f"{'='*60}")
    
    # Детализация по уровням
    print(f"\n📊 Детализация по уровням:")
    
    sql_results = [r for r in results['test_results'] if 'sql' in r.get('test_id', '').lower() or 'author' in r.get('input', '').lower()]
    answer_results = [r for r in results['test_results'] if 'answer' in r.get('test_id', '').lower()]
    
    if sql_results:
        sql_success = sum(1 for r in sql_results if r['success'])
        print(f"   SQL Generation: {sql_success}/{len(sql_results)} ({sql_success/len(sql_results)*100:.1f}%)")
    
    if answer_results:
        answer_success = sum(1 for r in answer_results if r['success'])
        print(f"   Final Answer: {answer_success}/{len(answer_results)} ({answer_success/len(answer_results)*100:.1f}%)")

    # Сохранение результатов
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Добавляем метрики в результаты
    results['metrics'] = {
        'total': total,
        'successful': successful,
        'failed': total - successful,
        'success_rate': success_rate,
        'total_steps': total_steps,
        'avg_steps': avg_steps,
        'efficiency_score': efficiency_score,
        'overall_score': overall_score,
        'grade': grade
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\n💾 Результаты сохранены: {output_path}")

    await cleanup(app, infra)


async def cleanup(app, infra):
    await app.shutdown()
    await infra.shutdown()


if __name__ == '__main__':
    asyncio.run(main())
