"""
Чистая реализация ComposableAgentInterface для работы с компонуемыми паттернами мышления агента.
"""

from typing import Any, Dict, Optional, List
from core.agent_runtime.interfaces import ComposableAgentInterface
from core.atomic_actions.base import AtomicAction
from core.atomic_actions.executor import AtomicActionExecutor
from core.composable_patterns.base import ComposablePattern
from core.agent_runtime.runtime_interface import AgentRuntimeInterface
from core.agent_runtime.model import StrategyDecision, StrategyDecisionType
from core.session_context.session_context import SessionContext
from core.system_context.system_context import SystemContext
from core.domain_management.domain_manager import DomainManager


class ComposableAgent(ComposableAgentInterface):
    """
    Чистая реализация ComposableAgentInterface.
    
    Агент, который поддерживает компонуемые паттерны мышления, позволяя
    динамически собирать и выполнять сложные поведения из атомарных действий.
    
    Примеры использования:
        # Создание агента
        agent = ComposableAgent("MyAgent", "Agent for processing tasks")
        
        # Выполнение атомарного действия
        result = await agent.execute_atomic_action(think_action, context, {"param": "value"})
        
        # Выполнение компонуемого паттерна
        result = await agent.execute_composable_pattern(pattern, context, {"param": "value"})
        
        # Адаптация к домену
        agent.adapt_to_domain("software_development")
    """
    
    def __init__(self, name: str, description: str = "", runtime: Optional[AgentRuntimeInterface] = None):
        """
        Инициализирует компонуемого агента.
        
        Args:
            name: Имя агента
            description: Описание агента
            runtime: Внешний объект среды выполнения (опционально)
        """
        self.name = name
        self.description = description
        self.domains: List[str] = []
        self.runtime: Optional[AgentRuntimeInterface] = runtime
        self.domain_manager = DomainManager()
        self.context: Any = None
        self._available_domains: List[str] = [
            "general", "code_analysis", "database_query", 
            "research", "planning", "problem_solving", "data_analysis"
        ]
    
    async def execute_atomic_action(
        self,
        action: AtomicAction,
        context: Any,
        parameters: Optional[Dict[str, Any]] = None
    ) -> StrategyDecision:
        """
        Выполняет атомарное действие.
        
        Args:
            action: Атомарное действие для выполнения
            context: Контекст выполнения
            parameters: Дополнительные параметры для действия
            
        Returns:
            StrategyDecision: Решение стратегии после выполнения действия
        """
        if not isinstance(action, AtomicAction):
            raise TypeError(f"Expected AtomicAction, got {type(action)}")
        
        # Убедимся, что у нас есть runtime для выполнения действия
        if not self.runtime:
            from core.agent_runtime.runtime import AgentRuntime
            from core.system_context.system_context import SystemContext
            from core.session_context.session_context import SessionContext
            self.runtime = AgentRuntime(SystemContext(), SessionContext())
        
        # Выполняем атомарное действие через его метод execute
        result = await action.execute(self.runtime, context, parameters)
        return result
    
    async def execute_atomic_action_with_full_lifecycle(
        self,
        action: AtomicAction,
        context: Any,
        parameters: Optional[Dict[str, Any]] = None
    ) -> StrategyDecision:
        """
        Выполняет атомарное действие с полным жизненным циклом, используя AtomicActionExecutor.
        Этот метод обеспечивает полную обработку атомарного действия, включая подготовку контекста,
        логирование, обработку ошибок и интеграцию с системой принятия решений агента.
        
        Args:
            action: Атомарное действие для выполнения
            context: Контекст выполнения
            parameters: Дополнительные параметры для действия
            
        Returns:
            StrategyDecision: Решение стратегии после выполнения действия с полным жизненным циклом
        """
        if not isinstance(action, AtomicAction):
            raise TypeError(f"Expected AtomicAction, got {type(action)}")
        
        # Убедимся, что у нас есть runtime для выполнения действия
        if not self.runtime:
            from core.agent_runtime.runtime import AgentRuntime
            from core.system_context.system_context import SystemContext
            from core.session_context.session_context import SessionContext
            self.runtime = AgentRuntime(SystemContext(), SessionContext())
        
        # Создаем исполнителя атомарных действий с полным жизненным циклом
        executor = AtomicActionExecutor(self.runtime)
        return await executor.execute_atomic_action(action, context, parameters)
    
    
    async def execute_composable_pattern(
        self,
        pattern: ComposablePattern,
        context: Any,
        parameters: Optional[Dict[str, Any]] = None
    ) -> StrategyDecision:
        """
        Выполняет компонуемый паттерн.
        
        Args:
            pattern: Компонуемый паттерн для выполнения
            context: Контекст выполнения
            parameters: Дополнительные параметры для паттерна
            
        Returns:
            StrategyDecision: Решение стратегии после выполнения паттерна
        """
        if not isinstance(pattern, ComposablePattern):
            raise TypeError(f"Expected ComposablePattern, got {type(pattern)}")
        
        # Убедимся, что у нас есть runtime для выполнения паттерна
        if not self.runtime:
            from core.agent_runtime.runtime import AgentRuntime
            from core.system_context.system_context import SystemContext
            from core.session_context.session_context import SessionContext
            self.runtime = AgentRuntime(SystemContext(), SessionContext())
        
        # Выполняем компонуемый паттерн через его метод execute
        result = await pattern.execute(self.runtime, context, parameters)
        return result
    
    def adapt_to_domain(self, domain: str) -> None:
        """
        Адаптирует агента к конкретному домену.
        
        Args:
            domain: Название домена, к которому адаптируется агент
        """
        if domain not in self._available_domains:
            raise ValueError(f"Domain '{domain}' is not supported. Available domains: {self._available_domains}")
        
        # Добавляем домен в список адаптированных доменов
        if domain not in self.domains:
            self.domains.append(domain)
        
        # Если домен не зарегистрирован в DomainManager, регистрируем его как общий
        if domain not in self.domain_manager.get_available_domains():
            default_config = {
                "name": f"{domain.replace('_', ' ').title()} Domain",
                "description": f"Domain for {domain.replace('_', ' ')} tasks",
                "default_pattern": "react",
                "tools": ["file_reader", "file_writer", "project_navigator"],
                "prompt_templates": {
                    "system": f"You are an assistant for {domain.replace('_', ' ')} tasks.",
                    "user": f"Help with {domain.replace('_', ' ')} task: {{query}}"
                }
            }
            self.domain_manager.register_domain(domain, default_config)
        
        # Адаптируем доменный менеджер
        self.domain_manager.set_current_domain(domain)
    
    def get_available_domains(self) -> List[str]:
        """
        Получает список доступных доменов.
        
        Returns:
            list[str]: Список доступных доменов
        """
        return self._available_domains.copy()


class SimpleComposableAgent(ComposableAgent):
    """
    Упрощенная реализация компонуемого агента с дополнительными удобствами.
    
    Примеры использования:
        # Создание простого агента
        agent = SimpleComposableAgent("SimpleAgent", "Simple agent for basic tasks")
        agent.adapt_to_domain("general")
        
        # Создание и выполнение простого паттерна
        pattern = (PatternBuilder("simple_pattern")
                  .add_think()
                  .add_act()
                  .build())
        result = await agent.execute_composable_pattern(pattern, context)
    """
    
    def __init__(self, name: str, description: str = "", initial_domain: Optional[str] = None, runtime: Optional[AgentRuntimeInterface] = None):
        super().__init__(name, description, runtime)
        if initial_domain:
            self.adapt_to_domain(initial_domain)
    
    async def simple_execute(
        self,
        actions_or_pattern: Any,
        context: Any,
        parameters: Optional[Dict[str, Any]] = None
    ) -> StrategyDecision:
        """
        Упрощенное выполнение - автоматически определяет, что нужно выполнить:
        атомарное действие или компонуемый паттерн.
        
        Args:
            actions_or_pattern: Атомарное действие или компонуемый паттерн
            context: Контекст выполнения
            parameters: Дополнительные параметры
            
        Returns:
            StrategyDecision: Результат выполнения
        """
        if isinstance(actions_or_pattern, AtomicAction):
            return await self.execute_atomic_action(actions_or_pattern, context, parameters)
        elif isinstance(actions_or_pattern, ComposablePattern):
            return await self.execute_composable_pattern(actions_or_pattern, context, parameters)
        else:
            raise TypeError(f"Expected AtomicAction or ComposablePattern, got {type(actions_or_pattern)}")