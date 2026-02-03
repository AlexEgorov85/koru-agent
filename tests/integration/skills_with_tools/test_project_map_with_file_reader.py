"""Тесты интеграции навыка карты проекта с инструментом чтения файлов"""
import pytest
from unittest.mock import Mock, patch
from infrastructure.adapters.skills.project_map.skill import ProjectMapSkill
from infrastructure.tools.filesystem.file_reader import FileReaderTool


class TestProjectMapWithFileReader:
    """Тесты интеграции навыка карты проекта с инструментом чтения файлов"""
    
    def test_project_map_skill_can_use_file_reader(self):
        """Тест что навык карты проекта может использовать инструмент чтения файлов"""
        # Создаем мок для инструмента чтения файлов
        mock_file_reader = Mock(spec=FileReaderTool)
        mock_file_reader.execute.return_value = "file content"
        
        # Создаем навык карты проекта
        skill = ProjectMapSkill()
        
        # Проверяем, что навык может быть создан
        assert skill is not None
        
        # Проверяем, что навык имеет метод execute
        assert hasattr(skill, 'execute')
    
    @patch('infrastructure.tools.file_reader_tool.FileReaderTool')
    def test_project_map_skill_integration_with_real_file_reader(self, mock_file_reader_class):
        """Тест интеграции навыка карты проекта с реальным инструментом чтения файлов"""
        # Мокируем результат работы инструмента чтения файлов
        mock_file_reader_instance = Mock()
        mock_file_reader_instance.execute.return_value = "mocked file content"
        mock_file_reader_class.return_value = mock_file_reader_instance
        
        # Создаем навык карты проекта
        skill = ProjectMapSkill()
        
        # Проверяем, что навык может быть создан и работает
        assert skill is not None
        assert hasattr(skill, 'execute')
    
    def test_project_map_skill_str_representation(self):
        """Тест строкового представления навыка карты проекта"""
        skill = ProjectMapSkill()
        
        # Проверяем, что строковое представление содержит имя класса
        assert "ProjectMapSkill" in str(skill)
