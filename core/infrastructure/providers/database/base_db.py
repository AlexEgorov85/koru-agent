"""
Базовый класс для всех DB провайдеров.
Реализует стандартный интерфейс для работы с различными СУБД.
"""

import time
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional, Union


from core.application.agent.components.policy import AgentPolicy
from core.models.types.db_types import DBConnectionConfig, DBHealthStatus, DBQueryResult
from core.infrastructure.providers.base_provider import BaseProvider


class BaseDBProvider(BaseProvider, ABC):
    """
    Базовый класс для всех DB провайдеров.

    АРХИТЕКТУРНЫЕ ПРИНЦИПЫ:
    1. Инверсия зависимостей: Зависит только от абстракций (DBPort)
    2. Единый контракт: Все методы имеют стандартизированную сигнатуру
    3. Безопасность: Параметризованные запросы, защита от SQL-инъекций
    4. Отказоустойчивость: Пулы соединений, таймауты, graceful degradation
    5. Наблюдаемость: Метрики производительности и использования

    МЕТОДЫ:
    - initialize(): Асинхронная инициализация пула соединений
    - shutdown(): Корректное завершение работы
    - health_check(): Проверка состояния здоровья
    - execute(): Выполнение SQL запроса
    - transaction(): Контекстный менеджер для транзакций
    - _update_metrics(): Обновление внутренних метрик

    ПРИМЕР ИСПОЛЬЗОВАНИЯ:
    provider = PostgreSQLProvider(config)
    await provider.initialize()
    result = await provider.execute("SELECT * FROM users WHERE id = $1", [user_id])
    if result.success:
        for row in result.rows:
            print(row)
    """

    def __init__(self, config: Union[Dict[str, Any], DBConnectionConfig]):
        """
        Инициализация DB провайдера.

        ПАРАМЕТРЫ:
        - config: Конфигурация подключения
        """
        if isinstance(config, dict):
            db_config = DBConnectionConfig(**config)
        else:
            db_config = config

        super().__init__(
            name=f"{db_config.database}@{db_config.host}",
            config=config if isinstance(config, dict) else vars(config) if hasattr(config, '__dict__') else config
        )
        self.config = db_config
        self.health_status = DBHealthStatus.UNKNOWN
        self.last_health_check = None
        self.connection_pool = None

    @abstractmethod
    async def initialize(self) -> bool:
        """Асинхронная инициализация провайдера."""
        pass

    @abstractmethod
    async def shutdown(self) -> None:
        """Корректное завершение работы провайдера."""
        pass

    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """Проверка здоровья провайдера."""
        pass

    @abstractmethod
    async def execute(self, query: str, params: Optional[Dict[str, Any]] = None) -> DBQueryResult:
        """Выполнение SQL запроса."""
        pass

    @abstractmethod
    @asynccontextmanager
    async def transaction(self):
        """Контекстный менеджер для транзакций."""
        yield

    def _update_metrics(self, query_time: float, success: bool = True):
        """Обновление внутренних метрик провайдера."""
        super()._update_metrics(query_time, success)
        
        # Специфичная логика для DB
        if self.error_count > 0 and self.request_count > 1:
            error_rate = self.error_count / self.request_count
            if error_rate > 0.95:
                self.health_status = DBHealthStatus.UNHEALTHY
            elif error_rate >= 0.5:
                self.health_status = DBHealthStatus.DEGRADED

    def get_connection_info(self) -> Dict[str, Any]:
        """Получение информации о подключении."""
        info = super().get_info()
        info.update({
            "database": self.config.database,
            "host": self.config.host,
            "port": self.config.port,
            "username": self.config.username,
        })
        return info
