import time
from typing import Dict, Any, List
from pydantic import BaseModel

from core.agent.components.action_executor import ExecutionContext
from core.models.data.execution import ExecutionStatus
from core.components.skills.handlers.base_handler import SkillHandler
from core.components.skills.utils.param_validator import ParamValidator


SCRIPTS_REGISTRY: Dict[str, Dict[str, Any]] = {
    "get_all_books": {
        "description": "Получить все книги из библиотеки",
        "name": "get_all_books",
        "sql": 'SELECT * FROM "Lib".books ORDER BY id LIMIT %s',
        "required_parameters": [],
        "optional_parameters": [],
    },
    "get_books_by_author": {
        "description": "Получить книги по автору",
        "name": "get_books_by_author",
        "sql": '''
            SELECT b.*, a.first_name, a.last_name 
            FROM "Lib".books b 
            JOIN "Lib".authors a ON b.author_id = a.id 
            WHERE a.last_name ILIKE %s OR a.first_name ILIKE %s
            ORDER BY b.title 
            LIMIT %s
        ''',
        "required_parameters": ["author"],
        "optional_parameters": [],
        "validation": {
            "author": {
                "table": "authors",
                "search_fields": ["first_name", "last_name"],
                "vector_source": "authors",
            }
        }
    },
    "count_books": {
        "description": "Посчитать количество книг",
        "name": "count_books",
        "sql": 'SELECT COUNT(*) as total FROM "Lib".books',
        "required_parameters": [],
        "optional_parameters": [],
    },
    "get_books_by_year_range": {
        "description": "Получить книги за период",
        "name": "get_books_by_year_range",
        "sql": '''
            SELECT * FROM "Lib".books 
            WHERE publication_year >= %s AND publication_year <= %s
            ORDER BY publication_year
            LIMIT %s
        ''',
        "required_parameters": [],
        "optional_parameters": ["year_from", "year_to"],
    },
    "get_books_by_genre": {
        "description": "Получить книги по жанру",
        "name": "get_books_by_genre",
        "sql": '''
            SELECT b.*, g.name as genre_name
            FROM "Lib".books b 
            JOIN "Lib".book_genres bg ON b.id = bg.book_id 
            JOIN "Lib".genres g ON bg.genre_id = g.id 
            WHERE g.name ILIKE %s
            ORDER BY b.title 
            LIMIT %s
        ''',
        "required_parameters": ["genre"],
        "optional_parameters": [],
        "validation": {
            "genre": {
                "table": "genres",
                "search_fields": ["name"],
                "vector_source": "genres",
            }
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
            schema="Lib",
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

        output_schema = self.get_output_schema()
        if output_schema:
            return output_schema.model_validate(result_data)

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
        all_params = [p for p in required + optional if p != "max_rows"]

        sql_params_list = []
        for param_name in all_params:
            if param_name in script_params:
                value = script_params[param_name]
                if isinstance(value, str) and '%' not in value:
                    value = f'%{value}%'
                sql_params_list.append(value)

        sql_params_list.append(script_params.get("max_rows", 50))
        return sql_params_list

    async def _execute_sql(self, sql: str, sql_params: List[Any]) -> tuple:
        """Выполнение SQL запроса"""
        exec_context = ExecutionContext()

        result = await self.executor.execute_action(
            action_name="sql_query.execute",
            parameters={"sql": sql, "parameters": sql_params},
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