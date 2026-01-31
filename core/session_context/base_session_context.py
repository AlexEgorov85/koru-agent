

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from core.session_context.model import ContextItem, ContextItemMetadata, ContextItemType


class BaseSessionContext(ABC):
    """
    Базовый класс контекст сессии агента.
    """
    
    @abstractmethod
    def set_goal(self, goal: str) -> None:
        """
        Установка цели сессии.
        """
        pass

    @abstractmethod
    def get_goal(self) -> str:
        """
        Получение цели сессии.
        """
        pass

    @abstractmethod
    def add_context_item(
        self,
        item_type: ContextItemType,
        content: Any,
        metadata: Optional[ContextItemMetadata] = None
    ) -> str:
        """
        Добавление элемента в контекст.
        """
        pass
    
    @abstractmethod
    def get_context_item(self, item_id: str) -> Optional[ContextItem]:
        """
        Получение элемента контекста по ID.
        """
        pass
    
    @abstractmethod
    def register_step(
        self,
        step_number: int,
        capability_name: str,
        skill_name: str,
        action_item_id: str,
        observation_item_ids: List[str],
        summary: Optional[str] = None
    ) -> None:
        """
        Регистрация шага агента.
        """
        pass
    
    @abstractmethod
    def set_current_plan(self, plan_item_id: str) -> None:
        """
        Установка текущего плана.
        """
        pass
    
    @abstractmethod
    def get_current_plan(self) -> Optional[ContextItem]:
        """
        Получение текущего плана.
        """
        pass
    
    @abstractmethod
    def is_expired(self, ttl_minutes: int = 60) -> bool:
        """
        Проверка истечения срока жизни сессии.
        """
        pass
    
    @abstractmethod
    def get_summary(self) -> Dict[str, Any]:
        """
        Получение сводной информации о сессии.
        """
        pass

    @abstractmethod
    def get_current_plan_step(self):
        """Получение текущего шага плана."""
        pass

    @abstractmethod
    def record_action(self, action_data, step_number=None, metadata=None):
        """Запись действия агента в контекст"""
        pass
        
    @abstractmethod
    def record_observation(self, observation_data, source=None, step_number=None, metadata=None):
        """Запись результата выполнения в контекст"""
        pass
        
    @abstractmethod
    def record_plan(self, plan_data, plan_type="initial", metadata=None):
        """Запись плана и его обновлений в контекст"""
        pass
        
    @abstractmethod
    def record_decision(self, decision_data, reasoning=None, metadata=None):
        """Запись решения стратегии в контекст"""
        pass
        
    @abstractmethod
    def record_error(self, error_data, error_type=None, step_number=None, metadata=None):
        """Запись ошибки выполнения в контекст"""
        pass
        
    @abstractmethod
    def record_metric(self, name, value, unit=None, metadata=None):
        """Запись метрики выполнения в контекст"""
        pass
        
    @abstractmethod
    def record_system_event(self, event_type, description=None, metadata=None):
        """Запись системного события в контекст"""
        pass
