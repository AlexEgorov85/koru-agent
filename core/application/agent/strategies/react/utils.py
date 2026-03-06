"""
Утилиты для ReAct стратегии в новой архитектуре

АРХИТЕКТУРА:
- Типизированные объекты вместо dict
- Dataclass для структур данных
"""
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from core.models.data.capability import Capability


@dataclass
class ContextAnalysis:
    """
    Типизированный результат анализа контекста сессии.
    
    ATTRIBUTES:
    - goal: Цель сессии
    - last_steps: Последние шаги выполнения
    - progress: Текущий прогресс
    - current_step: Текущий номер шага
    - execution_time_seconds: Время выполнения в секундах
    - last_activity: Время последней активности
    - no_progress_steps: Количество шагов без прогресса
    - consecutive_errors: Количество последовательных ошибок
    - summary: Сводка из SessionContext
    """
    goal: str
    last_steps: List[Any] = field(default_factory=list)
    progress: Dict[str, Any] = field(default_factory=dict)
    current_step: int = 0
    execution_time_seconds: float = 0.0
    last_activity: Optional[Any] = None
    no_progress_steps: int = 0
    consecutive_errors: int = 0
    summary: Dict[str, Any] = field(default_factory=dict)


def analyze_context(session_context: 'SessionContext') -> ContextAnalysis:
    """
    Анализирует контекст сессии для ReAct стратегии.

    ARGS:
    - session_context: контекст сессии для анализа

    RETURNS:
    - ContextAnalysis: типизированный результат анализа
    """
    logger = logging.getLogger(__name__)

    try:
        # Получаем историю последних шагов
        last_steps = session_context.get_last_steps(limit=5) if hasattr(session_context, 'get_last_steps') else []

        # Получаем цель сессии
        goal = session_context.goal if hasattr(session_context, 'goal') else "Неизвестная цель"

        # Получаем текущий прогресс
        progress = session_context.get_progress() if hasattr(session_context, 'get_progress') else {}

        # Собираем информацию о контексте и возвращаем объект
        return ContextAnalysis(
            goal=str(goal) if goal is not None else "Неизвестная цель",
            last_steps=last_steps,
            progress=progress,
            current_step=getattr(session_context, 'current_step', 0),
            execution_time_seconds=float(getattr(session_context, 'execution_time', 0)),
            last_activity=getattr(session_context, 'last_activity', None),
            no_progress_steps=getattr(session_context, 'no_progress_steps', 0),
            consecutive_errors=getattr(session_context, 'consecutive_errors', 0),
            summary=session_context.get_summary() if hasattr(session_context, 'get_summary') else {}
        )

    except Exception as e:
        logger.error(f"Ошибка при анализе контекста: {str(e)}", exc_info=True)
        # Возвращаем минимальный анализ в случае ошибки
        return ContextAnalysis(
            goal="Неизвестная цель",
            last_steps=[],
            progress={},
            current_step=0,
            execution_time_seconds=0.0,
            summary={}
        )
