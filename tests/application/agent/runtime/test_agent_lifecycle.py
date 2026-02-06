"""
Тесты жизненного цикла агента - ТОЛЬКО жизненный цикл
"""
import pytest
from unittest.mock import Mock, AsyncMock
from application.agent.runtime.runtime import AgentRuntime
from domain.abstractions.event_types import IEventPublisher
from domain.abstractions.thinking_pattern import IThinkingPattern
from domain.abstractions.gateways.i_execution_gateway import IExecutionGateway
from domain.abstractions.system.i_skill_registry import ISkillRegistry
from domain.models.agent.agent_state import AgentState


class TestAgentLifecycle:
    """Тесты жизненного цикла агента - ТОЛЬКО инициализация, запуск, завершение"""
    
    @pytest.fixture
    def mock_dependencies(self):
        """Создает заглушки для всех зависимостей агента"""
        return {
            'session_context': Mock(),
            'thinking_pattern': Mock(spec=IThinkingPattern),
            'execution_gateway': Mock(spec=IExecutionGateway),
            'skill_registry': Mock(spec=ISkillRegistry),
            'event_publisher': Mock(spec=IEventPublisher)
        }
    
    @pytest.mark.asyncio
    async def test_agent_initialization_creates_state(self, mock_dependencies):
        """Тест: инициализация создает состояние агента"""
        agent = AgentRuntime(**mock_dependencies)
        
        # Проверим, что состояние создано
        assert isinstance(agent.state, AgentState)
        assert agent.state.step == 0
        assert not agent._initialized
    
    @pytest.mark.asyncio
    async def test_agent_can_be_initialized_once(self, mock_dependencies):
        """Тест: повторная инициализация не создает новых ресурсов"""
        mock_dependencies['skill_registry'].get_all_skills = Mock(return_value={'test_capability': 'available'})
        
        agent = AgentRuntime(**mock_dependencies)
        
        # Первичная инициализация
        result1 = await agent.initialize()
        initial_state = agent._initialized
        
        # Повторная инициализация
        result2 = await agent.initialize()
        final_state = agent._initialized
        
        assert result1 is True
        assert result2 is True
        assert initial_state == final_state  # Не изменилось
    
    @pytest.mark.asyncio
    async def test_agent_lifecycle_initialize_run_shutdown(self, mock_dependencies):
        """Тест: полный жизненный цикл - инициализация → выполнение → завершение"""
        mock_dependencies['skill_registry'].get_all_skills = Mock(return_value={'test_capability': 'available'})
        mock_dependencies['thinking_pattern'].adapt_to_task = AsyncMock(return_value={'domain': 'test', 'confidence': 0.8})
        mock_dependencies['thinking_pattern'].execute = AsyncMock(return_value={'action': 'CONTINUE'})
        
        agent = AgentRuntime(**mock_dependencies, max_steps=1)
        
        # 1. Инициализация
        init_result = await agent.initialize()
        assert init_result is True
        assert agent._initialized is True
        
        # 2. Выполнение (короткое)
        run_result = await agent.run("test goal")
        assert run_result is not None
        
        # 3. Завершение
        await agent.shutdown()
        assert agent._initialized is False
    
    @pytest.mark.asyncio
    async def test_agent_shutdown_without_initialization(self, mock_dependencies):
        """Тест: завершение без предварительной инициализации не вызывает ошибок"""
        agent = AgentRuntime(**mock_dependencies)
        
        # Попробуем завершить без инициализации
        await agent.shutdown()
        
        # Не должно быть ошибок
        assert True
    
    @pytest.mark.asyncio
    async def test_agent_lifecycle_events_published(self, mock_dependencies):
        """Тест: события жизненного цикла публикуются корректно"""
        mock_dependencies['skill_registry'].get_all_skills = Mock(return_value={'test_capability': 'available'})
        mock_dependencies['event_publisher'].publish = AsyncMock()
        
        agent = AgentRuntime(**mock_dependencies)
        
        # Инициализация
        await agent.initialize()
        
        # Проверим, что событие инициализации было опубликовано
        mock_dependencies['event_publisher'].publish.assert_called()
        
        # Сброс моков для проверки завершения
        mock_dependencies['event_publisher'].publish.reset_mock()
        
        # Завершение
        await agent.shutdown()
        
        # Проверим, что событие завершения было опубликовано
        mock_dependencies['event_publisher'].publish.assert_called()
    
    @pytest.mark.asyncio
    async def test_agent_state_preserved_during_lifecycle(self, mock_dependencies):
        """Тест: состояние агента сохраняется в течение жизненного цикла"""
        mock_dependencies['skill_registry'].get_all_skills = Mock(return_value={'test_capability': 'available'})
        
        agent = AgentRuntime(**mock_dependencies)
        
        # Сохраним начальное состояние
        initial_state = agent.state
        
        # Инициализируем
        await agent.initialize()
        
        # Проверим, что состояние то же самое (не пересоздано)
        assert agent.state is initial_state
        
        # Завершим
        await agent.shutdown()
        
        # Состояние все еще должно быть тем же
        assert agent.state is initial_state
    
    @pytest.mark.asyncio
    async def test_agent_lifecycle_respects_max_steps(self, mock_dependencies):
        """Тест: жизненный цикл учитывает максимальное количество шагов"""
        mock_dependencies['skill_registry'].get_all_skills = Mock(return_value={'test_capability': 'available'})
        mock_dependencies['thinking_pattern'].adapt_to_task = AsyncMock(return_value={'domain': 'test', 'confidence': 0.8})
        mock_dependencies['thinking_pattern'].execute = AsyncMock(return_value={'action': 'CONTINUE'})
        
        max_steps = 3
        agent = AgentRuntime(**mock_dependencies, max_steps=max_steps)
        
        await agent.initialize()
        
        # Выполним несколько шагов
        await agent.run("test goal")
        
        # Проверим, что агент не превышает максимальное количество шагов
        assert agent.state.step <= max_steps