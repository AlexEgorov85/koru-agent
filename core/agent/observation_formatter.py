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
    
    # Показываем только данные без метаинформации
    if isinstance(result_data, list) and result_data:
        for i, item in enumerate(result_data[:sample_count]):
            if hasattr(item, '__dict__'):
                item = item.__dict__
            if isinstance(item, dict):
                row_str = ", ".join(f"{k}={v}" for k, v in item.items())
                lines.append(f"[{i}] {row_str}")
            else:
                lines.append(f"[{i}] {str(item)}")
    elif hasattr(result_data, 'rows') and result_data.rows:
        sample_rows = list(result_data.rows)[:sample_count]
        for i, row in enumerate(sample_rows):
            if hasattr(row, '__dict__'):
                row = row.__dict__
            if isinstance(row, dict):
                row_str = ", ".join(f"{k}={v}" for k, v in row.items())
                lines.append(f"[{i}] {row_str}")
            else:
                lines.append(f"[{i}] {str(row)}")
    elif isinstance(result_data, str) and result_data:
        lines.append(result_data[:100])
    else:
        lines.append("Нет данных")
    
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
    max_display = 10

    lines = []
    
    if warning:
        lines.append(f"⚠️ {warning}")

    if not rows:
        lines.append("Нет данных")
        return "\n".join(lines)
    
    # Показываем только данные
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
    max_display = 10

    lines = []
    
    if warning:
        lines.append(f"⚠️ {warning}")

    if not rows:
        lines.append("Нет данных")
        return "\n".join(lines)
    
    # Показываем только данные
    for i, row in enumerate(rows[:max_display]):
        if isinstance(row, dict):
            row_str = ", ".join(f"{k}={v}" for k, v in row.items())
            lines.append(f"[{i}] {row_str}")
        else:
            lines.append(f"[{i}] {str(row)}")
    
    if len(rows) > max_display:
        lines.append(f"... и ещё {len(rows) - max_display} записей")

    return "\n".join(lines)


def _format_vector_search_observation(data: dict) -> str:
    """Форматирует vector search результат."""
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
            score = getattr(r, 'score', 0)
            lines.append(f"[{i}] ({score:.2f}) {r.text}")
        elif isinstance(r, dict):
            lines.append(f"[{i}] {json.dumps(r, ensure_ascii=False, default=str)}")
        else:
            lines.append(f"[{i}] {r}")

    return "\n".join(lines)


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
