"""
Тесты для AgentPolicy в agent_runtime.policy.
"""
import pytest
from core.agent_runtime.policy import AgentPolicy
from models.agent_state import AgentState


class TestAgentPolicy:
    """Тесты для AgentPolicy."""
    
    def test_agent_policy_initialization(self):
        """Тест инициализации AgentPolicy."""
        policy = AgentPolicy()
        
        assert policy.max_errors == 2
        assert policy.max_no_progress_steps == 3
    
    def test_agent_policy_custom_initialization(self):
        """Тест инициализации AgentPolicy с кастомными значениями."""
        policy = AgentPolicy(
            max_errors=5,
            max_no_progress_steps=10
        )
        
        assert policy.max_errors == 5
        assert policy.max_no_progress_steps == 10
    
    def test_should_fallback_default_threshold(self):
        """Тест метода should_fallback с порогом по умолчанию."""
        policy = AgentPolicy()  # max_errors = 2
        
        # Создаем состояние с разным количеством ошибок
        state_no_errors = AgentState(error_count=0)
        state_one_error = AgentState(error_count=1)
        state_two_errors = AgentState(error_count=2)  # пороговое значение
        state_three_errors = AgentState(error_count=3)  # выше порога
        
        # Проверяем, что fallback не нужен при малом количестве ошибок
        assert policy.should_fallback(state_no_errors) is False
        assert policy.should_fallback(state_one_error) is False
        
        # Проверяем, что fallback нужен при достижении и превышении порога
        assert policy.should_fallback(state_two_errors) is True
        assert policy.should_fallback(state_three_errors) is True
    
    def test_should_fallback_custom_threshold(self):
        """Тест метода should_fallback с кастомным порогом."""
        policy = AgentPolicy(max_errors=3)  # custom threshold
        
        state_two_errors = AgentState(error_count=2)
        state_three_errors = AgentState(error_count=3)  # пороговое значение
        state_four_errors = AgentState(error_count=4)  # выше порога
        
        # Проверяем, что fallback не нужен до достижения порога
        assert policy.should_fallback(state_two_errors) is False
        
        # Проверяем, что fallback нужен при достижении и превышении порога
        assert policy.should_fallback(state_three_errors) is True
        assert policy.should_fallback(state_four_errors) is True
    
    def test_should_stop_no_progress_default_threshold(self):
        """Тест метода should_stop_no_progress с порогом по умолчанию."""
        policy = AgentPolicy()  # max_no_progress_steps = 3
        
        # Создаем состояние с разным количеством шагов без прогресса
        state_no_progress_0 = AgentState(no_progress_steps=0)
        state_no_progress_1 = AgentState(no_progress_steps=1)
        state_no_progress_2 = AgentState(no_progress_steps=2)
        state_no_progress_3 = AgentState(no_progress_steps=3)  # пороговое значение
        state_no_progress_4 = AgentState(no_progress_steps=4)  # выше порога
        
        # Проверяем, что остановка не нужна при малом количестве шагов без прогресса
        assert policy.should_stop_no_progress(state_no_progress_0) is False
        assert policy.should_stop_no_progress(state_no_progress_1) is False
        assert policy.should_stop_no_progress(state_no_progress_2) is False
        
        # Проверяем, что остановка нужна при достижении и превышении порога
        assert policy.should_stop_no_progress(state_no_progress_3) is True
        assert policy.should_stop_no_progress(state_no_progress_4) is True
    
    def test_should_stop_no_progress_custom_threshold(self):
        """Тест метода should_stop_no_progress с кастомным порогом."""
        policy = AgentPolicy(max_no_progress_steps=5)  # custom threshold
        
        state_no_progress_4 = AgentState(no_progress_steps=4)
        state_no_progress_5 = AgentState(no_progress_steps=5)  # пороговое значение
        state_no_progress_6 = AgentState(no_progress_steps=6)  # выше порога
        
        # Проверяем, что остановка не нужна до достижения порога
        assert policy.should_stop_no_progress(state_no_progress_4) is False
        
        # Проверяем, что остановка нужна при достижении и превышении порога
        assert policy.should_stop_no_progress(state_no_progress_5) is True
        assert policy.should_stop_no_progress(state_no_progress_6) is True
    
    def test_combined_policy_scenarios(self):
        """Тест сценариев с комбинированной политикой."""
        policy = AgentPolicy(max_errors=2, max_no_progress_steps=3)
        
        # Состояние с превышением лимита ошибок, но не шагов без прогресса
        state_many_errors_few_no_progress = AgentState(error_count=3, no_progress_steps=1)
        assert policy.should_fallback(state_many_errors_few_no_progress) is True
        assert policy.should_stop_no_progress(state_many_errors_few_no_progress) is False
        
        # Состояние с превышением шагов без прогресса, но не ошибок
        state_few_errors_many_no_progress = AgentState(error_count=1, no_progress_steps=4)
        assert policy.should_fallback(state_few_errors_many_no_progress) is False
        assert policy.should_stop_no_progress(state_few_errors_many_no_progress) is True
        
        # Состояние с превышением обоих лимитов
        state_many_errors_many_no_progress = AgentState(error_count=3, no_progress_steps=4)
        assert policy.should_fallback(state_many_errors_many_no_progress) is True
        assert policy.should_stop_no_progress(state_many_errors_many_no_progress) is True
    
    def test_policy_with_other_state_attributes(self):
        """Тест политики с другими атрибутами состояния."""
        policy = AgentPolicy(max_errors=1, max_no_progress_steps=2)
        
        # Создаем состояние с другими атрибутами, кроме тех, что используются в политике
        state = AgentState(
            step=10,
            error_count=2,  # Превышает лимит ошибок (1)
            no_progress_steps=1,  # Ниже лимита (2)
            finished=False,
            history=["action1", "action2", "action3"]
        )
        
        # Проверяем, что политика основывается только на нужных атрибутах
        assert policy.should_fallback(state) is True  # error_count=2 > max_errors=1
        assert policy.should_stop_no_progress(state) is False  # no_progress_steps=1 < max_no_progress_steps=2
    
    def test_edge_case_zero_thresholds(self):
        """Тест крайнего случая с нулевыми порогами."""
        policy = AgentPolicy(max_errors=0, max_no_progress_steps=0)
        
        # Даже одна ошибка приведет к fallback
        state_one_error = AgentState(error_count=1)
        assert policy.should_fallback(state_one_error) is True
        
        # Даже один шаг без прогресса приведет к остановке
        state_one_no_progress = AgentState(no_progress_steps=1)
        assert policy.should_stop_no_progress(state_one_no_progress) is True
        
        # Даже без ошибок или без прогресса, если порог 0, то сразу триггер
        state_no_errors = AgentState(error_count=0)
        assert policy.should_fallback(state_no_errors) is False  # 0 не >= 0
        
        state_no_progress = AgentState(no_progress_steps=0)
        assert policy.should_stop_no_progress(state_no_progress) is False  # 0 не >= 0


def test_agent_policy_independence():
    """Тест независимости разных экземпляров AgentPolicy."""
    policy1 = AgentPolicy(max_errors=1, max_no_progress_steps=2)
    policy2 = AgentPolicy(max_errors=5, max_no_progress_steps=10)
    
    state = AgentState(error_count=3, no_progress_steps=5)
    
    # Проверяем, что разные политики дают разные результаты для одного состояния
    assert policy1.should_fallback(state) is True  # 3 >= 1
    assert policy2.should_fallback(state) is False  # 3 < 5
    
    assert policy1.should_stop_no_progress(state) is True  # 5 >= 2
    assert policy2.should_stop_no_progress(state) is False  # 5 < 10
    
    # Внутренние состояния политик не влияют друг на друга
    assert policy1.max_errors != policy2.max_errors
    assert policy1.max_no_progress_steps != policy2.max_no_progress_steps


def test_agent_policy_default_values_consistency():
    """Тест согласованности значений по умолчанию."""
    policy1 = AgentPolicy()
    policy2 = AgentPolicy()
    
    # Обе политики должны иметь одинаковые значения по умолчанию
    assert policy1.max_errors == policy2.max_errors == 2
    assert policy1.max_no_progress_steps == policy2.max_no_progress_steps == 3
    
    # И методы должны работать одинаково для одинаковых состояний
    state = AgentState(error_count=3, no_progress_steps=4)
    
    assert policy1.should_fallback(state) == policy2.should_fallback(state)
    assert policy1.should_stop_no_progress(state) == policy2.should_stop_no_progress(state)
    
    # Оба должны вернуть True, потому что оба лимита превышены
    assert policy1.should_fallback(state) is True
    assert policy1.should_stop_no_progress(state) is True


def test_policy_behavior_with_boundary_values():
    """Тест поведения политики с граничными значениями."""
    policy = AgentPolicy(max_errors=3, max_no_progress_steps=4)
    
    # Граничные значения для ошибок
    state_at_error_limit = AgentState(error_count=3)  # Ровно лимит
    state_above_error_limit = AgentState(error_count=4)  # Выше лимита
    state_below_error_limit = AgentState(error_count=2)  # Ниже лимита
    
    assert policy.should_fallback(state_at_error_limit) is True  # 3 >= 3
    assert policy.should_fallback(state_above_error_limit) is True  # 4 >= 3
    assert policy.should_fallback(state_below_error_limit) is False  # 2 < 3
    
    # Граничные значения для шагов без прогресса
    state_at_progress_limit = AgentState(no_progress_steps=4)  # Ровно лимит
    state_above_progress_limit = AgentState(no_progress_steps=5)  # Выше лимита
    state_below_progress_limit = AgentState(no_progress_steps=3)  # Ниже лимита
    
    assert policy.should_stop_no_progress(state_at_progress_limit) is True  # 4 >= 4
    assert policy.should_stop_no_progress(state_above_progress_limit) is True  # 5 >= 4
    assert policy.should_stop_no_progress(state_below_progress_limit) is False  # 3 < 4