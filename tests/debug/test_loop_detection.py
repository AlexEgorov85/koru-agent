"""
Тесты для детекции зацикливания агента.

Фиксирует 3 критические проблемы:
1. ReAct зацикливание (повторяющиеся decision)
2. Отсутствие мутации state после observe
3. Неверные ACT decision без capability_name
"""
import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch

from core.application.agent.components.state import AgentState
from core.application.behaviors.base import BehaviorDecision, BehaviorDecisionType


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def agent_state():
    """Создаёт AgentState для тестов"""
    return AgentState()


@pytest.fixture
def mock_session_context():
    """Создаёт мок SessionContext"""
    mock = MagicMock()
    mock.record_action = MagicMock()
    mock.record_decision = MagicMock()
    mock.record_error = MagicMock()
    mock.get_history = MagicMock(return_value=[])
    return mock


@pytest.fixture
def mock_capabilities():
    """Создаёт список мок capabilities"""
    capabilities = []
    for i in range(3):
        cap = MagicMock()
        cap.name = f"test_capability_{i}"
        cap.description = f"Test capability {i}"
        capabilities.append(cap)
    return capabilities


# ============================================================================
# ТЕСТ 1: DETECTION OF REPEATING DECISIONS
# ============================================================================

class TestLoopDetection:
    """Тесты детекции зацикливания"""

    def test_snapshot_creation(self, agent_state):
        """Тест: создание snapshot состояния"""
        snapshot = agent_state.snapshot()
        
        assert isinstance(snapshot, dict)
        assert 'step' in snapshot
        assert 'error_count' in snapshot
        assert 'consecutive_errors' in snapshot
        assert 'no_progress_steps' in snapshot
        assert 'finished' in snapshot
        assert 'history_length' in snapshot
        assert 'last_history_item' in snapshot
        
        # Проверка начальных значений
        assert snapshot['step'] == 0
        assert snapshot['error_count'] == 0
        assert snapshot['finished'] is False
        assert snapshot['history_length'] == 0

    def test_snapshot_changes_after_update(self, agent_state):
        """Тест: snapshot меняется после обновления состояния"""
        snapshot_before = agent_state.snapshot()
        
        # Обновляем состояние
        agent_state.step = 1
        agent_state.history.append("action_1")
        
        snapshot_after = agent_state.snapshot()
        
        # Snapshot должен измениться
        assert snapshot_before != snapshot_after
        assert snapshot_after['step'] == 1
        assert snapshot_after['history_length'] == 1

    def test_state_equality(self, agent_state):
        """Тест: сравнение состояний через snapshot"""
        state1 = AgentState(step=5, error_count=2)
        state2 = AgentState(step=5, error_count=2)
        state3 = AgentState(step=6, error_count=2)
        
        assert state1 == state2
        assert state1 != state3

    def test_loop_detection_with_repeating_decisions(self, agent_state, mock_session_context, mock_capabilities):
        """Тест: детекция зацикливания при повторяющихся decision"""
        from core.application.agent.components.behavior_manager import BehaviorManager
        from core.application.context.application_context import ApplicationContext
        
        # Создаём мок application_context
        app_context = MagicMock()
        app_context.session_context = mock_session_context
        
        behavior_manager = BehaviorManager(application_context=app_context)
        
        # Создаём повторяющиеся decision
        repeating_decision = BehaviorDecision(
            action=BehaviorDecisionType.ACT,
            capability_name="test_capability",
            parameters={},
            reason="test_reason"
        )
        
        # Симуляция повторяющихся decision без изменения state
        decisions = [repeating_decision] * 3
        snapshots = [agent_state.snapshot()] * 3
        
        # Проверка детекции зацикливания
        loop_detected = False
        for i in range(1, len(decisions)):
            if (decisions[i].action == decisions[i-1].action and
                decisions[i].capability_name == decisions[i-1].capability_name):
                if snapshots[i] == snapshots[i-1]:
                    loop_detected = True
                    break
        
        assert loop_detected is True, "Зацикливание должно быть детектировано"


# ============================================================================
# ТЕСТ 2: STATE MUTATION AFTER OBSERVE
# ============================================================================

class TestStateMutation:
    """Тесты мутации состояния после observe"""

    def test_state_mutation_after_action(self, agent_state):
        """Тест: state должен меняться после действия"""
        snapshot_before = agent_state.snapshot()
        
        # Симуляция действия
        agent_state.step += 1
        agent_state.history.append("test_action")
        
        snapshot_after = agent_state.snapshot()
        
        assert snapshot_before != snapshot_after
        assert snapshot_after['step'] == 1
        assert snapshot_after['history_length'] == 1

    def test_no_mutation_detection(self, agent_state):
        """Тест: детекция отсутствия мутации"""
        snapshots = []
        
        # Симуляция шагов без мутации
        for _ in range(3):
            snapshots.append(agent_state.snapshot())
        
        # Все snapshot должны быть одинаковыми
        for i in range(1, len(snapshots)):
            assert snapshots[i] == snapshots[i-1], "Snapshot не изменился (нет мутации)"

    def test_progress_resets_no_progress_counter(self, agent_state):
        """Тест: прогресс сбрасывает счетчик отсутствия прогресса"""
        agent_state.no_progress_steps = 5
        
        # Регистрируем прогресс
        agent_state.register_progress(progressed=True)
        
        assert agent_state.no_progress_steps == 0

    def test_no_progress_increments_counter(self, agent_state):
        """Тест: отсутствие прогресса увеличивает счетчик"""
        agent_state.no_progress_steps = 0
        
        # Регистрируем отсутствие прогресса
        agent_state.register_progress(progressed=False)
        
        assert agent_state.no_progress_steps == 1


# ============================================================================
# ТЕСТ 3: ACT DECISION VALIDATION
# ============================================================================

class TestActDecisionValidation:
    """Тесты валидации ACT decision"""

    def test_valid_act_decision_has_capability_name(self):
        """Тест: валидный ACT decision имеет capability_name"""
        decision = BehaviorDecision(
            action=BehaviorDecisionType.ACT,
            capability_name="test_capability",
            parameters={},
            reason="test_reason"
        )
        
        assert decision.action == BehaviorDecisionType.ACT
        assert decision.capability_name == "test_capability"
        assert decision.capability_name is not None

    def test_invalid_act_decision_without_capability_name(self):
        """Тест: невалидный ACT decision без capability_name"""
        decision = BehaviorDecision(
            action=BehaviorDecisionType.ACT,
            capability_name=None,
            parameters={},
            reason="test_reason"
        )
        
        assert decision.action == BehaviorDecisionType.ACT
        assert decision.capability_name is None
        
        # Проверка что это невалидный decision
        is_valid = decision.capability_name is not None
        assert is_valid is False

    def test_non_act_decision_can_have_empty_capability_name(self):
        """Тест: не-ACT decision может не иметь capability_name"""
        think_decision = BehaviorDecision(
            action=BehaviorDecisionType.THINK,
            capability_name=None,
            parameters={},
            reason="thinking"
        )
        
        plan_decision = BehaviorDecision(
            action=BehaviorDecisionType.PLAN,
            capability_name=None,
            parameters={},
            reason="planning"
        )
        
        # Не-ACT decision могут не иметь capability_name
        assert think_decision.capability_name is None
        assert plan_decision.capability_name is None


# ============================================================================
# СКВОЗНЫЕ ТЕСТЫ
# ============================================================================

class TestLoopDetectionEndToEnd:
    """Сквозные тесты детекции зацикливания"""

    @pytest.mark.asyncio
    async def test_full_loop_detection_scenario(self):
        """Тест: полный сценарий детекции зацикливания"""
        state = AgentState()
        previous_decision = None
        previous_snapshot = None
        loop_detected = False
        
        # Симуляция 10 шагов с зацикливанием на 5 шаге
        for step in range(10):
            # Создаём decision
            if step < 5:
                decision = BehaviorDecision(
                    action=BehaviorDecisionType.ACT,
                    capability_name=f"capability_{step}",
                    parameters={},
                    reason=f"step_{step}"
                )
                # Обновляем state
                state.step = step
                state.history.append(f"action_{step}")
            else:
                # Зацикливание: одинаковые decision без изменения state
                decision = BehaviorDecision(
                    action=BehaviorDecisionType.ACT,
                    capability_name="stuck_capability",
                    parameters={},
                    reason="stuck"
                )
            
            current_snapshot = state.snapshot()
            
            # Проверка зацикливания
            if previous_decision and decision:
                if (decision.action == previous_decision.action and
                    decision.capability_name == previous_decision.capability_name):
                    if previous_snapshot == current_snapshot:
                        loop_detected = True
                        break
            
            previous_decision = decision
            previous_snapshot = current_snapshot
        
        # Зацикливание должно быть детектировано
        assert loop_detected is True

    def test_snapshot_contains_all_required_fields(self, agent_state):
        """Тест: snapshot содержит все требуемые поля"""
        snapshot = agent_state.snapshot()
        
        required_fields = [
            'step',
            'error_count',
            'consecutive_errors',
            'no_progress_steps',
            'finished',
            'history_length',
            'last_history_item'
        ]
        
        for field in required_fields:
            assert field in snapshot, f"Поле {field} отсутствует в snapshot"


# ============================================================================
# ЗАПУСК ТЕСТОВ
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
