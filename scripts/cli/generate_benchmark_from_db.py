#!/usr/bin/env python3
"""
Генерация бенчмарка из реальных данных БД.

Скрипт подключается к БД, загружает реальные данные и создаёт тестовые кейсы.

Использование:
    py -m scripts.cli.generate_benchmark_from_db -c book_library
"""
import asyncio
import json
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any


async def main():
    parser = argparse.ArgumentParser(description='Генерация бенчмарка из БД')
    parser.add_argument('--capability', '-c', type=str, default='book_library',
                        help='Название способности')
    parser.add_argument('--output', '-o', type=str, 
                        default='data/benchmarks/generated_benchmark.json',
                        help='Файл для сохранения бенчмарка')
    args = parser.parse_args()

    print("="*70)
    print("ГЕНЕРАЦИЯ БЕНЧМАРКА ИЗ РЕАЛЬНЫХ ДАННЫХ БД")
    print("="*70)
    print(f"Capability: {args.capability}")
    print(f"Output: {args.output}")
    print()

    from core.config import get_config
    from core.infrastructure.context.infrastructure_context import InfrastructureContext
    
    config = get_config(profile='dev', data_dir='data')
    
    print("🔄 Инициализация инфраструктуры...")
    infra = InfrastructureContext(config)
    await infra.initialize()
    print("✅ Инфраструктура готова\n")

    print("="*70)
    print("ЭТАП 1: ЗАГРУЗКА ДАННЫХ ИЗ БД")
    print("="*70)

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
    print("ЭТАП 2: ГЕНЕРАЦИЯ ТЕСТОВЫХ КЕЙСОВ")
    print("="*70)

    test_cases = []

    if args.capability == 'book_library':
        test_cases = await generate_book_library_benchmarks(db_provider)
    elif args.capability == 'sql_generation':
        test_cases = await generate_sql_generation_benchmarks(db_provider)
    else:
        print(f"⚠️  Нет генератора для {args.capability}")
        await cleanup(infra)
        return

    print(f"\n✅ Сгенерировано {len(test_cases)} тестовых кейсов")

    print("\n" + "="*70)
    print("ЭТАП 3: СТАТИСТИКА БД")
    print("="*70)

    stats = await get_db_statistics(db_provider)
    print(f"📊 Статистика БД:")
    for key, value in stats.items():
        print(f"   {key}: {value}")

    print("\n" + "="*70)
    print("ЭТАП 4: СОХРАНЕНИЕ БЕНЧМАРКА")
    print("="*70)

    benchmark = {
        'generated_at': datetime.now().isoformat(),
        'capability': args.capability,
        'database_stats': stats,
        'test_cases': [tc.to_dict() for tc in test_cases],
        'metadata': {
            'source': 'database',
            'dynamic': True,
            'version': '1.0'
        }
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(benchmark, f, indent=2, ensure_ascii=False)

    print(f"💾 Бенчмарк сохранён: {output_path}")
    print(f"📊 Размер: {output_path.stat().st_size / 1024:.1f} KB")

    print("\n" + "="*70)
    print("ПРИМЕРЫ ТЕСТОВЫХ КЕЙСОВ")
    print("="*70)

    for i, tc in enumerate(test_cases[:3], 1):
        print(f"\n{i}. {tc.name}")
        print(f"   Input: {tc.input_data}")
        print(f"   Expected: {tc.expected_output.get('count', 'N/A')} результатов")
        print(f"   Difficulty: {tc.difficulty}")

    await cleanup(infra)


async def get_row_value(row, key_or_idx):
    """Универсальный доступ к значению строки (dict или tuple)"""
    if isinstance(row, dict):
        return row.get(key_or_idx)
    else:
        return row[key_or_idx] if isinstance(key_or_idx, int) else None


async def generate_book_library_benchmarks(db_provider) -> List:
    from dataclasses import dataclass, field
    from typing import Dict, Any, List
    
    @dataclass
    class BenchmarkTestCase:
        id: str
        name: str
        description: str
        input_data: Dict[str, Any]
        expected_output: Dict[str, Any]
        sql_query: str
        difficulty: str
        category: str
        metadata: Dict[str, Any] = field(default_factory=dict)
        
        def to_dict(self) -> Dict[str, Any]:
            return {
                'id': self.id,
                'name': self.name,
                'description': self.description,
                'input_data': self.input_data,
                'expected_output': self.expected_output,
                'sql_query': self.sql_query,
                'difficulty': self.difficulty,
                'category': self.category,
                'metadata': self.metadata
            }
    
    test_cases = []

    try:
        # 1. Авторы
        authors_result = await db_provider.query(
            'SELECT * FROM "Lib".authors ORDER BY last_name'
        )
        authors = [
            {
                'id': await get_row_value(row, 'id'),
                'first_name': await get_row_value(row, 'first_name'),
                'last_name': await get_row_value(row, 'last_name')
            }
            for row in authors_result.rows
        ]
        print(f"📚 Найдено авторов: {len(authors)}")

        for author in authors[:10]:
            last_name = author['last_name']
            
            books_result = await db_provider.query(f"""
                SELECT b.id, b.title, b.isbn, b.publication_date
                FROM "Lib".books b
                JOIN "Lib".authors a ON b.author_id = a.id
                WHERE a.last_name = '{last_name}'
                ORDER BY b.title
            """)
            
            books = [
                {
                    'book_id': await get_row_value(row, 'id'),
                    'title': await get_row_value(row, 'title'),
                    'isbn': await get_row_value(row, 'isbn'),
                    'publication_date': str(await get_row_value(row, 'publication_date')) if await get_row_value(row, 'publication_date') else None
                }
                for row in books_result.rows
            ]

            if books:
                test_cases.append(BenchmarkTestCase(
                    id=f"author_{last_name.lower().replace(' ', '_')}",
                    name=f"Поиск книг: {author['first_name']} {last_name}",
                    description=f"Найти все книги автора {last_name}",
                    input_data={'author': last_name},
                    expected_output={'success': True, 'books': books, 'count': len(books)},
                    sql_query=f"SELECT * FROM \"Lib\".books WHERE author_id = (SELECT id FROM \"Lib\".authors WHERE last_name = '{last_name}')",
                    difficulty='easy' if len(books) <= 3 else 'medium',
                    category='search',
                    metadata={'author_name': f"{author['first_name']} {last_name}", 'expected_count': len(books)}
                ))

        # 2. Категории
        categories_result = await db_provider.query("""
            SELECT DISTINCT category 
            FROM "Lib".books 
            WHERE category IS NOT NULL 
            ORDER BY category
        """)
        categories = [await get_row_value(row, 'category') for row in categories_result.rows]
        print(f"📚 Найдено категорий: {len(categories)}")

        for category in categories[:5]:
            books_result = await db_provider.query(f"""
                SELECT id, title, author_id
                FROM "Lib".books
                WHERE category = '{category}'
                ORDER BY title
                LIMIT 10
            """)
            books_count = len(books_result.rows)

            test_cases.append(BenchmarkTestCase(
                id=f"category_{category.lower().replace(' ', '_')}",
                name=f"Поиск по категории: {category}",
                description=f"Найти все книги в категории {category}",
                input_data={'category': category},
                expected_output={'success': True, 'category': category, 'count': books_count},
                sql_query=f"SELECT * FROM \"Lib\".books WHERE category = '{category}'",
                difficulty='easy',
                category='search',
                metadata={'category': category, 'expected_count': books_count}
            ))

        # 3. Агрегация
        agg_result = await db_provider.query("""
            SELECT a.last_name, a.first_name, COUNT(b.id) as book_count
            FROM "Lib".authors a
            LEFT JOIN "Lib".books b ON a.id = b.author_id
            GROUP BY a.id, a.first_name, a.last_name
            ORDER BY book_count DESC
            LIMIT 5
        """)
        
        for row in agg_result.rows:
            last_name = await get_row_value(row, 'last_name')
            first_name = await get_row_value(row, 'first_name')
            count = await get_row_value(row, 'book_count')

            test_cases.append(BenchmarkTestCase(
                id=f"agg_author_{last_name.lower().replace(' ', '_')}",
                name=f"Агрегация: книги {last_name}",
                description=f"Посчитать количество книг автора {last_name}",
                input_data={'author': last_name, 'aggregate': 'count'},
                expected_output={'success': True, 'author': f"{first_name} {last_name}", 'book_count': count},
                sql_query=f"SELECT COUNT(*) FROM \"Lib\".books WHERE author_id = (SELECT id FROM \"Lib\".authors WHERE last_name = '{last_name}')",
                difficulty='medium',
                category='aggregation',
                metadata={'author_name': f"{first_name} {last_name}", 'expected_count': count}
            ))

    except Exception as e:
        print(f"❌ Ошибка генерации бенчмарков: {e}")
        import traceback
        traceback.print_exc()

    return test_cases


async def generate_sql_generation_benchmarks(db_provider) -> List:
    from dataclasses import dataclass, field
    from typing import Dict, Any, List
    
    @dataclass
    class BenchmarkTestCase:
        id: str
        name: str
        description: str
        input_data: Dict[str, Any]
        expected_output: Dict[str, Any]
        sql_query: str
        difficulty: str
        category: str
        metadata: Dict[str, Any] = field(default_factory=dict)
        
        def to_dict(self) -> Dict[str, Any]:
            return {
                'id': self.id,
                'name': self.name,
                'description': self.description,
                'input_data': self.input_data,
                'expected_output': self.expected_output,
                'sql_query': self.sql_query,
                'difficulty': self.difficulty,
                'category': self.category,
                'metadata': self.metadata
            }
    
    book_cases = await generate_book_library_benchmarks(db_provider)
    
    sql_cases = []
    for case in book_cases:
        sql_case = BenchmarkTestCase(
            id=f"sql_{case.id}",
            name=f"SQL: {case.name}",
            description=f"Сгенерировать SQL для: {case.description}",
            input_data={'natural_language': case.description, 'tables': ['books', 'authors']},
            expected_output={'success': True, 'sql': case.sql_query, 'valid': True},
            sql_query=case.sql_query,
            difficulty=case.difficulty,
            category=f"sql_{case.category}",
            metadata=case.metadata
        )
        sql_cases.append(sql_case)

    return sql_cases


async def get_db_statistics(db_provider) -> Dict[str, Any]:
    stats = {}
    try:
        authors_result = await db_provider.query('SELECT COUNT(*) as count FROM "Lib".authors')
        stats['authors_count'] = await get_row_value(authors_result.rows[0], 'count') if authors_result.rows else 0

        books_result = await db_provider.query('SELECT COUNT(*) as count FROM "Lib".books')
        stats['books_count'] = await get_row_value(books_result.rows[0], 'count') if books_result.rows else 0

        categories_result = await db_provider.query("SELECT DISTINCT category FROM \"Lib\".books WHERE category IS NOT NULL")
        stats['categories'] = [await get_row_value(row, 'category') for row in categories_result.rows]
        stats['categories_count'] = len(stats['categories'])

    except Exception as e:
        print(f"⚠️  Ошибка получения статистики: {e}")

    return stats


async def cleanup(infra):
    await infra.shutdown()


if __name__ == '__main__':
    asyncio.run(main())
