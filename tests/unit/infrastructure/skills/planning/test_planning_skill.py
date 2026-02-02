"""Тесты для навыка планирования"""
import pytest
from infrastructure.adapters.skills.planning.skill import PlanningSkill


class TestPlanningSkill:
    """Тесты для навыка планирования"""
    
    def test_planning_skill_creation(self):
        """Тест создания навыка планирования"""
        skill = PlanningSkill()
        
        # Проверяем, что объект создался успешно
        assert skill is not None
        assert hasattr(skill, 'execute')
        assert skill.name == "planning"
    
    def test_planning_skill_execute_method_exists(self):
        """Тест что у навыка планирования есть метод execute"""
        skill = PlanningSkill()
        
        assert hasattr(skill, 'execute')
        assert callable(getattr(skill, 'execute'))
    
    def test_planning_skill_get_capabilities(self):
        """Тест метода получения возможностей навыка"""
        skill = PlanningSkill()
        
        capabilities = skill.get_capabilities()
        assert len(capabilities) >= 1 # Может быть больше одного capability
    
    def test_planning_skill_str_representation(self):
        """Тест строкового представления навыка планирования"""
        skill = PlanningSkill()
        
        # Проверяем, что строковое представление содержит имя класса
        assert "PlanningSkill" in str(skill)
    
    def test_planning_skill_repr_contains_class_name(self):
        """Тест repr содержит название класса"""
        skill = PlanningSkill()
        
        repr_str = repr(skill)
        assert "PlanningSkill" in repr_str
