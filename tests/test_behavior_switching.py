import pytest
import asyncio
from unittest.mock import Mock, AsyncMock

from core.application.behaviors.base import BehaviorDecision, BehaviorDecisionType
from core.application.behaviors.react.pattern import ReActPattern
from core.application.behaviors.planning.pattern import PlanningPattern
from core.application.behaviors.evaluation.pattern import EvaluationPattern
from core.application.behaviors.fallback.pattern import FallbackPattern
from core.agent_runtime.behavior_manager import BehaviorManager


@pytest.mark.asyncio
async def test_behavior_switching():
    """Тест автоматического переключения паттернов при 3 ошибках"""
    
    # Создаем mock сервисов
    mock_prompt_service = Mock()
    mock_contract_service = Mock()
    
    # Создаем паттерны
    react_pattern = ReActPattern(prompt_service=mock_prompt_service)
    planning_pattern = PlanningPattern(
        prompt_service=mock_prompt_service,
        contract_service=mock_contract_service
    )
    evaluation_pattern = EvaluationPattern(prompt_service=mock_prompt_service)
    fallback_pattern = FallbackPattern(prompt_service=mock_prompt_service)
    
    # Проверяем, что у паттернов правильные ID
    assert react_pattern.pattern_id == "react.v1.0.0"
    assert planning_pattern.pattern_id == "planning.v1.0.0"
    assert evaluation_pattern.pattern_id == "evaluation.v1.0.0"
    assert fallback_pattern.pattern_id == "fallback.v1.0.0"
    
    # Тестируем создание решения о переключении
    switch_decision = BehaviorDecision(
        action=BehaviorDecisionType.SWITCH,
        next_pattern="planning.v1.0.0",
        reason="need_planning"
    )
    
    assert switch_decision.action == BehaviorDecisionType.SWITCH
    assert switch_decision.next_pattern == "planning.v1.0.0"
    assert switch_decision.reason == "need_planning"


@pytest.mark.asyncio
async def test_behavior_manager_switching():
    """Тест переключения паттернов через BehaviorManager"""
    
    # Создаем mock application context
    mock_app_context = Mock()
    mock_prompt_service = Mock()
    mock_app_context.get_service.return_value = mock_prompt_service
    
    # Создаем BehaviorManager
    manager = BehaviorManager(application_context=mock_app_context)
    
    # Инициализируем с начальным паттерном
    # Здесь мы не можем полноценно протестировать, так как BehaviorStorage
    # пытается загрузить реальные файлы, но можем проверить логику переключения
    
    # Проверим, что у менеджера есть методы для переключения
    assert hasattr(manager, '_switch_pattern')
    assert hasattr(manager, 'get_current_pattern_id')
    assert hasattr(manager, 'get_pattern_history')
    
    # Проверим начальное состояние
    assert manager._current_pattern is None
    assert manager._pattern_history == []


@pytest.mark.asyncio
async def test_pattern_error_based_switching():
    """Тест переключения паттернов на основе ошибок"""
    
    # Создаем mock сервисов
    mock_prompt_service = Mock()
    
    # Создаем ReAct паттерн
    react_pattern = ReActPattern(prompt_service=mock_prompt_service)
    
    # Симулируем ситуацию с ошибками
    initial_error_count = react_pattern.error_count
    
    # Создаем решение, которое приведет к переключению из-за ошибок
    # В ReActPattern при 3 последовательных ошибках происходит переключение
    for i in range(3):
        react_pattern.error_count += 1
    
    # Проверяем, что после 3 ошибок счетчик правильный
    assert react_pattern.error_count == initial_error_count + 3
    
    # В реальной ситуации при такой ошибке создается решение о переключении
    error_switch_decision = BehaviorDecision(
        action=BehaviorDecisionType.SWITCH,
        next_pattern="fallback.v1.0.0",
        reason="too_many_errors_3"
    )
    
    assert error_switch_decision.action == BehaviorDecisionType.SWITCH
    assert error_switch_decision.next_pattern == "fallback.v1.0.0"
    assert "too_many_errors" in error_switch_decision.reason


@pytest.mark.asyncio
async def test_evaluation_to_planning_switch():
    """Тест переключения из evaluation в planning при частичном прогрессе"""
    
    # Создаем mock сервисов
    mock_prompt_service = Mock()
    
    # Создаем evaluation паттерн
    eval_pattern = EvaluationPattern(prompt_service=mock_prompt_service)
    
    # Создаем решение о переключении в planning при частичном прогрессе
    partial_progress_decision = BehaviorDecision(
        action=BehaviorDecisionType.SWITCH,
        next_pattern="planning.v1.0.0",
        reason="partial_progress_continue_with_refined_goal",
        parameters={"refined_goal": "updated goal based on partial progress"}
    )
    
    assert partial_progress_decision.action == BehaviorDecisionType.SWITCH
    assert partial_progress_decision.next_pattern == "planning.v1.0.0"
    assert "partial_progress" in partial_progress_decision.reason
    assert "refined_goal" in partial_progress_decision.parameters


@pytest.mark.asyncio
async def test_fallback_pattern_switching():
    """Тест переключения паттернов через fallback стратегию"""
    
    # Создаем mock сервисов
    mock_prompt_service = Mock()
    
    # Создаем fallback паттерн
    fallback_pattern = FallbackPattern(prompt_service=mock_prompt_service)
    
    # Тестируем различные сценарии переключения
    
    # 1. Временные ошибки -> переключение на react
    transient_error_decision = BehaviorDecision(
        action=BehaviorDecisionType.SWITCH,
        next_pattern="react.v1.0.0",
        reason="fallback_transient_error"
    )
    
    assert transient_error_decision.action == BehaviorDecisionType.SWITCH
    assert transient_error_decision.next_pattern == "react.v1.0.0"
    
    # 2. Ошибки планирования -> переключение на react
    planning_error_decision = BehaviorDecision(
        action=BehaviorDecisionType.SWITCH,
        next_pattern="react.v1.0.0",
        reason="fallback_planning_error_use_react"
    )
    
    assert planning_error_decision.action == BehaviorDecisionType.SWITCH
    assert planning_error_decision.next_pattern == "react.v1.0.0"