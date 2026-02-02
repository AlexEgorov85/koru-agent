"""
ComposableAgent - главный класс агента с минимальной ответственностью.
Теперь он отвечает только за координацию между различными компонентами.
Соответствует принципу единственной ответственности (SRP) из SOLID.
"""
from typing import Any, Dict, List, Optional
from abc import ABC, abstractmethod
from application.orchestration.executors.action_executor import AtomicActionExecutor


class IComposableAgent(ABC):
    """
    Интерфейс для компонуемого агента.
    """
    
    @abstractmethod
    async def execute_task(self, task: Dict[str, Any]) -> Any:
        """
        Выполнить задачу
        
        Args:
            task: Словарь с описанием задачи
            
        Returns:
            Результат выполнения задачи
        """
        pass


class ComposableAgent(IComposableAgent):
    """
    Реализация компонуемого агента с минимальной ответственностью.
    Основная функция - координировать выполнение задач через другие компоненты.
    """
    
    def __init__(self, atomic_action_executor: AtomicActionExecutor):
        """
        Инициализация агента с внедрением зависимостей
        
        Args:
            atomic_action_executor: Исполнитель атомарных действий
        """
        self.atomic_action_executor = atomic_action_executor
        # В дальнейшем могут быть добавлены другие зависимости через DI
    
    async def execute_task(self, task: Dict[str, Any]) -> Any:
        """
        Выполнить задачу
        
        Args:
            task: Словарь с описанием задачи
            
        Returns:
            Результат выполнения задачи
        """
        # Основная логика выполнения задачи через компоненты
        task_type = task.get("type")
        
        if task_type == "atomic_action":
            return await self._execute_atomic_action(task.get("action"))
        elif task_type == "composite_action":
            return await self._execute_composite_action(task.get("actions"))
        else:
            raise ValueError(f"Unknown task type: {task_type}")
    
    async def _execute_atomic_action(self, action: Dict[str, Any]) -> Any:
        """Выполнить атомарное действие"""
        if not action:
            raise ValueError("Action is required for atomic_action task")
        
        return await self.atomic_action_executor.execute_action(action)
    
    async def _execute_composite_action(self, actions: List[Dict[str, Any]]) -> List[Any]:
        """Выполнить составное действие из нескольких атомарных действий"""
        if not actions:
            raise ValueError("Actions list is required for composite_action task")
        
        results = []
        for action in actions:
            result = await self._execute_atomic_action(action)
            results.append(result)
        
        return results