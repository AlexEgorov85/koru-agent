"""
Утилита для формирования наблюдений из результатов выполнения.

АРХИТЕКТУРА:
- format_observation: единая функция с интеллектуальным форматированием
  - Маленькие данные (до 5 строк или 500 символов) → всё как есть
  - Большие данные → статистика + пример (3 строки или 100 символов)
"""
import json
from typing import Any, Dict, Optional

# =============================================================================
# ЛИМИТЫ ДЛЯ ОЦЕНКИ РАЗМЕРА ДАННЫХ
# =============================================================================
# Можно менять гибко, они все в одном месте
MAX_ROWS = 5                    # Максимальное количество строк для полного показа
MAX_JSON_BYTES = 1500            # Максимальный размер JSON в байтах
MAX_TEXT_CHARS = 1500            # Максимальная длина текста в символах
MAX_DICT_KEYS = 10              # Максимальное количество ключей в словаре
MAX_SUMMARY_CHARS = 500         # Лимит для краткого форматирования
MAX_SAMPLE_ROWS = 3             # Количество примеров строк в кратком формате
MAX_SAMPLE_CHARS = 100          # Длина примера в кратком формате


def format_observation(
    result_data: Any,
    capability_name: str,
    parameters: Optional[Dict[str, Any]] = None
) -> str:
    """
    Интеллектуальное форматирование результата для наблюдения.
    
    ЛОГИКА:
    - Данные до 5 строк или 500 символов → полное форматирование
    - Большие данные → статистика + пример + указание на анализ
    - Специальная обработка для vector search (score), violations, SQL
    """
    if result_data is None:
        return "Данные отсутствуют"
    
    # Конвертируем Pydantic/dataclass в dict для единообразной обработки
    data = _to_dict(result_data)
    
    # Определяем размер данных
    row_count = _estimate_row_count(data)
    data_str = _to_string(data)
    char_count = len(data_str)
    
    # Маленькие данные → полное форматирование
    if row_count <= MAX_ROWS and char_count <= MAX_SUMMARY_CHARS:
        return _format_full(data, capability_name, parameters)
    
    # Большие данные → краткая статистика + пример
    return _format_summary(data, capability_name, row_count, char_count)


def _to_dict(data: Any) -> Any:
    """Конвертирует dict/dataclass/pydantic в dict."""
    if isinstance(data, dict):
        return data
    if hasattr(data, 'model_dump'):
        try:
            return data.model_dump()
        except Exception:
            pass
    if hasattr(data, '__dict__') and not isinstance(data, dict):
        return data.__dict__
    return data


def _to_string(data: Any) -> str:
    """Преобразует данные в строку для оценки размера."""
    try:
        if isinstance(data, dict):
            return json.dumps(data, ensure_ascii=False, default=str)
        return str(data)
    except Exception:
        return str(data)


def _estimate_row_count(data: Any) -> int:
    """Оценивает количество строк/элементов в данных."""
    if isinstance(data, list):
        return len(data)
    if isinstance(data, dict):
        if "rows" in data:
            return len(data.get("rows", []))
        if "results" in data:
            return len(data.get("results", []))
    if hasattr(data, 'rows'):
        return len(getattr(data, 'rows', []))
    return 0


def _format_full(data: Any, capability_name: str, parameters: Optional[Dict[str, Any]]) -> str:
    """Полное форматирование для небольших данных."""
    if isinstance(data, dict):
        return _format_dict_full(data, capability_name, parameters)
    elif isinstance(data, list):
        return _format_list_full(data)
    elif isinstance(data, str):
        return data
    else:
        return str(data)


def _format_dict_full(data: dict, capability_name: str, parameters: Optional[Dict[str, Any]]) -> str:
    """Полное форматирование dict."""
    if "rows" in data and ("rowcount" in data or "warning" in data):
        return _format_sql_full(data, parameters)
    elif "results" in data and "query" in data:
        return _format_vector_search_full(data)
    elif capability_name.startswith("vector_search"):
        return _format_vector_search_full(data)
    elif capability_name.startswith("data_analysis") and "content" in data:
        return str(data["content"])
    else:
        return json.dumps(data, ensure_ascii=False, indent=2, default=str)


def _format_sql_full(data: dict, parameters: Optional[Dict[str, Any]] = None) -> str:
    """Полное форматирование SQL результата."""
    rows = data.get("rows", [])
    warning = data.get("warning")
    sql_query = data.get("sql_query", "")
    
    if warning:
        return f"⚠️ {warning}"
    
    if not rows:
        return "Запрос выполнен, данных не найдено"
    
    lines = []
    if sql_query:
        lines.append(f"Выполнен запрос: {sql_query}")
        lines.append("")
    
    for i, row in enumerate(rows[:10]):
        if isinstance(row, dict):
            line = "| " + " | ".join(str(v) for v in row.values()) + " |"
            lines.append(line)
        else:
            lines.append(f"| {row} |")
    
    if len(rows) > 10:
        lines.append(f"... и ещё {len(rows) - 10} записей")
    
    return "\n".join(lines)


def _format_vector_search_full(data: Any) -> str:
    """Полное форматирование vector search результата."""
    if isinstance(data, list):
        results = data
        if not results:
            return "Результатов не найдено"
        lines = [f"Найдено: {len(results)}", ""]
        for i, r in enumerate(results[:10]):
            if isinstance(r, dict):
                score = r.get('score', 0)
                text = r.get('matched_text', r.get('title', r.get('description', str(r))))[:100]
                lines.append(f"  [{i+1}] ({score:.2f}) {text}")
            else:
                lines.append(f"  [{i+1}] {r}")
        return "\n".join(lines)
    
    if isinstance(data, dict):
        results = data.get("results", [])
        query = data.get("query", "")
        if not results:
            return f"Запрос: {query}\nРезультатов не найдено"
        lines = [f"Запрос: {query}", f"Найдено: {len(results)}", ""]
        for i, r in enumerate(results[:10]):
            if isinstance(r, dict):
                score = r.get('score', 0)
                text = r.get('matched_text', r.get('title', str(r)))[:100]
                lines.append(f"  [{i+1}] ({score:.2f}) {text}")
            else:
                lines.append(f"  [{i+1}] {r}")
        return "\n".join(lines)
    
    return str(data)


def _format_list_full(data: list) -> str:
    """Полное форматирование списка."""
    if not data:
        return "Пустой список"
    
    lines = []
    for i, item in enumerate(data[:10]):
        if isinstance(item, dict):
            line = ", ".join(f"{k}={v}" for k, v in item.items())
            lines.append(f"[{i}] {line}")
        else:
            lines.append(f"[{i}] {item}")
    
    if len(data) > 10:
        lines.append(f"... и ещё {len(data) - 10} элементов")
    
    return "\n".join(lines)


def _format_summary(data: Any, capability_name: str, row_count: int, char_count: int) -> str:
    """Краткая статистика для больших данных."""
    lines = []
    
    # Специальная обработка для vector search (проверка на score)
    if isinstance(data, list) and data:
        if _is_vector_search_results(data):
            lines.append(f"📊 Найдено: {row_count} результатов")
            for i, r in enumerate(data[:3]):
                if isinstance(r, dict):
                    score = r.get('score', 0)
                    text = r.get('matched_text', r.get('content', str(r)))[:80]
                    lines.append(f"  [{i+1}] ({score:.2f}) {text}")
            lines.append(f"💡 Для полного анализа используйте data_analysis.analyze_step_data")
            return "\n".join(lines)
        
        if _is_violations_list(data):
            lines.append(f"📊 Найдено: {row_count} нарушений")
            for i, r in enumerate(data[:3]):
                if isinstance(r, dict):
                    score = r.get('score', 0)
                    text = r.get('matched_text', r.get('description', str(r)))[:80]
                    lines.append(f"  [{i+1}] ({score:.2f}) {text}")
            lines.append(f"💡 Для полного анализа используйте data_analysis.analyze_step_data")
            return "\n".join(lines)
    
    # SQL результаты
    if isinstance(data, dict) and "rows" in data:
        rows = data.get("rows", [])
        lines.append(f"📊 Получено {len(rows)} строк ({char_count} символов)")
        columns = data.get("columns", [])
        if columns:
            lines.append(f"📐 Колонки: {', '.join(str(c) for c in columns[:10])}")
        for i, row in enumerate(rows[:3]):
            if isinstance(row, dict):
                preview = {k: row[k] for k in list(row.keys())[:5]}
                lines.append(f"  Пример {i+1}: {json.dumps(preview, ensure_ascii=False, default=str)}")
        lines.append(f"💡 Для полного анализа используйте data_analysis.analyze_step_data")
        return "\n".join(lines)
    
    # Общий случай
    lines.append(f"📊 Данные: {row_count} элементов, {char_count} символов")
    lines.append(f"💡 Для полного анализа используйте data_analysis.analyze_step_data")
    return "\n".join(lines)


def _is_vector_search_results(data: list) -> bool:
    """Проверяет, является ли список результатами vector search."""
    return any(
        (isinstance(r, dict) and "score" in r) or 
        (not isinstance(r, dict) and hasattr(r, 'score'))
        for r in data
    )


def _is_violations_list(data: list) -> bool:
    """Проверяет, является ли список результатами нарушений."""
    for r in data:
        if isinstance(r, dict) and r.get("type") == "violations":
            return True
        if not isinstance(r, dict) and getattr(r, 'type', None) == "violations":
            return True
    return False
