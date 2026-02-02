"""Тесты для навыка карты проекта"""
import pytest
from domain.models.capability import Capability
from infrastructure.adapters.skills.project_map.skill import ProjectMapSkill



class TestProjectMapSkill:
    """Тесты для навыка карты проекта"""
    
    def test_project_map_skill_creation(self):
        """Тест создания навыка карты проекта"""
        skill = ProjectMapSkill()
        
        # Проверяем, что объект создался успешно
        assert skill is not None
        assert hasattr(skill, 'execute')
        assert skill.name == "project_map"
    
    def test_project_map_skill_execute_method_exists(self):
        """Тест что у навыка карты проекта есть метод execute"""
        skill = ProjectMapSkill()
        
        assert hasattr(skill, 'execute')
        assert callable(getattr(skill, 'execute'))
    
    def test_project_map_skill_get_capabilities(self):
        """Тест метода получения возможностей навыка"""
        skill = ProjectMapSkill()
        
        capabilities = skill.get_capabilities()
        assert len(capabilities) == 1
        assert isinstance(capabilities[0], Capability)
        assert capabilities[0].name == "project_map.analyze_project"
    
    def test_project_map_skill_str_representation(self):
        """Тест строкового представления навыка карты проекта"""
        skill = ProjectMapSkill()
        
        # Проверяем, что строковое представление содержит имя класса
        assert "ProjectMapSkill" in str(skill)
    
    def test_project_map_skill_repr_contains_class_name(self):
        """Тест repr содержит название класса"""
        skill = ProjectMapSkill()
        
        repr_str = repr(skill)
        assert "ProjectMapSkill" in repr_str
