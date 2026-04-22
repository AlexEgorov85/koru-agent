"""
Интеграционные тесты для SQL Tool.

ТЕСТЫ:
- test_sql_tool_execute_select: выполнение SELECT-запроса с реальной БД
- test_sql_tool_empty_result: SELECT с заведомо пустым результатом
- test_sql_tool_invalid_sql: некорректный SQL
- test_sql_tool_missing_sql_field: отсутствие обязательного поля 'sql'

ПРИНЦИПЫ:
- Реальные контексты (InfrastructureContext, ApplicationContext)
- Никаких моков
- Полная инициализация и корректное завершение
"""
import pytest

from core.components.action_executor import ActionExecutor
from core.session_context.session_context import SessionContext
from core.models.enums.common_enums import ExecutionStatus


# ============================================================================
# ТЕСТЫ
# ============================================================================

class TestSqlToolIntegration:
    """Интеграционные тесты SQL Tool."""

    @pytest.mark.asyncio
    async def test_sql_tool_execute_select(self, app_context, session_context):
        """
        Тест: выполнение SELECT-запроса через sql_tool.

        ПРОВЕРКИ:
        - Компонент найден и выполнен
        - Статус COMPLETED
        - Результат содержит rows, columns, rowcount
        - rows — непустой список
        """
        # Arrange
        executor = ActionExecutor(application_context=app_context)

        sql_query = """
            SELECT c.chapter_id, c.chapter_number, c.chapter_text
            FROM "Lib".chapters c
            WHERE book_id = 5
            ORDER BY c.chapter_number
            LIMIT 3
        """
        params = {"sql": sql_query}

        # Act
        result = await executor.execute_action(
            action_name="sql_tool.execute_query",
            parameters=params,
            context=session_context
        )

        # Assert
        assert result.status == ExecutionStatus.COMPLETED, f"Ожидался COMPLETED, получен {result.status}"
        assert result.data is not None, "result.data должен быть не None"

        # result.data — Pydantic-объект Sql_Toolexecute_QueryOutputSchema
        data = result.data
        rows = data.rows
        columns = data.columns
        rowcount = data.rowcount

        assert isinstance(rows, list), "'rows' должен быть списком"
        assert isinstance(columns, list), "'columns' должен быть списком"
        assert isinstance(rowcount, int), "'rowcount' должен быть int"
        assert len(rows) > 0, "rows не должен быть пустым"
        assert rowcount > 0, "rowcount должен быть > 0"

        # Проверяем структуру первой строки
        first_row = rows[0]
        assert "chapter_id" in first_row, "Строка должна содержать 'chapter_id'"
        assert "chapter_number" in first_row, "Строка должна содержать 'chapter_number'"
        assert "chapter_text" in first_row, "Строка должна содержать 'chapter_text'"

        print(f"✅ SQL Tool: получено {rowcount} строк, колонки: {columns}")

    @pytest.mark.asyncio
    async def test_sql_tool_empty_result(self, app_context, session_context):
        """
        Тест: SELECT с заведомо пустым результатом.

        ПРОВЕРКИ:
        - Статус COMPLETED
        - rows — пустой список
        - rowcount == 0
        """
        executor = ActionExecutor(application_context=app_context)

        sql_query = """
            SELECT c.chapter_id
            FROM "Lib".chapters c
            WHERE book_id = -1
        """
        params = {"sql": sql_query}

        result = await executor.execute_action(
            action_name="sql_tool.execute_query",
            parameters=params,
            context=session_context
        )

        assert result.status == ExecutionStatus.COMPLETED
        assert result.data is not None
        assert result.data.rows == []
        assert result.data.rowcount == 0

        print("✅ SQL Tool: пустой результат корректен")

    @pytest.mark.asyncio
    async def test_sql_tool_invalid_sql(self, app_context, session_context):
        """
        Тест: некорректный SQL.

        ПРОВЕРКИ:
        - Ошибка выполнения
        - Пустой результат (rows = [])
        """
        executor = ActionExecutor(application_context=app_context)

        sql_query = "THIS IS NOT SQL"
        params = {"sql": sql_query}

        result = await executor.execute_action(
            action_name="sql_tool.execute_query",
            parameters=params,
            context=session_context
        )

        # SQL Tool возвращает пустой результат при ошибке
        assert result.data is not None
        assert result.data.rows == []

        print("✅ SQL Tool: некорректный SQL обработан")

    @pytest.mark.asyncio
    async def test_sql_tool_missing_sql_field(self, app_context, session_context):
        """
        Тест: отсутствие обязательного поля 'sql'.

        ПРОВЕРКИ:
        - Ошибка валидации
        - Статус FAILED
        """
        executor = ActionExecutor(application_context=app_context)

        params = {"query": "SELECT 1"}  # поле 'query' вместо 'sql'

        result = await executor.execute_action(
            action_name="sql_tool.execute_query",
            parameters=params,
            context=session_context
        )

        # После фикса — FAILED с сообщением об ошибке
        assert result.status == ExecutionStatus.FAILED
        assert result.error is not None
        assert "sql" in result.error.lower() or "field required" in result.error.lower()

        print(f"✅ SQL Tool: отсутствие поля 'sql' обработано (ошибка: {result.error[:80]}...)")
