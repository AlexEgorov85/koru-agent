"""
AnalyticsEngine — безопасный движок аналитики.

ОТВЕТСТВЕННОСТЬ:
- Фильтрация строк по условиям
- Группировка и агрегация (sum, mean, count, min, max, median)
- Сортировка и лимитирование
- Базовое описание данных (describe)
- Выполнение JSON DSL спецификаций от LLM Planner

НЕ ОТВЕТСТВЕННОСТЬ:
- Генерация кода (НЕТ exec/eval)
- Прямой вызов LLM
- Работа с файловой системой

АРХИТЕКТУРА:
- Только if/elif логика — НЕТ exec/eval
- 100% безопасно (sandbox-free)
- Детерминировано (одинаковый вход → одинаковый результат)
- Легко тестировать

JSON DSL СПЕЦИФИКАЦИЯ:
{
    "operations": [
        {"type": "filter", "column": "age", "operator": "gt", "value": 18},
        {"type": "group_by", "columns": ["category"], "metrics": [{"column": "price", "func": "sum"}]},
        {"type": "sort", "column": "total", "order": "desc"},
        {"type": "limit", "n": 10}
    ]
}
"""
import statistics
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime


class AnalyticsEngine:
    """
    Безопасный движок аналитики на чистом Python.

    АРХИТЕКТУРА:
    - Статические методы (не требует состояния)
    - Принимает rows: List[Dict]
    - Возвращает обработанные rows или агрегированные результаты
    - Поддерживает JSON DSL для сложных операций

    ГАРАНТИИ:
    - НЕТ exec/eval
    - НЕТ доступа к ФС/БД
    - 100% детерминировано
    """

    @staticmethod
    def describe(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Базовое описание данных (аналог pandas describe).

        ARGS:
        - rows: List[Dict] — входные данные

        RETURNS:
        - Dict со статистикой по каждой колонке

        EXAMPLE:
        >>> AnalyticsEngine.describe([{"age": 25}, {"age": 30}])
        {'row_count': 2, 'columns': {'age': {...}}}
        """
        if not rows:
            return {"row_count": 0, "columns": {}}

        columns = set()
        for row in rows:
            columns.update(row.keys())

        result = {
            "row_count": len(rows),
            "columns": {}
        }

        for col in columns:
            values = [row.get(col) for row in rows]
            non_null = [v for v in values if v is not None]

            col_stats = {
                "count": len(non_null),
                "null_count": len(values) - len(non_null),
                "unique": len(set(str(v) for v in non_null))
            }

            # Числовая статистика
            if non_null and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in non_null):
                numeric = [float(v) for v in non_null]
                col_stats.update({
                    "mean": round(statistics.mean(numeric), 2),
                    "min": min(numeric),
                    "max": max(numeric),
                    "median": round(statistics.median(numeric), 2) if len(numeric) > 1 else numeric[0],
                    "stdev": round(statistics.stdev(numeric), 2) if len(numeric) > 1 else 0
                })

            result["columns"][col] = col_stats

        return result

    @staticmethod
    def filter_rows(
        rows: List[Dict[str, Any]],
        conditions: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Фильтрация строк по условиям.

        ПОДДЕРЖИВАЕМЫЕ ОПЕРАТОРЫ:
        - eq: равно (==)
        - ne: не равно (!=)
        - gt: больше (>)
        - gte: больше или равно (>=)
        - lt: меньше (<)
        - lte: меньше или равно (<=)
        - in: в списке
        - contains: содержит подстроку
        - not_null: не None
        - is_null: равно None

        ARGS:
        - rows: List[Dict] — входные данные
        - conditions: List[Dict] — список условий:
          [{"column": "age", "operator": "gt", "value": 18}]

        RETURNS:
        - List[Dict] — отфильтрованные строки

        EXAMPLE:
        >>> rows = [{"age": 25}, {"age": 15}]
        >>> AnalyticsEngine.filter_rows(rows, [{"column": "age", "operator": "gt", "value": 18}])
        [{'age': 25}]
        """
        if not conditions:
            return rows

        def check_condition(row: Dict[str, Any], condition: Dict[str, Any]) -> bool:
            """Проверка одного условия для строки."""
            col = condition["column"]
            op = condition["operator"]
            value = condition.get("value")

            row_value = row.get(col)

            if op == "eq":
                return row_value == value
            elif op == "ne":
                return row_value != value
            elif op == "gt":
                return row_value is not None and row_value > value
            elif op == "gte":
                return row_value is not None and row_value >= value
            elif op == "lt":
                return row_value is not None and row_value < value
            elif op == "lte":
                return row_value is not None and row_value <= value
            elif op == "in":
                return row_value in value if isinstance(value, list) else False
            elif op == "contains":
                return isinstance(row_value, str) and value in row_value
            elif op == "not_null":
                return row_value is not None
            elif op == "is_null":
                return row_value is None
            else:
                raise ValueError(f"Неподдерживаемый оператор: {op}")

        result = []
        for row in rows:
            if all(check_condition(row, cond) for cond in conditions):
                result.append(row)

        return result

    @staticmethod
    def group_by(
        rows: List[Dict[str, Any]],
        columns: List[str],
        metrics: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Группировка с агрегацией.

        ПОДДЕРЖИВАЕМЫЕ МЕТРИКИ:
        - count: количество строк
        - sum: сумма
        - mean: среднее
        - min: минимум
        - max: максимум
        - median: медиана
        - unique: количество уникальных значений

        ARGS:
        - rows: List[Dict] — входные данные
        - columns: List[str] — колонки для группировки
        - metrics: List[Dict] — метрики для агрегации:
          [{"column": "price", "func": "sum", "alias": "total_price"}]

        RETURNS:
        - List[Dict] — сгруппированные данные

        EXAMPLE:
        >>> rows = [{"cat": "A", "price": 10}, {"cat": "A", "price": 20}]
        >>> AnalyticsEngine.group_by(rows, ["cat"], [{"column": "price", "func": "sum"}])
        [{'cat': 'A', 'price_sum': 30}]
        """
        if not rows:
            return []

        # Группируем
        groups: Dict[tuple, List[Dict]] = {}
        for row in rows:
            key = tuple(row.get(col) for col in columns)
            if key not in groups:
                groups[key] = []
            groups[key].append(row)

        # Агрегируем
        result = []
        for key, group_rows in groups.items():
            row = dict(zip(columns, key))

            for metric in metrics:
                col = metric["column"]
                func = metric["func"]
                alias = metric.get("alias", f"{col}_{func}")

                values = [r.get(col) for r in group_rows if r.get(col) is not None]

                if func == "count":
                    row[alias] = len(group_rows)
                elif func == "sum":
                    row[alias] = sum(float(v) for v in values if isinstance(v, (int, float)))
                elif func == "mean":
                    row[alias] = round(statistics.mean([float(v) for v in values if isinstance(v, (int, float))]), 2) if values else 0
                elif func == "min":
                    row[alias] = min(values) if values else None
                elif func == "max":
                    row[alias] = max(values) if values else None
                elif func == "median":
                    numeric = [float(v) for v in values if isinstance(v, (int, float))]
                    row[alias] = round(statistics.median(numeric), 2) if len(numeric) > 1 else (numeric[0] if numeric else None)
                elif func == "unique":
                    row[alias] = len(set(str(v) for v in values))
                else:
                    raise ValueError(f"Неподдерживаемая метрика: {func}")

            result.append(row)

        return result

    @staticmethod
    def sort_rows(
        rows: List[Dict[str, Any]],
        column: str,
        order: str = "asc"
    ) -> List[Dict[str, Any]]:
        """
        Сортировка строк по колонке.

        ARGS:
        - rows: List[Dict] — входные данные
        - column: str — колонка для сортировки
        - order: str — "asc" или "desc"

        RETURNS:
        - List[Dict] — отсортированные строки

        EXAMPLE:
        >>> rows = [{"age": 25}, {"age": 15}]
        >>> AnalyticsEngine.sort_rows(rows, "age", "desc")
        [{'age': 25}, {'age': 15}]
        """
        if not rows:
            return []

        reverse = order.lower() in ("desc", "descending")
        
        # Фильтруем None для корректной сортировки
        def sort_key(row):
            val = row.get(column)
            if val is None:
                return (1, "")  # None всегда в конце
            return (0, val)

        return sorted(rows, key=sort_key, reverse=reverse)

    @staticmethod
    def limit_rows(rows: List[Dict[str, Any]], n: int) -> List[Dict[str, Any]]:
        """
        Ограничение количества строк.

        ARGS:
        - rows: List[Dict] — входные данные
        - n: int — максимум строк

        RETURNS:
        - List[Dict] — первые n строк

        EXAMPLE:
        >>> AnalyticsEngine.limit_rows([{"a": 1}, {"b": 2}, {"c": 3}], 2)
        [{'a': 1}, {'b': 2}]
        """
        return rows[:n]

    @staticmethod
    def execute_dsl(
        rows: List[Dict[str, Any]],
        dsl_spec: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Выполнение JSON DSL спецификации.

        ПОДДЕРЖИВАЕМЫЕ ОПЕРАЦИИ:
        - filter: фильтрация
        - group_by: группировка
        - aggregate: агрегация (без группировки)
        - sort: сортировка
        - limit: ограничение
        - select: выбор колонок
        - describe: описание данных

        ARGS:
        - rows: List[Dict] — входные данные
        - dsl_spec: Dict — JSON DSL спецификация:
          {"operations": [{"type": "filter", ...}, ...]}

        RETURNS:
        - Dict с результатом и метаданными:
          {"result": [...], "operations_executed": 3, "row_count": 10}

        EXAMPLE:
        >>> dsl = {
        ...     "operations": [
        ...         {"type": "filter", "conditions": [...]},
        ...         {"type": "group_by", "columns": [...], "metrics": [...]}
        ...     ]
        ... }
        >>> AnalyticsEngine.execute_dsl(rows, dsl)
        {'result': [...], 'operations_executed': 2}
        """
        if not rows:
            return {
                "result": [],
                "operations_executed": 0,
                "row_count": 0,
                "message": "Входные данные пусты"
            }

        operations = dsl_spec.get("operations", [])
        current_rows = rows.copy()
        operations_executed = 0

        for i, op in enumerate(operations):
            op_type = op.get("type")

            try:
                if op_type == "filter":
                    conditions = op.get("conditions", [])
                    current_rows = AnalyticsEngine.filter_rows(current_rows, conditions)
                
                elif op_type == "group_by":
                    columns = op.get("columns", [])
                    metrics = op.get("metrics", [])
                    current_rows = AnalyticsEngine.group_by(current_rows, columns, metrics)
                
                elif op_type == "aggregate":
                    # Агрегация без группировки (весь датасет = 1 группа)
                    metrics = op.get("metrics", [])
                    current_rows = AnalyticsEngine.group_by(current_rows, [], metrics)
                
                elif op_type == "sort":
                    column = op.get("column")
                    order = op.get("order", "asc")
                    current_rows = AnalyticsEngine.sort_rows(current_rows, column, order)
                
                elif op_type == "limit":
                    n = op.get("n", 10)
                    current_rows = AnalyticsEngine.limit_rows(current_rows, n)
                
                elif op_type == "select":
                    columns = op.get("columns", [])
                    if columns:
                        current_rows = [{k: row.get(k) for k in columns} for row in current_rows]
                
                elif op_type == "describe":
                    # describe возвращает статистику, а не строки
                    desc = AnalyticsEngine.describe(current_rows)
                    return {
                        "result": desc,
                        "operations_executed": i + 1,
                        "row_count": desc.get("row_count", 0),
                        "operation_type": "describe"
                    }
                
                else:
                    raise ValueError(f"Неподдерживаемая операция: {op_type}")

                operations_executed += 1

            except Exception as e:
                raise ValueError(
                    f"Ошибка выполнения операции #{i} ({op_type}): {str(e)}. "
                    f"Проверьте параметры операции."
                )

        return {
            "result": current_rows,
            "operations_executed": operations_executed,
            "row_count": len(current_rows),
            "operation_type": "transform"
        }

    @staticmethod
    def auto_aggregate(
        rows: List[Dict[str, Any]],
        value_column: Optional[str] = None,
        group_column: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Автоматическая агрегация для быстрого анализа.

        ИСПОЛЬЗОВАНИЕ:
        - Когда LLM не дал спецификацию
        - Для быстрых метрик по умолчанию
        - Для дебага и превью данных

        ARGS:
        - rows: List[Dict] — входные данные
        - value_column: str — колонка для агрегации (автопоиск если None)
        - group_column: str — колонка для группировки (опционально)

        RETURNS:
        - Dict с агрегацией

        EXAMPLE:
        >>> AnalyticsEngine.auto_aggregate([{"price": 10}, {"price": 20}])
        {'count': 2, 'sum': 30, 'mean': 15, ...}
        """
        if not rows:
            return {"count": 0, "message": "Нет данных"}

        # Автопоиск числовой колонки
        if not value_column:
            for col in rows[0].keys():
                values = [r.get(col) for r in rows[:10]]
                if all(isinstance(v, (int, float)) for v in values if v is not None):
                    value_column = col
                    break

        if not value_column:
            return {
                "count": len(rows),
                "message": "Числовые колонки не найдены",
                "columns": list(rows[0].keys())
            }

        values = [r.get(value_column) for r in rows if r.get(value_column) is not None]
        numeric = [float(v) for v in values if isinstance(v, (int, float))]

        result = {
            "count": len(rows),
            "non_null": len(numeric),
            "column": value_column
        }

        if numeric:
            result.update({
                "sum": round(sum(numeric), 2),
                "mean": round(statistics.mean(numeric), 2),
                "min": min(numeric),
                "max": max(numeric),
                "median": round(statistics.median(numeric), 2) if len(numeric) > 1 else numeric[0]
            })

        return result
