"""
Тесты для минималистичного runtime агента.

ПРОВЕРКИ:
1. AgentState — создание и обновление
2. StepResult — фабричные методы
3. AgentMetrics — подсчёт шагов и ошибок
4. Controller — policy решения
5. Observer — анализ результатов
6. Executor — выполнение действий (mock)
7. AgentLoop — полный цикл step
8. AgentRuntime — полный цикл run (mock)
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock

# Импортируем компоненты напрямую из модуля
import sys
sys.path.insert(0, '/workspace')

from core.agent.runtime_minimal import (
    AgentState, StepResult, AgentMetrics,
    Controller, Observer, Executor, RetryExecutor,
    AgentLoop, AgentRuntime
)


class TestAgentState:
    """Тесты для AgentState."""
    
    def test_create_state(self):
        """Создание состояния."""
        state = AgentState(goal="test goal")
        assert state.goal == "test goal"
        assert state.steps == 0
        assert state.max_steps == 10
        assert state.failures == 0
    
    def test_apply_success_step(self):
        """Применение успешного шага."""
        from core.models.data.execution import ExecutionResult
        
        state = AgentState(goal="test")
        result = ExecutionResult.success({"data": "test"})
        observation = {"status": "success"}
        
        state.apply("test_action", result, observation)
        
        assert state.steps == 1
        assert state.last_action == "test_action"
        assert state.failures == 0
        assert len(state.history) == 1
    
    def test_apply_failure_step(self):
        """Применение неудачного шага."""
        from core.models.data.execution import ExecutionResult
        
        state = AgentState(goal="test")
        result = ExecutionResult.failure("error message")
        observation = {"status": "error"}
        
        state.apply("test_action", result, observation)
        
        assert state.steps == 1
        assert state.failures == 1
    
    def test_consecutive_failures_reset_on_success(self):
        """Сброс счётчика ошибок при успехе."""
        from core.models.data.execution import ExecutionResult
        
        state = AgentState(goal="test")
        
        # 3 ошибки подряд
        for i in range(3):
            result = ExecutionResult.failure(f"error {i}")
            state.apply(f"action_{i}", result, {})
        
        assert state.failures == 3
        
        # Успех сбрасывает счётчик
        result = ExecutionResult.success({"data": "ok"})
        state.apply("success_action", result, {})
        
        assert state.failures == 0


class TestStepResult:
    """Тесты для StepResult."""
    
    def test_done_result(self):
        """Результат завершения."""
        state = AgentState(goal="test")
        result = StepResult.done(state)
        
        assert result.done is True
        assert result.success is True
        assert result.state == state
    
    def test_fail_result(self):
        """Результат ошибки."""
        state = AgentState(goal="test")
        result = StepResult.fail("error message", state)
        
        assert result.done is True
        assert result.success is False
        assert result.error == "error message"
    
    def test_continue_result(self):
        """Результат продолжения."""
        state = AgentState(goal="test")
        result = StepResult.continue_(state)
        
        assert result.done is False
        assert result.success is True


class TestAgentMetrics:
    """Тесты для AgentMetrics."""
    
    def test_initial_metrics(self):
        """Начальные значения метрик."""
        metrics = AgentMetrics()
        
        assert metrics.steps == 0
        assert metrics.errors == 0
        assert metrics.empty_results == 0
        assert metrics.repeated_actions == 0
    
    def test_update_with_success(self):
        """Обновление метрик успешным шагом."""
        metrics = AgentMetrics()
        result = StepResult.continue_(AgentState(goal="test"))
        
        metrics.update(result)
        
        assert metrics.steps == 1
        assert metrics.errors == 0
    
    def test_update_with_error(self):
        """Обновление метрик ошибочным шагом."""
        metrics = AgentMetrics()
        result = StepResult.fail("error", AgentState(goal="test"))
        
        metrics.update(result)
        
        assert metrics.steps == 1
        assert metrics.errors == 1
    
    def test_should_stop_on_errors(self):
        """Остановка при превышении лимита ошибок."""
        metrics = AgentMetrics()
        
        # 10 ошибок
        for i in range(10):
            result = StepResult.fail(f"error {i}", AgentState(goal="test"))
            metrics.update(result)
        
        should_stop, reason = metrics.should_stop(max_errors=10)
        
        assert should_stop is True
        assert "max_errors_reached" in reason
    
    def test_should_continue(self):
        """Продолжение работы в пределах лимитов."""
        metrics = AgentMetrics()
        
        # 5 ошибок (меньше лимита)
        for i in range(5):
            result = StepResult.fail(f"error {i}", AgentState(goal="test"))
            metrics.update(result)
        
        should_stop, reason = metrics.should_stop(max_errors=10)
        
        assert should_stop is False


class TestController:
    """Тесты для Controller."""
    
    def test_continue_on_success(self):
        """Продолжение при успехе."""
        controller = Controller(max_steps=10, max_failures=3)
        state = AgentState(goal="test")
        
        from core.models.data.execution import ExecutionResult
        result = ExecutionResult.success({"data": "ok"})
        
        decision = controller.evaluate(state, result)
        
        assert decision.done is False
        assert decision.success is True
    
    def test_stop_on_max_steps(self):
        """Остановка по лимиту шагов."""
        controller = Controller(max_steps=5, max_failures=3)
        state = AgentState(goal="test", steps=5)
        
        from core.models.data.execution import ExecutionResult
        result = ExecutionResult.success({"data": "ok"})
        
        decision = controller.evaluate(state, result)
        
        assert decision.done is True
    
    def test_stop_on_too_many_failures(self):
        """Остановка при слишком большом количестве ошибок."""
        controller = Controller(max_steps=10, max_failures=2)
        state = AgentState(goal="test", failures=3)
        
        from core.models.data.execution import ExecutionResult
        result = ExecutionResult.failure("error")
        
        decision = controller.evaluate(state, result)
        
        assert decision.done is True
        assert decision.success is False
        assert "too many errors" in decision.error


class TestObserver:
    """Тесты для Observer."""
    
    @pytest.mark.asyncio
    async def test_observe_success(self):
        """Наблюдение успешного результата."""
        observer = Observer()
        
        from core.models.data.execution import ExecutionResult
        result = ExecutionResult.success({"data": "test"})
        state = AgentState(goal="test")
        
        observation = await observer.observe(result, state)
        
        assert observation["success"] is True
        assert observation["status"] == "success"
    
    @pytest.mark.asyncio
    async def test_observe_error(self):
        """Наблюдение ошибки."""
        observer = Observer()
        
        from core.models.data.execution import ExecutionResult
        result = ExecutionResult.failure("error message")
        state = AgentState(goal="test")
        
        observation = await observer.observe(result, state)
        
        assert observation["success"] is False
        assert observation["status"] == "error"
        assert observation["error"] == "error message"
    
    @pytest.mark.asyncio
    async def test_observe_empty_result(self):
        """Наблюдение пустого результата."""
        observer = Observer()
        
        from core.models.data.execution import ExecutionResult
        result = ExecutionResult.success({})  # Пустой dict
        state = AgentState(goal="test")
        
        observation = await observer.observe(result, state)
        
        assert observation["success"] is True
        assert observation["status"] == "empty"


class TestExecutor:
    """Тесты для Executor."""
    
    @pytest.mark.asyncio
    async def test_execute_success(self):
        """Успешное выполнение действия."""
        # Mock tool registry
        mock_tool = AsyncMock()
        mock_tool.run = AsyncMock(return_value={"result": "success"})
        
        mock_registry = MagicMock()
        mock_registry.get = MagicMock(return_value=mock_tool)
        
        mock_event_bus = AsyncMock()
        
        executor = Executor(
            tool_registry=mock_registry,
            event_bus=mock_event_bus,
            session_id="test_session",
            agent_id="test_agent"
        )
        
        state = AgentState(goal="test")
        result = await executor.execute("test_action", state)
        
        assert result.success is True
        mock_tool.run.assert_called_once()
        mock_event_bus.publish.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_execute_tool_not_found(self):
        """Выполнение несуществующего инструмента."""
        mock_registry = MagicMock()
        mock_registry.get = MagicMock(return_value=None)
        
        executor = Executor(
            tool_registry=mock_registry,
            event_bus=None
        )
        
        state = AgentState(goal="test")
        result = await executor.execute("nonexistent_action", state)
        
        assert result.success is False
        assert "Tool not found" in result.error
    
    @pytest.mark.asyncio
    async def test_execute_exception(self):
        """Исключение при выполнении."""
        mock_tool = AsyncMock()
        mock_tool.run = AsyncMock(side_effect=Exception("test error"))
        
        mock_registry = MagicMock()
        mock_registry.get = MagicMock(return_value=mock_tool)
        
        executor = Executor(
            tool_registry=mock_registry,
            event_bus=None
        )
        
        state = AgentState(goal="test")
        result = await executor.execute("test_action", state)
        
        assert result.success is False
        assert "test error" in result.error


class TestRetryExecutor:
    """Тесты для RetryExecutor."""
    
    @pytest.mark.asyncio
    async def test_retry_on_failure(self):
        """Retry при неудаче."""
        call_count = 0
        
        async def failing_execute(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                from core.models.data.execution import ExecutionResult
                return ExecutionResult.failure(f"attempt {call_count}")
            return ExecutionResult.success({"result": "success"})
        
        mock_executor = MagicMock()
        mock_executor.execute = failing_execute
        
        retry_executor = RetryExecutor(
            executor=mock_executor,
            max_retries=3,
            base_delay=0.01  # Быстрая задержка для теста
        )
        
        state = AgentState(goal="test")
        result = await retry_executor.execute("test_action", state)
        
        assert result.success is True
        assert call_count == 3  # 3 попытки
    
    @pytest.mark.asyncio
    async def test_no_retry_on_success(self):
        """Нет retry при успехе."""
        async def success_execute(*args, **kwargs):
            from core.models.data.execution import ExecutionResult
            return ExecutionResult.success({"result": "success"})
        
        mock_executor = MagicMock()
        mock_executor.execute = success_execute
        
        retry_executor = RetryExecutor(
            executor=mock_executor,
            max_retries=3
        )
        
        state = AgentState(goal="test")
        result = await retry_executor.execute("test_action", state)
        
        assert result.success is True
        mock_executor.execute.assert_called_once()


class TestAgentLoop:
    """Тесты для AgentLoop."""
    
    @pytest.mark.asyncio
    async def test_full_step_cycle(self):
        """Полный цикл шага."""
        # Mock components
        mock_decision_maker = AsyncMock()
        mock_decision_maker.decide = AsyncMock(return_value="test_action")
        
        mock_executor = AsyncMock()
        from core.models.data.execution import ExecutionResult
        mock_executor.execute = AsyncMock(return_value=ExecutionResult.success({"data": "ok"}))
        
        mock_observer = AsyncMock()
        mock_observer.observe = AsyncMock(return_value={"status": "success"})
        
        mock_controller = MagicMock()
        mock_controller.evaluate = MagicMock(return_value=StepResult.continue_(None))
        
        loop = AgentLoop(
            decision_maker=mock_decision_maker,
            executor=mock_executor,
            observer=mock_observer,
            controller=mock_controller
        )
        
        state = AgentState(goal="test")
        result = await loop.step(state)
        
        # Все компоненты вызваны
        mock_decision_maker.decide.assert_called_once()
        mock_executor.execute.assert_called_once()
        mock_observer.observe.assert_called_once()
        mock_controller.evaluate.assert_called_once()
        
        # State обновлён
        assert state.steps == 1
        assert state.last_action == "test_action"


class TestIntegration:
    """Интеграционные тесты."""
    
    @pytest.mark.asyncio
    async def test_successful_run(self):
        """Успешный запуск агента."""
        # Mock application context
        mock_app_context = MagicMock()
        mock_log_session = MagicMock()
        mock_logger = MagicMock()
        mock_log_session.create_agent_logger = MagicMock(return_value=mock_logger)
        mock_app_context.infrastructure_context.log_session = mock_log_session
        
        # Mock loop что завершается после 1 шага
        mock_loop = AsyncMock()
        mock_loop.step = AsyncMock(
            side_effect=[
                StepResult.done(AgentState(goal="test"))
            ]
        )
        
        metrics = AgentMetrics()
        
        runtime = AgentRuntime(
            loop=mock_loop,
            metrics=metrics,
            application_context=mock_app_context,
            goal="test goal",
            max_steps=5
        )
        
        result = await runtime.run()
        
        assert result.success is True
        mock_loop.step.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
