"""
Тесты инвариантов ReActPattern.

Проверяют:
1. observe() мутирует state.history
2. generate_decision() вызывает LLM
3. LLM вызов гарантирован через InfrastructureError
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from core.models.errors import InfrastructureError, PatternError
from core.agent.behaviors.base import BehaviorDecisionType


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def mock_application_context():
    """Создаёт мок ApplicationContext"""
    mock = MagicMock()
    mock.session_context = MagicMock()
    mock.session_context.get_goal = MagicMock(return_value="Тестовая цель")
    mock.session_context.current_step = 0
    
    # Создаём правильный мок event_bus с async publish
    mock_event_bus = AsyncMock()
    mock_event_bus.publish = AsyncMock()
    
    mock_infrastructure = MagicMock()
    mock_infrastructure.event_bus = mock_event_bus
    mock.infrastructure_context = mock_infrastructure
    
    mock.get_provider = MagicMock(return_value=None)  # LLM провайдер по умолчанию недоступен
    return mock


@pytest.fixture
def mock_component_config():
    """Создаёт мок ComponentConfig"""
    mock = MagicMock()
    mock.resolved_prompts = {}
    mock.contracts = {}
    return mock


@pytest.fixture
def mock_executor():
    """Создаёт мок ActionExecutor"""
    mock = MagicMock()
    return mock


# ============================================================================
# ТЕСТ 1: LLm CALL GUARANTEE
# ============================================================================

class TestReActLLMGuarantee:
    """Тесты гарантии вызова LLM в ReActPattern"""

    @pytest.mark.asyncio
    async def test_llm_called_in_generate_decision(
        self, mock_application_context, mock_component_config, mock_executor
    ):
        """Тест: LLM вызывается в generate_decision"""
        from core.agent.behaviors.react.pattern import ReActPattern

        # Создаём паттерн
        pattern = ReActPattern(
            component_name="react_pattern",
            component_config=mock_component_config,
            application_context=mock_application_context,
            executor=mock_executor
        )

        # Мокаем LLM провайдер
        mock_llm = AsyncMock()
        mock_llm.generate_structured = AsyncMock(return_value={
            "raw_response": {
                "thought": "Тестовое рассуждение",
                "decision": {
                    "next_action": "test.capability",
                    "reasoning": "Тест",
                    "parameters": {}
                }
            }
        })
        mock_application_context.get_provider = MagicMock(return_value=mock_llm)

        # Инициализируем паттерн
        await pattern.initialize()

        # Создаём тестовые данные
        session_context = mock_application_context.session_context
        available_capabilities = []
        context_analysis = {
            "goal": "Тестовая цель",
            "last_steps": [],
            "no_progress_steps": 0,
            "consecutive_errors": 0
        }

        # Вызываем generate_decision
        decision = await pattern.generate_decision(
            session_context=session_context,
            available_capabilities=available_capabilities,
            context_analysis=context_analysis
        )

        # Проверяем что LLM был вызван
        mock_llm.generate_structured.assert_called_once()

        # Проверяем что решение возвращено
        assert decision is not None
        assert decision.action is not None

    @pytest.mark.asyncio
    async def test_infrastructure_error_if_llm_not_called(
        self, mock_application_context, mock_component_config, mock_executor
    ):
        """Тест: InfrastructureError если LLM не был вызван"""
        from core.agent.behaviors.react.pattern import ReActPattern

        # Создаём паттерн
        pattern = ReActPattern(
            component_name="react_pattern",
            component_config=mock_component_config,
            application_context=mock_application_context,
            executor=mock_executor
        )

        # Мокаем _perform_structured_reasoning чтобы он не вызывал LLM
        original_method = pattern._perform_structured_reasoning
        
        async def mock_reasoning(*args, **kwargs):
            # Возвращаем результат без вызова LLM
            return {
                "analysis": {
                    "current_situation": "Тест",
                    "progress_assessment": "Тест",
                    "confidence": 0.5,
                    "errors_detected": False,
                    "consecutive_errors": 0,
                    "execution_time": 0,
                    "no_progress_steps": 0
                },
                "decision": {
                    "next_action": "test.capability",
                    "reasoning": "Тест без LLM",
                    "parameters": {}
                },
                "available_capabilities": [],
                "needs_rollback": False
            }

        pattern._perform_structured_reasoning = mock_reasoning

        # Инициализируем паттерн
        await pattern.initialize()

        # Создаём тестовые данные
        session_context = mock_application_context.session_context
        available_capabilities = []
        context_analysis = {
            "goal": "Тестовая цель",
            "last_steps": [],
            "no_progress_steps": 0,
            "consecutive_errors": 0
        }

        # ТЕПЕРЬ: Проверяем что InfrastructureError выбрасывается
        # (так как LLM провайдер недоступен - это ошибка)
        from core.errors.exceptions import InfrastructureError, SkillExecutionError
        
        with pytest.raises((InfrastructureError, SkillExecutionError)):
            await pattern.generate_decision(
                session_context=session_context,
                available_capabilities=available_capabilities,
                context_analysis=context_analysis
            )


# ============================================================================
# ТЕСТ 2: STATE MUTATION INVARIANT
# ============================================================================

class TestStateMutationInvariant:
    """Тесты мутации состояния в ReActPattern"""

    def test_state_snapshot_changes_after_action(self):
        """Тест: snapshot состояния меняется после действия"""
        from core.agent.components.state import AgentState

        state = AgentState()
        snapshot_before = state.snapshot()

        # Симуляция действия
        state.step += 1
        state.history.append("test_action")

        snapshot_after = state.snapshot()

        # Snapshot должен измениться
        assert snapshot_before != snapshot_after
        assert snapshot_after['step'] == 1
        assert snapshot_after['history_length'] == 1

    def test_state_equality_comparison(self):
        """Тест: сравнение состояний"""
        from core.agent.components.state import AgentState

        state1 = AgentState(step=5, error_count=2)
        state2 = AgentState(step=5, error_count=2)
        state3 = AgentState(step=6, error_count=2)

        assert state1 == state2
        assert state1 != state3


# ============================================================================
# ТЕСТ 3: DECISION VALIDATION
# ============================================================================

class TestDecisionValidation:
    """Тесты валидации decision в ReActPattern"""

    @pytest.mark.asyncio
    async def test_act_decision_has_capability_name(
        self, mock_application_context, mock_component_config, mock_executor
    ):
        """Тест: ACT decision имеет capability_name"""
        from core.agent.behaviors.react.pattern import ReActPattern

        pattern = ReActPattern(
            component_name="react_pattern",
            component_config=mock_component_config,
            application_context=mock_application_context,
            executor=mock_executor
        )

        # Мокаем LLM провайдер
        mock_llm = AsyncMock()
        mock_llm.generate_structured = AsyncMock(return_value={
            "raw_response": {
                "thought": "Тестовое рассуждение",
                "decision": {
                    "next_action": "test.capability",
                    "reasoning": "Тест",
                    "parameters": {}
                }
            }
        })
        mock_application_context.get_provider = MagicMock(return_value=mock_llm)

        await pattern.initialize()

        session_context = mock_application_context.session_context
        available_capabilities = []
        context_analysis = {
            "goal": "Тестовая цель",
            "last_steps": [],
            "no_progress_steps": 0,
            "consecutive_errors": 0
        }

        decision = await pattern.generate_decision(
            session_context=session_context,
            available_capabilities=available_capabilities,
            context_analysis=context_analysis
        )

        # Если decision.action == ACT, capability_name должен быть указан
        if decision.action == BehaviorDecisionType.ACT:
            assert decision.capability_name is not None
            assert decision.capability_name != ""


# ============================================================================
# ТЕСТ 4: ERROR HANDLING
# ============================================================================

class TestErrorHandling:
    """Тесты обработки ошибок в ReActPattern"""

    @pytest.mark.asyncio
    async def test_raises_error_on_llm_unavailable(
        self, mock_application_context, mock_component_config, mock_executor
    ):
        """Тест: Выбрасывает InfrastructureError когда LLM недоступен"""
        from core.agent.behaviors.react.pattern import ReActPattern
        from core.errors.exceptions import InfrastructureError, SkillExecutionError

        # LLM провайдер недоступен (по умолчанию в mock_application_context)
        pattern = ReActPattern(
            component_name="react_pattern",
            component_config=mock_component_config,
            application_context=mock_application_context,
            executor=mock_executor
        )

        await pattern.initialize()

        session_context = mock_application_context.session_context
        available_capabilities = []
        context_analysis = {
            "goal": "Тестовая цель",
            "last_steps": [],
            "no_progress_steps": 0,
            "consecutive_errors": 0
        }

        # ТЕПЕРЬ: Должно выбросить ошибку вместо fallback
        with pytest.raises((InfrastructureError, SkillExecutionError)):
            await pattern.generate_decision(
                session_context=session_context,
                available_capabilities=available_capabilities,
                context_analysis=context_analysis
            )


# ============================================================================
# ЗАПУСК ТЕСТОВ
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
