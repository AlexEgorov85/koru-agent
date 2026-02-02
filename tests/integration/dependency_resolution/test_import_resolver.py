"""Тесты интеграции разрешения зависимостей и импорта"""
import pytest
from unittest.mock import Mock, patch
from infrastructure.services.code_analysis.resolvers.import_resolver import ImportResolver


class TestImportResolverIntegration:
    """Тесты интеграции разрешения зависимостей и импорта"""
    
    def test_import_resolver_creation(self):
        """Тест создания резолвера импорта"""
        resolver = ImportResolver()
        
        # Проверяем, что объект создался успешно
        assert resolver is not None
        assert hasattr(resolver, 'resolve_import')
        assert isinstance(resolver._cache, dict)
    
    def test_import_resolver_resolve_import_method_exists(self):
        """Тест что у резолвера импорта есть метод resolve_import"""
        resolver = ImportResolver()
        
        assert hasattr(resolver, 'resolve_import')
        assert callable(getattr(resolver, 'resolve_import'))
    
    def test_import_resolver_detect_language_method_exists(self):
        """Тест что у резолвера импорта есть метод определения языка"""
        resolver = ImportResolver()
        
        assert hasattr(resolver, '_detect_language')
        assert callable(getattr(resolver, '_detect_language'))
    
    def test_import_resolver_str_representation(self):
        """Тест строкового представления резолвера импорта"""
        resolver = ImportResolver()
        
        # Проверяем, что объект имеет строковое представление
        assert str(resolver) == "<ImportResolver object>"
    
    def test_import_resolver_repr_contains_class_name(self):
        """Тест repr содержит название класса"""
        resolver = ImportResolver()
        
        repr_str = repr(resolver)
        assert "ImportResolver" in repr_str
    
    def test_import_resolver_detect_language_functionality(self):
        """Тест функциональности определения языка"""
        resolver = ImportResolver()
        
        # Тестируем определение различных языков
        assert resolver._detect_language('.py') == 'python'
        assert resolver._detect_language('.js') == 'javascript'
        assert resolver._detect_language('.ts') == 'typescript'
        assert resolver._detect_language('.jsx') == 'javascript'
        assert resolver._detect_language('.tsx') == 'typescript'
        assert resolver._detect_language('.unknown') == 'unknown'
    
    def test_import_resolver_handles_different_import_patterns(self):
        """Тест что резолвер импорта обрабатывает разные паттерны импорта"""
        resolver = ImportResolver()
        
        # Проверяем, что резолвер имеет методы для различных видов импортов
        assert hasattr(resolver, 'resolve_import')
        assert hasattr(resolver, '_resolve_python_import')
        assert hasattr(resolver, '_resolve_js_ts_import')
        assert hasattr(resolver, '_resolve_relative_python_import')
