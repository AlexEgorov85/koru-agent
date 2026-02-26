"""
Типы данных для работы с базами данных.
"""
from dataclasses import dataclass
from typing import Dict, Any, List, Optional
from enum import Enum


class DBHealthStatus(Enum):
    """
    Статусы здоровья БД.
    """
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class DBConnectionConfig:
    """
    Конфигурация подключения к БД.
    
    ATTRIBUTES:
    - host: хост БД
    - port: порт БД
    - database: имя базы данных
    - username: имя пользователя
    - password: пароль
    - pool_size: размер пула соединений
    - timeout: таймаут подключения
    - sslmode: режим SSL
    """
    host: str = "localhost"
    port: int = 5432
    database: str = "postgres"
    username: str = "postgres"
    password: str = ""
    pool_size: int = 10
    timeout: int = 30
    sslmode: str = "disable"


@dataclass
class DBQueryResult:
    """
    Результат выполнения SQL запроса.
    
    ATTRIBUTES:
    - success: успешность выполнения
    - rows: результаты запроса
    - rowcount: количество затронутых строк
    - columns: имена столбцов
    - error: текст ошибки (если была)
    - execution_time: время выполнения
    - metadata: дополнительные метаданные
    """
    success: bool
    rows: List[Dict[str, Any]]
    rowcount: int
    columns: List[str]
    error: Optional[str] = None
    execution_time: float = 0.0
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}