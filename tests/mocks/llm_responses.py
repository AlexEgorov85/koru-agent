"""
Пары вопрос/ответ для MockLLM.

Структура: {ключ_в_промпте: ответ}

Добавляй новые пары из логов в формате:
    mock.register_response(
        "ключевая_фраза_в_промпте",
        "ответ"
    )

Ключевая фраза должна быть уникальной для типа запроса:
- ReasoningResult → решения ReAct
- SQLGenerationOutput → генерация SQL
- final_answer → финальный ответ
"""

DEFAULT_MOCK_RESPONSES = {
    " ReasoningResult": {
        "stop_condition": False,
        "decision": {
            "next_action": "check_result.generate_script",
            "parameters": {"query": "количество проверок в 2025 и 2026 годах"}
        }
    },
    "SQLGenerationOutput": {
        "analysis_understanding": "Query about checks by year",
        "analysis_schema": "Table oarb.audits",
        "analysis_strategy": "SELECT with GROUP BY",
        "analysis_validation": "OK",
        "analysis_security": "SELECT-only",
        "analysis_optimization": "Simple query",
        "generated_sql": "SELECT year, COUNT(*) FROM oarb.audits GROUP BY year",
        "confidence_score": 0.95,
        "potential_issues": [],
        "final_check": "Query correct"
    },
    "final_answer.generate": "В 2025 году было 0 проверок. В 2026 году данных пока нет.",
}


STOP_CONDITION_TRUE = {
    " ReasoningResult": {
        "stop_condition": True,
        "decision": {
            "next_action": "final_answer.generate",
            "parameters": {}
        }
    },
}


REASONING_EMPTY_CONTEXT = """{"stop_condition": false, "analysis_progress": "Нет данных о количестве проверок. Начинаю сбор информации.", "analysis_state": "Шаги не выполнены. Нет истории действий.", "analysis_deficit": "Неизвестно, сколько проверок было проведено в 2025 и 2026 годах. Требуется получить данные из базы данных.", "analysis_history": "Нет предыдущих шагов или повторов.", "analysis_errors": "Нет ошибок или пустых результатов.", "analysis_tool_choice": "check_result.generate_script", "analysis_params": "Параметры: query='количество проверок в 2025 и 2026 годах', schema_context='audits'", "analysis_fallback": "Если генерация SQL не удастся, попробовать vector_search.", "analysis_stop": "Цель не достигнута — данные отсутствуют.", "analysis_final": "Выполнить check_result.generate_script для получения количества проверок.", "decision": {"next_action": "check_result.generate_script", "parameters": {"query": "количество проверок в 2025 и 2026 годах", "schema_context": "audits"}}}"""


SQL_COUNT_CHECKS = """{"analysis_understanding": "Пользователь хочет узнать количество проверок в 2025 и 2026 годах. Используется таблица audits.", "analysis_schema": "Таблица oarb.audits, колонки id, planned_date, actual_date.", "analysis_strategy": "SELECT с группировкой по году.", "analysis_validation": "Условия учтены.", "analysis_security": "SELECT-only.", "analysis_optimization": "Простой запрос.", "generated_sql": "SELECT EXTRACT(YEAR FROM planned_date) AS year, COUNT(*) AS check_count FROM oarb.audits WHERE planned_date >= '2025-01-01' AND planned_date < '2027-01-01' GROUP BY EXTRACT(YEAR FROM planned_date) ORDER BY year;", "confidence_score": 0.98, "potential_issues": ["Может вернуть пустоту если нет данных за эти годы"], "final_check": "Запрос корректен."}"""


REASONING_EMPTY_RESULTS = """{"stop_condition": false, "analysis_progress": "Начало анализа: цель не достигнута, данные не собраны", "analysis_state": "Шаги не выполнены, история пуста", "analysis_deficit": "Неизвестно, сколько проверок прошло в 2025 и 2026 годах", "analysis_history": "Нет выполненных шагов", "analysis_errors": "Ошибок не было", "analysis_tool_choice": "check_result.generate_script", "analysis_params": "Параметры: query='сколько проверок было проведено в 2025 и 2026 годах?'", "analysis_fallback": "Если запрос вернёт пустые результаты — попробовать с более точным фильтром по дате", "analysis_stop": "Цель не достигнута", "analysis_final": "Выполнить SQL-запрос для подсчёта проверок в 2025 и 2026 годах", "decision": {"next_action": "check_result.generate_script", "parameters": {"query": "сколько проверок было проведено в 2025 и 2026 годах?"}}, "confidence_score": 0.92, "assumptions_made": ["в базе данных есть таблица с данными о проверках", "дата проведения проверок хранится в формате годов"], "schema_validation_needed": false, "fallback_on_empty": "попробовать с более точным фильтром по дате", "confidence_triggers_action": "RE_VALIDATE"}"""


FINAL_ANSWER_DEFAULT = "По данным аудиторской системы, проверок в указанный период не зафиксировано. Рекомендуется уточнить период или проверить доступность данных."