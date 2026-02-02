"""Тесты для навыка навигации по проекту"""
import pytest
from infrastructure.adapters.skills.project_navigator.skill import ProjectNavigatorSkill


class TestProjectNavigatorSkill:
    """Тесты для навыка навигации по проекту"""
    
    def test_project_navigator_skill_creation(self):
        """Тест создания навыка навигации по проекту"""
        skill = ProjectNavigatorSkill()
        
        # Проверяем, что объект создался успешно
        assert skill is not None
        assert hasattr(skill, 'execute')
        assert skill.name == "project_navigator"
    
    def test_project_navigator_skill_execute_method_exists(self):
        """Тест что у навыка навигации по проекту есть метод execute"""
        skill = ProjectNavigatorSkill()
        
        assert hasattr(skill, 'execute')
        assert callable(getattr(skill, 'execute'))
    
    def test_project_navigator_skill_get_capabilities(self):
        """Тест метода получения возможностей навыка"""
        skill = ProjectNavigatorSkill()
        
        capabilities = skill.get_capabilities()
        assert len(capabilities) >= 1 # Может быть больше одного capability
    
    def test_project_navigator_skill_str_representation(self):
        """Тест строкового представления навыка навигации по проекту"""
        skill = ProjectNavigatorSkill()
        
        # Проверяем, что строковое представление содержит имя класса
        assert "ProjectNavigatorSkill" in str(skill)
    
    def test_project_navigator_skill_repr_contains_class_name(self):
        """Тест repr содержит название класса"""
        skill = ProjectNavigatorSkill()
        
        repr_str = repr(skill)
        assert "ProjectNavigatorSkill" in repr_str
