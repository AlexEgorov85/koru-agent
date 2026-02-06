from enum import Enum
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
from datetime import datetime
from uuid import uuid4
from domain.models.agent.agent_state import AgentState
from domain.models.composable_pattern_state import ComposablePatternState, ComposablePatternStatus


class AgentRuntimeStatus(str, Enum):
    """
    Статусы выполнения рантайма агента
    """
    INITIALIZING = "initializing"      # Инициализация
    READY = "ready"                   # Готов к работе
    THINKING = "thinking"             # Выполняет мышление (Thought)
    ACTING = "acting"                 # Выполняет действие (Action)
    OBSERVING = "observing"           # Выполняет наблюдение (Observation)
    EXECUTING = "executing"           # Выполняет общую логику
    WAITING_FOR_INPUT = "waiting_for_input"  # Ожидает ввода от пользователя
    PAUSED = "paused"                 # Приостановлен
    COMPLETED = "completed"           # Завершен успешно
    FAILED = "failed"                 # Завершен с ошибкой
    STOPPED = "stopped"               # Остановлен пользователем
    TERMINATED = "terminated"         # Принудительно завершен


class AgentRuntimeState(BaseModel):
    """
    Состояние рантайма агента для ReAct (Reasoning and Acting)
    
    Служит для отслеживания прогресса выполнения задачи агентом, включая:
    - текущее состояние выполнения
    - историю итераций ReAct
    - метрики прогресса
    - информацию о текущем цикле ReAct
    """
    
    # Идентификация
    id: str = Field(default_factory=lambda: f"runtime_state_{uuid4().hex[:12]}")
    agent_id: str = ""                 # ID агента
    session_id: str = ""               # ID сессии, к которой относится состояние
    task_id: str = ""                  # ID задачи, которую выполняет агент
    
    # Статус и жизненный цикл
    status: AgentRuntimeStatus = AgentRuntimeStatus.INITIALIZING
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
    
    # История выполнения ReAct
    thought_history: List[Dict[str, Any]] = Field(default_factory=list)      # История мышления
    action_history: List[Dict[str, Any]] = Field(default_factory=list)       # История действий
    observation_history: List[Dict[str, Any]] = Field(default_factory=list)  # История наблюдений
    
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
    
    # Связь с паттерном ReAct
    current_pattern_state: Optional[ComposablePatternState] = None  # Состояние текущего паттерна
    
    class Config:
        arbitrary_types_allowed = True
    
    def start_execution(self, agent_id: str, session_id: str, task_id: str, task_description: str = ""):
        """Начать выполнение задачи агентом"""
        self.agent_id = agent_id
        self.session_id = session_id
        self.task_id = task_id
        self.status = AgentRuntimeStatus.THINKING
        self.started_at = datetime.utcnow()
        self.metadata["task_description"] = task_description
        self.step_count = 0
        self.iteration_count = 0
        self.error_count = 0
        self.no_progress_iterations = 0
    
    def start_iteration(self):
        """Начать новую итерацию ReAct"""
        self.iteration_count += 1
        self.step_count += 1
        self.status = AgentRuntimeStatus.THINKING
        
        # Очистить текущие данные итерации
        self.current_thought = None
        self.current_action = None
        self.current_observation = None
    
    def start_thinking(self, thought: str):
        """Начать фазу мышления"""
        self.status = AgentRuntimeStatus.THINKING
        self.current_thought = thought
        self.thought_history.append({
            "step": self.step_count,
            "iteration": self.iteration_count,
            "thought": thought,
            "timestamp": datetime.utcnow()
        })
    
    def start_acting(self, action: Dict[str, Any]):
        """Начать фазу действия"""
        self.status = AgentRuntimeStatus.ACTING
        self.current_action = action
        self.action_history.append({
            "step": self.step_count,
            "iteration": self.iteration_count,
            "action": action,
            "timestamp": datetime.utcnow()
        })
    
    def start_observing(self, observation: str):
        """Начать фазу наблюдения"""
        self.status = AgentRuntimeStatus.OBSERVING
        self.current_observation = observation
        self.observation_history.append({
            "step": self.step_count,
            "iteration": self.iteration_count,
            "observation": observation,
            "timestamp": datetime.utcnow()
        })
    
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
        """Отметить выполнение как завершенное"""
        self.status = AgentRuntimeStatus.COMPLETED
        self.finished = True
        self.finished_at = datetime.utcnow()
    
    def pause(self):
        """Приостановить выполнение"""
        self.status = AgentRuntimeStatus.PAUSED
    
    def resume(self):
        """Возобновить выполнение"""
        self.status = AgentRuntimeStatus.THINKING  # Начать с фазы мышления
    
    def waiting_for_input(self):
        """Отметить как ожидающий ввода"""
        self.status = AgentRuntimeStatus.WAITING_FOR_INPUT
    
    def fail(self, error_details: Optional[Dict[str, Any]] = None):
        """Отметить выполнение как завершенное с ошибкой"""
        self.status = AgentRuntimeStatus.FAILED
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