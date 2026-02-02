from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional, List, Type


@dataclass
class ToolInput:
    """
    Базовый класс для входных данных инструментов.
    
    АРХИТЕКТУРА:
    - Расположение: доменный слой (абстракция)
    - Зависимости: только от стандартной библиотеки
    - Ответственность: определение контракта для входных данных инструментов
    - Принципы: соблюдение инверсии зависимостей (D в SOLID)
    
    ПРИМЕР ИСПОЛЬЗОВАНИЯ:
    ```python
    @dataclass
    class FileReadInput(ToolInput):
        path: str
        encoding: str = "utf-8"
    ```
    """
    pass


@dataclass
class ToolOutput:
    """
    Базовый класс для выходных данных инструментов.
    
    АРХИТЕКТУРА:
    - Расположение: доменный слой (абстракция)
    - Зависимости: только от стандартной библиотеки
    - Ответственность: определение контракта для выходных данных инструментов
    - Принципы: соблюдение инверсии зависимостей (D в SOLID)
    
    ПРИМЕР ИСПОЛЬЗОВАНИЯ:
    ```python
    @dataclass
    class FileReadOutput(ToolOutput):
        success: bool
        content: str = ""
        error: Optional[str] = None
    ```
    """
    success: bool = True


class BaseTool(ABC):
    """
    Базовый абстрактный класс для всех инструментов в системе.
    
    АРХИТЕКТУРА:
    - Расположение: доменный слой (абстракция)
    - Зависимости: только от доменных моделей
    - Ответственность: определение общего контракта для всех инструментов
    - Принципы: соблюдение инверсии зависимостей (D в SOLID)
    
    ПРИМЕР ИСПОЛЬЗОВАНИЯ:
    ```python
    class CustomTool(BaseTool):
        async def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
            # Реализация инструмента
            pass
    ```
    """
    
    @abstractmethod
    async def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Единый контракт: вход и выход — словари (для сериализации)
        
        Args:
            parameters: Параметры выполнения инструмента
            
        Returns:
            Dict[str, Any]: Результат выполнения инструмента в формате словаря
        """
        pass
    
    # ДОПОЛНИТЕЛЬНО: вспомогательные методы для удобства
    def validate_input(self, params: Dict[str, Any]) -> bool:
        """Валидация входных параметров (опционально)"""
        return True
    
    def transform_output(self, raw_result: Any) -> Dict[str, Any]:
        """Преобразование результата в стандартный формат"""
        if isinstance(raw_result, dict):
            return raw_result
        return {"result": raw_result}


class ToolAdapter:
    """Адаптер для преобразования между кастомными и стандартными типами"""
    
    @staticmethod
    def wrap_tool(tool_class: Type['BaseTool'], 
                  input_class: Optional[Type] = None,
                  output_class: Optional[Type] = None) -> Type['BaseTool']:
        """Оборачивает инструмент в совместимую оболочку"""
        
        class WrappedTool(tool_class):
            async def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
                # 1. Валидация и преобразование входных данных
                if input_class:
                    validated = input_class(**parameters)
                    parameters = validated.__dict__ if hasattr(validated, '__dict__') else parameters
                
                # 2. Выполнение оригинального метода
                result = await super(WrappedTool, self).execute(parameters)
                
                # 3. Преобразование результата в словарь
                if output_class and isinstance(result, output_class):
                    return result.__dict__ if hasattr(result, '__dict__') else vars(result)
                elif isinstance(result, dict):
                    return result
                else:
                    return {"result": result}
        
        return WrappedTool
