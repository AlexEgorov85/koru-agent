import time
from typing import Dict, Any, List, Optional
from pydantic import BaseModel

from core.agent.components.action_executor import ExecutionContext
from core.models.data.execution import ExecutionStatus
from core.components.skills.handlers.base_handler import SkillHandler
from core.components.skills.utils.param_validator import ParamValidator


# =============================================================================
# КОНФИГУРАЦИЯ СКРИПТА
# =============================================================================
# 
# Полная структура скрипта:
# ```python
# {
#     "description": "Описание скрипта для LLM",  # Обязательно
#     "sql": "SELECT ... WHERE status = %s",       # Обязательно
#     
#     # ПАРАМЕТРЫ (обязательные + опциональные в одном месте)
#     "parameters": {
#         "status": {                    # Имя параметра
#             "type": "like",             # "like" = ILIKE %value% (по умолч), "exact" = точное сравнение
#             "required": True,           # Обязательный? По умолч. False
#             "description": "Статус...", # Подсказка для LLM (попадает в промт)
#             "validation": {             # Валидация (опционально, для умной проверки)
#                 "table": "audits",      # Таблица для проверки
#                 "search_fields": ["status"],  # Поля для LIKE поиска
#                 "vector_source": "audits"    # Source для vector search
#             }
#         },
#         "max_rows": "limit"             # Специальный тип: "limit" = лимит результатов
#     }
# }
# ```
#
# СОКРАЩЁННАЯ ЗАПИСЬ (без валидации и описания):
#     "parameters": {"status": "like", "audit_id": "exact", "max_rows": "limit"}
#
# ТИПЫ ПАРАМЕТРОВ:
# - "like"     → ILIKE %value% (поиск по подстроке, с wildcards)
# - "exact"    → = value (точное равенство, без wildcards)
# - "limit"    → LIMIT value (число результатов, по умолч. 50)
# - None/unknown → treated as "exact" (для ID и числовых полей)
#
# ВАЖНО:
# - Параметры с type="like" автоматически обрамляются в % для SQL
# - Параметры с type="exact" передаются как есть
# - Параметр max_rows завёрнут в "limit" и не добавляет %


SCRIPTS_REGISTRY: Dict[str, Dict[str, Any]] = {
    "get_all_audits": {
        "description": "Список всех проверок (без фильтрации)",
        "returns": "id, название, тип, даты, статус, объект проверки",
        "long_description": "Возвращает ВСЕ проверки без фильтрации. Подходит когда пользователь спрашивает 'покажи все проверки', 'список проверок' без уточнений.",
        "sql": '''
            SELECT id, title, audit_type, planned_date, actual_date, status, auditee_entity
            FROM oarb.audits
            ORDER BY planned_date DESC
            LIMIT %s
        ''',
        "parameters": {
            "max_rows": "limit"
        }
    },
    "get_audit_by_status": {
        "description": "Проверки с фильтром по статусу",
        "returns": "id, название, тип, даты, статус, объект проверки",
        "long_description": "ТОЛЬКО если пользователь ЯВНО указал статус в запросе: 'завершенные проверки', 'проверки в работе', 'отмененные проверки'. Не используй если статус не упомянут.",
        "sql": '''
            SELECT id, title, audit_type, planned_date, actual_date, status, auditee_entity
            FROM oarb.audits
            WHERE status ILIKE %s
            ORDER BY planned_date DESC
            LIMIT %s
        ''',
        "parameters": {
            "status": {
                "type": "like",
                "required": True,
                "description": "Статус: 'В работе', 'Завершена', 'Отменена', 'Планируется'",
                "validation": {
                    "type": "enum",
                    "allowed_values": ["В работе", "Завершена", "Отменена", "Планируется"]
                }
            },
            "max_rows": "limit"
        }
    },
    "get_audit_reports": {
        "description": "Акты конкретной проверки по её ID",
        "returns": "id акта, номер, дата, название, полный текст",
        "long_description": "ТОЛЬКО если известен ID проверки и нужно получить её акты. Обычно используется после получения списка проверок.",
        "sql": '''
            SELECT ar.id, ar.report_number, ar.report_date, ar.title, ar.full_text
            FROM oarb.audit_reports ar
            WHERE ar.audit_id = %s
            ORDER BY ar.report_date DESC
            LIMIT %s
        ''',
        "parameters": {
            "audit_id": {
                "type": "exact",
                "required": True,
                "description": "ID проверки (число)"
            },
            "max_rows": "limit"
        }
    },
    "get_report_items": {
        "description": "Пункты конкретного акта по его ID",
        "returns": "id пункта, номер, название пункта, содержание, порядок",
        "long_description": "ТОЛЬКО если известен ID акта. Используется после получения актов проверки.",
        "sql": '''
            SELECT id, item_number, item_title, item_content, order_index
            FROM oarb.report_items
            WHERE report_id = %s
            ORDER BY order_index
            LIMIT %s
        ''',
        "parameters": {
            "report_id": {
                "type": "exact",
                "required": True,
                "description": "ID акта (число)"
            },
            "max_rows": "limit"
        }
    },
    "get_violations_by_audit": {
        "description": "Все отклонения конкретной проверки по ID",
        "returns": "id, код, описание, рекомендация, критичность, статус, ответственный, срок",
        "long_description": "ТОЛЬКО если известен ID проверки. Возвращает отклонения отсортированные по критичности (Высокая→Средняя→Низкая).",
        "sql": '''
            SELECT v.id, v.violation_code, v.description, v.recommendation,
                   v.severity, v.status, v.responsible, v.deadline
            FROM oarb.violations v
            WHERE v.audit_id = %s
            ORDER BY
                CASE v.severity
                    WHEN 'Высокая' THEN 1
                    WHEN 'Средняя' THEN 2
                    WHEN 'Низкая' THEN 3
                END,
                v.created_at DESC
            LIMIT %s
        ''',
        "parameters": {
            "audit_id": {
                "type": "exact",
                "required": True,
                "description": "ID проверки (число)"
            },
            "max_rows": "limit"
        }
    },
    "get_violations_by_status": {
        "description": "Отклонения с фильтром по статусу",
        "returns": "id, код, описание, рекомендация, критичность, статус, ответственный, срок, название проверки",
        "long_description": "ТОЛЬКО если пользователь ЯВНО указал статус отклонения: 'открытые отклонения', 'устраненные нарушения', 'на проверке'. НЕ используй для общего списка отклонений.",
        "sql": '''
            SELECT v.id, v.violation_code, v.description, v.recommendation,
                   v.severity, v.status, v.responsible, v.deadline,
                   a.title as audit_title
            FROM oarb.violations v
            JOIN oarb.audits a ON v.audit_id = a.id
            WHERE v.status ILIKE %s
            ORDER BY
                CASE v.severity
                    WHEN 'Высокая' THEN 1
                    WHEN 'Средняя' THEN 2
                    WHEN 'Низкая' THEN 3
                END
            LIMIT %s
        ''',
        "parameters": {
            "status": {
                "type": "like",
                "required": True,
                "description": "Статус: 'Открыто', 'В работе', 'Устранено', 'На проверке'",
                "validation": {
                    "type": "enum",
                    "allowed_values": ["Открыто", "В работе", "Устранено", "На проверке"]
                }
            },
            "max_rows": "limit"
        }
    },
    "get_violations_by_severity": {
        "description": "Отклонения с фильтром по критичности",
        "returns": "id, код, описание, рекомендация, критичность, статус, ответственный, срок, название проверки",
        "long_description": "ТОЛЬКО если пользователь ЯВНО указал уровень критичности: 'высококритичные нарушения', 'средние отклонения'. НЕ используй для общего списка.",
        "sql": '''
            SELECT v.id, v.violation_code, v.description, v.recommendation,
                   v.severity, v.status, v.responsible, v.deadline,
                   a.title as audit_title
            FROM oarb.violations v
            JOIN oarb.audits a ON v.audit_id = a.id
            WHERE v.severity ILIKE %s
            ORDER BY v.created_at DESC
            LIMIT %s
        ''',
        "parameters": {
            "severity": {
                "type": "like",
                "required": True,
                "description": "Критичность: 'Высокая', 'Средняя', 'Низкая'",
                "validation": {
                    "type": "enum",
                    "allowed_values": ["Высокая", "Средняя", "Низкая"]
                }
            },
            "max_rows": "limit"
        }
    },
    "get_overdue_violations": {
        "description": "Просроченные отклонения (срок < сегодня)",
        "returns": "id, код, описание, рекомендация, критичность, статус, ответственный, срок, название проверки, дней просрочки",
        "long_description": "ТОЛЬКО если спрашивают про просроченные/просрочку/пропущенные сроки. Автоматически исключает устранённые. Сортировка: сначала самые просроченные.",
        "sql": '''
            SELECT v.id, v.violation_code, v.description, v.recommendation,
                   v.severity, v.status, v.responsible, v.deadline,
                   a.title as audit_title,
                   CURRENT_DATE - v.deadline AS days_overdue
            FROM oarb.violations v
            JOIN oarb.audits a ON v.audit_id = a.id
            WHERE v.deadline < CURRENT_DATE
              AND v.status != 'Устранено'
            ORDER BY days_overdue DESC, v.severity DESC
            LIMIT %s
        ''',
        "parameters": {
            "max_rows": "limit"
        }
    },
    "get_violations_by_responsible": {
        "description": "Отклонения конкретного ответственного",
        "returns": "id, код, описание, рекомендация, критичность, статус, ответственный, срок, название проверки",
        "long_description": "ТОЛЬКО если пользователь указал конкретного ответственного: 'нарушения Иванова', 'задачи Петровой'. Поддерживает частичный поиск по ФИО.",
        "sql": '''
            SELECT v.id, v.violation_code, v.description, v.recommendation,
                   v.severity, v.status, v.responsible, v.deadline,
                   a.title as audit_title
            FROM oarb.violations v
            JOIN oarb.audits a ON v.audit_id = a.id
            WHERE v.responsible ILIKE %s
            ORDER BY v.deadline
            LIMIT %s
        ''',
        "parameters": {
            "responsible": {
                "type": "like",
                "required": True,
                "description": "ФИО ответственного (частичный поиск)",
                "validation": {
                    "table": "violations",
                    "search_fields": ["responsible"],
                    "vector_source": "violations"
                }
            },
            "max_rows": "limit"
        }
    },
    "get_audit_statistics": {
        "description": "Статистика: количество проверок и отклонений",
        "returns": "id проверки, название, тип, общее число отклонений, из них открытых/высоких/средних/низких",
        "long_description": "ТОЛЬКО если спрашивают про статистику, количество, сводку, отчёты по проверкам. НЕ используй для получения детального списка нарушений.",
        "sql": '''
            SELECT
                a.id as audit_id,
                a.title as audit_title,
                a.status as audit_status,
                COUNT(DISTINCT ar.id) as reports_count,
                COUNT(DISTINCT ri.id) as items_count,
                COUNT(DISTINCT v.id) as violations_count,
                COUNT(DISTINCT CASE WHEN v.severity = 'Высокая' THEN v.id END) as high_severity_count,
                COUNT(DISTINCT CASE WHEN v.severity = 'Средняя' THEN v.id END) as medium_severity_count,
                COUNT(DISTINCT CASE WHEN v.severity = 'Низкая' THEN v.id END) as low_severity_count,
                COUNT(DISTINCT CASE WHEN v.status = 'Открыто' THEN v.id END) as open_violations_count,
                COUNT(DISTINCT CASE WHEN v.status = 'Устранено' THEN v.id END) as resolved_violations_count
            FROM oarb.audits a
            LEFT JOIN oarb.audit_reports ar ON a.id = ar.audit_id
            LEFT JOIN oarb.report_items ri ON ar.id = ri.report_id
            LEFT JOIN oarb.violations v ON a.id = v.audit_id
            GROUP BY a.id, a.title, a.status
            ORDER BY a.planned_date DESC
            LIMIT %s
        ''',
        "parameters": {
            "max_rows": "limit"
        }
    },
}


class ExecuteScriptHandler(SkillHandler):
    """
    Обработчик выполнения заготовленных скриптов проверки.

    RESPONSIBILITIES:
    - Поиск и выполнение заготовленного скрипта
    - Многоэтапная валидация параметров через ParamValidator (SQL → Vector → Fuzzy)
    - Обработка результатов

    CAPABILITY:
    - check_result.execute_script
    """

    capability_name = "check_result.execute_script"

    def __init__(self, skill):
        super().__init__(skill)
        self._param_validator = ParamValidator(
            executor=self.executor,
            schema="oarb",
            log_callback=self._log_debug
        )

    async def _log_debug(self, message: str):
        """Логирование для валидатора"""
        await self.log_debug(message)

    async def execute(self, params: BaseModel, execution_context: Any = None) -> BaseModel:
        """
        Выполнение заготовленного скрипта с многоэтапной валидацией.

        ЭТАПЫ:
        1. Проверка существования скрипта
        2. Валидация параметров через ParamValidator (3 ступени)
        3. Применение автокоррекции
        4. Подготовка параметров для SQL
        5. Выполнение SQL
        6. Публикация метрик
        """
        start_time = time.time()

        script_name = params.script_name if hasattr(params, 'script_name') else ''
        max_rows = params.max_rows if hasattr(params, 'max_rows') else 1000

        # Извлекаем параметры скрипта:
        # 1. Сначала пробуем params.parameters (если LLM обернул в parameters)
        # 2. Если пусто — берём все поля из params кроме script_name и max_rows
        if hasattr(params, 'parameters') and params.parameters:
            script_params = params.parameters
        else:
            # LLM передал параметры на верхнем уровне — извлекаем их
            script_params = {}
            if hasattr(params, 'model_dump'):
                all_fields = params.model_dump()
            elif hasattr(params, 'dict'):
                all_fields = params.dict()
            else:
                all_fields = {}
            for key, value in all_fields.items():
                if key not in ('script_name', 'max_rows') and value is not None:
                    script_params[key] = value

        await self.log_info(f"Запуск выполнения скрипта: {script_name}")
        await self.log_info(f"Параметры скрипта: {script_params}")

        # Этап 1: Проверка что скрипт существует
        if script_name not in SCRIPTS_REGISTRY:
            available_scripts = list(SCRIPTS_REGISTRY.keys())
            raise ValueError(f"Скрипт '{script_name}' не найден. Доступные: {available_scripts}")

        script_config = SCRIPTS_REGISTRY[script_name]
        sql_query = script_config.get("sql", "")

        if not sql_query:
            raise ValueError(f"Скрипт '{script_name}' не имеет SQL запроса")

        # Преобразуем Pydantic в dict
        if hasattr(script_params, 'model_dump'):
            params_dict = script_params.model_dump()
        elif hasattr(script_params, 'dict'):
            params_dict = script_params.dict()
        else:
            params_dict = script_params or {}

        # Этап 2: Валидация параметров через ParamValidator (4 ступени: Enum → SQL → Vector → Fuzzy)
        # Собираем validation конфиг из новой структуры parameters
        parameters = script_config.get("parameters", {})
        validation_config = {}
        for param_name, param_config in parameters.items():
            if isinstance(param_config, dict) and "validation" in param_config:
                validation_config[param_name] = param_config["validation"]

        validation_result = await self._param_validator.validate_multiple(
            params_dict,
            validation_config
        )

        # Валидация НЕ БЛОКИРУЕТ — только warnings
        warnings = validation_result.get("warnings", [])
        if warnings:
            for warning in warnings:
                await self.log_info(f"⚠️ Валидация: {warning}")

            # Добавляем suggestions в result (если есть)
            suggestions = validation_result.get("suggestions", {})
            if suggestions:
                for param_name, sugg_list in suggestions.items():
                    if sugg_list:
                        await self.log_info(f"💡 Возможно вы имели в виду ({param_name}): {', '.join(sugg_list)}")

        # Этап 3: Применение автокоррекции
        corrected_params = validation_result.get("corrected_params", {})
        if corrected_params:
            params_dict.update(corrected_params)

        # Этап 4: Подготовка параметров
        prepared_params = self._prepare_script_params(params_dict, script_config, max_rows)
        sql_params = self._convert_to_sql_params(prepared_params, script_config)

        # Этап 5: Выполнение SQL
        rows, execution_time = await self._execute_sql(sql_query, sql_params)

        total_time = time.time() - start_time
        # Собираем все warnings в одну строку
        validation_warnings = validation_result.get("warnings", [])
        warning_str = "; ".join(validation_warnings) if validation_warnings else None

        columns = list(rows[0].keys()) if rows else []
        
        result_data = {
            "rows": rows,
            "columns": columns,
            "rowcount": len(rows),
            "execution_time": total_time,
            "execution_type": "static",
            "script_name": script_name,
            "warning": warning_str or ("Результатов не найдено" if not rows else None)
        }

        # Этап 6: Публикация метрик
        await self.publish_metrics(
            success=True,
            execution_time_ms=total_time * 1000,
            execution_type="static",
            rows_returned=len(rows)
        )

        # Возвращаем dict — валидацию выполнит Component._validate_output()
        return result_data

    def _prepare_script_params(
        self,
        params: Dict[str, Any],
        script_config: Dict[str, Any],
        max_rows: int
    ) -> Dict[str, Any]:
        """Подготовка параметров для скрипта"""
        script_params = params.copy()
        script_params.pop('script_name', None)

        if 'max_rows' not in script_params:
            script_params['max_rows'] = max_rows

        return script_params

    def _convert_to_sql_params(
        self,
        script_params: Dict[str, Any],
        script_config: Dict[str, Any]
    ) -> List[Any]:
        """Преобразование именованных параметров в позиционные"""
        parameters = script_config.get("parameters", {})
        
        # Собираем все параметры кроме max_rows
        all_params = [p for p in parameters.keys() if p != "max_rows"]

        sql_params_list = []
        for param_name in all_params:
            if param_name in script_params:
                value = script_params[param_name]
                
                # Определяем тип параметра
                param_config = parameters.get(param_name, "exact")
                if isinstance(param_config, dict):
                    param_type = param_config.get("type", "exact")
                else:
                    # Сокращённая запись: "exact" или "like"
                    param_type = param_config if param_config else "exact"
                
                # Для like-параметров добавляем % если нет wildcard
                if param_type == "like" and isinstance(value, str) and '%' not in value:
                    value = f'%{value}%'
                
                sql_params_list.append(value)

        sql_params_list.append(script_params.get("max_rows", 1000))
        return sql_params_list

    async def _execute_sql(self, sql: str, sql_params: List[Any]) -> tuple:
        """Выполнение SQL запроса"""
        exec_context = ExecutionContext()

        result = await self.executor.execute_action(
            action_name="service.sql_query_service.execute_query",
            parameters={
                "sql_query": sql,
                "parameters": {str(i+1): val for i, val in enumerate(sql_params)},
                "max_rows": 1000
            },
            context=exec_context
        )

        if result.status == ExecutionStatus.COMPLETED and result.data:
            # result.data — это dict {"query_result": DBQueryResult, ...}
            if isinstance(result.data, dict):
                query_result = result.data.get("query_result")
                if hasattr(query_result, 'rows'):
                    rows = query_result.rows if query_result.rows else []
                    exec_time = query_result.execution_time if query_result.execution_time else 0.0
                    return rows, exec_time
            # Fallback: если вдруг напрямую DBQueryResult
            elif hasattr(result.data, 'rows'):
                rows = result.data.rows if result.data.rows else []
                exec_time = result.data.execution_time if result.data.execution_time else 0.0
                return rows, exec_time

        raise RuntimeError(f"Ошибка выполнения SQL: {result.error}")


def get_all_scripts() -> Dict[str, Dict[str, Any]]:
    """Получение всех скриптов"""
    return SCRIPTS_REGISTRY