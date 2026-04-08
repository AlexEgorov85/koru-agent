from typing import Dict, Any, Optional, List
from core.infrastructure.event_bus.unified_event_bus import EventType
from core.models.data.capability import Capability
from core.components.services.base_service import BaseService
from core.application_context.application_context import ApplicationContext
from core.models.enums.common_enums import ResourceType


class TableDescriptionService(BaseService):
    """
    Сервис получения описания структуры таблиц из БД.

    Использует sql_tool для выполнения запросов к information_schema.
    Автоматически выбирает нужный DB провайдер по имени schema.
    """

    @property
    def description(self) -> str:
        return "Сервис получения описания структуры таблиц из БД"

    def __init__(self, application_context: ApplicationContext, name: str = None, component_config=None, executor=None, event_bus=None):
        from core.config.component_config import ComponentConfig
        if component_config is None:
            component_config = ComponentConfig(
                variant_id="table_description_service_default",
                prompt_versions={},
                input_contract_versions={},
                output_contract_versions={}
            )
        super().__init__(
            name=name or "table_description_service",
            application_context=application_context,
            component_config=component_config,
            executor=executor,
            event_bus=event_bus
        )

    async def _custom_initialize(self) -> bool:
        self._table_cache = {}
        return True

    def _empty_result(self, schema_name, table_name, reason) -> Dict[str, Any]:
        """Возврат пустого результата с описанием причины."""
        return {
            "schema_name": schema_name,
            "table_name": table_name,
            "description": reason,
            "columns": [],
            "constraints": [],
            "examples": []
        }

    def _get_event_type_for_success(self) -> EventType:
        return EventType.PROVIDER_REGISTERED

    def _execute_impl(
        self,
        capability: Capability,
        parameters: Dict[str, Any],
        execution_context: 'ExecutionContext'
    ) -> Dict[str, Any]:
        from core.infrastructure.event_bus.unified_event_bus import safe_async_call
        metadata = safe_async_call(self.get_table_metadata(
            schema_name=parameters.get("schema_name", ""),
            table_name=parameters.get("table_name", ""),
            context=parameters.get("context"),
            step_number=parameters.get("step_number")
        ))
        return {"metadata": metadata, "capability": capability.name}

    async def shutdown(self) -> None:
        pass

    async def get_table(
        self,
        table_name: str,
        schema_name: str = "public"
    ) -> Dict[str, Any]:
        session_context = getattr(self.application_context, 'data_context', self.application_context)
        metadata = await self.get_table_metadata(
            schema_name=schema_name,
            table_name=table_name,
            context=session_context,
            step_number=1
        )
        return {"metadata": metadata}

    async def get_table_metadata(
        self,
        schema_name: str,
        table_name: str,
        context: Any,
        step_number: int
    ) -> Dict[str, Any]:
        try:
            if not self._is_valid_identifier(schema_name) or not self._is_valid_identifier(table_name):
                raise ValueError("Invalid schema or table name")

            sql = """
            SELECT
                cols.column_name,
                cols.data_type,
                cols.character_maximum_length,
                cols.numeric_precision,
                cols.numeric_scale,
                cols.is_nullable,
                cols.column_default
            FROM information_schema.columns cols
            WHERE cols.table_schema = %s AND cols.table_name = %s
            ORDER BY cols.ordinal_position
            """

            from core.agent.components.action_executor import ExecutionContext
            exec_context = ExecutionContext()

            columns_result = await self.executor.execute_action(
                action_name="sql_tool.execute",
                parameters={
                    "sql": sql,
                    "parameters": {"1": schema_name, "2": table_name}
                },
                context=exec_context
            )

            # Проверяем результат — data может быть dict или объектом
            if columns_result.status.name != "COMPLETED" or not columns_result.data:
                return self._empty_result(schema_name, table_name, f"Запрос не выполнен: {columns_result.error}")

            data = columns_result.data
            rows = data.get("rows", []) if isinstance(data, dict) else getattr(data, "rows", [])

            if not rows:
                return self._empty_result(schema_name, table_name, "Таблица не найдена или не имеет столбцов")

            columns = []
            for row in rows:
                if isinstance(row, dict):
                    column_name = row.get("column_name", "")
                    data_type = row.get("data_type", "")
                    is_nullable = row.get("is_nullable", "YES")
                    column_default = row.get("column_default", None)
                else:
                    column_name = getattr(row, "column_name", "")
                    data_type = getattr(row, "data_type", "")
                    is_nullable = getattr(row, "is_nullable", "YES")
                    column_default = getattr(row, "column_default", None)

                columns.append({
                    "column_name": column_name,
                    "data_type": data_type,
                    "is_nullable": is_nullable,
                    "column_default": column_default
                })

            return {
                "schema_name": schema_name,
                "table_name": table_name,
                "description": "",
                "columns": columns,
                "constraints": [],
                "examples": []
            }

        except Exception as e:
            return {
                "schema_name": schema_name,
                "table_name": table_name,
                "description": f"Ошибка получения метаданных: {str(e)}",
                "columns": [],
                "constraints": [],
                "examples": []
            }

    def _is_valid_identifier(self, identifier: str) -> bool:
        if not identifier or len(identifier) > 128:
            return False
        import re
        return bool(re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', identifier))