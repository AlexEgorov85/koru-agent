"""Планировщик задач для агента."""
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
import asyncio
from dataclasses import dataclass
from enum import Enum


class TaskStatus(Enum):
    """
    TaskStatus - перечисление статусов задачи.
    
    НАЗНАЧЕНИЕ:
    - Определяет возможные состояния задачи в процессе выполнения
    - Позволяет отслеживать прогресс выполнения задач
    - Обеспечивает согласованное представление состояния задачи
    
    ВОЗМОЖНОСТИ:
    - Определяет статус ожидания задачи (PENDING)
    - Определяет статус выполнения задачи (RUNNING)
    - Определяет статус успешного завершения (COMPLETED)
    - Определяет статус ошибки при выполнении (FAILED)
    - Определяет статус отмены задачи (CANCELLED)
    
    ПРИМЕРЫ РАБОТЫ:
    # Проверка статуса задачи
    if task.status == TaskStatus.COMPLETED:
        print("Задача выполнена")
    elif task.status == TaskStatus.FAILED:
        print(f"Задача завершилась с ошибкой: {task.error}")
    """
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Task:
    """
    Task - описание задачи для планировщика.
    
    НАЗНАЧЕНИЕ:
    - Инкапсулирует информацию о задаче
    - Обеспечивает структурированное хранение атрибутов задачи
    - Предоставляет удобный интерфейс для работы с задачами
    
    ВОЗМОЖНОСТИ:
    - Хранит уникальный идентификатор задачи
    - Хранит название и описание задачи
    - Хранит зависимости от других задач
    - Хранит текущий статус выполнения
    - Хранит результат выполнения задачи
    - Хранит информацию об ошибках
    
    ПРИМЕРЫ РАБОТЫ:
    # Создание задачи
    task = Task(
        id="task_001",
        name="Process Data",
        description="Обработка входных данных",
        dependencies=["task_00"],
        status=TaskStatus.PENDING
    )
    
    # Обновление статуса задачи
    task.status = TaskStatus.RUNNING
    
    # Сохранение результата
    task.result = processed_data
    """
    id: str
    name: str
    description: str
    dependencies: List[str]
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[Any] = None
    error: Optional[str] = None


class TaskScheduler(ABC):
    """
    TaskScheduler - интерфейс планировщика задач.
    
    НАЗНАЧЕНИЕ:
    - Определяет общий интерфейс для всех планировщиков задач
    - Обеспечивает возможность реализации различных алгоритмов планирования
    - Позволяет заменять реализации планировщиков без изменения клиентского кода
    
    ВОЗМОЖНОСТИ:
    - Планирование новых задач
    - Получение информации о текущей задаче
    - Отметка задач как выполненных или неудачных
    - Поддержка различных стратегий планирования
    
    ПРИМЕРЫ РАБОТЫ:
    # Реализация собственного планировщика
    class CustomScheduler(TaskScheduler):
        async def schedule_task(self, task: Task) -> str:
            # Логика планирования задачи
            pass
        
        async def get_current_task_id(self) -> Optional[str]:
            # Логика получения текущей задачи
            pass
        
        async def mark_task_completed(self, task_id: str, result: Any = None):
            # Логика завершения задачи
            pass
        
        async def mark_task_failed(self, task_id: str, error: str):
            # Логика обработки ошибки задачи
            pass
    """
    
    @abstractmethod
    async def schedule_task(self, task: Task) -> str:
        """Запланировать задачу."""
        pass
    
    @abstractmethod
    async def get_current_task_id(self) -> Optional[str]:
        """Получить ID текущей задачи."""
        pass
    
    @abstractmethod
    async def mark_task_completed(self, task_id: str, result: Any = None):
        """Отметить задачу как выполненную."""
        pass
    
    @abstractmethod
    async def mark_task_failed(self, task_id: str, error: str):
        """Отметить задачу как неудачную."""
        pass


class SimpleTaskScheduler(TaskScheduler):
    """
    SimpleTaskScheduler - простой планировщик задач.
    
    НАЗНАЧЕНИЕ:
    - Обеспечивает базовую функциональность планирования задач
    - Реализует простую очередь задач
    - Обеспечивает последовательное выполнение задач
    
    ВОЗМОЖНОСТИ:
    - Добавление задач в очередь
    - Отслеживание текущей задачи
    - Обновление статусов задач
    - Обработка результатов и ошибок выполнения
    - Автоматическое переключение к следующей задаче
    
    ПРИМЕРЫ РАБОТЫ:
    # Создание планировщика
    scheduler = SimpleTaskScheduler()
    
    # Создание и планирование задачи
    task = Task(
        id="task_001",
        name="Example Task",
        description="Пример задачи",
        dependencies=[]
    )
    task_id = await scheduler.schedule_task(task)
    
    # Отметка задачи как выполненной
    await scheduler.mark_task_completed(task_id, result="Success")
    
    # Получение текущей задачи
    current_task_id = await scheduler.get_current_task_id()
    """
    
    def __init__(self):
        self._tasks: Dict[str, Task] = {}
        self._current_task_id: Optional[str] = None
        self._task_queue: List[str] = []
    
    async def schedule_task(self, task: Task) -> str:
        """Запланировать задачу."""
        self._tasks[task.id] = task
        self._task_queue.append(task.id)
        
        # Если это первая задача и текущая задача не установлена, делаем эту задачу текущей
        if not self._current_task_id and self._task_queue:
            self._current_task_id = self._task_queue[0]
        
        return task.id
    
    async def get_current_task_id(self) -> Optional[str]:
        """Получить ID текущей задачи."""
        return self._current_task_id
    
    async def mark_task_completed(self, task_id: str, result: Any = None):
        """Отметить задачу как выполненную."""
        if task_id in self._tasks:
            task = self._tasks[task_id]
            task.status = TaskStatus.COMPLETED
            task.result = result
            
            # Удаляем задачу из очереди
            if task_id in self._task_queue:
                self._task_queue.remove(task_id)
            
            # Переходим к следующей задаче
            if self._current_task_id == task_id and self._task_queue:
                self._current_task_id = self._task_queue[0]
            elif self._current_task_id == task_id:
                self._current_task_id = None
    
    async def mark_task_failed(self, task_id: str, error: str):
        """Отметить задачу как неудачную."""
        if task_id in self._tasks:
            task = self._tasks[task_id]
            task.status = TaskStatus.FAILED
            task.error = error
            
            # Удаляем задачу из очереди
            if task_id in self._task_queue:
                self._task_queue.remove(task_id)
            
            # Переходим к следующей задаче
            if self._current_task_id == task_id and self._task_queue:
                self._current_task_id = self._task_queue[0]
            elif self._current_task_id == task_id:
                self._current_task_id = None
