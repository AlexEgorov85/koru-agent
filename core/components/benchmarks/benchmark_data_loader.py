"""
BenchmarkDataLoader — загрузка тестовых данных из БД для бенчмарков.

ОТВЕТСТВЕННОСТЬ:
- Подключение к БД
- Загрузка реальных тестовых данных
- Формирование тестовых кейсов
- Валидация данных
"""
import asyncio
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime

from core.infrastructure.providers.database.base_db import BaseDBProvider
from core.infrastructure.event_bus.unified_event_bus import EventType, EventDomain, UnifiedEventBus


@dataclass
class BenchmarkTestCase:
    """Тестовый кейс для бенчмарка"""
    id: str
    name: str
    description: str
    input_data: Dict[str, Any]
    expected_output: Dict[str, Any]
    sql_query: str
    difficulty: str  # easy, medium, hard
    category: str  # search, aggregation, join, etc.
    metadata: Dict[str, Any] = field(default_factory=dict)


class BenchmarkDataLoader:
    """
    Загрузчик тестовых данных из БД.

    USAGE:
    ```python
    loader = BenchmarkDataLoader(db_provider, event_bus=event_bus)
    await loader.initialize()
    
    test_cases = await loader.load_test_cases('book_library')
    ```
    """

    def __init__(
        self,
        db_provider: BaseDBProvider,
        event_bus: Optional[UnifiedEventBus] = None,
        session_id: Optional[str] = None,
        agent_id: Optional[str] = None
    ):
        """
        Инициализация.

        ARGS:
        - db_provider: провайдер БД
        - event_bus: шина событий для логирования
        - session_id: ID сессии
        - agent_id: ID агента
        """
        self.db_provider = db_provider
        self.event_bus = event_bus
        self.session_id = session_id
        self.agent_id = agent_id
        self.initialized = False

    async def initialize(self) -> bool:
        """
        Инициализация подключения к БД.

        RETURNS:
        - bool: успешно ли
        """
        try:
            await self.db_provider.execute("SELECT 1")
            self.initialized = True
            return True
        except Exception as e:
            if self.event_bus:
                await self.event_bus.publish(
                    EventType.LOG_ERROR,
                    data={"message": f"Ошибка подключения к БД: {str(e)}"},
                    session_id=self.session_id,
                    domain=EventDomain.BENCHMARK
                )
            return False

    async def load_test_cases(
        self,
        capability: str,
        limit: Optional[int] = None
    ) -> List[BenchmarkTestCase]:
        """
        Загрузка тестовых кейсов для capability.

        ARGS:
        - capability: название способности
        - limit: максимум кейсов

        RETURNS:
        - List[BenchmarkTestCase]: тестовые кейсы
        """
        if not self.initialized:
            await self.initialize()

        if capability == 'book_library':
            return await self._load_book_library_test_cases(limit)
        elif capability == 'sql_generation':
            return await self._load_sql_generation_test_cases(limit)
        else:
            if self.event_bus:
                await self.event_bus.publish(
                    EventType.LOG_WARNING,
                    data={"message": f"Нет тестовых данных для {capability}"},
                    session_id=self.session_id,
                    domain=EventDomain.BENCHMARK
                )
            return []

    async def _load_book_library_test_cases(
        self,
        limit: Optional[int] = None
    ) -> List[BenchmarkTestCase]:
        """
        Загрузка тестовых кейсов для book_library.

        Данные загружаются из реальной БД.

        ARGS:
        - limit: максимум кейсов

        RETURNS:
        - List[BenchmarkTestCase]: тестовые кейсы
        """
        test_cases = []

        try:
            # === КЕЙС 1: Поиск книг по автору ===
            authors_result = await self.db_provider.execute(
                "SELECT DISTINCT author FROM books ORDER BY author LIMIT 5"
            )
            
            for row in authors_result.rows[:3]:
                author = row[0]
                
                # Получаем ожидаемый результат
                books_result = await self.db_provider.execute(
                    f"SELECT title, year FROM books WHERE author = '{author}' ORDER BY title"
                )
                
                expected_books = [
                    {'title': row[0], 'year': row[1]}
                    for row in books_result.rows
                ]

                test_cases.append(BenchmarkTestCase(
                    id=f"book_lib_author_{author.replace(' ', '_').lower()}",
                    name=f"Поиск книг: {author}",
                    description=f"Найти все книги автора {author}",
                    input_data={'author': author},
                    expected_output={
                        'success': True,
                        'books': expected_books,
                        'count': len(expected_books)
                    },
                    sql_query=f"SELECT title, year FROM books WHERE author = '{author}'",
                    difficulty='easy',
                    category='search',
                    metadata={'author': author, 'expected_count': len(expected_books)}
                ))

            # === КЕЙС 2: Поиск по жанру ===
            genres_result = await self.db_provider.execute(
                "SELECT DISTINCT genre FROM books WHERE genre IS NOT NULL ORDER BY genre"
            )
            
            for row in genres_result.rows[:2]:
                genre = row[0]
                
                books_result = await self.db_provider.execute(
                    f"SELECT title, author FROM books WHERE genre = '{genre}' ORDER BY title"
                )
                
                expected_books = [
                    {'title': row[0], 'author': row[1]}
                    for row in books_result.rows
                ]

                test_cases.append(BenchmarkTestCase(
                    id=f"book_lib_genre_{genre.replace(' ', '_').lower()}",
                    name=f"Поиск по жанру: {genre}",
                    description=f"Найти все книги в жанре {genre}",
                    input_data={'genre': genre},
                    expected_output={
                        'success': True,
                        'books': expected_books,
                        'count': len(expected_books)
                    },
                    sql_query=f"SELECT title, author FROM books WHERE genre = '{genre}'",
                    difficulty='easy',
                    category='search',
                    metadata={'genre': genre, 'expected_count': len(expected_books)}
                ))

            # === КЕЙС 3: Агрегация по авторам ===
            agg_result = await self.db_provider.execute(
                "SELECT author, COUNT(*) as book_count FROM books GROUP BY author ORDER BY book_count DESC"
            )
            
            for row in agg_result.rows[:2]:
                author = row[0]
                count = row[1]

                test_cases.append(BenchmarkTestCase(
                    id=f"book_lib_agg_{author.replace(' ', '_').lower()}",
                    name=f"Агрегация: книги по {author}",
                    description=f"Посчитать количество книг автора {author}",
                    input_data={'author': author, 'aggregate': 'count'},
                    expected_output={
                        'success': True,
                        'author': author,
                        'book_count': count
                    },
                    sql_query=f"SELECT COUNT(*) FROM books WHERE author = '{author}'",
                    difficulty='medium',
                    category='aggregation',
                    metadata={'author': author, 'expected_count': count}
                ))

            # === КЕЙС 4: Поиск по году ===
            year_result = await self.db_provider.execute(
                "SELECT DISTINCT year FROM books ORDER BY year DESC LIMIT 3"
            )
            
            for row in year_result.rows:
                year = row[0]
                
                books_result = await self.db_provider.execute(
                    f"SELECT title, author FROM books WHERE year = {year}"
                )
                
                expected_books = [
                    {'title': row[0], 'author': row[1]}
                    for row in books_result.rows
                ]

                test_cases.append(BenchmarkTestCase(
                    id=f"book_lib_year_{year}",
                    name=f"Поиск по году: {year}",
                    description=f"Найти все книги {year} года",
                    input_data={'year': year},
                    expected_output={
                        'success': True,
                        'books': expected_books,
                        'count': len(expected_books)
                    },
                    sql_query=f"SELECT title, author FROM books WHERE year = {year}",
                    difficulty='easy',
                    category='search',
                    metadata={'year': year, 'expected_count': len(expected_books)}
                ))

            # === КЕЙС 5: Сложный запрос (JOIN) ===
            # Получаем данные для JOIN запроса
            join_result = await self.db_provider.execute("""
                SELECT b.title, a.first_name, a.last_name
                FROM books b
                JOIN authors a ON b.author_id = a.id
                WHERE a.last_name = 'Пушкин'
                ORDER BY b.title
            """)
            
            if join_result.rows:
                expected_books = [
                    {'title': row[0], 'author': f"{row[1]} {row[2]}"}
                    for row in join_result.rows
                ]

                test_cases.append(BenchmarkTestCase(
                    id="book_lib_join_pushkin",
                    name="JOIN: Книги Пушкина",
                    description="Найти книги через JOIN с таблицей авторов",
                    input_data={'author_last_name': 'Пушкин'},
                    expected_output={
                        'success': True,
                        'books': expected_books,
                        'count': len(expected_books)
                    },
                    sql_query="""
                        SELECT b.title, a.first_name, a.last_name
                        FROM books b
                        JOIN authors a ON b.author_id = a.id
                        WHERE a.last_name = 'Пушкин'
                    """,
                    difficulty='hard',
                    category='join',
                    metadata={'author': 'Пушкин', 'expected_count': len(expected_books)}
                ))

            # === КЕЙС 6: Поиск с фильтрацией ===
            filtered_result = await self.db_provider.execute("""
                SELECT title, year, genre
                FROM books
                WHERE year > 1860 AND genre = 'Роман'
                ORDER BY year DESC
            """)
            
            expected_books = [
                {'title': row[0], 'year': row[1], 'genre': row[2]}
                for row in filtered_result.rows
            ]

            test_cases.append(BenchmarkTestCase(
                id="book_lib_filtered_romans",
                name="Фильтрация: Романы после 1860",
                description="Найти романы изданные после 1860 года",
                input_data={'year_from': 1860, 'genre': 'Роман'},
                expected_output={
                    'success': True,
                    'books': expected_books,
                    'count': len(expected_books)
                },
                sql_query="""
                    SELECT title, year, genre
                    FROM books
                    WHERE year > 1860 AND genre = 'Роман'
                """,
                difficulty='medium',
                category='filtered_search',
                metadata={'year_from': 1860, 'genre': 'Роман', 'expected_count': len(expected_books)}
            ))

        except Exception as e:
            if self.event_bus:
                await self.event_bus.publish(
                    EventType.LOG_ERROR,
                    data={"message": f"Ошибка загрузки тестовых данных: {str(e)}"},
                    session_id=self.session_id,
                    domain=EventDomain.BENCHMARK
                )

        if limit:
            test_cases = test_cases[:limit]

        if self.event_bus:
            await self.event_bus.publish(
                EventType.LOG_INFO,
                data={"message": f"Загружено {len(test_cases)} тестовых кейсов для book_library"},
                session_id=self.session_id,
                domain=EventDomain.BENCHMARK
            )
        return test_cases

    async def _load_sql_generation_test_cases(
        self,
        limit: Optional[int] = None
    ) -> List[BenchmarkTestCase]:
        """
        Загрузка тестовых кейсов для sql_generation.

        ARGS:
        - limit: максимум кейсов

        RETURNS:
        - List[BenchmarkTestCase]: тестовые кейсы
        """
        # Для sql_generation используем те же данные но с другими input/output
        book_cases = await self._load_book_library_test_cases(limit)
        
        sql_cases = []
        for case in book_cases:
            sql_case = BenchmarkTestCase(
                id=f"sql_{case.id}",
                name=f"SQL: {case.name}",
                description=f"Сгенерировать SQL для: {case.description}",
                input_data={
                    'natural_language': case.description,
                    'tables': ['books', 'authors']
                },
                expected_output={
                    'success': True,
                    'sql': case.sql_query,
                    'valid': True
                },
                sql_query=case.sql_query,
                difficulty=case.difficulty,
                category=case.category,
                metadata=case.metadata
            )
            sql_cases.append(sql_case)

        return sql_cases

    async def get_statistics(self) -> Dict[str, Any]:
        """
        Получение статистики БД.

        RETURNS:
        - Dict[str, Any]: статистика
        """
        if not self.initialized:
            await self.initialize()

        stats = {}

        try:
            # Количество книг
            books_result = await self.db_provider.execute("SELECT COUNT(*) FROM books")
            stats['books_count'] = books_result.rows[0][0] if books_result.rows else 0

            # Количество авторов
            authors_result = await self.db_provider.execute("SELECT COUNT(*) FROM authors")
            stats['authors_count'] = authors_result.rows[0][0] if authors_result.rows else 0

            # Жанры
            genres_result = await self.db_provider.execute(
                "SELECT DISTINCT genre FROM books WHERE genre IS NOT NULL"
            )
            stats['genres'] = [row[0] for row in genres_result.rows]

            # Период
            year_result = await self.db_provider.execute(
                "SELECT MIN(year), MAX(year) FROM books"
            )
            if year_result.rows and year_result.rows[0][0]:
                stats['year_range'] = {
                    'min': year_result.rows[0][0],
                    'max': year_result.rows[0][1]
                }

        except Exception as e:
            if self.event_bus:
                await self.event_bus.publish(
                    EventType.LOG_WARNING,
                    data={"message": f"Ошибка получения статистики: {str(e)}"},
                    session_id=self.session_id,
                    domain=EventDomain.BENCHMARK
                )

        return stats
