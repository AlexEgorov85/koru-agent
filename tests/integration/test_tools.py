"""
Интеграционные тесты для всех Tools.

ТЕСТЫ:
  SQL Tool (4):
  - test_sql_tool_execute_select: SELECT с результатами
  - test_sql_tool_empty_result: SELECT без результатов
  - test_sql_tool_invalid_sql: некорректный SQL
  - test_sql_tool_missing_sql_field: отсутствие поля 'sql'

  Vector Search (4):
  - test_vector_search_search_books: поиск по книгам
  - test_vector_search_search_authors: поиск по авторам
  - test_vector_search_min_score: поиск с фильтром по score
  - test_vector_search_empty_query: пустой query (ожидается FAILED)

ПРИНЦИПЫ:
- Контексты поднимаются ОДИН РАЗ (scope="module")
- Строгие проверки: status == COMPLETED
- Реальные контексты, без моков
"""
import pytest
import pytest_asyncio
from pathlib import Path

from core.config import get_config
from core.config.app_config import AppConfig
from core.infrastructure_context.infrastructure_context import InfrastructureContext
from core.application_context.application_context import ApplicationContext
from core.session_context.session_context import SessionContext
from core.models.enums.common_enums import ExecutionStatus


# ============================================================================
# ФИКСТУРЫ (scope="module" — один подъём на ВСЕ тесты)
# ============================================================================

@pytest.fixture(scope="module")
def config():
    return get_config(profile='prod', data_dir='data')


@pytest_asyncio.fixture(scope="module")
async def infrastructure(config):
    infra = InfrastructureContext(config)
    await infra.initialize()
    yield infra
    await infra.shutdown()


@pytest_asyncio.fixture(scope="module")
async def app_context(infrastructure):
    app_config = AppConfig.from_discovery(
        profile="prod",
        data_dir=infrastructure.config.data_dir
    )
    ctx = ApplicationContext(
        infrastructure_context=infrastructure,
        config=app_config,
        profile="prod"
    )
    await ctx.initialize()
    yield ctx
    await ctx.shutdown()


@pytest_asyncio.fixture(scope="module")
async def executor(app_context):
    from core.components.action_executor import ActionExecutor
    return ActionExecutor(application_context=app_context)


@pytest.fixture
def session():
    return SessionContext()


# ============================================================================
# SQL TOOL
# ============================================================================

class TestSqlToolIntegration:
    """SQL Tool — 4 теста."""

    @pytest.mark.asyncio
    async def test_sql_tool_execute_select(self, executor, session):
        sql_query = """
            SELECT c.chapter_id, c.chapter_number, c.chapter_text
            FROM "Lib".chapters c
            WHERE book_id = 5
            ORDER BY c.chapter_number
            LIMIT 3
        """
        result = await executor.execute_action(
            action_name="sql_tool.execute_query",
            parameters={"sql": sql_query},
            context=session
        )

        assert result.status == ExecutionStatus.COMPLETED, f"FAILED: {result.error}"
        assert result.data is not None
        assert len(result.data.rows) > 0
        assert result.data.rowcount > 0
        assert "chapter_id" in result.data.rows[0]
        print(f"✅ SQL: {result.data.rowcount} строк, колонки: {result.data.columns}")

    @pytest.mark.asyncio
    async def test_sql_tool_empty_result(self, executor, session):
        result = await executor.execute_action(
            action_name="sql_tool.execute_query",
            parameters={"sql": "SELECT c.chapter_id FROM \"Lib\".chapters c WHERE book_id = -1"},
            context=session
        )

        assert result.status == ExecutionStatus.COMPLETED, f"FAILED: {result.error}"
        assert result.data.rows == []
        assert result.data.rowcount == 0
        print("✅ SQL: пустой результат")

    @pytest.mark.asyncio
    async def test_sql_tool_invalid_sql(self, executor, session):
        result = await executor.execute_action(
            action_name="sql_tool.execute_query",
            parameters={"sql": "THIS IS NOT SQL"},
            context=session
        )

        assert result.status == ExecutionStatus.COMPLETED, f"FAILED: {result.error}"
        assert result.data.rows == []
        print("✅ SQL: некорректный SQL обработан")

    @pytest.mark.asyncio
    async def test_sql_tool_missing_sql_field(self, executor, session):
        result = await executor.execute_action(
            action_name="sql_tool.execute_query",
            parameters={"query": "SELECT 1"},
            context=session
        )

        assert result.status == ExecutionStatus.FAILED
        assert "sql" in result.error.lower() or "field required" in result.error.lower()
        print("✅ SQL: missing field 'sql' → FAILED")


# ============================================================================
# VECTOR SEARCH TOOL
# ============================================================================

class TestVectorSearchToolIntegration:
    """Vector Search Tool — 4 теста (books + authors)."""

    @pytest.mark.asyncio
    async def test_vector_search_search_books(self, executor, session):
        """Поиск по книгам."""
        result = await executor.execute_action(
            action_name="vector_search.search",
            parameters={"query": "главный герой романа", "top_k": 5, "min_score": 0.3, "source": "books"},
            context=session
        )

        assert result.status == ExecutionStatus.COMPLETED, f"FAILED: {result.error}"
        assert result.data is not None
        data = result.data if isinstance(result.data, dict) else result.data.model_dump()
        assert data.get("total_found", 0) >= 0
        print(f"✅ Vector Search (books): {data.get('total_found', 0)} результатов")

    @pytest.mark.asyncio
    async def test_vector_search_search_authors(self, executor, session):
        """Поиск по авторам."""
        result = await executor.execute_action(
            action_name="vector_search.search",
            parameters={"query": "Пушкин", "top_k": 5, "min_score": 0.3, "source": "authors"},
            context=session
        )

        assert result.status == ExecutionStatus.COMPLETED, f"FAILED: {result.error}"
        assert result.data is not None
        data = result.data if isinstance(result.data, dict) else result.data.model_dump()
        assert data.get("total_found", 0) > 0, f"Ожидались результаты поиска по автору 'Пушкин', получено: {data}"
        print(f"✅ Vector Search (authors): {data['total_found']} результатов")

    @pytest.mark.asyncio
    async def test_vector_search_min_score(self, executor, session):
        """Поиск с высоким порогом — мало результатов."""
        result = await executor.execute_action(
            action_name="vector_search.search",
            parameters={"query": "роман", "top_k": 3, "min_score": 0.9, "source": "books"},
            context=session
        )

        assert result.status == ExecutionStatus.COMPLETED, f"FAILED: {result.error}"
        print(f"✅ Vector Search (high score): поиск выполнен")

    @pytest.mark.asyncio
    async def test_vector_search_empty_query(self, executor, session):
        """Пустой query — ожидается FAILED (контракт требует min_length=1)."""
        result = await executor.execute_action(
            action_name="vector_search.search",
            parameters={"query": "", "top_k": 3, "source": "books"},
            context=session
        )

        assert result.status == ExecutionStatus.FAILED
        assert "query" in result.error.lower() or "string_too_short" in result.error.lower()
        print("✅ Vector Search: пустой query → FAILED (валидация)")
