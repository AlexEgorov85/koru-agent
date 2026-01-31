"""
Тесты для класса DataContext.
"""
import pytest
from datetime import datetime
from core.session_context.data_context import DataContext
from core.session_context.model import ContextItem, ContextItemMetadata, ContextItemType


class TestDataContext:
    """Тесты для DataContext."""
    
    def test_initialization(self):
        """Тест инициализации DataContext."""
        data_context = DataContext()
        
        assert data_context.items == {}
        assert isinstance(data_context.items, dict)
    
    def test_add_item(self):
        """Тест метода add_item."""
        data_context = DataContext()
        
        item = ContextItem(
            item_id="test_id",
            session_id="session_123",
            item_type=ContextItemType.ACTION,
            content={"test": "content"},
            metadata=ContextItemMetadata(source="test"),
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        result_id = data_context.add_item(item)
        
        assert result_id == "test_id"
        assert "test_id" in data_context.items
        assert data_context.items["test_id"] == item
    
    def test_add_item_generates_id_if_missing(self):
        """Тест метода add_item с генерацией ID."""
        data_context = DataContext()
        
        # Создаем элемент без ID, чтобы он был сгенерирован
        item = ContextItem(
            item_id="",  # Пустой ID для тестирования генерации
            session_id="session_123",
            item_type=ContextItemType.ACTION,
            content={"test": "content"},
            metadata=ContextItemMetadata(source="test"),
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        result_id = data_context.add_item(item)
        
        assert result_id != ""
        assert result_id in data_context.items
    
    def test_get_item_found(self):
        """Тест метода get_item - элемент найден."""
        data_context = DataContext()
        
        item = ContextItem(
            item_id="test_id",
            session_id="session_123",
            item_type=ContextItemType.ACTION,
            content={"test": "content"},
            metadata=ContextItemMetadata(source="test"),
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        data_context.add_item(item)
        
        retrieved_item = data_context.get_item("test_id")
        
        assert retrieved_item == item
    
    def test_get_item_not_found(self):
        """Тест метода get_item - элемент не найден."""
        data_context = DataContext()
        
        retrieved_item = data_context.get_item("nonexistent_id")
        
        assert retrieved_item is None
    
    def test_count_items(self):
        """Тест метода count."""
        data_context = DataContext()
        
        # Добавляем несколько элементов
        item1 = ContextItem(
            item_id="id1",
            session_id="session_123",
            item_type=ContextItemType.ACTION,
            content={"test": "content1"},
            metadata=ContextItemMetadata(source="test"),
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        item2 = ContextItem(
            item_id="id2",
            session_id="session_123",
            item_type=ContextItemType.OBSERVATION,
            content={"test": "content2"},
            metadata=ContextItemMetadata(source="test"),
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        data_context.add_item(item1)
        data_context.add_item(item2)
        
        count = data_context.count()
        
        assert count == 2
    
    def test_count_empty_context(self):
        """Тест метода count для пустого контекста."""
        data_context = DataContext()
        
        count = data_context.count()
        
        assert count == 0
    
    def test_update_existing_item(self):
        """Тест обновления существующего элемента."""
        data_context = DataContext()
        
        original_item = ContextItem(
            item_id="test_id",
            session_id="session_123",
            item_type=ContextItemType.ACTION,
            content={"test": "original"},
            metadata=ContextItemMetadata(source="test"),
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        data_context.add_item(original_item)
        
        # Создаем обновленный элемент с тем же ID
        updated_item = ContextItem(
            item_id="test_id",
            session_id="session_123",
            item_type=ContextItemType.ACTION,
            content={"test": "updated"},
            metadata=ContextItemMetadata(source="test"),
            created_at=original_item.created_at,  # Сохраняем оригинальное время создания
            updated_at=datetime.now()
        )
        
        data_context.add_item(updated_item)
        
        retrieved_item = data_context.get_item("test_id")
        
        assert retrieved_item.content == {"test": "updated"}
        assert retrieved_item.created_at == original_item.created_at  # Не изменяется
        assert retrieved_item.updated_at != original_item.updated_at  # Обновляется