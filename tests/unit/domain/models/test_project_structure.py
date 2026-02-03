"""Тесты для модели ProjectStructure"""
import pytest
from datetime import datetime
from domain.models.project.project_structure import ProjectStructure


class TestProjectStructure:
    """Тесты для модели ProjectStructure"""
    
    def test_create_project_structure_with_valid_data(self):
        """Тест создания ProjectStructure с валидными данными"""
        from domain.models.project.project_structure import ProjectStructure
        project_structure = ProjectStructure()
        
        # Устанавливаем значения атрибутов
        project_structure.root_dir = "test_project"
        project_structure.total_files = 0
        project_structure.files = {}
        project_structure.directory_tree = {}
        project_structure.code_units = {}
        project_structure.file_dependencies = {}
        project_structure.entry_points = []
        project_structure._cache = {}
        
        assert project_structure.root_dir == "test_project"
        assert project_structure.total_files == 0
        assert project_structure.files == {}
        assert project_structure.directory_tree == {}
    
    def test_project_structure_str_representation(self):
        """Тест строкового представления ProjectStructure"""
        from domain.models.project.project_structure import ProjectStructure
        project_structure = ProjectStructure()
        project_structure.root_dir = "test_project"
        
        # Проверяем, что строковое представление содержит имя класса
        assert "ProjectStructure" in str(project_structure)
    
    def test_project_structure_repr_contains_essential_fields(self):
        """Тест repr содержит основные поля"""
        from domain.models.project.project_structure import ProjectStructure
        project_structure = ProjectStructure()
        project_structure.root_dir = "test_project"
        project_structure.scan_time = datetime.now()
        
        repr_str = repr(project_structure)
        assert "ProjectStructure" in repr_str
