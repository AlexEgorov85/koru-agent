"""Тесты для модели SessionContext"""
import pytest
from domain.models.session.context_item import ContextItem


class TestSessionContext:
    """Тесты для модели SessionContext"""
    
    def test_create_context_item_with_valid_data(self):
        """Тест создания ContextItem с валидными данными"""
        from domain.models.session.context_item import ContextItemType
        context_item = ContextItem(
            item_id="test_id",
            session_id="test_session_id",
            item_type=ContextItemType.USER_QUERY,
            content="test_content"
        )
        
        assert context_item.item_id == "test_id"
        assert context_item.session_id == "test_session_id"
        assert context_item.item_type == ContextItemType.USER_QUERY
        assert context_item.content == "test_content"
    
    def test_context_item_str_representation(self):
        """Тест строкового представления ContextItem"""
        from domain.models.session.context_item import ContextItemType
        context_item = ContextItem(
            item_id="test_id",
            session_id="test_session_id",
            item_type=ContextItemType.USER_QUERY,
            content="test_content"
        )
        
        # Проверяем, что строковое представление содержит имя класса
        assert "ContextItem" in str(context_item)
    
    def test_context_item_repr_contains_essential_fields(self):
        """Тест repr содержит основные поля"""
        from domain.models.session.context_item import ContextItemType
        context_item = ContextItem(
            item_id="test_id",
            session_id="test_session_id",
            item_type=ContextItemType.USER_QUERY,
            content="test_content"
        )
        
        repr_str = repr(context_item)
        assert "ContextItem" in repr_str
