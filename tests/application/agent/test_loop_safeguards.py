"""
Тесты для Loop Safeguards в AgentRuntime.

Проверяет:
1. Детекцию зацикливания действий (3 одинаковых действия подряд)
2. Метод _should_stop_early()
3. Остановку при no-progress шагах
4. Запись ошибки в metadata при детекции цикла
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from core.models.data.execution import ExecutionResult, ExecutionStatus
from core.agent.behaviors.base import BehaviorDecision, BehaviorDecisionType


class TestLoopDetection:
    """Тесты детекции зацикливания."""

    @pytest.fixture
    def mock_runtime(self):
        """Создаёт мок AgentRuntime с минимальной инициализацией."""
        from core.agent.runtime import AgentRuntime
        
        # Создаём runtime с моками
        mock_app_ctx = MagicMock()
        mock_app_ctx.is_ready = True
        mock_app_ctx.infrastructure_context = MagicMock()
        mock_app_ctx.infrastructure_context.is_ready = True
        mock_app_ctx.infrastructure_context.event_bus = AsyncMock()
        mock_app_ctx.session_context = MagicMock()
        mock_app_ctx.session_context.session_id = "test_session"
        
        runtime = AgentRuntime(
            application_context=mock_app_ctx,
            goal="Тестовая цель",
            max_steps=10
        )
        
        # Мокаем behavior_manager
        runtime.behavior_manager = AsyncMock()
        runtime.behavior_manager.initialize = AsyncMock()
        
        return runtime

    @pytest.mark.asyncio
    async def test_detect_loop_after_three_same_actions(self, mock_runtime):
        """Тест: детекция цикла после 3 одинаковых действий."""
        runtime = mock_runtime
        
        # Настраиваем behavior_manager на возврат одного и того же decision
        same_decision = BehaviorDecision(
            action=BehaviorDecisionType.ACT,
            capability_name="test.capability",
            parameters={}
        )
        runtime.behavior_manager.generate_next_decision = AsyncMock(return_value=same_decision)
        
        # Настраиваем _execute_single_step_internal на возврат COMPLETED
        # Важно: обновляем state чтобы избежать AgentStuckError
        def update_state(result):
            runtime.state.step += 1  # Меняем state
        runtime._execute_single_step_internal = AsyncMock(
            return_value=ExecutionResult.success(data={"result": "ok"})
        )
        runtime._update_state = MagicMock(side_effect=update_state)
        runtime._should_stop = MagicMock(return_value=False)
        runtime._should_stop_early = MagicMock(return_value=False)
        
        # Запускаем цикл
        result = await runtime._run_async()
        
        # Проверяем что цикл был обнаружен
        assert result.status == ExecutionStatus.FAILED
        assert "loop" in result.error.lower() or "Loop" in result.error
        assert "test.capability" in result.error

    @pytest.mark.asyncio
    async def test_no_loop_on_different_actions(self, mock_runtime):
        """Тест: нет детекции цикла при разных действиях."""
        runtime = mock_runtime
        
        # Возвращаем разные decision
        decisions = [
            BehaviorDecision(action=BehaviorDecisionType.ACT, capability_name="cap.one", parameters={}),
            BehaviorDecision(action=BehaviorDecisionType.ACT, capability_name="cap.two", parameters={}),
            BehaviorDecision(action=BehaviorDecisionType.ACT, capability_name="cap.three", parameters={}),
        ]
        
        call_count = [0]
        async def get_decision(*args, **kwargs):
            idx = min(call_count[0], len(decisions) - 1)
            call_count[0] += 1
            return decisions[idx]
        
        runtime.behavior_manager.generate_next_decision = get_decision
        runtime._execute_single_step_internal = AsyncMock(
            return_value=ExecutionResult.success(data={"result": "ok"})
        )
        runtime._update_state = MagicMock()
        runtime._should_stop = MagicMock(return_value=False)
        runtime._should_stop_early = MagicMock(return_value=False)
        runtime.state.finished = True  # Останавливаем после 3 шагов
        
        result = await runtime._run_async()
        
        # Нет ошибки цикла
        assert "loop" not in str(result.error).lower() if result.error else True

    @pytest.mark.asyncio
    async def test_loop_metadata_contains_details(self, mock_runtime):
        """Тест: metadata содержит детали о цикле."""
        runtime = mock_runtime
        
        same_decision = BehaviorDecision(
            action=BehaviorDecisionType.ACT,
            capability_name="repeated.capability",
            parameters={}
        )
        runtime.behavior_manager.generate_next_decision = AsyncMock(return_value=same_decision)
        
        # Обновляем state чтобы избежать AgentStuckError
        def update_state(result):
            runtime.state.step += 1
        runtime._execute_single_step_internal = AsyncMock(
            return_value=ExecutionResult.success(data={"result": "ok"})
        )
        runtime._update_state = MagicMock(side_effect=update_state)
        runtime._should_stop = MagicMock(return_value=False)
        runtime._should_stop_early = MagicMock(return_value=False)
        
        result = await runtime._run_async()
        
        # Проверяем metadata
        assert result.metadata.get("error_type") == "loop_detected"
        assert result.metadata.get("repeated_action") == "act:repeated.capability"
        assert result.metadata.get("consecutive_count") >= 3


class TestShouldStopEarly:
    """Тесты метода _should_stop_early()."""

    @pytest.fixture
    def mock_runtime(self):
        """Создаёт мок AgentRuntime."""
        from core.agent.runtime import AgentRuntime
        
        mock_app_ctx = MagicMock()
        mock_app_ctx.is_ready = True
        mock_app_ctx.infrastructure_context = MagicMock()
        mock_app_ctx.infrastructure_context.is_ready = True
        mock_app_ctx.infrastructure_context.event_bus = AsyncMock()
        mock_app_ctx.session_context = MagicMock()
        mock_app_ctx.session_context.session_id = "test_session"
        
        runtime = AgentRuntime(
            application_context=mock_app_ctx,
            goal="Тестовая цель",
            max_steps=10
        )
        
        return runtime

    def test_should_stop_early_when_finished(self, mock_runtime):
        """Тест: остановка когда state.finished=True."""
        runtime = mock_runtime
        runtime.state.finished = True
        
        assert runtime._should_stop_early() is True

    def test_should_stop_early_on_no_progress_limit(self, mock_runtime):
        """Тест: остановка при лимите no-progress шагов."""
        runtime = mock_runtime
        runtime.progress_metrics.no_progress_steps = 3  # По умолчанию max_no_progress_steps=3
        
        assert runtime._should_stop_early() is True

    def test_should_stop_early_on_high_confidence(self, mock_runtime):
        """Тест: остановка при высоком confidence."""
        runtime = mock_runtime
        runtime.state.confidence = 0.96  # > 0.95
        
        assert runtime._should_stop_early() is True

    def test_should_not_stop_early_when_normal(self, mock_runtime):
        """Тест: нет остановки при нормальных условиях."""
        runtime = mock_runtime
        runtime.state.finished = False
        runtime.progress_metrics.no_progress_steps = 0
        # confidence нет или < 0.95
        
        assert runtime._should_stop_early() is False

    def test_should_stop_early_confidence_boundary(self, mock_runtime):
        """Тест: граница confidence (0.95 не останавливает)."""
        runtime = mock_runtime
        runtime.state.confidence = 0.95  # Ровно 0.95 — не останавливает
        
        assert runtime._should_stop_early() is False
        
        runtime.state.confidence = 0.951  # > 0.95 — останавливает
        assert runtime._should_stop_early() is True


class TestIntegration:
    """Интеграционные тесты Loop Safeguards."""

    @pytest.mark.asyncio
    async def test_full_loop_detection_workflow(self):
        """Тест: полный цикл детекции зацикливания."""
        from core.agent.runtime import AgentRuntime
        
        mock_app_ctx = MagicMock()
        mock_app_ctx.is_ready = True
        mock_app_ctx.infrastructure_context = MagicMock()
        mock_app_ctx.infrastructure_context.is_ready = True
        mock_app_ctx.infrastructure_context.event_bus = AsyncMock()
        mock_app_ctx.session_context = MagicMock()
        mock_app_ctx.session_context.session_id = "test_session"
        
        runtime = AgentRuntime(
            application_context=mock_app_ctx,
            goal="Тест с зацикливанием",
            max_steps=20  # Больше чем нужно для детекции
        )
        
        # Один и тот же decision
        same_decision = BehaviorDecision(
            action=BehaviorDecisionType.ACT,
            capability_name="loop.test",
            parameters={}
        )
        runtime.behavior_manager.generate_next_decision = AsyncMock(return_value=same_decision)
        runtime.behavior_manager.initialize = AsyncMock()
        
        # Успешное выполнение (чтобы цикл продолжался)
        # Обновляем state чтобы избежать AgentStuckError
        def update_state(result):
            runtime.state.step += 1
        runtime._execute_single_step_internal = AsyncMock(
            return_value=ExecutionResult.success(data={"result": "ok"})
        )
        runtime._update_state = MagicMock(side_effect=update_state)
        
        result = await runtime._run_async()
        
        # Детекция цикла
        assert result.status == ExecutionStatus.FAILED
        assert "loop" in result.error.lower()
        assert "loop.test" in result.error
        assert result.metadata.get("error_type") == "loop_detected"

    @pytest.mark.asyncio
    async def test_early_stop_prevents_max_steps(self):
        """Тест: ранняя остановка предотвращает достижение max_steps."""
        from core.agent.runtime import AgentRuntime
        
        mock_app_ctx = MagicMock()
        mock_app_ctx.is_ready = True
        mock_app_ctx.infrastructure_context = MagicMock()
        mock_app_ctx.infrastructure_context.is_ready = True
        mock_app_ctx.infrastructure_context.event_bus = AsyncMock()
        mock_app_ctx.session_context = MagicMock()
        mock_app_ctx.session_context.session_id = "test_session"
        
        runtime = AgentRuntime(
            application_context=mock_app_ctx,
            goal="Быстрая цель",
            max_steps=100  # Много шагов
        )
        
        # State finished после первого шага
        runtime.state.finished = False
        
        async def set_finished(*args, **kwargs):
            runtime.state.finished = True
            return ExecutionResult.success(data={"done": True})
        
        runtime.behavior_manager.initialize = AsyncMock()
        runtime.behavior_manager.generate_next_decision = AsyncMock(
            return_value=BehaviorDecision(
                action=BehaviorDecisionType.ACT,
                capability_name="finish.fast",
                parameters={}
            )
        )
        runtime._execute_single_step_internal = set_finished
        
        result = await runtime._run_async()
        
        # Остановились рано, не достигли max_steps
        assert runtime._current_step < 100
        assert result.status == ExecutionStatus.COMPLETED


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
