"""
Модели данных для execution traces.

ИСПОЛЬЗУЕТСЯ:
- ExecutionTrace: полный след выполнения сессии (optimization модули)
- StepTrace: след одного шага (optimization модули)
- ErrorType: типы ошибок (pattern_analyzer)
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from core.models.types.llm_types import LLMRequest, LLMResponse


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
class StepTrace:
    """
    След одного шага агента.
    """
    step_number: int
    capability: str
    goal: str

    llm_request: Optional[LLMRequest] = None
    llm_response: Optional[LLMResponse] = None

    errors: List['ErrorDetail'] = field(default_factory=list)

    time_ms: float = 0.0
    tokens_used: int = 0

    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def success(self) -> bool:
        return len(self.errors) == 0

    @property
    def has_llm_call(self) -> bool:
        return self.llm_request is not None and self.llm_response is not None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'step_number': self.step_number,
            'capability': self.capability,
            'goal': self.goal,
            'llm_request': self.llm_request.to_dict() if self.llm_request else None,
            'llm_response': self.llm_response.to_dict() if self.llm_response else None,
            'errors': [e.to_dict() for e in self.errors],
            'time_ms': self.time_ms,
            'tokens_used': self.tokens_used,
            'success': self.success,
            'metadata': self.metadata
        }


@dataclass
class ErrorDetail:
    """Детальная информация об ошибке."""
    error_type: ErrorType
    message: str
    traceback: Optional[str] = None
    capability: Optional[str] = None
    step_number: Optional[int] = None
    context: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'error_type': self.error_type.value,
            'message': self.message,
            'traceback': self.traceback,
            'capability': self.capability,
            'step_number': self.step_number,
            'context': self.context
        }


@dataclass
class ExecutionTrace:
    """
    Полный след выполнения сессии.
    """
    session_id: str
    agent_id: str
    goal: str

    steps: List[StepTrace] = field(default_factory=list)

    success: bool = True
    total_time_ms: float = 0.0
    total_tokens: int = 0
    final_answer: Optional[str] = None
    error: Optional[str] = None

    started_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None

    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_step(self, step: StepTrace) -> None:
        self.steps.append(step)
        self.steps.sort(key=lambda s: s.step_number)

        self.total_time_ms = sum(s.time_ms for s in self.steps)
        self.total_tokens = sum(s.tokens_used for s in self.steps)

        if not step.success:
            self.success = False
            if step.errors:
                self.error = step.errors[-1].message

        self.completed_at = datetime.now()

    @property
    def step_count(self) -> int:
        return len(self.steps)

    @property
    def error_count(self) -> int:
        return sum(len(s.errors) for s in self.steps)

    @property
    def llm_call_count(self) -> int:
        return sum(1 for s in self.steps if s.has_llm_call)

    def get_errors_by_type(self) -> Dict[str, int]:
        error_counts = {}
        for step in self.steps:
            for error in step.errors:
                error_type = error.error_type.value
                error_counts[error_type] = error_counts.get(error_type, 0) + 1
        return error_counts

    def get_capabilities_used(self) -> List[str]:
        return list(set(s.capability for s in self.steps))

    def to_dict(self) -> Dict[str, Any]:
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
