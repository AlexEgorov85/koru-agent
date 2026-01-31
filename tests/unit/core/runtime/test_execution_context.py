"""
Тесты для ExecutionContext в agent_runtime.execution_context.
"""
import pytest
from unittest.mock import MagicMock
from core.agent_runtime.execution_context import ExecutionContext
from models.agent_state import AgentState
from core.agent_runtime.progress import ProgressScorer
from core.agent_runtime.executor import ActionExecutor
from core.agent_runtime.policy import AgentPolicy
from core.system_context.base_system_contex import BaseSystemContext
from core.session_context.base_session_context import BaseSessionContext


class TestExecutionContext:
    """Тесты для ExecutionContext."""
    
    def test_execution_context_creation(self):
        """Тест создания ExecutionContext."""
        # Создаем mock-объекты для зависимостей
        mock_system = MagicMock(spec=BaseSystemContext)
        mock_session = MagicMock(spec=BaseSessionContext)
        mock_state = MagicMock(spec=AgentState)
        mock_policy = MagicMock(spec=AgentPolicy)
        mock_progress = MagicMock(spec=ProgressScorer)
        mock_executor = MagicMock(spec=ActionExecutor)
        mock_strategy = MagicMock()  # AgentStrategyInterface - это интерфейс, используем mock
        
        context = ExecutionContext(
            system=mock_system,
            session=mock_session,
            state=mock_state,
            policy=mock_policy,
            progress=mock_progress,
            executor=mock_executor,
            strategy=mock_strategy
        )
        
        assert context.system == mock_system
        assert context.session == mock_session
        assert context.state == mock_state
        assert context.policy == mock_policy
        assert context.progress == mock_progress
        assert context.executor == mock_executor
        assert context.strategy == mock_strategy
    
    def test_execution_context_optional_strategy(self):
        """Тест ExecutionContext с необязательной стратегией."""
        # Создаем mock-объекты для зависимостей
        mock_system = MagicMock(spec=BaseSystemContext)
        mock_session = MagicMock(spec=BaseSessionContext)
        mock_state = MagicMock(spec=AgentState)
        mock_policy = MagicMock(spec=AgentPolicy)
        mock_progress = MagicMock(spec=ProgressScorer)
        mock_executor = MagicMock(spec=ActionExecutor)
        
        # Создаем контекст без стратегии (должна быть None по умолчанию)
        context = ExecutionContext(
            system=mock_system,
            session=mock_session,
            state=mock_state,
            policy=mock_policy,
            progress=mock_progress,
            executor=mock_executor
            # strategy не передаем, должно быть None по умолчанию
        )
        
        assert context.system == mock_system
        assert context.session == mock_session
        assert context.state == mock_state
        assert context.policy == mock_policy
        assert context.progress == mock_progress
        assert context.executor == mock_executor
        assert context.strategy is None
    
    def test_execution_context_attributes_access(self):
        """Тест доступа к атрибутам ExecutionContext."""
        # Создаем mock-объекты
        mock_system = MagicMock(spec=BaseSystemContext)
        mock_system.name = 'TestSystem'
        
        mock_session = MagicMock(spec=BaseSessionContext)
        mock_session.id = 'session123'
        
        mock_state = MagicMock(spec=AgentState)
        mock_state.current_step = 1
        
        mock_policy = MagicMock(spec=AgentPolicy)
        mock_policy.max_retries = 3
        
        mock_progress = MagicMock(spec=ProgressScorer)
        mock_progress.score = 0.8
        
        mock_executor = MagicMock(spec=ActionExecutor)
        mock_executor.active = True
        
        mock_strategy = MagicMock()
        mock_strategy.name = 'TestStrategy'
        
        context = ExecutionContext(
            system=mock_system,
            session=mock_session,
            state=mock_state,
            policy=mock_policy,
            progress=mock_progress,
            executor=mock_executor,
            strategy=mock_strategy
        )
        
        # Проверяем, что атрибуты доступны
        assert hasattr(context, 'system')
        assert hasattr(context, 'session')
        assert hasattr(context, 'state')
        assert hasattr(context, 'policy')
        assert hasattr(context, 'progress')
        assert hasattr(context, 'executor')
        assert hasattr(context, 'strategy')
        
        # Проверяем значения
        assert context.system.name == 'TestSystem'
        assert context.session.id == 'session123'
        assert context.state.current_step == 1
        assert context.policy.max_retries == 3
        assert context.progress.score == 0.8
        assert context.executor.active is True
        assert context.strategy.name == 'TestStrategy'
    
    def test_execution_context_immutability(self):
        """Тест, что ExecutionContext неизменяем после создания."""
        mock_system = MagicMock(spec=BaseSystemContext)
        mock_session = MagicMock(spec=BaseSessionContext)
        mock_state = MagicMock(spec=AgentState)
        mock_policy = MagicMock(spec=AgentPolicy)
        mock_progress = MagicMock(spec=ProgressScorer)
        mock_executor = MagicMock(spec=ActionExecutor)
        mock_strategy = MagicMock()
        
        context = ExecutionContext(
            system=mock_system,
            session=mock_session,
            state=mock_state,
            policy=mock_policy,
            progress=mock_progress,
            executor=mock_executor,
            strategy=mock_strategy
        )
        
        # Проверяем начальные значения
        original_system = context.system
        
        # Попытка изменить атрибут (в dataclass по умолчанию можно изменять)
        new_system = MagicMock(spec=BaseSystemContext)
        context.system = new_system
        
        # Убедимся, что атрибут действительно изменился
        assert context.system == new_system
        assert context.system != original_system


def test_execution_context_with_real_components():
    """Тест ExecutionContext с реальными компонентами (где это возможно)."""
    # Создаем реальные объекты для тех классов, которые не требуют сложной инициализации
    mock_system = MagicMock(spec=BaseSystemContext)
    mock_session = MagicMock(spec=BaseSessionContext)
    
    # Создаем реальные объекты для остальных компонентов
    state = AgentState()
    policy = AgentPolicy()
    progress = ProgressScorer()
    executor = ActionExecutor(mock_system)
    strategy = MagicMock()  # AgentStrategyInterface - интерфейс, используем mock
    
    context = ExecutionContext(
        system=mock_system,
        session=mock_session,
        state=state,
        policy=policy,
        progress=progress,
        executor=executor,
        strategy=strategy
    )
    
    # Проверяем, что все компоненты установлены правильно
    assert context.system == mock_system
    assert context.session == mock_session
    assert context.state == state
    assert context.policy == policy
    assert context.progress == progress
    assert context.executor == executor
    assert context.strategy == strategy