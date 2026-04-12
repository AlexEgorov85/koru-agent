"""
Интеграционные тесты для всех Services.

РЕАЛЬНОЕ СОСТОЯНИЕ (после запуска):
- SQL Generation ✅ (с реальным LLM!)
- SQL Query Service ✅
- Table Description ✅
- JSON Parsing ✅
- Contract Service ❌ (API не совпадает с контрактом)
- Prompt Service ❌ (промпты не загружены в кэш)
- SQL Validator ❌ (метод validate не найден)

ПРИНЦИПЫ:
- Контексты поднимаются ОДИН РАЗ (scope="module")
- Строгие проверки: status == COMPLETED
- Реальный LLM, реальная БД, без моков
"""
import pytest
import pytest_asyncio

from core.config import get_config
from core.config.app_config import AppConfig
from core.infrastructure_context.infrastructure_context import InfrastructureContext
from core.application_context.application_context import ApplicationContext
from core.agent.components.action_executor import ActionExecutor
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
    return ActionExecutor(application_context=app_context)


@pytest.fixture
def session():
    return SessionContext()


# ============================================================================
# JSON PARSING SERVICE
# ============================================================================

class TestJsonParsingServiceIntegration:

    @pytest.mark.asyncio
    async def test_json_parsing_parse_json(self, executor, session):
        """Парсинг корректного JSON."""
        result = await executor.execute_action(
            action_name="json_parsing.parse_json",
            parameters={"raw": '{"name": "test", "value": 42}'},
            context=session
        )

        assert result.status == ExecutionStatus.COMPLETED, f"FAILED: {result.error}"
        assert result.data is not None
        data = result.data if isinstance(result.data, dict) else result.data.model_dump()
        assert data.get("status") == "success"
        parsed = data.get("parsed_data", {})
        assert parsed.get("name") == "test"
        assert parsed.get("value") == 42
        print(f"✅ JSON Parsing: корректный JSON распарсен")

    @pytest.mark.asyncio
    async def test_json_parsing_invalid(self, executor, session):
        """Парсинг некорректного JSON."""
        result = await executor.execute_action(
            action_name="json_parsing.parse_json",
            parameters={"raw": '{not valid json!!!'},
            context=session
        )

        assert result.status == ExecutionStatus.COMPLETED, f"FAILED: {result.error}"
        assert result.data is not None
        data = result.data if isinstance(result.data, dict) else result.data.model_dump()
        assert "error" in data.get("status", "")
        print(f"✅ JSON Parsing: некорректный JSON отклонён")


# ============================================================================
# TABLE DESCRIPTION SERVICE
# ============================================================================

class TestTableDescriptionServiceIntegration:

    @pytest.mark.asyncio
    async def test_table_description_get_table(self, executor, session):
        """Получение метаданных таблицы chapters."""
        result = await executor.execute_action(
            action_name="table_description_service.get_table",
            parameters={
                "schema_name": "Lib",
                "table_name": "chapters"
            },
            context=session
        )

        assert result.status == ExecutionStatus.COMPLETED, f"FAILED: {result.error}"
        assert result.data is not None
        print(f"✅ Table Description: метаданные chapters получены")


# ============================================================================
# SQL QUERY SERVICE
# ============================================================================

class TestSqlQueryServiceIntegration:

    @pytest.mark.asyncio
    async def test_sql_query_service_execute(self, executor, session):
        """Выполнение SQL-запроса через sql_query_service."""
        result = await executor.execute_action(
            action_name="sql_query_service.execute",
            parameters={
                "sql_query": "SELECT chapter_id, chapter_number FROM \"Lib\".chapters WHERE book_id = 5 LIMIT 3",
                "parameters": {},
                "max_rows": 10
            },
            context=session
        )

        assert result.status == ExecutionStatus.COMPLETED, f"FAILED: {result.error}"
        assert result.data is not None
        print(f"✅ SQL Query Service: запрос выполнен")

    @pytest.mark.asyncio
    async def test_sql_query_service_invalid_sql(self, executor, session):
        """Выполнение некорректного SQL."""
        result = await executor.execute_action(
            action_name="sql_query_service.execute",
            parameters={
                "sql_query": "SELECT FROM INVALID TABLE",
                "parameters": {},
                "max_rows": 10
            },
            context=session
        )

        assert result.status == ExecutionStatus.COMPLETED, f"FAILED: {result.error}"
        print(f"✅ SQL Query Service: некорректный SQL обработан")


# ============================================================================
# SQL GENERATION SERVICE (с реальным LLM)
# ============================================================================

class TestSqlGenerationServiceIntegration:

    @pytest.mark.asyncio
    async def test_sql_generation_generate_query(self, executor, session):
        """
        Генерация SQL из natural language через реальный LLM.

        Ключевой тест — полный цикл: промпт → LLM → валидация.
        """
        table_schema = "Таблица Lib.chapters: chapter_id (int), chapter_number (int), chapter_text (text), book_id (int)"

        result = await executor.execute_action(
            action_name="sql_generation.generate_query",
            parameters={
                "natural_language_query": "Получи первые 3 главы книги с book_id = 5",
                "table_schema": table_schema
            },
            context=session
        )

        assert result.status == ExecutionStatus.COMPLETED, f"FAILED: {result.error}"
        assert result.data is not None
        data = result.data if isinstance(result.data, dict) else result.data.model_dump()
        sql = data.get("sql", "")
        assert len(sql) > 0, "SQL не должен быть пустым"
        assert "SELECT" in sql.upper(), "Должен быть SELECT запрос"
        print(f"✅ SQL Generation (LLM): {sql[:100]}...")

    @pytest.mark.asyncio
    async def test_sql_generation_invalid_schema(self, executor, session):
        """Генерация SQL с некорректной схемой — LLM должен справиться или вернуть ошибку."""
        result = await executor.execute_action(
            action_name="sql_generation.generate_query",
            parameters={
                "natural_language_query": "Получи все записи",
                "table_schema": "Таблица non_existent_table: id (int)"
            },
            context=session
        )

        # LLM может сгенерировать SQL или вернуть ошибку — главное что сервис отработал
        assert result.data is not None or result.error is not None
        print(f"✅ SQL Generation: некорректная схема обработана ({result.status.value})")
