from asyncio.log import logger
import time
from dataclasses import dataclass
from typing import Optional, Any

from core.infrastructure.tools.base_tool import BaseTool, ToolInput, ToolOutput
from core.system_context.base_system_contex import BaseSystemContext

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
    """Инструмент для выполнения SQL-запросов с четким контрактом."""
    
    @property
    def description(self) -> str:
        return "Выполнение SQL-запросов к базе данных"
    
    def __init__(self, name: str, system_context: BaseSystemContext, **kwargs):
        super().__init__(name, system_context, **kwargs)
        self.db_connection = kwargs.get("db_connection") or system_context.get_resource("default_db")

    
    async def initialize(self) -> bool:
        """Инициализация подключения к БД."""
        pass
        # return await self.db_connection.is_healthy()
    
    async def shutdown(self) -> None:
        """Корректное завершение работы (базовая реализация)."""
        logger.debug(f"Базовое завершение работы для инструмента {self.name}")
    
    async def execute(self, input_data: SQLToolInput) -> SQLToolOutput:
        """Чистое выполнение SQL-запроса без дополнительной логики."""
        start_time = time.time()
        
        result = await self.db_connection.execute(
            query=input_data.sql,
            params=input_data.parameters,
            max_rows=input_data.max_rows
        )
        
        execution_time = time.time() - start_time
        
        return SQLToolOutput(
            rows=result.rows,
            columns=result.columns,
            rowcount=result.rowcount,
            execution_time=execution_time
        )