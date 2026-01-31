from abc import ABC, abstractmethod
from typing import Union, TYPE_CHECKING, Dict, Any
from core.agent_runtime.runtime_interface import AgentRuntimeInterface

# Используем TYPE_CHECKING для предотвращения циклических импортов
if TYPE_CHECKING:
    from core.agent_runtime.execution_context import ExecutionContext
    from core.composable_patterns.base import ComposablePattern  # Добавляем импорт для новой архитектуры

from core.agent_runtime.model import StrategyDecision  # Импортируем для выполнения, не только для типизации


class AgentThinkingPatternInterface(ABC):
    """
    Базовый интерфейс паттерна мышления для новой архитектуры агента.
    
    Паттерн мышления:
    - анализирует состояние с учетом контекста задачи и домена
    - принимает решение о следующем действии
    - НЕ исполняет действия напрямую, а лишь определяет стратегию
    - может использовать компонуемые паттерны для построения сложного поведения
    """

    name: str

    @abstractmethod
    async def next_step(
        self,
        runtime: Union[AgentRuntimeInterface, 'ExecutionContext']
    ) -> StrategyDecision:
        """
        Вернуть решение на текущем шаге.
        
        В новой архитектуре этот метод может:
        - использовать атомарные действия для построения ответа
        - обращаться к реестру компонуемых паттернов
        - адаптировать поведение под домен задачи
        """
        pass

    def get_composable_pattern(self, pattern_name: str) -> 'ComposablePattern':
        """
        Получить компонуемый паттерн по имени из реестра.
        """
        from core.composable_patterns.registry import PatternRegistry
        registry = PatternRegistry()
        return registry.get_pattern(pattern_name)

    def adapt_to_domain(self, domain: str) -> Dict[str, Any]:
        """
        Адаптировать поведение паттерна под указанный домен.
        """
        from core.domain_management.domain_manager import DomainManager
        domain_manager = DomainManager()
        return domain_manager.get_domain_config(domain)
