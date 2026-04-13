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
    
    test_cases = await loader.load_test_cases('sql_generation')
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

        if capability == 'sql_generation':
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
        # TODO: Загрузка из БД или файла
        return []

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
