"""
SQL Diagnostic Service — пост-обработчик пустых SQL-результатов.

АРХИТЕКТУРА:
- Выполняет диагностические запросы (COUNT, MIN/MAX, DISTINCT)
- Использует ParamValidator для fuzzy matching значений фильтров
- Возвращает структурированные подсказки для LLM
- Обработка синтаксических ошибок и таймаутов (Фаза 3)

ВЫЗОВ:
После выполнения SQL с rowcount=0 или ошибкой:
    diag_result = await sql_diagnostic.analyze_empty_result(sql_query, params)
    diag_result = await sql_diagnostic.analyze_error(sql_query, error_message)
"""

import re
from typing import Any, Dict, List, Optional, Literal

from core.components.action_executor import ExecutionContext
from core.components.skills.utils.param_validator import ParamValidator
from core.models.data.execution import ExecutionStatus, ExecutionResult


class SQLDiagnosticService:
    """
    Сервис диагностики SQL-ошибок и пустых результатов.

    ОБЪЕДИНЯЕТ:
    - Автоматические диагностические запросы (COUNT, MIN/MAX)
    - ParamValidator для fuzzy/enum matching значений фильтров
    - Анализ синтаксических ошибок и таймаутов (Фаза 3)
    """

    def __init__(self, executor):
        self.executor = executor
        self.param_validator = ParamValidator(executor=executor)

    async def analyze_empty_result(
        self,
        sql_query: str,
        original_params: Dict[str, Any],
        table_hint: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Анализирует пустой результат SQL и возвращает подсказки.

        ARGS:
        - sql_query: исходный SQL запрос
        - original_params: параметры запроса
        - table_hint: подсказка с именем таблицы (опционально)

        RETURNS:
        - Dict с ключами:
          - status: статус диагностики
          - hints: список подсказок для LLM
          - corrected_params: исправленные параметры
          - table_name: имя таблицы
          - total_count: общее количество записей
        """
        hints = []
        corrected_params = {}
        table_name = table_hint
        total_count = None

        if not sql_query:
            return {
                "status": "no_query",
                "hints": ["SQL запрос не передан для диагностики"],
                "corrected_params": {},
                "table_name": None,
                "total_count": None,
            }

        if not table_name:
            table_match = re.search(r"FROM\s+([^\s,]+)", sql_query, re.IGNORECASE)
            if table_match:
                table_name = table_match.group(1).strip()

        if not table_name:
            return {
                "status": "unknown_table",
                "hints": ["Не удалось определить таблицу для диагностики"],
                "corrected_params": {},
                "table_name": None,
                "total_count": None,
            }

        try:
            count_result = await self._execute_query(f"SELECT COUNT(*) as total FROM {table_name}")
            if count_result.get("rows"):
                total_count = count_result["rows"][0].get("total", 0)
                if total_count == 0:
                    hints.append(f"Таблица `{table_name}` пуста (0 записей)")
                    return {
                        "status": "empty_table",
                        "hints": hints,
                        "corrected_params": {},
                        "table_name": table_name,
                        "total_count": 0,
                    }
                else:
                    hints.append(f"В таблице `{table_name}` {total_count} записей")
        except Exception as e:
            hints.append(f"Не удалось проверить COUNT: {e}")

        where_match = re.search(
            r"WHERE\s+(.+?)(?:GROUP\s+BY|ORDER\s+BY|LIMIT|$)",
            sql_query,
            re.IGNORECASE | re.DOTALL,
        )

        if where_match:
            where_clause = where_match.group(1)
            conditions = re.split(r"\s+AND\s+", where_clause, flags=re.IGNORECASE)

            for cond in conditions[:2]:
                col_match = re.match(r"([a-zA-Z_][\w.]*)\s*[>=<!~]+", cond)
                if not col_match:
                    continue

                col_name = col_match.group(1).split(".")[-1]

                try:
                    range_result = await self._execute_query(
                        f'SELECT MIN("{col_name}") as min_val, MAX("{col_name}") as max_val FROM {table_name}'
                    )
                    if range_result.get("rows") and range_result["rows"][0].get("min_val") is not None:
                        row = range_result["rows"][0]
                        min_v, max_v = row.get("min_val"), row.get("max_val")
                        hints.append(f"Диапазон `{col_name}`: [{min_v} ... {max_v}]")
                except Exception:
                    pass

                param_key = self._find_param_key(col_name, original_params)
                if param_key and param_key in original_params:
                    raw_val = str(original_params[param_key])
                    validation = await self.param_validator.validate(
                        param_value=raw_val,
                        config={
                            "table": table_name.replace('"', "").replace("'", "").split(".")[-1],
                            "search_fields": [col_name],
                        },
                    )
                    if validation.get("corrected_value") and validation["corrected_value"] != raw_val:
                        corrected_params[param_key] = validation["corrected_value"]
                        hints.append(
                            f"Возможно, вы имели в виду: `{param_key}` = `{validation['corrected_value']}` "
                            f"(найдено через поиск в БД)"
                        )

                try:
                    distinct_result = await self._execute_query(
                        f'SELECT DISTINCT "{col_name}", COUNT(*) as cnt FROM {table_name} '
                        f'WHERE "{col_name}" IS NOT NULL GROUP BY "{col_name}" '
                        f"ORDER BY cnt DESC LIMIT 5"
                    )
                    if distinct_result.get("rows"):
                        values = [str(row.get(col_name, "")) for row in distinct_result["rows"]]
                        if values:
                            hints.append(f"Реальные значения `{col_name}`: {', '.join(values)}")
                except Exception:
                    pass

        if not hints:
            hints.append("Диагностика не выявила проблем. Проверь логику запроса.")

        return {
            "status": "diagnostic_complete",
            "hints": hints,
            "corrected_params": corrected_params,
            "table_name": table_name,
            "total_count": total_count,
        }

    async def _execute_query(self, sql: str) -> Dict[str, Any]:
        """Выполняет SQL запрос через executor."""
        ctx = ExecutionContext()
        try:
            res = await self.executor.execute_action(
                action_name="sql_tool.execute",
                parameters={"sql": sql, "max_rows": 10},
                context=ctx,
            )
            if res.status == ExecutionStatus.COMPLETED and res.data:
                data_dict = res.data.model_dump() if hasattr(res.data, "model_dump") else res.data
                return data_dict if isinstance(data_dict, dict) else {}
            return {}
        except Exception:
            return {}

    def _find_param_key(self, col_name: str, params: Dict[str, Any]) -> Optional[str]:
        """Находит ключ параметра, соответствующий колонке в WHERE."""
        col_base = col_name.lower().replace('"', "")

        for key in params:
            key_lower = key.lower().replace("_", "")
            col_check = col_base.replace("_", "")

            if key_lower == col_check or col_check in key_lower or key_lower in col_check:
                return key

            if "_id" in key_lower and col_check.endswith("_id"):
                return key
            if "_name" in key_lower and col_check.endswith("_name"):
                return key
            if "_date" in key_lower and col_check.endswith("_date"):
                return key
            if "_year" in key_lower and col_check.endswith("_year"):
                return key

        return None

    # ========================================================================
    # ERROR DIAGNOSTICS (Фаза 3)
    # ========================================================================

    async def analyze_error(
        self,
        sql_query: str,
        error_message: str,
        original_params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Анализирует ошибку выполнения SQL и возвращает рекомендации.
        
        ОБРАБАТЫВАЕТ:
        - SyntaxError: ошибки синтаксиса SQL
        - TimeoutError: превышение времени выполнения
        - OperationalError: проблемы с подключением/блокировками
        - Другие ошибки выполнения
        
        ПАРАМЕТРЫ:
        - sql_query: исходный SQL запрос
        - error_message: текст ошибки
        - original_params: параметры запроса (опционально)
        
        ВОЗВРАЩАЕТ:
        - Dict с ключами:
          - error_type: тип ошибки (syntax|timeout|operational|other)
          - hints: список рекомендаций для LLM
          - suggested_fix: предложенное исправление запроса
          - retry_possible: можно ли повторить с изменениями
        """
        hints = []
        suggested_fix = None
        retry_possible = False
        error_type = "other"
        
        # Нормализуем сообщение об ошибке
        error_lower = error_message.lower()
        
        # --------------------------------------------------------------------
        # Синтаксические ошибки
        # --------------------------------------------------------------------
        syntax_patterns = [
            r"syntax error",
            r"parse error",
            r"invalid sql",
            r"incorrect syntax",
            r"unexpected token",
            r"missing keyword",
        ]
        
        if any(re.search(pattern, error_lower) for pattern in syntax_patterns):
            error_type = "syntax"
            hints.append("Обнаружена синтаксическая ошибка в SQL запросе")
            
            # Эвристики для распространённых ошибок
            if "select*" in sql_query.replace(" ", ""):
                hints.append("Возможно, пропущен пробел между SELECT и *")
                suggested_fix = sql_query.replace("SELECT*", "SELECT *")
                retry_possible = True
            
            if re.search(r"FROM\s*,", sql_query, re.IGNORECASE):
                hints.append("Обнаружен устаревший стиль JOIN через запятую. Используйте явный JOIN")
            
            if re.search(r"WHERE\s+AND", sql_query, re.IGNORECASE):
                hints.append("Лишнее WHERE перед AND. Проверьте условия фильтрации")
                retry_possible = True
            
            if re.search(r"GROUP\s+BY\s*,", sql_query, re.IGNORECASE):
                hints.append("Лишняя запятая после GROUP BY")
            
            # Предлагаем использовать EXPLAIN для отладки
            hints.append("Используй EXPLAIN для анализа плана выполнения запроса")
            
            if sql_query and not sql_query.upper().startswith("EXPLAIN"):
                suggested_fix = f"EXPLAIN {sql_query}"
                retry_possible = True
        
        # --------------------------------------------------------------------
        # Таймауты
        # --------------------------------------------------------------------
        timeout_patterns = [
            r"timeout",
            r"timed out",
            r"execution time exceeded",
            r"query took too long",
            r"lock wait timeout",
        ]
        
        if any(re.search(pattern, error_lower) for pattern in timeout_patterns):
            error_type = "timeout"
            hints.append("Превышено время выполнения запроса")
            
            # Извлекаем таблицу из запроса
            table_match = re.search(r"FROM\s+([^\s,]+)", sql_query, re.IGNORECASE)
            if table_match:
                table_name = table_match.group(1)
                hints.append(f"Таблица `{table_name}` может содержать много данных")
            
            # Рекомендации по оптимизации
            hints.append("Добавь LIMIT для ограничения количества строк")
            hints.append("Проверь наличие индексов по полям в WHERE")
            hints.append("Избегай SELECT *, указывай конкретные колонки")
            
            # Предлагаем оптимизированный вариант
            if "LIMIT" not in sql_query.upper():
                suggested_fix = f"{sql_query.rstrip(';')} LIMIT 100"
                retry_possible = True
            
            if re.search(r"SELECT\s+\*", sql_query, re.IGNORECASE):
                hints.append("Замени SELECT * на конкретные колонки для ускорения")
        
        # --------------------------------------------------------------------
        # Операционные ошибки (блокировки, подключения)
        # --------------------------------------------------------------------
        operational_patterns = [
            r"connection",
            r"locked",
            r"deadlock",
            r"cannot connect",
            r"access denied",
            r"permission denied",
        ]
        
        if any(re.search(pattern, error_lower) for pattern in operational_patterns):
            error_type = "operational"
            hints.append("Операционная ошибка: проблема с подключением или блокировкой")
            
            if "lock" in error_lower or "deadlock" in error_lower:
                hints.append("Таблица заблокирована другой транзакцией")
                hints.append("Повтори запрос через несколько секунд")
                retry_possible = True
            
            if "permission" in error_lower or "access denied" in error_lower:
                hints.append("Недостаточно прав для выполнения операции")
                hints.append("Проверь права доступа к таблице")
        
        # --------------------------------------------------------------------
        # Общие рекомендации
        # --------------------------------------------------------------------
        if not hints:
            hints.append("Не удалось определить конкретную причину ошибки")
            hints.append("Проверь логи базы данных для детальной информации")
        
        # Всегда предлагаем упростить запрос как fallback
        if not suggested_fix and sql_query:
            # Упрощаем: убираем JOIN, оставляем только базовый SELECT
            simple_select = re.search(
                r"SELECT\s+(.+?)\s+FROM\s+(\w+)",
                sql_query,
                re.IGNORECASE,
            )
            if simple_select:
                columns, table = simple_select.groups()
                suggested_fix = f"SELECT {columns} FROM {table} LIMIT 10"
                retry_possible = True
                hints.append("Попробуй упрощённую версию запроса без JOIN и подзапросов")
        
        return {
            "status": "error_diagnosed",
            "error_type": error_type,
            "original_error": error_message,
            "hints": hints,
            "suggested_fix": suggested_fix,
            "retry_possible": retry_possible,
            "table_name": self._extract_table_name(sql_query),
        }

    def _extract_table_name(self, sql_query: str) -> Optional[str]:
        """Извлекает имя таблицы из SQL запроса."""
        if not sql_query:
            return None
        
        # Основная таблица из FROM
        table_match = re.search(r"FROM\s+([^\s,(]+)", sql_query, re.IGNORECASE)
        if table_match:
            return table_match.group(1).strip('"').strip("'")
        
        return None
