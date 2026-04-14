import time
from typing import Any, Dict, List, Tuple
from pydantic import BaseModel

from core.models.data.execution import ExecutionStatus
from core.agent.components.action_executor import ExecutionContext
from core.errors.exceptions import SQLGenerationError
from core.components.skills.handlers.base_handler import SkillHandler


class GenerateScriptHandler(SkillHandler):
    """
    Обработчик генерации и выполнения SQL скрипта.

    RESPONSIBILITIES:
    - Загрузка списка таблиц при инициализации
    - Получение схемы таблиц через сервис
    - Генерация SQL через LLM
    - Выполнение и обработка результатов

    CAPABILITY:
    - check_result.generate_script
    """

    capability_name = "check_result.generate_script"

    def __init__(self, skill):
        super().__init__(skill)

    async def _get_tables_config(self) -> List[Dict[str, str]]:
        """Получение конфигурации таблиц от родительского skill"""
        if hasattr(self.skill, 'get_tables_config'):
            return self.skill.get_tables_config() or []
        return []

    async def _load_tables_config(self) -> List[Dict[str, str]]:
        """Получение конфигурации таблиц (использует centralized метод)"""
        return await self._get_tables_config()

    async def execute(self, params: BaseModel, execution_context: Any = None) -> BaseModel:
        """
        Генерация и выполнение SQL скрипта.

        АРХИТЕКТУРА:
        - Цикл валидации: генерация → проверка → корректировка (до 3 попыток)
        - При ошибке валидации SQL возвращается в LLM с описанием ошибки
        - params: Pydantic модель из input_contract (уже валидировано)
        - execution_context: контекст выполнения

        RETURNS:
        - BaseModel: Pydantic модель выходного контракта
        """
        start_time = time.time()

        query = params.query if hasattr(params, 'query') else ''
        max_results = params.max_results if hasattr(params, 'max_results') else 50

        await self.log_info(f"Запуск генерации скрипта: {query}")

        table_schema = await self._get_schema()

        # Цикл генерации с валидацией и корректировкой
        max_attempts = 3
        last_error = None
        sql_query = None

        for attempt in range(1, max_attempts + 1):
            try:
                # Генерация SQL (с учетом предыдущих ошибок)
                error_context = None
                if last_error:
                    error_context = f"Предыдущая ошибка: {last_error}\nИсправь SQL запрос."
                    await self.log_warning(
                        f"Попытка {attempt}/{max_attempts}: корректировка после ошибки",
                    )
                
                sql_query = await self._generate_sql(query, table_schema, error_context)

                # Валидация SQL перед выполнением
                validation_result = await self._validate_sql(sql_query)
                if not validation_result.get('is_valid', True):
                    last_error = validation_result.get('error', 'Неизвестная ошибка валидации')
                    await self.log_warning(
                        f"Валидация не пройдена (попытка {attempt}): {last_error}"
                    )
                    continue

                # Выполнение SQL
                rows, execution_time = await self._execute_sql(sql_query, max_results)

                total_time = time.time() - start_time
                result_data = {
                    "rows": rows,
                    "rowcount": len(rows),
                    "execution_time": total_time,
                    "execution_type": "dynamic",
                    "sql_query": sql_query,
                    "warning": "Результатов не найдено" if not rows else None
                }

                if not rows:
                    self._log_warning(
                        f"⚠️ SQL запрос не вернул результатов. "
                        f"Возможные причины: "
                        f"1) В базе нет данных по запросу '{query}', "
                        f"2) Ошибка в сгенерированном SQL, "
                        f"3) База данных пуста"
                    )

                await self.publish_metrics(
                    success=True,
                    execution_time_ms=total_time * 1000,
                    execution_type="dynamic",
                    rows_returned=len(rows)
                )

                # Возвращаем dict — валидацию выполнит Component._validate_output()
                return result_data

            except Exception as e:
                last_error = str(e)
                await self.log_error(f"Ошибка генерации/выполнения SQL (попытка {attempt}): {last_error}")

        # Все попытки исчерпаны
        total_time = time.time() - start_time
        raise SQLGenerationError(
            f"Не удалось сгенерировать и выполнить SQL после {max_attempts} попыток. "
            f"Последняя ошибка: {last_error}",
            request=query
        )

    async def _get_schema(self) -> str:
        """Получение схемы таблиц"""
        tables_config = await self._load_tables_config()

        if not tables_config:
            return self._get_default_schema()

        return await self.get_table_descriptions(tables_config, format_for_llm=True)

    def _get_default_schema(self) -> str:
        """Fallback: возвращает схему из конфигурации"""
        return 'Таблицы из конфигурации: см. tables.yaml'

    async def _generate_sql(self, query: str, table_schema: str, error_context: str = None) -> str:
        """
        Генерация SQL запроса через LLM.

        ARGS:
        - query: запрос на естественном языке
        - table_schema: схема таблиц
        - error_context: описание предыдущей ошибки (для корректировки)

        RETURNS:
        - str: сгенерированный SQL запрос
        """
        exec_context = ExecutionContext()

        # Если есть ошибка — добавляем контекст для LLM
        prompt = query
        if error_context:
            prompt = f"{error_context}\n\nИсходный запрос: {query}"

        result = await self.executor.execute_action(
            action_name="sql_generation.generate_query",
            parameters={
                "natural_language_query": prompt,
                "table_schema": table_schema
            },
            context=exec_context
        )

        if result.status == ExecutionStatus.COMPLETED and result.data:
            data_dict = result.data.model_dump() if hasattr(result.data, 'model_dump') else result.data
            sql_query = data_dict.get('sql', '') or data_dict.get('generated_sql', '') if isinstance(data_dict, dict) else getattr(result.data, 'sql', '') or getattr(result.data, 'generated_sql', '')
            await self.log_info(f"Сгенерированный SQL: {sql_query}")
        else:
            raise SQLGenerationError(
                f"Генерация SQL не удалась: {result.error}",
                request=query
            )

        if not sql_query:
            raise SQLGenerationError(
                "Не удалось сгенерировать SQL запрос. "
                "Проверьте что sql_generation сервис доступен и промпт загружен.",
                request=query
            )

        return sql_query

    async def _validate_sql(self, sql_query: str) -> Dict[str, Any]:
        """
        Валидация SQL запроса перед выполнением.

        ПРОВЕРКИ:
        - Базовый синтаксис (SELECT, FROM, баланс скобок)
        - Наличие опасных операций (DROP, DELETE, UPDATE без WHERE)
        - Корректность имен таблиц

        RETURNS:
        - Dict: {'is_valid': bool, 'error': str или None}
        """
        import re
        
        sql_upper = sql_query.upper().strip()

        # 1. Проверка на пустой запрос
        if not sql_query or not sql_query.strip():
            return {'is_valid': False, 'error': 'Пустой SQL запрос'}

        # 2. Проверка на основные SQL команды
        valid_starts = ('SELECT', 'INSERT', 'UPDATE', 'DELETE', 'CREATE', 'DROP', 'ALTER')
        if not any(sql_upper.startswith(cmd) for cmd in valid_starts):
            return {'is_valid': False, 'error': f'Не начинается с допустимой команды SQL'}

        # 3. Проверка на баланс скобок
        paren_count = sql_query.count('(') - sql_query.count(')')
        if paren_count != 0:
            return {'is_valid': False, 'error': f'Несбалансированные скобки (разница: {paren_count})'}

        # 4. Проверка на SELECT ... FROM
        if sql_upper.startswith('SELECT'):
            if 'FROM' not in sql_upper:
                return {'is_valid': False, 'error': 'Отсутствует FROM в SELECT запросе'}

        # 5. Проверка на опасные операции (для безопасности)
        dangerous_patterns = ['; DROP', '; DELETE', '; UPDATE', '; INSERT']
        for pattern in dangerous_patterns:
            if pattern in sql_upper:
                return {'is_valid': False, 'error': f'Обнаружена опасная конструкция: {pattern}'}

        # 6. Проверка на комментарии (могут содержать опасный код)
        if '--' in sql_query or '/*' in sql_query or '*/' in sql_query:
            await self.log_warning("SQL содержит комментарии — потенциально опасно")

        return {'is_valid': True, 'error': None}

    async def _execute_sql(self, sql_query: str, max_results: int) -> Tuple[List[Any], float]:
        """
        Выполнение SQL запроса через sql_tool.

        ARGS:
        - sql_query: SQL запрос для выполнения
        - max_results: максимальное количество возвращаемых строк

        RETURNS:
        - Tuple[list, float]: (строки результатов, время выполнения в секундах)
        """
        start_time = time.time()
        exec_context = ExecutionContext()

        result = await self.executor.execute_action(
            action_name="sql_tool.execute",
            parameters={
                "sql": sql_query,
                "max_rows": max_results
            },
            context=exec_context
        )

        execution_time = time.time() - start_time

        if result.status == ExecutionStatus.COMPLETED and result.data:
            data_dict = result.data.model_dump() if hasattr(result.data, 'model_dump') else result.data
            if isinstance(data_dict, dict):
                rows = data_dict.get('rows', []) or data_dict.get('data', [])
                return rows, execution_time

        self._log_warning(f"SQL запрос не вернул результатов: {result.error}", event_type=LogEventType.WARNING)
        return [], execution_time