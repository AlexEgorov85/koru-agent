"""
Тесты для детекции зацикливания агента (AgentStuckError).

Проверяет что AgentRuntime корректно детектирует зацикливание
и выбрасывает AgentStuckError.
"""
import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch

from core.agent.components.state import AgentState
from core.agent.behaviors.base import BehaviorDecision, BehaviorDecisionType
from core.models.errors import AgentStuckError


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def mock_application_context():
    """Создаёт мок ApplicationContext"""
    mock = MagicMock()
    mock.session_context = MagicMock()
    mock.session_context.record_action = MagicMock()
    mock.session_context.record_decision = MagicMock()
    mock.session_context.record_error = MagicMock()
    mock.session_context.get_history = MagicMock(return_value=[])
    mock.session_context.step_context.count = MagicMock(return_value=1)
    mock.get_all_capabilities = AsyncMock(return_value=[])  # ← AsyncMock вместо MagicMock
    mock.infrastructure_context = MagicMock()
    mock.infrastructure_context.event_bus = MagicMock()
    # Делаем publish awaitable
    mock.infrastructure_context.event_bus.publish = AsyncMock()
    return mock


@pytest.fixture
def mock_behavior_manager():
    """Создаёт мок BehaviorManager"""
    mock = AsyncMock()
    mock.initialize = AsyncMock()
    mock.generate_next_decision = AsyncMock()
    mock._current_pattern = MagicMock()
    return mock


@pytest.fixture
def mock_executor():
    """Создаёт мок ActionExecutor"""
    mock = AsyncMock()
    mock.execute_capability = AsyncMock()
    return mock


# ============================================================================
# ТЕСТЫ ПРОПУЩЕНЫ — УСТАРЕЛИ ПОСЛЕ РЕФАКТОРИНГА
# ============================================================================

@pytest.mark.skip(reason="Тесты устарели — изменился API после рефакторинга SafeExecutor")
class TestAgentStuckErrorDetection:
    """Тесты детекции зацикливания через AgentStuckError"""

    @pytest.mark.asyncio
    async def test_agent_stuck_on_repeating_decisions(
        self, mock_application_context, mock_behavior_manager
    ):
        """Тест: AgentStuckError при повторяющихся decision без изменения state"""
        from core.agent.runtime import AgentRuntime
        from core.agent.components.policy import AgentPolicy
        from core.models.enums.common_enums import ExecutionStatus

        # Создаём повторяющийся decision
        repeating_decision = BehaviorDecision(
            action=BehaviorDecisionType.ACT,
            capability_name="test_capability",
            parameters={},
            reason="test_reason"
        )

        # BehaviorManager всегда возвращает одинаковый decision
        mock_behavior_manager.generate_next_decision = AsyncMock(
            return_value=repeating_decision
        )

        # Создаём runtime
        runtime = AgentRuntime(
            application_context=mock_application_context,
            goal="Тестовая цель",
            policy=AgentPolicy(),
            max_steps=10
        )

        # Подменяем behavior_manager на мок
        runtime.behavior_manager = mock_behavior_manager

        # Подменяем _execute_single_step_internal чтобы state не менялся
        async def mock_execute_step(decision, available_caps):
            # State не меняется
            return None

        runtime._execute_single_step_internal = mock_execute_step

        # Запуск должен завершиться с ошибкой
        result = await runtime.run()

        # Проверяем что агент завершился с ошибкой
        assert result.status == ExecutionStatus.FAILED
        # Проверяем что ошибка связана с зацикливанием или отсутствием прогресса
        assert result.error is not None
        assert "no_progress" in result.error.lower() or "steps" in result.error.lower()

    @pytest.mark.asyncio
    async def test_agent_stuck_on_state_not_mutating(
        self, mock_application_context, mock_behavior_manager
    ):
        """Тест: AgentStuckError если state не меняется после observe"""
        from core.agent.runtime import AgentRuntime
        from core.agent.components.policy import AgentPolicy
        from core.models.enums.common_enums import ExecutionStatus

        # Создаём разные decision чтобы избежать первой проверки
        decisions = [
            BehaviorDecision(
                action=BehaviorDecisionType.ACT,
                capability_name=f"capability_{i}",
                parameters={},
                reason=f"step_{i}"
            )
            for i in range(5)
        ]

        # BehaviorManager возвращает разные decision
        call_count = [0]
        async def mock_generate_decision(*args, **kwargs):
            idx = call_count[0] % len(decisions)
            call_count[0] += 1
            return decisions[idx]

        mock_behavior_manager.generate_next_decision = mock_generate_decision

        # Создаём runtime
        runtime = AgentRuntime(
            application_context=mock_application_context,
            goal="Тестовая цель",
            policy=AgentPolicy(),
            max_steps=10
        )

        runtime.behavior_manager = mock_behavior_manager

        # Сохраняем snapshot до выполнения
        initial_snapshot = runtime.state.snapshot()

        # Подменяем _execute_single_step_internal чтобы state не менялся
        async def mock_execute_step(decision, available_caps):
            # State не меняется
            return None

        runtime._execute_single_step_internal = mock_execute_step

        # Запуск должен завершиться с ошибкой
        result = await runtime.run()

        # Проверяем что агент завершился с ошибкой
        assert result.status == ExecutionStatus.FAILED
        # Проверяем что ошибка связана с зацикливанием или отсутствием прогресса
        assert result.error is not None
        assert "no_progress" in result.error.lower() or "steps" in result.error.lower()

    @pytest.mark.asyncio
    async def test_no_error_when_state_mutates(
        self, mock_application_context, mock_behavior_manager
    ):
        """Тест: Нет ошибки если state меняется"""
        from core.agent.runtime import AgentRuntime
        from core.agent.components.policy import AgentPolicy

        # Создаём разные decision
        decisions = [
            BehaviorDecision(
                action=BehaviorDecisionType.ACT,
                capability_name=f"capability_{i}",
                parameters={},
                reason=f"step_{i}"
            )
            for i in range(3)
        ]

        call_count = [0]
        async def mock_generate_decision(*args, **kwargs):
            idx = call_count[0] % len(decisions)
            call_count[0] += 1
            return decisions[idx]

        mock_behavior_manager.generate_next_decision = mock_generate_decision

        runtime = AgentRuntime(
            application_context=mock_application_context,
            goal="Тестовая цель",
            policy=AgentPolicy(),
            max_steps=5
        )

        runtime.behavior_manager = mock_behavior_manager

        # State меняется при каждом шаге
        async def mock_execute_step(decision, available_caps):
            runtime.state.step += 1
            runtime.state.history.append(f"action_{runtime.state.step}")
            return None

        runtime._execute_single_step_internal = mock_execute_step

        # Запуск не должен выбросить ошибку
        result = await runtime.run()

        # Проверяем что агент выполнился без AgentStuckError
        assert result is not None
        assert "AgentStuckError" not in str(result.result)


# ============================================================================
# ТЕСТ 2: AGENTSTATE SNAPSHOT
# ============================================================================

class TestAgentStateSnapshot:
    """Тесты snapshot состояния агента"""

    def test_snapshot_contains_all_fields(self):
        """Тест: snapshot содержит все требуемые поля"""
        state = AgentState(
            step=5,
            error_count=2,
            consecutive_errors=1,
            no_progress_steps=3,
            finished=False,
            history=["action1", "action2"]
        )

        snapshot = state.snapshot()

        assert snapshot['step'] == 5
        assert snapshot['error_count'] == 2
        assert snapshot['consecutive_errors'] == 1
        assert snapshot['no_progress_steps'] == 3
        assert snapshot['finished'] is False
        assert snapshot['history_length'] == 2
        assert snapshot['last_history_item'] == "action2"

    def test_snapshot_comparison(self):
        """Тест: сравнение snapshot"""
        state1 = AgentState(step=5, error_count=2)
        state2 = AgentState(step=5, error_count=2)
        state3 = AgentState(step=6, error_count=2)

        assert state1.snapshot() == state2.snapshot()
        assert state1.snapshot() != state3.snapshot()

    def test_state_equality_operator(self):
        """Тест: оператор сравнения состояний"""
        state1 = AgentState(step=5, error_count=2)
        state2 = AgentState(step=5, error_count=2)
        state3 = AgentState(step=6, error_count=2)

        assert state1 == state2
        assert state1 != state3

    def test_snapshot_with_empty_history(self):
        """Тест: snapshot с пустой историей"""
        state = AgentState()
        snapshot = state.snapshot()

        assert snapshot['history_length'] == 0
        assert snapshot['last_history_item'] is None


# ============================================================================
# ТЕСТ 3: NO_PROGRESS_COUNTER
# ============================================================================

class TestNoProgressCounter:
    """Тесты счетчика отсутствия прогресса"""

    def test_no_progress_increments_counter(self):
        """Тест: отсутствие прогресса увеличивает счетчик"""
        state = AgentState()

        state.register_progress(progressed=False)
        assert state.no_progress_steps == 1

        state.register_progress(progressed=False)
        assert state.no_progress_steps == 2

    def test_progress_resets_counter(self):
        """Тест: прогресс сбрасывает счетчик"""
        state = AgentState(no_progress_steps=5)

        state.register_progress(progressed=True)
        assert state.no_progress_steps == 0

    def test_mixed_progress_and_no_progress(self):
        """Тест: смешанный прогресс и отсутствие прогресса"""
        state = AgentState()

        state.register_progress(progressed=False)
        state.register_progress(progressed=False)
        assert state.no_progress_steps == 2

        state.register_progress(progressed=True)
        assert state.no_progress_steps == 0

        state.register_progress(progressed=False)
        assert state.no_progress_steps == 1


# ============================================================================
# ЗАПУСК ТЕСТОВ
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
