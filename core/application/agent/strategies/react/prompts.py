"""
Промпты для ReAct стратегии в новой архитектуре
"""
from typing import Dict, Any, List
from models.capability import Capability


def build_system_prompt_for_reasoning() -> str:
    """
    Создает системный промпт для процесса рассуждения.
    
    RETURNS:
    - Строку системного промпта
    """
    return """
Ты - агент, реализующий ReAct (Reasoning and Acting) подход.
Твоя задача - анализировать текущую ситуацию и принимать решения о следующих действиях.
Ты должен:
1. Оценить текущую ситуацию
2. Оценить прогресс
3. Принять решение о следующем действии
4. Обеспечить безопасность и корректность действий
"""


def build_reasoning_prompt(
    context_analysis: Dict[str, Any],
    available_capabilities: List[Dict[str, Any]]
) -> str:
    """
    Создает промпт для процесса рассуждения.
    
    ARGS:
    - context_analysis: анализ текущего контекста
    - available_capabilities: список доступных capability
    
    RETURNS:
    - Строку промпта для рассуждения
    """
    goal = context_analysis.get("goal", "Неизвестная цель")
    last_steps = context_analysis.get("last_steps", [])
    no_progress_steps = context_analysis.get("no_progress_steps", 0)
    consecutive_errors = context_analysis.get("consecutive_errors", 0)
    
    prompt_parts = [
        f"ЦЕЛЬ: {goal}\n",
        "=== ТЕКУЩИЙ КОНТЕКСТ ===\n",
        f"- Шагов без прогресса: {no_progress_steps}",
        f"- Последовательных ошибок: {consecutive_errors}",
        f"- Последние шаги ({len(last_steps)}):"
    ]
    
    for i, step in enumerate(last_steps[-3:], 1):  # Показываем последние 3 шага
        prompt_parts.append(f"  {i}. {step}")
    
    prompt_parts.extend([
        "\n=== ДОСТУПНЫЕ CAPABILITIES ===\n",
        "Доступные действия:"
    ])
    
    for cap in available_capabilities:
        cap_desc = cap.get('description', 'Без описания')
        cap_params = cap.get('parameters_schema', {})
        prompt_parts.append(f"- {cap['name']}: {cap_desc}")
        if cap_params:
            prompt_parts.append(f"  Параметры: {list(cap_params.keys())}")
    
    prompt_parts.extend([
        "\n=== ИНСТРУКЦИЯ ===",
        "Проанализируй текущую ситуацию и реши:",
        "1. Какова текущая ситуация?",
        "2. Каков прогресс по сравнению с предыдущими шагами?",
        "3. Какое действие следует выполнить следующим?",
        "4. Какова уверенность в этом решении?",
        "5. Требуется ли откат к предыдущему состоянию?",
        "Ответь в формате JSON с полями: analysis, recommended_action, needs_rollback, rollback_steps"
    ])
    
    return "\n".join(prompt_parts)