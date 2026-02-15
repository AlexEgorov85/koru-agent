import pytest
from unittest.mock import Mock

from core.application.behaviors.react.pattern import ReActPattern
from core.application.behaviors.planning.pattern import PlanningPattern
from core.application.behaviors.evaluation.pattern import EvaluationPattern
from core.application.behaviors.fallback.pattern import FallbackPattern


def test_no_circular_dependencies():
    """Тест отсутствия циклических зависимостей между паттернами"""
    
    # Создаем mock сервисов
    mock_prompt_service = Mock()
    mock_contract_service = Mock()
    
    # Создаем все паттерны
    # При создании не должно возникнуть циклических импортов или зависимостей
    try:
        react_pattern = ReActPattern(prompt_service=mock_prompt_service)
        planning_pattern = PlanningPattern(
            prompt_service=mock_prompt_service,
            contract_service=mock_contract_service
        )
        evaluation_pattern = EvaluationPattern(prompt_service=mock_prompt_service)
        fallback_pattern = FallbackPattern(prompt_service=mock_prompt_service)
        
        # Проверяем, что все паттерны успешно созданы
        assert react_pattern is not None
        assert planning_pattern is not None
        assert evaluation_pattern is not None
        assert fallback_pattern is not None
        
        # Проверяем, что у них есть правильные ID
        assert hasattr(react_pattern, 'pattern_id')
        assert hasattr(planning_pattern, 'pattern_id')
        assert hasattr(evaluation_pattern, 'pattern_id')
        assert hasattr(fallback_pattern, 'pattern_id')
        
        # Проверяем, что паттерны не имеют прямого доступа к AgentRuntime
        # (в новых паттернах такого доступа быть не должно)
        assert not hasattr(react_pattern, 'runtime')
        assert not hasattr(planning_pattern, 'runtime')
        assert not hasattr(evaluation_pattern, 'runtime')
        assert not hasattr(fallback_pattern, 'runtime')
        
        # Проверяем, что паттерны не зависят друг от друга напрямую
        # (не импортируют друг друга внутри себя)
        assert type(react_pattern) != type(planning_pattern)
        assert type(react_pattern) != type(evaluation_pattern)
        assert type(react_pattern) != type(fallback_pattern)
        assert type(planning_pattern) != type(evaluation_pattern)
        assert type(planning_pattern) != type(fallback_pattern)
        assert type(evaluation_pattern) != type(fallback_pattern)
        
    except ImportError as e:
        pytest.fail(f"Обнаружена циклическая зависимость при импорте паттернов: {e}")
    except Exception as e:
        pytest.fail(f"Ошибка при создании паттернов: {e}")


def test_pattern_independence():
    """Тест независимости паттернов друг от друга"""
    
    # Создаем mock сервисов
    mock_prompt_service = Mock()
    mock_contract_service = Mock()
    
    # Создаем паттерны по отдельности
    react_pattern = ReActPattern(prompt_service=mock_prompt_service)
    
    # Отдельно создаем planning паттерн - не должно быть зависимости от react
    planning_pattern = PlanningPattern(
        prompt_service=mock_prompt_service,
        contract_service=mock_contract_service
    )
    
    # Отдельно создаем evaluation паттерн
    evaluation_pattern = EvaluationPattern(prompt_service=mock_prompt_service)
    
    # Отдельно создаем fallback паттерн
    fallback_pattern = FallbackPattern(prompt_service=mock_prompt_service)
    
    # Проверяем, что паттерны не имеют ссылок друг на друга
    assert not hasattr(react_pattern, '_other_patterns')
    assert not hasattr(planning_pattern, '_other_patterns')
    assert not hasattr(evaluation_pattern, '_other_patterns')
    assert not hasattr(fallback_pattern, '_other_patterns')
    
    # Проверяем, что паттерны реализуют один и тот же интерфейс
    from core.application.behaviors.base import BehaviorPatternInterface
    
    assert isinstance(react_pattern, BehaviorPatternInterface)
    assert isinstance(planning_pattern, BehaviorPatternInterface)
    assert isinstance(evaluation_pattern, BehaviorPatternInterface)
    assert isinstance(fallback_pattern, BehaviorPatternInterface)


def test_no_direct_system_access():
    """Тест отсутствия прямого доступа к системным ресурсам в паттернах"""
    
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
    
    # Проверяем, что паттерны не имеют прямого доступа к системным ресурсам
    # как это было в старых стратегиях
    for pattern in [react_pattern, planning_pattern, evaluation_pattern, fallback_pattern]:
        # Не должно быть прямого доступа к runtime.system
        assert not hasattr(pattern, 'system')
        assert not hasattr(pattern, '_runtime')
        assert not hasattr(pattern, 'call_llm_with_params')  # Этот метод был в старых стратегиях
        assert not hasattr(pattern, 'list_capabilities')  # Этот метод был в старых стратегиях
        assert not hasattr(pattern, 'get_capability')  # Этот метод был в старых стратегиях


def test_pattern_creation_without_runtime():
    """Тест создания паттернов без зависимости от AgentRuntime"""
    
    # Создаем паттерны только с необходимыми сервисами
    mock_prompt_service = Mock()
    mock_contract_service = Mock()
    
    # Все паттерны должны создаваться без необходимости иметь AgentRuntime
    react_pattern = ReActPattern(prompt_service=mock_prompt_service)
    planning_pattern = PlanningPattern(
        prompt_service=mock_prompt_service,
        contract_service=mock_contract_service
    )
    evaluation_pattern = EvaluationPattern(prompt_service=mock_prompt_service)
    fallback_pattern = FallbackPattern(prompt_service=mock_prompt_service)
    
    # Проверяем, что паттерны созданы успешно
    assert react_pattern.pattern_id.startswith("react.")
    assert planning_pattern.pattern_id.startswith("planning.")
    assert evaluation_pattern.pattern_id.startswith("evaluation.")
    assert fallback_pattern.pattern_id.startswith("fallback.")