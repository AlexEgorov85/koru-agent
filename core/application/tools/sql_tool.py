"""
Инструмент для выполнения SQL-запросов с поддержкой изолированных кэшей и sandbox режима.

АРХИТЕКТУРА:
- Использует изолированные кэши, предзагруженные через ComponentConfig
- Зависимости запрашиваются из инфраструктуры при выполнении
- Поддержка sandbox режима для безопасного выполнения запросов
"""
import asyncio
import time
from dataclasses import dataclass
from typing import Dict, Optional, Any

from core.application.tools.base_tool import BaseTool, ToolInput, ToolOutput
from core.application.context.application_context import ApplicationContext
from core.config.component_config import ComponentConfig
from core.infrastructure.logging import EventBusLogger


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

    # Явная декларация зависимостей
    DEPENDENCIES = []  # Нет зависимостей (использует инфраструктуру напрямую)

    @property
    def description(self) -> str:
        return "Выполнение SQL-запросов к базе данных с поддержкой изолированных кэшей и sandbox режима"

    def __init__(self, name: str, application_context: ApplicationContext, component_config: Optional[ComponentConfig] = None, executor=None, **kwargs):
        super().__init__(name, application_context, component_config=component_config, executor=executor, **kwargs)
        # EventBusLogger для асинхронного логирования
        self.event_bus_logger = None
        self._init_event_bus_logger()

    def _init_event_bus_logger(self):
        """Инициализация EventBusLogger для асинхронного логирования."""
        if hasattr(self, 'application_context') and self.application_context:
            event_bus = getattr(self.application_context.infrastructure_context, 'event_bus', None)
            if event_bus:
                self.event_bus_logger = EventBusLogger(
                    event_bus,
                    session_id="system",
                    agent_id="system",
                    component=self.__class__.__name__
                )

    def _log_sync(self, level: str, message: str):
        """
        Синхронная обёртка для логирования через EventBusLogger.
        Используется в синхронных методах.
        """
        if not hasattr(self, 'event_bus_logger') or self.event_bus_logger is None:
            return

        if self.event_bus_logger:
            import asyncio
            try:
                loop = asyncio.get_running_loop()
                log_method = getattr(self.event_bus_logger, level, None)
                if log_method:
                    asyncio.create_task(log_method(message))
            except RuntimeError:
                pass

    async def initialize(self) -> bool:
        """Инициализация инструмента (в данном случае не требуется подключения к БД, т.к. оно запрашивается при выполнении)."""
        # Вызываем родительскую инициализацию для правильной установки флага _initialized
        result = await super().initialize()
        return result

    async def shutdown(self) -> None:
        """Корректное завершение работы (базовая реализация)."""
        self._log_sync("debug", f"Базовое завершение работы для инструмента {self.name}")

    def _is_write_query(self, sql: str) -> bool:
        """Проверяет, является ли SQL-запрос write-операцией."""
        sql_upper = sql.strip().upper()
        write_operations = ['INSERT', 'UPDATE', 'DELETE', 'DROP', 'CREATE', 'ALTER', 'TRUNCATE', 'MERGE']
        for op in write_operations:
            if sql_upper.startswith(op):
                return True
        return False

    async def _execute_impl(
        self,
        capability: 'Capability',
        parameters: Dict[str, Any],
        execution_context: 'ExecutionContext'
    ) -> Dict[str, Any]:
        """Выполнение SQL-запроса с использованием изолированных ресурсов и проверкой sandbox режима."""
        # Преобразуем параметры во входные данные
        input_data = self._convert_params_to_input(parameters)
        
        # === ЭТАП 1: Валидация входных данных через схему ===
        input_schema = self.get_cached_input_contract_safe("sql_tool.execute_query")
        if input_schema:
            try:
                input_schema.model_validate({
                    "sql": input_data.sql,
                    "parameters": input_data.parameters,
                    "max_rows": input_data.max_rows
                })
            except Exception as e:
                if self.event_bus_logger:
                    await self.event_bus_logger.error(f"Валидация входных данных не пройдена: {e}")
                else:
                    self.logger.error(f"Валидация входных данных не пройдена: {e}")
                return {
                    "rows": [],
                    "columns": [],
                    "rowcount": 0,
                    "execution_time": 0
                }

        start_time = time.time()

        # Запрашиваем зависимости из инфраструктуры при выполнении через унифицированный метод
        db_provider = self.get_db_provider("default_db")

        if not db_provider:
            if self.event_bus_logger:
                await self.event_bus_logger.error("DB провайдер не найден")
            else:
                self.logger.error("DB провайдер не найден")
            return {
                "rows": [],
                "columns": [],
                "rowcount": 0,
                "execution_time": time.time() - start_time
            }

        # Проверка sandbox-режима
        if not self.component_config.side_effects_enabled and self._is_write_query(input_data.sql):
            return {
                "rows": [],
                "columns": [],
                "rowcount": 0,
                "execution_time": time.time() - start_time
            }

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

        output = {
            "rows": result.rows,
            "columns": result.columns,
            "rowcount": result.rowcount,
            "execution_time": execution_time
        }

        # === ЭТАП 2: Валидация выходных данных через схему ===
        output_schema = self.get_cached_output_contract_safe("sql_tool.execute_query")
        if output_schema:
            try:
                from dataclasses import asdict
                output_schema.model_validate(output)
            except Exception as e:
                if self.event_bus_logger:
                    await self.event_bus_logger.error(f"Валидация выходных данных не пройдена: {e}")
                else:
                    self.logger.error(f"Валидация выходных данных не пройдена: {e}")

        return output

    def _convert_params_to_input(self, parameters: Dict[str, Any]) -> SQLToolInput:
        """
        Преобразование параметров нового интерфейса в SQLToolInput.
        """
        sql = parameters.get('sql', '')
        parameters_dict = parameters.get('parameters', {})
        max_rows = parameters.get('max_rows', 1000)
        return SQLToolInput(sql=sql, parameters=parameters_dict, max_rows=max_rows)