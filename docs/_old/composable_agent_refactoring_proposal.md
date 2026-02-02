# Предложение по рефакторингу ComposableAgent

## Текущая проблема

Файл `core/composable_agent.py` нарушает принцип единственной ответственности (SRP), так как объединяет в себе:
- Основную логику агента
- Управление доменами
- Выполнение атомарных действий
- Выполнение компонуемых паттернов
- Управление контекстом выполнения

## Предлагаемое разбиение

### 1. Основной агент (остается в Application слое)

Файл: `core/application/agents/composable_agent.py`

Содержит только основную логику агента, управление доменами и базовые методы взаимодействия с другими компонентами. Убираем создание зависимостей внутрь методов, вместо этого внедряем их через конструктор или метод установки.

```python
from typing import Any, Dict, Optional, List
from core.agent_runtime.interfaces import ComposableAgentInterface
from core.atomic_actions.base import AtomicAction
from core.composable_patterns.base import ComposablePattern
from core.agent_runtime.runtime_interface import AgentRuntimeInterface
from core.domain_management.domain_manager import DomainManager

class ComposableAgent(ComposableAgentInterface):
    """
    Основной класс компонуемого агента с минимальной ответственностью.
    """
    
    def __init__(
        self, 
        name: str, 
        description: str = "",
        runtime: AgentRuntimeInterface,
        domain_manager: DomainManager,
        atomic_action_executor: 'AtomicActionExecutor',
        pattern_executor: 'PatternExecutor'
    ):
        self.name = name
        self.description = description
        self.domains: List[str] = []
        self.runtime = runtime
        self.domain_manager = domain_manager
        self.atomic_action_executor = atomic_action_executor
        self.pattern_executor = pattern_executor
        self._available_domains: List[str] = [
            "general", "code_analysis", "database_query", 
            "research", "planning", "problem_solving", "data_analysis"
        ]
    
    async def execute_atomic_action(
        self,
        action: AtomicAction,
        context: Any,
        parameters: Optional[Dict[str, Any]] = None
    ) -> Any:
        """Выполняет атомарное действие через внедренный executor."""
        return await self.atomic_action_executor.execute(action, context, parameters)
    
    async def execute_composable_pattern(
        self,
        pattern: ComposablePattern,
        context: Any,
        parameters: Optional[Dict[str, Any]] = None
    ) -> Any:
        """Выполняет компонуемый паттерн через внедренный executor."""
        return await self.pattern_executor.execute(pattern, context, parameters)
    
    def adapt_to_domain(self, domain: str) -> None:
        """Адаптирует агента к конкретному домену."""
        if domain not in self._available_domains:
            raise ValueError(f"Domain '{domain}' is not supported. Available domains: {self._available_domains}")
        
        if domain not in self.domains:
            self.domains.append(domain)
        self.domain_manager.set_current_domain(domain)
    
    def get_available_domains(self) -> List[str]:
        """Получает список доступных доменов."""
        return self._available_domains.copy()
```

### 2. Исполнитель атомарных действий (переходит из Application в Infrastructure слой)

Файл: `core/infrastructure/executors/atomic_action_executor.py`

Отдельный класс, отвечающий только за выполнение атомарных действий, с полным жизненным циклом.

```python
from typing import Any, Dict, Optional
from core.atomic_actions.base import AtomicAction
from core.agent_runtime.runtime_interface import AgentRuntimeInterface

class AtomicActionExecutor:
    """Исполнитель атомарных действий с полным жизненным циклом."""
    
    def __init__(self, runtime: AgentRuntimeInterface):
        self.runtime = runtime
    
    async def execute(
        self,
        action: AtomicAction,
        context: Any,
        parameters: Optional[Dict[str, Any]] = None
    ) -> Any:
        """Выполняет атомарное действие с полным жизненным циклом."""
        if not isinstance(action, AtomicAction):
            raise TypeError(f"Expected AtomicAction, got {type(action)}")
            
        return await action.execute(self.runtime, context, parameters)
```

### 3. Исполнитель паттернов (Application слой)

Файл: `core/application/executors/pattern_executor.py`

Отдельный класс, отвечающий только за выполнение компонуемых паттернов.

```python
from typing import Any, Dict, Optional
from core.composable_patterns.base import ComposablePattern
from core.agent_runtime.runtime_interface import AgentRuntimeInterface

class PatternExecutor:
    """Исполнитель компонуемых паттернов."""
    
    def __init__(self, runtime: AgentRuntimeInterface):
        self.runtime = runtime
    
    async def execute(
        self,
        pattern: ComposablePattern,
        context: Any,
        parameters: Optional[Dict[str, Any]] = None
    ) -> Any:
        """Выполняет компонуемый паттерн."""
        if not isinstance(pattern, ComposablePattern):
            raise TypeError(f"Expected ComposablePattern, got {type(pattern)}")
            
        return await pattern.execute(self.runtime, context, parameters)
```

### 4. Фабрика агентов (Application слой)

Файл: `core/application/factories/agent_factory.py`

Фабрика для создания экземпляров агентов с правильными зависимостями.

```python
from core.application.agents.composable_agent import ComposableAgent
from core.application.executors.atomic_action_executor import AtomicActionExecutor
from core.application.executors.pattern_executor import PatternExecutor
from core.domain_management.domain_manager import DomainManager
from core.agent_runtime.runtime_interface import AgentRuntimeInterface

class AgentFactory:
    """Фабрика для создания компонуемых агентов."""
    
    def __init__(self, default_runtime: AgentRuntimeInterface):
        self.default_runtime = default_runtime
    
    def create_agent(
        self,
        name: str,
        description: str = "",
        runtime: Optional[AgentRuntimeInterface] = None,
        domain_manager: Optional[DomainManager] = None
    ) -> ComposableAgent:
        """Создает экземпляр ComposableAgent с внедренными зависимостями."""
        actual_runtime = runtime or self.default_runtime
        actual_domain_manager = domain_manager or DomainManager()
        
        atomic_executor = AtomicActionExecutor(actual_runtime)
        pattern_executor = PatternExecutor(actual_runtime)
        
        return ComposableAgent(
            name=name,
            description=description,
            runtime=actual_runtime,
            domain_manager=actual_domain_manager,
            atomic_action_executor=atomic_executor,
            pattern_executor=pattern_executor
        )
```

### 5. Упрощенный агент (Application слой)

Файл: `core/application/agents/simple_composable_agent.py`

Содержит упрощенную версию агента с удобными методами, как в оригинале, но с правильной архитектурой.

```python
from typing import Any, Dict, Optional
from core.application.agents.composable_agent import ComposableAgent
from core.atomic_actions.base import AtomicAction
from core.composable_patterns.base import ComposablePattern

class SimpleComposableAgent(ComposableAgent):
    """Упрощенная реализация компонуемого агента."""
    
    def __init__(
        self, 
        name: str, 
        description: str = "", 
        initial_domain: Optional[str] = None,
        *args, **kwargs
    ):
        super().__init__(name, description, *args, **kwargs)
        if initial_domain:
            self.adapt_to_domain(initial_domain)
    
    async def simple_execute(
        self,
        actions_or_pattern: Any,
        context: Any,
        parameters: Optional[Dict[str, Any]] = None
    ) -> Any:
        """Упрощенное выполнение - автоматически определяет тип исполняемого объекта."""
        if isinstance(actions_or_pattern, AtomicAction):
            return await self.execute_atomic_action(actions_or_pattern, context, parameters)
        elif isinstance(actions_or_pattern, ComposablePattern):
            return await self.execute_composable_pattern(actions_or_pattern, context, parameters)
        else:
            raise TypeError(f"Expected AtomicAction or ComposablePattern, got {type(actions_or_pattern)}")
```

## Преимущества предлагаемого подхода

1. **Разделение ответственностей**: Каждый класс теперь имеет одну четко определенную ответственность
2. **Легкость тестирования**: Каждый компонент может быть протестирован изолированно
3. **Гибкость внедрения зависимостей**: Зависимости явно передаются в конструкторы, что упрощает замену реализаций
4. **Соблюдение принципа инверсии зависимостей**: Модули высокого уровня не зависят от модулей низкого уровня
5. **Соблюдение архитектурных границ**: Четкое разделение между Domain, Application и Infrastructure слоями

## План миграции

1. Создать новые файлы с новой архитектурой
2. Обновить все импорты в проекте, чтобы использовать новые пути
3. Постепенно перенести функциональность из старого ComposableAgent в новые компоненты
4. После проверки работоспособности удалить старый файл
5. Обновить тесты для соответствия новой архитектуре

## Зависимости

- Domain слой: `core/domain_management/domain_manager.py`, модели данных
- Application слой: `core/application/agents/composable_agent.py`, `core/application/executors/*`, `core/application/factories/*`
- Infrastructure слой: `core/infrastructure/executors/atomic_action_executor.py`, провайдеры, инструменты

Таким образом, мы достигаем лучшей архитектуры, соответствующей принципам SOLID и Clean Architecture, при этом сохраняя всю функциональность оригинального агента.