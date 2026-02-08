"""
Снапшот текущего поведения — НЕ МЕНЯТЬ после создания
"""
import pytest
from unittest.mock import Mock, AsyncMock
from application.agent.runtime import AgentRuntime
from domain.abstractions.event_types import IEventPublisher
from domain.abstractions.thinking_pattern import IThinkingPattern
from domain.abstractions.gateways.i_execution_gateway import IExecutionGateway
from domain.abstractions.system.i_skill_registry import ISkillRegistry


class TestAgentSnapshot:
    """Снапшот текущего поведения — НЕ МЕНЯТЬ после создания"""
    
    @pytest.mark.asyncio
    async def test_agent_run_returns_result_on_success(self):
        """Фиксируем: успешное выполнение возвращает результат"""
        # Подготовим моки зависимостей
        session_context = Mock()
        thinking_pattern = Mock(spec=IThinkingPattern)
        execution_gateway = Mock(spec=IExecutionGateway)
        skill_registry = Mock(spec=ISkillRegistry)
        event_publisher = Mock(spec=IEventPublisher)
        
        # Настроим возвращаемые значения
        skill_registry.get_all_skills = Mock(return_value={'test_capability': 'available'})
        skill_registry.get_capability_names = AsyncMock(return_value=['test_capability'])
        thinking_pattern.adapt_to_task = AsyncMock(return_value={'domain': 'test', 'confidence': 0.8})
        thinking_pattern.execute = AsyncMock(return_value={'action': 'CONTINUE'})
        
        # Создадим агента
        agent = AgentRuntime(
            session_context=session_context,
            thinking_pattern=thinking_pattern,
            execution_gateway=execution_gateway,
            skill_registry=skill_registry,
            event_publisher=event_publisher,
            max_steps=1
        )
        
        # Выполним задачу
        result = await agent.run("test goal")
        
        # Проверим, что результат возвращается
        assert result is not None
        assert hasattr(result, 'status')
        assert hasattr(result, 'result')
    
    @pytest.mark.asyncio
    async def test_agent_stops_after_max_steps(self):
        """Фиксируем: агент останавливается после достижения max_steps"""
        # Подготовим моки зависимостей
        session_context = Mock()
        thinking_pattern = Mock(spec=IThinkingPattern)
        execution_gateway = Mock(spec=IExecutionGateway)
        skill_registry = Mock(spec=ISkillRegistry)
        event_publisher = Mock(spec=IEventPublisher)
        
        # Настроим возвращаемые значения
        skill_registry.get_all_skills = Mock(return_value={'test_capability': 'available'})
        skill_registry.get_capability_names = AsyncMock(return_value=['test_capability'])
        thinking_pattern.adapt_to_task = AsyncMock(return_value={'domain': 'test', 'confidence': 0.8})
        thinking_pattern.execute = AsyncMock(return_value={'action': 'CONTINUE'})
        
        # Создадим агента с максимальным количеством шагов 2
        max_steps = 2
        agent = AgentRuntime(
            session_context=session_context,
            thinking_pattern=thinking_pattern,
            execution_gateway=execution_gateway,
            skill_registry=skill_registry,
            event_publisher=event_publisher,
            max_steps=max_steps
        )
        
        # Выполним задачу
        result = await agent.run("test goal")
        
        # Проверим, что агент не превышает максимальное количество шагов
        assert agent.state.step <= max_steps
    
    @pytest.mark.asyncio
    async def test_agent_initialize_returns_boolean(self):
        """Фиксируем: метод initialize возвращает boolean"""
        # Подготовим моки зависимостей
        session_context = Mock()
        thinking_pattern = Mock(spec=IThinkingPattern)
        execution_gateway = Mock(spec=IExecutionGateway)
        skill_registry = Mock(spec=ISkillRegistry)
        event_publisher = Mock(spec=IEventPublisher)
        
        # Настроим возвращаемые значения
        skill_registry.get_all_skills = Mock(return_value={'test_capability': 'available'})
        
        # Создадим агента
        agent = AgentRuntime(
            session_context=session_context,
            thinking_pattern=thinking_pattern,
            execution_gateway=execution_gateway,
            skill_registry=skill_registry,
            event_publisher=event_publisher
        )
        
        # Вызовем инициализацию
        result = await agent.initialize()
        
        # Проверим, что возвращается boolean
        assert isinstance(result, bool)
    
    @pytest.mark.asyncio
    async def test_agent_shutdown_completes_without_error(self):
        """Фиксируем: метод shutdown завершается без ошибок"""
        # Подготовим моки зависимостей
        session_context = Mock()
        thinking_pattern = Mock(spec=IThinkingPattern)
        execution_gateway = Mock(spec=IExecutionGateway)
        skill_registry = Mock(spec=ISkillRegistry)
        event_publisher = Mock(spec=IEventPublisher)
        
        # Настроим возвращаемые значения
        skill_registry.get_all_skills = Mock(return_value={'test_capability': 'available'})
        
        # Создадим агента
        agent = AgentRuntime(
            session_context=session_context,
            thinking_pattern=thinking_pattern,
            execution_gateway=execution_gateway,
            skill_registry=skill_registry,
            event_publisher=event_publisher
        )
        
        # Инициализируем агента
        await agent.initialize()
        
        # Вызовем shutdown
        await agent.shutdown()
        
        # Проверим, что флаг инициализации сброшен
        assert agent._initialized is False
    
    @pytest.mark.asyncio
    async def test_agent_handles_empty_capabilities_gracefully(self):
        """Фиксируем: агент корректно обрабатывает отсутствие возможностей"""
        # Подготовим моки зависимостей
        session_context = Mock()
        thinking_pattern = Mock(spec=IThinkingPattern)
        execution_gateway = Mock(spec=IExecutionGateway)
        skill_registry = Mock(spec=ISkillRegistry)
        event_publisher = Mock(spec=IEventPublisher)
        
        # Настроим возвращаемые значения - нет возможностей
        skill_registry.get_all_skills = Mock(return_value={})
        
        # Создадим агента
        agent = AgentRuntime(
            session_context=session_context,
            thinking_pattern=thinking_pattern,
            execution_gateway=execution_gateway,
            skill_registry=skill_registry,
            event_publisher=event_publisher
        )
        
        # Попробуем инициализировать агента
        result = await agent.initialize()
        
        # Проверим, что инициализация возвращает False при отсутствии возможностей
        assert result is False