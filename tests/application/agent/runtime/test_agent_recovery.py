"""
Тесты восстановления агента - ТОЛЬКО восстановление
"""
import pytest
from unittest.mock import Mock, AsyncMock
from application.coordination.pattern_recovery_manager import PatternRecoveryManager
from application.to_infrastructure.runtime.runtime import AgentRuntime
from domain.abstractions.event_types import IEventPublisher
from domain.abstractions.gateways.i_execution_gateway import IExecutionGateway
from domain.abstractions.system.i_skill_registry import ISkillRegistry
from domain.models.execution.execution_result import ExecutionResult
from domain.models.execution.execution_status import ExecutionStatus


class MockSessionContext:
    """Мок сессионного контекста для тестов восстановления"""
    def __init__(self, session_id="recovery_test_session"):
        self.session_id = session_id
        self.data = {}
    
    def set_session_data(self, key, value):
        self.data[key] = value
    
    def get_session_data(self, key, default=None):
        return self.data.get(key, default)


class TestAgentRecovery:
    """Тесты восстановления агента - ТОЛЬКО восстановление после ошибок"""
    
    @pytest.fixture
    def mock_session_context(self):
        """Создает мок сессионного контекста"""
        return MockSessionContext()
    
    @pytest.fixture
    def mock_execution_gateway(self):
        """Создает мок шлюза выполнения"""
        gateway = Mock(spec=IExecutionGateway)
        gateway.execute_action = AsyncMock(return_value=ExecutionResult(
            status=ExecutionStatus.SUCCESS,
            result="executed",
            observation_item_id="test_observation",
            summary="Test execution result"
        ))
        return gateway
    
    @pytest.fixture
    def mock_skill_registry(self):
        """Создает мок реестра навыков"""
        registry = Mock(spec=ISkillRegistry)
        registry.get_all_skills = Mock(return_value={'test_capability': 'available'})
        registry.get_capability_names = AsyncMock(return_value=['test_capability'])
        return registry
    
    @pytest.fixture
    def mock_event_publisher(self):
        """Создает мок паблишера событий"""
        publisher = Mock(spec=IEventPublisher)
        publisher.publish = AsyncMock()
        return publisher
    
    @pytest.fixture
    def basic_thinking_pattern(self):
        """Создает базовый паттерн мышления"""
        # Используем существующий ReActPattern из оркестрации
        from application.orchestration.patterns.patterns import ReActPattern
        from domain.abstractions.prompt_renderer import IPromptRenderer
        from domain.abstractions.system_initialization_service import ISystemInitializationService
        
        # Создаем моки для зависимостей
        mock_prompt_renderer = Mock(spec=IPromptRenderer)
        mock_system_init_service = Mock(spec=ISystemInitializationService)
        
        pattern = ReActPattern(
            prompt_renderer=mock_prompt_renderer,
            system_initialization_service=mock_system_init_service
        )
        # Мокаем метод execute, чтобы контролировать поведение
        pattern.execute = AsyncMock(return_value={'action': 'CONTINUE', 'thought': 'Continuing'})
        pattern.adapt_to_task = AsyncMock(return_value={'domain': 'test', 'confidence': 0.8, 'parameters': {}})
        return pattern
    
    @pytest.mark.asyncio
    async def test_agent_can_set_recovery_manager_dependency(
        self,
        mock_session_context,
        mock_execution_gateway,
        mock_skill_registry,
        mock_event_publisher,
        basic_thinking_pattern
    ):
        """Тест: агент может установить менеджер восстановления через setter"""
        agent = AgentRuntime(
            session_context=mock_session_context,
            thinking_pattern=basic_thinking_pattern,
            execution_gateway=mock_execution_gateway,
            skill_registry=mock_skill_registry,
            event_publisher=mock_event_publisher
        )
        
        # Создаем мок recovery manager
        recovery_manager = Mock(spec=PatternRecoveryManager)
        recovery_manager.fallback_to_safe_pattern = AsyncMock(return_value=True)
        
        # Устанавливаем recovery manager
        agent.set_recovery_manager(recovery_manager)
        
        # Проверяем, что recovery manager установлен
        assert agent.recovery_manager is recovery_manager
    
    @pytest.mark.asyncio
    async def test_agent_handles_error_with_recovery_manager(
        self,
        mock_session_context,
        mock_execution_gateway,
        mock_skill_registry,
        mock_event_publisher,
        basic_thinking_pattern
    ):
        """Тест: агент обрабатывает ошибку с использованием recovery manager"""
        agent = AgentRuntime(
            session_context=mock_session_context,
            thinking_pattern=basic_thinking_pattern,
            execution_gateway=mock_execution_gateway,
            skill_registry=mock_skill_registry,
            event_publisher=mock_event_publisher
        )
        
        # Создаем мок recovery manager
        recovery_manager = Mock(spec=PatternRecoveryManager)
        recovery_manager.fallback_to_safe_pattern = AsyncMock(return_value=True)
        
        # Устанавливаем recovery manager
        agent.set_recovery_manager(recovery_manager)
        
        # Мокаем паттерн мышления, чтобы он выбросил ошибку
        original_execute = basic_thinking_pattern.execute
        basic_thinking_pattern.execute = AsyncMock(side_effect=Exception("Test error"))
        
        # Запускаем агента - он должен обработать ошибку
        result = await agent.run("Test goal")
        
        # Проверяем, что recovery manager был вызван
        recovery_manager.fallback_to_safe_pattern.assert_called_once()
        
        # Восстанавливаем оригинальный метод
        basic_thinking_pattern.execute = original_execute
    
    @pytest.mark.asyncio
    async def test_agent_continues_after_recovery(
        self,
        mock_session_context,
        mock_execution_gateway,
        mock_skill_registry,
        mock_event_publisher,
        basic_thinking_pattern
    ):
        """Тест: агент продолжает выполнение после восстановления"""
        agent = AgentRuntime(
            session_context=mock_session_context,
            thinking_pattern=basic_thinking_pattern,
            execution_gateway=mock_execution_gateway,
            skill_registry=mock_skill_registry,
            event_publisher=mock_event_publisher,
            max_steps=2
        )
        
        # Создаем мок recovery manager
        recovery_manager = Mock(spec=PatternRecoveryManager)
        recovery_manager.fallback_to_safe_pattern = AsyncMock(return_value=True)
        
        # Устанавливаем recovery manager
        agent.set_recovery_manager(recovery_manager)
        
        # Мокаем паттерн мышления, чтобы он выбросил ошибку только первый раз
        call_count = 0
        async def conditional_error_execute(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Test error")
            else:
                return {'action': 'CONTINUE', 'thought': 'Continuing after recovery'}
        
        basic_thinking_pattern.execute = AsyncMock(side_effect=conditional_error_execute)
        
        # Запускаем агента
        result = await agent.run("Test goal")
        
        # Проверяем, что recovery manager был вызван
        recovery_manager.fallback_to_safe_pattern.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_agent_handles_recovery_failure_gracefully(
        self,
        mock_session_context,
        mock_execution_gateway,
        mock_skill_registry,
        mock_event_publisher,
        basic_thinking_pattern
    ):
        """Тест: агент корректно обрабатывает ошибку при восстановлении"""
        agent = AgentRuntime(
            session_context=mock_session_context,
            thinking_pattern=basic_thinking_pattern,
            execution_gateway=mock_execution_gateway,
            skill_registry=mock_skill_registry,
            event_publisher=mock_event_publisher
        )
        
        # Создаем мок recovery manager, который выбрасывает ошибку
        recovery_manager = Mock(spec=PatternRecoveryManager)
        recovery_manager.fallback_to_safe_pattern = AsyncMock(side_effect=Exception("Recovery error"))
        
        # Устанавливаем recovery manager
        agent.set_recovery_manager(recovery_manager)
        
        # Мокаем паттерн мышления, чтобы он выбросил ошибку
        basic_thinking_pattern.execute = AsyncMock(side_effect=Exception("Test error"))
        
        # Запускаем агента - он должен обработать ошибку восстановления
        result = await agent.run("Test goal")
        
        # Проверяем, что результат отражает ошибку
        assert result is not None
        
        # Проверяем, что recovery manager был вызван
        recovery_manager.fallback_to_safe_pattern.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_agent_without_recovery_manager_handles_errors_normally(
        self,
        mock_session_context,
        mock_execution_gateway,
        mock_skill_registry,
        mock_event_publisher,
        basic_thinking_pattern
    ):
        """Тест: агент без recovery manager обрабатывает ошибки нормально"""
        agent = AgentRuntime(
            session_context=mock_session_context,
            thinking_pattern=basic_thinking_pattern,
            execution_gateway=mock_execution_gateway,
            skill_registry=mock_skill_registry,
            event_publisher=mock_event_publisher
        )
        
        # Убедимся, что recovery manager не установлен
        assert agent.recovery_manager is None
        
        # Мокаем паттерн мышления, чтобы он выбросил ошибку
        basic_thinking_pattern.execute = AsyncMock(side_effect=Exception("Test error"))
        
        # Запускаем агента - он должен завершиться с ошибкой
        result = await agent.run("Test goal")
        
        # Проверяем, что результат отражает ошибку
        assert result.status == ExecutionStatus.FAILED
        assert "Критическая ошибка" in result.result
    
    @pytest.mark.asyncio
    async def test_recovery_manager_fallback_method_called_correctly(
        self,
        mock_session_context,
        mock_execution_gateway,
        mock_skill_registry,
        mock_event_publisher,
        basic_thinking_pattern
    ):
        """Тест: метод fallback_to_safe_pattern вызывается с правильными аргументами"""
        agent = AgentRuntime(
            session_context=mock_session_context,
            thinking_pattern=basic_thinking_pattern,
            execution_gateway=mock_execution_gateway,
            skill_registry=mock_skill_registry,
            event_publisher=mock_event_publisher
        )
        
        # Создаем мок recovery manager
        recovery_manager = Mock(spec=PatternRecoveryManager)
        recovery_manager.fallback_to_safe_pattern = AsyncMock(return_value=True)
        
        # Устанавливаем recovery manager
        agent.set_recovery_manager(recovery_manager)
        
        # Мокаем паттерн мышления, чтобы он выбросил ошибку
        basic_thinking_pattern.execute = AsyncMock(side_effect=Exception("Test error"))
        
        # Запускаем агента
        result = await agent.run("Test goal")
        
        # Проверяем, что метод был вызван с правильными аргументами
        recovery_manager.fallback_to_safe_pattern.assert_called_once_with(agent, basic_thinking_pattern.name)