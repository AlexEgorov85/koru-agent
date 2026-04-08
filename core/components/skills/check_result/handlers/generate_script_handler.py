import time
import os
import yaml
from typing import Dict, Any, List, Optional
from pydantic import BaseModel

from core.models.data.execution import ExecutionStatus
from core.agent.components.action_executor import ExecutionContext
from core.errors.exceptions import SQLGenerationError
from core.components.skills.handlers.base_handler import BaseSkillHandler


TABLES_CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
    "data", "skills", "check_result", "tables.yaml"
)


class GenerateScriptHandler(BaseSkillHandler):
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
        self._tables_config: Optional[List[Dict[str, str]]] = None

    async def _load_tables_config(self) -> List[Dict[str, str]]:
        """Загрузка конфигурации таблиц из YAML файла"""
        if self._tables_config is not None:
            return self._tables_config

        if os.path.exists(TABLES_CONFIG_PATH):
            with open(TABLES_CONFIG_PATH, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                self._tables_config = config.get('tables', [])
                await self.log_info(f"Загружена конфигурация таблиц из файла: {len(self._tables_config)} таблиц")
        else:
            await self.log_warning(f"Файл конфигурации таблиц не найден: {TABLES_CONFIG_PATH}")
            self._tables_config = []

        return self._tables_config

    async def execute(self, params: BaseModel, execution_context: Any = None) -> BaseModel:
        """
        Генерация и выполнение SQL скрипта.

        АРХИТЕКТУРА:
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

        sql_query = await self._generate_sql(query, table_schema)

        rows, execution_time = await self._execute_sql(sql_query, max_results)

        if not rows:
            await self.log_warning(
                f"⚠️ SQL запрос не вернул результатов. "
                f"Возможные причины: "
                f"1) В базе нет данных по запросу '{query}', "
                f"2) Ошибка в сгенерированном SQL, "
                f"3) База данных пуста"
            )

        total_time = time.time() - start_time
        result_data = {
            "rows": rows,
            "rowcount": len(rows),
            "execution_time": total_time,
            "execution_type": "dynamic",
            "sql_query": sql_query,
            "warning": "Результатов не найдено" if not rows else None
        }

        await self.publish_metrics(
            success=True,
            execution_time_ms=total_time * 1000,
            execution_type="dynamic",
            rows_returned=len(rows)
        )

        output_schema = self.get_output_schema()
        if output_schema:
            return output_schema.model_validate(result_data)

        return result_data

    async def _get_schema(self) -> str:
        """Получение схемы таблиц"""
        tables_config = await self._load_tables_config()

        if not tables_config:
            return self._get_default_schema()

        tables_list = [f"{t['schema']}.{t['table']}" for t in tables_config]

        try:
            exec_context = ExecutionContext()
            result = await self.executor.execute_action(
                action_name="table_description_service.execute",
                parameters={
                    "table_list": [t['table'] for t in tables_config],
                    "schema_name": tables_config[0].get('schema', 'public')
                },
                context=exec_context
            )

            if result.status == ExecutionStatus.COMPLETED and result.data:
                tables_metadata = result.data
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
        """Fallback: возвращает схему из конфигурации"""
        return 'Таблицы из конфигурации: см. tables.yaml'

    async def _generate_sql(self, query: str, table_schema: str) -> str:
        """Генерация SQL запроса через LLM"""
        exec_context = ExecutionContext()

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