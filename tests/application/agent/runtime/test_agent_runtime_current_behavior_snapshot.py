"""
Снапшот текущего поведения — НЕ МЕНЯТЬ после создания
"""
import pytest
from application.agent.runtime import AgentRuntime


class TestAgentCurrentBehavior:
    """Снапшот текущего поведения — НЕ МЕНЯТЬ после создания"""
    
    def test_agent_runtime_basic_instantiation(self):
        """Фиксируем: базовая инициализация агента"""
        # Проверим, что агент создается без ошибок с необходимыми зависимостями
        from unittest.mock import Mock
        from domain.abstractions.thinking_pattern import IThinkingPattern
        
        runtime = AgentRuntime(
            session_context=Mock(),
            thinking_pattern=Mock(spec=IThinkingPattern),
            execution_gateway=Mock(),
            skill_registry=Mock(),
            event_publisher=Mock()
        )
        assert runtime is not None
    
    @pytest.mark.asyncio
    async def test_agent_runtime_methods_exist(self):
        """Фиксируем: существование методов агента"""
        from unittest.mock import Mock
        from domain.abstractions.thinking_pattern import IThinkingPattern
        
        runtime = AgentRuntime(
            session_context=Mock(),
            thinking_pattern=Mock(spec=IThinkingPattern),
            execution_gateway=Mock(),
            skill_registry=Mock(),
            event_publisher=Mock()
        )
        # Проверим, что методы существуют
        assert hasattr(runtime, "run")
        assert hasattr(runtime, "initialize")
        assert hasattr(runtime, "shutdown")
