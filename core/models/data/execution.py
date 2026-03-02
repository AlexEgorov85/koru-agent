"""
Модели для выполнения задач.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, Optional, List

from core.models.enums.common_enums import ExecutionStatus


@dataclass
class SkillResult:
    """
    Унифицированный результат выполнения Skill.

    ИСПОЛЬЗУЕТСЯ ВО ВСЕХ SKILLS ДЛЯ ЕДИНОГО ФОРМАТА ВОЗВРАТА.

    ATTRIBUTES:
    - technical_success: технический успех выполнения (True/False)
    - data: полезные данные результата
    - error: описание ошибки (если была)
    - metadata: дополнительные метаданные (время, токены, версии)
    - side_effect: был ли side-effect (файл, сеть, БД, изменение контекста)
    """
    technical_success: bool = True
    data: Optional[Any] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    side_effect: bool = False

    def __post_init__(self):
        # Гарантируем, что metadata всегда dict
        if self.metadata is None:
            self.metadata = {}

    def to_dict(self) -> Dict[str, Any]:
        """Конвертация в словарь для сериализации."""
        return {
            "technical_success": self.technical_success,
            "data": self.data,
            "error": self.error,
            "metadata": self.metadata,
            "side_effect": self.side_effect
        }

    @classmethod
    def success(cls, data: Any = None, metadata: Optional[Dict[str, Any]] = None, side_effect: bool = False) -> 'SkillResult':
        """Factory метод для успешного результата."""
        return cls(
            technical_success=True,
            data=data,
            error=None,
            metadata=metadata or {},
            side_effect=side_effect
        )

    @classmethod
    def failure(cls, error: str, metadata: Optional[Dict[str, Any]] = None) -> 'SkillResult':
        """Factory метод для неудачного результата."""
        return cls(
            technical_success=False,
            data=None,
            error=error,
            metadata=metadata or {},
            side_effect=False
        )


@dataclass
class ExecutionResult:
    """
    Результат выполнения задачи.

    ATTRIBUTES:
    - status: статус выполнения
    - result: результат выполнения
    - error: ошибка (если была)
    - metadata: дополнительные метаданные
    """
    status: ExecutionStatus
    result: Optional[Any] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class ExecutionContextSnapshot:
    """
    Снимок контекста выполнения для обучения.
    
    СОХРАНЯЕТСЯ В ЛОГИ ДЛЯ АНАЛИЗА РЕШЕНИЙ АГЕНТА.
    
    ATTRIBUTES:
    - agent_id: идентификатор агента
    - session_id: идентификатор сессии
    - step_number: номер шага выполнения
    - timestamp: время снимка
    - available_capabilities: доступные способности
    - selected_capability: выбранная способность
    - behavior_pattern: паттерн поведения
    - reasoning: обоснование решения
    - input_parameters: входные параметры
    - output_result: результат выполнения
    - execution_time_ms: время выполнения в мс
    - tokens_used: количество использованных токенов
    - success: успешность выполнения
    - prompt_version: версия промпта
    - contract_version: версия контракта
    - step_quality_score: оценка качества шага (0.0-1.0)
    """
    agent_id: str
    session_id: str
    step_number: int
    timestamp: datetime = field(default_factory=datetime.now)
    
    # Контекст решения
    available_capabilities: List[str] = field(default_factory=list)
    selected_capability: str = ""
    behavior_pattern: str = ""
    reasoning: str = ""
    
    # Параметры выполнения
    input_parameters: Dict[str, Any] = field(default_factory=dict)
    output_result: Optional[Dict[str, Any]] = None
    
    # Метрики
    execution_time_ms: float = 0.0
    tokens_used: int = 0
    success: bool = True
    
    # Версии ресурсов
    prompt_version: str = ""
    contract_version: str = ""
    
    # Оценка качества (для обучения)
    step_quality_score: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Конвертация в словарь для логирования.
        
        RETURNS:
        - Dict[str, Any]: словарь с данными контекста
        """
        return {
            'agent_id': self.agent_id,
            'session_id': self.session_id,
            'step_number': self.step_number,
            'timestamp': self.timestamp.isoformat(),
            'available_capabilities': self.available_capabilities,
            'selected_capability': self.selected_capability,
            'behavior_pattern': self.behavior_pattern,
            'reasoning': self.reasoning,
            'input_parameters': self.input_parameters,
            'output_result': self.output_result,
            'execution_time_ms': self.execution_time_ms,
            'tokens_used': self.tokens_used,
            'success': self.success,
            'prompt_version': self.prompt_version,
            'contract_version': self.contract_version,
            'step_quality_score': self.step_quality_score
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ExecutionContextSnapshot':
        """
        Десериализация из словаря.
        
        ARGS:
        - data: словарь с данными
        
        RETURNS:
        - ExecutionContextSnapshot: объект контекста
        """
        return cls(
            agent_id=data['agent_id'],
            session_id=data['session_id'],
            step_number=data['step_number'],
            timestamp=datetime.fromisoformat(data['timestamp']),
            available_capabilities=data.get('available_capabilities', []),
            selected_capability=data.get('selected_capability', ''),
            behavior_pattern=data.get('behavior_pattern', ''),
            reasoning=data.get('reasoning', ''),
            input_parameters=data.get('input_parameters', {}),
            output_result=data.get('output_result'),
            execution_time_ms=data.get('execution_time_ms', 0.0),
            tokens_used=data.get('tokens_used', 0),
            success=data.get('success', True),
            prompt_version=data.get('prompt_version', ''),
            contract_version=data.get('contract_version', ''),
            step_quality_score=data.get('step_quality_score')
        )
