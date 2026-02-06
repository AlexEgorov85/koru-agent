from enum import Enum
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
from datetime import datetime
from uuid import uuid4


class ComposablePatternStatus(str, Enum):
    """
    Статусы выполнения композиционного паттерна
    """
    INITIALIZING = "initializing"      # Инициализация
    ACTIVE = "active"                  # Активен, выполняет действия
    WAITING_FOR_INPUT = "waiting_for_input"  # Ожидает ввода от пользователя
    PAUSED = "paused"                  # Приостановлен
    COMPLETED = "completed"            # Завершен успешно
    FAILED = "failed"                  # Завершен с ошибкой
    STOPPED = "stopped"                # Остановлен пользователем
    TERMINATED = "terminated"          # Принудительно завершен


class ComposablePatternState(BaseModel):
    """
    Состояние композиционного паттерна для ReAct (Reasoning and Acting)
    
    Служит для отслеживания прогресса выполнения паттерна, включая:
    - текущее состояние выполнения
    - историю действий
    - метрики прогресса
    - информацию о текущем цикле ReAct
    """
    
    # Идентификация
    id: str = Field(default_factory=lambda: f"pattern_state_{uuid4().hex[:12]}")
    pattern_name: str = ""  # Название паттерна (например, "ReAct")
    session_id: str = ""    # ID сессии, к которой относится состояние
    
    # Статус и жизненный цикл
    status: ComposablePatternStatus = ComposablePatternStatus.INITIALIZING
    started_at: datetime = Field(default_factory=datetime.utcnow)
    finished_at: Optional[datetime] = None
    
    # Счетчики и прогресс
    step_count: int = 0                    # Общее количество шагов
    iteration_count: int = 0               # Количество итераций ReAct
    error_count: int = 0                   # Количество ошибок
    no_progress_iterations: int = 0        # Количество итераций без прогресса
    
    # Информация о текущем состоянии ReAct
    current_thought: Optional[str] = None  # Текущее мышление
    current_action: Optional[Dict[str, Any]] = None  # Текущее действие
    current_observation: Optional[str] = None        # Текущее наблюдение
    
    # История выполнения
    action_history: List[Dict[str, Any]] = Field(default_factory=list)  # История действий
    thought_history: List[str] = Field(default_factory=list)           # История мышления
    observation_history: List[str] = Field(default_factory=list)       # История наблюдений
    
    # Метрики и прогресс
    progress_percentage: float = 0.0       # Процент выполнения задачи
    last_progress_update: Optional[datetime] = None  # Время последнего прогресса
    
    # Дополнительные данные
    metadata: Dict[str, Any] = Field(default_factory=dict)  # Дополнительные метаданные
    error_details: Optional[Dict[str, Any]] = None         # Детали последней ошибки
    
    # Управление выполнением
    max_iterations: int = 50              # Максимальное количество итераций
    max_no_progress_iterations: int = 3   # Максимум итераций без прогресса
    finished: bool = False                # Флаг завершения выполнения
    
    # Стек отмены (для поддержки undo операций)
    undo_stack: List[Dict[str, Any]] = Field(default_factory=list)
    
    class Config:
        arbitrary_types_allowed = True
    
    def start_execution(self, pattern_name: str, description: str = ""):
        """Начать выполнение паттерна"""
        self.pattern_name = pattern_name
        self.status = ComposablePatternStatus.ACTIVE
        self.started_at = datetime.utcnow()
        self.metadata["description"] = description
        self.step_count = 0
        self.iteration_count = 0
        self.error_count = 0
        self.no_progress_iterations = 0
    
    def start_iteration(self):
        """Начать новую итерацию ReAct"""
        self.iteration_count += 1
        self.step_count += 1
        
        # Очистить текущие данные итерации
        self.current_thought = None
        self.current_action = None
        self.current_observation = None
    
    def record_thought(self, thought: str):
        """Записать мышление в текущую итерацию"""
        self.current_thought = thought
        self.thought_history.append(thought)
    
    def record_action(self, action: Dict[str, Any]):
        """Записать действие в текущую итерацию"""
        self.current_action = action
        self.action_history.append({
            "step": self.step_count,
            "action": action,
            "timestamp": datetime.utcnow(),
            "iteration": self.iteration_count
        })
    
    def record_observation(self, observation: str):
        """Записать наблюдение в текущую итерацию"""
        self.current_observation = observation
        self.observation_history.append(observation)
    
    def register_error(self):
        """Зарегистрировать ошибку"""
        self.error_count += 1
    
    def register_progress(self, progressed: bool):
        """Зарегистрировать прогресс"""
        if progressed:
            self.no_progress_iterations = 0
            self.last_progress_update = datetime.utcnow()
            # Обновить процент выполнения на основе прогресса
            self.progress_percentage = min(100.0, self.progress_percentage + 5.0)
        else:
            self.no_progress_iterations += 1
    
    def complete(self):
        """Отметить паттерн как завершенный"""
        self.status = ComposablePatternStatus.COMPLETED
        self.finished = True
        self.finished_at = datetime.utcnow()
    
    def pause(self):
        """Приостановить выполнение паттерна"""
        self.status = ComposablePatternStatus.PAUSED
    
    def resume(self):
        """Возобновить выполнение паттерна"""
        self.status = ComposablePatternStatus.ACTIVE
    
    def waiting_for_input(self):
        """Отметить паттерн как ожидающий ввода"""
        self.status = ComposablePatternStatus.WAITING_FOR_INPUT
    
    def fail(self, error_details: Optional[Dict[str, Any]] = None):
        """Отметить паттерн как завершенный с ошибкой"""
        self.status = ComposablePatternStatus.FAILED
        self.finished = True
        self.finished_at = datetime.utcnow()
        if error_details:
            self.error_details = error_details
    
    def add_to_undo_stack(self, operation: Dict[str, Any]):
        """Добавить операцию в стек отмены"""
        self.undo_stack.append(operation)
    
    def pop_from_undo_stack(self) -> Optional[Dict[str, Any]]:
        """Извлечь последнюю операцию из стека отмены"""
        if self.undo_stack:
            return self.undo_stack.pop()
        return None
    
    def is_max_iterations_reached(self) -> bool:
        """Проверить, достигнуто ли максимальное количество итераций"""
        return self.iteration_count >= self.max_iterations
    
    def is_no_progress_limit_reached(self) -> bool:
        """Проверить, достигнуто ли ограничение на итерации без прогресса"""
        return self.no_progress_iterations >= self.max_no_progress_iterations