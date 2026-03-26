#!/usr/bin/env python3
"""
Генерация бенчмарка для тестирования АГЕНТА (не только SQL).

Создаёт ДВА уровня тестов:
1. SQL Generation — проверка качества генерации SQL
2. Final Answer — проверка качества финального ответа

Использование:
    py -m scripts.cli.generate_agent_benchmark
"""
import asyncio
import json
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any


async def main():
    parser = argparse.ArgumentParser(description='Генерация бенчмарка для агента')
    parser.add_argument('--output', '-o', type=str, 
                        default='data/benchmarks/agent_benchmark.json',
                        help='Файл для сохранения бенчмарка')
    args = parser.parse_args()

    print("="*70)
    print("ГЕНЕРАЦИЯ БЕНЧМАРКА ДЛЯ ТЕСТИРОВАНИЯ АГЕНТА")
    print("="*70)
    print(f"Output: {args.output}")
    print()

    from core.config import get_config
    from core.infrastructure_context.infrastructure_context import InfrastructureContext
    
    config = get_config(profile='dev', data_dir='data')
    
    print("🔄 Инициализация инфраструктуры...")
    infra = InfrastructureContext(config)
    await infra.initialize()
    print("✅ Инфраструктура готова\n")

    db_provider = infra.lifecycle_manager.get_resource('default_db')
    
    if not db_provider:
        print("❌ DB провайдер не найден")
        await cleanup(infra)
        return
    
    try:
        await db_provider.query("SELECT 1")
        print("✅ Подключение к БД успешно")
    except Exception as e:
        print(f"❌ Ошибка подключения к БД: {e}")
        await cleanup(infra)
        return

    print("\n" + "="*70)
    print("ГЕНЕРАЦИЯ ТЕСТОВЫХ КЕЙСОВ")
    print("="*70)

    # Генерируем оба уровня тестов
    sql_tests = await generate_sql_generation_tests(db_provider)
    final_answer_tests = await generate_final_answer_tests(db_provider)

    print(f"\n✅ SQL Generation тестов: {len(sql_tests)}")
    print(f"✅ Final Answer тестов: {len(final_answer_tests)}")

    print("\n" + "="*70)
    print("СОХРАНЕНИЕ БЕНЧМАРКА")
    print("="*70)

    benchmark = {
        'generated_at': datetime.now().isoformat(),
        'version': '1.0',
        'description': 'Бенчмарк для тестирования агента (SQL + Final Answer)',
        'levels': {
            'sql_generation': {
                'description': 'Проверка качества генерации SQL запросов',
                'test_cases': sql_tests
            },
            'final_answer': {
                'description': 'Проверка качества финального ответа',
                'test_cases': final_answer_tests
            }
        },
        'metadata': {
            'source': 'database',
            'dynamic': True
        }
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(benchmark, f, indent=2, ensure_ascii=False)

    print(f"💾 Бенчмарк сохранён: {output_path}")
    print(f"📊 Размер: {output_path.stat().st_size / 1024:.1f} KB")

    # Примеры
    print("\n" + "="*70)
    print("ПРИМЕРЫ ТЕСТОВ")
    print("="*70)

    print("\n📝 SQL Generation:")
    for i, test in enumerate(sql_tests[:2], 1):
        print(f"\n  {i}. {test['name']}")
        print(f"     Input: {test['input']}")
        print(f"     Expected SQL tables: {test['validation']['must_have_tables']}")

    print("\n📝 Final Answer:")
    for i, test in enumerate(final_answer_tests[:2], 1):
        print(f"\n  {i}. {test['name']}")
        print(f"     Input: {test['input']}")
        print(f"     Expected keywords: {test['validation']['must_contain_keywords'][:3]}")

    await cleanup(infra)


async def generate_sql_generation_tests(db_provider) -> List[Dict[str, Any]]:
    """
    Генерация тестов для SQL Generation.
    
    Проверяет:
    - Правильность SQL запроса
    - Наличие нужных таблиц
    - Наличие WHERE clause
    - Валидность SQL
    """
    tests = []
    
    # Получаем авторов для тестов
    authors_result = await db_provider.query(
        'SELECT * FROM "Lib".authors ORDER BY last_name'
    )
    authors = [
        {
            'id': row.get('id') if isinstance(row, dict) else row[0],
            'first_name': row.get('first_name') if isinstance(row, dict) else row[1],
            'last_name': row.get('last_name') if isinstance(row, dict) else row[2]
        }
        for row in authors_result.rows
    ]

    # Берём только 3 авторов для 3 разных типов вопросов
    # Чтобы не раздувать бенчмарк дублирующимися вопросами
    test_authors = authors[:3]  # Первые 3 автора
    
    # Разные типы формулировок вопросов
    question_templates = [
        lambda a: f"Какие книги написал {a['first_name']} {a['last_name']}?",  # Прямой вопрос
        lambda a: f"Найти все книги автора {a['last_name']}",  # Команда
        lambda a: f"Покажи книги {a['first_name']} {a['last_name']}",  # Другая команда
    ]

    for i, author in enumerate(test_authors):
        last_name = author['last_name']
        first_name = author['first_name']

        # Получаем книги для проверки
        books_result = await db_provider.query(f"""
            SELECT b.id, b.title, b.isbn, b.publication_date
            FROM "Lib".books b
            JOIN "Lib".authors a ON b.author_id = a.id
            WHERE a.last_name = '{last_name}'
            ORDER BY b.title
        """)

        books = [
            {
                'title': row.get('title') if isinstance(row, dict) else row[1],
                'year': str(row.get('publication_date')) if isinstance(row, dict) else str(row[3])
            }
            for row in books_result.rows
        ]

        # Один вопрос на автора (разная формулировка)
        nl_query = question_templates[i](author)

        tests.append({
            'id': f"sql_{last_name.lower().replace(' ', '_')}_{hash(nl_query) % 1000}",
            'name': f"SQL: {nl_query[:50]}",
            'input': nl_query,
            'expected_output': {
                'success': True,
                'books': books,
                'count': len(books)
            },
            'validation': {
                'must_have_tables': ['books', 'authors'],
                'must_have_where': True,
                'must_have_join': True,
                'must_be_valid_sql': True,
                'must_return_correct_columns': ['title', 'isbn', 'publication_date']
            },
            'metadata': {
                'author': f"{first_name} {last_name}",
                'expected_count': len(books),
                'difficulty': 'easy' if len(books) <= 2 else 'medium',
                'question_type': ['direct', 'command_find', 'command_show'][i]
            }
        })

    # Дополнительные тесты: агрегация
    tests.append({
        'id': 'sql_aggregation_count',
        'name': 'SQL: Посчитать количество книг',
        'input': 'Сколько всего книг в библиотеке?',
        'expected_output': {
            'success': True,
            'query_type': 'aggregation'
        },
        'validation': {
            'must_have_tables': ['books'],
            'must_have_count': True,
            'must_be_valid_sql': True
        },
        'metadata': {
            'query_type': 'aggregation',
            'difficulty': 'easy'
        }
    })

    # Дополнительные тесты: фильтрация по году
    tests.append({
        'id': 'sql_filter_by_year',
        'name': 'SQL: Книги после 1850 года',
        'input': 'Найти книги изданные после 1850 года',
        'expected_output': {
            'success': True,
            'query_type': 'filtered_search'
        },
        'validation': {
            'must_have_tables': ['books'],
            'must_have_where': True,
            'must_have_year_filter': True,
            'must_be_valid_sql': True
        },
        'metadata': {
            'filter': {'year_from': 1850},
            'difficulty': 'medium'
        }
    })

    # Тесты: Семантический поиск (по описанию сюжета/темы)
    # Оставляем только 2 теста для компактности
    semantic_search_tests = [
        {
            'id': 'sql_semantic_captain_daughter',
            'name': 'SQL: Роман о пугачёвском восстании',
            'input': 'Найди книгу про пугачёвское восстание и офицера который присягнул самозванцу',
            'expected_output': {
                'success': True,
                'books': [{'title': 'Капитанская дочка'}],
                'count': 1
            },
            'validation': {
                'must_have_tables': ['books'],
                'must_have_where': True,
                'must_be_valid_sql': True,
                'must_return_correct_columns': ['title', 'isbn', 'publication_date']
            },
            'metadata': {
                'search_type': 'semantic',
                'target_book': 'Капитанская дочка',
                'target_author': 'Александр Пушкин',
                'difficulty': 'hard'
            }
        },
        {
            'id': 'sql_semantic_crime_punishment',
            'name': 'SQL: Роман о преступлении студента',
            'input': 'Найди роман где студент убил старуху процентщицу',
            'expected_output': {
                'success': True,
                'books': [{'title': 'Преступление и наказание'}],
                'count': 1
            },
            'validation': {
                'must_have_tables': ['books'],
                'must_have_where': True,
                'must_be_valid_sql': True,
                'must_return_correct_columns': ['title', 'isbn', 'publication_date']
            },
            'metadata': {
                'search_type': 'semantic',
                'target_book': 'Преступление и наказание',
                'target_author': 'Фёдор Достоевский',
                'difficulty': 'hard'
            }
        },
    ]

    tests.extend(semantic_search_tests)

    return tests


async def generate_final_answer_tests(db_provider) -> List[Dict[str, Any]]:
    """
    Генерация тестов для Final Answer.
    
    Проверяет:
    - Наличие всех книг в ответе
    - Язык ответа (русский)
    - Отсутствие галлюцинаций
    - Формат ответа
    """
    tests = []
    
    # Получаем авторов
    authors_result = await db_provider.query(
        'SELECT * FROM "Lib".authors ORDER BY last_name'
    )
    authors = [
        {
            'id': row.get('id') if isinstance(row, dict) else row[0],
            'first_name': row.get('first_name') if isinstance(row, dict) else row[1],
            'last_name': row.get('last_name') if isinstance(row, dict) else row[2]
        }
        for row in authors_result.rows
    ]

    for author in authors[:6]:  # Берём 6 авторов
        last_name = author['last_name']
        first_name = author['first_name']
        
        # Получаем книги
        books_result = await db_provider.query(f"""
            SELECT b.title, b.publication_date
            FROM "Lib".books b
            JOIN "Lib".authors a ON b.author_id = a.id
            WHERE a.last_name = '{last_name}'
            ORDER BY b.title
        """)
        
        books = [
            {
                'title': row.get('title') if isinstance(row, dict) else row[1],
                'year': str(row.get('publication_date')) if isinstance(row, dict) else str(row[3])
            }
            for row in books_result.rows
        ]

        # Ключевые слова которые должны быть в ответе
        required_keywords = [book['title'] for book in books[:3]]  # Минимум 3 книги
        if len(books) > 3:
            required_keywords.append(f"{len(books)} книг")  # Или упоминание количества

        # SQL результат (контекст для final_answer)
        sql_context = {
            'query': f"SELECT * FROM books WHERE author = '{last_name}'",
            'rows': books,
            'count': len(books)
        }

        tests.append({
            'id': f"answer_{last_name.lower().replace(' ', '_')}",
            'name': f"Answer: Книги {first_name} {last_name}",
            'input': f"Какие книги написал {first_name} {last_name}?",
            'context': {
                'sql_result': sql_context
            },
            'expected_output': {
                'success': True,
                'language': 'ru',
                'format': 'natural_language'
            },
            'validation': {
                'must_contain_keywords': required_keywords,
                'must_be_in_russian': True,
                'must_not_hallucinate': True,
                'must_mention_author': True,
                'min_length': 20  # Минимум 20 символов
            },
            'metadata': {
                'author': f"{first_name} {last_name}",
                'expected_books': len(books),
                'difficulty': 'easy' if len(books) <= 2 else 'medium'
            }
        })

    # Тест: пустой результат
    tests.append({
        'id': 'answer_no_results',
        'name': 'Answer: Нет результатов',
        'input': 'Какие книги написал Неизвестный Автор?',
        'context': {
            'sql_result': {
                'query': "SELECT * FROM books WHERE author = 'Неизвестный Автор'",
                'rows': [],
                'count': 0
            }
        },
        'expected_output': {
            'success': True,
            'language': 'ru',
            'format': 'natural_language'
        },
        'validation': {
            'must_indicate_no_results': True,
            'must_be_polite': True,
            'must_be_in_russian': True,
            'must_not_hallucinate': True
        },
        'metadata': {
            'expected_books': 0,
            'difficulty': 'easy',
            'edge_case': 'no_results'
        }
    })

    # Тест: агрегация
    tests.append({
        'id': 'answer_aggregation',
        'name': 'Answer: Количество книг',
        'input': 'Сколько всего книг в библиотеке?',
        'context': {
            'sql_result': {
                'query': 'SELECT COUNT(*) FROM books',
                'rows': [{'count': 33}],
                'count': 33
            }
        },
        'expected_output': {
            'success': True,
            'language': 'ru',
            'format': 'natural_language'
        },
        'validation': {
            'must_contain_number': True,
            'must_be_in_russian': True,
            'must_not_hallucinate': True
        },
        'metadata': {
            'query_type': 'aggregation',
            'difficulty': 'easy'
        }
    })

    return tests


async def cleanup(infra):
    await infra.shutdown()


if __name__ == '__main__':
    asyncio.run(main())
