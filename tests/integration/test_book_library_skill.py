#!/usr/bin/env python3
"""
Интеграционные тесты для навыка book_library.

Тестируются:
1. Выполнение заготовленных скриптов (static)
2. Динамическая генерация SQL (dynamic)
3. Валидация контрактов
4. Обработка ошибок

ЗАПУСК:
    python -m pytest tests/integration/test_book_library_skill.py -v

ЗАПУСК С ПОКРЫТИЕМ:
    python -m pytest tests/integration/test_book_library_skill.py --cov=core/application/skills/book_library --cov-report=html
"""
import pytest
import asyncio
import sys
from pathlib import Path
from typing import Dict, Any

# Добавим путь к корню проекта
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


# ============================================================================
# ФИКСТУРЫ
# ============================================================================

@pytest.fixture(scope="session")
def event_loop():
    """Создание event loop для асинхронных тестов."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def app_contexts():
    """
    Инициализация контекстов для тестирования.
    
    Возвращает словарь с контекстами:
    - config: SystemConfig
    - infra: InfrastructureContext
    - app: ApplicationContext
    """
    from core.config.models import SystemConfig
    from core.infrastructure.context.infrastructure_context import InfrastructureContext
    from core.application.context.application_context import ApplicationContext
    
    config = SystemConfig(data_dir='data')
    infra = InfrastructureContext(config)
    await infra.initialize()
    
    app_context = await ApplicationContext.create_from_registry(
        infrastructure_context=infra,
        profile="prod"
    )
    
    yield {
        "config": config,
        "infra": infra,
        "app": app_context
    }
    
    # Завершение работы
    await infra.shutdown()


@pytest.fixture
async def book_library_skill(app_contexts):
    """Получение экземпляра навыка book_library."""
    app_context = app_contexts["app"]
    skill = app_context.get_skill("book_library")
    
    if skill is None:
        pytest.skip("Навык book_library не найден в реестре")
    
    # Инициализация навыка
    await skill.initialize()
    
    yield skill


# ============================================================================
# ТЕСТЫ STATIC СКРИПТОВ
# ============================================================================

class TestStaticScripts:
    """Тесты для capability book_library.execute_script."""
    
    @pytest.mark.asyncio
    async def test_get_all_books_script(self, book_library_skill):
        """Тест скрипта get_all_books."""
        from core.models.data.execution import ExecutionResult
        
        result = await book_library_skill.execute(
            capability="book_library.execute_script",
            parameters={
                "script_name": "get_all_books",
                "parameters": {
                    "max_rows": 10
                }
            },
            execution_context=None
        )
        
        # Проверка результата
        assert isinstance(result, dict)
        assert "rows" in result
        assert "rowcount" in result
        assert result.get("execution_type") == "static"
        assert result.get("script_name") == "get_all_books"
        
        print(f"[OK] test_get_all_books_script: найдено {result['rowcount']} книг")
    
    @pytest.mark.asyncio
    async def test_get_books_by_author_script(self, book_library_skill):
        """Тест скрипта get_books_by_author."""
        result = await book_library_skill.execute(
            capability="book_library.execute_script",
            parameters={
                "script_name": "get_books_by_author",
                "parameters": {
                    "author": "Лев Толстой",
                    "max_rows": 20
                }
            },
            execution_context=None
        )
        
        assert isinstance(result, dict)
        assert "rows" in result
        assert "rowcount" in result
        assert result.get("execution_type") == "static"
        
        # Проверка что все книги принадлежат Толстому
        if result["rows"]:
            for book in result["rows"]:
                assert "Толстой" in book.get("author", "")
        
        print(f"[OK] test_get_books_by_author_script: найдено {result['rowcount']} книг Толстого")
    
    @pytest.mark.asyncio
    async def test_get_books_by_genre_script(self, book_library_skill):
        """Тест скрипта get_books_by_genre."""
        result = await book_library_skill.execute(
            capability="book_library.execute_script",
            parameters={
                "script_name": "get_books_by_genre",
                "parameters": {
                    "genre": "Роман",
                    "max_rows": 20
                }
            },
            execution_context=None
        )
        
        assert isinstance(result, dict)
        assert "rows" in result
        assert result.get("execution_type") == "static"
        
        print(f"[OK] test_get_books_by_genre_script: найдено {result['rowcount']} романов")
    
    @pytest.mark.asyncio
    async def test_get_book_by_id_script(self, book_library_skill):
        """Тест скрипта get_book_by_id."""
        result = await book_library_skill.execute(
            capability="book_library.execute_script",
            parameters={
                "script_name": "get_book_by_id",
                "parameters": {
                    "book_id": 1
                }
            },
            execution_context=None
        )
        
        assert isinstance(result, dict)
        assert "rows" in result
        assert result.get("execution_type") == "static"
        
        # Проверка что найдена книга с ID=1
        if result["rows"]:
            assert result["rows"][0].get("id") == 1
        
        print(f"[OK] test_get_book_by_id_script: найдена книга с ID=1")
    
    @pytest.mark.asyncio
    async def test_count_books_by_author_script(self, book_library_skill):
        """Тест скрипта count_books_by_author."""
        result = await book_library_skill.execute(
            capability="book_library.execute_script",
            parameters={
                "script_name": "count_books_by_author",
                "parameters": {
                    "author": "Лев Толстой"
                }
            },
            execution_context=None
        )
        
        assert isinstance(result, dict)
        assert "rows" in result
        assert result.get("execution_type") == "static"
        
        print(f"[OK] test_count_books_by_author_script: {result['rows']}")
    
    @pytest.mark.asyncio
    async def test_invalid_script_name(self, book_library_skill):
        """Тест обработки несуществующего скрипта."""
        result = await book_library_skill.execute(
            capability="book_library.execute_script",
            parameters={
                "script_name": "nonexistent_script",
                "parameters": {}
            },
            execution_context=None
        )
        
        assert isinstance(result, dict)
        assert "error" in result
        assert "не найден" in result["error"].lower()
        
        print(f"[OK] test_invalid_script_name: ошибка корректно обработана")
    
    @pytest.mark.asyncio
    async def test_missing_required_parameter(self, book_library_skill):
        """Тест обработки отсутствующего обязательного параметра."""
        result = await book_library_skill.execute(
            capability="book_library.execute_script",
            parameters={
                "script_name": "get_books_by_author",
                "parameters": {
                    # author отсутствует
                    "max_rows": 10
                }
            },
            execution_context=None
        )
        
        assert isinstance(result, dict)
        assert "error" in result
        assert "отсутствуют" in result["error"].lower() or "обязательные" in result["error"].lower()
        
        print(f"[OK] test_missing_required_parameter: ошибка корректно обработана")


# ============================================================================
# ТЕСТЫ DYNAMIC ПОИСКА
# ============================================================================

class TestDynamicSearch:
    """Тесты для capability book_library.search_books."""
    
    @pytest.mark.asyncio
    async def test_search_books_by_author(self, book_library_skill):
        """Тест динамического поиска книг по автору."""
        result = await book_library_skill.execute(
            capability="book_library.search_books",
            parameters={
                "query": "Найти все книги Пушкина",
                "max_results": 10
            },
            execution_context=None
        )
        
        assert isinstance(result, dict)
        assert "rows" in result
        assert "rowcount" in result
        assert result.get("execution_type") == "dynamic"
        
        print(f"[OK] test_search_books_by_author: найдено {result['rowcount']} книг")
    
    @pytest.mark.asyncio
    async def test_search_books_by_genre(self, book_library_skill):
        """Тест динамического поиска книг по жанру."""
        result = await book_library_skill.execute(
            capability="book_library.search_books",
            parameters={
                "query": "Найти книги в жанре Роман",
                "max_results": 10
            },
            execution_context=None
        )
        
        assert isinstance(result, dict)
        assert "rows" in result
        assert result.get("execution_type") == "dynamic"
        
        print(f"[OK] test_search_books_by_genre: найдено {result['rowcount']} книг")
    
    @pytest.mark.asyncio
    async def test_search_books_by_year_range(self, book_library_skill):
        """Тест динамического поиска книг по диапазону лет."""
        result = await book_library_skill.execute(
            capability="book_library.search_books",
            parameters={
                "query": "Найти книги изданные между 1850 и 1900 годом",
                "max_results": 20
            },
            execution_context=None
        )
        
        assert isinstance(result, dict)
        assert "rows" in result
        assert result.get("execution_type") == "dynamic"
        
        print(f"[OK] test_search_books_by_year_range: найдено {result['rowcount']} книг")
    
    @pytest.mark.asyncio
    async def test_search_books_empty_query(self, book_library_skill):
        """Тест динамического поиска с пустым запросом."""
        result = await book_library_skill.execute(
            capability="book_library.search_books",
            parameters={
                "query": "",
                "max_results": 10
            },
            execution_context=None
        )
        
        assert isinstance(result, dict)
        assert "rows" in result
        assert result.get("execution_type") == "dynamic"
        
        print(f"[OK] test_search_books_empty_query: обработка пустого запроса")


# ============================================================================
# ТЕСТЫ ПРОИЗВОДИТЕЛЬНОСТИ
# ============================================================================

class TestPerformance:
    """Тесты производительности."""
    
    @pytest.mark.asyncio
    async def test_static_script_performance(self, book_library_skill):
        """Тест производительности static скрипта."""
        import time
        
        start = time.time()
        result = await book_library_skill.execute(
            capability="book_library.execute_script",
            parameters={
                "script_name": "get_all_books",
                "parameters": {"max_rows": 50}
            },
            execution_context=None
        )
        elapsed = time.time() - start
        
        assert elapsed < 1.0, f"Static скрипт выполняется слишком долго: {elapsed}с"
        assert isinstance(result, dict)
        
        print(f"[OK] test_static_script_performance: {elapsed*1000:.2f} мс")
    
    @pytest.mark.asyncio
    async def test_dynamic_search_performance(self, book_library_skill):
        """Тест производительности dynamic поиска."""
        import time
        
        start = time.time()
        result = await book_library_skill.execute(
            capability="book_library.search_books",
            parameters={
                "query": "Найти книги Толстого",
                "max_results": 10
            },
            execution_context=None
        )
        elapsed = time.time() - start
        
        # Dynamic поиск может быть медленнее из-за LLM
        assert elapsed < 5.0, f"Dynamic поиск выполняется слишком долго: {elapsed}с"
        assert isinstance(result, dict)
        
        print(f"[OK] test_dynamic_search_performance: {elapsed*1000:.2f} мс")


# ============================================================================
# ТЕСТЫ РЕЕСТРА СКРИПТОВ
# ============================================================================

class TestScriptsRegistry:
    """Тесты реестра скриптов."""
    
    def test_registry_import(self):
        """Тест импорта реестра скриптов."""
        from core.application.skills.book_library.scripts_registry import (
            SCRIPTS_REGISTRY,
            get_script,
            get_all_scripts,
            get_allowed_scripts_list,
            validate_script_parameters
        )
        
        assert SCRIPTS_REGISTRY is not None
        assert len(SCRIPTS_REGISTRY) > 0
        
        print(f"[OK] test_registry_import: загружено {len(SCRIPTS_REGISTRY)} скриптов")
    
    def test_get_script(self):
        """Тест получения скрипта из реестра."""
        from core.application.skills.book_library.scripts_registry import get_script
        
        script = get_script("get_all_books")
        assert script is not None
        assert script.name == "get_all_books"
        assert "SELECT" in script.sql
        
        print(f"[OK] test_get_script: скрипт получен")
    
    def test_validate_script_parameters(self):
        """Тест валидации параметров скрипта."""
        from core.application.skills.book_library.scripts_registry import validate_script_parameters
        
        # Валидные параметры
        is_valid, error = validate_script_parameters(
            "get_books_by_author",
            {"author": "Толстой", "max_rows": 10}
        )
        assert is_valid, f"Ожидалась валидность, получена ошибка: {error}"
        
        # Невалидные параметры (отсутствует author)
        is_valid, error = validate_script_parameters(
            "get_books_by_author",
            {"max_rows": 10}
        )
        assert not is_valid, "Ожидалась ошибка валидации"
        
        print(f"[OK] test_validate_script_parameters: валидация работает")


# ============================================================================
# ЗАПУСК ТЕСТОВ
# ============================================================================

if __name__ == "__main__":
    # Запуск тестов через pytest
    pytest.main([
        __file__,
        "-v",
        "--tb=short",
        "-s"  # Показывать print выводы
    ])
