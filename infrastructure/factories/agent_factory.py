"""
AgentFactory - фабрика для создания агентов с инъекцией зависимостей.

АРХИТЕКТУРА:
- Pattern: Factory
- Создает экземпляры агентов с необходимыми зависимостями
- Обеспечивает инъекцию системного контекста, шины событий и других компонентов
"""
from typing import Any, Optional
from application.context.system.system_context import SystemContext
from infrastructure.gateways.event_system import EventSystem
from application.agent.runtime.runtime import AgentRuntime
from application.agent.composable_patterns.patterns import ReActPattern, PlanAndExecutePattern, ToolUsePattern, ReflectionPattern
from domain.abstractions.thinking_pattern import IThinkingPattern
from application.context.session.session_context import SessionContext
from domain.abstractions.event_types import IEventPublisher
from domain.abstractions.gateways.i_execution_gateway import IExecutionGateway
from domain.abstractions.system.i_skill_registry import ISkillRegistry
from infrastructure.adapters.event_publisher_adapter import EventPublisherAdapter


class AgentFactory:
    """
    Фабрика агентов - создает экземпляры агентов с инъекцией зависимостей.

    ОТВЕТСТВЕННОСТЬ:
    - Создание агентов с нужными зависимостями
    - Инъекция системного контекста, шины событий и других компонентов
    """

    def __init__(self, system_context: SystemContext, event_system: EventSystem):
        """
        Инициализация фабрики агентов.

        ПАРАМЕТРЫ:
        - system_context: Системный контекст (реестр компонентов)
        - event_system: Шина событий (один экземпляр на систему)
        """
        self.system_context = system_context
        self.event_system = event_system

    async def create_agent(
        self,
        agent_type: str = "composable",
        domain: Optional[str] = None,
        **kwargs
    ) -> AgentRuntime:
        # 1. Создаем инфраструктурные компоненты ВНУТРИ фабрики (скрыто)
        # system_context already provided in constructor
        
        # 2. Создаем ПОРТЫ через инфраструктурные фабрики
        from infrastructure.factories.execution_gateway_factory import ExecutionGatewayFactory
        from infrastructure.factories.pattern_executor_factory import PatternExecutorFactory
        
        execution_gateway = ExecutionGatewayFactory.create_execution_gateway(
            skill_registry=self.system_context.get_skill_registry(),
            event_publisher=EventPublisherAdapter(self.event_system) if self.event_system else None
        )
        
        # Создаем PromptRenderer через инфраструктурную фабрику
        from infrastructure.services.prompt_storage.file_prompt_repository import FilePromptRepository
        from application.services.prompt_renderer import PromptRenderer
        from infrastructure.services.prompt_storage.prompt_loader import PromptLoader
        
        prompt_repository = FilePromptRepository()
        prompt_renderer = PromptRenderer(
            prompt_repository=prompt_repository,
            snapshot_manager=None  # Можно добавить snapshot manager позже
        )
        
        pattern_executor = PatternExecutorFactory.create_pattern_executor(
            prompt_renderer=prompt_renderer,
            llm_provider=getattr(self.system_context, '_llm_provider', None),
            event_publisher=EventPublisherAdapter(self.event_system) if self.event_system else None
        )
        
        event_publisher = EventPublisherAdapter(self.event_system)  # Convert event_system to IEventPublisher
        skill_registry = self.system_context.get_skill_registry()
        
        # 3. Создаем паттерн мышления (теперь это Composable Pattern, использующий Atomic Actions)
        thinking_pattern = self._create_thinking_pattern(agent_type, domain, kwargs)
        
        # 4. Создаем контекст сессии (ТОЛЬКО данные)
        session_context = SessionContext(
            session_id=kwargs.get("session_id", "default_session"),
            user_id=kwargs.get("user_id"),
            goal=kwargs.get("goal", "Без цели"),
            metadata=kwargs.get("meta", {})
        )
        
        # 5. Создаем агента с инъекцией ПОРТОВ (НЕ инфраструктуры!)
        agent = AgentRuntime(
            session_context=session_context,
            thinking_pattern=thinking_pattern,
            pattern_executor=pattern_executor,      # ← НОВЫЙ ПОРТ
            execution_gateway=execution_gateway,  # ← ПОРТ
            skill_registry=skill_registry,        # ← ПОРТ
            event_publisher=event_publisher,      # ← ПОРТ
            max_steps=kwargs.get("max_steps", 10)
        )
        
        return agent

    def _create_thinking_pattern(self, agent_type: str, domain: Optional[str], kwargs: dict) -> IThinkingPattern:
        """Create the appropriate thinking pattern based on agent type."""
        # Composable Patterns больше не принимают инфраструктурные компоненты напрямую
        # Они используют только доменные параметры

        if agent_type.lower() == "react":
            return ReActPattern(
                max_iterations=kwargs.get("max_iterations", 10)
            )
        elif agent_type.lower() == "plan_and_execute":
            return PlanAndExecutePattern(
                max_iterations=kwargs.get("max_iterations", 10)
            )
        elif agent_type.lower() == "tool_use":
            return ToolUsePattern(
                max_iterations=kwargs.get("max_iterations", 10)
            )
        elif agent_type.lower() == "reflection":
            return ReflectionPattern(
                max_iterations=kwargs.get("max_iterations", 10)
            )
        else:
            # Default to ReAct pattern for composable agents
            return ReActPattern(
                max_iterations=kwargs.get("max_iterations", 10)
            )