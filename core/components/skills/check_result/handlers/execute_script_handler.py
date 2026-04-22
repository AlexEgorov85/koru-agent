import re
import time
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, Literal
from pydantic import BaseModel

from core.components.action_executor import ExecutionContext
from core.models.data.execution import ExecutionStatus
from core.components.skills.handlers.base_handler import SkillHandler
from core.components.skills.utils.param_validator import ParamValidator


# =============================================================================
# ТИПИЗИРОВАННЫЕ МОДЕЛИ
# =============================================================================

@dataclass
class ParamDefinition:
    """Определение параметра скрипта"""
    type: Literal["like", "exact", "limit", "number", "date", "enum", "boolean"] = "exact"
    required: bool = False
    description: str = ""
    validation: Optional[Dict[str, Any]] = None


@dataclass
class ScriptDefinition:
    """Типизированное определение скрипта"""
    name: str
    description: str
    sql_template: str
    parameters: Dict[str, ParamDefinition] = field(default_factory=dict)
    max_rows_default: int = 50
    returns: str = ""
    long_description: str = ""


# =============================================================================
# ДИНАМИЧЕСКИЙ ПОСТРОИТЕЛЬ SQL С ШАБЛОНАМИ
# =============================================================================

class DynamicQueryBuilder:
    """Динамическая сборка SQL с Jinja2-подобными шаблонами"""

    @staticmethod
    def _render_template(sql_template: str, params: Dict[str, Any]) -> str:
        """Рендеринг шаблона: удаление {% if param %}...{% endif %} если параметр пустой"""
        result = sql_template
        
        # Паттерн для {% if param_name %} ... {% endif %}
        # Учитывает if, elif, и вложенные условия
        pattern = r'\{%\s*if\s+(\w+)\s*%\}(.*?)\{%\s*endif\s*%\}'
        
        def replace_if_block(match):
            param_name = match.group(1)
            content = match.group(2)
            
            if param_name in params and params[param_name] is not None:
                value = params[param_name]
                # Проверяем непустые значения
                if isinstance(value, str) and not value.strip():
                    return ""
                # Для boolean True - включаем блок
                if isinstance(value, bool) and value:
                    # Удаляем {% if param %} и {% else %} из контента
                    rendered = re.sub(r'\{%.*?else.*?%\}', '', content, flags=re.DOTALL)
                    rendered = rendered.strip()
                    return rendered
                # Для не-boolean значений - включаем если есть
                if not isinstance(value, bool):
                    # Также удаляем else
                    rendered = re.sub(r'\{%.*?else.*?%\}', '', content, flags=re.DOTALL)
                    rendered = rendered.strip()
                    return rendered
            return ""
        
        # Применяем несколько проходов для вложенных условий
        prev_result = None
        while prev_result != result:
            prev_result = result
            result = re.sub(pattern, replace_if_block, result, flags=re.DOTALL)
        
        # Удаляем пустые строки и отступы
        lines = result.split('\n')
        cleaned_lines = []
        for line in lines:
            stripped = line.strip()
            if stripped:
                cleaned_lines.append(stripped)
        result = '\n'.join(cleaned_lines)
        
        # Заменяем WHERE 1=1 AND -> WHERE
        result = re.sub(r'\bWHERE\s+1=1\s+AND\b', 'WHERE', result, flags=re.IGNORECASE)
        # Заменяем WHERE 1=1 в конце -> удаляем WHERE
        result = re.sub(r'\bWHERE\s+1=1\s*$', '', result, flags=re.IGNORECASE)
        # Заменяем AND в начале условий (если WHERE было удалено)
        result = re.sub(r'\bWHERE\s+AND\b', 'WHERE', result, flags=re.IGNORECASE)
        
        return result

    @staticmethod
    def build(
        script: ScriptDefinition,
        params: Dict[str, Any]
    ) -> tuple[str, Dict[str, Any]]:
        """Подготовка SQL и параметров - форматирование значений + рендеринг шаблона"""
        clean_params: Dict[str, Any] = {}
        
        # Сначала обрабатываем параметры
        for param_name, param_def in script.parameters.items():
            value = params.get(param_name)

            if value is None or (isinstance(value, str) and not value.strip()):
                if not param_def.required:
                    continue
                raise ValueError(f"Обязательный параметр '{param_name}' отсутствует")

            formatted_value = value

            if param_def.type == "like" and isinstance(value, str):
                if "%" not in value:
                    formatted_value = f"%{value}%"
            elif param_def.type == "limit":
                clean_params["max_rows"] = int(value) if value else script.max_rows_default
                continue
            elif param_def.type == "boolean":
                clean_params[param_name] = bool(value)
                continue
            elif param_def.type == "number":
                clean_params[param_name] = int(value) if value else None
                continue

            clean_params[param_name] = formatted_value

        # Рендерим шаблон
        final_sql = DynamicQueryBuilder._render_template(script.sql_template, clean_params)

        # Гарантируем наличие max_rows
        if "max_rows" not in clean_params:
            clean_params["max_rows"] = script.max_rows_default
            if ":max_rows" not in final_sql:
                final_sql += " LIMIT :max_rows"

        return final_sql, clean_params


# =============================================================================
# РЕЕСТР СКРИПТОВ (УНИФИЦИРОВАННЫЙ)
# =============================================================================

SCRIPTS_REGISTRY: Dict[str, ScriptDefinition] = {
    # ==========================================
    # 1. АУДИТЫ (Унифицированный поиск)
    # ==========================================
    "get_audits": ScriptDefinition(
        name="get_audits",
        description="Поиск аудиторских проверок с комбинированными фильтрами",
        returns="id, название, тип, даты, статус, объект проверки",
        long_description="Универсальный поиск проверок. Поддерживает любые комбинации фильтров: по статусу, типу, датам, объекту проверки.",
        sql_template='''
            SELECT id, title, audit_type, planned_date, actual_date, status, auditee_entity
            FROM oarb.audits
            WHERE 1=1
            {% if status %} AND status ILIKE :status {% endif %}
            {% if audit_type %} AND audit_type ILIKE :audit_type {% endif %}
            {% if date_from %} AND planned_date >= :date_from {% endif %}
            {% if date_to %} AND planned_date <= :date_to {% endif %}
            {% if auditee_entity %} AND auditee_entity ILIKE :auditee_entity {% endif %}
            ORDER BY planned_date DESC
        ''',
        parameters={
            "status": ParamDefinition(
                type="like",
                required=False,
                description="Статус проверки",
                validation={"type": "enum", "allowed_values": ["Планируется", "В работе", "Завершена", "Отменена"]}
            ),
            "audit_type": ParamDefinition(
                type="like",
                required=False,
                description="Тип проверки"
            ),
            "date_from": ParamDefinition(
                type="date",
                required=False,
                description="Дата планирования от"
            ),
            "date_to": ParamDefinition(
                type="date",
                required=False,
                description="Дата планирования до"
            ),
            "auditee_entity": ParamDefinition(
                type="like",
                required=False,
                description="Проверяемый объект"
            ),
            "max_rows": ParamDefinition(type="limit", required=False)
        },
        max_rows_default=50
    ),

    # ==========================================
    # 2. ОТЧЁТЫ (Акты проверок)
    # ==========================================
    "get_audit_reports": ScriptDefinition(
        name="get_audit_reports",
        description="Акты аудиторских проверок по ID проверки или статусу",
        returns="id акта, номер, дата, название, полный текст",
        long_description="Получение актов проверки. Можно фильтровать по ID проверки или статусу акта.",
        sql_template='''
            SELECT ar.id, ar.report_number, ar.report_date, ar.title, ar.full_text
            FROM oarb.audit_reports ar
            WHERE 1=1
            {% if audit_id %} AND ar.audit_id = :audit_id {% endif %}
            {% if status %} AND ar.status ILIKE :status {% endif %}
            {% if date_from %} AND ar.report_date >= :date_from {% endif %}
            ORDER BY ar.report_date DESC
        ''',
        parameters={
            "audit_id": ParamDefinition(
                type="number",
                required=False,
                description="ID проверки"
            ),
            "status": ParamDefinition(
                type="like",
                required=False,
                description="Статус акта"
            ),
            "date_from": ParamDefinition(
                type="date",
                required=False,
                description="Дата акта от"
            ),
            "max_rows": ParamDefinition(type="limit", required=False)
        },
        max_rows_default=50
    ),

    "get_report_items": ScriptDefinition(
        name="get_report_items",
        description="Пункты акта проверки с фильтрацией",
        returns="id пункта, номер, название, содержание, порядок",
        long_description="Получение пунктов (нарушений) из акта. Фильтрация по ID акта или статусу пункта.",
        sql_template='''
            SELECT id, item_number, item_title, item_content, order_index, status
            FROM oarb.report_items
            WHERE 1=1
            {% if report_id %} AND report_id = :report_id {% endif %}
            {% if status %} AND status ILIKE :status {% endif %}
            ORDER BY order_index
        ''',
        parameters={
            "report_id": ParamDefinition(
                type="number",
                required=False,
                description="ID акта"
            ),
            "status": ParamDefinition(
                type="like",
                required=False,
                description="Статус пункта"
            ),
            "max_rows": ParamDefinition(type="limit", required=False)
        },
        max_rows_default=50
    ),

    # ==========================================
    # 3. ОТКЛОНЕНИЯ (Полная унификация)
    # ==========================================
    "get_violations": ScriptDefinition(
        name="get_violations",
        description="Универсальный поиск отклонений с комбинированными фильтрами",
        returns="id, код, описание, рекомендация, критичность, статус, ответственный, срок, название проверки",
        long_description="Универсальный поиск отклонений. Заменяет все отдельные скрипты: by_status, by_severity, by_responsible, by_audit, overdue. Поддерживает любые комбинации фильтров.",
        sql_template='''
            SELECT v.id, v.violation_code, v.description, v.recommendation,
                   v.severity, v.status, v.responsible, v.deadline,
                   a.title as audit_title, a.status as audit_status
            FROM oarb.violations v
            JOIN oarb.audits a ON v.audit_id = a.id
            WHERE 1=1
            {% if audit_id %} AND v.audit_id = :audit_id {% endif %}
            {% if status %} AND v.status ILIKE :status {% endif %}
            {% if severity %} AND v.severity = :severity {% endif %}
            {% if responsible %} AND v.responsible ILIKE :responsible {% endif %}
            {% if deadline_from %} AND v.deadline >= :deadline_from {% endif %}
            {% if deadline_to %} AND v.deadline <= :deadline_to {% endif %}
            {% if is_overdue %} AND v.deadline < CURRENT_DATE AND v.status != 'Устранено' {% endif %}
            {% if violation_code %} AND v.violation_code ILIKE :violation_code {% endif %}
            ORDER BY 
                CASE v.severity WHEN 'Высокая' THEN 1 WHEN 'Средняя' THEN 2 ELSE 3 END,
                v.deadline ASC
        ''',
        parameters={
            "audit_id": ParamDefinition(
                type="number",
                required=False,
                description="ID проверки"
            ),
            "status": ParamDefinition(
                type="like",
                required=False,
                description="Статус отклонения",
                validation={"type": "enum", "allowed_values": ["Открыто", "В работе", "Устранено", "На проверке"]}
            ),
            "severity": ParamDefinition(
                type="exact",
                required=False,
                description="Критичность",
                validation={"type": "enum", "allowed_values": ["Высокая", "Средняя", "Низкая"]}
            ),
            "responsible": ParamDefinition(
                type="like",
                required=False,
                description="Ответственный"
            ),
            "deadline_from": ParamDefinition(
                type="date",
                required=False,
                description="Дедлайн от"
            ),
            "deadline_to": ParamDefinition(
                type="date",
                required=False,
                description="Дедлайн до"
            ),
            "is_overdue": ParamDefinition(
                type="boolean",
                required=False,
                description="Только просроченные"
            ),
            "violation_code": ParamDefinition(
                type="like",
                required=False,
                description="Код нарушения"
            ),
            "max_rows": ParamDefinition(type="limit", required=False)
        },
        max_rows_default=50
    ),

    # ==========================================
    # 4. АНАЛИТИКА
    # ==========================================
    "get_audit_statistics": ScriptDefinition(
        name="get_audit_statistics",
        description="Агрегированная статистика по проверкам и отклонениям",
        returns="id проверки, название, статус, кол-во актов, пунктов, отклонений, открытых, просроченных",
        long_description="Агрегированная статистика. Показывает общее количество отклонений по проверкам с разбивкой по статусам и критичности.",
        sql_template='''
            SELECT
                a.id as audit_id, a.title, a.status,
                COUNT(DISTINCT ar.id) as reports_count,
                COUNT(DISTINCT ri.id) as items_count,
                COUNT(DISTINCT v.id) as violations_count,
                COUNT(DISTINCT CASE WHEN v.severity = 'Высокая' THEN v.id END) as high_sev,
                COUNT(DISTINCT CASE WHEN v.severity = 'Средняя' THEN v.id END) as med_sev,
                COUNT(DISTINCT CASE WHEN v.severity = 'Низкая' THEN v.id END) as low_sev,
                COUNT(DISTINCT CASE WHEN v.status = 'Открыто' THEN v.id END) as open_viol,
                COUNT(DISTINCT CASE WHEN v.status = 'Устранено' THEN v.id END) as resolved_viol,
                COUNT(DISTINCT CASE WHEN v.deadline < CURRENT_DATE AND v.status != 'Устранено' THEN v.id END) as overdue_viol
            FROM oarb.audits a
            LEFT JOIN oarb.audit_reports ar ON a.id = ar.audit_id
            LEFT JOIN oarb.report_items ri ON ar.id = ri.report_id
            LEFT JOIN oarb.violations v ON a.id = v.audit_id
            WHERE 1=1
            {% if status %} AND a.status ILIKE :status {% endif %}
            {% if date_from %} AND a.planned_date >= :date_from {% endif %}
            GROUP BY a.id, a.title, a.status
            ORDER BY a.planned_date DESC
        ''',
        parameters={
            "status": ParamDefinition(
                type="like",
                required=False,
                description="Статус проверки"
            ),
            "date_from": ParamDefinition(
                type="date",
                required=False,
                description="Период от"
            ),
            "max_rows": ParamDefinition(type="limit", required=False)
        },
        max_rows_default=50
    ),

    "get_violations_timeline": ScriptDefinition(
        name="get_violations_timeline",
        description="Динамика появления отклонений по дням",
        returns="дата, общее кол-во, кол-во открытых",
        long_description="Показывает динамику появления отклонений по дням. Полезно для анализа трендов.",
        sql_template='''
            SELECT 
                DATE_TRUNC('day', v.created_at)::date as date,
                COUNT(*) as total_count,
                COUNT(CASE WHEN v.status = 'Открыто' THEN 1 END) as open_count
            FROM oarb.violations v
            WHERE 1=1
            {% if date_from %} AND v.created_at >= :date_from {% endif %}
            {% if date_to %} AND v.created_at <= :date_to {% endif %}
            GROUP BY DATE_TRUNC('day', v.created_at)
            ORDER BY date ASC
        ''',
        parameters={
            "date_from": ParamDefinition(
                type="date",
                required=False,
                description="Дата от"
            ),
            "date_to": ParamDefinition(
                type="date",
                required=False,
                description="Дата до"
            ),
            "max_rows": ParamDefinition(type="limit", required=False)
        },
        max_rows_default=50
    ),
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

        script_def = SCRIPTS_REGISTRY[script_name]
        sql_template = script_def.sql_template

        if not sql_template:
            raise ValueError(f"Скрипт '{script_name}' не имеет SQL запроса")

        # Преобразуем Pydantic в dict
        if hasattr(script_params, 'model_dump'):
            params_dict = script_params.model_dump()
        elif hasattr(script_params, 'dict'):
            params_dict = script_params.dict()
        else:
            params_dict = script_params or {}

        # Этап 2: Валидация параметров через ParamValidator (4 ступени: Enum → SQL → Vector → Fuzzy)
        validation_config = {}
        for param_name, param_def in script_def.parameters.items():
            if param_def.validation:
                validation_config[param_name] = param_def.validation

        validation_result = await self._param_validator.validate_multiple(
            params_dict,
            validation_config
        )

        # Валидация НЕ БЛОКИРУЕТ — только warnings
        warnings = validation_result.get("warnings", [])
        if warnings:
            for warning in warnings:
                await self.log_info(f"⚠️ Валидация: {warning}")

            suggestions = validation_result.get("suggestions", {})
            if suggestions:
                for param_name, sugg_list in suggestions.items():
                    if sugg_list:
                        await self.log_info(f"💡 Возможно вы имели в виду ({param_name}): {', '.join(sugg_list)}")

        # Этап 3: Применение автокоррекции
        corrected_params = validation_result.get("corrected_params", {})
        if corrected_params:
            params_dict.update(corrected_params)

        # Этап 4: Подготовка параметров + динамическая сборка SQL
        if 'max_rows' not in params_dict:
            params_dict['max_rows'] = max_rows

        final_sql, db_params = DynamicQueryBuilder.build(script_def, params_dict)

        # Этап 5: Выполнение SQL
        rows, execution_time = await self._execute_sql(final_sql, db_params)

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

    async def _execute_sql(self, sql: str, sql_params: Dict[str, Any]) -> tuple:
        """Выполнение SQL запроса"""
        exec_context = ExecutionContext()

        result = await self.executor.execute_action(
            action_name="service.sql_query_service.execute_query",
            parameters={
                "sql_query": sql,
                "parameters": sql_params,
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


def get_all_scripts() -> Dict[str, ScriptDefinition]:
    """Получение всех скриптов"""
    return SCRIPTS_REGISTRY