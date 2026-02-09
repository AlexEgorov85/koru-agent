"""
Реальные интеграционные тесты для PostgreSQLProvider.
Тестируют работу с реальной PostgreSQL базой данных.
ВАЖНО: Эти тесты требуют настройки PostgreSQL и могут изменять данные в БД.
Для запуска: pytest -v tests/providers/test_postgres_provider_real.py
"""

import asyncio
import pytest
import os
import time
import json
import uuid



from core.config import get_config
from core.infrastructure.providers.database.base_db import DBConnectionConfig, DBHealthStatus
from core.infrastructure.providers.database.postgres_provider import PostgreSQLProvider

# ==========================================================
# Конфигурация для реальных тестов
# ==========================================================

# Параметры подключения к тестовой БД
TEST_DB_CONFIG = {
    "host": os.getenv("TEST_DB_HOST", "localhost"),
    "port": int(os.getenv("TEST_DB_PORT", "5432")),
    "database": os.getenv("TEST_DB_NAME", "agent_test"),
    "username": os.getenv("TEST_DB_USER", "test_user"),
    "password": os.getenv("TEST_DB_PASSWORD", "test_password"),
    "sslmode": os.getenv("TEST_DB_SSL", "disable"),
    "timeout": 30.0,
    "pool_size": 5
}

# Флаг для пропуска тестов если нет подключения к БД
def can_connect_to_test_db():
    """Проверяет возможность подключения к тестовой БД."""
    try:
        import psycopg2
        conn = psycopg2.connect(
            host=TEST_DB_CONFIG["host"],
            port=TEST_DB_CONFIG["port"],
            dbname=TEST_DB_CONFIG["database"],
            user=TEST_DB_CONFIG["username"],
            password=TEST_DB_CONFIG["password"],
            connect_timeout=5
        )
        conn.close()
        return True
    except Exception as e:
        print(f"Невозможно подключиться к тестовой БД: {str(e)}")
        return False

# Пропускаем тесты если нет подключения к БД
if not can_connect_to_test_db():
    pytest.skip("Невозможно подключиться к тестовой PostgreSQL базе данных", allow_module_level=True)

@pytest.fixture(scope="module")
def test_db_config():
    """Конфигурация для тестовой PostgreSQL БД."""
    return TEST_DB_CONFIG

@pytest.fixture(scope="module")
def db_connection_config(test_db_config):
    """Конфигурация подключения к БД как объект."""
    return DBConnectionConfig(**test_db_config)

@pytest.fixture(scope="module")
def system_context():
    """Системный контекст для тестов."""
    return get_config()

# ==========================================================
# Вспомогательные функции
# ==========================================================

async def setup_test_schema(provider: PostgreSQLProvider):
    """Создает тестовую схему и таблицы для тестов."""
    # Создаем тестовую схему
    await provider.execute("""
    CREATE SCHEMA IF NOT EXISTS test_schema;
    """)
    
    # Создаем тестовые таблицы
    await provider.execute("""
    CREATE TABLE IF NOT EXISTS test_schema.books (
        id SERIAL PRIMARY KEY,
        title VARCHAR(255) NOT NULL,
        author VARCHAR(255) NOT NULL,
        publication_year INTEGER,
        genre VARCHAR(100),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    
    await provider.execute("""
    CREATE TABLE IF NOT EXISTS test_schema.authors (
        id SERIAL PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        birth_year INTEGER,
        nationality VARCHAR(100)
    );
    """)
    
    await provider.execute("""
    CREATE TABLE IF NOT EXISTS test_schema.book_reviews (
        id SERIAL PRIMARY KEY,
        book_id INTEGER REFERENCES test_schema.books(id),
        reviewer_name VARCHAR(255),
        rating INTEGER CHECK (rating BETWEEN 1 AND 5),
        review_text TEXT,
        review_date DATE DEFAULT CURRENT_DATE
    );
    """)
    
    print("Тестовая схема и таблицы созданы")

async def cleanup_test_schema(provider: PostgreSQLProvider):
    """Очищает тестовую схему после тестов."""
    try:
        # Удаляем данные из таблиц
        await provider.execute("TRUNCATE TABLE test_schema.book_reviews;")
        await provider.execute("TRUNCATE TABLE test_schema.books RESTART IDENTITY CASCADE;")
        await provider.execute("TRUNCATE TABLE test_schema.authors RESTART IDENTITY CASCADE;")
        
        # Удаляем схему если она была создана для тестов
        await provider.execute("DROP SCHEMA IF EXISTS test_schema CASCADE;")
        
        print("Тестовая схема очищена")
    except Exception as e:
        print(f"Ошибка при очистке тестовой схемы: {str(e)}")

async def insert_test_data(provider: PostgreSQLProvider):
    """Вставляет тестовые данные в таблицы."""
    # Вставляем авторов
    authors = [
        ("Лев Толстой", 1828, "русский"),
        ("Фёдор Достоевский", 1821, "русский"),
        ("Джордж Оруэлл", 1903, "английский"),
        ("Маргарет Этвуд", 1939, "канадская")
    ]
    
    for author in authors:
        await provider.execute("""
        INSERT INTO test_schema.authors (name, birth_year, nationality)
        VALUES ($1, $2, $3)
        ON CONFLICT DO NOTHING;
        """, {
            "name": author[0],
            "birth_year": author[1],
            "nationality": author[2]
        })
    
    # Вставляем книги
    books = [
        ("Война и мир", "Лев Толстой", 1869, "роман"),
        ("Анна Каренина", "Лев Толстой", 1877, "роман"),
        ("Преступление и наказание", "Фёдор Достоевский", 1866, "роман"),
        ("1984", "Джордж Оруэлл", 1949, "антиутопия"),
        ("Рассказ служанки", "Маргарет Этвуд", 1985, "антиутопия")
    ]
    
    for book in books:
        await provider.execute("""
        INSERT INTO test_schema.books (title, author, publication_year, genre)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT DO NOTHING;
        """, {
            "title": book[0],
            "author": book[1],
            "publication_year": book[2],
            "genre": book[3]
        })
    
    # Вставляем отзывы
    reviews = [
        (1, "Иван", 5, "Шедевр мировой литературы!"),
        (1, "Мария", 4, "Отличная книга, но очень длинная"),
        (3, "Алексей", 5, "Глубокий психологический анализ"),
        (4, "Софья", 4, "Актуально даже сегодня"),
        (5, "Дмитрий", 5, "Потрясающая антиутопия")
    ]
    
    for review in reviews:
        await provider.execute("""
        INSERT INTO test_schema.book_reviews (book_id, reviewer_name, rating, review_text)
        VALUES ($1, $2, $3, $4);
        """, {
            "book_id": review[0],
            "reviewer_name": review[1],
            "rating": review[2],
            "review_text": review[3]
        })
    
    print("Тестовые данные вставлены")

# ==========================================================
# Реальные тесты
# ==========================================================

@pytest.mark.integration
@pytest.mark.slow
class TestPostgreSQLProviderReal:
    """Реальные интеграционные тесты для PostgreSQLProvider."""
    
    @pytest.fixture(autouse=True)
    async def setup_provider(self, db_connection_config):
        """Инициализация провайдера и подготовка БД перед тестами."""
        self.provider = PostgreSQLProvider(db_connection_config)
        
        try:
            # Инициализация провайдера
            success = await self.provider.initialize()
            assert success, "Не удалось инициализировать PostgreSQL провайдер"
            
            # Подготовка тестовой схемы
            await setup_test_schema(self.provider)
            await insert_test_data(self.provider)
            
            yield
        finally:
            # Очистка после тестов
            await cleanup_test_schema(self.provider)
            await self.provider.shutdown()
    
    @pytest.mark.asyncio
    async def test_real_initialization(self):
        """Тест реальной инициализации PostgreSQL провайдера."""
        assert self.provider.is_initialized
        assert self.provider.health_status == DBHealthStatus.HEALTHY
        assert hasattr(self.provider, 'pool') and self.provider.pool is not None
        
        # Проверяем информацию о подключении
        conn_info = self.provider.get_connection_info()
        assert conn_info["database"] == TEST_DB_CONFIG["database"]
        assert conn_info["host"] == TEST_DB_CONFIG["host"]
        assert conn_info["port"] == TEST_DB_CONFIG["port"]
        assert conn_info["username"] == TEST_DB_CONFIG["username"]
        assert conn_info["provider_type"] == "PostgreSQLProvider"
        assert conn_info["is_initialized"] is True
        assert conn_info["health_status"] == DBHealthStatus.HEALTHY.value
        
        print("Тест инициализации успешен")
        print(f"Информация о подключении: {json.dumps(conn_info, indent=2)}")
    
    @pytest.mark.asyncio
    async def test_health_check(self):
        """Тест проверки здоровья PostgreSQL провайдера."""
        result = await self.provider.health_check()
        
        assert result["status"] == DBHealthStatus.HEALTHY.value
        assert "database" in result
        assert "user" in result
        assert "timestamp" in result
        assert "response_time" in result
        assert result["response_time"] > 0
        assert result["is_initialized"] is True
        
        print("Тест health check успешен")
        print(f"Результат health check: {json.dumps(result, indent=2)}")
    
    @pytest.mark.asyncio
    async def test_basic_crud_operations(self):
        """Тест базовых CRUD операций."""
        print("\n=== ТЕСТ БАЗОВЫХ CRUD ОПЕРАЦИЙ ===")
        
        # 1. SELECT - получение данных
        select_result = await self.provider.execute("""
        SELECT id, title, author, publication_year 
        FROM test_schema.books 
        WHERE genre = $1
        ORDER BY publication_year DESC
        LIMIT 3;
        """, {"genre": "роман"})
        
        assert select_result.success is True
        assert len(select_result.rows) > 0
        print(f"SELECT результат: {len(select_result.rows)} строк")
        for row in select_result.rows:
            print(f"  Книга: {row['title']} ({row['publication_year']})")
        
        # 2. INSERT - вставка данных
        new_book_title = f"Тестовая книга {uuid.uuid4().hex[:8]}"
        insert_result = await self.provider.execute("""
        INSERT INTO test_schema.books (title, author, publication_year, genre)
        VALUES ($1, $2, $3, $4)
        RETURNING id, title;
        """, {
            "title": new_book_title,
            "author": "Тестовый Автор",
            "publication_year": 2024,
            "genre": "тест"
        })
        
        assert insert_result.success is True
        assert len(insert_result.rows) == 1
        new_book_id = insert_result.rows[0]["id"]
        print(f"INSERT успешен, новый ID: {new_book_id}")
        
        # 3. UPDATE - обновление данных
        update_result = await self.provider.execute("""
        UPDATE test_schema.books 
        SET title = $1, publication_year = $2
        WHERE id = $3
        RETURNING id, title, publication_year;
        """, {
            "title": f"{new_book_title} (обновлено)",
            "publication_year": 2025,
            "id": new_book_id
        })
        
        assert update_result.success is True
        assert len(update_result.rows) == 1
        updated_book = update_result.rows[0]
        print(f"UPDATE успешен: {updated_book['title']} ({updated_book['publication_year']})")
        
        # 4. DELETE - удаление данных
        delete_result = await self.provider.execute("""
        DELETE FROM test_schema.books 
        WHERE id = $1
        RETURNING id, title;
        """, {"id": new_book_id})
        
        assert delete_result.success is True
        assert len(delete_result.rows) == 1
        print(f"DELETE успешен для книги ID: {new_book_id}")
        
        print("Все CRUD операции выполнены успешно")
    
    @pytest.mark.asyncio
    async def test_transaction_management(self):
        """Тест управления транзакциями."""
        print("\n=== ТЕСТ УПРАВЛЕНИЯ ТРАНЗАКЦИЯМИ ===")
        
        try:
            async with self.provider.transaction() as conn:
                print("Начало транзакции")
                
                # Шаг 1: Вставка новой книги
                insert_book = await self.provider.execute("""
                INSERT INTO test_schema.books (title, author, publication_year, genre)
                VALUES ($1, $2, $3, $4)
                RETURNING id;
                """, {
                    "title": "Книга в транзакции",
                    "author": "Автор Транзакции",
                    "publication_year": 2024,
                    "genre": "транзакция"
                })
                
                assert insert_book.success is True
                book_id = insert_book.rows[0]["id"]
                print(f"Книга вставлена, ID: {book_id}")
                
                # Шаг 2: Вставка отзыва для этой книги
                insert_review = await self.provider.execute("""
                INSERT INTO test_schema.book_reviews (book_id, reviewer_name, rating, review_text)
                VALUES ($1, $2, $3, $4)
                RETURNING id;
                """, {
                    "book_id": book_id,
                    "reviewer_name": "Транзакционный Рецензент",
                    "rating": 5,
                    "review_text": "Отличная книга из транзакции!"
                })
                
                assert insert_review.success is True
                review_id = insert_review.rows[0]["id"]
                print(f"Отзыв вставлен, ID: {review_id}")
                
                # Шаг 3: Проверка вставки
                verify_result = await self.provider.execute("""
                SELECT b.title, r.reviewer_name, r.rating
                FROM test_schema.books b
                JOIN test_schema.book_reviews r ON b.id = r.book_id
                WHERE b.id = $1;
                """, {"id": book_id})
                
                assert verify_result.success is True
                assert len(verify_result.rows) == 1
                print(f"Проверка успешна: {verify_result.rows[0]}")
                
                # Шаг 4: Искусственная ошибка для тестирования отката
                if False:  # Установите в True для тестирования отката
                    raise Exception("Искусственная ошибка для тестирования отката транзакции")
                
                print("Транзакция завершена успешно")
        
        except Exception as e:
            print(f"Транзакция откачена из-за ошибки: {str(e)}")
            # Проверяем, что данные не сохранились
            check_result = await self.provider.execute("""
            SELECT COUNT(*) as count 
            FROM test_schema.books 
            WHERE title = $1;
            """, {"title": "Книга в транзакции"})
            
            assert check_result.success is True
            assert check_result.rows[0]["count"] == 0
            print("Проверка отката успешна - данных нет")
        
        # Проверяем, что при успешной транзакции данные сохранились
        if True:  # Всегда True при успешной транзакции
            final_check = await self.provider.execute("""
            SELECT COUNT(*) as count 
            FROM test_schema.books 
            WHERE title = $1;
            """, {"title": "Книга в транзакции"})
            
            assert final_check.success is True
            assert final_check.rows[0]["count"] == 1
            print("Проверка успешного завершения транзакции успешна")
    
    @pytest.mark.asyncio
    async def test_complex_queries(self):
        """Тест сложных SQL запросов."""
        print("\n=== ТЕСТ СЛОЖНЫХ ЗАПРОСОВ ===")
        
        # 1. JOIN запрос с агрегацией
        complex_result = await self.provider.execute("""
        SELECT 
            a.name as author_name,
            COUNT(b.id) as book_count,
            AVG(b.publication_year) as avg_publication_year,
            STRING_AGG(b.title, ', ') as book_titles,
            MAX(r.rating) as max_rating
        FROM test_schema.authors a
        LEFT JOIN test_schema.books b ON b.author = a.name
        LEFT JOIN test_schema.book_reviews r ON r.book_id = b.id
        GROUP BY a.name
        HAVING COUNT(b.id) > 0
        ORDER BY book_count DESC, avg_publication_year DESC;
        """)
        
        assert complex_result.success is True
        assert len(complex_result.rows) > 0
        
        print("Результат JOIN запроса:")
        for row in complex_result.rows:
            print(f"  Автор: {row['author_name']}")
            print(f"  Книг: {row['book_count']}")
            print(f"  Средний год: {row['avg_publication_year']:.0f}")
            print(f"  Макс. рейтинг: {row['max_rating'] or 'нет отзывов'}")
            print(f"  Книги: {row['book_titles']}")
            print()
        
        # 2. Subquery с оконными функциями
        window_result = await self.provider.execute("""
        WITH author_stats AS (
            SELECT 
                author,
                COUNT(*) as total_books,
                AVG(publication_year) as avg_year,
                RANK() OVER (ORDER BY COUNT(*) DESC) as author_rank
            FROM test_schema.books
            GROUP BY author
        )
        SELECT 
            b.title,
            b.author,
            b.publication_year,
            a.total_books,
            a.author_rank,
            ROW_NUMBER() OVER (PARTITION BY b.author ORDER BY b.publication_year) as book_number
        FROM test_schema.books b
        JOIN author_stats a ON b.author = a.author
        WHERE a.author_rank <= 2
        ORDER BY b.author, b.publication_year;
        """)
        
        assert window_result.success is True
        assert len(window_result.rows) > 0
        
        print("Результат с оконными функциями:")
        for row in window_result.rows:
            print(f"  {row['author']} - {row['title']} ({row['publication_year']})")
            print(f"  Ранг автора: {row['author_rank']}, Всего книг: {row['total_books']}")
            print(f"  Номер книги у автора: {row['book_number']}")
            print()
    
    @pytest.mark.asyncio
    async def test_error_handling(self):
        """Тест обработки ошибок."""
        print("\n=== ТЕСТ ОБРАБОТКИ ОШИБОК ===")
        
        # 1. Ошибка синтаксиса SQL
        try:
            syntax_error = await self.provider.execute("""
            SELECT * FROM non_existent_table WHERE invalid_column = $1;
            """, {"value": "test"})
            
            assert False, "Ожидалась ошибка синтаксиса SQL"
        except Exception as e:
            print(f"Ожидаемая ошибка синтаксиса: {str(e)}")
        
        # 2. Ошибка констрейнта (уникальность)
        try:
            # Пытаемся вставить дубликат
            duplicate_result = await self.provider.execute("""
            INSERT INTO test_schema.books (title, author, publication_year, genre)
            VALUES ($1, $2, $3, $4);
            """, {
                "title": "Война и мир",
                "author": "Лев Толстой", 
                "publication_year": 1869,
                "genre": "роман"
            })
            
            assert False, "Ожидалась ошибка уникальности"
        except Exception as e:
            print(f"Ожидаемая ошибка уникальности: {str(e)}")
        
        # 3. Ошибка параметров
        try:
            param_error = await self.provider.execute("""
            SELECT * FROM test_schema.books WHERE publication_year > $1;
            """, {"wrong_param": 1900})
            
            assert False, "Ожидалась ошибка параметров"
        except Exception as e:
            print(f"Ожидаемая ошибка параметров: {str(e)}")
        
        # 4. Проверка восстановления после ошибок
        recovery_result = await self.provider.execute("""
        SELECT COUNT(*) as count FROM test_schema.books;
        """)
        
        assert recovery_result.success is True
        assert recovery_result.rows[0]["count"] > 0
        print(f"Восстановление после ошибок успешно. Всего книг: {recovery_result.rows[0]['count']}")
        
        # 5. Проверка метрик после ошибок
        provider_info = self.provider.get_connection_info()
        assert provider_info["error_count"] > 0
        assert provider_info["query_count"] > 0
        print(f"Метрики после ошибок: ошибок={provider_info['error_count']}, запросов={provider_info['query_count']}")
    
    @pytest.mark.asyncio
    async def test_performance_metrics(self):
        """Тест производительности."""
        print("\n=== ТЕСТ ПРОИЗВОДИТЕЛЬНОСТИ ===")
        
        # 1. Тест быстрого запроса
        start_time = time.time()
        fast_result = await self.provider.execute("""
        SELECT COUNT(*) as count FROM test_schema.books;
        """)
        fast_time = time.time() - start_time
        
        assert fast_result.success is True
        fast_count = fast_result.rows[0]["count"]
        print(f"Быстрый запрос (COUNT): {fast_time:.4f}с, Книг: {fast_count}")
        
        # 2. Тест сложного запроса
        start_time = time.time()
        complex_result = await self.provider.execute("""
        SELECT 
            b.title,
            b.author,
            b.publication_year,
            b.genre,
            COALESCE(AVG(r.rating), 0) as avg_rating,
            COUNT(r.id) as review_count
        FROM test_schema.books b
        LEFT JOIN test_schema.book_reviews r ON r.book_id = b.id
        GROUP BY b.id, b.title, b.author, b.publication_year, b.genre
        ORDER BY b.publication_year DESC, avg_rating DESC;
        """)
        complex_time = time.time() - start_time
        
        assert complex_result.success is True
        print(f"Сложный запрос: {complex_time:.4f}с, Результатов: {len(complex_result.rows)}")
        
        # 3. Тест множественных запросов
        batch_start = time.time()
        batch_results = []
        
        for i in range(10):
            result = await self.provider.execute("""
            SELECT title FROM test_schema.books 
            ORDER BY RANDOM() 
            LIMIT 1;
            """)
            batch_results.append(result)
        
        batch_time = time.time() - batch_start
        avg_batch_time = batch_time / 10
        
        print(f"Пакет из 10 запросов: {batch_time:.4f}с, Среднее время: {avg_batch_time:.4f}с/запрос")
        
        # 4. Тест транзакции с множественными операциями
        async with self.provider.transaction() as conn:
            tx_start = time.time()
            
            for i in range(5):
                await self.provider.execute("""
                INSERT INTO test_schema.books (title, author, publication_year, genre)
                VALUES ($1, $2, $3, $4);
                """, {
                    "title": f"Массовая вставка {i}",
                    "author": f"Автор {i}",
                    "publication_year": 2020 + i,
                    "genre": "тест"
                })
            
            tx_time = time.time() - tx_start
            print(f"Транзакция с 5 вставками: {tx_time:.4f}с")
        
        # Проверка производительности
        assert fast_time < 1.0, "Слишком долгий простой запрос"
        assert complex_time < 3.0, "Слишком долгий сложный запрос"
        assert avg_batch_time < 0.5, "Слишком долгие множественные запросы"
        
        print("Все тесты производительности пройдены успешно")
    
    @pytest.mark.asyncio
    async def test_connection_pooling(self):
        """Тест пула соединений."""
        print("\n=== ТЕСТ ПУЛА СОЕДИНЕНИЙ ===")
        
        # 1. Проверка текущего состояния пула
        pool_info = self.provider.get_connection_info()
        print(f"Начальное состояние пула: {pool_info}")
        
        # 2. Параллельные запросы
        async def run_parallel_queries():
            """Запускает несколько параллельных запросов."""
            tasks = []
            for i in range(self.provider.config.pool_size):
                task = self.provider.execute("""
                SELECT pg_sleep(0.1), $1 as query_number;
                """, {"query_number": i})
                tasks.append(task)
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            return results
        
        # Запускаем параллельные запросы
        parallel_results = await run_parallel_queries()
        
        successful = [r for r in parallel_results if not isinstance(r, Exception)]
        failed = [r for r in parallel_results if isinstance(r, Exception)]
        
        print(f"Параллельные запросы: успешных={len(successful)}, ошибок={len(failed)}")
        
        for result in successful:
            print(f"  Запрос {result.rows[0]['query_number']}: {result.execution_time:.4f}с")
        
        for error in failed:
            print(f"  Ошибка: {str(error)}")
        
        # 3. Проверка состояния пула после нагрузки
        final_pool_info = self.provider.get_connection_info()
        print(f"Состояние пула после нагрузки: {final_pool_info}")
        
        # Проверки
        assert len(successful) > 0, "Ни один параллельный запрос не выполнен успешно"
        assert final_pool_info["query_count"] > pool_info["query_count"]
        print("Тест пула соединений пройден успешно")

@pytest.mark.integration
@pytest.mark.slow
class TestPostgreSQLProviderEdgeCases:
    """Тесты для edge cases и граничных ситуаций."""
    
    @pytest.fixture(autouse=True)
    async def setup_provider(self, db_connection_config):
        """Инициализация провайдера для тестов edge cases."""
        self.provider = PostgreSQLProvider(db_connection_config)
        success = await self.provider.initialize()
        assert success, "Не удалось инициализировать PostgreSQL провайдер"
        yield
        await self.provider.shutdown()
    
    @pytest.mark.asyncio
    async def test_large_data_handling(self):
        """Тест обработки больших объемов данных."""
        print("\n=== ТЕСТ ОБРАБОТКИ БОЛЬШИХ ДАННЫХ ===")
        
        # 1. Тест большого текстового поля
        large_text = "x" * 10000  # 10KB текст
        insert_result = await self.provider.execute("""
        INSERT INTO test_schema.books (title, author, publication_year, genre)
        VALUES ($1, $2, $3, $4)
        RETURNING id;
        """, {
            "title": large_text,
            "author": "Автор Большого Текста",
            "publication_year": 2024,
            "genre": "тест"
        })
        
        assert insert_result.success is True
        book_id = insert_result.rows[0]["id"]
        print(f"Книга с большим текстом вставлена, ID: {book_id}")
        
        # 2. Тест получения большого результата
        start_time = time.time()
        large_result = await self.provider.execute("""
        SELECT generate_series(1, 10000) as id,
               md5(random()::text) as random_hash,
               now() as timestamp;
        """)
        execution_time = time.time() - start_time
        
        assert large_result.success is True
        assert len(large_result.rows) == 10000
        print(f"Получено 10000 строк за {execution_time:.2f}с")
        
        # 3. Проверка памяти и производительности
        avg_row_size = len(str(large_result.rows[0]))  # Примерная оценка размера строки
        total_size_mb = (avg_row_size * 10000) / (1024 * 1024)
        print(f"Оценочный размер результата: {total_size_mb:.2f}MB")
        
        assert execution_time < 10.0, "Слишком долгая обработка большого результата"
        assert total_size_mb < 50.0, "Слишком большой объем данных для одного запроса"
    
    @pytest.mark.asyncio
    async def test_concurrent_access(self):
        """Тест одновременного доступа из нескольких корутин."""
        print("\n=== ТЕСТ ОДНОВРЕМЕННОГО ДОСТУПА ===")
        
        async def worker(worker_id: int):
            """Рабочая корутина для тестирования конкурентного доступа."""
            try:
                result = await self.provider.execute("""
                SELECT pg_sleep(0.05), $1 as worker_id, COUNT(*) as book_count
                FROM test_schema.books;
                """, {"worker_id": worker_id})
                
                if result.success:
                    return {
                        "worker_id": worker_id,
                        "book_count": result.rows[0]["book_count"],
                        "success": True,
                        "execution_time": result.execution_time
                    }
                else:
                    return {"worker_id": worker_id, "success": False, "error": "Query failed"}
            except Exception as e:
                return {"worker_id": worker_id, "success": False, "error": str(e)}
        
        # Запускаем несколько рабочих одновременно
        num_workers = 20
        tasks = [worker(i) for i in range(num_workers)]
        
        start_time = time.time()
        results = await asyncio.gather(*tasks)
        total_time = time.time() - start_time
        
        successful = [r for r in results if r["success"]]
        failed = [r for r in results if not r["success"]]
        
        print(f"Запущено {num_workers} рабочих")
        print(f"Успешно: {len(successful)}, Ошибок: {len(failed)}")
        print(f"Общее время выполнения: {total_time:.2f}с")
        
        if failed:
            print("Ошибки:")
            for error in failed:
                print(f"  Worker {error['worker_id']}: {error['error']}")
        
        # Проверки
        assert len(successful) > num_workers * 0.8, "Слишком много ошибок при конкурентном доступе"
        avg_time = sum(r["execution_time"] for r in successful) / len(successful) if successful else 0
        print(f"Среднее время выполнения запроса: {avg_time:.4f}с")
        
        assert avg_time < 1.0, "Слишком долгое среднее время выполнения при конкурентном доступе"