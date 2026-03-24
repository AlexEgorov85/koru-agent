import time
from typing import Dict, Any, List, Optional
from pydantic import BaseModel

from core.application.agent.components.action_executor import ExecutionContext
from core.models.data.execution import ExecutionStatus
from .base_handler import BaseBookLibraryHandler


class ExecuteScriptHandler(BaseBookLibraryHandler):
    """
    Обработчик выполнения заготовленных SQL-скриптов.

    RESPONSIBILITIES:
    - Валидация и выполнение статических скриптов
    - Проверка разрешённых скриптов
    - Преобразование параметров для SQL

    CAPABILITY:
    - book_library.execute_script
    """

    capability_name = "book_library.execute_script"

    async def execute(self, params: Dict[str, Any]) -> Any:
        """
        Выполнение статического скрипта.

        ARGS:
        - params: входные параметры (script_name, ...)

        RETURNS:
        - Pydantic модель или dict с результатами выполнения
        """
        start_time = time.time()
        await self.log_info(f"Запуск статического скрипта: {params}")

        # 1. Извлечение параметров
        script_name, max_rows = self._extract_params(params)

        # 2. Проверка что скрипт существует
        allowed_scripts = self._get_allowed_scripts()
        if script_name not in allowed_scripts:
            available_scripts = list(allowed_scripts.keys())
            raise ValueError(f"Скрипт '{script_name}' не найден. Доступные: {available_scripts}")

        # 3. Получение конфигурации скрипта
        script_config = allowed_scripts[script_name]
        sql_query = script_config['sql']

        # 4. Подготовка параметров для SQL
        script_params = self._prepare_script_params(params, script_config, max_rows)
        sql_params_list = self._convert_to_sql_params(script_params, script_config, max_rows)

        # 5. Выполнение SQL
        rows, execution_time = await self._execute_sql(sql_query, sql_params_list)

        # 6. Формирование результата
        total_time = time.time() - start_time
        result_data = {
            "rows": rows,
            "rowcount": len(rows),
            "execution_time": total_time,
            "execution_type": "static",
            "script_name": script_name
        }

        # 7. Публикация метрик
        await self.publish_metrics(
            success=True,
            execution_time_ms=total_time * 1000,
            execution_type="static",
            rows_returned=len(rows),
            script_name=script_name
        )

        # 8. Валидация через выходной контракт
        return self._validate_output(result_data)

    def _extract_params(self, params: Dict[str, Any]) -> tuple:
        """
        Извлечение параметров script_name и max_rows.

        ARGS:
        - params: входные параметры

        RETURNS:
        - tuple: (script_name, max_rows)
        """
        if isinstance(params, dict):
            script_name = params.get('script_name')
            max_rows = params.get('max_rows', 100)
        else:
            script_name = getattr(params, 'script_name', None)
            max_rows = getattr(params, 'max_rows', 100)

        if not script_name:
            raise ValueError("Требуется параметр 'script_name'")

        return script_name, max_rows

    def _get_allowed_scripts(self) -> Dict[str, Dict[str, Any]]:
        """Получение реестра разрешённых скриптов"""
        if self.skill._scripts_registry:
            return {name: config.to_dict() for name, config in self.skill._scripts_registry.items()}
        return self.skill._get_allowed_scripts()

    def _prepare_script_params(
        self,
        params: Dict[str, Any],
        script_config: Dict[str, Any],
        max_rows: int
    ) -> Dict[str, Any]:
        """
        Подготовка параметров для скрипта.

        ARGS:
        - params: входные параметры
        - script_config: конфигурация скрипта
        - max_rows: максимальное количество строк

        RETURNS:
        - dict: параметры для SQL
        """
        script_params = {}

        if isinstance(params, dict):
            script_params = params.copy()
            script_params.pop('script_name', None)
        elif hasattr(params, 'model_dump'):
            script_params = params.model_dump()
            script_params.pop('script_name', None)
        elif hasattr(params, 'parameters'):
            script_params = getattr(params, 'parameters', {})
            if hasattr(script_params, 'model_dump'):
                script_params = script_params.model_dump()

        # Добавляем max_rows
        if isinstance(params, dict) and 'max_rows' in params:
            script_params['max_rows'] = params['max_rows']
        elif hasattr(params, 'max_rows'):
            max_rows_val = getattr(params, 'max_rows')
            if max_rows_val is not None:
                script_params['max_rows'] = max_rows_val
        else:
            script_params['max_rows'] = max_rows

        # Проверка обязательных параметров
        required_params = script_config.get('required_parameters', [])
        missing_params = set(required_params) - set(script_params.keys())
        if missing_params:
            raise ValueError(f"Отсутствуют обязательные параметры: {missing_params}")

        return script_params

    def _convert_to_sql_params(
        self,
        script_params: Dict[str, Any],
        script_config: Dict[str, Any],
        max_rows: int
    ) -> List[Any]:
        """
        Преобразование именованных параметров в позиционные для PostgreSQL.

        ARGS:
        - script_params: параметры скрипта
        - script_config: конфигурация скрипта
        - max_rows: максимальное количество строк

        RETURNS:
        - list: позиционные параметры для psycopg2
        """
        required_params = script_config.get('required_parameters', [])
        optional_params = script_config.get('parameters', [])
        all_params = required_params + [p for p in optional_params if p not in required_params]

        sql_params_list = []

        for param_name in all_params:
            if param_name == 'max_rows':
                continue
            if param_name in script_params:
                param_value = script_params[param_name]
                # Для ILIKE параметров добавляем % если нет wildcard
                if param_name in ['author', 'title_pattern']:
                    if param_value and '%' not in param_value:
                        param_value = f'%{param_value}%'
                sql_params_list.append(param_value)

        sql_params_list.append(max_rows)
        return sql_params_list

    async def _execute_sql(self, sql: str, params: List[Any]) -> tuple:
        """
        Выполнение SQL запроса.

        ARGS:
        - sql: SQL запрос
        - params: позиционные параметры

        RETURNS:
        - tuple: (rows, execution_time)
        """
        rows = []
        execution_time = 0.0

        try:
            exec_context = ExecutionContext()
            result = await self.executor.execute_action(
                action_name="sql_query_service.execute_query",
                parameters={
                    "sql_query": sql,
                    "parameters": params
                },
                context=exec_context
            )

            if result.status == ExecutionStatus.COMPLETED and result.data:
                rows = result.data.rows if hasattr(result.data, 'rows') else []
                execution_time = result.data.execution_time if hasattr(result.data, 'execution_time') else 0.0
            else:
                error_msg = result.error if hasattr(result, 'error') else "Неизвестная ошибка"
                raise RuntimeError(f"Ошибка выполнения SQL: {error_msg}")

        except Exception as e:
            await self.log_error(f"Ошибка выполнения скрипта: {e}")
            raise

        return rows, execution_time

    def _validate_output(self, result: Dict[str, Any]) -> Any:
        """
        Валидация результата через выходной контракт.

        ARGS:
        - result: результат выполнения

        RETURNS:
        - Pydantic модель или dict
        """
        output_schema = self.get_output_schema()
        if output_schema:
            validated_result = output_schema.model_validate(result)
            return validated_result
        return result
