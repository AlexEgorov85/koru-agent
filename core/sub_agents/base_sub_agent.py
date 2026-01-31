"""
Базовый класс для субагентов.
"""

import uuid
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, List
from datetime import datetime

from core.session_context.session_context import SessionContext
from core.session_context.model import ContextItem, ContextItemType, ContextItemMetadata


logger = logging.getLogger(__name__)


class BaseSubAgent(ABC):
    """
    Базовый класс для всех субагентов.
    
    ПРИНЦИПЫ:
    1. Единый интерфейс для всех субагентов
    2. Возможность интеграции с SessionContext
    3. Стандартизированная обработка ошибок и статусов
    4. Возможность мониторинга и управления
    """
    
    def __init__(self, name: str, description: str = "", agent_id: Optional[str] = None):
        """
        Инициализация субагента.
        
        ПАРАМЕТРЫ:
        - name: Название субагента
        - description: Описание субагента
        - agent_id: Уникальный идентификатор субагента (генерируется автоматически, если не указан)
        """
        self.agent_id = agent_id or str(uuid.uuid4())
        self.name = name
        self.description = description
        self.created_at = datetime.now()
        self.status = "initialized"
        self.start_time = None
        self.end_time = None
        self.progress = 0.0
        self.session_context = None
        self.task_queue = []
        self.results = []
        self.errors = []
        
        logger.info(f"SubAgent '{name}' initialized with ID: {self.agent_id}")
    
    def set_session_context(self, session_context: SessionContext):
        """
        Установка контекста сессии для субагента.
        
        ПАРАМЕТРЫ:
        - session_context: Экземпляр SessionContext
        """
        self.session_context = session_context
        logger.debug(f"Session context set for subagent '{self.name}'")
    
    def add_task(self, task: Dict[str, Any]):
        """
        Добавление задачи в очередь.
        
        ПАРАМЕТРЫ:
        - task: Словарь с описанием задачи
        """
        self.task_queue.append(task)
        logger.debug(f"Task added to queue for subagent '{self.name}', queue size: {len(self.task_queue)}")
    
    def get_status(self) -> Dict[str, Any]:
        """
        Получение статуса субагента.
        
        ВОЗВРАЩАЕТ:
        - Словарь с информацией о статусе субагента
        """
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "description": self.description,
            "status": self.status,
            "progress": self.progress,
            "created_at": self.created_at.isoformat(),
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "tasks_remaining": len(self.task_queue),
            "results_count": len(self.results),
            "errors_count": len(self.errors)
        }
    
    def initialize(self) -> bool:
        """
        Инициализация субагента перед запуском.
        
        ВОЗВРАЩАЕТ:
        - True если инициализация успешна, иначе False
        """
        try:
            self.status = "initialized"
            logger.info(f"SubAgent '{self.name}' ({self.agent_id}) initialized")
            return True
        except Exception as e:
            self.status = "error"
            self.errors.append({
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
                "phase": "initialization"
            })
            logger.error(f"Error initializing subagent '{self.name}': {str(e)}")
            return False
    
    async def run(self, task_description: str, context: SessionContext) -> Dict[str, Any]:
        """
        Основной метод выполнения задачи субагентом.
        
        ПАРАМЕТРЫ:
        - task_description: Описание задачи для выполнения
        - context: Контекст сессии
        
        ВОЗВРАЩАЕТ:
        - Словарь с результатами выполнения задачи
        """
        # Устанавливаем контекст
        self.set_session_context(context)
        
        # Начинаем выполнение
        self.start_time = datetime.now()
        self.status = "running"
        
        # Записываем начало работы субагента в контекст
        if self.session_context:
            self._record_start_in_context(task_description)
        
        try:
            # Выполняем задачу
            result = await self._execute_task(task_description)
            
            # Обновляем статус
            self.status = "completed"
            self.progress = 1.0
            self.end_time = datetime.now()
            
            # Сохраняем результат
            self.results.append(result)
            
            # Записываем результат в контекст
            if self.session_context:
                self._record_result_in_context(result)
            
            execution_time = (self.end_time - self.start_time).total_seconds()
            
            logger.info(f"SubAgent '{self.name}' completed task successfully in {execution_time}s")
            
            return {
                "success": True,
                "agent_id": self.agent_id,
                "task": task_description,
                "result": result,
                "execution_time": execution_time,
                "status": self.status
            }
        except Exception as e:
            # Обрабатываем ошибку
            self.status = "failed"
            self.end_time = datetime.now()
            
            error_info = {
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
                "phase": "execution"
            }
            self.errors.append(error_info)
            
            # Записываем ошибку в контекст
            if self.session_context:
                self._record_error_in_context(error_info)
            
            execution_time = (self.end_time - self.start_time).total_seconds()
            
            logger.error(f"SubAgent '{self.name}' failed to complete task: {str(e)}")
            
            return {
                "success": False,
                "agent_id": self.agent_id,
                "task": task_description,
                "error": str(e),
                "execution_time": execution_time,
                "status": self.status
            }
    
    @abstractmethod
    async def _execute_task(self, task_description: str) -> Any:
        """
        Абстрактный метод для выполнения конкретной задачи.
        Должен быть реализован в каждом конкретном субагенте.
        
        ПАРАМЕТРЫ:
        - task_description: Описание задачи для выполнения
        
        ВОЗВРАЩАЕТ:
        - Результат выполнения задачи
        """
        pass
    
    def _record_start_in_context(self, task_description: str):
        """
        Записывает информацию о начале работы субагента в контекст.
        
        ПАРАМЕТРЫ:
        - task_description: Описание задачи
        """
        if not self.session_context:
            return
            
        metadata = ContextItemMetadata(
            source=f"subagent.{self.name}",
            confidence=0.9,
            additional_data={
                "agent_id": self.agent_id,
                "task_description": task_description,
                "start_time": self.start_time.isoformat()
            }
        )
        
        content = {
            "event": "subagent_started",
            "agent_name": self.name,
            "agent_id": self.agent_id,
            "task": task_description,
            "timestamp": self.start_time.isoformat()
        }
        
        self.session_context.add_context_item(
            item_type=ContextItemType.THOUGHT,
            content=content,
            metadata=metadata
        )
        
        logger.debug(f"Started event recorded for subagent '{self.name}' in context")
    
    def _record_result_in_context(self, result: Any):
        """
        Записывает результат работы субагента в контекст.
        
        ПАРАМЕТРЫ:
        - result: Результат выполнения задачи
        """
        if not self.session_context:
            return
            
        metadata = ContextItemMetadata(
            source=f"subagent.{self.name}",
            confidence=0.85,
            additional_data={
                "agent_id": self.agent_id,
                "result_type": type(result).__name__,
                "completion_time": self.end_time.isoformat()
            }
        )
        
        content = {
            "event": "subagent_completed",
            "agent_name": self.name,
            "agent_id": self.agent_id,
            "result": result,
            "timestamp": self.end_time.isoformat(),
            "execution_time": (self.end_time - self.start_time).total_seconds()
        }
        
        self.session_context.add_context_item(
            item_type=ContextItemType.SKILL_RESULT,
            content=content,
            metadata=metadata
        )
        
        logger.debug(f"Result recorded for subagent '{self.name}' in context")
    
    def _record_error_in_context(self, error_info: Dict[str, Any]):
        """
        Записывает информацию об ошибке субагента в контекст.
        
        ПАРАМЕТРЫ:
        - error_info: Информация об ошибке
        """
        if not self.session_context:
            return
            
        metadata = ContextItemMetadata(
            source=f"subagent.{self.name}",
            confidence=0.1,
            additional_data={
                "agent_id": self.agent_id,
                "error_phase": error_info.get("phase", "unknown")
            }
        )
        
        content = {
            "event": "subagent_error",
            "agent_name": self.name,
            "agent_id": self.agent_id,
            "error": error_info["error"],
            "timestamp": error_info["timestamp"],
            "phase": error_info["phase"]
        }
        
        self.session_context.add_context_item(
            item_type=ContextItemType.ERROR_LOG,
            content=content,
            metadata=metadata
        )
        
        logger.debug(f"Error recorded for subagent '{self.name}' in context")
    
    def terminate(self):
        """
        Завершение работы субагента.
        """
        self.status = "terminated"
        self.end_time = datetime.now()
        
        logger.info(f"SubAgent '{self.name}' terminated")