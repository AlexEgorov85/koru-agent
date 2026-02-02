from enum import Enum


class ExecutionStatus(str, Enum):
    """
    Перечисление возможных статусов выполнения действия или состояния выполнения.
    
    СТАТУСЫ:
    - SUCCESS: Действие выполнено успешно
    - FAILED: Действие завершилось с ошибкой
    - INITIALIZING: Инициализация процесса выполнения
    - IDLE: Процесс ожидает
    - ACTIVE: Процесс активен
    - WAITING: Процесс в состоянии ожидания
    - COMPLETED: Процесс завершен
    - ERROR: Произшла ошибка
    - STOPPED: Процесс остановлен
    - TERMINATED: Процесс принудительно завершен
    - PENDING: Ожидает выполнения
    - RUNNING: Выполняется
    - CANCELLED: Отменен
    
    ПРИМЕР ИСПОЛЬЗОВАНИЯ:
    if result.status == ExecutionStatus.SUCCESS:
        process_result(result.observation_item_id)
    elif result.status == ExecutionStatus.FAILED:
        handle_error(result.error)
    elif state.status == ExecutionStatus.ACTIVE:
        continue_execution()
    
    ЗАМЕЧАНИЕ:
    В будущем можно расширить перечисление дополнительными статусами.
    """
    # Статусы для результатов выполнения
    SUCCESS = "success"
    FAILED = "failed"
    PENDING = "pending"
    RUNNING = "running"
    CANCELLED = "cancelled"
    
    # Статусы для состояния выполнения
    INITIALIZING = "initializing"
    IDLE = "idle"
    ACTIVE = "active"
    WAITING = "waiting"
    COMPLETED = "completed"
    ERROR = "error"
    STOPPED = "stopped"
    TERMINATED = "terminated"