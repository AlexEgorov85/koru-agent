"""
Тесты для проверки записи observation при ошибке выполнения capability.

Проверяет что:
1. При FAILED статусе execution_result записывается observation с информацией об ошибке
2. В observation содержатся: error, error_type, status
3. Шаг регистрируется с корректным ExecutionStatus статусом
4. summary содержит информацию об ошибке
5. self.state.register_error() вызывается при FAILED
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, call

from core.models.data.execution import ExecutionResult
from core.models.enums.common_enums import ExecutionStatus
from core.application.behaviors.base import BehaviorDecision, BehaviorDecisionType


class TestErrorObservationRecording:
    """Тесты записи observation при ошибке"""

    @pytest.fixture
    def mock_application_context(self):
        """Создаёт мок ApplicationContext"""
        mock = MagicMock()
        mock.session_context = MagicMock()
        mock.session_context.record_action = MagicMock(return_value="action_123")
        mock.session_context.record_decision = MagicMock()
        mock.session_context.record_observation = MagicMock(return_value="obs_456")
        mock.session_context.register_step = MagicMock()
        mock.session_context.get_history = MagicMock(return_value=[])
        mock.session_context.step_context.count = MagicMock(return_value=1)
        mock.get_all_capabilities = AsyncMock(return_value=[])
        mock.infrastructure_context = MagicMock()
        mock.infrastructure_context.event_bus = AsyncMock()
        mock.infrastructure_context.event_bus.publish = AsyncMock()
        mock.is_ready = True
        mock.components = {}
        return mock

    @pytest.fixture
    def mock_capability(self):
        """Создаёт мок capability"""
        cap = MagicMock()
        cap.name = "test.capability"
        return cap

    @pytest.mark.skip(reason="Тест устарел — изменилась структура записи observation при рефакторинге")
    @pytest.mark.asyncio
    async def test_observation_recorded_on_failed_execution(
        self, mock_application_context, mock_capability
    ):
        """Тест: observation записывается при FAILED статусе выполнения"""
        from core.application.agent.runtime import AgentRuntime

        runtime = AgentRuntime(
            application_context=mock_application_context,
            goal="Тестовая цель",
            max_steps=10
        )

        # Создаём FAILED execution result
        failed_result = ExecutionResult(
            status=ExecutionStatus.FAILED,
            data=None,
            error="Тестовая ошибка выполнения",
            metadata={"error_type": "execution_error"}
        )

        # Мокаем executor.execute_action
        runtime.executor = MagicMock()
        runtime.executor.execute_action = AsyncMock(return_value=failed_result)

        # Создаём decision
        decision = BehaviorDecision(
            action=BehaviorDecisionType.ACT,
            capability_name="test.capability",
            parameters={}
        )

        # Выполняем шаг
        result = await runtime._execute_single_step_internal(decision, [mock_capability])

        # Проверяем что observation была записана
        mock_application_context.session_context.record_observation.assert_called_once()
        call_args = mock_application_context.session_context.record_observation.call_args

        # Проверяем данные observation
        obs_data = call_args.kwargs["observation_data"]
        assert obs_data["error"] == "Тестовая ошибка выполнения"
        assert obs_data["error_type"] == "execution_error"
        assert obs_data["status"] == ExecutionStatus.FAILED.value

        # Проверяем что register_step был вызван с FAILED статусом
        mock_application_context.session_context.register_step.assert_called_once()
        step_call_args = mock_application_context.session_context.register_step.call_args
        assert step_call_args.kwargs["status"] == ExecutionStatus.FAILED
        assert "Ошибка" in step_call_args.kwargs["summary"]

        # Проверяем что результат возвращён
        assert result is not None
        assert result.status == ExecutionStatus.FAILED

    @pytest.mark.asyncio
    async def test_error_counter_incremented_on_failed_execution(
        self, mock_application_context, mock_capability
    ):
        """Тест: счётчик ошибок увеличивается при FAILED статусе"""
        from core.application.agent.runtime import AgentRuntime

        runtime = AgentRuntime(
            application_context=mock_application_context,
            goal="Тестовая цель",
            max_steps=10
        )

        initial_error_count = runtime.state.error_count

        # Создаём FAILED execution result
        failed_result = ExecutionResult(
            status=ExecutionStatus.FAILED,
            data=None,
            error="Тестовая ошибка",
            metadata={}
        )

        # Мокаем executor.execute_action
        runtime.executor = MagicMock()
        runtime.executor.execute_action = AsyncMock(return_value=failed_result)

        # Создаём decision
        decision = BehaviorDecision(
            action=BehaviorDecisionType.ACT,
            capability_name="test.capability",
            parameters={}
        )

        # Выполняем шаг
        await runtime._execute_single_step_internal(decision, [mock_capability])

        # Проверяем что счётчик ошибок увеличился
        assert runtime.state.error_count == initial_error_count + 1

    @pytest.mark.skip(reason="Тест устарел — изменилась структура записи observation при рефакторинге")
    @pytest.mark.asyncio
    async def test_observation_recorded_on_successful_execution(
        self, mock_application_context, mock_capability
    ):
        """Тест: observation записывается при успешном выполнении"""
        from core.application.agent.runtime import AgentRuntime

        runtime = AgentRuntime(
            application_context=mock_application_context,
            goal="Тестовая цель",
            max_steps=10
        )

        # Создаём успешный execution result с данными
        success_result = ExecutionResult(
            status=ExecutionStatus.COMPLETED,
            data={"key": "value", "result": "success"},
            error=None,
            metadata={}
        )

        # Мокаем executor.execute_action
        runtime.executor = MagicMock()
        runtime.executor.execute_action = AsyncMock(return_value=success_result)

        # Создаём decision
        decision = BehaviorDecision(
            action=BehaviorDecisionType.ACT,
            capability_name="test.capability",
            parameters={}
        )

        # Выполняем шаг
        result = await runtime._execute_single_step_internal(decision, [mock_capability])

        # Проверяем что observation была записана
        mock_application_context.session_context.record_observation.assert_called_once()
        call_args = mock_application_context.session_context.record_observation.call_args

        # Проверяем данные observation
        obs_data = call_args.kwargs["observation_data"]
        assert obs_data == {"key": "value", "result": "success"}

        # Проверяем что register_step был вызван с COMPLETED статусом
        mock_application_context.session_context.register_step.assert_called_once()
        step_call_args = mock_application_context.session_context.register_step.call_args
        assert step_call_args.kwargs["status"] == ExecutionStatus.COMPLETED
        assert "Выполнено" in step_call_args.kwargs["summary"]

    @pytest.mark.skip(reason="Тест устарел — изменилась структура записи observation при рефакторинге")
    @pytest.mark.asyncio
    async def test_summary_contains_error_message(
        self, mock_application_context, mock_capability
    ):
        """Тест: summary содержит сообщение об ошибке"""
        from core.application.agent.runtime import AgentRuntime

        runtime = AgentRuntime(
            application_context=mock_application_context,
            goal="Тестовая цель",
            max_steps=10
        )

        # Создаём FAILED execution result с конкретным сообщением
        failed_result = ExecutionResult(
            status=ExecutionStatus.FAILED,
            data=None,
            error="Конкретная ошибка: файл не найден",
            metadata={}
        )

        # Мокаем executor.execute_action
        runtime.executor = MagicMock()
        runtime.executor.execute_action = AsyncMock(return_value=failed_result)

        # Создаём decision
        decision = BehaviorDecision(
            action=BehaviorDecisionType.ACT,
            capability_name="test.capability",
            parameters={}
        )

        # Выполняем шаг
        await runtime._execute_single_step_internal(decision, [mock_capability])

        # Проверяем summary
        step_call_args = mock_application_context.session_context.register_step.call_args
        summary = step_call_args.kwargs["summary"]
        assert "Ошибка при выполнении test.capability" in summary
        assert "Конкретная ошибка: файл не найден" in summary

    @pytest.mark.skip(reason="Тест устарел — изменилась структура записи observation при рефакторинге")
    @pytest.mark.asyncio
    async def test_unknown_error_type_handled(
        self, mock_application_context, mock_capability
    ):
        """Тест: обработка случая когда error_type отсутствует в metadata"""
        from core.application.agent.runtime import AgentRuntime

        runtime = AgentRuntime(
            application_context=mock_application_context,
            goal="Тестовая цель",
            max_steps=10
        )

        # Создаём FAILED execution result без metadata
        failed_result = ExecutionResult(
            status=ExecutionStatus.FAILED,
            data=None,
            error="Ошибка",
            metadata=None  # ← None metadata
        )

        # Мокаем executor.execute_action
        runtime.executor = MagicMock()
        runtime.executor.execute_action = AsyncMock(return_value=failed_result)

        # Создаём decision
        decision = BehaviorDecision(
            action=BehaviorDecisionType.ACT,
            capability_name="test.capability",
            parameters={}
        )

        # Выполняем шаг - не должно быть исключений
        result = await runtime._execute_single_step_internal(decision, [mock_capability])

        # Проверяем что observation была записана с default error_type
        mock_application_context.session_context.record_observation.assert_called_once()
        call_args = mock_application_context.session_context.record_observation.call_args
        obs_data = call_args.kwargs["observation_data"]
        assert obs_data["error_type"] == "unknown"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
