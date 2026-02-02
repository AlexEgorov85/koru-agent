"""Тесты для атомарных действий"""
import pytest
from application.orchestration.atomic_actions.actions import THINK, ACT, OBSERVE, PLAN, REFLECT, EVALUATE, VERIFY, ADAPT


class TestAtomicActions:
    """Тесты для атомарных действий"""
    
    def test_think_action_creation(self):
        """Тест создания действия THINK"""
        action = THINK()
        assert action is not None
        assert isinstance(action, THINK)
    
    def test_act_action_creation(self):
        """Тест создания действия ACT"""
        action = ACT()
        assert action is not None
        assert isinstance(action, ACT)
    
    def test_observe_action_creation(self):
        """Тест создания действия OBSERVE"""
        action = OBSERVE()
        assert action is not None
        assert isinstance(action, OBSERVE)
    
    def test_plan_action_creation(self):
        """Тест создания действия PLAN"""
        action = PLAN()
        assert action is not None
        assert isinstance(action, PLAN)
    
    def test_reflect_action_creation(self):
        """Тест создания действия REFLECT"""
        action = REFLECT()
        assert action is not None
        assert isinstance(action, REFLECT)
    
    def test_evaluate_action_creation(self):
        """Тест создания действия EVALUATE"""
        action = EVALUATE()
        assert action is not None
        assert isinstance(action, EVALUATE)
    
    def test_verify_action_creation(self):
        """Тест создания действия VERIFY"""
        action = VERIFY()
        assert action is not None
        assert isinstance(action, VERIFY)
    
    def test_adapt_action_creation(self):
        """Тест создания действия ADAPT"""
        action = ADAPT()
        assert action is not None
        assert isinstance(action, ADAPT)
    
    def test_all_atomic_actions_are_distinct(self):
        """Тест что все атомарные действия различны"""
        actions = [THINK(), ACT(), OBSERVE(), PLAN(), REFLECT(), EVALUATE(), VERIFY(), ADAPT()]
        action_types = [type(action) for action in actions]
        # Проверяем, что все типы уникальны
        assert len(set(action_types)) == len(action_types)
