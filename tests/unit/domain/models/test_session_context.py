"""Тесты для модели SessionContext"""
import pytest
from domain.models.session.context_item import ContextItem


class TestSessionContext:
    """Тесты для модели SessionContext"""
    
    def test_create_context_item_with_valid_data(self):
        """Тест создания ContextItem с валидными данными"""
        context_item = ContextItem(
            key="test_key",
            value="test_value",
            metadata={}
        )
        
        assert context_item.key == "test_key"
        assert context_item.value == "test_value"
        assert context_item.metadata == {}
    
    def test_context_item_str_representation(self):
        """Тест строкового представления ContextItem"""
        context_item = ContextItem(
            key="test_key",
            value="test_value",
            metadata={}
        )
        
        # Проверяем, что строковое представление содержит имя класса и ключ
        assert "test_key" in str(context_item)
        assert "ContextItem" in str(context_item)
    
    def test_context_item_repr_contains_essential_fields(self):
        """Тест repr содержит основные поля"""
        context_item = ContextItem(
            key="test_key",
            value="test_value",
            metadata={}
        )
        
        repr_str = repr(context_item)
        assert "test_key" in repr_str
        assert "test_value" in repr_str
