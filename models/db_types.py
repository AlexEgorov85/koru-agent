"""
Типы данных для DB порта.
Содержит стандартизированные типы для работы со всеми DB провайдерами.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

class DBHealthStatus(str, Enum):
    """
    Стандартизированные статусы здоровья для DB провайдеров.
    
    ПРИНЦИПЫ:
    - Единый контракт для всех БД провайдеров
    - Поддержка graceful degradation
    - Интеграция с системой мониторинга
    
    СТРАТЕГИИ:
    - HEALTHY: Нормальная работа, все операции выполняются
    - DEGRADED: Работает, но с ограничениями (таймауты, частичная доступность)
    - UNHEALTHY: Критические проблемы, БД недоступна
    - UNKNOWN: Статус неизвестен (инициализация, нет данных о состоянии)
    
    ИСПОЛЬЗОВАНИЕ:
    if db_provider.health_status == DBHealthStatus.HEALTHY:
        execute_critical_queries()
    elif db_provider.health_status == DBHealthStatus.DEGRADED:
        use_cached_data_or_read_only_mode()
    """
    HEALTHY = "healthy"
    DEGRADED = "degraded" 
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"

@dataclass
class DBConnectionConfig:
    """
    Конфигурация подключения к базе данных.
    
    АРХИТЕКТУРНАЯ РОЛЬ:
    - Стандартизирует параметры подключения для всех БД
    - Обеспечивает валидацию и безопасность
    - Поддерживает разные типы СУБД через единый интерфейс
    
    ПОЛЯ:
    - host: Хост базы данных
    - port: Порт подключения
    - database: Имя базы данных
    - username: Имя пользователя
    - password: Пароль (должен шифроваться на уровне конфигурации)
    - sslmode: Режим SSL соединения
    - timeout: Таймаут подключения в секундах
    - pool_size: Размер пула соединений
    
    ПРИМЕР ИСПОЛЬЗОВАНИЯ:
    config = DBConnectionConfig(
        host="localhost",
        port=5432,
        database="agent_db", 
        username="user",
        password="${DB_PASSWORD}",  # Переменная окружения
        sslmode="prefer",
        timeout=30.0,
        pool_size=10
    )
    """
    host: str = "localhost"
    port: int = 5432
    database: str = ""
    username: str = ""
    password: str = ""
    sslmode: str = "prefer"
    timeout: float = 30.0
    pool_size: int = 10
    
    def __post_init__(self):
        """Валидация параметров конфигурации."""
        if not self.database:
            raise ValueError("database не может быть пустым")
        if not self.username:
            raise ValueError("username не может быть пустым")
        if self.port <= 0 or self.port > 65535:
            raise ValueError("Некорректный port")
        if self.timeout <= 0:
            raise ValueError("timeout должен быть положительным")
        if self.pool_size <= 0:
            raise ValueError("pool_size должен быть положительным")

@dataclass
class DBQueryResult:
    """
    Результат выполнения SQL запроса.
    
    ПРИНЦИПЫ:
    - Единый формат для всех БД провайдеров
    - Поддержка как успешных, так и неудачных запросов
    - Метрики выполнения для мониторинга
    
    ПОЛЯ:
    - success: Успешность выполнения
    - rows: Строки результата (для SELECT)
    - rowcount: Количество затронутых строк (для INSERT/UPDATE/DELETE)
    - columns: Имена колонок
    - execution_time: Время выполнения в секундах
    - error: Текст ошибки при неудачном выполнении
    - meta Дополнительные метаданные (план выполнения, статистика)
    
    МЕТОДЫ:
    - first(): Получение первой строки результата
    - __len__(): Количество строк в результате
    
    ПРИМЕР ИСПОЛЬЗОВАНИЯ:
    result = await db_provider.execute("SELECT * FROM users WHERE id = $1", [user_id])
    if result.success:
        if result.rows:
            user = result.first()
            print(f"Найден пользователь: {user['name']}")
        else:
            print("Пользователь не найден")
    else:
        print(f"Ошибка выполнения: {result.error}")
    """
    success: bool
    rows: List[Dict[str, Any]]
    rowcount: int
    columns: List[str]
    execution_time: float = 0.0
    error: Optional[str] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
        if self.error and self.success:
            raise ValueError("success не может быть True при наличии error")
    
    def first(self) -> Optional[Dict[str, Any]]:
        """Получение первой строки результата."""
        return self.rows[0] if self.rows else None
    
    def __len__(self):
        return len(self.rows)