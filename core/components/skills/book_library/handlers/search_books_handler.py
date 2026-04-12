import time
from typing import Dict, Any
from pydantic import BaseModel

from core.models.data.execution import ExecutionStatus
from core.agent.components.action_executor import ExecutionContext
from core.errors.exceptions import SQLGenerationError
from core.components.skills.handlers.base_handler import SkillHandler


class SearchBooksHandler(SkillHandler):
    """
    Обработчик динамической генерации SQL через LLM.

    RESPONSIBILITIES:
    - Генерация SQL запроса на основе естественного языка
    - Валидация и выполнение сгенерированного SQL
    - Обработка пустых результатов

    CAPABILITY:
    - book_library.search_books
    """

    capability_name = "book_library.search_books"

    DEFAULT_SCHEMA = "Lib"
    TABLES = ["books", "authors"]

    async def _execute_impl(
        self,
        capability,
        parameters,
        execution_context=None
    ):
        """Делегирует execute() — обратная совместимость."""
        return await self.execute(parameters, execution_context)

    async def execute(self, params: BaseModel, execution_context: Any = None) -> BaseModel:
        """
        Выполнение динамического поиска книг.

        АРХИТЕКТУРА:
        - params: Pydantic модель из input_contract (уже валидировано)
        - execution_context: контекст выполнения

        RETURNS:
        - BaseModel: Pydantic модель выходного контракта
        """
        start_time = time.time()
        await self.log_info(f"Запуск динамического поиска книг: params={params}")

        query_val = params.query if hasattr(params, 'query') else ''
        max_results_val = params.max_results if hasattr(params, 'max_results') else 10

        # 2. Получение промпта для генерации SQL
        prompt_obj = self.component_config.resolved_prompts.get(self.capability_name)
        prompt_text = prompt_obj.content if prompt_obj else None
        if not prompt_text:
            raise ValueError("Промпт для поиска книг не найден")

        # 3. Генерация SQL через sql_generation сервис
        sql_query = await self._generate_sql(query_val)

        # 4. Выполнение SQL через sql_query_service
        rows, execution_time = await self._execute_sql(sql_query, max_results_val)

        # 5. Обработка пустых результатов
        if not rows:
            await self.log_warning(
                f"⚠️ SQL запрос не вернул результатов. "
                f"Возможные причины: "
                f"1) В базе нет данных по запросу '{query_val}', "
                f"2) Ошибка в сгенерированном SQL, "
                f"3) База данных пуста"
            )

        # 6. Формирование результата
        total_time = time.time() - start_time
        result = {
            "rows": rows,
            "rowcount": len(rows),
            "execution_time": total_time,
            "execution_type": "dynamic",
            "sql_query": sql_query,
            "warning": "Результатов не найдено" if not rows else None
        }

        # 7. Публикация метрик
        await self.publish_metrics(
            success=True,
            execution_time_ms=total_time * 1000,
            execution_type="dynamic",
            rows_returned=len(rows)
        )

        # 8. Валидация через выходной контракт
        return self._validate_output(result)

    async def _generate_sql(self, query: str) -> str:
        """
        Генерация SQL запроса через LLM.

        ARGS:
        - query: запрос на естественном языке

        RETURNS:
        - str: сгенерированный SQL запрос

        RAISES:
        - SQLGenerationError: если генерация не удалась
        """
        exec_context = ExecutionContext()

        table_schema = await self._get_book_library_schema()

        result = await self.executor.execute_action(
            action_name="sql_generation.generate_query",
            parameters={
                "natural_language_query": query,
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

    async def _get_book_library_schema(self) -> str:
        """
        Получение схемы таблиц библиотеки через table_description_service.

        RETURNS:
        - str: отформатированная схема таблиц для LLM
        """
        tables_config = self.skill.get_tables_config()
        if tables_config:
            return await self.get_table_descriptions(tables_config, format_for_llm=True)
        
        return self._get_default_schema()

    def _get_default_schema(self) -> str:
        """Fallback: возвращает захардкоженную схему если сервис недоступен"""
        schema = self.DEFAULT_SCHEMA
        tables = self.TABLES

        schema_map = {
            "books": '''id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    author_id INTEGER REFERENCES "Lib".authors(id),
    isbn TEXT,
    publication_date DATE,
    genre TEXT''',
            "authors": '''id INTEGER PRIMARY KEY,
    first_name TEXT,
    last_name TEXT,
    birth_date DATE'''
        }

        schema_parts = []
        for table in tables:
            if table in schema_map:
                schema_parts.append(f'"{schema}"."{table}" (\n    {schema_map[table]}\n)')

        return ",\n\n".join(schema_parts)

    async def _execute_sql(self, sql_query: str, max_results: int = 100):
        """
        Выполнение сгенерированного SQL запроса.

        ARGS:
        - sql_query: SQL запрос для выполнения
        - max_results: максимальное количество результатов

        RETURNS:
        - tuple: (rows, execution_time)
        """
        exec_context = ExecutionContext()

        result = await self.executor.execute_action(
            action_name="sql_query_service.execute",
            parameters={
                "sql_query": sql_query,
                "max_rows": max_results
            },
            context=exec_context
        )

        if result.status == ExecutionStatus.COMPLETED and result.data:
            data = result.data
            rows = data.get("rows", []) if isinstance(data, dict) else getattr(data, "rows", [])
            exec_time = data.get("execution_time", 0) if isinstance(data, dict) else getattr(data, "execution_time", 0)
            return rows, exec_time
        else:
            raise SQLGenerationError(
                f"Ошибка выполнения SQL запроса: {result.error}",
                request=sql_query
            )
