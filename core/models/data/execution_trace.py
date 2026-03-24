"""
Модели данных для execution traces.

КОМПОНЕНТЫ:
- LLMRequest: запрос к LLM
- LLMResponse: ответ от LLM
- Action: действие агента
- ActionResult: результат действия
- ErrorDetail: детальная информация об ошибке
- StepTrace: след одного шага
- ExecutionTrace: полный след выполнения сессии

USAGE:
```python
trace = ExecutionTrace(
    session_id="session_123",
    goal="Какие книги написал Пушкин?",
    steps=[...],
    success=True
)
```
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class ActionType(Enum):
    """Типы действий агента"""
    LLM_CALL = "llm_call"
    TOOL_CALL = "tool_call"
    SKILL_CALL = "skill_call"
    DATABASE_QUERY = "database_query"
    FILE_OPERATION = "file_operation"
    VECTOR_SEARCH = "vector_search"
    NONE = "none"


class ErrorType(Enum):
    """Типы ошибок"""
    SYNTAX_ERROR = "syntax_error"
    VALIDATION_ERROR = "validation_error"
    TIMEOUT = "timeout"
    CONNECTION_ERROR = "connection_error"
    LOGIC_ERROR = "logic_error"
    CONTEXT_LOSS = "context_loss"
    SCHEMA_VIOLATION = "schema_violation"
    UNKNOWN = "unknown"


@dataclass
class LLMRequest:
    """
    Запрос к LLM.

    ATTRIBUTES:
    - prompt: основной промпт
    - system_prompt: системный промпт
    - temperature: температура генерации
    - max_tokens: максимум токенов
    - model: модель LLM
    - timestamp: время запроса
    - metadata: дополнительные метаданные
    """
    prompt: str
    system_prompt: str = ""
    temperature: float = 0.7
    max_tokens: int = 2048
    model: str = "default"
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Сериализация в словарь"""
        return {
            'prompt': self.prompt,
            'system_prompt': self.system_prompt,
            'temperature': self.temperature,
            'max_tokens': self.max_tokens,
            'model': self.model,
            'timestamp': self.timestamp.isoformat(),
            'metadata': self.metadata
        }


@dataclass
class LLMResponse:
    """
    Ответ от LLM.

    ATTRIBUTES:
    - content: содержимое ответа
    - tokens_used: количество использованных токенов
    - latency_ms: время генерации (мс)
    - model: модель LLM
    - timestamp: время ответа
    - finish_reason: причина завершения
    - metadata: дополнительные метаданные
    """
    content: str
    tokens_used: int = 0
    latency_ms: float = 0.0
    model: str = "default"
    timestamp: datetime = field(default_factory=datetime.now)
    finish_reason: str = "stop"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Сериализация в словарь"""
        return {
            'content': self.content,
            'tokens_used': self.tokens_used,
            'latency_ms': self.latency_ms,
            'model': self.model,
            'timestamp': self.timestamp.isoformat(),
            'finish_reason': self.finish_reason,
            'metadata': self.metadata
        }


@dataclass
class Action:
    """
    Действие агента.

    ATTRIBUTES:
    - action_type: тип действия
    - name: название действия/инструмента
    - input_data: входные данные
    - timestamp: время выполнения
    """
    action_type: ActionType
    name: str
    input_data: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Сериализация в словарь"""
        return {
            'action_type': self.action_type.value,
            'name': self.name,
            'input_data': self.input_data,
            'timestamp': self.timestamp.isoformat()
        }


@dataclass
class ActionResult:
    """
    Результат действия.

    ATTRIBUTES:
    - success: успешность выполнения
    - output_data: выходные данные
    - execution_time_ms: время выполнения (мс)
    - error: ошибка (если была)
    """
    success: bool
    output_data: Optional[Dict[str, Any]] = None
    execution_time_ms: float = 0.0
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Сериализация в словарь"""
        return {
            'success': self.success,
            'output_data': self.output_data,
            'execution_time_ms': self.execution_time_ms,
            'error': self.error
        }


@dataclass
class ErrorDetail:
    """
    Детальная информация об ошибке.

    ATTRIBUTES:
    - error_type: тип ошибки
    - message: сообщение об ошибке
    - traceback: стек вызовов
    - capability: название способности
    - step_number: номер шага
    - context: контекст ошибки
    """
    error_type: ErrorType
    message: str
    traceback: Optional[str] = None
    capability: Optional[str] = None
    step_number: Optional[int] = None
    context: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Сериализация в словарь"""
        return {
            'error_type': self.error_type.value,
            'message': self.message,
            'traceback': self.traceback,
            'capability': self.capability,
            'step_number': self.step_number,
            'context': self.context
        }


@dataclass
class StepTrace:
    """
    След одного шага агента.

    ATTRIBUTES:
    - step_number: номер шага
    - capability: название способности
    - goal: цель шага
    - llm_request: запрос к LLM
    - llm_response: ответ от LLM
    - action: выполненное действие
    - action_result: результат действия
    - errors: список ошибок
    - time_ms: время выполнения (мс)
    - tokens_used: количество токенов
    - metadata: дополнительные метаданные
    """
    step_number: int
    capability: str
    goal: str
    
    # Промпт и ответ
    llm_request: Optional[LLMRequest] = None
    llm_response: Optional[LLMResponse] = None
    
    # Действие
    action: Optional[Action] = None
    action_result: Optional[ActionResult] = None
    
    # Ошибки
    errors: List[ErrorDetail] = field(default_factory=list)
    
    # Метрики
    time_ms: float = 0.0
    tokens_used: int = 0
    
    # Метаданные
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def success(self) -> bool:
        """Проверка успешности шага"""
        return len(self.errors) == 0

    @property
    def has_llm_call(self) -> bool:
        """Есть ли LLM вызов"""
        return self.llm_request is not None and self.llm_response is not None

    def to_dict(self) -> Dict[str, Any]:
        """Сериализация в словарь"""
        return {
            'step_number': self.step_number,
            'capability': self.capability,
            'goal': self.goal,
            'llm_request': self.llm_request.to_dict() if self.llm_request else None,
            'llm_response': self.llm_response.to_dict() if self.llm_response else None,
            'action': self.action.to_dict() if self.action else None,
            'action_result': self.action_result.to_dict() if self.action_result else None,
            'errors': [e.to_dict() for e in self.errors],
            'time_ms': self.time_ms,
            'tokens_used': self.tokens_used,
            'success': self.success,
            'metadata': self.metadata
        }


@dataclass
class ExecutionTrace:
    """
    Полный след выполнения сессии.

    ATTRIBUTES:
    - session_id: идентификатор сессии
    - agent_id: идентификатор агента
    - goal: цель выполнения
    - steps: шаги выполнения
    - success: успешность выполнения
    - total_time_ms: общее время (мс)
    - total_tokens: общее количество токенов
    - final_answer: финальный ответ
    - error: ошибка (если была)
    - started_at: время начала
    - completed_at: время завершения
    - metadata: дополнительные метаданные
    """
    session_id: str
    agent_id: str
    goal: str
    
    # Полный путь
    steps: List[StepTrace] = field(default_factory=list)
    
    # Итог
    success: bool = True
    total_time_ms: float = 0.0
    total_tokens: int = 0
    final_answer: Optional[str] = None
    error: Optional[str] = None
    
    # Время
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    
    # Метаданные
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_step(self, step: StepTrace) -> None:
        """Добавление шага"""
        self.steps.append(step)
        self.steps.sort(key=lambda s: s.step_number)
        
        # Обновление метрик
        self.total_time_ms = sum(s.time_ms for s in self.steps)
        self.total_tokens = sum(s.tokens_used for s in self.steps)
        
        # Проверка успешности
        if not step.success:
            self.success = False
            if step.errors:
                self.error = step.errors[-1].message
        
        # Обновление времени завершения
        self.completed_at = datetime.now()

    @property
    def step_count(self) -> int:
        """Количество шагов"""
        return len(self.steps)

    @property
    def error_count(self) -> int:
        """Количество ошибок"""
        return sum(len(s.errors) for s in self.steps)

    @property
    def llm_call_count(self) -> int:
        """Количество LLM вызовов"""
        return sum(1 for s in self.steps if s.has_llm_call)

    def get_errors_by_type(self) -> Dict[str, int]:
        """Группировка ошибок по типам"""
        error_counts = {}
        for step in self.steps:
            for error in step.errors:
                error_type = error.error_type.value
                error_counts[error_type] = error_counts.get(error_type, 0) + 1
        return error_counts

    def get_capabilities_used(self) -> List[str]:
        """Получение списка использованных способностей"""
        return list(set(s.capability for s in self.steps))

    def to_dict(self) -> Dict[str, Any]:
        """Сериализация в словарь"""
        return {
            'session_id': self.session_id,
            'agent_id': self.agent_id,
            'goal': self.goal,
            'steps': [s.to_dict() for s in self.steps],
            'success': self.success,
            'total_time_ms': self.total_time_ms,
            'total_tokens': self.total_tokens,
            'final_answer': self.final_answer,
            'error': self.error,
            'started_at': self.started_at.isoformat(),
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'step_count': self.step_count,
            'error_count': self.error_count,
            'llm_call_count': self.llm_call_count,
            'errors_by_type': self.get_errors_by_type(),
            'capabilities_used': self.get_capabilities_used(),
            'metadata': self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ExecutionTrace':
        """Десериализация из словаря"""
        trace = cls(
            session_id=data['session_id'],
            agent_id=data['agent_id'],
            goal=data['goal'],
            success=data.get('success', True),
            total_time_ms=data.get('total_time_ms', 0),
            total_tokens=data.get('total_tokens', 0),
            final_answer=data.get('final_answer'),
            error=data.get('error'),
            started_at=datetime.fromisoformat(data['started_at']),
            metadata=data.get('metadata', {})
        )
        
        if data.get('completed_at'):
            trace.completed_at = datetime.fromisoformat(data['completed_at'])
        
        for step_data in data.get('steps', []):
            step = StepTrace(
                step_number=step_data['step_number'],
                capability=step_data['capability'],
                goal=step_data['goal'],
                time_ms=step_data.get('time_ms', 0),
                tokens_used=step_data.get('tokens_used', 0),
                metadata=step_data.get('metadata', {})
            )
            
            if step_data.get('llm_request'):
                req = step_data['llm_request']
                step.llm_request = LLMRequest(
                    prompt=req['prompt'],
                    system_prompt=req.get('system_prompt', ''),
                    temperature=req.get('temperature', 0.7),
                    max_tokens=req.get('max_tokens', 2048),
                    model=req.get('model', 'default'),
                    timestamp=datetime.fromisoformat(req['timestamp']),
                    metadata=req.get('metadata', {})
                )
            
            if step_data.get('llm_response'):
                resp = step_data['llm_response']
                step.llm_response = LLMResponse(
                    content=resp['content'],
                    tokens_used=resp.get('tokens_used', 0),
                    latency_ms=resp.get('latency_ms', 0),
                    model=resp.get('model', 'default'),
                    timestamp=datetime.fromisoformat(resp['timestamp']),
                    finish_reason=resp.get('finish_reason', 'stop'),
                    metadata=resp.get('metadata', {})
                )
            
            if step_data.get('action'):
                act = step_data['action']
                step.action = Action(
                    action_type=ActionType(act['action_type']),
                    name=act['name'],
                    input_data=act.get('input_data', {}),
                    timestamp=datetime.fromisoformat(act['timestamp'])
                )
            
            if step_data.get('action_result'):
                res = step_data['action_result']
                step.action_result = ActionResult(
                    success=res['success'],
                    output_data=res.get('output_data'),
                    execution_time_ms=res.get('execution_time_ms', 0),
                    error=res.get('error')
                )
            
            for err_data in step_data.get('errors', []):
                error = ErrorDetail(
                    error_type=ErrorType(err_data['error_type']),
                    message=err_data['message'],
                    traceback=err_data.get('traceback'),
                    capability=err_data.get('capability'),
                    step_number=err_data.get('step_number'),
                    context=err_data.get('context', {})
                )
                step.errors.append(error)
            
            trace.add_step(step)
        
        return trace


@dataclass
class TraceSummary:
    """
    Краткая сводка по trace.

    ATTRIBUTES:
    - session_id: идентификатор сессии
    - goal: цель
    - success: успешность
    - step_count: количество шагов
    - total_time_ms: общее время
    - error_types: типы ошибок
    """
    session_id: str
    goal: str
    success: bool
    step_count: int
    total_time_ms: float
    error_types: List[str]

    @classmethod
    def from_trace(cls, trace: ExecutionTrace) -> 'TraceSummary':
        """Создание из ExecutionTrace"""
        return cls(
            session_id=trace.session_id,
            goal=trace.goal,
            success=trace.success,
            step_count=trace.step_count,
            total_time_ms=trace.total_time_ms,
            error_types=list(trace.get_errors_by_type().keys())
        )
