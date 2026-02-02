"""Тесты для инструмента списка файлов"""
import pytest
from infrastructure.tools.filesystem.file_lister import FileListerTool


class TestFileLister:
    """Тесты для инструмента списка файлов"""
    
    def test_file_lister_creation(self):
        """Тест создания инструмента списка файлов"""
        lister = FileListerTool()
        
        # Проверяем, что объект создался успешно
        assert lister is not None
        assert hasattr(lister, 'execute')
        assert lister.name == "file_lister"
    
    def test_file_lister_execute_method_exists(self):
        """Тест что у инструмента списка файлов есть метод execute"""
        lister = FileListerTool()
        
        assert hasattr(lister, 'execute')
        assert callable(getattr(lister, 'execute'))
    
    def test_file_lister_str_representation(self):
        """Тест строкового представления инструмента списка файлов"""
        lister = FileListerTool()
        
        # Проверяем, что строковое представление содержит имя класса
        assert "FileListerTool" in str(lister)
    
    def test_file_lister_repr_contains_class_name(self):
        """Тест repr содержит название класса"""
        lister = FileListerTool()
        
        repr_str = repr(lister)
        assert "FileListerTool" in repr_str
