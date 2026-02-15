"""
Утилиты для ReAct стратегии в новой архитектуре
"""
import logging
from typing import Any, Dict, List
from models.capability import Capability


def analyze_context(session_context: 'SessionContext') -> Dict[str, Any]:
    """
    Анализирует контекст сессии для ReAct стратегии.
    
    ARGS:
    - session_context: контекст сессии для анализа
    
    RETURNS:
    - Словарь с результатами анализа
    """
    logger = logging.getLogger(__name__)
    
    try:
        # Получаем историю последних шагов
        last_steps = session_context.get_last_steps(limit=5) if hasattr(session_context, 'get_last_steps') else []
        
        # Получаем цель сессии
        goal = session_context.goal if hasattr(session_context, 'goal') else "Неизвестная цель"
        
        # Получаем текущий прогресс
        progress = session_context.get_progress() if hasattr(session_context, 'get_progress') else {}
        
        # Собираем информацию о контексте
        context_analysis = {
            "goal": goal,
            "last_steps": last_steps,
            "progress": progress,
            "current_step": getattr(session_context, 'current_step', 0),
            "execution_time_seconds": getattr(session_context, 'execution_time', 0),
            "last_activity": getattr(session_context, 'last_activity', None),
            "no_progress_steps": getattr(session_context, 'no_progress_steps', 0),  # Добавляем как атрибут
            "consecutive_errors": getattr(session_context, 'consecutive_errors', 0),  # Добавляем как атрибут
            "summary": session_context.get_summary() if hasattr(session_context, 'get_summary') else {}
        }
        
        logger.debug(f"Контекст проанализирован. Цель: {goal[:50]}...")
        return context_analysis
        
    except Exception as e:
        logger.error(f"Ошибка при анализе контекста: {str(e)}", exc_info=True)
        # Возвращаем минимальный анализ в случае ошибки
        return {
            "goal": "Неизвестная цель",
            "last_steps": [],
            "progress": {},
            "current_step": 0,
            "execution_time_seconds": 0,
            "summary": {}
        }