#!/usr/bin/env python3
"""
Запуск агента на бенчмарке и сравнение результатов.

1. Загружает бенчмарк
2. Запускает агента на каждом тесте
3. Сравнивает ответ агента с ожидаемым
4. Выводит метрики качества

Использование:
    py -m scripts.cli.run_agent_benchmark
"""
import asyncio
import json
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional


async def main():
    parser = argparse.ArgumentParser(description='Запуск агента на бенчмарке')
    parser.add_argument('--benchmark', '-b', type=str, 
                        default='data/benchmarks/agent_benchmark.json',
                        help='Файл бенчмарка')
    parser.add_argument('--output', '-o', type=str,
                        default='data/benchmarks/benchmark_results.json',
                        help='Файл для результатов')
    parser.add_argument('--capability', '-c', type=str, default='book_library',
                        help='Тестируемая способность')
    args = parser.parse_args()

    print("="*70)
    print("ЗАПУСК АГЕНТА НА БЕНЧМАРКЕ")
    print("="*70)
    print(f"Benchmark: {args.benchmark}")
    print(f"Capability: {args.capability}")
    print()

    # Загрузка бенчмарка
    benchmark_path = Path(args.benchmark)
    if not benchmark_path.exists():
        print(f"❌ Бенчмарк не найден: {benchmark_path}")
        return

    with open(benchmark_path, 'r', encoding='utf-8') as f:
        benchmark = json.load(f)

    print(f"📊 Загружено тестов:")
    print(f"   SQL Generation: {len(benchmark['levels']['sql_generation']['test_cases'])}")
    print(f"   Final Answer: {len(benchmark['levels']['final_answer']['test_cases'])}")
    print()

    # Инициализация
    from core.config import get_config
    from core.infrastructure.context.infrastructure_context import InfrastructureContext
    from core.application.context.application_context import ApplicationContext
    
    config = get_config(profile='dev', data_dir='data')
    
    print("🔄 Инициализация инфраструктуры...")
    infra = InfrastructureContext(config)
    await infra.initialize()
    
    app = ApplicationContext(infra, config, 'dev')
    await app.initialize()
    print("✅ Инфраструктура готова\n")

    # Запуск тестов
    print("="*70)
    print("ЗАПУСК ТЕСТОВ")
    print("="*70)

    results = {
        'run_at': datetime.now().isoformat(),
        'benchmark': args.benchmark,
        'capability': args.capability,
        'levels': {}
    }

    # SQL Generation тесты
    sql_results = await run_sql_generation_tests(
        benchmark['levels']['sql_generation']['test_cases'],
        app, infra
    )
    results['levels']['sql_generation'] = sql_results

    # Final Answer тесты
    answer_results = await run_final_answer_tests(
        benchmark['levels']['final_answer']['test_cases'],
        app, infra
    )
    results['levels']['final_answer'] = answer_results

    # Итоговая статистика
    print("\n" + "="*70)
    print("ИТОГОВАЯ СТАТИСТИКА")
    print("="*70)

    stats = calculate_statistics(results)
    print(f"\n📊 SQL Generation:")
    print(f"   Всего тестов: {stats['sql']['total']}")
    print(f"   Успешных: {stats['sql']['passed']}")
    print(f"   Failed: {stats['sql']['failed']}")
    print(f"   Success Rate: {stats['sql']['success_rate']:.1%}")

    print(f"\n📊 Final Answer:")
    print(f"   Всего тестов: {stats['answer']['total']}")
    print(f"   Успешных: {stats['answer']['passed']}")
    print(f"   Failed: {stats['answer']['failed']}")
    print(f"   Success Rate: {stats['answer']['success_rate']:.1%}")

    # Сохранение результатов
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\n💾 Результаты сохранены: {output_path}")

    await cleanup(app, infra)


async def run_sql_generation_tests(
    test_cases: List[Dict[str, Any]],
    app, infra
) -> Dict[str, Any]:
    """
    Запуск тестов SQL Generation.
    """
    print("\n📝 SQL Generation тесты...")
    
    results = []
    passed = 0
    failed = 0

    for i, test in enumerate(test_cases[:5], 1):  # Первые 5 для теста
        print(f"\n  Тест {i}/{len(test_cases[:5])}: {test['name'][:50]}...")
        
        # Запуск агента
        agent_response = await run_agent_on_input(test['input'], app)
        
        # Валидация
        validation_result = validate_sql_generation(
            agent_response,
            test['validation'],
            test['expected_output']
        )
        
        if validation_result['passed']:
            passed += 1
            print(f"    ✅ PASS")
        else:
            failed += 1
            print(f"    ❌ FAIL: {', '.join(validation_result['errors'])}")
        
        results.append({
            'test_id': test['id'],
            'input': test['input'],
            'agent_response': agent_response,
            'validation': validation_result,
            'passed': validation_result['passed']
        })

    print(f"\n  Итого: {passed} passed, {failed} failed")
    
    return {
        'test_cases': results,
        'passed': passed,
        'failed': failed,
        'total': len(test_cases[:5])
    }


async def run_final_answer_tests(
    test_cases: List[Dict[str, Any]],
    app, infra
) -> Dict[str, Any]:
    """
    Запуск тестов Final Answer.
    """
    print("\n📝 Final Answer тесты...")
    
    results = []
    passed = 0
    failed = 0

    for i, test in enumerate(test_cases[:3], 1):  # Первые 3 для теста
        print(f"\n  Тест {i}/{len(test_cases[:3])}: {test['name'][:50]}...")
        
        # Запуск агента (с контекстом из SQL результата)
        agent_response = await run_agent_on_input(test['input'], app)
        
        # Валидация
        validation_result = validate_final_answer(
            agent_response,
            test['validation'],
            test.get('context', {})
        )
        
        if validation_result['passed']:
            passed += 1
            print(f"    ✅ PASS")
        else:
            failed += 1
            print(f"    ❌ FAIL: {', '.join(validation_result['errors'])}")
        
        results.append({
            'test_id': test['id'],
            'input': test['input'],
            'agent_response': agent_response,
            'validation': validation_result,
            'passed': validation_result['passed']
        })

    print(f"\n  Итого: {passed} passed, {failed} failed")
    
    return {
        'test_cases': results,
        'passed': passed,
        'failed': failed,
        'total': len(test_cases[:3])
    }


async def run_agent_on_input(input_text: str, app) -> Dict[str, Any]:
    """
    Запуск агента на входном тексте.
    
    В РЕАЛЬНОСТИ: здесь должен быть вызов полного агента
    СЕЙЧАС: mock для демонстрации
    """
    # TODO: Реальный вызов агента
    # agent = app.agent_factory.create_agent(input_text)
    # result = await agent.run()
    
    # Mock ответ для демонстрации
    return {
        'sql': 'SELECT * FROM "Lib".books WHERE author_id = ...',
        'sql_valid': True,
        'final_answer': f'Ответ на вопрос: {input_text[:50]}...',
        'books': [],
        'execution_time_ms': 100,
        'tokens_used': 50
    }


def validate_sql_generation(
    agent_response: Dict[str, Any],
    validation_rules: Dict[str, Any],
    expected_output: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Валидация SQL Generation ответа.
    """
    errors = []
    
    # Проверка валидности SQL
    if validation_rules.get('must_be_valid_sql') and not agent_response.get('sql_valid'):
        errors.append('SQL не валидный')
    
    # Проверка таблиц
    if validation_rules.get('must_have_tables'):
        required_tables = validation_rules['must_have_tables']
        # TODO: Парсить SQL и проверять таблицы
        # Сейчас заглушка
        pass
    
    # Проверка WHERE clause
    if validation_rules.get('must_have_where'):
        if 'WHERE' not in agent_response.get('sql', '').upper():
            errors.append('Нет WHERE clause')
    
    # Проверка JOIN
    if validation_rules.get('must_have_join'):
        if 'JOIN' not in agent_response.get('sql', '').upper():
            errors.append('Нет JOIN')
    
    return {
        'passed': len(errors) == 0,
        'errors': errors,
        'checks': {
            'sql_valid': agent_response.get('sql_valid', False),
            'has_where': 'WHERE' in agent_response.get('sql', '').upper(),
            'has_join': 'JOIN' in agent_response.get('sql', '').upper()
        }
    }


def validate_final_answer(
    agent_response: Dict[str, Any],
    validation_rules: Dict[str, Any],
    context: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Валидация Final Answer ответа.
    """
    errors = []
    answer = agent_response.get('final_answer', '')
    
    # Проверка keywords
    if validation_rules.get('must_contain_keywords'):
        required_keywords = validation_rules['must_contain_keywords']
        missing_keywords = [
            kw for kw in required_keywords
            if kw.lower() not in answer.lower()
        ]
        if missing_keywords:
            errors.append(f'Нет keywords: {missing_keywords[:3]}')
    
    # Проверка языка (русский)
    if validation_rules.get('must_be_in_russian'):
        # Простая проверка на кириллицу
        has_cyrillic = any('\u0400' <= c <= '\u04FF' for c in answer)
        if not has_cyrillic:
            errors.append('Ответ не на русском')
    
    # Проверка на галлюцинации
    if validation_rules.get('must_not_hallucinate'):
        # TODO: Сравнивать с SQL результатом
        pass
    
    # Проверка минимальной длины
    if validation_rules.get('min_length'):
        if len(answer) < validation_rules['min_length']:
            errors.append(f'Ответ слишком короткий ({len(answer)} < {validation_rules["min_length"]})')
    
    return {
        'passed': len(errors) == 0,
        'errors': errors,
        'checks': {
            'has_keywords': len([e for e in errors if 'keywords' in e]) == 0,
            'is_russian': any('\u0400' <= c <= '\u04FF' for c in answer),
            'length': len(answer)
        }
    }


def calculate_statistics(results: Dict[str, Any]) -> Dict[str, Any]:
    """
    Расчёт статистики результатов.
    """
    stats = {}
    
    for level in ['sql_generation', 'final_answer']:
        level_data = results['levels'].get(level, {})
        total = level_data.get('total', 0)
        passed = level_data.get('passed', 0)
        failed = level_data.get('failed', 0)
        
        stats[level.split('_')[0]] = {
            'total': total,
            'passed': passed,
            'failed': failed,
            'success_rate': passed / total if total > 0 else 0.0
        }
    
    return stats


async def cleanup(app, infra):
    await app.shutdown()
    await infra.shutdown()


if __name__ == '__main__':
    asyncio.run(main())
