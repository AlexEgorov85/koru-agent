"""
Примеры юнит-тестов с использованием mock-интерфейсов.

ДЕМОНСТРАЦИЯ:
- Как тестировать навыки без реальной инфраструктуры
- Как проверять вызовы интерфейсов через assert
- Как изолировать тесты от внешних зависимостей

ЗАПУСК:
```bash
pytest tests/unit/example/test_skill_with_mocks.py -v
```
"""
import pytest
from typing import Dict, Any, List

from tests.mocks.interfaces import MockDatabase, MockLLM, MockCache
from core.interfaces import DatabaseInterface, LLMInterface, CacheInterface


# ============================================================
# Пример 1: Простой тест с MockDatabase
# ============================================================

class ExampleSkillWithDB:
    """
    Пример навыка, который работает с БД.
    
    В реальном проекте это был бы BookLibrarySkill или аналогичный.
    """
    
    def __init__(
        self,
        name: str,
        db_port: DatabaseInterface,
        cache_port: CacheInterface
    ):
        self.name = name
        self._db_port = db_port
        self._cache_port = cache_port
        self._initialized = False
    
    async def initialize(self) -> bool:
        self._initialized = True
        return True
    
    async def search_books(self, query: str) -> List[Dict[str, Any]]:
        """Поиск книг по названию."""
        # Проверка кэша
        cached = await self._cache_port.get(f"search:{query}")
        if cached:
            return cached
        
        # Запрос к БД
        sql = "SELECT * FROM books WHERE title LIKE :query"
        params = {"query": f"%{query}%"}
        results = await self._db_port.query(sql, params)
        
        # Кэширование результата
        await self._cache_port.set(f"search:{query}", results, ttl=300)
        
        return results
    
    async def get_book_count(self) -> int:
        """Получить количество книг."""
        sql = "SELECT COUNT(*) as count FROM books"
        result = await self._db_port.query(sql)
        return result[0]["count"] if result else 0


class TestExampleSkillWithDB:
    """Тесты навыка с mock-портами."""
    
    @pytest.fixture
    def mock_db(self) -> DatabaseInterface:
        """Создать mock БД с предопределёнными результатами."""
        return MockDatabase(predefined_results={
            "SELECT * FROM books": [
                {"id": 1, "title": "Test Book 1", "author": "Author 1"},
                {"id": 2, "title": "Test Book 2", "author": "Author 2"},
            ],
            "SELECT COUNT": [
                {"count": 42}
            ]
        })
    
    @pytest.fixture
    def mock_cache(self) -> CacheInterface:
        """Создать mock кэша."""
        return MockCache()
    
    @pytest.fixture
    def skill(self, mock_db: DatabaseInterface, mock_cache: CacheInterface):
        """Создать навык для тестирования."""
        return ExampleSkillWithDB(
            name="example_skill",
            db_port=mock_db,
            cache_port=mock_cache
        )
    
    async def test_search_books_returns_results(
        self,
        skill: ExampleSkillWithDB,
        mock_db: MockDatabase
    ):
        """Тест: поиск книг возвращает результаты."""
        # Arrange
        await skill.initialize()
        
        # Act
        results = await skill.search_books("Test")
        
        # Assert
        assert len(results) == 2
        assert results[0]["title"] == "Test Book 1"
        
        # Проверка что БД запрос был выполнен
        assert len(mock_db.queries_executed) == 1
        assert "SELECT * FROM books" in mock_db.queries_executed[0]["sql"]
    
    async def test_search_books_uses_cache(
        self,
        skill: ExampleSkillWithDB,
        mock_db: MockDatabase,
        mock_cache: MockCache
    ):
        """Тест: повторный поиск использует кэш."""
        # Arrange
        await skill.initialize()
        
        # Первый запрос (без кэша)
        await skill.search_books("Test")
        assert len(mock_db.queries_executed) == 1
        
        # Act: Второй запрос (должен использовать кэш)
        results = await skill.search_books("Test")
        
        # Assert
        assert len(results) == 2
        assert len(mock_db.queries_executed) == 1  # БД не вызывалась повторно!
        assert mock_cache.hits == 1  # Второе чтение - hit
        assert mock_cache.misses == 1  # Первое чтение - miss
    
    async def test_get_book_count(
        self,
        skill: ExampleSkillWithDB,
        mock_db: MockDatabase
    ):
        """Тест: получение количества книг."""
        # Arrange
        await skill.initialize()
        
        # Act
        count = await skill.get_book_count()
        
        # Assert
        assert count == 42
        assert len(mock_db.queries_executed) == 1


# ============================================================
# Пример 2: Тест с MockLLM
# ============================================================

class ExampleSkillWithLLM:
    """Пример навыка, который использует LLM."""
    
    def __init__(
        self,
        name: str,
        llm_port: LLMInterface
    ):
        self.name = name
        self._llm_port = llm_port
        self._initialized = False
    
    async def initialize(self) -> bool:
        self._initialized = True
        return True
    
    async def analyze_text(self, text: str) -> Dict[str, Any]:
        """Анализ текста через LLM."""
        messages = [
            {"role": "system", "content": "You are a text analyst."},
            {"role": "user", "content": f"Analyze: {text}"}
        ]
        
        response = await self._llm_port.generate(
            messages=messages,
            temperature=0.7
        )
        
        return {
            "analysis": response,
            "tokens_used": await self._llm_port.count_tokens(messages)
        }
    
    async def summarize(self, text: str) -> str:
        """Краткое содержание текста."""
        messages = [
            {"role": "system", "content": "Summarize the text."},
            {"role": "user", "content": text}
        ]
        
        return await self._llm_port.generate(
            messages=messages,
            temperature=0.5,
            max_tokens=100
        )


class TestExampleSkillWithLLM:
    """Тесты навыка с mock LLM."""
    
    @pytest.fixture
    def mock_llm(self) -> LLMInterface:
        """Создать mock LLM с предопределёнными ответами."""
        return MockLLM(
            predefined_responses=[
                "This text is positive and optimistic.",
                "Summary: The main points are..."
            ],
            delay_seconds=0.0  # Без задержки для тестов
        )
    
    @pytest.fixture
    def skill(self, mock_llm: LLMInterface):
        """Создать навык для тестирования."""
        return ExampleSkillWithLLM(
            name="example_llm_skill",
            llm_port=mock_llm
        )
    
    async def test_analyze_text_calls_llm(
        self,
        skill: ExampleSkillWithLLM,
        mock_llm: MockLLM
    ):
        """Тест: анализ текста вызывает LLM."""
        # Arrange
        await skill.initialize()
        
        # Act
        result = await skill.analyze_text("This is a great day!")
        
        # Assert
        assert result["analysis"] == "This text is positive and optimistic."
        assert mock_llm.call_count == 1
    
    async def test_summarize_records_messages(
        self,
        skill: ExampleSkillWithLLM,
        mock_llm: MockLLM
    ):
        """Тест: summarize записывает историю сообщений."""
        # Arrange
        await skill.initialize()
        
        # Act
        await skill.summarize("Long text here...")
        
        # Assert
        assert len(mock_llm.messages_history) == 1
        messages = mock_llm.messages_history[0]
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
    
    async def test_multiple_calls_cycle_responses(
        self,
        skill: ExampleSkillWithLLM,
        mock_llm: MockLLM
    ):
        """Тест: множественные вызовы циклически используют ответы."""
        # Arrange
        await skill.initialize()
        
        # Act
        result1 = await skill.analyze_text("Text 1")
        result2 = await skill.analyze_text("Text 2")
        
        # Assert
        assert mock_llm.call_count == 2
        # Ответы циклически повторяются
        assert result1["analysis"] != result2["analysis"] or len(mock_llm._responses) == 1


# ============================================================
# Пример 3: Тест с комбинацией портов
# ============================================================

class ExampleComplexSkill:
    """Пример сложного навыка с несколькими портами."""
    
    def __init__(
        self,
        name: str,
        db_port: DatabaseInterface,
        llm_port: LLMInterface,
        cache_port: CacheInterface
    ):
        self.name = name
        self._db_port = db_port
        self._llm_port = llm_port
        self._cache_port = cache_port
        self._initialized = False
    
    async def initialize(self) -> bool:
        self._initialized = True
        return True
    
    async def process_query(self, query: str) -> Dict[str, Any]:
        """
        Комплексная обработка запроса:
        1. Проверка кэша
        2. Запрос к БД
        3. Анализ через LLM
        4. Кэширование результата
        """
        # Кэш
        cached = await self._cache_port.get(f"query:{query}")
        if cached:
            return {"result": cached, "from_cache": True}
        
        # БД
        sql = "SELECT content FROM documents WHERE query = :query"
        db_results = await self._db_port.query(sql, {"query": query})
        
        if not db_results:
            return {"result": "No data found", "from_cache": False}
        
        # LLM анализ
        messages = [
            {"role": "user", "content": f"Process: {db_results[0]['content']}"}
        ]
        llm_result = await self._llm_port.generate(messages)
        
        # Кэширование
        await self._cache_port.set(f"query:{query}", llm_result, ttl=600)
        
        return {
            "result": llm_result,
            "from_cache": False,
            "db_rows": len(db_results)
        }


class TestExampleComplexSkill:
    """Тесты сложного навыка с комбинацией портов."""
    
    @pytest.fixture
    def mock_db(self) -> DatabaseInterface:
        return MockDatabase(predefined_results={
            "SELECT content FROM documents": [
                {"content": "Document content here"}
            ]
        })
    
    @pytest.fixture
    def mock_llm(self) -> LLMInterface:
        return MockLLM(
            predefined_responses=["Processed by LLM"]
        )
    
    @pytest.fixture
    def mock_cache(self) -> CacheInterface:
        return MockCache()
    
    @pytest.fixture
    def skill(
        self,
        mock_db: DatabaseInterface,
        mock_llm: LLMInterface,
        mock_cache: CacheInterface
    ):
        return ExampleComplexSkill(
            name="complex_skill",
            db_port=mock_db,
            llm_port=mock_llm,
            cache_port=mock_cache
        )
    
    async def test_process_query_uses_all_ports(
        self,
        skill: ExampleComplexSkill,
        mock_db: MockDatabase,
        mock_llm: MockLLM,
        mock_cache: MockCache
    ):
        """Тест: обработка запроса использует все порты."""
        # Arrange
        await skill.initialize()
        
        # Act
        result = await skill.process_query("test query")
        
        # Assert
        assert result["from_cache"] is False
        assert result["result"] == "Processed by LLM"
        
        # Проверка вызовов портов
        assert len(mock_db.queries_executed) == 1
        assert mock_llm.call_count == 1
        assert mock_cache.misses == 1  # Первый вызов - miss (кэш пуст)
        # hits = 0, т.к. после set() не было get()
    
    async def test_process_query_uses_cache_on_second_call(
        self,
        skill: ExampleComplexSkill,
        mock_db: MockDatabase,
        mock_llm: MockLLM,
        mock_cache: CacheInterface
    ):
        """Тест: повторный вызов использует кэш."""
        # Arrange
        await skill.initialize()
        
        # Первый вызов
        await skill.process_query("test")
        
        # Act: Второй вызов
        result = await skill.process_query("test")
        
        # Assert
        assert result["from_cache"] is True
        assert len(mock_db.queries_executed) == 1  # БД не вызывалась повторно
        assert mock_llm.call_count == 1  # LLM не вызывался повторно
        assert mock_cache.hits == 1  # Второе чтение - hit (первое был miss)


# ============================================================
# Пример 4: Тестирование ошибок
# ============================================================

class TestErrorHandling:
    """Тесты обработки ошибок с mock-портами."""
    
    async def test_skill_handles_db_failure(
        self,
    ):
        """Тест: навык корректно обрабатывает ошибку БД."""
        # Arrange
        mock_db = MockDatabase(should_fail=True)
        mock_cache = MockCache()
        
        skill = ExampleSkillWithDB(
            name="test_skill",
            db_port=mock_db,
            cache_port=mock_cache
        )
        await skill.initialize()
        
        # Act & Assert
        with pytest.raises(ConnectionError, match="Mock database"):
            await skill.search_books("test")
    
    async def test_skill_handles_llm_timeout(
        self,
    ):
        """Тест: навык корректно обрабатывает таймаут LLM."""
        # Arrange
        mock_llm = MockLLM(should_fail=True)
        
        skill = ExampleSkillWithLLM(
            name="test_skill",
            llm_port=mock_llm
        )
        await skill.initialize()
        
        # Act & Assert
        with pytest.raises(TimeoutError, match="Mock LLM"):
            await skill.analyze_text("test")
