"""
Инструмент для выполнения SQL-запросов с поддержкой изолированных кэшей и sandbox режима.

АРХИТЕКТУРА:
- Stateless: получает DB провайдер из application_context при каждом вызове
- Использует изолированные кэши, предзагруженные через ComponentConfig
- Поддержка sandbox режима для безопасного выполнения запросов
"""
import time
from dataclasses import dataclass
from typing import Dict, Optional, Any

from core.components.tools.tool import Tool, ToolInput, ToolOutput
from core.application_context.application_context import ApplicationContext
from core.config.component_config import ComponentConfig
from core.models.enums.common_enums import ResourceType
from core.infrastructure.logging.event_types import LogEventType


@dataclass
class SQLToolInput(ToolInput):
    sql: str
    parameters: Optional[dict] = None
    max_rows: int = 1000


@dataclass
class SQLToolOutput(ToolOutput):
    rows: list
    columns: list
    rowcount: int
    execution_time: float


class SQLTool(Tool):
    """Инструмент для выполнения SQL-запросов с четким контрактом и поддержкой изолированных кэшей."""

    @property
    def description(self) -> str:
        return "Выполнение SQL-запросов к базе данных с поддержкой изолированных кэшей и sandbox режима"

    def __init__(
        self,
        name: str,
        component_config: ComponentConfig,
        executor,
        application_context: Optional[ApplicationContext] = None
    ):
        super().__init__(
            name=name,
            component_config=component_config,
            executor=executor,
            application_context=application_context
        )

    async def initialize(self) -> bool:
        """Инициализация инструмента (не требует подключения к БД)."""
        result = await super().initialize()
        return result

    async def shutdown(self) -> None:
        """Корректное завершение работы (базовая реализация)."""
        self._log_debug(f"Завершение работы для инструмента {self.name}", event_type=LogEventType.DEBUG)

    def _is_write_query(self, sql: str) -> bool:
        """Проверяет, является ли SQL-запрос write-операцией."""
        sql_upper = sql.strip().upper()
        write_operations = ['INSERT', 'UPDATE', 'DELETE', 'DROP', 'CREATE', 'ALTER', 'TRUNCATE', 'MERGE']
        for op in write_operations:
            if sql_upper.startswith(op):
                return True
        return False

    def _get_db_provider(self):
        """
        Получение DB провайдера из инфраструктуры (stateless).

        Возвращает первый доступный DB провайдер из resource_registry.
        Предпочитает провайдер по умолчанию (is_default=True).
        """
        try:
            infra_ctx = self.application_context.infrastructure_context
            # Сначала ищем провайдер по умолчанию
            default_db = infra_ctx.resource_registry.get_default_resource(ResourceType.DATABASE)
            if default_db and default_db.instance:
                return default_db.instance

            # Если нет default — берём первый доступный
            db_resources = infra_ctx.resource_registry.get_resources_by_type(ResourceType.DATABASE)
            if db_resources:
                return db_resources[0].instance
        except Exception as e:
            self._log_error(f"Ошибка получения DB провайдера: {e}", event_type=LogEventType.ERROR)
        return None

    async def _execute_impl(
        self,
        capability: 'Capability',
        parameters: Dict[str, Any],
        execution_context: 'ExecutionContext'
    ) -> Dict[str, Any]:
        """
        Выполнение SQL-запроса с использованием изолированных ресурсов и проверкой sandbox режима.

        Теперь async-метод — можно вызывать db.execute_query напрямую через await.
        """
        # Преобразуем параметры в dict (если это Pydantic-объект)
        if hasattr(parameters, 'model_dump'):
            params_dict = parameters.model_dump()
        elif isinstance(parameters, dict):
            params_dict = parameters
        else:
            error_msg = f"Неподдерживаемый тип параметров: {type(parameters)}"
            self._log_error(error_msg, event_type=LogEventType.ERROR)
            return {
                "rows": [],
                "columns": [],
                "rowcount": 0,
                "execution_time": 0,
                "error": error_msg,
                "sql_query": parameters.get('sql', '') if isinstance(parameters, dict) else ''
            }

        # Преобразуем параметры во входные данные
        input_data = self._convert_params_to_input(params_dict)

        start_time = time.time()

        # Получаем DB провайдер из инфраструктуры (stateless подход)
        db_provider = self._get_db_provider()
        if not db_provider:
            error_msg = "DB провайдер не найден в infrastructure_context"
            self._log_error(error_msg, event_type=LogEventType.ERROR)
            return {
                "rows": [],
                "columns": [],
                "rowcount": 0,
                "execution_time": time.time() - start_time,
                "error": error_msg,
                "sql_query": input_data.sql
            }

        # Проверка sandbox-режима
        if not self.component_config.side_effects_enabled and self._is_write_query(input_data.sql):
            error_msg = "Sandbox режим: write-запрос отклонён"
            self._log_warning(error_msg, event_type=LogEventType.WARNING)
            return {
                "rows": [],
                "columns": [],
                "rowcount": 0,
                "execution_time": time.time() - start_time,
                "error": error_msg,
                "sql_query": input_data.sql
            }

        # Выполнение через провайдера — НАПРЯМУЮ через await (мы в async контексте)
        try:
            result = await db_provider.execute_query(
                query=input_data.sql,
                params=input_data.parameters
            )
        except Exception as e:
            error_msg = str(e)
            self._log_error(f"Ошибка выполнения SQL: {error_msg}", event_type=LogEventType.ERROR)
            return {
                "rows": [],
                "columns": [],
                "rowcount": 0,
                "execution_time": time.time() - start_time,
                "error": error_msg,
                "sql_query": input_data.sql
            }

        execution_time = time.time() - start_time

        output = {
            "rows": result.rows,
            "columns": result.columns,
            "rowcount": result.rowcount,
            "execution_time": execution_time,
            "sql_query": input_data.sql
        }

        # === ЭТАП 2: Валидация выходных данных через схему ===
        output_schema = self.get_output_contract("sql_tool.execute_query")
        if output_schema:
            try:
                from dataclasses import asdict
                output_schema.model_validate(output)
            except Exception as e:
                error_msg = f"Валидация выходных данных не пройдена: {e}"
                self._log_error(error_msg, event_type=LogEventType.ERROR)
                return {
                    "rows": [],
                    "columns": [],
                    "rowcount": 0,
                    "execution_time": execution_time,
                    "error": error_msg,
                    "sql_query": input_data.sql
                }

        return output

    def _is_write_operation(self, sql: str) -> bool:
        """Проверка является ли SQL операцией записи."""
        sql_upper = sql.strip().upper()
        write_operations = ['INSERT', 'UPDATE', 'DELETE', 'DROP', 'CREATE', 'ALTER', 'TRUNCATE', 'MERGE']
        for op in write_operations:
            if sql_upper.startswith(op):
                return True
        return False

    def _convert_params_to_input(self, parameters: Dict[str, Any]) -> SQLToolInput:
        """
        Преобразование параметров нового интерфейса в SQLToolInput.
        """
        sql = parameters.get('sql', '')
        parameters_dict = parameters.get('parameters', {})
        max_rows = parameters.get('max_rows', 1000)
        return SQLToolInput(sql=sql, parameters=parameters_dict, max_rows=max_rows)