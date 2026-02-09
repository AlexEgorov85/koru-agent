"""
Вспомогательные функции для ReAct стратегии с полным анализом контекста.
ОСОБЕННОСТИ:
- Анализ прогресса и ошибок
- Оценка состояния плана
- Сравнение результатов шагов
- Подготовка данных для рассуждений
"""
import logging
import json
import re
from datetime import datetime
from typing import Dict, Any, Optional
from core.session_context.model import ContextItemType
logger = logging.getLogger(__name__)

def analyze_context(session) -> Dict[str, Any]:
    """
    Анализирует текущий контекст сессии для принятия решений.
    ВОЗВРАЩАЕТ:
    Словарь с метриками для использования в рассуждениях
    """
    steps = session.step_context.steps
    current_time = datetime.now().timestamp()
    
    # Анализ последних шагов
    last_steps = steps[-10:] if len(steps) >= 10 else steps
    consecutive_errors = 0
    
    # Подсчет последовательных ошибок
    for step in reversed(last_steps):
        if step.summary and _is_error_summary(step.summary):
            consecutive_errors += 1
        else:
            break
    
    # Анализ прогресса
    no_progress_steps = 0
    for i in range(1, len(last_steps)):
        if _is_similar_summary(last_steps[i-1].summary, last_steps[i].summary):
            no_progress_steps += 1
    
    # Анализ плана
    has_plan = hasattr(session, 'current_plan_item_id') and session.current_plan_item_id
    plan_status = _get_plan_status(session)
    
    # Расчет времени выполнения
    execution_time = current_time - (session.created_at.timestamp() if hasattr(session, 'created_at') else current_time)
    
    return {
        "total_steps": len(steps),
        "consecutive_errors": consecutive_errors,
        "no_progress_steps": no_progress_steps,
        "has_plan": has_plan,
        "plan_status": plan_status,
        "execution_time_seconds": execution_time,
        "current_goal": session.get_goal(),
        "last_steps": [
            {
                "step_number": step.step_number,
                "capability": step.capability_name,
                "parameters": session.get_context_item(step.action_item_id).content.get("parameters"),
                "summary": step.summary,
                "success": not (step.summary and "error" in step.summary.lower())
            }
            for step in last_steps
        ]
    }

def _is_error_summary(summary: str) -> bool:
    """Определяет, содержит ли summary признаки ошибки."""
    error_keywords = [
        "error", "ошибка", "failed", "не удалось", "exception",
        "исключение", "timeout", "таймаут", "invalid", "некорректный",
        "not found", "не найден", "unavailable", "недоступен"
    ]
    summary_lower = summary.lower()
    return any(keyword in summary_lower for keyword in error_keywords)

def _is_similar_summary(summary1: str, summary2: str, similarity_threshold: float = 0.8) -> bool:
    """Сравнивает два summary на схожесть."""
    def normalize(text):
        return re.sub(r'[^\w\s]', '', text.lower()).strip()
    
    norm1 = normalize(summary1 or "")
    norm2 = normalize(summary2 or "")
    
    if not norm1 or not norm2:
        return False
    
    words1 = set(norm1.split())
    words2 = set(norm2.split())
    
    if not words1 or not words2:
        return False
    
    common_words = words1.intersection(words2)
    similarity = len(common_words) / max(len(words1), len(words2))
    
    return similarity >= similarity_threshold

def _get_plan_status(session) -> str:
    """Определяет статус текущего плана."""
    if not hasattr(session, 'current_plan_item_id') or not session.current_plan_item_id:
        return "none"
    
    try:
        plan_item = session.get_current_plan()
        if not plan_item:
            return "none"
        
        content = plan_item.content
        if isinstance(content, dict):
            if content.get("completed", False):
                return "completed"
            elif content.get("in_progress", False):
                return "in_progress"
            return content.get("status", "active")
        return "unknown"
    except Exception as e:
        logger.warning(f"Ошибка при определении статуса плана: {str(e)}")
        return "unknown"