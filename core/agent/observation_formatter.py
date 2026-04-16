"""
Утилита для формирования понятного наблюдения из результатов выполнения.

ARCHITECTURE:
- Форматирует result.data в читаемое описание для LLM
- Структурированный вывод с метаданными о типе данных и способе доступа
- Поддержка разных типов результатов (SQL, vector search, и т.д.)
"""
from typing import Any, Dict, Optional


def format_observation(
    result_data: Any,
    capability_name: str,
    parameters: Optional[Dict[str, Any]] = None
) -> str:
    """
    Формирует понятное наблюдение из результата выполнения.

    ARGS:
    - result_data: данные результата от инструмента/skills
    - capability_name: имя capability (например: sql_tool.execute)
    - parameters: параметры запроса (опционально)

    RETURNS:
    - Строка с описанием данных для LLM

    EXAMPLE:
    ```
    # SQL результат:
    format_observation({"rows": [...], "columns": [...], "rowcount": 100}, "sql_tool.execute")
    
    # Результат:
    # === ПОЛУЧЕННЫЕ ДАННЫЕ ===
    # Тип: list[dict]
    # Количество записей: 100
    # Колонки: ['id', 'name', 'price']
    # 
    # 📋 ПЕРВЫЕ 3 ЗАПИСИ:
    # - {'id': 1, 'name': 'Товар А', 'price': 100}
    # - {'id': 2, 'name': 'Товар Б', 'price': 200}
    # - {'id': 3, 'name': 'Товар В', 'price': 300}
    ```
    """
    if result_data is None:
        return "Данные отсутствуют"

    # Форматируем по типу данных
    if isinstance(result_data, dict):
        return _format_dict_observation(result_data, capability_name, parameters)
    elif isinstance(result_data, list):
        return _format_list_observation(result_data, capability_name)
    elif isinstance(result_data, str):
        return _format_string_observation(result_data, capability_name)
    else:
        return _format_generic_observation(result_data, capability_name)


def _format_dict_observation(
    data: dict,
    capability_name: str,
    parameters: Optional[Dict[str, Any]]
) -> str:
    """Форматирует dict результат."""
    
    # Определяем тип по структуре данных
    if "rows" in data and "rowcount" in data:
        return _format_sql_observation(data, capability_name, parameters)
    elif capability_name in ("sql_tool.execute", "sql_tool.execute_query"):
        return _format_sql_observation(data, capability_name, parameters)
    elif "results" in data and "query" in data:
        return _format_vector_search_observation(data, capability_name)
    elif capability_name.startswith("vector_search"):
        return _format_vector_search_observation(data, capability_name)
    else:
        return _format_generic_dict(data, capability_name)


def _format_sql_observation(data: dict, capability_name: str, parameters: Optional[Dict[str, Any]] = None) -> str:
    """Форматирует SQL результат."""
    rows = data.get("rows", [])
    columns = data.get("columns", [])
    rowcount = data.get("rowcount", 0)
    execution_time = data.get("execution_time", 0)
    warning = data.get("warning")

    lines = []
    lines.append("=== ПОЛУЧЕННЫЕ ДАННЫЕ ===")
    lines.append(f"📊 Тип: SQL результат (таблица)")
    lines.append(f"📋 Количество записей: {rowcount}")
    lines.append(f"📑 Колонки: {columns}")
    lines.append(f"⏱ Время выполнения: {execution_time:.3f} сек")
    
    # Предупреждение если есть truncation warning
    if warning:
        lines.append(f"⚠️ ВНИМАНИЕ: {warning}")
    
    # Проверка max_rows
    max_rows_param = None
    if parameters:
        max_rows_param = parameters.get("max_rows")
    elif isinstance(parameters, dict) and "parameters" in parameters:
        max_rows_param = parameters.get("parameters", {}).get("max_rows")
    
    if max_rows_param and rowcount >= max_rows_param:
        lines.append(f"⚠️ ВНИМАНИЕ: Получено {rowcount} записей = лимит {max_rows_param}. Данные могут быть неполными! Увеличьте max_rows для повторного запроса.")
    
    lines.append("")

    if not rows:
        lines.append("💡 Данные отсутствуют (0 записей)")
        return "\n".join(lines)

    lines.append(f"📋 ВСЕ {len(rows)} ЗАПИСЕЙ:")
    for i, row in enumerate(rows):
        lines.append(f"  [{i}] {row}")

    return "\n".join(lines)


def _format_vector_search_observation(data: dict, capability_name: str) -> str:
    """Форматирует vector search результат."""
    results = data.get("results", [])
    query = data.get("query", "")
    total_found = data.get("total_found", len(results))

    lines = []
    lines.append("=== ПОЛУЧЕННЫЕ ДАННЫЕ ===")
    lines.append(f"📊 Тип: Семантический поиск")
    lines.append(f"🔍 Запрос: {query}")
    lines.append(f"📋 Найдено результатов: {total_found}")

    if not results:
        lines.append("💡 Результаты не найдены")
        return "\n".join(lines)

    lines.append("")
    lines.append("💾 КАК ПОЛУЧИТЬ ДОСТУП К ДАННЫМ:")
    lines.append("  results = result['results']      # list[SearchResult]")
    lines.append("  first = results[0]              # SearchResult")
    lines.append("  text = first.text               # текст документа")
    lines.append("  score = first.score            # релевантность (0-1)")
    lines.append("")

    lines.append(f"📋 ВСЕ {len(results)} РЕЗУЛЬТАТОВ:")
    for i, r in enumerate(results):
        if hasattr(r, 'text'):
            score = getattr(r, 'score', 0)
            lines.append(f"  [{i}] (score={score:.2f}) {r.text}")
        else:
            lines.append(f"  [{i}] {r}")

    return "\n".join(lines)


def _format_generic_dict(data: dict, capability_name: str) -> str:
    """Форматирует generic dict."""
    keys = list(data.keys())
    
    lines = []
    lines.append("=== ПОЛУЧЕННЫЕ ДАННЫЕ ===")
    lines.append(f"📊 Тип: dict")
    lines.append(f"📋 Ключи: {keys}")
    lines.append("")

    lines.append("💾 КАК ПОЛУЧИТЬ ДОСТУП К ДАННЫМ:")
    for key in keys:
        value = data[key]
        value_type = type(value).__name__
        if isinstance(value, list):
            lines.append(f"  {key} = result['{key}']  # list, {len(value)} элементов")
        elif isinstance(value, dict):
            lines.append(f"  {key} = result['{key}']  # dict, {len(value)} ключей")
        else:
            lines.append(f"  {key} = result['{key}']  # {value_type}")
    
    return "\n".join(lines)


def _format_list_observation(data: list, capability_name: str) -> str:
    """Формирует list результат."""
    if not data:
        return "=== ПОЛУЧЕННЫЕ ДАННЫЕ ===\n💡 Список пуст (0 элементов)"

    element_type = type(data[0]).__name__ if data else "unknown"
    lines = []

    lines.append("=== ПОЛУЧЕННЫЕ ДАННЫЕ ===")
    lines.append(f"📊 Тип: list[{element_type}]")
    lines.append(f"📋 Количество элементов: {len(data)}")
    lines.append("")

    lines.append("💾 КАК ПОЛУЧИТЬ ДОСТУП К ДАННЫМ:")
    lines.append("  first = result[0]             # первый элемент")
    lines.append("  value = result[0].field       # если объект")
    lines.append("")

    lines.append(f"📋 ВСЕ {len(data)} ЭЛЕМЕНТЫ:")
    for i, item in enumerate(data):
        lines.append(f"  [{i}] {item}")

    return "\n".join(lines)


def _format_string_observation(data: str, capability_name: str) -> str:
    """Форматирует string результат."""
    lines = []
    lines.append("=== ПОЛУЧЕННЫЕ ДАННЫЕ ===")
    lines.append(f"📊 Тип: str")
    lines.append(f"📋 Длина: {len(data)} символов")
    lines.append("")
    lines.append("💾 КАК ПОЛУЧИТЬ ДОСТУП К ДАННЫМ:")
    lines.append("  text = result                # str")
    lines.append("")
    lines.append("📄 СОДЕРЖИМОЕ:")
    lines.append(data)

    return "\n".join(lines)


def _format_generic_observation(data: Any, capability_name: str) -> str:
    """Форматирует generic результат."""
    data_type = type(data).__name__
    
    lines = []
    lines.append("=== ПОЛУЧЕННЫЕ ДАННЫЕ ===")
    lines.append(f"📊 Тип: {data_type}")
    lines.append("")
    lines.append(f"💾 ЗНАЧЕНИЕ: {str(data)}")

    return "\n".join(lines)