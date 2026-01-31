from dataclasses import dataclass
from enum import Enum
from typing import Dict, Any, Optional


class ProgressStatus(str, Enum):
    """
    Статус прогресса выполнения задачи.
    
    ПРИМЕНИЕ:
    - Используется для отслеживания состояния выполнения задач
    - Позволяет системе принимать решения на основе прогресса
    - Интегрируется с системой мониторинга и управления задачами
    
    ПРИМЕР ИСПОЛЬЗОВАНИЯ:
    progress = Progress(
        current=5,
        total=10,
        status=ProgressStatus.IN_PROGRESS
    )
    if progress.status == ProgressStatus.COMPLETED:
        handle_completion()
    """
    PENDING = "pending"              # задача ожидает выполнения
    IN_PROGRESS = "in_progress"      # задача выполняется
    COMPLETED = "completed"          # задача завершена
    FAILED = "failed"                # задача завершена с ошибкой
    CANCELLED = "cancelled"          # задача отменена
    PAUSED = "paused"                # задача приостановлена
    WAITING_FOR_INPUT = "waiting_for_input"  # ожидание ввода от пользователя


@dataclass
class Progress:
    """
    Модель для отслеживания прогресса выполнения задачи.
    
    ПОЛЯ:
    - current: текущий прогресс (например, количество выполненных шагов)
    - total: общий объем работы (например, общее количество шагов)
    - status: текущий статус выполнения
    - details: дополнительные детали о прогрессе
    - metadata: метаданные для расширения функциональности
    
    ПРИМЕР ИСПОЛЬЗОВАНИЯ:
    progress = Progress(
        current=5,
        total=10,
        status=ProgressStatus.IN_PROGRESS,
        details={"current_step": "processing", "items_processed": 500}
    )
    
    # Вычисление процента выполнения
    percentage = (progress.current / progress.total) * 100 if progress.total > 0 else 0
    """
    current: int
    total: int
    status: ProgressStatus
    details: Dict[str, Any] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.details is None:
            self.details = {}
        if self.metadata is None:
            self.metadata = {}
    
    @property
    def percentage(self) -> float:
        """Процент выполнения задачи."""
        return (self.current / self.total * 100) if self.total > 0 else 0.0
    
    @property
    def is_complete(self) -> bool:
        """Проверка, завершена ли задача."""
        return self.status == ProgressStatus.COMPLETED
    
    @property
    def is_active(self) -> bool:
        """Проверка, активна ли задача (в процессе выполнения)."""
        return self.status in [ProgressStatus.PENDING, ProgressStatus.IN_PROGRESS]


@dataclass
class ProgressTracker:
    """
    Трекер прогресса для отслеживания выполнения сложных задач.
    
    ПОЛЯ:
    - task_id: уникальный идентификатор задачи
    - current_step: текущий шаг выполнения
    - total_steps: общее количество шагов
    - status: статус выполнения
    - details: детали текущего состояния
    - metadata: метаданные трекера
    
    ПРИМЕР ИСПОЛЬЗОВАНИЯ:
    tracker = ProgressTracker(
        task_id="task_123",
        current_step=2,
        total_steps=5,
        status=ProgressStatus.IN_PROGRESS
    )
    
    if tracker.is_step_complete:
        tracker.move_to_next_step()
    """
    task_id: str
    current_step: int
    total_steps: int
    status: ProgressStatus
    details: Dict[str, Any] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.details is None:
            self.details = {}
        if self.metadata is None:
            self.metadata = {}
    
    @property
    def is_complete(self) -> bool:
        """Проверка завершения задачи."""
        return self.current_step >= self.total_steps and self.status == ProgressStatus.COMPLETED
    
    @property
    def is_step_complete(self) -> bool:
        """Проверка завершения текущего шага."""
        return self.status in [ProgressStatus.COMPLETED, ProgressStatus.FAILED]
    
    def move_to_next_step(self):
        """Переход к следующему шагу."""
        if self.current_step < self.total_steps:
            self.current_step += 1
            if self.current_step >= self.total_steps:
                self.status = ProgressStatus.COMPLETED
            else:
                self.status = ProgressStatus.IN_PROGRESS
    
    @property
    def percentage_completed(self) -> float:
        """Процент выполнения задачи."""
        return (self.current_step / self.total_steps * 100) if self.total_steps > 0 else 0.0