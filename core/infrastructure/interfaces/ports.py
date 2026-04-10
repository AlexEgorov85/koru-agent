"""
Порты (интерфейсы) для архитектуры Ports & Adapters.

ПОРТЫ = Абстракции, которые определяют ЧТО нужно компоненту.
АДАПТЕРЫ = Реализации, которые определяют КАК это работает.

ИСПОЛЬЗОВАНИЕ:
```python
from core.infrastructure.interfaces.ports import DatabasePort, LLMPort

class BookLibrarySkill(BaseSkill):
    def __init__(
        self,
        name: str,
        db_port: DatabasePort,  # ← Абстракция
        llm_port: LLMPort,
        executor: ActionExecutor
    ):
        self._db_port = db_port
        self._llm_port = llm_port
```
"""
from typing import Protocol, List, Dict, Any, Optional, Callable, Awaitable
from datetime import datetime


class DatabasePort(Protocol):
    """
    Порт для работы с базой данных.
    
    АБСТРАКЦИЯ: Определяет что нужно для работы с БД.
    РЕАЛИЗАЦИЯ: PostgreSQLAdapter и т.д.
    """
    
    async def query(
        self,
        sql: str,
        params: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Выполнить SELECT запрос.
        
        ARGS:
        - sql: SQL запрос
        - params: Параметры запроса
        
        RETURNS:
        - Список строк результата
        """
        ...
    
    async def execute(
        self,
        sql: str,
        params: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        Выполнить INSERT/UPDATE/DELETE запрос.
        
        ARGS:
        - sql: SQL запрос
        - params: Параметры запроса
        
        RETURNS:
        - Количество затронутых строк
        """
        ...
    
    async def transaction(
        self,
        operations: List[Callable[[], Awaitable[Any]]]
    ) -> Any:
        """
        Выполнить операции в транзакции.
        
        ARGS:
        - operations: Список асинхронных операций
        
        RETURNS:
        - Результат последней операции
        """
        ...
    
    async def close(self) -> None:
        """Закрыть соединение."""
        ...


class LLMPort(Protocol):
    """
    Порт для работы с LLM.
    
    АБСТРАКЦИЯ: Определяет что нужно для генерации текста.
    РЕАЛИЗАЦИЯ: VLLMAdapter, LlamaAdapter, OpenAIAdapter и т.д.
    """
    
    async def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stop_sequences: Optional[List[str]] = None
    ) -> str:
        """
        Сгенерировать текстовый ответ.
        
        ARGS:
        - messages: Список сообщений в формате [{"role": "user", "content": "..."}]
        - temperature: Температура генерации (0.0-1.0)
        - max_tokens: Максимальное количество токенов
        - stop_sequences: Последовательности для остановки генерации
        
        RETURNS:
        - Сгенерированный текст
        """
        ...
    
    async def generate_structured(
        self,
        messages: List[Dict[str, str]],
        response_schema: Dict[str, Any],
        temperature: float = 0.7
    ) -> Dict[str, Any]:
        """
        Сгенерировать структурированный ответ (JSON).
        
        ARGS:
        - messages: Список сообщений
        - response_schema: JSON Schema ожидаемого ответа
        - temperature: Температура генерации
        
        RETURNS:
        - Словарь с полями согласно схеме
        """
        ...
    
    async def count_tokens(self, messages: List[Dict[str, str]]) -> int:
        """
        Подсчитать количество токенов в сообщениях.
        
        ARGS:
        - messages: Список сообщений
        
        RETURNS:
        - Количество токенов
        """
        ...


class VectorPort(Protocol):
    """
    Порт для векторного поиска.
    
    АБСТРАКЦИЯ: Определяет что нужно для семантического поиска.
    РЕАЛИЗАЦИЯ: FAISSAdapter, ChromaAdapter, QDrantAdapter и т.д.
    """
    
    async def search(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
        threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        Поиск похожих векторов.
        
        ARGS:
        - query: Текстовый запрос
        - top_k: Количество результатов
        - filters: Фильтры по метаданным
        - threshold: Порог схожести (0.0-1.0)
        
        RETURNS:
        - Список результатов с полями: id, content, metadata, score
        """
        ...
    
    async def add(
        self,
        documents: List[Dict[str, Any]]
    ) -> List[str]:
        """
        Добавить документы в индекс.
        
        ARGS:
        - documents: Документы с полями: content, metadata
        
        RETURNS:
        - Список ID добавленных документов
        """
        ...
    
    async def delete(self, ids: List[str]) -> int:
        """
        Удалить документы по ID.
        
        ARGS:
        - ids: Список ID для удаления
        
        RETURNS:
        - Количество удалённых документов
        """
        ...
    
    async def rebuild_index(self) -> bool:
        """
        Перестроить индекс (после массового добавления).
        
        RETURNS:
        - True если успешно
        """
        ...


class CachePort(Protocol):
    """
    Порт для кэширования.
    
    АБСТРАКЦИЯ: Определяет что нужно для кэширования данных.
    РЕАЛИЗАЦИЯ: MemoryCacheAdapter, RedisAdapter и т.д.
    """
    
    async def get(self, key: str) -> Optional[Any]:
        """
        Получить значение из кэша.
        
        ARGS:
        - key: Ключ кэша
        
        RETURNS:
        - Значение или None если не найдено
        """
        ...
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None
    ) -> None:
        """
        Сохранить значение в кэш.
        
        ARGS:
        - key: Ключ кэша
        - value: Значение
        - ttl: Время жизни в секундах (None = бессрочно)
        """
        ...
    
    async def delete(self, key: str) -> bool:
        """
        Удалить значение из кэша.
        
        ARGS:
        - key: Ключ кэша
        
        RETURNS:
        - True если ключ существовал
        """
        ...
    
    async def exists(self, key: str) -> bool:
        """
        Проверить наличие ключа в кэше.
        
        ARGS:
        - key: Ключ кэша
        
        RETURNS:
        - True если ключ существует
        """
        ...
    
    async def clear(self) -> None:
        """Очистить весь кэш."""
        ...


class EventPort(Protocol):
    """
    Порт для событий.
    
    АБСТРАКЦИЯ: Определяет что нужно для публикации/подписки на события.
    РЕАЛИЗАЦИЯ: UnifiedEventBus, EventBusConcurrent и т.д.
    """
    
    async def publish(
        self,
        event_type: str,
        payload: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Опубликовать событие.
        
        ARGS:
        - event_type: Тип события (например, "SKILL_EXECUTED")
        - payload: Данные события
        - metadata: Метаданные (session_id, agent_id, timestamp)
        """
        ...
    
    def subscribe(
        self,
        event_type: str,
        handler: Callable[[Dict[str, Any]], Awaitable[None]],
        priority: int = 0
    ) -> None:
        """
        Подписаться на событие.
        
        ARGS:
        - event_type: Тип события (или "*" для всех)
        - handler: Асинхронная функция-обработчик
        - priority: Приоритет (чем выше, тем раньше вызывается)
        """
        ...
    
    def unsubscribe(
        self,
        event_type: str,
        handler: Callable[[Dict[str, Any]], Awaitable[None]]
    ) -> None:
        """
        Отписаться от события.
        
        ARGS:
        - event_type: Тип события
        - handler: Функция-обработчик
        """
        ...
    
    async def shutdown(self) -> None:
        """Завершить работу шины событий."""
        ...


class StoragePort(Protocol):
    """
    Порт для работы с файловым хранилищем.
    
    АБСТРАКЦИЯ: Определяет что нужно для работы с файлами.
    РЕАЛИЗАЦИЯ: FileSystemAdapter, S3Adapter и т.д.
    """
    
    async def read(self, path: str, encoding: str = "utf-8") -> str:
        """
        Прочитать файл.
        
        ARGS:
        - path: Путь к файлу
        - encoding: Кодировка
        
        RETURNS:
        - Содержимое файла
        """
        ...
    
    async def write(
        self,
        path: str,
        content: str,
        encoding: str = "utf-8"
    ) -> None:
        """
        Записать файл.
        
        ARGS:
        - path: Путь к файлу
        - content: Содержимое
        - encoding: Кодировка
        """
        ...
    
    async def exists(self, path: str) -> bool:
        """
        Проверить наличие файла.
        
        ARGS:
        - path: Путь к файлу
        
        RETURNS:
        - True если файл существует
        """
        ...
    
    async def delete(self, path: str) -> bool:
        """
        Удалить файл.
        
        ARGS:
        - path: Путь к файлу
        
        RETURNS:
        - True если файл удалён
        """
        ...
    
    async def list_files(
        self,
        directory: str,
        pattern: Optional[str] = None
    ) -> List[str]:
        """
        Список файлов в директории.
        
        ARGS:
        - directory: Путь к директории
        - pattern: Глоб-паттерн (например, "*.yaml")
        
        RETURNS:
        - Список путей к файлам
        """
        ...


class MetricsPort(Protocol):
    """
    Порт для сбора метрик.
    
    АБСТРАКЦИЯ: Определяет что нужно для мониторинга.
    РЕАЛИЗАЦИЯ: FileSystemMetricsAdapter, PrometheusAdapter и т.д.
    """
    
    async def record(
        self,
        metric_name: str,
        value: float,
        tags: Optional[Dict[str, str]] = None,
        timestamp: Optional[datetime] = None
    ) -> None:
        """
        Записать метрику.
        
        ARGS:
        - metric_name: Имя метрики
        - value: Значение
        - tags: Теги для группировки
        - timestamp: Время записи (по умолчанию now)
        """
        ...
    
    async def increment(
        self,
        counter_name: str,
        value: int = 1,
        tags: Optional[Dict[str, str]] = None
    ) -> None:
        """
        Инкрементировать счётчик.
        
        ARGS:
        - counter_name: Имя счётчика
        - value: На сколько инкрементировать
        - tags: Теги для группировки
        """
        ...
    
    async def get_metrics(
        self,
        metric_name: str,
        start_time: datetime,
        end_time: Optional[datetime] = None,
        tags: Optional[Dict[str, str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Получить метрики за период.
        
        ARGS:
        - metric_name: Имя метрики
        - start_time: Начало периода
        - end_time: Конец периода (по умолчанию now)
        - tags: Фильтр по тегам
        
        RETURNS:
        - Список записей метрик
        """
        ...
