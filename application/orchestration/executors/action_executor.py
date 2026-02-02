"""
Исполнитель атомарных действий - инфраструктурный компонент для выполнения простых операций.
Соответствует принципу единственной ответственности (SRP) из SOLID.
"""
from typing import Any, Dict, Optional
from abc import ABC, abstractmethod


class IAtomicActionExecutor(ABC):
    """
    Интерфейс для исполнителя атомарных действий.
    """
    
    @abstractmethod
    async def execute_action(self, action: Dict[str, Any]) -> Any:
        """
        Выполнить атомарное действие
        
        Args:
            action: Словарь с описанием действия
            
        Returns:
            Результат выполнения действия
        """
        pass


class AtomicActionExecutor(IAtomicActionExecutor):
    """
    Реализация исполнителя атомарных действий.
    """
    
    def __init__(self):
        # Здесь можно инициализировать зависимости
        pass
    
    async def execute_action(self, action: Dict[str, Any]) -> Any:
        """
        Выполнить атомарное действие
        
        Args:
            action: Словарь с описанием действия
            
        Returns:
            Результат выполнения действия
        """
        # Реализация выполнения атомарного действия
        action_type = action.get("type")
        action_params = action.get("params", {})
        
        # В зависимости от типа действия выполняем соответствующую операцию
        if action_type == "file_read":
            return await self._execute_file_read(action_params)
        elif action_type == "file_write":
            return await self._execute_file_write(action_params)
        elif action_type == "code_analyze":
            return await self._execute_code_analyze(action_params)
        else:
            raise ValueError(f"Unknown action type: {action_type}")
    
    async def _execute_file_read(self, params: Dict[str, Any]) -> str:
        """Выполнить действие чтения файла"""
        file_path = params.get("path")
        if not file_path:
            raise ValueError("File path is required for file_read action")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    
    async def _execute_file_write(self, params: Dict[str, Any]) -> bool:
        """Выполнить действие записи файла"""
        file_path = params.get("path")
        content = params.get("content")
        
        if not file_path or content is None:
            raise ValueError("File path and content are required for file_write action")
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return True
    
    async def _execute_code_analyze(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Выполнить анализ кода"""
        code = params.get("code")
        if not code:
            raise ValueError("Code is required for code_analyze action")
        
        # Простой анализ кода (в реальной реализации будет более сложной)
        lines = code.split('\n')
        return {
            "line_count": len(lines),
            "char_count": len(code),
            "has_functions": any(line.strip().startswith('def ') for line in lines),
            "has_classes": any(line.strip().startswith('class ') for line in lines)
        }