"""
Утилита для формирования наблюдений из результатов выполнения.

ARCHITECTURE:
- format_observation: полное форматирование (для сохранения всех данных)
- smart_format_observation: интеллектуальное форматирование (для быстрого просмотра)
  - маленькие данные (до 5 строк или 500 символов) → всё как есть
  - большие данные → статистика + пример + указание на анализ
"""
import json
from typing import Any, Dict, Optional


def format_observation(
    result_data: Any,
    capability_name: str,
    parameters: Optional[Dict[str, Any]] = None
) -> str:
    """
    Полное форматирование результата для сохранения в observation.
    """
    if result_data is None:
        return "Данные отсутствуют"

    if isinstance(result_data, dict):
        return _format_dict_observation(result_data, capability_name, parameters)
    elif isinstance(result_data, list):
        return _format_list_observation(result_data, capability_name)
    elif isinstance(result_data, str):
        return _format_string_observation(result_data, capability_name)
    else:
        return _format_generic_observation(result_data, capability_name)


def smart_format_observation(
    result_data: Any,
    capability_name: str,
    parameters: Optional[Dict[str, Any]] = None
) -> str:
    """
    Интеллектуальное форматирование для быстрого просмотра.

    ПРАВИЛА:
    - Данные до 5 строк или 500 символов → показать всё
    - Большие данные → статистика + пример (3 строки или 100 символов)
    """
    if result_data is None:
        return "Данные отсутствуют"

    data_type = type(result_data).__name__

    if isinstance(result_data, list):
        row_count = len(result_data)
        sample_count = min(3, row_count)
    else:
        row_count = 0
        sample_count = 0

    if hasattr(result_data, 'rows'):
        row_count = len(getattr(result_data, 'rows', [])) or row_count

    try:
        if hasattr(result_data, 'model_dump'):
            data_dict = result_data.model_dump()
        elif hasattr(result_data, '__dict__'):
            data_dict = result_data.__dict__
        elif isinstance(result_data, dict):
            data_dict = result_data
        else:
            data_dict = None

        if data_dict:
            data_str = json.dumps(data_dict, ensure_ascii=False, default=str)
        else:
            data_str = str(result_data)
    except:
        data_str = str(result_data)

    char_count = len(data_str)

    MAX_ROWS = 5
    MAX_CHARS = 500

    if row_count <= MAX_ROWS and char_count <= MAX_CHARS:
        return format_observation(result_data, capability_name, parameters)

    lines = []

    rows_data = []

    if isinstance(result_data, list) and result_data:
        rows_data = result_data[:sample_count]
    elif hasattr(result_data, 'rows') and result_data.rows:
        rows_data = list(result_data.rows)[:sample_count]
    elif isinstance(result_data, dict) and "rows" in result_data:
        row_count_dict = len(result_data.get("rows", []))
        if row_count_dict > 0:
            lines.append(f"📊 Получено {row_count_dict} строк")
            columns = result_data.get("columns", [])
            if columns:
                lines.append(f"📐 Колонки: {', '.join(str(c) for c in columns[:10])}")
            sample = result_data["rows"][:3]
            for i, row in enumerate(sample):
                if isinstance(row, dict):
                    preview = {k: row[k] for k in list(row.keys())[:5]}
                    lines.append(f"  Пример {i+1}: {json.dumps(preview, ensure_ascii=False)}")
            if row_count_dict > 3:
                lines.append(f"💡 Для полного анализа используйте data_analysis.analyze_step_data")
    elif isinstance(result_data, list) and result_data and any("score" in r for r in result_data if isinstance(r, dict)):
        # Обработка результатов векторного поиска (новый формат — список)
        results_count = len(result_data)
        if results_count > 0:
            lines.append(f"📊 Найдено: {results_count} результатов")
            sample = result_data[:3]
            for i, r in enumerate(sample):
                if isinstance(r, dict):
                    score = r.get('score', 0)
                    text = r.get('matched_text', r.get('content', str(r)))[:80]
                    lines.append(f"  [{i+1}] ({score:.2f}) {text}")
            if results_count > 3:
                lines.append(f"💡 Для полного анализа используйте data_analysis.analyze_step_data")
    elif isinstance(result_data, str) and result_data:
        lines.append(result_data[:100])
    else:
        lines.append(f"Нет данных (тип: {type(result_data).__name__})")

    if rows_data:
        for i, row in enumerate(rows_data):
            if isinstance(row, dict):
                row_str = ", ".join(f"{k}={v}" for k, v in row.items())
                lines.append(f"[{i}] {row_str}")
            elif hasattr(row, '__dict__'):
                row_str = ", ".join(f"{k}={v}" for k, v in row.__dict__.items())
                lines.append(f"[{i}] {row_str}")
            else:
                lines.append(f"[{i}] {str(row)}")

    return "\n".join(lines)


def _format_dict_observation(
    data: Any,
    capability_name: str,
    parameters: Optional[Dict[str, Any]]
) -> str:
    """Форматирует dict/dataclass/pydantic результат."""
    data_dict = _to_dict(data)

    if "rows" in data_dict and "rowcount" in data_dict:
        return _format_sql_observation(data_dict, parameters)
    elif "results" in data_dict and "query" in data_dict:
        return _format_vector_search_observation(data_dict)
    elif capability_name.startswith("vector_search"):
        return _format_vector_search_observation(data_dict)
    else:
        return json.dumps(data_dict, ensure_ascii=False, indent=2, default=str)


def _to_dict(data: Any) -> dict:
    """Конвертирует dict/dataclass/pydantic в dict."""
    if isinstance(data, dict):
        return data
    if hasattr(data, 'model_dump'):
        return data.model_dump()
    if hasattr(data, '__dict__'):
        return data.__dict__
    return {"value": str(data)}


def _format_sql_result_object(data: Any, parameters: Optional[Dict[str, Any]] = None) -> str:
    """Форматирует SQL результат (dataclass/pydantic объект)."""
    rows = getattr(data, 'rows', []) or []
    warning = getattr(data, 'warning', None)
    sql_query = getattr(data, 'sql_query', "")
    max_display = 10

    lines = []

    if sql_query:
        lines.append(f"SQL: {sql_query}")
        if rows:
            lines.append("")

    if warning:
        lines.append(f"⚠️ {warning}")

    if not rows:
        lines.append("Нет данных")
        return "\n".join(lines)

    for i, row in enumerate(rows[:max_display]):
        if hasattr(row, '__dict__'):
            row = row.__dict__
        if isinstance(row, dict):
            row_str = ", ".join(f"{k}={v}" for k, v in row.items())
            lines.append(f"[{i}] {row_str}")
        else:
            lines.append(f"[{i}] {str(row)}")

    if len(rows) > max_display:
        lines.append(f"... и ещё {len(rows) - max_display} записей")

    return "\n".join(lines)


def _format_vector_search_result_object(data: Any) -> str:
    """Форматирует vector search результат (dataclass/pydantic объект)."""
    results = getattr(data, 'results', []) or []
    query = getattr(data, 'query', "")

    if not results:
        return f"Запрос: {query}\nРезультатов не найдено"

    lines = []
    lines.append(f"Запрос: {query}")
    lines.append(f"Найдено: {len(results)}")
    lines.append("")

    for i, r in enumerate(results[:10]):
        if hasattr(r, 'text'):
            score = getattr(r, 'score', 0)
            lines.append(f"[{i}] ({score:.2f}) {r.text}")
        elif hasattr(r, '__dict__'):
            lines.append(f"[{i}] {json.dumps(r.__dict__, ensure_ascii=False, default=str)}")
        else:
            lines.append(f"[{i}] {str(r)}")

    return "\n".join(lines)


def _format_sql_observation(data: dict, parameters: Optional[Dict[str, Any]] = None) -> str:
    """Форматирует SQL результат."""
    rows = data.get("rows", [])
    warning = data.get("warning")
    sql_query = data.get("sql_query", "")
    max_display = 10

    if warning:
        return f"⚠️ {warning}"

    if not rows:
        return "Запрос выполнен, данных не найдено"

    display_rows = rows[:max_display]
    row_count = len(rows)
    total_chars = sum(len(str(r)) for r in display_rows)

    is_small = len(display_rows) < 5 and total_chars < 500

    if is_small:
        lines = []
        for row in display_rows:
            if isinstance(row, dict):
                line = "| " + " | ".join(str(v) for v in row.values()) + " |"
                lines.append(line)
            else:
                lines.append(f"| {row} |")

        if len(rows) > max_display:
            lines.append(f"| ... (+ ещё {len(rows) - max_display} записей) |")

        table = "\n".join(lines)
    else:
        table = f"Получено {row_count} строк ({total_chars} символов). Для анализа запустите data_analysis."

    if sql_query:
        clean_sql = sql_query.replace('\n', ' ').strip()
        return f"Выполнен запрос {clean_sql};\n{table}"

    return table


def _format_vector_search_observation(data: Any) -> str:
    """Форматирует vector search результат (поддерживает и старый dict, и новый list формат)."""
    # Новый формат: список результатов напрямую
    if isinstance(data, list):
        results = data
        if not results:
            return "Результатов не найдено"
        lines = [f"Найдено: {len(results)}", ""]
        for i, r in enumerate(results[:10]):
            if isinstance(r, dict):
                score = r.get('score', 0)
                text = r.get('matched_text', r.get('title', r.get('description', str(r))))[:80]
                lines.append(f"  [{i+1}] ({score:.2f}) {text}")
            else:
                lines.append(f"  [{i+1}] {r}")
        return "\n".join(lines)

    # Старый формат: словарь с ключами results, query
    if isinstance(data, dict):
        results = data.get("results", [])
        query = data.get("query", "")

        if not results:
            return f"Запрос: {query}\nРезультатов не найдено"

        lines = []
        lines.append(f"Запрос: {query}")
        lines.append(f"Найдено: {len(results)}")
        lines.append("")

        for i, r in enumerate(results[:10]):
            if hasattr(r, 'text'):
                score = getattr(r, 'score',0)
                lines.append(f"[{i}] ({score:.2f}) {r.text}")
            elif isinstance(r, dict):
                lines.append(f"[{i}] {json.dumps(r, ensure_ascii=False, default=str)}")
            else:
                lines.append(f"[{i}] {r}")

        return "\n".join(lines)

    return str(data)


def _format_list_observation(data: list, capability_name: str) -> str:
    """Формирует list результат."""
    if not data:
        return "Пустой список"

    lines = []
    for i, item in enumerate(data[:10]):
        if isinstance(item, dict):
            row_str = ", ".join(f"{k}={v}" for k, v in item.items())
            lines.append(f"[{i}] {row_str}")
        else:
            lines.append(f"[{i}] {item}")

    if len(data) > 10:
        lines.append(f"... и ещё {len(data) - 10} элементов")

    return "\n".join(lines)


def _format_string_observation(data: str, capability_name: str) -> str:
    """Форматирует string результат."""
    return data


def _format_generic_observation(data: Any, capability_name: str) -> str:
    """Форматирует generic результат."""
    if hasattr(data, 'model_dump'):
        return json.dumps(data.model_dump(), ensure_ascii=False, indent=2, default=str)
    elif isinstance(data, dict):
        return json.dumps(data, ensure_ascii=False, indent=2, default=str)
    return str(data)