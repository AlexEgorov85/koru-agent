"""
Инструмент для выполнения SQL-запросов с поддержкой изолированных кэшей и sandbox режима.

АРХИТЕКТУРА:
- Использует изолированные кэши, предзагруженные через ComponentConfig
- Зависимости запрашиваются из инфраструктуры при выполнении
- Поддержка sandbox режима для безопасного выполнения запросов
"""
from asyncio.log import logger
import time
from dataclasses import dataclass
from typing import Optional, Any

from core.application.tools.base_tool import BaseTool, ToolInput, ToolOutput
from core.application.context.application_context import ApplicationContext
from core.config.component_config import ComponentConfig


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


class SQLTool(BaseTool):
    """Инструмент для выполнения SQL-запросов с четким контрактом и поддержкой изолированных кэшей."""

    @property
    def description(self) -> str:
        return "Выполнение SQL-запросов к базе данных с поддержкой изолированных кэшей и sandbox режима"

    def __init__(self, name: str, application_context: ApplicationContext, component_config: Optional[ComponentConfig] = None, **kwargs):
        super().__init__(name, application_context, component_config, **kwargs)

    async def initialize(self) -> bool:
        """Инициализация инструмента (в данном случае не требуется подключения к БД, т.к. оно запрашивается при выполнении)."""
        return True

    async def shutdown(self) -> None:
        """Корректное завершение работы (базовая реализация)."""
        logger.debug(f"Базовое завершение работы для инструмента {self.name}")

    def _is_write_query(self, sql: str) -> bool:
        """Проверяет, является ли SQL-запрос write-операцией."""
        sql_upper = sql.strip().upper()
        write_operations = ['INSERT', 'UPDATE', 'DELETE', 'DROP', 'CREATE', 'ALTER', 'TRUNCATE', 'MERGE']
        for op in write_operations:
            if sql_upper.startswith(op):
                return True
        return False

    async def execute(self, input_data: SQLToolInput) -> SQLToolOutput:
        """Выполнение SQL-запроса с использованием изолированных ресурсов и проверкой sandbox режима."""
        start_time = time.time()

        # Запрашиваем зависимости из инфраструктуры при выполнении
        db_provider = self.application_context.infrastructure_context.get_provider("default_db")

        # Проверка sandbox-режима
        if not self.component_config.side_effects_enabled and self._is_write_query(input_data.sql):
            return SQLToolOutput(
                rows=[],
                columns=[],
                rowcount=0,
                execution_time=time.time() - start_time
            )

        # Выполнение через провайдера
        # Проверяем, поддерживает ли провайдер параметр max_rows
        import inspect
        sig = inspect.signature(db_provider.execute)
        if 'max_rows' in sig.parameters:
            result = await db_provider.execute(
                query=input_data.sql,
                params=input_data.parameters,
                max_rows=input_data.max_rows
            )
        else:
            # Для совместимости с mock-провайдерами
            result = await db_provider.execute(
                query=input_data.sql,
                params=input_data.parameters
            )

        execution_time = time.time() - start_time

        return SQLToolOutput(
            rows=result.rows,
            columns=result.columns,
            rowcount=result.rowcount,
            execution_time=execution_time
        )