"""
Тесты для базового класса контекста сессии (BaseSessionContext).
"""
import pytest
from unittest.mock import MagicMock
from core.session_context.base_session_context import BaseSessionContext
from core.session_context.model import ContextItem, ContextItemMetadata, ContextItemType


class ConcreteSessionContext(BaseSessionContext):
    """Конкретная реализация BaseSessionContext для тестов."""
    
    def set_goal(self, goal: str) -> None:
        self.goal = goal

    def get_goal(self) -> str:
        return getattr(self, 'goal', '')

    def add_context_item(
        self,
        item_type: ContextItemType,
        content: any,
        metadata=None
    ) -> str:
        if not hasattr(self, 'items'):
            self.items = {}
        item_id = f"item_{len(self.items)}"
        self.items[item_id] = ContextItem(
            item_id=item_id,
            session_id="test_session",
            item_type=item_type,
            content=content,
            metadata=metadata or ContextItemMetadata(),
            created_at=None,
            updated_at=None
        )
        return item_id

    def get_context_item(self, item_id: str) -> ContextItem:
        return getattr(self, 'items', {}).get(item_id)

    def register_step(
        self,
        step_number: int,
        capability_name: str,
        skill_name: str,
        action_item_id: str,
        observation_item_ids: list,
        summary=None
    ) -> None:
        if not hasattr(self, 'steps'):
            self.steps = {}
        self.steps[step_number] = {
            "capability_name": capability_name,
            "skill_name": skill_name,
            "action_item_id": action_item_id,  # Исправлено
            "observation_item_ids": observation_item_ids,
            "summary": summary
        }

    def set_current_plan(self, plan_item_id: str) -> None:
        self.current_plan_item_id = plan_item_id

    def get_current_plan(self) -> ContextItem:
        if hasattr(self, 'current_plan_item_id') and hasattr(self, 'items'):
            return self.items.get(self.current_plan_item_id)
        return None

    def is_expired(self, ttl_minutes: int = 60) -> bool:
        return False  # Для тестов всегда возвращаем False

    def get_summary(self) -> dict:
        return {
            "session_id": getattr(self, 'session_id', 'test_session'),
            "goal": getattr(self, 'goal', ''),
            "step_count": len(getattr(self, 'steps', {}))
        }

    def get_current_plan_step(self):
        return getattr(self, 'current_plan_step', None)


class TestBaseSessionContext:
    """Тесты для BaseSessionContext."""
    
    def test_initialization(self):
        """Тест инициализации контекста сессии."""
        session_context = ConcreteSessionContext()
        
        # Проверяем, что базовый класс инициализирован без ошибок
        assert session_context is not None
    
    def test_set_and_get_goal(self):
        """Тест установки и получения цели сессии."""
        session_context = ConcreteSessionContext()
        
        session_context.set_goal("Тестовая цель")
        goal = session_context.get_goal()
        
        assert goal == "Тестовая цель"
    
    def test_add_context_item(self):
        """Тест добавления элемента контекста."""
        session_context = ConcreteSessionContext()
        
        item_id = session_context.add_context_item(
            item_type=ContextItemType.ACTION,
            content={"test": "data"}
        )
        
        assert item_id is not None
        assert item_id in session_context.items
        assert session_context.items[item_id].content == {"test": "data"}
        assert session_context.items[item_id].item_type == ContextItemType.ACTION
    
    def test_get_context_item(self):
        """Тест получения элемента контекста."""
        session_context = ConcreteSessionContext()
        
        # Сначала добавляем элемент
        item_id = session_context.add_context_item(
            item_type=ContextItemType.OBSERVATION,
            content={"observation": "test"}
        )
        
        # Затем получаем его
        retrieved_item = session_context.get_context_item(item_id)
        
        assert retrieved_item is not None
        assert retrieved_item.content == {"observation": "test"}
        assert retrieved_item.item_type == ContextItemType.OBSERVATION
    
    def test_get_context_item_not_found(self):
        """Тест получения несуществующего элемента контекста."""
        session_context = ConcreteSessionContext()
        
        retrieved_item = session_context.get_context_item("nonexistent_id")
        
        assert retrieved_item is None
    
    def test_register_step(self):
        """Тест регистрации шага."""
        session_context = ConcreteSessionContext()
        
        session_context.register_step(
            step_number=1,
            capability_name="test_capability",
            skill_name="test_skill",
            action_item_id="action_1",
            observation_item_ids=["obs_1", "obs_2"],
            summary="Test step summary"
        )
        
        step = session_context.steps[1]
        assert step["capability_name"] == "test_capability"
        assert step["skill_name"] == "test_skill"
        assert step["action_item_id"] == "action_1"
        assert step["observation_item_ids"] == ["obs_1", "obs_2"]
        assert step["summary"] == "Test step summary"
    
    def test_set_and_get_current_plan(self):
        """Тест установки и получения текущего плана."""
        session_context = ConcreteSessionContext()
        
        # Добавляем элемент плана
        plan_item_id = session_context.add_context_item(
            item_type=ContextItemType.EXECUTION_PLAN,
            content={"plan": "test plan"}
        )
        
        # Устанавливаем его как текущий план
        session_context.set_current_plan(plan_item_id)
        
        # Получаем текущий план
        current_plan = session_context.get_current_plan()
        
        assert current_plan is not None
        assert current_plan.content == {"plan": "test plan"}
    
    def test_is_expired_default_ttl(self):
        """Тест проверки истечения срока с TTL по умолчанию."""
        session_context = ConcreteSessionContext()
        
        # Для нашей реализации всегда возвращает False
        expired = session_context.is_expired()
        
        assert expired is False
    
    def test_is_expired_custom_ttl(self):
        """Тест проверки истечения срока с кастомным TTL."""
        session_context = ConcreteSessionContext()
        
        # Для нашей реализации всегда возвращает False
        expired = session_context.is_expired(ttl_minutes=30)
        
        assert expired is False
    
    def test_get_summary(self):
        """Тест получения сводки сессии."""
        session_context = ConcreteSessionContext()
        
        session_context.set_goal("Тестовая цель")
        
        # Регистрируем несколько шагов
        session_context.register_step(
            step_number=1,
            capability_name="cap1",
            skill_name="skill1",
            action_item_id="action1",
            observation_item_ids=["obs1"]
        )
        
        session_context.register_step(
            step_number=2,
            capability_name="cap2",
            skill_name="skill2",
            action_item_id="action2",
            observation_item_ids=["obs2"]
        )
        
        summary = session_context.get_summary()
        
        assert summary["session_id"] == "test_session"
        assert summary["goal"] == "Тестовая цель"
        assert summary["step_count"] == 2
    
    def test_get_current_plan_step(self):
        """Тест получения текущего шага плана."""
        session_context = ConcreteSessionContext()
        
        # Устанавливаем текущий шаг плана
        session_context.current_plan_step = {"step_id": "step_1", "description": "Test step"}
        
        current_step = session_context.get_current_plan_step()
        
        assert current_step == {"step_id": "step_1", "description": "Test step"}
    
    def test_get_current_plan_step_none(self):
        """Тест получения текущего шага плана когда он не установлен."""
        session_context = ConcreteSessionContext()
        
        current_step = session_context.get_current_plan_step()
        
        assert current_step is None


def test_base_session_context_abstract_methods():
    """Тест, что BaseSessionContext нельзя инстанцировать без реализации абстрактных методов."""
    
    with pytest.raises(TypeError):
        BaseSessionContext()