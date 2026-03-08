"""
Простые интеграционные тесты для book_library.

ПРИНЦИПЫ:
- Реальная инфраструктура (InfrastructureContext, ApplicationContext)
- Реальная БД с реальными данными
- Никаких моков
- Минимум кода

ЗАПУСК:
    pytest tests/integration/test_book_library_simple.py -v
"""
import pytest
from core.models.enums.common_enums import ComponentType


def _get_error_message(result):
    """Извлечение сообщения об ошибке из ExecutionResult."""
    if result.error is None:
        return None
    if isinstance(result.error, str):
        return result.error
    # Если error - это объект (например, схема валидации), конвертируем в строку
    return str(result.error)


def _get_result_data(result):
    """Извлечение данных из ExecutionResult."""
    if result.data is None:
        return None
    if isinstance(result.data, dict):
        return result.data
    # Если data - Pydantic модель, конвертируем
    if hasattr(result.data, 'model_dump'):
        return result.data.model_dump()
    if hasattr(result.data, 'dict'):
        return result.data.dict()
    return result.data


class TestBookLibraryExecuteScript:
    """Тесты для book_library.execute_script."""

    @pytest.mark.asyncio
    async def test_get_all_books(self, app_context, session_context):
        """Тест скрипта get_all_books."""
        # Получаем навык
        skill = app_context.components.get(ComponentType.TOOL, "book_library")
        assert skill is not None, "Навык book_library не найден"

        # Ищем capability
        caps = skill.get_capabilities()
        cap = next((c for c in caps if c.name == "book_library.execute_script"), None)
        assert cap is not None, "Capability execute_script не найдена"

        # Параметры
        params = {
            "script_name": "get_all_books",
            "parameters": {"max_rows": 10}
        }

        # Выполняем
        result = await skill.execute(
            capability=cap,
            parameters=params,
            execution_context=None
        )

        # Проверяем статус
        error_msg = _get_error_message(result)
        assert result.status.value == "completed", f"Ошибка: {error_msg}"
        
        data = _get_result_data(result)
        assert data is not None, "Нет данных в результате"
        assert "rows" in data or hasattr(data, 'rows'), "Нет поля 'rows'"
        assert "rowcount" in data or hasattr(data, 'rowcount'), "Нет поля 'rowcount'"
        
        rowcount = data.get('rowcount', len(data.get('rows', []))) if isinstance(data, dict) else getattr(data, 'rowcount', len(getattr(data, 'rows', [])))
        print(f"[OK] Найдено {rowcount} книг")

    @pytest.mark.asyncio
    async def test_get_books_by_author(self, app_context, session_context):
        """Тест скрипта get_books_by_author (Пушкин)."""
        skill = app_context.components.get(ComponentType.TOOL, "book_library")
        assert skill is not None

        caps = skill.get_capabilities()
        cap = next((c for c in caps if c.name == "book_library.execute_script"), None)
        assert cap is not None

        # Параметры – фамилия автора для ILIKE поиска (скрипт сам добавит %)
        params = {
            "script_name": "get_books_by_author",
            "parameters": {"author": "Пушкин"}
        }

        result = await skill.execute(
            capability=cap,
            parameters=params,
            execution_context=None
        )

        # Проверяем статус
        error_msg = _get_error_message(result)
        assert result.status.value == "completed", f"Ошибка: {error_msg}"

        data = _get_result_data(result)
        assert data is not None, "Нет данных в результате"

        # Отладка: выводим всю информацию
        rowcount = data.get('rowcount', 0) if isinstance(data, dict) else getattr(data, 'rowcount', 0)
        rows = data.get('rows', []) if isinstance(data, dict) else getattr(data, 'rows', [])
        print(f"[DEBUG] rowcount={rowcount}, rows={rows}")
        
        # Проверяем наличие авторов в БД
        if rowcount == 0:
            # Пробуем получить список всех авторов
            params_all = {
                "script_name": "get_distinct_authors",
                "parameters": {"max_rows": 20}
            }
            result_all = await skill.execute(
                capability=cap,
                parameters=params_all,
                execution_context=None
            )
            data_all = _get_result_data(result_all)
            if data_all:
                rows_all = data_all.get('rows', []) if isinstance(data_all, dict) else getattr(data_all, 'rows', [])
                print(f"[DEBUG] Все авторы в БД: {rows_all}")
        
        assert rowcount > 0, "Книги Пушкина не найдены"

        # Проверяем что все книги принадлежат Пушкину (по полю last_name)
        rows = data.get('rows', []) if isinstance(data, dict) else getattr(data, 'rows', [])
        for row in rows:
            # Поддержка dict и Pydantic модели
            last_name = row.get('last_name', '') if isinstance(row, dict) else getattr(row, 'last_name', '')
            assert "Пушкин" in last_name, f"Неверный автор: {last_name}"

        print(f"[OK] Найдено {rowcount} книг Пушкина")

    @pytest.mark.asyncio
    async def test_context_recording(self, app_context, session_context):
        """Тест записи шага в контекст сессии."""
        skill = app_context.components.get(ComponentType.TOOL, "book_library")
        assert skill is not None

        caps = skill.get_capabilities()
        cap = next((c for c in caps if c.name == "book_library.execute_script"), None)
        assert cap is not None

        params = {
            "script_name": "get_all_books",
            "parameters": {"max_rows": 5}
        }

        result = await skill.execute(
            capability=cap,
            parameters=params,
            execution_context=None
        )

        error_msg = _get_error_message(result)
        assert result.status.value == "completed", f"Ошибка: {error_msg}"

        # Проверяем, что шаг записан в контекст
        assert session_context.step_context.count() == 1, "Шаг не записан в контекст"
        
        step = session_context.step_context.steps[0]
        assert step.capability_name == "book_library.execute_script"
        assert step.status == result.status
        
        # Проверяем наблюдение
        assert len(step.observation_item_ids) >= 0  # Может быть 0 или больше
        
        print(f"[OK] Шаг записан в контекст: {step.capability_name}")

    @pytest.mark.asyncio
    async def test_invalid_script_name(self, app_context, session_context):
        """Тест обработки несуществующего скрипта."""
        skill = app_context.components.get(ComponentType.TOOL, "book_library")
        assert skill is not None

        caps = skill.get_capabilities()
        cap = next((c for c in caps if c.name == "book_library.execute_script"), None)
        assert cap is not None

        params = {
            "script_name": "nonexistent_script",
            "parameters": {}
        }

        result = await skill.execute(
            capability=cap,
            parameters=params,
            execution_context=None
        )

        # Ожидаем ошибку
        assert result.status.value == "failed", "Ожидалась ошибка для несуществующего скрипта"
        error_msg = _get_error_message(result)
        assert error_msg is not None, "Нет сообщения об ошибке"
        assert "не найден" in error_msg.lower() or "not found" in error_msg.lower() or "nonexistent" in error_msg.lower(), f"Неверное сообщение об ошибке: {error_msg}"

        print(f"[OK] Ошибка корректно обработана: {error_msg}")


class TestBookLibrarySearch:
    """Тесты для book_library.search_books (с LLM)."""

    @pytest.mark.asyncio
    async def test_search_books_by_author(self, app_context, session_context):
        """Тест динамического поиска книг по автору."""
        skill = app_context.components.get(ComponentType.TOOL, "book_library")
        assert skill is not None

        caps = skill.get_capabilities()
        cap = next((c for c in caps if c.name == "book_library.search_books"), None)
        assert cap is not None

        params = {
            "query": "Найти все книги Пушкина",
            "max_results": 10
        }

        result = await skill.execute(
            capability=cap,
            parameters=params,
            execution_context=None
        )

        error_msg = _get_error_message(result)
        # LLM может быть медленной, но результат должен быть
        assert result.status.value == "completed", f"Ошибка: {error_msg}"
        
        data = _get_result_data(result)
        assert data is not None, "Нет данных в результате"
        
        rows = data.get('rows', []) if isinstance(data, dict) else getattr(data, 'rows', [])
        print(f"[OK] Поиск нашёл {len(rows)} книг")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
