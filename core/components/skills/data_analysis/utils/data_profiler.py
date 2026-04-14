"""
DataProfiler — профилирование данных для анализа.

ОТВЕТСТВЕННОСТЬ:
- Анализ типов колонок (int, float, str, bool, datetime)
- Базовая статистика (min, max, mean, median для числовых)
- Подсчёт пропусков и уникальных значений
- Генерация компактной схемы для промпта LLM

НЕ ОТВЕТСТВЕННОСТЬ:
- Модификация исходных данных
- Сложные ML-вычисления
- Работа с файловой системой

АРХИТЕКТУРА:
- Принимает rows: List[Dict] или текст: str
- Возвращает Dict с компактным описанием схемы
- Используется для генерации контекста промпта
"""
import statistics
import time
from typing import List, Dict, Any, Optional, Union
from datetime import datetime


class DataProfiler:
    """
    Профилировщик данных для генерации схемы и статистики.

    АРХИТЕКТУРА:
    - Статические методы (не требует состояния)
    - Работает с List[Dict] (табличные данные) и str (текст)
    - Возвращает компактный Dict для промпта
    - Поддерживает кэширование типов для производительности
    """

    # Кэш типов колонок для производительности
    _type_cache: Dict[str, str] = {}

    @staticmethod
    def profile_rows(
        rows: List[Dict[str, Any]],
        max_unique_values: int = 20
    ) -> Dict[str, Any]:
        """
        Профилирование табличных данных.

        АРХИТЕКТУРА:
        1. Определяет типы колонок
        2. Считает статистику для числовых
        3. Считает пропуски и уникальные значения
        4. Возвращает компактный Dict

        ARGS:
        - rows: List[Dict] — табличные данные
        - max_unique_values: максимум уникальных значений в выводе

        RETURNS:
        - Dict с профилем данных:
          {
              "row_count": int,
              "columns": [
                  {
                      "name": str,
                      "type": str,
                      "nullable": bool,
                      "unique_count": int,
                      "sample_values": [...],
                      "stats": {min, max, mean, median}  # для числовых
                  }
              ]
          }

        EXAMPLE:
        >>> rows = [{"age": 25, "name": "Alice"}, {"age": 30, "name": "Bob"}]
        >>> DataProfiler.profile_rows(rows)
        {'row_count': 2, 'columns': [...]}
        """
        if not rows:
            return {
                "row_count": 0,
                "columns": [],
                "summary": "Данные отсутствуют"
            }

        # Собираем все уникальные колонки
        all_columns = set()
        for row in rows:
            all_columns.update(row.keys())

        columns_profile = []
        for col_name in sorted(all_columns):
            values = [row.get(col_name) for row in rows]
            non_null_values = [v for v in values if v is not None]

            # Определяем тип
            col_type = DataProfiler._infer_column_type(non_null_values)
            
            # Статистика для числовых
            stats = None
            if col_type in ("integer", "float"):
                numeric_values = [float(v) for v in non_null_values if v is not None]
                if numeric_values:
                    stats = {
                        "min": min(numeric_values),
                        "max": max(numeric_values),
                        "mean": round(statistics.mean(numeric_values), 2),
                        "median": round(statistics.median(numeric_values), 2) if len(numeric_values) > 1 else numeric_values[0]
                    }

            # Уникальные значения
            unique_count = len(set(str(v) for v in non_null_values))
            sample_values = non_null_values[:5] if non_null_values else []

            columns_profile.append({
                "name": col_name,
                "type": col_type,
                "nullable": len(non_null_values) < len(values),
                "null_count": len(values) - len(non_null_values),
                "unique_count": unique_count,
                "sample_values": sample_values[:max_unique_values],
                "stats": stats
            })

        return {
            "row_count": len(rows),
            "columns": columns_profile,
            "summary": f"{len(rows)} строк, {len(all_columns)} колонок"
        }

    @staticmethod
    def profile_text(text: str) -> Dict[str, Any]:
        """
        Профилирование текстовых данных.

        ARGS:
        - text: str — исходный текст

        RETURNS:
        - Dict с профилем текста:
          {
              "char_count": int,
              "word_count": int,
              "line_count": int,
              "estimated_tokens": int,
              "has_structure": bool,  # есть ли заголовки/маркеры
              "sample": str  # первые 200 символов
          }

        EXAMPLE:
        >>> DataProfiler.profile_text("Hello world\\nSecond line")
        {'char_count': 24, 'word_count': 4, ...}
        """
        if not text:
            return {
                "char_count": 0,
                "word_count": 0,
                "line_count": 0,
                "estimated_tokens": 0,
                "has_structure": False,
                "sample": ""
            }

        lines = text.split('\n')
        words = text.split()
        
        # Проверяем наличие структуры (заголовки, маркеры)
        has_structure = any(
            line.strip().startswith(('#', '-', '*', '1.', '•'))
            for line in lines[:50]  # Проверяем первые 50 строк
        )

        return {
            "char_count": len(text),
            "word_count": len(words),
            "line_count": len(lines),
            "estimated_tokens": len(text) // 4,  # Эвристика: 4 символа ≈ 1 токен
            "has_structure": has_structure,
            "sample": text[:200] + ("..." if len(text) > 200 else "")
        }

    @staticmethod
    def generate_prompt_schema(
        data: Union[List[Dict[str, Any]], str],
        max_rows_sample: int = 100
    ) -> Dict[str, Any]:
        """
        Генерация компактной схемы данных для промпта LLM.

        ИСПОЛЬЗОВАНИЕ:
        - Вставляется в промпт как контекст
        - LLM видит схему, а не все данные
        - Экономит токены и улучшает качество ответов

        ARGS:
        - data: List[Dict] или str — исходные данные
        - max_rows_sample: максимум строк для анализа типов

        RETURNS:
        - Dict для вставки в промпт

        EXAMPLE:
        >>> schema = DataProfiler.generate_prompt_schema(rows)
        >>> prompt = f"Данные: {schema}\\nВопрос: ..."
        """
        if isinstance(data, str):
            profile = DataProfiler.profile_text(data)
            return {
                "type": "text",
                "profile": profile
            }
        elif isinstance(data, list):
            # Анализируем подмножество для производительности
            sample = data[:max_rows_sample] if len(data) > max_rows_sample else data
            profile = DataProfiler.profile_rows(sample)
            
            return {
                "type": "tabular",
                "profile": profile,
                "truncated": len(data) > max_rows_sample,
                "total_rows": len(data)
            }
        else:
            return {
                "type": "unknown",
                "error": f"Неподдерживаемый тип данных: {type(data).__name__}"
            }

    @staticmethod
    def _infer_column_type(values: List[Any]) -> str:
        """
        Вывод типа колонки на основе значений.

        ПРИОРИТЕТЫ:
        1. integer (если все целые числа)
        2. float (если есть дроби)
        3. boolean (если True/False)
        4. datetime (если парсятся даты)
        5. string (по умолчанию)

        ARGS:
        - values: List[Any] — ненулевые значения

        RETURNS:
        - str: тип колонки
        """
        if not values:
            return "string"

        # Проверяем boolean
        if all(isinstance(v, bool) for v in values):
            return "boolean"

        # Проверяем числовые
        numeric_count = 0
        float_count = 0
        for v in values:
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                numeric_count += 1
                if isinstance(v, float) or (isinstance(v, int) and '.' in str(v)):
                    float_count += 1
        
        if numeric_count == len(values):
            return "float" if float_count > 0 else "integer"

        # Проверяем datetime
        datetime_count = 0
        for v in values:
            if isinstance(v, str):
                # Пробуем распознать дату
                for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%Y-%m-%dT%H:%M:%S"):
                    try:
                        datetime.strptime(v, fmt)
                        datetime_count += 1
                        break
                    except ValueError:
                        continue

        if datetime_count == len(values):
            return "datetime"

        return "string"

    @staticmethod
    def should_use_python_mode(
        question: str,
        data_profile: Dict[str, Any]
    ) -> bool:
        """
        Автоопределение: можно ли ответить через python mode.

        PYTHON mode подходит если:
        - Вопрос про суммы/средние/количество
        - Данные табличные с числовыми колонками
        - Не нужна интерпретация или работа с текстом

        ARGS:
        - question: str — вопрос пользователя
        - data_profile: Dict — профиль данных

        RETURNS:
        - bool: True если python mode достаточно
        """
        python_keywords = [
            "посчитай", "сколько", "сумма", "средн", "колич",
            "min", "max", "минимум", "максимум", "итог", "всего",
            "sum", "count", "avg", "mean", "total", "number",
            "найди сумму", "найди среднее", "вычисли"
        ]

        question_lower = question.lower()
        has_python_intent = any(
            kw in question_lower for kw in python_keywords
        )

        # Проверяем что данные табличные
        is_tabular = data_profile.get("type") == "tabular"
        has_numeric = False
        if is_tabular:
            for col in data_profile.get("profile", {}).get("columns", []):
                if col.get("type") in ("integer", "float"):
                    has_numeric = True
                    break

        return has_python_intent and is_tabular and has_numeric

    @staticmethod
    def should_use_semantic_mode(
        question: str,
        data_profile: Dict[str, Any]
    ) -> bool:
        """
        Автоопределение: нужен ли semantic mode.

        SEMANTIC mode нужен если:
        - Вопрос про текст/смысл/выводы
        - Данные текстовые (большие описания)
        - Нужна работа с естественным языком

        ARGS:
        - question: str — вопрос пользователя
        - data_profile: Dict — профиль данных

        RETURNS:
        - bool: True если нужен semantic mode
        """
        semantic_keywords = [
            "текст", "смысл", "описани", "проблем", "тренд",
            "ключев", "выдели", "проанализируй", "резюме",
            "text", "meaning", "describe", "trend", "key",
            "проблемы", "статусы", "выводы"
        ]

        question_lower = question.lower()
        has_semantic_intent = any(
            kw in question_lower for kw in semantic_keywords
        )

        # Проверяем что данные текстовые
        is_text = data_profile.get("type") == "text"

        return has_semantic_intent or is_text

    @staticmethod
    def estimate_processing_time(
        row_count: int,
        char_count: int,
        mode: str = "python"
    ) -> float:
        """
        Оценка времени обработки в миллисекундах.

        ARGS:
        - row_count: int — количество строк
        - char_count: int — количество символов
        - mode: str — режим обработки

        RETURNS:
        - float: оценка времени в мс
        """
        if mode == "python":
            # Python: ~1мс на 100 строк
            return max(1.0, row_count / 100.0)
        elif mode == "llm":
            # LLM: ~100мс + 1мс на 100 символов промпта
            return max(100.0, char_count / 100.0)
        elif mode == "semantic":
            # Semantic: ~200мс + 1мс на 50 символов
            return max(200.0, char_count / 50.0)
        else:
            return 50.0  # default estimate
