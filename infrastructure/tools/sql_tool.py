import time
from dataclasses import dataclass
from typing import Dict, Optional, Any

from domain.abstractions.tools.base_tool import BaseTool
from domain.abstractions.tools.base_tool import ToolInput, ToolOutput


@dataclass
class SQLToolInput(ToolInput):
    sql: str
    parameters: Optional[dict] = None
    max_rows: int = 1000


@dataclass
class SQLToolOutput(ToolOutput):
    success: bool = True
    rows: list = None
    columns: list = None
    rowcount: int = 0
    execution_time: float = 0.0
    
    def __post_init__(self):
        if self.rows is None:
            self.rows = []
        if self.columns is None:
            self.columns = []


class SQLTool(BaseTool):
    """Инструмент для выполнения SQL-запросов с четким контрактом."""

    name = "sql_tool"
    
    @property
    def description(self) -> str:
        return "Выполнение SQL-запросов к базе данных"
    
    def __init__(self, name: str = "sql_tool", system_context: Any = None, **kwargs):
        # Изменим инициализацию, чтобы она соответствовала базовому классу
        super().__init__()
        self.name = name
        self.system_context = system_context
        self.db_connection = kwargs.get("db_connection") or (system_context.get_resource("default_db") if hasattr(system_context, 'get_resource') else None)

    async def _execute_internal(self, input_data: SQLToolInput) -> SQLToolOutput:
        """Внутренняя реализация выполнения SQL-запроса."""
        start_time = time.time()
        
        # Заглушка для выполнения запроса
        # result = await self.db_connection.execute(
        #     query=input_data.sql,
        #     params=input_data.parameters,
        #     max_rows=input_data.max_rows
        # )
        
        # Временная заглушка до тех пор, пока не будет реализовано подключение к БД
        result = type('Result', (), {
            'rows': [['stub_data']],
            'columns': ['column1'],
            'rowcount': 1
        })()
        
        execution_time = time.time() - start_time
        
        return SQLToolOutput(
            success=True,
            rows=result.rows,
            columns=result.columns,
            rowcount=result.rowcount,
            execution_time=execution_time
        )

    async def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Выполнение инструмента согласно новому контракту."""
        # Создаем объект входных данных из параметров
        input_data = SQLToolInput(**parameters)
        # Выполняем внутреннюю логику
        result = await self._execute_internal(input_data)
        # Возвращаем результат виде словаря
        return {
            "success": result.success,
            "rows": result.rows,
            "columns": result.columns,
            "rowcount": result.rowcount,
            "execution_time": result.execution_time
        }
