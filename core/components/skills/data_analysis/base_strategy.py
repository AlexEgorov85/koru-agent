"""
Базовый класс стратегии анализа данных.

АРХИТЕКТУРА:
- AbstractStrategy — контракт для всех стратегий
- AnalysisInput — унифицированный вход
- AnalysisResult — унифицированный выход

НОВАЯ СТРАТЕГИЯ = новый файл в strategies/, импорт + регистрация в skill.py
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class AnalysisInput(BaseModel):
    """Унифицированный вход для любой стратегии."""

    data: List[Dict[str, Any]] = Field(description="Данные в row-формате (list[dict])")
    question: str = Field(description="Исходный вопрос пользователя")
    step_id: int = Field(description="Номер шага")
    execution_context: Any = Field(description="Контекст выполнения")
    capabilities: List[Any] = Field(default_factory=list, description="Контекстные возможности")


class AnalysisResult(BaseModel):
    """Унифицированный выход для любой стратегии."""

    answer: str = Field(default="", description="Текстовый ответ")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Уверенность 0.0-1.0")
    operations: List[str] = Field(default_factory=list, description="Выполненные операции")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Метаданные")
    error: Optional[str] = Field(default=None, description="Текст ошибки, если есть")


class AbstractStrategy(ABC):
    """Контракт стратегии анализа данных."""

    def __init__(self, skill: Any) -> None:
        self._skill = skill

    @property
    @abstractmethod
    def name(self) -> str:
        """Уникальное имя стратегии (llm, python, mapreduce)."""
        ...

    @abstractmethod
    def can_handle(self, data: List[Dict], question: str) -> bool:
        """
        Определяет, может ли стратегия обработать этот запрос.

        Заменяет _detect_mode. Новая стратегия сама декларирует,
        какие случаи она покрывает. Не нужно править _detect_mode.
        """
        ...

    @abstractmethod
    async def execute(self, input_data: AnalysisInput) -> AnalysisResult:
        ...

    def _get_executor(self, execution_context: Any) -> Any:
        """Получение executor из контекста или из скилла."""
        executor = None
        if execution_context is not None and hasattr(execution_context, 'executor'):
            executor = execution_context.executor
        if executor is None and execution_context is not None and hasattr(execution_context, 'session_context'):
            sc = execution_context.session_context
            if hasattr(sc, 'executor'):
                executor = sc.executor
        if executor is None:
            executor = self._skill.executor
        if executor is None:
            raise RuntimeError("Executor не найден ни в контексте, ни в навыке")
        return executor
