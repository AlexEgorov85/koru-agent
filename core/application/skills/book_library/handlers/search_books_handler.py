import time
from typing import Dict, Any, Optional
from pydantic import BaseModel

from core.application.agent.components.action_executor import ExecutionContext
from core.models.data.execution import ExecutionStatus
from core.errors.exceptions import SQLGenerationError
from .base_handler import BaseBookLibraryHandler


class SearchBooksHandler(BaseBookLibraryHandler):
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

    async def _extract_params(self, params: Dict[str, Any]) -> tuple:
        """
        Извлечение и валидация параметров.

        ARGS:
        - params: входные параметры (dict или Pydantic модель)

        RETURNS:
        - tuple: (query, max_results)
        """
        if isinstance(params, BaseModel):
            query_val = getattr(params, 'query', '')
            max_results_val = getattr(params, 'max_results', 10)
        else:
            input_schema = self.get_input_schema()
            if input_schema:
                try:
                    validated_params = input_schema.model_validate(params)
                    params = validated_params
                    query_val = getattr(params, 'query', '')
                    max_results_val = getattr(params, 'max_results', 10)
                except Exception as e:
                    await self.log_error(f"Ошибка валидации параметров: {e}")
                    raise ValueError(f"Неверные параметры: {str(e)}")
            else:
                await self.log_error("Контракт book_library.search_books.input не загружен в кэш")
                raise ValueError("Внутренняя ошибка: контракт не загружен")

        return query_val, max_results_val

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

        result = await self.executor.execute_action(
            action_name="sql_generation.generate_query",
            parameters={
                "natural_language_query": query,
                "table_schema": """
                    "Lib".books (
                        id INTEGER PRIMARY KEY,
                        title TEXT NOT NULL,
                        author_id INTEGER REFERENCES "Lib".authors(id),
                        isbn TEXT,
                        publication_date DATE,
                        genre TEXT
                    ),
                    "Lib".authors (
                        id INTEGER PRIMARY KEY,
                        first_name TEXT,
                        last_name TEXT,
                        birth_date DATE
                    )
                """.strip()
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

    async def _execute_sql(self, sql: str, max_rows: int) -> tuple:
        """
        Выполнение SQL запроса.

        ARGS:
        - sql: SQL запрос
        - max_rows: максимальное количество строк

        RETURNS:
        - tuple: (rows, execution_time)
        """
        rows = []
        execution_time = 0.0

        try:
            exec_context = ExecutionContext()
            result = await self.executor.execute_action(
                action_name="sql_query.execute",
                parameters={
                    "sql": sql,
                    "parameters": {},
                    "max_rows": max_rows
                },
                context=exec_context
            )

            if result.status == ExecutionStatus.COMPLETED and result.data:
                rows = result.data.rows if hasattr(result.data, 'rows') else []
                execution_time = result.data.execution_time if hasattr(result.data, 'execution_time') else 0.0
                await self.log_info(f"Найдено строк: {len(rows)}")
            else:
                raise RuntimeError(f"Ошибка выполнения SQL: {result.error}")

        except Exception as e:
            await self.log_error(f"Ошибка выполнения SQL: {e}")
            raise RuntimeError(f"Ошибка выполнения SQL запроса: {e}")

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
