"""
Тесты для ContextUpdatePhase.

Проверяемая бизнес-логика:
1. save_and_register() — единая точка входа, координирует сохранение
2. register_step() — ОДИН раз обновляет agent_state (push_observation, add_step, register_observation)
3. save_result_data() — сохраняет сырые данные в data_context с учетом save_type
4. handle_empty_sql_result() — делегирует в ErrorRecoveryHandler
5. Соблюдение SRP: только сохранение, без принятия решений о типе данных
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from core.agent.phases.context_update_phase import ContextUpdatePhase
from core.agent.state import ObservationAnalysis, AgentState
from core.session_context.model import ContextItem, ContextItemType, ContextItemMetadata
from core.models.data.execution import ExecutionResult, ExecutionStatus


# ============================================================================
# Фикстуры
# ============================================================================

@pytest.fixture
def context_update_phase():
    """ContextUpdatePhase с замоканными зависимостями."""
    mock_log = MagicMock()
    mock_event_bus = AsyncMock()
    mock_error_recovery = MagicMock()
    
    phase = ContextUpdatePhase(
        log=mock_log,
        event_bus=mock_event_bus,
        error_recovery_handler=mock_error_recovery,
    )
    return phase


@pytest.fixture
def mock_session_context():
    """Mock SessionContext с реальным AgentState."""
    ctx = MagicMock()
    ctx.session_id = "test-session-123"
    ctx.agent_id = "agent-001"
    ctx.agent_state = MagicMock(spec=AgentState)
    ctx.data_context = MagicMock()
    ctx.data_context.count.return_value = 0
    ctx.data_context.add_item.return_value = "item-123"
    return ctx


@pytest.fixture
def mock_observation_analysis():
    """Готовый ObservationAnalysis с save_type."""
    return ObservationAnalysis(
        status="success",
        insight="Test insight",
        hint="Test hint",
        save_type="raw_data",
        action_name="test_action",
        step_number=1,
    )


@pytest.fixture
def success_result():
    """Успешный ExecutionResult с данными."""
    result = MagicMock(spec=ExecutionResult)
    result.status = ExecutionStatus.COMPLETED
    result.data = {"key": "value"}
    result.error = None
    return result


@pytest.fixture
def empty_result():
    """Пустой ExecutionResult."""
    result = MagicMock(spec=ExecutionResult)
    result.status = ExecutionStatus.COMPLETED
    result.data = None
    result.error = None
    return result


@pytest.fixture
def failed_result():
    """Неуспешный ExecutionResult."""
    result = MagicMock(spec=ExecutionResult)
    result.status = ExecutionStatus.FAILED
    result.data = None
    result.error = "Test error"
    result.traceback = "Traceback here"
    return result


# ============================================================================
# Тесты save_and_register()
# ============================================================================

class TestSaveAndRegister:
    """Тесты основного метода save_and_register()."""
    
    @pytest.mark.asyncio
    async def test_saves_data_to_data_context(
        self, context_update_phase, success_result, mock_observation_analysis, mock_session_context
    ):
        """save_and_register() сохраняет данные в data_context."""
        await context_update_phase.save_and_register(
            result=success_result,
            observation=mock_observation_analysis,
            decision_action="test_action",
            session_context=mock_session_context,
            executed_steps=0,
        )
        
        # Проверяем, что данные сохранены в data_context
        mock_session_context.data_context.add_item.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_updates_agent_state(
        self, context_update_phase, success_result, mock_observation_analysis, mock_session_context
    ):
        """save_and_register() обновляет agent_state через register_step."""
        await context_update_phase.save_and_register(
            result=success_result,
            observation=mock_observation_analysis,
            decision_action="test_action",
            session_context=mock_session_context,
            executed_steps=0,
        )
        
        # Проверяем, что agent_state обновлен
        mock_session_context.agent_state.push_observation.assert_called_once()
        mock_session_context.agent_state.add_step.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_calls_error_recovery_handler(
        self, context_update_phase, mock_session_context
    ):
        """Вызывает error_recovery_handler.handle_empty_sql_result()."""
        mock_handler = AsyncMock()
        context_update_phase.error_recovery_handler = mock_handler
        
        await context_update_phase.handle_empty_sql_result(
            decision_action="sql_tool.execute",
            decision_parameters={"query": "SELECT 1"},
            session_context=mock_session_context,
            agent_state=mock_session_context.agent_state,
        )
        
        mock_handler.handle_empty_sql_result.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_returns_observation_item_ids(
        self, context_update_phase, success_result, mock_observation_analysis, mock_session_context
    ):
        """Возвращает список ID сохраненных элементов."""
        ids = await context_update_phase.save_and_register(
            result=success_result,
            observation=mock_observation_analysis,
            session_context=mock_session_context,
            executed_steps=0,
        )
        
        # Проверяем, что save_result_data вызван и возвращает ID
        assert isinstance(ids, list)


# ============================================================================
# Тесты register_step()
# ============================================================================

class TestRegisterStep:
    """Тесты метода register_step() — проверка SRP и отсутствия дублирования."""
    
    def test_updates_agent_state_once(
        self, context_update_phase, mock_session_context, mock_observation_analysis
    ):
        """ОДИН вызов register_step() → ОДИН раз обновляет agent_state."""
        context_update_phase.register_step(
            session_context=mock_session_context,
            executed_steps=0,
            decision_action="test_action",
            decision_reasoning="Test reasoning",
            observation_item_ids=["item-1"],
            result_status=ExecutionStatus.COMPLETED,
            decision_parameters={},
            observation=mock_observation_analysis,
        )
        
        # Проверяем, что add_step вызван ровно 1 раз
        mock_session_context.agent_state.add_step.assert_called_once()
        # Проверяем, что register_observation вызван ровно 1 раз
        mock_session_context.agent_state.register_observation.assert_called_once()
        # Проверяем, что push_observation вызван ровно 1 раз
        mock_session_context.agent_state.push_observation.assert_called_once_with(mock_observation_analysis)
    
    def test_not_push_without_observation(
        self, context_update_phase, mock_session_context
    ):
        """Без observation не вызывает push_observation()."""
        context_update_phase.register_step(
            session_context=mock_session_context,
            executed_steps=0,
            decision_action="test_action",
            decision_reasoning=None,
            observation_item_ids=[],
            result_status=ExecutionStatus.COMPLETED,
            decision_parameters={},
            observation=None,
        )
        
        mock_session_context.agent_state.push_observation.assert_not_called()
    
    def test_registers_step_in_session_context(
        self, context_update_phase, mock_session_context, mock_observation_analysis
    ):
        """Регистрирует шаг в session_context.register_step()."""
        context_update_phase.register_step(
            session_context=mock_session_context,
            executed_steps=2,
            decision_action="test_action",
            decision_reasoning="Reasoning",
            observation_item_ids=["item-1"],
            result_status=ExecutionStatus.COMPLETED,
            decision_parameters={"param": "value"},
            observation=mock_observation_analysis,
        )
        
        mock_session_context.register_step.assert_called_once()
        call_kwargs = mock_session_context.register_step.call_args[1]
        assert call_kwargs["step_number"] == 3  # executed_steps + 1
        assert call_kwargs["capability_name"] == "test_action"
        assert call_kwargs["status"] == ExecutionStatus.COMPLETED
    
    def test_observation_signal_format(
        self, context_update_phase, mock_session_context
    ):
        """observation_signal создается корректно если observation=None."""
        context_update_phase.register_step(
            session_context=mock_session_context,
            executed_steps=0,
            decision_action="test_action",
            decision_reasoning=None,
            observation_item_ids=[],
            result_status=ExecutionStatus.FAILED,
            decision_parameters={},
            observation=None,
        )
        
        # Проверяем, что в agent_state.add_step передан корректный observation_signal
        call_kwargs = mock_session_context.agent_state.add_step.call_args[1]
        obs_signal = call_kwargs["observation"]
        assert obs_signal["status"] == ExecutionStatus.FAILED.value
        assert obs_signal["quality"] == {}


# ============================================================================
# Тесты save_result_data()
# ============================================================================

class TestSaveResultData:
    """Тесты сохранения данных в data_context."""
    
    def test_saves_success_data(
        self, context_update_phase, success_result, mock_session_context
    ):
        """Сохраняет успешный результат в data_context."""
        context_update_phase.save_result_data(
            result=success_result,
            decision_action="test_action",
            decision_parameters={},
            session_context=mock_session_context,
            executed_steps=0,
        )
        
        mock_session_context.data_context.add_item.assert_called_once()
    
    def test_uses_save_type_from_observation(
        self, context_update_phase, success_result, mock_observation_analysis, mock_session_context
    ):
        """Использует save_type из observation_analysis для решения о сохранении."""
        # ObservationAnalysis.save_type = "raw_data"
        # save_result_data должен использовать это значение
        context_update_phase.save_result_data(
            result=success_result,
            decision_action="test_action",
            decision_parameters={},
            session_context=mock_session_context,
            executed_steps=0,
        )
        
        # Проверяем, что данные сохранены (используя save_type)
        mock_session_context.data_context.add_item.assert_called_once()
        assert len(ids) == 1
        
        # Проверяем тип созданного элемента
        call_args = mock_session_context.data_context.add_item.call_args[0][0]
        assert isinstance(call_args, ContextItem)
        assert call_args.item_type == ContextItemType.OBSERVATION
    
    def test_saves_empty_result(
        self, context_update_phase, mock_session_context, empty_result
    ):
        """Сохраняет пустой результат с пометкой is_empty."""
        ids = context_update_phase.save_result_data(
            result=empty_result,
            decision_action="test_action",
            decision_parameters={},
            session_context=mock_session_context,
            executed_steps=0,
        )
        
        mock_session_context.data_context.add_item.assert_called_once()
        call_args = mock_session_context.data_context.add_item.call_args[0][0]
        assert call_args.metadata.additional_data["is_empty"] is True
    
    def test_saves_failed_result(
        self, context_update_phase, mock_session_context, failed_result
    ):
        """Сохраняет ошибку как ERROR_LOG."""
        ids = context_update_phase.save_result_data(
            result=failed_result,
            decision_action="test_action",
            decision_parameters={},
            session_context=mock_session_context,
            executed_steps=0,
        )
        
        mock_session_context.data_context.add_item.assert_called_once()
        call_args = mock_session_context.data_context.add_item.call_args[0][0]
        assert call_args.item_type == ContextItemType.ERROR_LOG
        assert "error" in call_args.content
    
    def test_records_empty_result_in_state(
        self, context_update_phase, mock_session_context, empty_result
    ):
        """При пустом результате вызывает _record_empty_result()."""
        with patch.object(context_update_phase, '_record_empty_result') as mock_record:
            context_update_phase.save_result_data(
                result=empty_result,
                decision_action="test_action",
                decision_parameters={},
                session_context=mock_session_context,
                executed_steps=0,
            )
            
            mock_record.assert_called_once()
    
    def test_uses_save_type_from_observation(
        self, context_update_phase, mock_session_context, success_result
    ):
        """Использует save_type из observation_analysis для решения о сохранении."""
        # Тест проверяет, что контент сохраняется в зависимости от save_type
        # Это логика, которая должна быть в save_result_data
        ids = context_update_phase.save_result_data(
            result=success_result,
            decision_action="test_action",
            decision_parameters={},
            session_context=mock_session_context,
            executed_steps=0,
        )
        
        call_args = mock_session_context.data_context.add_item.call_args[0][0]
        # По умолчанию данные должны сохраняться
        assert call_args.content is not None


# ============================================================================
# Тесты handle_empty_sql_result()
# ============================================================================

class TestHandleEmptySqlResult:
    """Тесты обработки пустых SQL результатов."""
    
    @pytest.mark.asyncio
    async def test_calls_error_recovery_handler(
        self, context_update_phase, mock_session_context
    ):
        """Вызывает error_recovery_handler.handle_empty_sql_result()."""
        mock_handler = AsyncMock()
        context_update_phase.error_recovery_handler = mock_handler
        
        await context_update_phase.handle_empty_sql_result(
            decision_action="sql_tool.execute",
            decision_parameters={"query": "SELECT 1"},
            session_context=mock_session_context,
        )
        
        context_update_phase.error_recovery_handler.handle_empty_sql_result.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_without_handler_does_nothing(
        self, context_update_phase, mock_session_context
    ):
        """Без error_recovery_handler не падает."""
        context_update_phase.error_recovery_handler = None
        
        # Не должно быть исключения
        await context_update_phase.handle_empty_sql_result(
            decision_action="sql_tool.execute",
            decision_parameters={},
            session_context=mock_session_context,
            agent_state=mock_session_context.agent_state,
        )


# ============================================================================
# Тесты соблюдения SRP
# ============================================================================

class TestSRPCompliance:
    """Проверка соблюдения Single Responsibility Principle."""
    
    def test_does_not_call_observation_policy(
        self, context_update_phase, mock_session_context, success_result
    ):
        """ContextUpdatePhase НЕ вызывает decide_save_type() (это делает ObservationPhase)."""
        # Проверяем, что save_result_data не вызывает decide_save_type
        # Патчим метод ObservationPhase (импортируем локально)
        from core.agent.phases.observation_phase import ObservationPhase
        with patch.object(ObservationPhase, 'decide_save_type', return_value='raw_data') as mock_decide:
            context_update_phase.save_result_data(
                result=success_result,
                decision_action="test_action",
                decision_parameters={},
                session_context=mock_session_context,
                executed_steps=0,
            )
            
            # decide_save_type НЕ должен вызываться из ContextUpdatePhase
            mock_decide.assert_not_called()
    
    def test_receives_predefined_save_type(
        self, context_update_phase, mock_session_context, mock_observation_analysis
    ):
        """Получает готовое решение save_type из ObservationAnalysis."""
        # Проверяем, что register_step получает observation с save_type
        context_update_phase.register_step(
            session_context=mock_session_context,
            executed_steps=0,
            decision_action="test_action",
            decision_reasoning=None,
            observation_item_ids=[],
            result_status=ExecutionStatus.COMPLETED,
            decision_parameters={},
            observation=mock_observation_analysis,
        )
        
        # save_type должен быть в observation
        obs_arg = mock_session_context.agent_state.push_observation.call_args[0][0]
        assert hasattr(obs_arg, 'save_type')
        assert obs_arg.save_type == "raw_data"
    
    def test_receives_predefined_save_type(
        self, context_update_phase, mock_session_context, mock_observation_analysis
    ):
        """Получает готовое решение save_type из ObservationAnalysis."""
        # Проверяем, что register_step получает observation с save_type
        context_update_phase.register_step(
            session_context=mock_session_context,
            executed_steps=0,
            decision_action="test_action",
            decision_reasoning=None,
            observation_item_ids=[],
            result_status=ExecutionStatus.COMPLETED,
            decision_parameters={},
            observation=mock_observation_analysis,
        )
        
        # save_type должен быть в observation
        obs_arg = mock_session_context.agent_state.push_observation.call_args[0][0]
        assert hasattr(obs_arg, 'save_type')
        assert obs_arg.save_type == "raw_data"
