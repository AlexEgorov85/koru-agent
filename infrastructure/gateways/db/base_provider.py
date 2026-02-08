"""
BaseDBProvider - базовая абстракция для DB-провайдеров.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from enum import Enum


class DatabaseProviderType(Enum):
    """
    Типы DB-провайдеров.
    """
    POSTGRESQL = "postgresql"
    MYSQL = "mysql"
    SQLITE = "sqlite"
    MONGODB = "mongodb"
    REDIS = "redis"


class DatabaseHealthStatus(Enum):
    """
    Статус работоспособности DB-провайдера.
    """
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class BaseDBProvider(ABC):
    """
    Базовая абстракция для DB-провайдеров.
    
    АРХИТЕКТУРА:
    - Расположение: инфраструктурный слой (шлюз)
    - Ответственность: предоставление интерфейса для работы с базами данных
    - Принципы: соблюдение инверсии зависимостей (D в SOLID)
    """
    
    def __init__(self, connection_string: str, config: Dict[str, Any]):
        """
        Инициализация провайдера.
        
        Args:
            connection_string: Строка подключения к базе данных
            config: Конфигурация провайдера
        """
        self.connection_string = connection_string
        self.config = config
        self.health_status = DatabaseHealthStatus.UNKNOWN
        self.query_count = 0
        self.error_count = 0
        self.avg_query_time = 0.0
        self._is_connected = False
    
    @abstractmethod
    async def initialize(self) -> bool:
        """
        Инициализация провайдера.
        
        Returns:
            bool: Успешность инициализации
        """
        pass
    
    @abstractmethod
    async def shutdown(self) -> None:
        """
        Завершение работы провайдера.
        """
        pass
    
    @abstractmethod
    async def execute_query(self, query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Выполнение SQL-запроса.
        
        Args:
            query: SQL-запрос
            params: Параметры запроса
            
        Returns:
            List[Dict[str, Any]]: Результаты запроса
        """
        pass
    
    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """
        Проверка работоспособности.
        
        Returns:
            Dict[str, Any]: Статус работоспособности
        """
        pass
    
    async def execute_transaction(self, queries: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
        """
        Выполнение транзакции с несколькими запросами.
        
        Args:
            queries: Список запросов с параметрами в формате {"query": "...", "params": {...}}
            
        Returns:
            List[List[Dict[str, Any]]]: Результаты всех запросов
        """
        results = []
        try:
            # Начало транзакции (в реальной реализации)
            for query_info in queries:
                query = query_info["query"]
                params = query_info.get("params", {})
                result = await self.execute_query(query, params)
                results.append(result)
            
            # Фиксация транзакции (в реальной реализации)
            return results
        except Exception as e:
            # Откат транзакции (в реальной реализации)
            raise e
    
    async def batch_insert(self, table: str, records: List[Dict[str, Any]]) -> int:
        """
        Пакетная вставка записей в таблицу.
        
        Args:
            table: Название таблицы
            records: Список записей для вставки
            
        Returns:
            int: Количество вставленных записей
        """
        if not records:
            return 0
        
        # Создаем параметризованный запрос для вставки
        columns = list(records[0].keys())
        placeholders = ", ".join([f"${i+1}" if self.config.get("use_named_params") else "?" for i in range(len(columns))])
        columns_str = ", ".join(columns)
        query = f"INSERT INTO {table} ({columns_str}) VALUES ({placeholders})"
        
        # Выполняем пакетную вставку
        total_inserted = 0
        for record in records:
            params = [record[col] for col in columns]
            await self.execute_query(query, params)
            total_inserted += 1
        
        return total_inserted
    
    async def bulk_update(self, table: str, records: List[Dict[str, Any]], key_column: str) -> int:
        """
        Массовое обновление записей в таблице.
        
        Args:
            table: Название таблицы
            records: Список записей для обновления
            key_column: Колонка, по которой определяется уникальность записи
            
        Returns:
            int: Количество обновленных записей
        """
        if not records:
            return 0
        
        total_updated = 0
        for record in records:
            key_value = record.get(key_column)
            if key_value is None:
                continue
            
            # Формируем SET часть запроса
            set_clauses = []
            params = []
            param_index = 1
            
            for column, value in record.items():
                if column != key_column:
                    set_clauses.append(f"{column} = ${param_index}")
                    params.append(value)
                    param_index += 1
            
            # Добавляем условие WHERE
            set_clause = ", ".join(set_clauses)
            params.append(key_value)
            
            query = f"UPDATE {table} SET {set_clause} WHERE {key_column} = ${param_index}"
            await self.execute_query(query, params)
            total_updated += 1
        
        return total_updated
    
    def _update_metrics(self, query_time: float, success: bool = True):
        """
        Обновление метрик работы.
        
        Args:
            query_time: Время выполнения запроса
            success: Успешность операции
        """
        self.query_count += 1
        if not success:
            self.error_count += 1
        
        # Обновляем среднее время выполнения запроса
        total_time = self.avg_query_time * (self.query_count - 1)
        total_time += query_time
        self.avg_query_time = total_time / self.query_count