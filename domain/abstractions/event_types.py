from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import Any, Awaitable, Callable

class EventType(Enum):
    """
    Типы событий системы.
    
    АРХИТЕКТУРА:
    - Расположение: доменный слой (единый источник истины)
    - Ответственность: определение всех типов событий системы
    - Зависимости: только от стандартной библиотеки (никакой инфраструктуры)
    - Принципы: соблюдение единственного источника истины
    
    КАТЕГОРИИ СОБЫТИЙ:
    - СИСТЕМНЫЕ: INFO, WARNING, ERROR, DEBUG, SYSTEM
    - БИЗНЕС-ЛОГИКА: TASK_EXECUTION, PROGRESS, USER_INTERACTION
    - ДОПОЛНИТЕЛЬНЫЕ: SUCCESS, FAILURE, STARTED, COMPLETED и другие
    - ДОМЕННО-СПЕЦИФИЧНЫЕ: могут быть добавлены по мере развития системы
    """
    # Системные события
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    DEBUG = "debug"
    SYSTEM = "system"
    
    # События бизнес-логики
    TASK_EXECUTION = "task_execution"
    PROGRESS = "progress"
    USER_INTERACTION = "user_interaction"
    
    # Дополнительные типы событий для обеспечения совместимости
    SUCCESS = "success"
    FAILURE = "failure"
    STARTED = "started"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    EXCEPTION = "exception"
    RETRY = "retry"
    TIMEOUT = "timeout"
    CONNECTION = "connection"
    DISCONNECTION = "disconnection"
    HEARTBEAT = "heartbeat"
    METRICS = "metrics"
    LOG = "log"
    ALERT = "alert"
    MONITORING = "monitoring"
    HEALTH_CHECK = "health_check"
    INITIALIZATION = "initialization"
    SHUTDOWN = "shutdown"
    REQUEST = "request"
    RESPONSE = "response"
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    VALIDATION = "validation"
    TRANSFORMATION = "transformation"
    SERIALIZATION = "serialization"
    DESERIALIZATION = "deserialization"
    ENCRYPTION = "encryption"
    DECRYPTION = "decryption"
    COMPRESSION = "compression"
    DECOMPRESSION = "decompression"
    UPLOAD = "upload"
    DOWNLOAD = "download"
    SYNC = "sync"
    ASYNC = "async"
    BATCH = "batch"
    STREAM = "stream"
    CACHE_HIT = "cache_hit"
    CACHE_MISS = "cache_miss"
    DATABASE_QUERY = "database_query"
    DATABASE_CONNECTION = "database_connection"
    DATABASE_TRANSACTION = "database_transaction"
    DATABASE_MIGRATION = "database_migration"
    DATABASE_BACKUP = "database_backup"
    DATABASE_RESTORE = "database_restore"
    FILE_READ = "file_read"
    FILE_WRITE = "file_write"
    FILE_DELETE = "file_delete"
    FILE_CREATE = "file_create"
    FILE_MOVE = "file_move"
    FILE_COPY = "file_copy"
    FILE_PERMISSION_CHANGE = "file_permission_change"
    PROCESS_START = "process_start"
    PROCESS_END = "process_end"
    PROCESS_PAUSE = "process_pause"
    PROCESS_RESUME = "process_resume"
    THREAD_CREATED = "thread_created"
    THREAD_DESTROYED = "thread_destroyed"
    MEMORY_ALLOCATION = "memory_allocation"
    MEMORY_DEALLOCATION = "memory_deallocation"
    GC_START = "gc_start"
    GC_END = "gc_end"
    NETWORK_REQUEST = "network_request"
    NETWORK_RESPONSE = "network_response"
    NETWORK_CONNECT = "network_connect"
    NETWORK_DISCONNECT = "network_disconnect"
    NETWORK_TIMEOUT = "network_timeout"
    NETWORK_ERROR = "network_error"
    SSL_HANDSHAKE = "ssl_handshake"
    SSL_CERTIFICATE_VALIDATION = "ssl_certificate_validation"
    RATE_LIMIT = "rate_limit"
    THROTTLING = "throttling"
    BACKOFF = "backoff"
    CIRCUIT_BREAKER_OPEN = "circuit_breaker_open"
    CIRCUIT_BREAKER_CLOSE = "circuit_breaker_close"
    CIRCUIT_BREAKER_HALF_OPEN = "circuit_breaker_half_open"
    QUEUE_PUSH = "queue_push"
    QUEUE_POP = "queue_pop"
    QUEUE_SIZE_CHANGE = "queue_size_change"
    WORKER_ADDED = "worker_added"
    WORKER_REMOVED = "worker_removed"
    POOL_SIZE_CHANGE = "pool_size_change"
    RESOURCE_ACQUIRE = "resource_acquire"
    RESOURCE_RELEASE = "resource_release"
    LOCK_ACQUIRE = "lock_acquire"
    LOCK_RELEASE = "lock_release"
    SEMAPHORE_ACQUIRE = "semaphore_acquire"
    SEMAPHORE_RELEASE = "semaphore_release"
    MUTEX_ACQUIRE = "mutex_acquire"
    MUTEX_RELEASE = "mutex_release"
    CONDITION_WAIT = "condition_wait"
    CONDITION_NOTIFY = "condition_notify"
    EVENT_PUBLISH = "event_publish"
    EVENT_SUBSCRIBE = "event_subscribe"
    EVENT_UNSUBSCRIBE = "event_unsubscribe"
    MESSAGE_SENT = "message_sent"
    MESSAGE_RECEIVED = "message_received"
    MESSAGE_ACKNOWLEDGED = "message_acknowledged"
    MESSAGE_NACK = "message_nack"
    TOPIC_CREATE = "topic_create"
    TOPIC_DELETE = "topic_delete"
    SUBSCRIPTION_CREATE = "subscription_create"
    SUBSCRIPTION_DELETE = "subscription_delete"
    COMMIT = "commit"
    ROLLBACK = "rollback"
    SAVEPOINT_CREATE = "savepoint_create"
    SAVEPOINT_ROLLBACK = "savepoint_rollback"
    MIGRATION_START = "migration_start"
    MIGRATION_END = "migration_end"
    MIGRATION_ROLLBACK = "migration_rollback"
    SEED_START = "seed_start"
    SEED_END = "seed_end"
    VALIDATION_START = "validation_start"
    VALIDATION_END = "validation_end"
    TRANSFORMATION_START = "transformation_start"
    TRANSFORMATION_END = "transformation_end"
    SERIALIZATION_START = "serialization_start"
    SERIALIZATION_END = "serialization_end"
    DESERIALIZATION_START = "deserialization_start"
    DESERIALIZATION_END = "deserialization_end"
    ENCRYPTION_START = "encryption_start"
    ENCRYPTION_END = "encryption_end"
    DECRYPTION_START = "decryption_start"
    DECRYPTION_END = "decryption_end"
    COMPRESSION_START = "compression_start"
    COMPRESSION_END = "compression_end"
    DECOMPRESSION_START = "decompression_start"
    DECOMPRESSION_END = "decompression_end"
    COMPILATION_START = "compilation_start"
    COMPILATION_END = "compilation_end"
    EXECUTION_START = "execution_start"
    EXECUTION_END = "execution_end"
    PARSING_START = "parsing_start"
    PARSING_END = "parsing_end"
    ANALYSIS_START = "analysis_start"
    ANALYSIS_END = "analysis_end"
    OPTIMIZATION_START = "optimization_start"
    OPTIMIZATION_END = "optimization_end"
    GENERATION_START = "generation_start"
    GENERATION_END = "generation_end"
    TESTING_START = "testing_start"
    TESTING_END = "testing_end"
    BUILD_START = "build_start"
    BUILD_END = "build_end"
    DEPLOYMENT_START = "deployment_start"
    DEPLOYMENT_END = "deployment_end"
    RELEASE_START = "release_start"
    RELEASE_END = "release_end"
    MONITORING_START = "monitoring_start"
    MONITORING_END = "monitoring_end"
    PROFILING_START = "profiling_start"
    PROFILING_END = "profiling_end"
    TRACING_START = "tracing_start"
    TRACING_END = "tracing_end"
    DEBUGGING_START = "debugging_start"
    DEBUGGING_END = "debugging_end"
    LOGGING_START = "logging_start"
    LOGGING_END = "logging_end"
    AUDITING_START = "auditing_start"
    AUDITING_END = "auditing_end"
    BACKUP_START = "backup_start"
    BACKUP_END = "backup_end"
    RESTORE_START = "restore_start"
    RESTORE_END = "restore_end"
    REPLICATION_START = "replication_start"
    REPLICATION_END = "replication_end"
    SYNCHRONIZATION_START = "synchronization_start"
    SYNCHRONIZATION_END = "synchronization_end"
    CONFLICT_DETECTED = "conflict_detected"
    CONFLICT_RESOLVED = "conflict_resolved"
    MERGE_START = "merge_start"
    MERGE_END = "merge_end"
    CONFLICT_START = "conflict_start"
    CONFLICT_END = "conflict_end"
    RESOLUTION_START = "resolution_start"
    RESOLUTION_END = "resolution_end"
    VALIDATION_ERROR = "validation_error"
    TRANSFORMATION_ERROR = "transformation_error"
    SERIALIZATION_ERROR = "serialization_error"
    DESERIALIZATION_ERROR = "deserialization_error"
    ENCRYPTION_ERROR = "encryption_error"
    DECRYPTION_ERROR = "decryption_error"
    COMPRESSION_ERROR = "compression_error"
    DECOMPRESSION_ERROR = "decompression_error"
    COMPILATION_ERROR = "compilation_error"
    EXECUTION_ERROR = "execution_error"
    PARSING_ERROR = "parsing_error"
    ANALYSIS_ERROR = "analysis_error"
    OPTIMIZATION_ERROR = "optimization_error"
    GENERATION_ERROR = "generation_error"
    TESTING_ERROR = "testing_error"
    BUILD_ERROR = "build_error"
    DEPLOYMENT_ERROR = "deployment_error"
    RELEASE_ERROR = "release_error"
    MONITORING_ERROR = "monitoring_error"
    PROFILING_ERROR = "profiling_error"
    TRACING_ERROR = "tracing_error"
    DEBUGGING_ERROR = "debugging_error"
    LOGGING_ERROR = "logging_error"
    AUDITING_ERROR = "auditing_error"
    BACKUP_ERROR = "backup_error"
    RESTORE_ERROR = "restore_error"
    REPLICATION_ERROR = "replication_error"
    SYNCHRONIZATION_ERROR = "synchronization_error"
    MERGE_ERROR = "merge_error"
    CONFLICT_ERROR = "conflict_error"
    RESOLUTION_ERROR = "resolution_error"
    CUSTOM = "custom"


class Event:
    """
    Класс события.
    """
    def __init__(self, event_type: EventType, source: str, data: Any, timestamp: datetime = None):
        self.event_type = event_type
        self.source = source
        self.data = data
        self.timestamp = timestamp or datetime.now()
        self.id = f"{event_type.value}_{self.timestamp.timestamp()}_{source}"


class IEventPublisher(ABC):
    """Интерфейс издателя событий для инверсии зависимостей."""

    @abstractmethod
    async def publish(self, event_type: EventType, source: str, data: Any):
        """
        Публикация события.

        Args:
            event_type: Тип события
            source: Источник события
            data: Данные события
        """
        pass

    @abstractmethod
    def subscribe(self, event_type: EventType, handler: Callable[[Event], Awaitable[None]]):
        """
        Подписка на событие определенного типа.

        Args:
            event_type: Тип события
            handler: Обработчик события
        """
        pass

    async def publish_with_ack(self, event_type: EventType, source: str, data: Any) -> str:
        """
        Публикация события с отслеживанием подтверждения (опционально)
        
        Returns:
            str: ID события
        """
        # По умолчанию просто вызываем обычную публикацию
        event = Event(event_type=event_type, source=source, data=data)
        await self.publish(event_type, source, data)
        return event.id

    def subscribe_with_ack(self, event_type: EventType, handler: Callable[[Event], Awaitable[bool]]):
        """
        Подписка на событие с подтверждением (опционально)
        """
        # По умолчанию оборачиваем обычный обработчик
        async def wrapped_handler(event: Event) -> None:
            try:
                await handler(event)
            except Exception:
                pass  # Игнорируем ошибки в базовой реализации
        
        self.subscribe(event_type, wrapped_handler)