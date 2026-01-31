"""
Тесты для модели элемента контекста (ContextItem).
"""
import pytest
from datetime import datetime
from core.session_context.model import ContextItem, ContextItemMetadata, ContextItemType


class TestContextItem:
    """Тесты для ContextItem."""
    
    def test_context_item_creation(self):
        """Тест создания ContextItem."""
        metadata = ContextItemMetadata(
            source="test_source",
            step_number=1,
            confidence=0.9,
            tags=["test", "context"]
        )
        
        context_item = ContextItem(
            item_id="test_item_id",
            session_id="test_session_id",
            item_type=ContextItemType.ACTION,
            content={"action": "test_action", "params": {"param": "value"}},
            metadata=metadata,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        assert context_item.item_id == "test_item_id"
        assert context_item.session_id == "test_session_id"
        assert context_item.item_type == ContextItemType.ACTION
        assert context_item.content == {"action": "test_action", "params": {"param": "value"}}
        assert context_item.metadata.source == "test_source"
        assert context_item.metadata.confidence == 0.9
    
    def test_context_item_with_optional_fields(self):
        """Тест создания ContextItem с опциональными полями."""
        metadata = ContextItemMetadata(
            source="test_source",
            step_number=2,
            confidence=0.8,
            tags=["optional", "test"]
        )
        
        context_item = ContextItem(
            item_id="test_item_optional",
            session_id="test_session_optional",
            item_type=ContextItemType.OBSERVATION,
            content={"observation": "test_obs"},
            metadata=metadata,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            parent_id="parent_123"
        )
        
        assert context_item.parent_id == "parent_123"
        assert context_item.content == {"observation": "test_obs"}
        assert context_item.metadata.tags == ["optional", "test"]
    
    def test_context_item_default_values(self):
        """Тест значений по умолчанию для ContextItem."""
        # Создаем метаданные с минимальными полями
        metadata = ContextItemMetadata(
            source="minimal_source"
        )
        
        context_item = ContextItem(
            item_id="minimal_item",
            session_id="minimal_session",
            item_type=ContextItemType.THOUGHT,
            content={"thought": "test_thought"},
            metadata=metadata,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        # Проверяем, что parent_id по умолчанию None
        assert context_item.parent_id is None
    
    def test_context_item_equality(self):
        """Тест равенства ContextItem."""
        metadata = ContextItemMetadata(
            source="equality_test"
        )
        
        item1 = ContextItem(
            item_id="test_id_1",
            session_id="session_1",
            item_type=ContextItemType.ACTION,
            content={"test": "value"},
            metadata=metadata,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        item2 = ContextItem(
            item_id="test_id_1",  # То же ID
            session_id="session_1",
            item_type=ContextItemType.ACTION,
            content={"test": "value"},
            metadata=metadata,
            created_at=item1.created_at,
            updated_at=item1.updated_at
        )
        
        item3 = ContextItem(
            item_id="test_id_2",  # Другое ID
            session_id="session_1",
            item_type=ContextItemType.ACTION,
            content={"test": "value"},
            metadata=metadata,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        assert item1 == item2  # Одинаковые по значению
        assert item1 != item3  # Разные ID
        assert item2 != item3  # Разные ID
    
    def test_context_item_serialization(self):
        """Тест сериализации ContextItem."""
        metadata = ContextItemMetadata(
            source="serialization_test",
            step_number=5,
            confidence=0.75,
            tags=["serialize", "test"]
        )
        
        context_item = ContextItem(
            item_id="serialize_test_id",
            session_id="serialize_session",
            item_type=ContextItemType.EXECUTION_PLAN,
            content={"plan": "test_plan"},
            metadata=metadata,
            created_at=datetime(2023, 1, 1),
            updated_at=datetime(2023, 1, 1),
            parent_id="parent_serialize"
        )
        
        data = context_item.model_dump()
        
        assert data["item_id"] == "serialize_test_id"
        assert data["session_id"] == "serialize_session"
        assert data["item_type"] == "execution_plan"
        assert data["content"] == {"plan": "test_plan"}
        assert data["parent_id"] == "parent_serialize"
        assert data["metadata"]["source"] == "serialization_test"
        assert data["metadata"]["step_number"] == 5
        assert data["metadata"]["confidence"] == 0.75
        assert data["metadata"]["tags"] == ["serialize", "test"]
    
    def test_context_item_from_dict(self):
        """Тест создания ContextItem из словаря."""
        data = {
            "item_id": "from_dict_id",
            "session_id": "from_dict_session",
            "item_type": "observation",
            "content": {"observation": "test"},
            "metadata": {
                "source": "dict_source",
                "step_number": 10,
                "confidence": 0.95,
                "tags": ["dict", "test"]
            },
            "created_at": "2023-01-01T00:00:00",
            "updated_at": "2023-01-01T00:00:00",
            "parent_id": "dict_parent"
        }
        
        context_item = ContextItem.model_validate(data)
        
        assert context_item.item_id == "from_dict_id"
        assert context_item.session_id == "from_dict_session"
        assert context_item.item_type == ContextItemType.OBSERVATION
        assert context_item.content == {"observation": "test"}
        assert context_item.metadata.source == "dict_source"
        assert context_item.metadata.step_number == 10
        assert context_item.metadata.confidence == 0.95
        assert context_item.metadata.tags == ["dict", "test"]
        assert context_item.parent_id == "dict_parent"


class TestContextItemMetadata:
    """Тесты для ContextItemMetadata."""
    
    def test_metadata_creation(self):
        """Тест создания ContextItemMetadata."""
        metadata = ContextItemMetadata(
            source="test_source",
            step_number=1,
            confidence=0.8,
            tags=["tag1", "tag2"]
        )
        
        assert metadata.source == "test_source"
        assert metadata.step_number == 1
        assert metadata.confidence == 0.8
        assert metadata.tags == ["tag1", "tag2"]
    
    def test_metadata_optional_fields(self):
        """Тест создания ContextItemMetadata с опциональными полями."""
        metadata = ContextItemMetadata(
            source="optional_source",
            step_number=5,
            confidence=0.9,
            tags=["optional", "test"],
            priority=1,
            category="test_category"
        )
        
        assert metadata.source == "optional_source"
        assert metadata.priority == 1
        assert metadata.category == "test_category"
    
    def test_metadata_default_values(self):
        """Тест значений по умолчанию для ContextItemMetadata."""
        metadata = ContextItemMetadata(
            source="minimal_source"
        )
        
        assert metadata.source == "minimal_source"
        assert metadata.step_number is None      # значение по умолчанию
        assert metadata.confidence is None       # значение по умолчанию
        assert metadata.tags == []              # значение по умолчанию
        assert metadata.priority == 0           # значение по умолчанию
        assert metadata.category is None        # значение по умолчанию
    
    def test_metadata_serialization(self):
        """Тест сериализации ContextItemMetadata."""
        metadata = ContextItemMetadata(
            source="serialize_source",
            step_number=3,
            confidence=0.7,
            tags=["serialize", "test"],
            priority=2,
            category="serialize_category"
        )
        
        data = metadata.model_dump()
        
        assert data["source"] == "serialize_source"
        assert data["step_number"] == 3
        assert data["confidence"] == 0.7
        assert data["tags"] == ["serialize", "test"]
        assert data["priority"] == 2
        assert data["category"] == "serialize_category"


def test_context_item_type_enum_values():
    """Тест значений ContextItemType enum."""
    assert ContextItemType.ACTION.value == "action"
    assert ContextItemType.OBSERVATION.value == "observation"
    assert ContextItemType.THOUGHT.value == "thought"
    assert ContextItemType.EXECUTION_PLAN.value == "execution_plan"
    assert ContextItemType.PLAN_STEP.value == "plan_step"
    assert ContextItemType.ERROR_LOG.value == "error_log"
    assert ContextItemType.TOOL_RESULT.value == "tool_result"
    
    # Проверяем, что можем получить все значения
    all_types = [item_type.value for item_type in ContextItemType]
    expected_types = [
        "action", "observation", "thought", "execution_plan", 
        "plan_step", "error_log", "tool_result"
    ]
    assert set(all_types) == set(expected_types)