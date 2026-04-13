import time
from typing import Dict, Any, List
from pydantic import BaseModel

from core.agent.components.action_executor import ExecutionContext
from core.models.data.execution import ExecutionStatus
from core.components.skills.handlers.base_handler import SkillHandler
from core.components.skills.utils.param_validator import ParamValidator


SCRIPTS_REGISTRY: Dict[str, Dict[str, Any]] = {
    "get_all_audits": {
        "description": "Получить все аудиторские проверки",
        "name": "get_all_audits",
        "sql": '''
            SELECT id, title, audit_type, planned_date, actual_date, status, auditee_entity
            FROM audits
            ORDER BY planned_date DESC
            LIMIT %s
        ''',
        "required_parameters": [],
        "optional_parameters": [],
    },
    "get_audit_by_status": {
        "description": "Получить проверки по статусу",
        "name": "get_audit_by_status",
        "sql": '''
            SELECT id, title, audit_type, planned_date, actual_date, status, auditee_entity
            FROM audits
            WHERE status ILIKE %s
            ORDER BY planned_date DESC
            LIMIT %s
        ''',
        "required_parameters": ["status"],
        "optional_parameters": [],
        "param_types": {
            "status": "like"
        },
        "param_descriptions": {
            "status": "Статус проверки: 'В работе', 'Завершена', 'Отменена' и т.д."
        },
        "validation": {
            "status": {
                "table": "audits",
                "search_fields": ["status"],
                "vector_source": "audits",
            }
        }
    },
    "get_audit_reports": {
        "description": "Получить акты аудиторской проверки по ID проверки",
        "name": "get_audit_reports",
        "sql": '''
            SELECT ar.id, ar.report_number, ar.report_date, ar.title, ar.full_text
            FROM audit_reports ar
            WHERE ar.audit_id = %s
            ORDER BY ar.report_date DESC
            LIMIT %s
        ''',
        "required_parameters": ["audit_id"],
        "optional_parameters": [],
    },
    "get_report_items": {
        "description": "Получить пункты акта по ID акта",
        "name": "get_report_items",
        "sql": '''
            SELECT id, item_number, item_title, item_content, order_index
            FROM report_items
            WHERE report_id = %s
            ORDER BY order_index
            LIMIT %s
        ''',
        "required_parameters": ["report_id"],
        "optional_parameters": [],
    },
    "get_violations_by_audit": {
        "description": "Получить все отклонения по проверке",
        "name": "get_violations_by_audit",
        "sql": '''
            SELECT v.id, v.violation_code, v.description, v.recommendation,
                   v.severity, v.status, v.responsible, v.deadline
            FROM violations v
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
        "required_parameters": ["audit_id"],
        "optional_parameters": [],
    },
    "get_violations_by_status": {
        "description": "Получить отклонения по статусу",
        "name": "get_violations_by_status",
        "sql": '''
            SELECT v.id, v.violation_code, v.description, v.recommendation,
                   v.severity, v.status, v.responsible, v.deadline,
                   a.title as audit_title
            FROM violations v
            JOIN audits a ON v.audit_id = a.id
            WHERE v.status ILIKE %s
            ORDER BY
                CASE v.severity
                    WHEN 'Высокая' THEN 1
                    WHEN 'Средняя' THEN 2
                    WHEN 'Низкая' THEN 3
                END
            LIMIT %s
        ''',
        "required_parameters": ["status"],
        "optional_parameters": [],
        "param_types": {
            "status": "like"
        },
        "validation": {
            "status": {
                "table": "violations",
                "search_fields": ["status"],
                "vector_source": "violations",
            }
        }
    },
    "get_violations_by_severity": {
        "description": "Получить отклонения по уровню критичности",
        "name": "get_violations_by_severity",
        "sql": '''
            SELECT v.id, v.violation_code, v.description, v.recommendation,
                   v.severity, v.status, v.responsible, v.deadline,
                   a.title as audit_title
            FROM violations v
            JOIN audits a ON v.audit_id = a.id
            WHERE v.severity ILIKE %s
            ORDER BY v.created_at DESC
            LIMIT %s
        ''',
        "required_parameters": ["severity"],
        "optional_parameters": [],
        "param_types": {
            "severity": "like"
        },
        "validation": {
            "severity": {
                "table": "violations",
                "search_fields": ["severity"],
                "vector_source": "violations",
            }
        }
    },
    "get_overdue_violations": {
        "description": "Получить просроченные отклонения (deadline < текущей даты)",
        "name": "get_overdue_violations",
        "sql": '''
            SELECT v.id, v.violation_code, v.description, v.recommendation,
                   v.severity, v.status, v.responsible, v.deadline,
                   a.title as audit_title,
                   CURRENT_DATE - v.deadline AS days_overdue
            FROM violations v
            JOIN audits a ON v.audit_id = a.id
            WHERE v.deadline < CURRENT_DATE
              AND v.status != 'Устранено'
            ORDER BY days_overdue DESC, v.severity DESC
            LIMIT %s
        ''',
        "required_parameters": [],
        "optional_parameters": [],
    },
    "get_violations_by_responsible": {
        "description": "Получить отклонения по ответственному лицу",
        "name": "get_violations_by_responsible",
        "sql": '''
            SELECT v.id, v.violation_code, v.description, v.recommendation,
                   v.severity, v.status, v.responsible, v.deadline,
                   a.title as audit_title
            FROM violations v
            JOIN audits a ON v.audit_id = a.id
            WHERE v.responsible ILIKE %s
            ORDER BY v.deadline
            LIMIT %s
        ''',
        "required_parameters": ["responsible"],
        "optional_parameters": [],
        "param_types": {
            "responsible": "like"
        },
        "validation": {
            "responsible": {
                "table": "violations",
                "search_fields": ["responsible"],
                "vector_source": "violations",
            }
        }
    },
    "get_audit_statistics": {
        "description": "Получить статистику по проверкам и отклонениям",
        "name": "get_audit_statistics",
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
            FROM audits a
            LEFT JOIN audit_reports ar ON a.id = ar.audit_id
            LEFT JOIN report_items ri ON ar.id = ri.report_id
            LEFT JOIN violations v ON a.id = v.audit_id
            GROUP BY a.id, a.title, a.status
            ORDER BY a.planned_date DESC
            LIMIT %s
        ''',
        "required_parameters": [],
        "optional_parameters": [],
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
            schema=None,  # Схема не указывается, т.к. таблицы в public
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
        script_params = params.parameters if hasattr(params, 'parameters') else {}
        max_rows = params.max_rows if hasattr(params, 'max_rows') else 50

        await self.log_info(f"Запуск выполнения скрипта: {script_name}")

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

        # Этап 2: Валидация параметров через ParamValidator (3 ступени)
        validation_config = script_config.get("validation", {})
        validation_result = await self._param_validator.validate_multiple(
            params_dict, 
            validation_config
        )
        
        if validation_result.get("warning"):
            await self.log_info(f"✏️ Валидация: {validation_result['warning']}")
        
        if not validation_result["valid"]:
            warning = validation_result.get("warning", "Валидация не прошла")
            suggestions = validation_result.get("suggestions", [])
            if suggestions:
                raise ValueError(f"Параметры невалидны: {warning}. Возможно вы имели в виду: {', '.join(suggestions)}")
            else:
                raise ValueError(f"Параметры невалидны: {warning}")

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
        result_data = {
            "rows": rows,
            "rowcount": len(rows),
            "execution_time": total_time,
            "execution_type": "static",
            "script_name": script_name,
            "warning": validation_result.get("warning") or ("Результатов не найдено" if not rows else None)
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
        required = script_config.get("required_parameters", [])
        optional = script_config.get("optional_parameters", [])
        param_types = script_config.get("param_types", {})
        all_params = [p for p in required + optional if p != "max_rows"]

        sql_params_list = []
        for param_name in all_params:
            if param_name in script_params:
                value = script_params[param_name]
                param_type = param_types.get(param_name, "like")
                if param_type == "like" and isinstance(value, str) and '%' not in value:
                    value = f'%{value}%'
                sql_params_list.append(value)

        sql_params_list.append(script_params.get("max_rows", 50))
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
            rows = result.data.rows if hasattr(result.data, 'rows') else []
            exec_time = result.data.execution_time if hasattr(result.data, 'execution_time') else 0.0
            return rows, exec_time
        else:
            raise RuntimeError(f"Ошибка выполнения SQL: {result.error}")


def get_all_scripts() -> Dict[str, Dict[str, Any]]:
    """Получение всех скриптов"""
    return SCRIPTS_REGISTRY