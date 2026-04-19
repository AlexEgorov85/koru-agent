"""SQL recovery analyzer для диагностики пустых SQL-результатов.

АРХИТЕКТУРА:
- Выделен из AgentRuntime для соблюдения SRP.
- Содержит только эвристики анализа SQL и построения recovery-hints.
- Не зависит от инфраструктуры и может тестироваться изолированно.
"""

import re
from typing import Dict, List, Optional


class SQLRecoveryAnalyzer:
    """Анализатор пустых SQL-результатов и генератор подсказок."""

    def is_sql_action(self, action_name: Optional[str]) -> bool:
        """Проверка: действие относится к SQL-вызову."""
        return bool(action_name and "sql" in action_name)

    def analyze_empty_result(self, parameters: Optional[dict]) -> Dict[str, str]:
        """Сформировать универсальную подсказку для пустого SQL-результата."""
        params = parameters or {}
        query_candidate = params.get("query") or params.get("sql") or ""
        query_text = str(query_candidate).strip()

        if not query_text:
            return {
                "issues": ["sql_filter_mismatch"],
                "next_step_hint": (
                    "SQL вернул пусто: проверь таблицы/соединения и выполни "
                    "диагностический COUNT(*) без фильтров."
                ),
            }

        table_name = self._extract_table_name(query_text)
        where_clause = self._extract_where_clause(query_text)
        filter_conditions = self._extract_filter_conditions(where_clause)
        filter_columns = [item["column"] for item in filter_conditions]

        issues = ["sql_filter_mismatch"]
        if self._contains_year_like_filter(query_text, filter_columns):
            issues.append("sql_year_filter_mismatch")

        if filter_conditions and table_name:
            hint = self._build_filter_diagnostic_hint(table_name, filter_conditions)
        elif filter_columns:
            grouped_cols = ", ".join(filter_columns[:2])
            hint = (
                "SQL вернул пусто: проверь доступные значения по фильтрам "
                f"({grouped_cols}) через GROUP BY/COUNT и ослабь условия WHERE."
            )
        else:
            hint = (
                "SQL вернул пусто без явных фильтров: проверь JOIN-условия, "
                "источник таблиц и выполни COUNT(*) для базовой проверки наличия данных."
            )

        return {"issues": issues, "next_step_hint": hint}

    def _extract_table_name(self, query_text: str) -> Optional[str]:
        """Извлечь имя таблицы из FROM (эвристика для диагностических подсказок)."""
        match = re.search(r"\bfrom\s+([a-zA-Z0-9_\.]+)", query_text, re.IGNORECASE)
        return match.group(1) if match else None

    def _extract_where_clause(self, query_text: str) -> str:
        """Извлечь WHERE-клаузу до GROUP/ORDER/LIMIT (эвристика)."""
        match = re.search(
            r"\bwhere\b(.*?)(\bgroup\s+by\b|\border\s+by\b|\blimit\b|$)",
            query_text,
            re.IGNORECASE | re.DOTALL,
        )
        return match.group(1) if match else ""

    def _extract_filter_conditions(self, where_clause: str) -> List[Dict[str, str]]:
        """Извлечь фильтры WHERE с типом значения (string/number/date/unknown)."""
        if not where_clause:
            return []

        pattern = re.compile(
            r"([a-zA-Z_][a-zA-Z0-9_\.]*)\s*(=|!=|<>|>|<|>=|<=|like|ilike)\s*"
            r"('(?:[^']|''|\\')*'|\d+(?:\.\d+)?|\b\d{4}-\d{2}-\d{2}\b)",
            re.IGNORECASE,
        )
        conditions = []
        for match in pattern.finditer(where_clause):
            raw_column, operator, raw_value = match.groups()
            column = raw_column.split(".")[-1]
            value = raw_value.strip()
            value_type = self._infer_sql_value_type(value)
            conditions.append(
                {
                    "column": column,
                    "operator": operator.lower(),
                    "value": value,
                    "value_type": value_type,
                }
            )
        return conditions

    def _infer_sql_value_type(self, raw_value: str) -> str:
        """Эвристика типа значения фильтра."""
        value = raw_value.strip("'").strip()
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            return "date"
        if re.fullmatch(r"\d+(?:\.\d+)?", value):
            return "number"
        if value:
            return "string"
        return "unknown"

    def _build_filter_diagnostic_hint(
        self, table_name: str, filter_conditions: List[Dict[str, str]]
    ) -> str:
        """Собрать эффективную диагностику по первому фильтру."""
        first_condition = filter_conditions[0]
        column = first_condition["column"]
        value = first_condition["value"]
        value_type = first_condition["value_type"]

        if value_type == "string":
            value_literal = value if value.startswith("'") else f"'{value}'"
            prefix_value = value_literal.strip("'").replace("%", "").strip()
            prefix_literal = f"'{prefix_value}%'" if prefix_value else value_literal
            return (
                "SQL вернул пусто: не проверяй только точное совпадение строки. "
                f"Сделай 2 шага: (1) SELECT COUNT(*) FROM {table_name} WHERE LOWER(TRIM({column})) = LOWER(TRIM({value_literal})); "
                f"(2) SELECT DISTINCT {column} FROM {table_name} WHERE LOWER({column}) LIKE LOWER({prefix_literal}) LIMIT 20. "
                "Так ты найдёшь варианты написания/пробелы/регистр и скорректируешь фильтр."
            )

        if value_type == "number":
            return (
                "SQL вернул пусто: сначала проверь диапазон значений, затем точный фильтр. "
                f"SELECT MIN({column}), MAX({column}) FROM {table_name}; "
                f"SELECT {column}, COUNT(*) FROM {table_name} GROUP BY {column} ORDER BY {column} LIMIT 20."
            )

        if value_type == "date":
            return (
                "SQL вернул пусто: проверь диапазон дат и распределение по периодам. "
                f"SELECT MIN({column}), MAX({column}) FROM {table_name}; "
                f"SELECT DATE_TRUNC('month', {column}) AS m, COUNT(*) FROM {table_name} "
                "GROUP BY m ORDER BY m LIMIT 24."
            )

        grouped_cols = ", ".join([item["column"] for item in filter_conditions[:2]])
        return (
            "SQL вернул пусто: возможно, фильтры слишком узкие. "
            f"Сначала проверь доступные значения: SELECT {grouped_cols}, COUNT(*) "
            f"FROM {table_name} GROUP BY {grouped_cols} ORDER BY COUNT(*) DESC LIMIT 20; "
            "затем скорректируй условия WHERE."
        )

    def _contains_year_like_filter(
        self, query_text: str, filter_columns: List[str]
    ) -> bool:
        """Проверить, что в фильтрах есть годоподобный критерий."""
        lower_query = query_text.lower()
        has_year_keyword = any(
            token in lower_query
            for token in [" year", "год", "date_part('year", "extract(year"]
        )
        has_year_column = any(
            "year" in col.lower() or "год" in col.lower() for col in filter_columns
        )
        has_year_value = any(str(year) in lower_query for year in range(2000, 2036))
        return (has_year_keyword or has_year_column) and has_year_value
