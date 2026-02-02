from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from domain.models.execution.execution_result import ExecutionResult


class BaseSkill(ABC):
    """
    Базовый абстрактный класс для всех навыков (skills) в системе.
    
    АРХИТЕКТУРА:
    - Расположение: доменный слой (абстракция)
    - Зависимости: только от доменных моделей
    - Ответственность: определение контракта для всех навыков
    - Принципы: соблюдение инверсии зависимостей (D в SOLID)
    
    ПРИМЕР ИСПОЛЬЗОВАНИЯ:
    ```python
    class ProjectMapSkill(BaseSkill):
        async def execute(self, capability, parameters, context) -> ExecutionResult:
            # Реализация навыка
            pass
    ```
    """
    
    @abstractmethod
    async def execute(self, capability: Any, parameters: Dict[str, Any], context: Optional[Any] = None) -> ExecutionResult:
        """
        Асинхронное выполнение навыка с заданными параметрами и контекстом.
        
        Args:
            capability: Возможность или цель, которую нужно достичь
            parameters: Параметры выполнения навыка
            context: Необязательный контекст выполнения
        
        Returns:
            ExecutionResult: Результат выполнения навыка
        """
        pass