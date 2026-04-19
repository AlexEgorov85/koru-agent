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


# Сценарий: Параметры отсутствуют в БД (несуществующие колонки/таблицы)
REASONING_MISSING_PARAMS = """{"stop_condition": false, "analysis_progress": "Анализ запроса пользователя", "analysis_state": "Требуется генерация SQL", "analysis_deficit": "Пользователь запрашивает данные по несуществующим полям", "analysis_history": "Нет предыдущих шагов", "analysis_errors": "Нет ошибок", "analysis_tool_choice": "check_result.generate_script", "analysis_params": "Параметры: query='количество проверок по типу проверки и региону'", "analysis_fallback": "Если таблица не найдена — сообщить пользователю", "analysis_stop": "Цель не достигнута", "analysis_final": "Попытаться выполнить запрос, обработать ошибку БД", "decision": {"next_action": "check_result.generate_script", "parameters": {"query": "количество проверок по типу проверки и региону"}}}"""


SQL_MISSING_COLUMNS = """{"analysis_understanding": "Пользователь запрашивает группировку по несуществующим колонкам", "analysis_schema": "Таблица oarb.audits не содержит колонок check_type и region", "analysis_strategy": "Попытка выполнения запроса с обработкой ошибки", "analysis_validation": "Запрос может вызвать ошибку БД", "analysis_security": "SELECT-only", "analysis_optimization": "Простой запрос", "generated_sql": "SELECT check_type, region, COUNT(*) FROM oarb.audits GROUP BY check_type, region", "confidence_score": 0.5, "potential_issues": ["Колонки check_type и region отсутствуют в таблице", "Запрос вернёт ошибку БД"], "final_check": "Запрос содержит несуществующие колонки"}"""


REASONING_DB_ERROR = """{"stop_condition": false, "analysis_progress": "Обнаружена ошибка БД", "analysis_state": "Требуется обработка ошибки", "analysis_deficit": "Запрос не выполнен из-за отсутствия колонок", "analysis_history": "Одна попытка выполнения SQL", "analysis_errors": "Ошибка БД: column check_type does not exist", "analysis_tool_choice": "final_answer.generate", "analysis_params": "Параметры: error_message='Колонки не найдены'", "analysis_fallback": "Сообщить пользователю о проблеме", "analysis_stop": "Дальнейшие попытки бессмысленны", "analysis_final": "Сформировать ответ об ошибке", "decision": {"next_action": "final_answer.generate", "parameters": {"error_message": "Колонки check_type и region отсутствуют в таблице audits"}}}"""


FINAL_ANSWER_MISSING_PARAMS = "Запрос не может быть выполнен: в таблице audits отсутствуют колонки 'check_type' и 'region'. Доступные колонки: id, planned_date, actual_date. Пожалуйста, уточните запрос."


# Сценарий: Данные не существуют (пустая БД или период без данных)
REASONING_NO_DATA_EXISTS = """{"stop_condition": false, "analysis_progress": "Проверка наличия данных", "analysis_state": "Данные запрошены но отсутствуют", "analysis_deficit": "В БД нет записей за указанный период", "analysis_history": "SQL выполнен, результат пуст", "analysis_errors": "Нет ошибок, но результат пустой", "analysis_tool_choice": "final_answer.generate", "analysis_params": "Параметры: result=[]", "analysis_fallback": "Сообщить об отсутствии данных", "analysis_stop": "Данных нет, дальнейшие попытки бессмысленны", "analysis_final": "Сформировать ответ об отсутствии данных", "decision": {"next_action": "final_answer.generate", "parameters": {"result": []}}}"""


SQL_NO_DATA_QUERY = """{"analysis_understanding": "Пользователь запрашивает данные за период когда их нет", "analysis_schema": "Таблица oarb.audits существует", "analysis_strategy": "SELECT с фильтром по дате", "analysis_validation": "Запрос корректен", "analysis_security": "SELECT-only", "analysis_optimization": "Простой запрос", "generated_sql": "SELECT * FROM oarb.audits WHERE planned_date >= '2030-01-01'", "confidence_score": 0.95, "potential_issues": ["Может вернуть пустой результат если данных за 2030 год нет"], "final_check": "Запрос корректен, но данных может не быть"}"""


FINAL_ANSWER_NO_DATA = "По вашему запросу данных не найдено. Возможно, указанный период ещё не наступил или данные отсутствуют в системе. Попробуйте изменить параметры запроса."