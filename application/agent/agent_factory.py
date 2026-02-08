
from typing import Any, Optional
from application.agent.pattern_selector import IPatternSelector, SimplePatternSelector
from application.agent.patterns.patterns import ReActPattern
from application.agent.runtime import AgentRuntime
from application.thinking_patterns.composable.composable_pattern import PlanAndExecutePattern, ReflectionPattern, ToolUsePattern
from domain.abstractions.thinking_pattern import IThinkingPattern
from domain.models.domain_type import DomainType

class AgentFactory:
    """Фабрика для создания единого агента (AgentRuntime)"""
    
    def __init__(self, system_context: Any):
        self.system_context = system_context
    
    async def create_agent(
        self,
        agent_type: str = "default",  # Убрано "composable" — теперь только один тип
        domain: Optional[DomainType] = None,
        **kwargs
    ) -> AgentRuntime:
        """
        Создать ЕДИНСТВЕННЫЙ агент системы.
        
        Параметры:
        - agent_type: тип агента (в будущем — для специализированных агентов)
        - domain: целевой домен (опционально, определяется автоматически из задачи)
        """
        # 1. Создать сессию
        session = await self._create_session()
        
        # 2. Создать селектор паттернов
        pattern_selector = await self._create_pattern_selector()
        
        # 3. Получить зависимости из системного контекста
        prompt_repository = self.system_context.prompt_repository
        execution_gateway = session.execution_gateway
        skill_registry = self.system_context.skill_registry
        event_publisher = self.system_context.event_publisher
        
        # 4. Создать ЕДИНСТВЕННЫЙ агент
        agent = AgentRuntime(
            session_context=session,
            pattern_selector=pattern_selector,
            prompt_repository=prompt_repository,
            execution_gateway=execution_gateway,
            skill_registry=skill_registry,
            event_publisher=event_publisher,
            max_steps=kwargs.get("max_steps", 100)
        )
        
        return agent
    
    async def _create_pattern_selector(self) -> IPatternSelector:
        """Создать селектор паттернов с зарегистрированными паттернами"""
        # Получить паттерны из системного контекста или создать новые
        patterns = {
            "react": self._create_react_pattern(),
            "plan_and_execute": self._create_plan_and_execute_pattern(),
            "tool_use": self._create_tool_use_pattern(),
            "reflection": self._create_reflection_pattern()
        }
        return SimplePatternSelector(patterns)
    
    def _create_react_pattern(self) -> IThinkingPattern:
        return ReActPattern(max_iterations=10)
    
    def _create_plan_and_execute_pattern(self) -> IThinkingPattern:
        return PlanAndExecutePattern(max_iterations=10)
    
    def _create_tool_use_pattern(self) -> IThinkingPattern:
        return ToolUsePattern(max_iterations=10)
    
    def _create_reflection_pattern(self) -> IThinkingPattern:
        return ReflectionPattern(max_iterations=5)