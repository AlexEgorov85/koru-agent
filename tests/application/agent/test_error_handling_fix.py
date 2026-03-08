"""
Тесты для проверки исправления обработки ошибок в AgentRuntime.

Проверяет что:
1. Превышение лимита ошибок приводит к FAILED статусу
2. Превышение лимита отсутствия прогресса приводит к FAILED статусу
3. error_count и no_progress_steps попадают в metadata
"""
import pytest
from unittest.mock import MagicMock, AsyncMock

from core.application.agent.components.state import AgentState
from core.application.agent.components.policy import AgentPolicy
from core.application.behaviors.base import BehaviorDecision, BehaviorDecisionType
from core.models.enums.common_enums import ExecutionStatus


class TestErrorCountInFinalStatus:
    """Тесты проверки учёта ошибок при формировании статуса"""

    def test_policy_should_fallback_on_error_limit(self):
        """Тест: policy.should_fallback() возвращает True при превышении лимита ошибок"""
        policy = AgentPolicy(max_errors=2)
        state = AgentState()

        # До лимита
        state.register_error()
        assert policy.should_fallback(state) is False  # 1 ошибка из 2

        # Достигнут лимит
        state.register_error()
        assert policy.should_fallback(state) is True  # 2 ошибки из 2

    def test_policy_should_stop_no_progress(self):
        """Тест: policy.should_stop_no_progress() возвращает True при лимите отсутствия прогресса"""
        policy = AgentPolicy(max_no_progress_steps=3)
        state = AgentState()

        # До лимита
        state.register_progress(progressed=False)
        state.register_progress(progressed=False)
        assert policy.should_stop_no_progress(state) is False  # 2 шага из 3

        # Достигнут лимит
        state.register_progress(progressed=False)
        assert policy.should_stop_no_progress(state) is True  # 3 шага из 3

    def test_error_count_in_state(self):
        """Тест: error_count корректно увеличивается в state"""
        state = AgentState()
        assert state.error_count == 0

        state.register_error()
        assert state.error_count == 1

        state.register_error()
        assert state.error_count == 2

        state.register_error()
        assert state.error_count == 3

    def test_no_progress_steps_in_state(self):
        """Тест: no_progress_steps корректно увеличивается в state"""
        state = AgentState()
        assert state.no_progress_steps == 0

        state.register_progress(progressed=False)
        assert state.no_progress_steps == 1

        state.register_progress(progressed=False)
        assert state.no_progress_steps == 2

        # Прогресс сбрасывает счётчик
        state.register_progress(progressed=True)
        assert state.no_progress_steps == 0


class TestAgentRuntimeErrorHandling:
    """Тесты обработки ошибок в AgentRuntime"""

    @pytest.fixture
    def mock_application_context(self):
        """Создаёт мок ApplicationContext"""
        mock = MagicMock()
        mock.session_context = MagicMock()
        mock.session_context.record_action = MagicMock()
        mock.session_context.record_decision = MagicMock()
        mock.session_context.record_error = MagicMock()
        mock.session_context.get_history = MagicMock(return_value=[])
        mock.get_all_capabilities = AsyncMock(return_value=[])
        mock.infrastructure_context = MagicMock()
        mock.infrastructure_context.event_bus = AsyncMock()
        mock.infrastructure_context.event_bus.publish = AsyncMock()
        mock.is_ready = True
        return mock

    @pytest.mark.asyncio
    async def test_failed_status_on_error_limit(self, mock_application_context):
        """Тест: FAILED статус при превышении лимита ошибок"""
        from core.application.agent.runtime import AgentRuntime

        # Создаём runtime с лимитом 2 ошибки
        runtime = AgentRuntime(
            application_context=mock_application_context,
            goal="Тестовая цель",
            policy=AgentPolicy(max_errors=2),
            max_steps=10
        )

        # Имитируем ошибки при выполнении шагов
        async def mock_execute_step(decision, available_caps):
            runtime.state.register_error()
            # Возвращаем ExecutionResult с FAILED если лимит превышен
            if runtime.policy.should_fallback(runtime.state):
                from core.models.data.execution import ExecutionResult
                return ExecutionResult(
                    status=ExecutionStatus.FAILED,
                    error=f"Превышен лимит ошибок: {runtime.state.error_count}",
                    metadata={"error_count": runtime.state.error_count}
                )
            return None

        runtime._execute_single_step_internal = mock_execute_step

        # Мокаем behavior_manager
        runtime.behavior_manager = AsyncMock()
        runtime.behavior_manager.initialize = AsyncMock()
        runtime.behavior_manager.generate_next_decision = AsyncMock(
            return_value=BehaviorDecision(
                action=BehaviorDecisionType.ACT,
                capability_name="test.capability",
                parameters={}
            )
        )

        result = await runtime.run()

        # Проверяем что агент завершился с FAILED статусом
        assert result.status == ExecutionStatus.FAILED
        assert "error_count" in result.metadata
        assert result.metadata["error_count"] >= 2

    @pytest.mark.asyncio
    async def test_error_count_in_metadata(self, mock_application_context):
        """Тест: error_count попадает в metadata результата"""
        from core.application.agent.runtime import AgentRuntime

        runtime = AgentRuntime(
            application_context=mock_application_context,
            goal="Тестовая цель",
            policy=AgentPolicy(max_errors=5),
            max_steps=3
        )

        # Имитируем ошибки
        async def mock_execute_step(decision, available_caps):
            runtime.state.register_error()
            return None

        runtime._execute_single_step_internal = mock_execute_step

        # Мокаем behavior_manager
        runtime.behavior_manager = AsyncMock()
        runtime.behavior_manager.initialize = AsyncMock()
        runtime.behavior_manager.generate_next_decision = AsyncMock(
            return_value=BehaviorDecision(
                action=BehaviorDecisionType.ACT,
                capability_name="test.capability",
                parameters={}
            )
        )

        result = await runtime.run()

        # Проверяем что error_count есть в metadata
        assert "error_count" in result.metadata
        assert result.metadata["error_count"] > 0

    @pytest.mark.asyncio
    async def test_no_progress_in_metadata(self, mock_application_context):
        """Тест: no_progress_steps попадает в metadata результата"""
        from core.application.agent.runtime import AgentRuntime

        runtime = AgentRuntime(
            application_context=mock_application_context,
            goal="Тестовая цель",
            policy=AgentPolicy(max_no_progress_steps=5),
            max_steps=3
        )

        # Имитируем отсутствие прогресса
        async def mock_execute_step(decision, available_caps):
            runtime.state.register_progress(progressed=False)
            return None

        runtime._execute_single_step_internal = mock_execute_step

        # Мокаем behavior_manager
        runtime.behavior_manager = AsyncMock()
        runtime.behavior_manager.initialize = AsyncMock()
        runtime.behavior_manager.generate_next_decision = AsyncMock(
            return_value=BehaviorDecision(
                action=BehaviorDecisionType.ACT,
                capability_name="test.capability",
                parameters={}
            )
        )

        result = await runtime.run()

        # Проверяем что no_progress_steps есть в metadata
        assert "no_progress_steps" in result.metadata
        assert result.metadata["no_progress_steps"] > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
