"""
Контекст сессии агента - простой контейнер данных.
"""
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from domain.abstractions.system.base_session_context import BaseSessionContext
from application.context.session.models import (
    ContextItem, ContextItemType, 
    ContextItemMetadata, AgentStep
)
from application.context.session.data_context import DataContext
from application.context.session.step_context import StepContext


class SessionContext(BaseSessionContext):
    """
    Контекст сессии агента - immutable-ish контейнер данных конкретной сессии.
    
    СТРУКТУРА:
    - session_id: уникальный идентификатор сессии
    - user_id: идентификатор пользователя (опционально)
    - goal: цель сессии
    - created_at: время создания сессии
    - metadata: произвольные метаданные
    - data_context: хранит все сырые данные (private часть, доступна через навыки/инструменты)
    - step_context: хранит шаги агента для LLM (public часть, доступна агенту)
    """
    
    def __init__(
        self, 
        session_id: Optional[str] = None, 
        user_id: Optional[str] = None,
        goal: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Создание контекста сессии.
        
        ПАРАМЕТРЫ:
        - session_id: Уникальный идентификатор сессии (опционально)
        - user_id: Идентификатор пользователя (опционально)
        - goal: Цель сессии (опционально)
        - metadata: Произвольные метаданные (опционально)
        
        ПРИМЕЧАНИЕ:
        Если session_id не указан, генерируется автоматически
        """
        self.session_id = session_id or str(uuid.uuid4())
        self.user_id = user_id
        self.goal = goal
        self.created_at = datetime.now()
        self.metadata = metadata or {}
        
        # Контексты (разделение на public/private части как было подтверждено)
        self.data_context = DataContext()  # private часть - для навыков/инструментов
        self.step_context = StepContext()  # public часть - для агента

    def get_session_data(self, key: str) -> Optional[Any]:
        """Получить данные сессии по ключу"""
        return getattr(self, key, None)

    def set_session_data(self, key: str, value: Any) -> None:
        """Установить данные сессии по ключу"""
        setattr(self, key, value)

    def get_goal(self) -> Optional[str]:
        """Получить цель сессии"""
        return self.goal

    def get_last_steps(self, count: int) -> list:
        """Получить последние шаги (для совместимости с ExecutionGateway)"""
        # Возвращаем последние count шагов из step_context
        if hasattr(self.step_context, 'get_last_steps'):
            return self.step_context.get_last_steps(count)
        else:
            # Если метод не реализован, возвращаем пустой список
            return []

    def initialize(self) -> bool:
        """Инициализировать контекст сессии"""
        return True

    def cleanup(self) -> None:
        """Очистить ресурсы контекста сессии"""
        # Очищаем внутренние контексты
        if hasattr(self, 'data_context') and self.data_context:
            # Очистка data_context, если у него есть метод clear
            if hasattr(self.data_context, 'clear'):
                self.data_context.clear()
        
        if hasattr(self, 'step_context') and self.step_context:
            # Очистка step_context, если у него есть метод clear
            if hasattr(self.step_context, 'clear'):
                self.step_context.clear()

    def with_updates(self, **kwargs) -> 'SessionContext':
        """
        Создать новый экземпляр SessionContext с обновленными полями.
        
        ПАРАМЕТРЫ:
        - **kwargs: Поля для обновления
        
        ВОЗВРАЩАЕТ:
        - Новый экземпляр SessionContext с обновленными полями
        """
        # Создаем новый экземпляр с текущими значениями
        new_context = SessionContext(
            session_id=self.session_id,
            user_id=self.user_id,
            goal=self.goal,
            metadata=self.metadata.copy() if self.metadata else {}
        )
        
        # Обновляем только те поля, которые переданы в kwargs
        for key, value in kwargs.items():
            if hasattr(new_context, key):
                setattr(new_context, key, value)
        
        return new_context

    def get_skill_registry(self):
        """Получить реестр навыков через порт"""
        if hasattr(self, 'system_context') and self.system_context:
            return self.system_context.skill_registry
        return None

    def get_tool_registry(self):
        """Получить реестр инструментов через порт"""
        if hasattr(self, 'system_context') and self.system_context:
            return self.system_context.tool_registry
        return None

    def get_config_manager(self):
        """Получить менеджер конфигурации через порт"""
        if hasattr(self, 'system_context') and self.system_context:
            return self.system_context.config_manager
        return None

    def get_event_bus(self):
        """Получить шину событий через порт"""
        if hasattr(self, 'event_publisher'):
            return self.event_publisher
        return None

    def get_execution_gateway(self):
        """Получить шлюз выполнения через порт"""
        if hasattr(self, 'execution_gateway'):
            return self.execution_gateway
        return None
