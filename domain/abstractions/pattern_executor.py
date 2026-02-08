from abc import ABC, abstractmethod
from typing import Dict, Any
from domain.models.provider_type import LLMResponse  # ← ИСПОЛЬЗУЕМ СУЩЕСТВУЮЩИЙ!


class IPatternExecutor(ABC):
    """Порт для выполнения рассуждений через LLM. ЕДИНСТВЕННЫЙ способ вызова инфраструктуры из оркестратора."""
    
    @abstractmethod
    async def execute_thinking(
        self,
        pattern_name: str,
        session_id: str,
        context: Dict[str, Any]  # ← ТОЛЬКО ДАННЫЕ, НЕ ИНФРАСТРУКТУРА
    ) -> LLMResponse:  # ← ВОЗВРАЩАЕМ СУЩЕСТВУЮЩИЙ класс!
        """Выполнить рассуждение через LLM и вернуть валидированный ответ."""
        pass