import pytest
import asyncio
from unittest.mock import Mock

from core.application.behaviors.react.pattern import ReActPattern
from core.application.behaviors.base import BehaviorDecision, BehaviorDecisionType


@pytest.mark.asyncio
async def test_behavior_contracts_validation():
    """Тест валидации входных данных через ContractService"""
    
    # Создаем mock сервисов
    mock_prompt_service = Mock()
    
    # Создаем паттерн
    react_pattern = ReActPattern(prompt_service=mock_prompt_service)
    
    # Создаем mock объекты для тестирования
    mock_session_context = Mock()
    mock_capability = Mock()
    mock_capability.name = "test.capability"
    mock_capability.skill_name = "test_skill"
    mock_capability.supported_strategies = ["react"]
    
    available_capabilities = [mock_capability]
    
    # Тестируем analyze_context
    context_analysis = await react_pattern.analyze_context(
        session_context=mock_session_context,
        available_capabilities=available_capabilities,
        context_analysis={}
    )
    
    # Проверяем, что анализ контекста вернул ожидаемые данные
    assert "available_capabilities" in context_analysis
    assert "no_progress_steps" in context_analysis
    assert "consecutive_errors" in context_analysis
    
    # Проверяем фильтрацию capability
    filtered_caps = context_analysis["available_capabilities"]
    assert len(filtered_caps) == 1
    assert filtered_caps[0].name == "test.capability"
    
    # Тестируем generate_decision
    mock_session_context.get_goal.return_value = "test goal"
    
    # Создаем mock для валидации параметров
    from core.agent_runtime.strategies.react.schema_validator import SchemaValidator
    validator = SchemaValidator()
    
    # Проверяем, что паттерн может обработать различные типы входных данных
    # и что он следует контрактам поведения
    
    # Создаем тестовое решение
    decision = BehaviorDecision(
        action=BehaviorDecisionType.ACT,
        capability_name="test.capability",
        parameters={"input": "test input"},
        reason="test reason"
    )
    
    # Проверяем, что решение соответствует ожидаемому формату
    assert decision.action in BehaviorDecisionType
    assert decision.capability_name == "test.capability"
    assert isinstance(decision.parameters, dict)
    assert isinstance(decision.reason, str)
    
    # Проверяем, что паттерн может обрабатывать различные типы решений
    stop_decision = BehaviorDecision(
        action=BehaviorDecisionType.STOP,
        reason="goal achieved"
    )
    
    assert stop_decision.action == BehaviorDecisionType.STOP
    assert stop_decision.reason == "goal achieved"


def test_behavior_input_validation():
    """Тест валидации входных данных для паттернов"""
    
    # Проверяем, что BehaviorDecision правильно валидирует свои поля
    decision = BehaviorDecision(
        action=BehaviorDecisionType.ACT,
        capability_name="test.capability",
        parameters={"input": "test"},
        reason="test reason",
        confidence=0.9
    )
    
    assert decision.action == BehaviorDecisionType.ACT
    assert decision.capability_name == "test.capability"
    assert decision.parameters == {"input": "test"}
    assert decision.reason == "test reason"
    assert decision.confidence == 0.9
    
    # Проверяем значения по умолчанию
    minimal_decision = BehaviorDecision(action=BehaviorDecisionType.STOP)
    assert minimal_decision.action == BehaviorDecisionType.STOP
    assert minimal_decision.capability_name is None
    assert minimal_decision.parameters is None
    assert minimal_decision.reason == ""
    assert minimal_decision.confidence == 1.0


@pytest.mark.asyncio
async def test_capability_filtering_contract():
    """Тест контракта фильтрации capability"""
    
    # Создаем mock сервисов
    mock_prompt_service = Mock()
    
    # Создаем паттерн
    react_pattern = ReActPattern(prompt_service=mock_prompt_service)
    
    # Создаем mock capability
    cap1 = Mock()
    cap1.skill_name = "book_library"
    cap1.supported_strategies = ["react", "planning"]
    
    cap2 = Mock()
    cap2.skill_name = "sql_query"
    cap2.supported_strategies = ["react"]
    
    cap3 = Mock()
    cap3.skill_name = "planning"
    cap3.supported_strategies = ["planning"]
    
    all_caps = [cap1, cap2, cap3]
    
    # Тестируем фильтрацию
    filtered_caps = react_pattern._filter_capabilities(
        all_caps,
        ["book_library", "sql_query"]
    )
    
    # Проверяем, что остались только те, у которых skill_name в списке
    # и которые поддерживают "react" стратегию
    assert len(filtered_caps) == 2  # cap1 и cap2
    skill_names = [cap.skill_name for cap in filtered_caps]
    assert "book_library" in skill_names
    assert "sql_query" in skill_names
    assert "planning" not in skill_names  # потому что не в списке required_skills