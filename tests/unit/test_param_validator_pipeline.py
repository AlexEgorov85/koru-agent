"""Comprehensive тесты для ParamValidator — проверка пайплайна"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from core.components.skills.utils.param_validator import ParamValidator, fuzzy_match, levenshtein_distance
from core.models.data.execution import ExecutionResult, ExecutionStatus


class MockExecutionResult:
    """Mock результат от executor"""
    def __init__(self, rows=None, data=None):
        self.status = ExecutionStatus.COMPLETED
        self.data = data or MockData(rows=rows)
        self.error = None


class MockData:
    """Mock данные результата"""
    def __init__(self, rows=None):
        self.rows = rows or []


class TestParamValidatorPipeline:
    """Тесты пайплайна валидации — проверка переходов между этапами"""

    @pytest.fixture
    def create_tracked_executor(self):
        """Factory для создания tracked executor"""
        class TrackedExecutor:
            def __init__(self):
                self.calls = []
                self._response_map = {}

            def set_response(self, action_name, response):
                self._response_map[action_name] = response

            async def execute_action(self, action_name, parameters, context):
                self.calls.append({
                    "action": action_name,
                    "params": parameters
                })
                
                if action_name in self._response_map:
                    return self._response_map[action_name]
                
                # Default responses
                if action_name == "sql_query.execute":
                    return ExecutionResult(status=ExecutionStatus.COMPLETED, data=MockData(rows=[]))
                elif action_name == "vector_search.search":
                    return ExecutionResult(status=ExecutionStatus.COMPLETED, data={"results": [], "total_found": 0})
                return ExecutionResult(status=ExecutionStatus.COMPLETED, data=None)
        
        return TrackedExecutor

    # ========================================================================
    # ШАГ 1: Enum — проверяем что не делает лишних запросов
    # ========================================================================

    @pytest.mark.asyncio
    async def test_enum_found_stops_immediately(self, create_tracked_executor):
        """Enum нашёл значение — должен остановиться сразу, без SQL/Vector"""
        executor = create_tracked_executor()
        validator = ParamValidator(executor=executor)
        
        result = await validator.validate(
            param_value="Открыто",
            config={
                "type": "enum",
                "allowed_values": ["Открыто", "В работе"]
            }
        )
        
        assert result["valid"] is True
        assert result["corrected_value"] == "Открыто"
        assert result["warning"] is None
        
        # Не должно быть никаких вызовов executor
        assert len(executor.calls) == 0

    @pytest.mark.asyncio
    async def test_enum_not_found_continues_to_vector(self, create_tracked_executor):
        """Enum не нашёл — должен перейти к Vector"""
        executor = create_tracked_executor()
        validator = ParamValidator(executor=executor)
        
        result = await validator.validate(
            param_value="Закрыто",
            config={
                "type": "enum",
                "allowed_values": ["Открыто", "В работе"],
                "vector_source": "authors"
            }
        )
        
        # Enum не нашёл, но suggestions должны остаться
        assert result["valid"] is True
        assert result["suggestions"] == ["Открыто", "В работе"]

    # ========================================================================
    # ШАГ 1: SQL ILIKE — проверяем что находит и останавливается
    # ========================================================================

    @pytest.mark.asyncio
    async def test_sql_ilike_finds_value(self, create_tracked_executor):
        """SQL ILIKE нашёл значение через ILIKE — должен вернуть его"""
        executor = create_tracked_executor()
        executor.set_response(
            "sql_query.execute",
            ExecutionResult(status=ExecutionStatus.COMPLETED, data=MockData(rows=[["Пушкин"]]))
        )
        validator = ParamValidator(executor=executor)
        
        result = await validator.validate(
            param_value="Пушк",  # partial match
            config={
                "type": "search",
                "table": "authors",
                "search_fields": ["last_name"],
                "vector_source": "authors"
            }
        )
        
        assert result["valid"] is True
        assert result["corrected_value"] == "Пушкин"
        
        # Должен быть только SQL вызов, без Vector
        assert len(executor.calls) == 1
        assert executor.calls[0]["action"] == "sql_query.execute"
        assert "ILIKE" in executor.calls[0]["params"]["sql"]

    @pytest.mark.asyncio
    async def test_sql_not_found_continues_to_vector(self, create_tracked_executor):
        """SQL не нашёл — должен перейти к Vector"""
        executor = create_tracked_executor()
        # SQL возвращает пусто
        executor.set_response("sql_query.execute", 
            ExecutionResult(status=ExecutionStatus.COMPLETED, data=MockData(rows=[])))
        # Vector находит
        executor.set_response("vector_search.search",
            ExecutionResult(status=ExecutionStatus.COMPLETED, data={
                "results": [{"score": 0.85, "metadata": {"author": "Пушкин"}, "content": "Пушкин"}],
                "total_found": 1
            }))
        validator = ParamValidator(executor=executor)
        
        result = await validator.validate(
            param_value="русский классик",  # семантический запрос
            config={
                "type": "search",
                "table": "authors",
                "search_fields": ["last_name"],
                "vector_source": "authors"
            }
        )
        
        # SQL вызывается (не находит)
        assert len(executor.calls) >= 1
        assert executor.calls[0]["action"] == "sql_query.execute"
        # Vector должен был вызваться
        assert any(c["action"] == "vector_search.search" for c in executor.calls)
        # И должен найти
        assert result["corrected_value"] == "Пушкин"

    # ========================================================================
    # ШАГ 2: Vector search
    # ========================================================================

    @pytest.mark.asyncio
    async def test_vector_finds_with_high_score(self, create_tracked_executor):
        """Vector с высоким score находит значение"""
        executor = create_tracked_executor()
        # SQL пустой
        executor.set_response("sql_query.execute", 
            ExecutionResult(status=ExecutionStatus.COMPLETED, data=MockData(rows=[])))
        # Vector находит
        executor.set_response("vector_search.search",
            ExecutionResult(status=ExecutionStatus.COMPLETED, data={
                "results": [{"score": 0.85, "metadata": {"author": "Пушкин"}, "content": "Пушкин"}],
                "total_found": 1
            }))
        validator = ParamValidator(executor=executor)
        
        result = await validator.validate(
            param_value="русский классик",
            config={
                "type": "search",
                "table": "authors",
                "search_fields": ["last_name"],
                "vector_source": "authors",
                "vector_min_score": 0.7
            }
        )
        
        assert result["valid"] is True
        assert result["corrected_value"] == "Пушкин"
        
        # SQL вызывается, потом Vector
        vector_calls = [c for c in executor.calls if c["action"] == "vector_search.search"]
        assert len(vector_calls) == 1

    @pytest.mark.asyncio
    async def test_vector_low_score_continues_to_fuzzy(self, create_tracked_executor):
        """Vector нашёл но score < min_score — должен перейти к Fuzzy"""
        executor = create_tracked_executor()
        # SQL пустой
        executor.set_response("sql_query.execute", 
            ExecutionResult(status=ExecutionStatus.COMPLETED, data=MockData(rows=[])))
        # Vector находит но с низким score
        executor.set_response("vector_search.search",
            ExecutionResult(status=ExecutionStatus.COMPLETED, data={
                "results": [{"score": 0.5, "metadata": {"author": "Пушкин"}, "content": "Пушкин"}],
                "total_found": 1
            }))
        validator = ParamValidator(executor=executor)
        
        result = await validator.validate(
            param_value="слабый семантик",
            config={
                "type": "search",
                "table": "authors",
                "search_fields": ["last_name"],
                "vector_source": "authors",
                "vector_min_score": 0.7
            }
        )
        
        # Vector вызывается (с низким score)
        vector_calls = [c for c in executor.calls if c["action"] == "vector_search.search"]
        assert len(vector_calls) == 1
        
        # SQL для Fuzzy вызывается (получаем список всех значений)
        sql_calls = [c for c in executor.calls if c["action"] == "sql_query.execute"]
        assert len(sql_calls) >= 2  # ILIKE + Fuzzy list

    @pytest.mark.asyncio
    async def test_vector_not_found_continues_to_fuzzy(self, create_tracked_executor):
        """Vector не нашёл ничего — должен перейти к Fuzzy"""
        executor = create_tracked_executor()
        # SQL пустой
        executor.set_response("sql_query.execute", 
            ExecutionResult(status=ExecutionStatus.COMPLETED, data=MockData(rows=[])))
        # Vector пустой
        executor.set_response("vector_search.search",
            ExecutionResult(status=ExecutionStatus.COMPLETED, data={"results": [], "total_found": 0}))
        validator = ParamValidator(executor=executor)
        
        result = await validator.validate(
            param_value="не найти",
            config={
                "type": "search",
                "table": "authors",
                "search_fields": ["last_name"],
                "vector_source": "authors",
                "vector_min_score": 0.7
            }
        )
        
        # Проверяем что были вызовы
        assert len(executor.calls) > 0
        # Vector должен был вызваться
        vector_calls = [c for c in executor.calls if c["action"] == "vector_search.search"]
        assert len(vector_calls) == 1

    # ========================================================================
    # ШАГ 3: Fuzzy matching
    # ========================================================================

    @pytest.mark.asyncio
    async def test_fuzzy_finds_typo(self, create_tracked_executor):
        """Fuzzy находит опечатку"""
        executor = create_tracked_executor()
        # SQL возвращает пусто для ILIKE, но список для Fuzzy
        executor.set_response("sql_query.execute", 
            ExecutionResult(status=ExecutionStatus.COMPLETED, 
                data=MockData(rows=[["Пушкин"], ["Лермонтов"], ["Толстой"]])))
        executor.set_response("vector_search.search",
            ExecutionResult(status=ExecutionStatus.COMPLETED, data={"results": [], "total_found": 0}))
        validator = ParamValidator(executor=executor)
        
        result = await validator.validate(
            param_value="Пушкн",  # опечатка
            config={
                "type": "search",
                "table": "authors",
                "search_fields": ["last_name"],
                "vector_source": "authors"
            }
        )
        
        # Fuzzy должен был найти "Пушкин" (расстояние 1)
        assert result["valid"] is True
        assert result["corrected_value"] == "Пушкин"

    # ========================================================================
    # Комплексные сценарии
    # ========================================================================

    @pytest.mark.asyncio
    async def test_nothing_found_returns_suggestions(self, create_tracked_executor):
        """Ничего не найдено — возвращаем suggestions от enum"""
        executor = create_tracked_executor()
        executor.set_response("sql_query.execute", 
            ExecutionResult(status=ExecutionStatus.COMPLETED, data=MockData(rows=[])))
        executor.set_response("vector_search.search",
            ExecutionResult(status=ExecutionStatus.COMPLETED, data={"results": [], "total_found": 0}))
        validator = ParamValidator(executor=executor)
        
        result = await validator.validate(
            param_value="абракадабра",
            config={
                "type": "enum",
                "allowed_values": ["Открыто", "В работе"],
                "table": "authors",
                "search_fields": ["last_name"],
                "vector_source": "authors"
            }
        )
        
        assert result["valid"] is True
        assert result["corrected_value"] is None
        assert result["suggestions"] == ["Открыто", "В работе"]

    @pytest.mark.asyncio
    async def test_search_without_table_no_sql_calls(self, create_tracked_executor):
        """Search без table — не должен вызывать SQL"""
        executor = create_tracked_executor()
        validator = ParamValidator(executor=executor)
        
        result = await validator.validate(
            param_value="test",
            config={
                "type": "search",
                "vector_source": "authors"  # Есть vector_source, нет table
            }
        )
        
        # SQL вызовов быть не должно
        sql_calls = [c for c in executor.calls if c["action"] == "sql_query.execute"]
        assert len(sql_calls) == 0
        # Vector должен вызваться
        assert any(c["action"] == "vector_search.search" for c in executor.calls)


class TestParamValidatorPipelineDetailed:
    """Детальные тесты переходов между этапами"""

    @pytest.fixture
    def counting_executor(self):
        """Executor который считает вызовы каждого типа"""
        class CountingExecutor:
            def __init__(self):
                self.sql_calls = 0
                self.vector_calls = 0

            async def execute_action(self, action_name, parameters, context):
                if action_name == "sql_query.execute":
                    self.sql_calls += 1
                    return ExecutionResult(status=ExecutionStatus.COMPLETED, data=MockData(rows=[]))
                elif action_name == "vector_search.search":
                    self.vector_calls += 1
                    return ExecutionResult(status=ExecutionStatus.COMPLETED, data={"results": [], "total_found": 0})
                return ExecutionResult(status=ExecutionStatus.COMPLETED, data=None)
        
        return CountingExecutor()

    @pytest.mark.asyncio
    async def test_enum_stops_after_first_step(self, counting_executor):
        """Enum нашёл — только 0 вызовов (не доходит до SQL/Vector)"""
        validator = ParamValidator(executor=counting_executor)
        
        await validator.validate(
            param_value="Открыто",
            config={"type": "enum", "allowed_values": ["Открыто", "В работе"]}
        )
        
        assert counting_executor.sql_calls == 0
        assert counting_executor.vector_calls == 0

    @pytest.mark.asyncio
    async def test_search_uses_three_steps_max(self, counting_executor):
        """Search проходит все 3 этапа максимум"""
        validator = ParamValidator(executor=counting_executor)
        
        await validator.validate(
            param_value="test",
            config={
                "type": "search",
                "table": "authors",
                "search_fields": ["last_name"],
                "vector_source": "authors"
            }
        )
        
        # SQL (1 для ILIKE, 1+ для Fuzzy списка) + Vector (1)
        assert counting_executor.sql_calls >= 1
        assert counting_executor.vector_calls == 1

    @pytest.mark.asyncio
    async def test_no_vector_source_skips_vector(self, counting_executor):
        """Без vector_source — пропускает Vector этап"""
        validator = ParamValidator(executor=counting_executor)
        
        await validator.validate(
            param_value="test",
            config={
                "type": "search",
                "table": "authors",
                "search_fields": ["last_name"]
                # Нет vector_source
            }
        )
        
        assert counting_executor.vector_calls == 0


class TestEdgeCases:
    """Тесты граничных случаев"""

    @pytest.mark.asyncio
    async def test_empty_param_value(self):
        """Пустой параметр"""
        class EmptyExecutor:
            async def execute_action(self, action_name, parameters, context):
                return ExecutionResult(status=ExecutionStatus.COMPLETED, data=None)
        
        validator = ParamValidator(executor=EmptyExecutor())
        
        result = await validator.validate(
            param_value="",
            config={"type": "enum", "allowed_values": ["Открыто"]}
        )
        
        assert result["valid"] is True

    @pytest.mark.asyncio
    async def test_none_param_value(self):
        """None параметр"""
        class EmptyExecutor:
            async def execute_action(self, action_name, parameters, context):
                return ExecutionResult(status=ExecutionStatus.COMPLETED, data=None)
        
        validator = ParamValidator(executor=EmptyExecutor())
        
        result = await validator.validate(
            param_value=None,
            config={"type": "enum", "allowed_values": ["Открыто"]}
        )
        
        assert result["valid"] is True

    @pytest.mark.asyncio
    async def test_exception_in_sql_does_not_crash(self):
        """Исключение в SQL — продолжает работать"""
        class CrashingExecutor:
            async def execute_action(self, action_name, parameters, context):
                if action_name == "sql_query.execute":
                    raise Exception("SQL Error")
                return ExecutionResult(status=ExecutionStatus.COMPLETED, data=None)
        
        validator = ParamValidator(executor=CrashingExecutor())
        
        result = await validator.validate(
            param_value="test",
            config={
                "type": "search",
                "table": "authors",
                "search_fields": ["last_name"],
                "vector_source": "authors"
            }
        )
        
        # Не должно упасть
        assert result["valid"] is True

    @pytest.mark.asyncio
    async def test_exception_in_vector_does_not_crash(self):
        """Исключение в Vector — продолжает работать"""
        class CrashingExecutor:
            async def execute_action(self, action_name, parameters, context):
                if action_name == "vector_search.search":
                    raise Exception("Vector Error")
                return ExecutionResult(status=ExecutionStatus.COMPLETED, data=None)
        
        validator = ParamValidator(executor=CrashingExecutor())
        
        result = await validator.validate(
            param_value="test",
            config={
                "type": "search",
                "table": "authors",
                "search_fields": ["last_name"],
                "vector_source": "authors"
            }
        )
        
        # Не должно упасть
        assert result["valid"] is True
