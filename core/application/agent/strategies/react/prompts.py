"""
Промпты для ReAct стратегии в новой архитектуре.

Этот модуль предоставляет функции для получения промптов из репозитория через PromptService.
Прямое определение промптов в коде НЕ рекомендуется — используйте registry.yaml.
"""
from typing import Dict, Any, List


def build_system_prompt_for_reasoning() -> str:
    """
    Создает системный промпт для процесса рассуждения.
    
    ПРИМЕЧАНИЕ: В продакшене используйте PromptService для загрузки из репозитория.
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
    
    ВНИМАНИЕ: Это временная реализация для совместимости.
    В продакшене используйте PromptService.get_prompt('behavior.react.think', version).
    
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

    for i, step in enumerate(last_steps[-3:], 1):
        prompt_parts.append(f"  {i}. {step}")

    prompt_parts.extend([
        "\n=== ДОСТУПНЫЕ CAPABILITIES ===\n",
        "Доступные действия (ВЫБИРАЙ ТОЛЬКО ИЗ ЭТОГО СПИСКА):"
    ])

    for cap in available_capabilities:
        cap_desc = cap.get('description', 'Без описания')
        cap_params = cap.get('parameters_schema', {})
        prompt_parts.append(f"- {cap['name']}: {cap_desc}")
        if cap_params:
            prompt_parts.append(f"  Параметры: {list(cap_params.keys())}")

    prompt_parts.extend([
        "\n=== ИНСТРУКЦИЯ ===",
        "Проанализируй ситуацию и верни РЕШЕНИЕ в формате JSON.",
        "",
        "ТРЕБУЕМЫЙ ФОРМАТ JSON (строго следуй структуре):",
        """{
  "analysis": {
    "current_situation": "Опиши текущую ситуацию своими словами",
    "progress_assessment": "Оцени прогресс: что сделано, что осталось",
    "confidence": 0.85,
    "errors_detected": false
  },
  "recommended_action": {
    "action_type": "execute_capability",
    "capability_name": "ТОЧНОЕ ИМЯ capability из списка выше",
    "parameters": {"input": "параметры для capability"},
    "reasoning": "Почему выбрано это действие"
  },
  "needs_rollback": false,
  "rollback_steps": 0
}""",
        "",
        "ВАЖНО:",
        "1. Возвращай ТОЛЬКО JSON без дополнительного текста",
        "2. capability_name ДОЛЖЕН точно совпадать с именем из списка доступных",
        "3. parameters должны соответствовать ожидаемым параметрам capability",
        "4. confidence - число от 0.0 до 1.0",
        "5. needs_rollback - true только если обнаружена критическая ошибка"
    ])

    return "\n".join(prompt_parts)