"""
Тесты для интеграции FailureMemory и BehaviorManager.

Проверяет:
1. BehaviorManager получает FailureMemory
2. Проверка should_switch_pattern при генерации decision
3. Возврат SWITCH decision при рекомендации FailureMemory
4. Интеграция с AgentRuntime
"""
import pytest
from unittest.mock import MagicMock, AsyncMock

from core.models.data.capability import Capability
from core.agent.behaviors.base import BehaviorDecision, BehaviorDecisionType
from core.agent.components.behavior_manager import BehaviorManager
from core.agent.components.failure_memory import FailureMemory
from core.models.enums.common_enums import ErrorType


class TestBehaviorManagerFailureMemoryIntegration:
    """Тесты интеграции BehaviorManager и FailureMemory."""

    @pytest.fixture
    def mock_app_context(self):
        """Создаёт мок ApplicationContext."""
        mock = MagicMock()
        mock.infrastructure_context = MagicMock()
        mock.infrastructure_context.event_bus = AsyncMock()
        mock.get_service = MagicMock(return_value=MagicMock())
        return mock

    @pytest.fixture
    def mock_pattern(self):
        """Создаёт мок паттерна поведения."""
        mock = MagicMock()
        mock.pattern_id = "test_pattern"
        mock.analyze_context = AsyncMock(return_value={})
        mock.generate_decision = AsyncMock(
            return_value=BehaviorDecision(
                action=BehaviorDecisionType.ACT,
                capability_name="test.capability",
                parameters={},
                reason="Test decision"
            )
        )
        return mock

    @pytest.fixture
    def mock_storage(self, mock_pattern):
        """Создаёт мок BehaviorStorage."""
        mock = MagicMock()
        mock.load_pattern_by_component = AsyncMock(return_value=mock_pattern)
        return mock

    @pytest.mark.asyncio
    async def test_behavior_manager_receives_failure_memory(self, mock_app_context):
        """Тест: BehaviorManager получает FailureMemory."""
        failure_memory = FailureMemory()
        
        behavior_manager = BehaviorManager(
            application_context=mock_app_context,
            failure_memory=failure_memory
        )
        
        assert behavior_manager._failure_memory is failure_memory

    @pytest.mark.asyncio
    async def test_switch_pattern_on_failure_memory_recommendation(
        self, mock_app_context, mock_pattern, mock_storage
    ):
        """Тест: переключение паттерна при рекомендации FailureMemory."""
        failure_memory = FailureMemory()
        
        # Записываем 2 ошибки чтобы вызвать should_switch_pattern
        failure_memory.record(
            capability="test.capability",
            error_type=ErrorType.TRANSIENT,
        )
        failure_memory.record(
            capability="test.capability",
            error_type=ErrorType.TRANSIENT,
        )
        
        assert failure_memory.should_switch_pattern("test.capability") is True
        
        behavior_manager = BehaviorManager(
            application_context=mock_app_context,
            failure_memory=failure_memory
        )
        behavior_manager._behavior_storage = mock_storage
        behavior_manager._current_pattern = mock_pattern
        
        # Генерируем decision
        decision = await behavior_manager.generate_next_decision(
            session_context=MagicMock(),
            available_capabilities=[Capability(name="test.capability", description="Test", skill_name="test")]
        )
        
        # Должен вернуть SWITCH decision
        assert decision.action == BehaviorDecisionType.SWITCH
        # StrategySelector выбирает паттерн, обычно react_pattern при ошибках
        assert decision.next_pattern in ["react_pattern", "planning_pattern", "evaluation_pattern"]
        assert "failure_memory_recommendation" in decision.reason

    @pytest.mark.asyncio
    async def test_no_switch_on_single_error(
        self, mock_app_context, mock_pattern, mock_storage
    ):
        """Тест: нет переключения при одной ошибке."""
        failure_memory = FailureMemory()
        
        # Записываем только 1 ошибку
        failure_memory.record(
            capability="test.capability",
            error_type=ErrorType.TRANSIENT,
        )
        
        assert failure_memory.should_switch_pattern("test.capability") is False
        
        behavior_manager = BehaviorManager(
            application_context=mock_app_context,
            failure_memory=failure_memory
        )
        behavior_manager._behavior_storage = mock_storage
        behavior_manager._current_pattern = mock_pattern
        
        # Генерируем decision
        decision = await behavior_manager.generate_next_decision(
            session_context=MagicMock(),
            available_capabilities=[Capability(name="test.capability", description="Test", skill_name="test")]
        )
        
        # Должен вернуть ACT decision (не SWITCH)
        assert decision.action == BehaviorDecisionType.ACT
        assert decision.capability_name == "test.capability"

    @pytest.mark.asyncio
    async def test_no_switch_without_failure_memory(
        self, mock_app_context, mock_pattern, mock_storage
    ):
        """Тест: нет переключения без FailureMemory."""
        behavior_manager = BehaviorManager(
            application_context=mock_app_context,
            failure_memory=None  # Без FailureMemory
        )
        behavior_manager._behavior_storage = mock_storage
        behavior_manager._current_pattern = mock_pattern
        
        # Генерируем decision
        decision = await behavior_manager.generate_next_decision(
            session_context=MagicMock(),
            available_capabilities=[Capability(name="test.capability", description="Test", skill_name="test")]
        )
        
        # Должен вернуть ACT decision (не SWITCH)
        assert decision.action == BehaviorDecisionType.ACT

    @pytest.mark.asyncio
    async def test_switch_on_logic_errors(
        self, mock_app_context, mock_pattern, mock_storage
    ):
        """Тест: переключение при LOGIC ошибках."""
        failure_memory = FailureMemory()
        
        # Записываем 3 последовательные LOGIC ошибки
        for _ in range(3):
            failure_memory.record(
                capability="logic.capability",
                error_type=ErrorType.LOGIC,
            )
        
        assert failure_memory.should_switch_pattern("logic.capability") is True
        
        behavior_manager = BehaviorManager(
            application_context=mock_app_context,
            failure_memory=failure_memory
        )
        behavior_manager._behavior_storage = mock_storage
        behavior_manager._current_pattern = mock_pattern
        
        # Меняем capability_name в decision
        mock_pattern.generate_decision = AsyncMock(
            return_value=BehaviorDecision(
                action=BehaviorDecisionType.ACT,
                capability_name="logic.capability",
                parameters={},
                reason="Test decision"
            )
        )
        
        # Генерируем decision
        decision = await behavior_manager.generate_next_decision(
            session_context=MagicMock(),
            available_capabilities=[Capability(name="logic.capability", description="Test", skill_name="logic")]
        )
        
        # Должен вернуть SWITCH decision
        assert decision.action == BehaviorDecisionType.SWITCH
        # StrategySelector выбирает паттерн, обычно react_pattern при LOGIC ошибках
        assert decision.next_pattern in ["react_pattern", "planning_pattern", "evaluation_pattern"]


class TestAgentRuntimeIntegration:
    """Тесты интеграции AgentRuntime с FailureMemory."""

    @pytest.fixture
    def mock_app_context(self):
        """Создаёт мок ApplicationContext."""
        mock = MagicMock()
        mock.is_ready = True
        mock.infrastructure_context = MagicMock()
        mock.infrastructure_context.is_ready = True
        mock.infrastructure_context.event_bus = AsyncMock()
        mock.session_context = MagicMock()
        mock.session_context.session_id = "test_session"
        mock.get_service = MagicMock(return_value=MagicMock())
        return mock

    @pytest.mark.asyncio
    async def test_runtime_passes_failure_memory_to_behavior_manager(self, mock_app_context):
        """Тест: AgentRuntime передаёт failure_memory в BehaviorManager."""
        from core.agent.runtime import AgentRuntime
        
        runtime = AgentRuntime(
            application_context=mock_app_context,
            goal="Тестовая цель"
        )
        
        # Проверяем что failure_memory один и тот же
        assert runtime.failure_memory is runtime.behavior_manager._failure_memory

    @pytest.mark.asyncio
    async def test_full_integration_workflow(self, mock_app_context):
        """Тест: полный цикл интеграции."""
        from core.agent.runtime import AgentRuntime
        
        runtime = AgentRuntime(
            application_context=mock_app_context,
            goal="Тестовая цель",
            max_steps=5
        )
        
        # Записываем ошибки в failure_memory
        runtime.failure_memory.record(
            capability="test.capability",
            error_type=ErrorType.TRANSIENT,
        )
        runtime.failure_memory.record(
            capability="test.capability",
            error_type=ErrorType.TRANSIENT,
        )
        
        # Проверяем что failure_memory доступен в behavior_manager
        assert runtime.behavior_manager._failure_memory.should_switch_pattern("test.capability") is True


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
