"""
Интеграционные тесты для SQLTool.

ПРИНЦИПЫ:
- SELECT тесты без транзакции (только чтение)
- INSERT/UPDATE/DELETE тесты с BEGIN/ROLLBACK
- Реальная БД, реальные данные

ЗАПУСК:
    pytest tests/integration/test_sql_tool.py -v
"""
import pytest
from core.models.enums.common_enums import ComponentType


class TestSqlToolRead:
    """Тесты для SQLTool (только SELECT)."""

    @pytest.mark.asyncio
    async def test_select_books(self, app_context, session_context):
        """Тест простого SELECT запроса."""
        skill = app_context.components.get(ComponentType.TOOL, "sql_tool")
        if skill is None:
            pytest.skip("SQLTool не найден")

        caps = skill.get_capabilities()
        cap = next((c for c in caps if c.name == "sql_tool.execute"), None)
        if cap is None:
            pytest.skip("Capability execute не найдена")

        # Простой SELECT
        params = {
            "query": "SELECT * FROM books LIMIT 5",
            "side_effects_enabled": False
        }

        result = await skill.execute(
            capability=cap,
            parameters=params,
            context=session_context,
            execution_context=None
        )

        assert result.status.value == "completed", f"Ошибка: {result.error}"
        assert result.data is not None
        assert "rows" in result.data
        assert len(result.data["rows"]) <= 5

        print(f"[OK] SELECT вернул {len(result.data['rows'])} строк")

    @pytest.mark.asyncio
    async def test_select_with_parameters(self, app_context, session_context):
        """Тест SELECT с параметрами."""
        skill = app_context.components.get(ComponentType.TOOL, "sql_tool")
        if skill is None:
            pytest.skip("SQLTool не найден")

        caps = skill.get_capabilities()
        cap = next((c for c in caps if c.name == "sql_tool.execute"), None)
        if cap is None:
            pytest.skip("Capability execute не найдена")

        # SELECT с параметром
        params = {
            "query": "SELECT * FROM books WHERE author LIKE :author LIMIT 10",
            "parameters": {"author": "%Пушкин%"},
            "side_effects_enabled": False
        }

        result = await skill.execute(
            capability=cap,
            parameters=params,
            context=session_context,
            execution_context=None
        )

        assert result.status.value == "completed", f"Ошибка: {result.error}"
        assert result.data is not None
        
        # Проверяем что все книги содержат "Пушкин"
        for row in result.data["rows"]:
            assert "Пушкин" in row.get("author", ""), f"Неверный автор: {row.get('author')}"

        print(f"[OK] Найдено {len(result.data['rows'])} книг Пушкина")


class TestSqlToolWrite:
    """Тесты для SQLTool с записью (BEGIN/ROLLBACK)."""

    @pytest.mark.asyncio
    async def test_insert_with_rollback(self, app_context, session_context, db_transaction):
        """Тест INSERT с автоматическим откатом."""
        skill = app_context.components.get(ComponentType.TOOL, "sql_tool")
        if skill is None:
            pytest.skip("SQLTool не найден")

        caps = skill.get_capabilities()
        cap = next((c for c in caps if c.name == "sql_tool.execute"), None)
        if cap is None:
            pytest.skip("Capability execute не найдена")

        # INSERT (будет откачен после теста)
        params = {
            "query": """
                INSERT INTO books (title, author, genre, year) 
                VALUES ('Тестовая книга', 'Тестовый Автор', 'Тест', 2024)
            """,
            "side_effects_enabled": True
        }

        result = await skill.execute(
            capability=cap,
            parameters=params,
            context=session_context,
            execution_context=None
        )

        # INSERT должен выполниться успешно (в рамках транзакции)
        assert result.status.value == "completed", f"Ошибка: {result.error}"
        
        # Проверяем что запись добавлена (в рамках транзакции)
        verify_params = {
            "query": "SELECT * FROM books WHERE title = 'Тестовая книга'",
            "side_effects_enabled": False
        }
        
        verify_result = await skill.execute(
            capability=cap,
            parameters=verify_params,
            context=session_context,
            execution_context=None
        )
        
        assert verify_result.status.value == "completed"
        assert len(verify_result.data["rows"]) == 1, "Запись не найдена в транзакции"

        print("[OK] INSERT выполнен (будет откачен после теста)")

    @pytest.mark.asyncio
    async def test_update_with_rollback(self, app_context, session_context, db_transaction):
        """Тест UPDATE с автоматическим откатом."""
        skill = app_context.components.get(ComponentType.TOOL, "sql_tool")
        if skill is None:
            pytest.skip("SQLTool не найден")

        caps = skill.get_capabilities()
        cap = next((c for c in caps if c.name == "sql_tool.execute"), None)
        if cap is None:
            pytest.skip("Capability execute не найдена")

        # UPDATE существующей книги (будет откачен)
        params = {
            "query": """
                UPDATE books SET title = 'Обновлённое название' 
                WHERE id = 1
            """,
            "side_effects_enabled": True
        }

        result = await skill.execute(
            capability=cap,
            parameters=params,
            context=session_context,
            execution_context=None
        )

        assert result.status.value == "completed", f"Ошибка: {result.error}"
        
        # Проверяем что обновление произошло (в рамках транзакции)
        verify_params = {
            "query": "SELECT title FROM books WHERE id = 1",
            "side_effects_enabled": False
        }
        
        verify_result = await skill.execute(
            capability=cap,
            parameters=verify_params,
            context=session_context,
            execution_context=None
        )
        
        assert verify_result.status.value == "completed"
        assert verify_result.data["rows"][0]["title"] == "Обновлённое название"

        print("[OK] UPDATE выполнен (будет откачен после теста)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
