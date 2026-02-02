"""Тесты для инструмента чтения файлов"""
import pytest
from infrastructure.tools.filesystem.file_reader import FileReaderTool


class TestFileReader:
    """Тесты для инструмента чтения файлов"""
    
    def test_file_reader_creation(self):
        """Тест создания инструмента чтения файлов"""
        reader = FileReaderTool()
        
        # Проверяем, что объект создался успешно
        assert reader is not None
        assert hasattr(reader, 'execute')
        assert reader.name == "file_reader"
    
    def test_file_reader_execute_method_exists(self):
        """Тест что у инструмента чтения файлов есть метод execute"""
        reader = FileReaderTool()
        
        assert hasattr(reader, 'execute')
        assert callable(getattr(reader, 'execute'))
    
    def test_file_reader_str_representation(self):
        """Тест строкового представления инструмента чтения файлов"""
        reader = FileReaderTool()
        
        # Проверяем, что строковое представление содержит имя класса
        assert "FileReaderTool" in str(reader)
    
    def test_file_reader_repr_contains_class_name(self):
        """Тест repr содержит название класса"""
        reader = FileReaderTool()
        
        repr_str = repr(reader)
        assert "FileReaderTool" in repr_str
