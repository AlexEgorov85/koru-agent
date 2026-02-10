"""
Все промпты для ReAct стратегии в одном файле.
ОСОБЕННОСТИ:
- Все промпты вынесены из кода
- Четкая параметризация
- Поддержка различных сценариев
- Легко модифицировать и расширять
"""
from typing import Dict, Any, List

# Основные промпты для структурированного рассуждения
REASONING_PROMPT_TEMPLATE = """
ТВОЯ ЗАДАЧА: Проанализируй текущую ситуацию и предоставь структурированную рекомендацию по следующему действию.
КОНТЕКСТ ЗАДАЧИ:
Цель: {goal}
Общее количество шагов: {total_steps}
Время выполнения: {execution_time:.1f} секунд
Текущий план: {has_plan_str} (статус: {plan_status})

АНАЛИЗ ПРОГРЕССА:
- Последовательные ошибки: {consecutive_errors}
- Шаги без прогресса: {no_progress_steps}
- Уровень уверенности: {confidence_level}

ПОСЛЕДНИЕ ШАГИ:
{steps_history}

ДОСТУПНЫЕ ВОЗМОЖНОСТИ СИСТЕМЫ:
{capabilities_list}

ИНСТРУКЦИИ:
1. ВНИМАТЕЛЬНО проанализируй контекст и прогресс
2. ДАЙ подробную оценку текущей ситуации
3. ОЦЕНИ, требуется ли откат на предыдущие шаги из-за ошибок или отсутствия прогресса
4. ПРЕДЛОЖИ конкретное действие с обоснованием
5. УКАЖИ альтернативные подходы для рассмотрения

СТРУКТУРА АНАЛИЗА:
1. Текущая ситуация: кратко опиши, где мы сейчас
2. Прогресс: насколько мы приблизились к цели
3. Уверенность: оцени от 0.0 до 1.0
4. Ошибки: есть ли последовательные ошибки
5. План: есть ли план, каков его статус
6. Прогресс шагов: есть ли шаги без прогресса. 
7. Проверь реузльтат на последнем шаге, на сколько он корректен. Какие выводы можно из этого сделать?
8. Проверь реузльтат на последнем шаге параметры вызова навыка, на сколько значения соотвествуют description параметров.

ФОРМАТ ВЫВОДА:
Строго следуй JSON Schema, предоставленной в параметрах вызова. Не добавляй дополнительных полей или текста вне JSON.

КРИТЕРИИ КАЧЕСТВЕННОГО ОТВЕТА:
- Конкретные оценки прогресса
- Четкие критерии для отката
- Практичные рекомендации по действиям
- Реалистичные альтернативные подходы
- Логичные обоснования решений
- Нет повторений решений с ошибками или не ревалентным результатом
"""

SYSTEM_REASONING_PROMPT = "Ты — эксперт по анализу и принятию решений. Твоя задача — проанализировать контекст и предложить оптимальное действие в строгом JSON формате."

# Промпты для отката
ROLLBACK_DECISION_PROMPT = """
Анализ ситуации для отката:
- Количество шагов без прогресса: {no_progress_steps}
- Количество последовательных ошибок: {consecutive_errors}
- Текущее состояние системы: {current_state}

РЕКОМЕНДАЦИИ:
1. Определите, какие шаги нужно откатить (максимум 3)
2. Укажите причину отката
3. Предложите следующее действие после отката
"""

# Промпты для работы с планами
CREATE_PLAN_PROMPT = """
Создание нового плана для цели:
Цель: {goal}
Контекст: {context}
Максимальное количество шагов: {max_steps}

ИНСТРУКЦИИ:
1. СОЗДАЙ детальный план с конкретными шагами
2. УЧИТЫВАЙ доступные возможности системы
3. ДЕЛАЙ шаги выполнимыми и последовательными
4. УКАЖИ реалистичные оценки времени для каждого шага
5. СОХРАНЯЙ фокус на главной цели
"""

UPDATE_PLAN_PROMPT = """
Обновление существующего плана:
Текущий план: {current_plan}
Контекст: {context}
Обновления: {updates}

ИНСТРУКЦИИ:
1. СОХРАНИ существующую структуру плана
2. ИЗМЕНИ только необходимые шаги
3. УЧИТЫВАЙ уже выполненные шаги
4. СОХРАНЯЙ связность и логичность плана
5. ОБНОВИ оценки времени при необходимости
"""

# Промпты для корректировки параметров через LLM
PARAMETER_CORRECTION_PROMPT = """
Контекст: {context}
Цель агента: {goal}
ТРЕБУЕТСЯ ИСПРАВИТЬ ПАРАМЕТРЫ для capability: {capability_name}

НЕВАЛИДНЫЕ ПАРАМЕТРЫ:
{invalid_params_json}

ОШИБКИ ВАЛИДАЦИИ:
{errors_list}

СХЕМА ПАРАМЕТРОВ:
{schema_json}

ИНСТРУКЦИИ:
1. ПРОАНАЛИЗИРУЙ каждую ошибку валидации
2. ИСПРАВЬ соответствующие параметры для соответствия схеме
3. УЧТИ контекст и цель агента при выборе значений
4. ЕСЛИ параметр не может быть точно определен - используй разумное значение по умолчанию
5. НЕ добавляй параметры, которых нет в схеме
6. ВЕРНИ только исправленные параметры в формате JSON, без дополнительного текста
"""

def build_reasoning_prompt(
    context_analysis: Dict[str, Any],
    last_steps: List[Dict[str, Any]],
    available_capabilities: List[Dict[str, str]]
) -> str:
    """
    Формирует промпт для структурированного рассуждения с полным анализом.
    """
    # Извлечение основных параметров
    goal = context_analysis['current_goal']
    total_steps = context_analysis['total_steps']
    consecutive_errors = context_analysis['consecutive_errors']
    no_progress_steps = context_analysis['no_progress_steps']
    has_plan = context_analysis['has_plan']
    plan_status = context_analysis['plan_status']
    execution_time = context_analysis['execution_time_seconds']
    
    # Уровень уверенности
    confidence_level = "высокий" if consecutive_errors == 0 and no_progress_steps == 0 else "низкий"
    has_plan_str = "Да" if has_plan else "Нет"
    
    # Формирование истории последних шагов
    steps_history = []
    for i, step in enumerate(last_steps[-10:], 1):  # последние 10 шагов
        step_number = total_steps - len(last_steps) + i
        summary = step.get('summary', 'Без результата')
        capability = step.get('capability', 'capability не известен')
        parameters = step.get('parameters', 'parameters не известен')
        success = step.get('success', 'success не известен')
        # Ограничиваем длину summary
        if len(summary) > 1000:
            summary = summary[:1000] + "..."
        steps_history.append(f"Шаг {step_number}: вызван {capability} с параметрами {parameters} получен результат {summary}")
    
    steps_history_str = "\n".join(steps_history) if steps_history else "Нет выполненных шагов"
    
    # Динамическое формирование списка возможностей
    capabilities_list = []
    k = 0
    for cap in available_capabilities:  # ограничиваем для краткости
        k += 1
        name = cap.get('name', 'unknown')
        description = cap.get('description', 'Без описания')
        schema = cap.get('parameters_schema', 'Без схемы')
        # Проверяем, является ли schema словарем с ожидаемыми ключами
        if isinstance(schema, dict):
            schema_description = schema.get('description', 'Схема параметров')
            schema_properties = schema.get('properties', {})
            properties_str = ", ".join(list(schema_properties.keys())[:5]) if isinstance(schema_properties, dict) else str(schema_properties)
            capabilities_list.append(f"""{k}. {name}
                - Описание: {description}
                - Параметры: {properties_str}""")
        else:
            capabilities_list.append(f"""{k}. {name}
                - Описание: {description}
                - Параметры: {schema}""")
    
    capabilities_str = "\n".join(capabilities_list) if capabilities_list else "Нет доступных возможностей"
    
    # Формирование итогового промпта
    return REASONING_PROMPT_TEMPLATE.format(
        goal=goal,
        total_steps=total_steps,
        execution_time=execution_time,
        has_plan_str=has_plan_str,
        plan_status=plan_status,
        consecutive_errors=consecutive_errors,
        no_progress_steps=no_progress_steps,
        confidence_level=confidence_level,
        steps_history=steps_history_str,
        capabilities_list=capabilities_str
    )

def build_system_prompt_for_reasoning() -> str:
    """
    Создает системный промпт для структурированных рассуждений.
    """
    return SYSTEM_REASONING_PROMPT