import time
from typing import Dict, Any

from core.models.data.execution import ExecutionStatus
from core.errors.exceptions import SQLGenerationError
from core.services.skills.handlers.base_handler import BaseSkillHandler


class SearchBooksHandler(BaseSkillHandler):
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

    # Конфигурация таблиц для SQL генерации
    DEFAULT_SCHEMA = "Lib"
    TABLES = ["books", "authors"]

    async def execute(self, params: Dict[str, Any]) -> Any:
        """
        Выполнение динамического поиска книг.

        ARGS:
        - params: входные параметры (query, max_results)

        RETURNS:
        - Pydantic модель или dict с результатами поиска
        """
        start_time = time.time()
        await self.log_info(f"Запуск динамического поиска книг: {params}")

        # 1. Валидация и извлечение параметров
        query_val, max_results_val = self._extract_params(params)

        # 2. Получение промпта для генерации SQL
        prompt_obj = self.get_prompt()
        prompt_text = prompt_obj.content if prompt_obj else ""
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
                f"1) В базе нет данных по запросу '{query_val[:100]}', "
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
            sql_query = data_dict.get('generated_sql', '') if isinstance(data_dict, dict) else getattr(result.data, 'generated_sql', '')
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
        schema_name = self.DEFAULT_SCHEMA
        tables = self.TABLES

        try:
            table_service = self.skill.table_description_service_instance
            if table_service:
                tables_metadata = await table_service.get_tables_structure(
                    table_list=tables,
                    schema_name=schema_name
                )

                if tables_metadata:
                    schema_parts = []
                    for key, metadata in tables_metadata.items():
                        schema_parts.append(self._format_table_metadata(metadata))

                    if schema_parts:
                        return "\n\n".join(schema_parts)

        except Exception as e:
            await self.log_warning(f"Не удалось получить схему из сервиса: {e}")

        return self._get_default_schema()

    def _format_table_metadata(self, metadata: Dict[str, Any]) -> str:
        """Форматирование метаданных таблицы в строку для LLM"""
        schema_name = metadata.get("schema_name", "public")
        table_name = metadata.get("table_name", "unknown")
        description = metadata.get("description", "")
        columns = metadata.get("columns", [])

        cols_str = []
        for col in columns:
            col_name = col.get("column_name", "")
            data_type = col.get("data_type", "unknown")
            nullable = "NOT NULL" if col.get("is_nullable") == "NO" else ""
            default = f"DEFAULT {col.get('column_default')}" if col.get("column_default") else ""
            cols_str.append(f"{col_name} {data_type} {nullable} {default}".strip())

        result = f'"{schema_name}"."{table_name}" (\n'
        result += ",\n".join(f"    {c}" for c in cols_str)
        result += "\n)"
        if description:
            result += f" -- {description}"
        return result

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
