# Предложение по рефакторингу core/agent_runtime

## Текущая проблема

Директория `core/agent_runtime` содержит множество файлов, объединенных в application слой, но содержащих разные аспекты функциональности. Как указано в архитектурной миграции, необходимо "рассмотреть более тонкую градацию - возможно, выделить отдельные поддиректории для разных аспектов (состояния, выполнения, планирования)".

## Анализ текущей структуры

Файлы в директории `core/agent_runtime` можно разделить на следующие группы по функциональности:

1. **Интерфейсы и базовые классы**: `interfaces.py`, `base_agent_runtime.py`, `model.py`, `thinking_patterns/base.py`
2. **Основная логика выполнения**: `runtime.py`, `executor.py`, `execution_context.py`, `states.py`
3. **Стратегии и паттерны мышления**: `strategy_loader.py`, `pattern_selector.py`, `task_adapter.py`, `thinking_patterns/`
4. **Вспомогательные компоненты**: `progress.py`, `policy.py`, `checkpoint.py`

## Предлагаемое разбиение

### 1. Поддиректория interfaces (остается в application слое)

Файл: `core/application/agent_runtime_interfaces/interfaces.py`

Содержит интерфейсы для агентов и сессий, реализующие принцип разделения интерфейсов (ISP).

```python
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, List
from core.session_context.base_session_context import BaseSessionContext
from core.system_context.base_system_contex import BaseSystemContext
from models.execution import ExecutionResult

class IAgentRuntime(ABC):
    """Интерфейс для агента выполнения"""
    
    @abstractmethod
    async def execute(self) -> ExecutionResult:
        """Выполнение задачи агентом"""
        pass
    
    @abstractmethod
    def set_session_context(self, session_context: BaseSessionContext):
        """Установка контекста сессии"""
        pass
    
    @abstractmethod
    def get_session_context(self) -> BaseSessionContext:
        """Получение контекста сессии"""
        pass
    
    @abstractmethod
    def set_system_context(self, system_context: BaseSystemContext):
        """Установка системного контекста"""
        pass

class ISessionContext(ABC):
    """Интерфейс для контекста сессии"""
    
    @abstractmethod
    def get_context_item(self, item_id: str) -> Optional[Any]:
        """Получение элемента контекста по ID"""
        pass
    
    @abstractmethod
    def add_context_item(self, item: Any, item_type: str = "generic") -> str:
        """Добавление элемента контекста"""
        pass
    
    @abstractmethod
    def get_goal(self) -> Optional[str]:
        """Получение цели сессии"""
        pass
    
    @abstractmethod
    def set_goal(self, goal: str):
        """Установка цели сессии"""
        pass
    
    @abstractmethod
    def get_summary(self) -> str:
        """Получение краткого описания контекста"""
        pass

class IAgentFactory(ABC):
    """Интерфейс для фабрики агентов"""
    
    @abstractmethod
    async def create_agent(self, **kwargs) -> IAgentRuntime:
        """Асинхронное создание агента"""
        pass
    
    @abstractmethod
    async def create_agent_for_question(self, question: str, **kwargs) -> IAgentRuntime:
        """Создание агента, настроенного под конкретный вопрос"""
        pass
```

### 2. Поддиректория models (переходит в domain слой)

Файл: `core/domain/agent_runtime_models/model.py`

Содержит модели данных для стратегии и решений, определяющие типы решений, которые может вернуть стратегия в новой архитектуре.


```python
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional, Type, TYPE_CHECKING

# Используем TYPE_CHECKING для предотвращения циклических импортов
if TYPE_CHECKING:
    from core.atomic_actions.base import AtomicActionType
    from core.composable_patterns.base import ComposablePattern
    from core.agent_runtime.thinking_patterns.base import AgentThinkingPatternInterface

from models.capability import Capability

class StrategyDecisionType(Enum):
    """
    Типы решений, которые может вернуть стратегия в новой архитектуре.
    """
    ACT = "act"              # Выполнить действие
    STOP = "stop"            # Завершить выполнение агента
    SWITCH = "switch"        # Переключить стратегию
    RETRY = "retry"          # Повторить предыдущий шаг
    CONTINUE = "continue"    # Продолжить выполнение текущей стратегии
    EVALUATE = "evaluate"    # Оценить прогресс и принять решение
    
    def is_terminal(self) -> bool:
        """Проверяет, является ли действие терминальным."""
        return self in [StrategyDecisionType.STOP]

@dataclass
class StrategyDecision:
    """
    Формализованное решение стратегии в новой архитектуре.
    ОБНОВЛЕНО:
    - Поддержка компонуемых паттернов
    - Поддержка атомарных действий
    - Расширенная информация о принятом решении
    """
    action: StrategyDecisionType
    capability: Optional[Capability] = None
    parameters_class: Optional[Type] = None  # Класс Pydantic-модели для валидации
    payload: Optional[Dict[str, Any]] = None
    reason: Optional[str] = None
    next_strategy: Optional[str] = None
    atomic_action: Optional[str] = None      # Тип атомарного действия (например, "THINK", "ACT", "OBSERVE")
    composable_pattern: Optional['ComposablePattern'] = None  # Компонуемый паттерн, если используется (используем строковую аннотацию для предотвращения циклического импорта)
    domain_context: Optional[Dict[str, Any]] = None  # Контекст домена задачи
    
    def __post_init__(self):
        """Валидация после инициализации."""
        if self.action == StrategyDecisionType.ACT and not self.capability:
            raise ValueError("Для действия ACT необходимо указать capability")
        if self.action == StrategyDecisionType.SWITCH and not self.next_strategy:
            raise ValueError("Для действия SWITCH необходимо указать next_strategy")
        if self.action == StrategyDecisionType.EVALUATE and not self.payload:
            # Для EVALUATE может быть полезно иметь payload с информацией для оценки
            self.payload = {} if self.payload is None else self.payload
```

### 3. Поддиректория execution (остается в application слое)

Файлы: `core/application/agent_runtime_execution/executor.py`, `execution_context.py`, `states.py`

Содержит компоненты, отвечающие за выполнение действий агента.


#### executor.py
```python
from core.system_context.base_system_contex import BaseSystemContext
from models.capability import Capability
from core.session_context.base_session_context import BaseSessionContext
from models.execution import ExecutionResult

class ActionExecutor:
    """Единственная ответственность — выполнение capability."""
    
    def __init__(self, system_context: BaseSystemContext):
        self.system = system_context
        
    async def execute_capability(
        self,
        capability: Capability,
        parameters: dict,
        session_context: BaseSessionContext
    ) -> ExecutionResult:
        """Выполняет capability с заданными параметрами и контекстом."""
        return await self.system.execution_gateway.execute_capability(
            capability_name=capability.name,
            parameters=parameters,
            system_context=self.system,
            session_context=session_context
        )
```

#### execution_context.py
```python
"""Контекст выполнения для разделения ответственности."""
from dataclasses import dataclass
from typing import Any, Dict, TYPE_CHECKING
from core.agent_runtime.state import AgentState
from core.agent_runtime.progress import ProgressScorer
from core.agent_runtime.executor import ActionExecutor
from core.agent_runtime.policy import AgentPolicy
from core.system_context.base_system_contex import BaseSystemContext
from core.session_context.base_session_context import BaseSessionContext

if TYPE_CHECKING:
    from core.agent_runtime.thinking_patterns.base import AgentStrategyInterface
    from models.agent_state import AgentState

@dataclass
class ExecutionContext:
    """
    ExecutionContext - контекст выполнения агента.
    
    НАЗНАЧЕНИЕ:
    - Обеспечивает единый интерфейс доступа ко всем компонентам, необходимым для выполнения агента
    - Снижает связанность между компонентами, позволяя передавать только один объект
    - Предоставляет стратегиям доступ ко всем необходимым ресурсам
    
    ВОЗМОЖНОСТИ:
    - Хранит ссылки на все ключевые компоненты агента
    - Обеспечивает доступ к системному контексту
    - Обеспечивает доступ к сессионному контексту
    - Обеспечивает доступ к состоянию агента
    - Обеспечивает доступ к политике агента
    - Обеспечивает доступ к шкале прогресса
    - Обеспечивает доступ к исполнителю действий
    - Обеспечивает доступ к текущей стратегии
    
    ПРИМЕРЫ РАБОТЫ:
    # Создание контекста выполнения
    context = ExecutionContext(
        system=system_context,
        session=session_context,
        state=agent_state,
        policy=agent_policy,
        progress=progress_scorer,
        executor=action_executor,
        strategy=current_strategy
    )
    
    # Использование в стратегии
    async def next_step(self, context: ExecutionContext) -> StrategyDecision:
        # Доступ к сессии
        session = context.session
        # Доступ к системе
        system = context.system
        # Доступ к состоянию
        state = context.state
        # Доступ к исполнителю
        executor = context.executor
        # Доступ к стратегии
        strategy = context.strategy
        
        # Логика стратегии
        # ...
        
        return decision
    """
    system: BaseSystemContext
    session: BaseSessionContext
    state: AgentState
    policy: AgentPolicy
    progress: ProgressScorer
    executor: ActionExecutor
    strategy: 'AgentStrategyInterface' = None
```

#### states.py
```python
"""Состояния выполнения агента."""
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from core.agent_runtime.execution_context import ExecutionContext
    from core.agent_runtime.model import StrategyDecision

class AgentStateInterface(ABC):
    """
    AgentStateInterface - интерфейс состояния агента.
    
    НАЗНАЧЕНИЕ:
    - Определяет общий интерфейс для всех возможных состояний агента
    - Позволяет реализовать паттерн "Состояние" для управления поведением агента
    - Обеспечивает возможность изменения поведения агента в зависимости от его текущего состояния
    
    ВОЗМОЖНОСТИ:
    - Обеспечивает единый метод выполнения для всех состояний
    - Позволяет реализовать различные режимы работы агента
    - Обеспечивает возможность переключения между состояниями
    - Обеспечивает инкапсуляцию логики, зависящей от состояния агента
    
    ПРИМЕРЫ РАБОТЫ:
    # Реализация конкретного состояния
    class ActiveState(AgentStateInterface):
        async def execute(self, context: ExecutionContext) -> StrategyDecision:
            # Логика выполнения для активного состояния
            decision = await context.strategy.next_step(context)
            return decision
    
    # Использование в агенте
    state = ActiveState()
    decision = await state.execute(context)
    """
    
    @abstractmethod
    async def execute(self, context: 'ExecutionContext') -> 'StrategyDecision':
        """Выполнить состояние."""
        pass

class ExecutionState(AgentStateInterface):
    """
    ExecutionState - состояние выполнения шага агента.
    
    НАЗНАЧЕНИЕ:
    - Выполняет основной цикл принятия решений и выполнения действий
    - Обрабатывает решения, принимаемые стратегией
    - Обновляет состояние агента в зависимости от результата выполнения
    
    ВОЗМОЖНОСТИ:
    - Вызывает метод стратегии для получения решения
    - Обрабатывает терминальные решения (остановка агента)
    - Обновляет флаг завершения работы агента
    - Возвращает принятое решение для дальнейшей обработки
    
    ПРИМЕРЫ РАБОТЫ:
    # Создание состояния выполнения
    execution_state = ExecutionState()
    
    # Выполнение шага
    decision = await execution_state.execute(context)
    
    # Обработка решения
    if decision.action.is_terminal():
        context.state.finished = True
    """
    
    async def execute(self, context: 'ExecutionContext') -> 'StrategyDecision':
        """Выполнить основную логику шага."""
        # Получаем решение от паттерна мышления через контекст
        decision = await context.strategy.next_step(context)
        # Обновляем состояние агента
        if decision.action.is_terminal():
            context.state.finished = True
        
        return decision
```

### 4. Поддиректория thinking_patterns (остается в application слое)

Файлы: `core/application/agent_runtime_thinking_patterns/strategy_loader.py`, `pattern_selector.py`, `task_adapter.py`, `base.py`

Содержит компоненты для работы с паттернами мышления агента.


#### base.py
```python
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
```

#### strategy_loader.py
```python
"""Загрузчик паттернов мышления для агента с использованием новой архитектуры на основе атомарных действий и компонуемых паттернов."""

from typing import Dict, Type, Any
from core.agent_runtime.thinking_patterns.base import AgentThinkingPatternInterface

# Импорты для новой архитектуры
from core.composable_patterns.registry import PatternRegistry
from core.composable_patterns.patterns import (
    ReActPattern, PlanAndExecutePattern, ToolUsePattern, ReflectionPattern,
    CodeAnalysisPattern, DatabaseQueryPattern, ResearchPattern
)
from core.domain_management.domain_manager import DomainManager

# Импорты для работы с YAML и модулями
import yaml
import importlib

from core.system_context.event_bus import EventSystem, EventType

class ThinkingPatternLoader:
    """
    ThinkingPatternLoader - загрузчик паттернов мышления для агента.
    
    НАЗНАЧЕНИЕ:
    - Обеспечивает динамическую загрузку паттернов мышления выполнения агента
    - Позволяет регистрировать паттерны мышления из конфигурационных файлов
    - Обеспечивает централизованное управление паттернами мышления
    - Поддерживает новую архитектуру с атомарными действиями и компонуемыми паттернами
    
    ВОЗМОЖНОСТИ:
    - Загрузка паттернов мышления из YAML-конфигурационных файлов
    - Создание экземпляров паттернов мышления
    - Регистрация новых паттернов мышления во время выполнения
    - Проверка соответствия интерфейсу паттерна мышления
    - Регистрация компонуемых паттернов
    - Управление доменными паттернами
    """
    
    def __init__(self, config_path: str = None, use_new_architecture: bool = True):
        self.config_path = config_path
        self.use_new_architecture = use_new_architecture
        self._patterns: Dict[str, Type[AgentThinkingPatternInterface]] = {}
        self.pattern_registry = None
        self.domain_manager = DomainManager()
        
        if config_path:
            self.load_from_config(config_path)
        else:
            # Загружаем паттерны мышления по умолчанию
            self._register_default_patterns()
            
            if use_new_architecture:
                # Инициализируем новую архитектуру
                self._setup_new_architecture()
    
    def _setup_new_architecture(self):
        """Настройка новой архитектуры с компонуемыми паттернами."""
        self.pattern_registry = PatternRegistry()
        
        # Регистрация универсальных компонуемых паттернов
        self.pattern_registry.register_pattern("react_composable", ReActPattern)
        self.pattern_registry.register_pattern("plan_and_execute_composable", PlanAndExecutePattern)
        self.pattern_registry.register_pattern("tool_use_composable", ToolUsePattern)
        self.pattern_registry.register_pattern("reflection_composable", ReflectionPattern)
        
        # Регистрация доменных паттернов
        self.pattern_registry.register_domain_pattern("code_analysis", "default", CodeAnalysisPattern)
        self.pattern_registry.register_domain_pattern("database_query", "default", DatabaseQueryPattern)
        self.pattern_registry.register_domain_pattern("research", "default", ResearchPattern)
    
    def _register_default_patterns(self):
        """Регистрация паттернов мышления по умолчанию."""
        self._patterns = {}
    
    def load_from_config(self, config_path: str):
        """Загрузка паттернов мышления из YAML-конфига."""
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        patterns_config = config.get('thinking_patterns', {})
        
        for pattern_name, pattern_config in patterns_config.items():
            module_path = pattern_config['module']
            class_name = pattern_config['class']
            
            # Импортируем модуль
            module = importlib.import_module(module_path)
            
            # Получаем класс паттерна мышления
            pattern_class = getattr(module, class_name)
            
            # Проверяем, что класс реализует интерфейс паттерна мышления
            if not issubclass(pattern_class, AgentThinkingPatternInterface):
                raise ValueError(f"Класс {pattern_class} не реализует AgentThinkingPatternInterface")
        
            self._patterns[pattern_name] = pattern_class
    
    def get_pattern_class(self, pattern_name: str) -> Type[AgentThinkingPatternInterface]:
        """Получить класс паттерна мышления по имени."""
        if pattern_name not in self._patterns:
            raise ValueError(f"Паттерн мышления '{pattern_name}' не найден. Доступные: {list(self._patterns.keys())}")
        
        return self._patterns[pattern_name]
    
    def create_pattern(self, pattern_name: str, **kwargs) -> AgentThinkingPatternInterface:
        """Создать экземпляр паттерна мышления."""
        pattern_class = self.get_pattern_class(pattern_name)
        
        # Создаем экземпляр класса с переданными аргументами
        return pattern_class(**kwargs)
    
    def register_pattern(self, pattern_name: str, pattern_class: Type[AgentThinkingPatternInterface]):
        """Зарегистрировать новый паттерн мышления."""
        if not issubclass(pattern_class, AgentThinkingPatternInterface):
            raise ValueError(f"Класс {pattern_class} не реализует AgentThinkingPatternInterface")
        
        self._patterns[pattern_name] = pattern_class
    
    def get_pattern_registry(self) -> 'PatternRegistry':
        """Получить реестр компонуемых паттернов."""
        if self.pattern_registry is None:
            self._setup_new_architecture()
        return self.pattern_registry
    
    def get_domain_manager(self) -> 'DomainManager':
        """Получить менеджер доменов."""
        return self.domain_manager
    
    def get_pattern_for_domain(self, domain: str, task_description: str = "") -> str:
        """
        Получить подходящий паттерн для указанного домена и задачи.
        
        Args:
            domain: Домен задачи
            task_description: Описание задачи для более точного выбора паттерна
            
        Returns:
            Имя паттерна для использования
        """
        # Сначала пробуем найти специфичный паттерн для домена
        if self.pattern_registry:
            domain_patterns = self.pattern_registry.get_domain_patterns(domain)
            if domain_patterns:
                # Для простоты возвращаем первый найденный паттерн
                # В реальной реализации здесь может быть более сложная логика выбора
                return domain_patterns[0].split('.', 1)[1]  # Убираем префикс домена
        
        # Используем доменный менеджер для получения стандартного паттерна
        return self.domain_manager.get_domain_pattern(domain)
    
    def adapt_to_task(self, task_description: str) -> Dict[str, Any]:
        """
        Адаптироваться к задаче: определить домен и выбрать подходящий паттерн.
        
        Args:
            task_description: Описание задачи
            
        Returns:
            Словарь с информацией о домене и паттерне
        """
        domain = self.domain_manager.classify_task(task_description)
        pattern = self.get_pattern_for_domain(domain, task_description)
        
        return {
            "domain": domain,
            "pattern": pattern,
            "domain_config": self.domain_manager.get_domain_config(domain)
        }
```

#### pattern_selector.py
```python
"""
Селектор паттернов для выбора подходящей стратегии мышления.

Этот модуль содержит компонент, который отвечает за выбор подходящей стратегии
мышления на основе текущего состояния задачи, домена и доступных паттернов.
"""
from typing import Dict, Any, Optional
from core.composable_patterns.registry import PatternRegistry
from core.domain_management.domain_manager import DomainManager
from core.agent_runtime.strategy_loader import ThinkingPatternLoader

class PatternSelector:
    """
    Компонент для выбора подходящей стратегии мышления на основе различных факторов.
    
    ОСНОВНАЯ ОТВЕТСТВЕННОСТЬ:
    - Выбор наиболее подходящего паттерна мышления
    - Переключение между паттернами во время выполнения
    - Оценка применимости паттернов к текущей ситуации
    """
    
    def __init__(self):
        """Инициализация селектора паттернов."""
        self.pattern_loader = ThinkingPatternLoader(use_new_architecture=True)
        self.domain_manager = self.pattern_loader.get_domain_manager()
        self.pattern_registry = self.pattern_loader.get_pattern_registry()
        
        # Инициализация реестра паттернов
        self._pattern_registry = PatternRegistry()
        
        # Регистрация компонуемых паттернов как основных
        composable_patterns = {
            "react_composable": self._pattern_registry.get_pattern("react_composable"),
            "plan_and_execute_composable": self._pattern_registry.get_pattern("plan_and_execute_composable"),
            "tool_use_composable": self._pattern_registry.get_pattern("tool_use_composable"),
            "reflection_composable": self._pattern_registry.get_pattern("reflection_composable"),
            # Регистрация доменных паттернов
            "code_analysis.default": self._pattern_registry.get_pattern("code_analysis.default"),
            "database_query.default": self._pattern_registry.get_pattern("database_query.default"),
            "research.default": self._pattern_registry.get_pattern("research.default"),
        }

        # Фильтрация None значений (если какие-то паттерны не были найдены)
        self._thinking_pattern_registry = {k: v for k, v in composable_patterns.items() if v is not None}
    
    def select_pattern(self, current_context: Dict[str, Any], current_domain: str = "general") -> str:
        """
        Выбрать подходящий паттерн на основе текущего контекста и домена.
        
        ПАРАМЕТРЫ:
        - current_context: текущий контекст выполнения (включая историю, результаты и т.д.)
        - current_domain: текущий домен задачи
        
        ВОЗВРАЩАЕТ:
        - название выбранного паттерна
        """
        # Проверяем, есть ли информация о текущем прогрессе
        progress_info = current_context.get("progress", {})
        current_step = current_context.get("step", 0)
        execution_history = current_context.get("history", [])
        
        # Если есть доменный паттерн, используем его
        domain_pattern_key = f"{current_domain}.default"
        if domain_pattern_key in self._thinking_pattern_registry:
            # Но сначала проверим, подходит ли он для текущей ситуации
            if self._should_continue_with_domain_pattern(domain_pattern_key, progress_info, execution_history):
                return domain_pattern_key
        
        # Определяем, какой паттерн использовать на основе прогресса и истории
        if self._should_switch_to_reflection(progress_info, execution_history):
            return "reflection_composable"
        elif self._should_plan_next_steps(current_context):
            return "plan_and_execute_composable"
        elif self._should_use_tool_pattern(current_context):
            return "tool_use_composable"
        else:
            # По умолчанию возвращаем реактивный паттерн
            return "react_composable" if "react_composable" in self._thinking_pattern_registry else list(self._thinking_pattern_registry.keys())[0] if self._thinking_pattern_registry else "general"
    
    def _should_continue_with_domain_pattern(self, domain_pattern: str, progress_info: Dict[str, Any], history: list) -> bool:
        """
        Проверить, стоит ли продолжать использовать доменный паттерн.
        
        ПАРАМЕТРЫ:
        - domain_pattern: название доменного паттерна
        - progress_info: информация о прогрессе
        - history: история выполнения
        
        ВОЗВРАЩАЕТ:
        - True если стоит продолжать использовать доменный паттерн
        """
        # Если прогресс есть и он положительный, продолжаем использовать доменный паттерн
        if progress_info and progress_info.get("improvement", 0) > 0.1:
            return True
        
        # Если в истории есть успешные выполнения с этим паттерном, продолжаем
        successful_executions = [item for item in history if item.get("status") == "SUCCESS" and item.get("pattern") == domain_pattern]
        if len(successful_executions) > 0:
            return True
        
        # В остальных случаях проверяем, не нужно ли сменить стратегию
        return False
    
    def _should_switch_to_reflection(self, progress_info: Dict[str, Any], history: list) -> bool:
        """
        Проверить, стоит ли переключиться на паттерн рефлексии.
        
        ПАРАМЕТРЫ:
        - progress_info: информация о прогрессе
        - history: история выполнения
        
        ВОЗВРАЩАЕТ:
        - True если стоит переключиться на рефлексию
        """
        # Если прогресс минимальный или отрицательный
        if progress_info and progress_info.get("improvement", 0) <= 0:
            return True
        
        # Если в истории много ошибок
        error_count = len([item for item in history if item.get("status") == "ERROR"])
        total_count = len(history)
        if total_count > 0 and error_count / total_count > 0.3:  # Если больше 30% ошибок
            return True
        
        # Если выполнено много шагов, но прогресс мал
        steps_count = len(history)
        if steps_count > 5 and progress_info.get("overall_progress", 0) < 0.2:  # Если после 5+ шагов прогресс < 20%
            return True
        
        return False
    
    def _should_plan_next_steps(self, current_context: Dict[str, Any]) -> bool:
        """
        Проверить, стоит ли переключиться на паттерн планирования.
        
        ПАРАМЕТРЫ:
        - current_context: текущий контекст выполнения
        
        ВОЗВРАЩАЕТ:
        - True если стоит переключиться на планирование
        """
        # Если задача кажется сложной и многошаговой
        goal_complexity = current_context.get("goal_complexity", 1)
        if goal_complexity > 2:  # Сложная задача
            return True
        
        # Если есть много подзадач
        subtasks = current_context.get("subtasks", [])
        if len(subtasks) > 2:
            return True
        
        return False
    
    def _should_use_tool_pattern(self, current_context: Dict[str, Any]) -> bool:
        """
        Проверить, стоит ли использовать паттерн работы с инструментами.
        
        ПАРАМЕТРЫ:
        - current_context: текущий контекст выполнения
        
        ВОЗВРАЩАЕТ:
        - True если стоит использовать паттерн работы с инструментами
        """
        # Если в контексте есть упоминание об использовании инструментов
        goal = current_context.get("goal", "")
        if any(tool in goal.lower() for tool in ["инструмент", "tool", "навык", "skill", "сервис", "service"]):
            return True
        
        # Если есть ресурсы, которые нужно использовать
        resources = current_context.get("resources", [])
        if len(resources) > 0:
            return True
        
        return False
    
    def get_pattern_instance(self, pattern_name: str):
        """
        Получить экземпляр паттерна по его имени.
        
        ПАРАМЕТРЫ:
        - pattern_name: название паттерна
        
        ВОЗВРАЩАЕТ:
        - экземпляр паттерна или None если не найден
        """
        if pattern_name in self._thinking_pattern_registry:
            return self._thinking_pattern_registry[pattern_name]
        return None
    
    def validate_pattern_selection(self, pattern_name: str, current_context: Dict[str, Any]) -> bool:
        """
        Проверить корректность выбора паттерна.
        
        ПАРАМЕТРЫ:
        - pattern_name: название выбранного паттерна
        - current_context: текущий контекст выполнения
        
        ВОЗВРАЩАЕТ:
        - True если выбор корректен, иначе False
        """
        # Проверяем, существует ли паттерн
        if pattern_name not in self._thinking_pattern_registry:
            return False
        
        # Проверяем, применим ли паттерн к текущему домену
        current_domain = current_context.get("domain", "general")
        domain_pattern_key = f"{current_domain}.default"
        
        # Если доменный паттерн недоступен, но выбран другой, это может быть нормально
        # Но если доменный паттерн доступен и не используется без веской причины, это может быть проблемой
        
        return True
    
    def get_fallback_pattern(self) -> str:
        """
        Получить резервный паттерн для использования в случае ошибки.
        
        ВОЗВРАЩАЕТ:
        - название резервного паттерна
        """
        # Возвращаем реактивный паттерн как наиболее универсальный
        if "react_composable" in self._thinking_pattern_registry:
            return "react_composable"
        # Или первый доступный паттерн
        elif self._thinking_pattern_registry:
            return list(self._thinking_pattern_registry.keys())[0]
        else:
            return "general"
```

#### task_adapter.py
```python
"""
Адаптер задач для определения домена и выбора подходящего паттерна.

Этот модуль содержит компонент, который отвечает за адаптацию агента к задаче:
определение домена задачи и выбор подходящего паттерна мышления.
"""
from typing import Dict, Any, Optional
from core.composable_patterns.registry import PatternRegistry
from core.domain_management.domain_manager import DomainManager
from core.agent_runtime.strategy_loader import ThinkingPatternLoader

class TaskAdapter:
    """
    Компонент для адаптации агента к задаче: определение домена и выбор подходящего паттерна.
    
    ОСНОВНАЯ ОТВЕТСТВЕННОСТЬ:
    - Определение домена задачи
    - Выбор наиболее подходящего паттерна мышления
    - Адаптация параметров задачи под выбранный паттерн
    """
    
    def __init__(self):
        """Инициализация адаптера задач."""
        self.pattern_loader = ThinkingPatternLoader(use_new_architecture=True)
        self.domain_manager = self.pattern_loader.get_domain_manager()
        self.pattern_registry = self.pattern_loader.get_pattern_registry()
        
        # Инициализация реестра паттернов
        self._pattern_registry = PatternRegistry()
        
        # Регистрация компонуемых паттернов как основных
        composable_patterns = {
            "react_composable": self._pattern_registry.get_pattern("react_composable"),
            "plan_and_execute_composable": self._pattern_registry.get_pattern("plan_and_execute_composable"),
            "tool_use_composable": self._pattern_registry.get_pattern("tool_use_composable"),
            "reflection_composable": self._pattern_registry.get_pattern("reflection_composable"),
            # Регистрация доменных паттернов
            "code_analysis.default": self._pattern_registry.get_pattern("code_analysis.default"),
            "database_query.default": self._pattern_registry.get_pattern("database_query.default"),
            "research.default": self._pattern_registry.get_pattern("research.default"),
        }

        # Фильтрация None значений (если какие-то паттерны не были найдены)
        self._thinking_pattern_registry = {k: v for k, v in composable_patterns.items() if v is not None}
    
    def adapt_to_task(self, task_description: str) -> Dict[str, Any]:
        """
        Адаптировать агента к задаче: определить домен и выбрать подходящий паттерн.
        
        ПАРАМЕТРЫ:
        - task_description: описание задачи для анализа
        
        ВОЗВРАЩАЕТ:
        - словарь с информацией о домене и подходящем паттерне
        """
        # Определяем домен задачи
        domain_info = self.domain_manager.classify_domain(task_description)
        detected_domain = domain_info.get("primary_domain", "general")
        
        # Выбираем подходящий паттерн на основе домена
        selected_pattern = self._select_pattern_for_domain(detected_domain, task_description)
        
        return {
            "domain": detected_domain,
            "pattern": selected_pattern,
            "domain_confidence": domain_info.get("confidence", 0.0),
            "pattern_confidence": 0.8,  # Заглушка, в реальности должна быть рассчитана
            "adaptation_reasoning": f"Selected {selected_pattern} for {detected_domain} domain"
        }
    
    def _select_pattern_for_domain(self, domain: str, task_description: str) -> str:
        """
        Выбрать подходящий паттерн для указанного домена.
        
        ПАРАМЕТРЫ:
        - domain: домен задачи
        - task_description: описание задачи для дополнительного анализа
        
        ВОЗВРАЩАЕТ:
        - название подходящего паттерна
        """
        # Сначала пробуем найти доменный паттерн
        domain_pattern_key = f"{domain}.default"
        if domain_pattern_key in self._thinking_pattern_registry:
            return domain_pattern_key
        
        # Если доменный паттерн не найден, используем общий подход
        # Для разных типов задач выбираем разные паттерны
        task_lower = task_description.lower()
        
        # Определяем тип задачи по ключевым словам
        if any(keyword in task_lower for keyword in ["анализ", "code", "ошибка", "debug", "исправ", "ошибка"]):
            return "code_analysis.default" if "code_analysis.default" in self._thinking_pattern_registry else "react_composable"
        elif any(keyword in task_lower for keyword in ["база данных", "sql", "запрос", "таблица", "данные"]):
            return "database_query.default" if "database_query.default" in self._thinking_pattern_registry else "react_composable"
        elif any(keyword in task_lower for keyword in ["исследование", "research", "поиск", "найти", "информация"]):
            return "research.default" if "research.default" in self._thinking_pattern_registry else "react_composable"
        else:
            # По умолчанию используем реактивный паттерн
            return "react_composable" if "react_composable" in self._thinking_pattern_registry else list(self._thinking_pattern_registry.keys())[0] if self._thinking_pattern_registry else "general"
    
    def get_available_patterns(self) -> Dict[str, Any]:
        """
        Получить список доступных паттернов.
        
        ВОЗВРАЩАЕТ:
        - словарь с информацией о доступных паттернах
        """
        return {
            "patterns": list(self._thinking_pattern_registry.keys()),
            "count": len(self._thinking_pattern_registry),
            "domains_supported": self.domain_manager.get_available_domains()
        }
    
    def validate_task_adaptation(self, adaptation_result: Dict[str, Any]) -> bool:
        """
        Проверить корректность результата адаптации задачи.
        
        ПАРАМЕТРЫ:
        - adaptation_result: результат адаптации для проверки
        
        ВОЗВРАЩАЕТ:
        - True если адаптация корректна, иначе False
        """
        required_fields = ["domain", "pattern", "domain_confidence", "pattern_confidence"]
        for field in required_fields:
            if field not in adaptation_result:
                return False
        
        # Проверяем, что домен и паттерн не пустые
        if not adaptation_result["domain"] or not adaptation_result["pattern"]:
            return False
        
        # Проверяем, что уверенность в допустимом диапазоне
        if not (0.0 <= adaptation_result["domain_confidence"] <= 1.0):
            return False
        if not (0.0 <= adaptation_result["pattern_confidence"] <= 1.0):
            return False
        
        return True
```

### 5. Поддиректория utils (остается в application слое)

Файлы: `core/application/agent_runtime_utils/progress.py`, `policy.py`

Содержит вспомогательные компоненты для оценки прогресса и политик поведения агента.


#### progress.py
```python
class ProgressScorer:
    """
    Оценщик прогресса агента.
    """

    def __init__(self):
        self.last_summary = None

    def evaluate(self, session) -> bool:
        """
        Возвращает True если прогресс есть.
        """
        summary = session.get_summary()
        if summary == self.last_summary:
            return False
        self.last_summary = summary
        return True
```

#### policy.py
```python
class AgentPolicy:
    """
    Политики поведения агента.
    """

    def __init__(
        self,
        max_errors: int = 2,
        max_no_progress_steps: int = 3
    ):
        self.max_errors = max_errors
        self.max_no_progress_steps = max_no_progress_steps

    def should_fallback(self, state) -> bool:
        # Fallback происходит, когда количество ошибок достигает или превышает лимит
        # Особый случай: если лимит 0, то fallback происходит при любой ошибке (> 0)
        if self.max_errors == 0:
            return state.error_count > 0
        else:
            return state.error_count >= self.max_errors

    def should_stop_no_progress(self, state) -> bool:
        # Остановка происходит, когда количество шагов без прогресса достигает или превышает лимит
        # Особый случай: если лимит 0, то остановка происходит при любом шаге без прогресса (> 0)
        if self.max_no_progress_steps == 0:
            return state.no_progress_steps > 0
        else:
            return state.no_progress_steps >= self.max_no_progress_steps
```

### 6. Основной класс runtime (остается в application слое)

Файл: `core/application/agent_runtime/runtime.py`

Обновленный класс, который использует все вышеперечисленные компоненты.


```python
from datetime import datetime
import logging
from typing import Any, Dict, Optional

# Импорты для новой архитектуры
from core.agent_runtime.base_agent_runtime import BaseAgentRuntime
from core.composable_patterns.registry import PatternRegistry
from core.domain_management.domain_manager import DomainManager
from core.agent_runtime.strategy_loader import ThinkingPatternLoader
from core.composable_patterns.state_manager import ComposablePatternStateManager

from core.session_context.base_session_context import BaseSessionContext
from core.session_context.model import ContextItemMetadata
from core.system_context.base_system_contex import BaseSystemContext

# Импорты для TaskAdapter и PatternSelector
from core.agent_runtime.task_adapter import TaskAdapter
from core.agent_runtime.pattern_selector import PatternSelector

# Используем TYPE_CHECKING для предотвращения циклических импортов
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from core.session_context.session_context import SessionContext
    from core.atomic_actions.base import AtomicAction
    from core.composable_patterns.base import ComposablePattern

from models.agent_state import AgentState
from .progress import ProgressScorer
from .executor import ActionExecutor
from .policy import AgentPolicy
from .model import StrategyDecisionType
from .execution_context import ExecutionContext
from .states import ExecutionState
from models.execution import ExecutionResult, ExecutionStatus
from models.composable_pattern_state import ComposablePatternState, ComposablePatternStatus

# Импорт интерфейса для ComposableAgentRuntime
from .interfaces import ComposableAgentInterface

from core.system_context.event_bus import EventSystem, EventType

# Инициализируем шину событий для логирования
event_bus = EventSystem()

class AgentRuntime(BaseAgentRuntime):
    """Тонкий оркестратор выполнения агента.
    
    НЕ содержит логики стратегий."""
    
    def __init__(
        self,
        system_context: BaseSystemContext,
        session_context: BaseSessionContext,
        policy: AgentPolicy = None,
        max_steps: int = 10, 
        strategy: str = None
    ):
        # Вызываем конструктор базового класса
        super().__init__(system_context, session_context)
        self.policy = policy or AgentPolicy()
        self.max_steps = max_steps
        self.state = AgentState()
        self.progress = ProgressScorer()
        self.executor = ActionExecutor(system_context)
        
        # Инициализация менеджера состояния композиционных паттернов
        self.pattern_state_manager = ComposablePatternStateManager()
        self.current_pattern_state_id = None
        
        # Инициализация новой архитектуры
        self.pattern_loader = ThinkingPatternLoader(use_new_architecture=True)
        self.domain_manager = self.pattern_loader.get_domain_manager()
        self.pattern_registry = self.pattern_loader.get_pattern_registry()
        
        # Инициализация реестра паттернов
        self._pattern_registry = PatternRegistry()
        
        # Регистрация компонуемых паттернов как основных
        composable_patterns = {
            "react_composable": self._pattern_registry.get_pattern("react_composable"),
            "plan_and_execute_composable": self._pattern_registry.get_pattern("plan_and_execute_composable"),
            "tool_use_composable": self._pattern_registry.get_pattern("tool_use_composable"),
            "reflection_composable": self._pattern_registry.get_pattern("reflection_composable"),
            # Регистрация доменных паттернов
            "code_analysis.default": self._pattern_registry.get_pattern("code_analysis.default"),
            "database_query.default": self._pattern_registry.get_pattern("database_query.default"),
            "research.default": self._pattern_registry.get_pattern("research.default"),
        }

        # Фильтрация None значений (если какие-то паттерны не были найдены)
        self._thinking_pattern_registry = {k: v for k, v in composable_patterns.items() if v is not None}
        
        # Инициализация адаптера задач и селектора паттернов
        self.task_adapter = TaskAdapter()
        self.pattern_selector = PatternSelector()
        
        # Определение стратегии на основе параметра или по умолчанию
        if strategy:
            if strategy not in self._thinking_pattern_registry:
                raise ValueError(f"Стратегия '{strategy}' не найдена в реестре паттернов")
            self.strategy = self._thinking_pattern_registry[strategy]
        else:
            # По умолчанию начинать с компонуемого реактивного паттерна мышления
            if "react_composable" in self._thinking_pattern_registry:
                self.strategy = self._thinking_pattern_registry["react_composable"]
            else:
                # Если компонуемый не доступен, использовать резервную стратегию
                # или выбросить исключение, если нет подходящей стратегии
                available_strategies = list(self._thinking_pattern_registry.keys())
                if available_strategies:
                    self.strategy = self._thinking_pattern_registry[available_strategies[0]]
                else:
                    raise ValueError("Нет доступных стратегий для использования")
        
    def get_strategy(self, strategy_name: str):
        """Получение стратегии по имени.
        
        ПАРАМЕТРЫ:
        - strategy_name: имя стратегии
        
        ВОЗВРАЩАЕТ:
        - экземпляр стратегии
        
        ИСКЛЮЧЕНИЯ:
        - ValueError если стратегия не найдена
        """
        strategy_name = strategy_name.lower()
        if strategy_name not in self._thinking_pattern_registry:
            raise ValueError(f"Паттерн мышления '{strategy_name}' не найден. Доступные: {list(self._thinking_pattern_registry.keys())}")
        
        pattern = self._thinking_pattern_registry[strategy_name]
        if pattern is None:
            raise ValueError(f"Паттерн мышления '{strategy_name}' зарегистрирован, но не реализован")
        
        # В методе get_strategy мы не можем использовать await, так как это не асинхронный метод
        # Вместо этого, будем использовать стандартное логирование, которое позже можно будет заменить
        import asyncio
        # Создаем отдельную задачу для публикации события
        asyncio.create_task(event_bus.publish_simple(
            event_type=EventType.DEBUG,
            source="AgentRuntime",
            data={
                "message": f"Получен паттерн мышления: {strategy_name} -> {pattern.__class__.__name__}",
                "strategy_name": strategy_name
            }
        ))
        return pattern

    def adapt_to_task(self, task_description: str) -> Dict[str, Any]:
        """
        Адаптировать агента к задаче: определить домен и выбрать подходящий паттерн.
        """
        return self.pattern_loader.adapt_to_task(task_description)

    async def execute(self) -> ExecutionResult:
        """Выполнение задачи агентом."""
        # Используем метод run с предопределенной целью
        # В реальной реализации цель должна быть передана или установлена ранее
        if not self.session.goal:
            await event_bus.publish_simple(
                event_type=EventType.WARNING,
                source="AgentRuntime",
                data={
                    "message": "Цель агента не установлена, выполнение может не дать ожидаемого результата",
                    "context": "agent_goal_not_set"
                }
            )
            return ExecutionResult(status=ExecutionStatus.FAILED, result=None, observation_item_id=None, summary="Goal not set", error="NO_GOAL_SET")
        
        # Выполняем основной цикл агента
        await self.run(self.session.goal)
        
        # Возвращаем результат выполнения
        return ExecutionResult(
            status=ExecutionStatus.SUCCESS if self.state.finished else ExecutionStatus.PENDING,
            result=self.session.get_summary(),
            observation_item_id=None,
            summary=f"Agent execution completed. Finished: {self.state.finished}, Steps: {self.state.step}",
            error=None
        )

    async def run(self, goal: str):
        """Главный execution loop агента."""
        self.session.goal = goal
        
        # Используем TaskAdapter для определения домена и подходящего паттерна
        task_adaptation = self.task_adapter.adapt_to_task(goal)
        detected_domain = task_adaptation["domain"]
        await event_bus.publish_simple(
            event_type=EventType.INFO,
            source="AgentRuntime",
            data={
                "message": f"Определен домен задачи: {detected_domain}",
                "domain": detected_domain
            }
        )
        
        # Создаем состояние для текущего паттерна мышления
        self.current_pattern_state_id = self.pattern_state_manager.create_state(
            pattern_name=self.strategy.name if hasattr(self.strategy, 'name') else str(type(self.strategy).__name__),
            pattern_description=f"Выполнение паттерна мышления для задачи: {goal}"
        )
        
        # Запись системного события
        self.session.record_system_event("session_start", f"Starting session with goal: {goal} (domain: {detected_domain})")
        
        # Используем паттерн "Состояние" для управления выполнением
        execution_state = ExecutionState()
        
        for _ in range(self.max_steps):
            if self.state.finished:
                break
            
            # Текущий номер шага (начинаем с 1)
            current_step = self.state.step + 1
            
            # Обновляем состояние паттерна
            if self.current_pattern_state_id:
                self.pattern_state_manager.update_state(self.current_pattern_state_id, {
                    "step": current_step,
                    "status": ComposablePatternStatus.ACTIVE
                })
            
            # Создаем контекст выполнения для текущего шага
            execution_context = ExecutionContext(
                system=self.system,
                session=self.session,
                state=self.state,
                policy=self.policy,
                progress=self.progress,
                executor=self.executor,
                strategy=self.strategy
            )
            
            decision = await execution_state.execute(execution_context)
            
            # Запись решения стратегии
            if decision:
                self.session.record_decision(decision.action.value, reasoning=decision.reason)
            
            if decision.action == StrategyDecisionType.STOP:
                self.state.finished = True
                # Обновляем состояние паттерна как завершенное
                if self.current_pattern_state_id:
                    self.pattern_state_manager.complete(self.current_pattern_state_id)
                # Регистрируем финальное решение
                self.session.record_decision(
                    decision_data="STOP",
                    reasoning="goal_achieved",
                    metadata=ContextItemMetadata(step_number=current_step)
                )
                break
            
            if decision.action == StrategyDecisionType.SWITCH:
                try:
                    # Обновляем состояние паттерна перед переключением
                    if self.current_pattern_state_id:
                        self.pattern_state_manager.update_state(self.current_pattern_state_id, {
                            "status": ComposablePatternStatus.TERMINATED
                        })
                    
                    # Используем новый метод для получения стратегии
                    old_strategy_name = self.strategy.name if hasattr(self.strategy, 'name') else str(type(self.strategy).__name__)
                    self.strategy = self.get_strategy(decision.next_strategy)
                    await event_bus.publish_simple(
                        event_type=EventType.INFO,
                        source="AgentRuntime",
                        data={
                            "message": f"Переключение стратегии на: {decision.next_strategy}",
                            "next_strategy": decision.next_strategy
                        }
                    )
                    
                    # Создаем новое состояние для нового паттерна
                    self.current_pattern_state_id = self.pattern_state_manager.create_state(
                        pattern_name=self.strategy.name if hasattr(self.strategy, 'name') else str(type(self.strategy).__name__),
                        pattern_description=f"Переключение на паттерн мышления: {decision.next_strategy}"
                    )
                    
                except Exception as e:
                    await event_bus.publish_simple(
                        event_type=EventType.ERROR,
                        source="AgentRuntime",
                        data={
                            "message": f"Ошибка переключения стратегии: {str(e)}. Используется fallback стратегия.",
                            "error": str(e),
                            "context": "strategy_switch_error"
                        }
                    )
                    # Пытаемся использовать любую доступную стратегию в качестве fallback
                    available_strategies = list(self._thinking_pattern_registry.keys())
                    if available_strategies:
                        self.strategy = self.get_strategy(available_strategies[0])
                
                # Регистрируем смену стратегии
                self.session.record_decision(
                    decision_data="SWITCH",
                    reasoning={"action": "strategy_change", "to_strategy": decision.next_strategy},
                    metadata=ContextItemMetadata(step_number=current_step)
                )
                continue
            
            if decision.action == StrategyDecisionType.ACT:
                try:
                    # Начинаем выполнение действия в состоянии паттерна
                    if self.current_pattern_state_id:
                        self.pattern_state_manager.start_action_execution(self.current_pattern_state_id, decision.reason)
                    
                    # 1. Создаем элемент действия в контексте перед выполнением
                    action_content = {
                        "capability": decision.capability.name,
                        "parameters": decision.payload,
                        "reason": decision.reason,
                        "skill": decision.capability.skill_name,
                        "step_number": current_step
                    }
                    
                    action_item_id = self.session.record_action(
                        action_data=action_content,
                        step_number=current_step,
                        metadata=ContextItemMetadata(
                            source="agent_runtime",
                            timestamp=datetime.now(),
                            confidence=0.9
                        )
                    )
                    
                    # 2. Выполняем capability
                    execution_result = await self.executor.execute_capability(
                        capability=decision.capability,
                        parameters=decision.payload,
                        session_context=self.session
                    )
                    
                    # 3. Проверяем тип результата (инвариант)
                    if not isinstance(execution_result, ExecutionResult):
                        await event_bus.publish_simple(
                            event_type=EventType.ERROR,
                            source="AgentRuntime",
                            data={
                                "message": f"Нарушен инвариант: ожидается ExecutionResult, получен {type(execution_result)}",
                                "step": current_step,
                                "capability_name": decision.capability.name,
                                "actual_type": str(type(execution_result)),
                                "context": "type_invariant_violation"
                            }
                        )
                        # Создаем корректный ExecutionResult с ошибкой
                        execution_result = ExecutionResult(
                            status=ExecutionStatus.FAILED,
                            result=None,
                            observation_item_id=None,
                            summary=f"Нарушен инвариант типа: ожидается ExecutionResult, получен {type(execution_result)}",
                            error="TYPE_INVARIANT_VIOLATION"
                        )
                    
                    
                    # 3. Завершаем выполнение действия в состоянии паттерна
                    if self.current_pattern_state_id:
                        self.pattern_state_manager.finish_action_execution(self.current_pattern_state_id, {
                            "action_name": decision.reason,
                            "result": execution_result.result,
                            "status": execution_result.status.value
                        })
                    
                    # 3. Запись результата выполнения
                    self.session.register_step(
                        step_number=current_step,
                        capability_name=decision.capability.name,
                        skill_name = decision.capability.skill_name,
                        action_item_id = action_item_id,
                        observation_item_ids = execution_result.observation_item_id,
                        summary=execution_result.summary,
                        status=execution_result.status.value
                    )
                    
                    # 3.5 Обновление статуса шага в плане, если он был выполнен
                    if hasattr(self.session, 'current_plan_step_id') and self.session.current_plan_step_id:
                        await self._update_step_status_via_capability(
                            session=self.session,
                            step_id=self.session.current_plan_step_id,
                            status="completed" if execution_result.status == ExecutionStatus.SUCCESS else "failed",
                            result=execution_result.result,
                            error=execution_result.error
                        )
                        # Очищаем ID текущего шага после обновления
                        self.session.current_plan_step_id = None
                    
                    # 4. Оценка прогресса и обновление состояния
                    progressed = self.progress.evaluate(self.session)
                    self.state.register_progress(progressed)
                    
                    # Обновляем прогресс в состоянии паттерна
                    if self.current_pattern_state_id:
                        self.pattern_state_manager.register_progress(self.current_pattern_state_id, progressed)
                        
                except Exception as e:
                    await event_bus.publish_simple(
                        event_type=EventType.ERROR,
                        source="AgentRuntime",
                        data={
                            "message": f"Ошибка в работе агента на шаге {current_step}: {e}",
                            "step": current_step,
                            "error": str(e),
                            "context": "agent_execution_error"
                        }
                    )
                    self.state.register_error()
                    
                    # Регистрация ошибки в состоянии паттерна
                    if self.current_pattern_state_id:
                        self.pattern_state_manager.register_error(self.current_pattern_state_id)
                    
                    # Регистрация ошибки в контексте
                    error_item_id = self.session.record_error(
                        error_data=str(e),
                        error_type="execution_error",
                        step_number=current_step,
                        metadata=ContextItemMetadata(
                            source="agent_runtime",
                            timestamp=datetime.now()
                        )
                    )
                    
                    # Обновление статуса шага в плане при ошибке
                    if hasattr(self.session, 'current_plan_step_id') and self.session.current_plan_step_id:
                        await self._update_step_status_via_capability(
                            session=self.session,
                            step_id=self.session.current_plan_step_id,
                            status="failed",
                            error=str(e)
                        )
                        # Очищаем ID текущего шага после обновления
                        self.session.current_plan_step_id = None
            
            # Обновление состояния сессии
            self.state.step += 1
            self.session.last_activity = datetime.now()
            # Сохраняем текущий домен в сессии для возможного динамического переключения
            self.session.current_domain = detected_domain
        
        # Регистрация завершения сессии
        self.session.record_system_event(
            event_type="session_complete",
            description=f"Result: {self.session.get_summary()} (domain: {detected_domain})",
            metadata=ContextItemMetadata(
                timestamp=datetime.now(),
                step_number=self.state.step
            )
        )
        
        # Завершаем состояние текущего паттерна
        if self.current_pattern_state_id:
            self.pattern_state_manager.update_state(self.current_pattern_state_id, {
                "status": ComposablePatternStatus.COMPLETED if self.state.finished else ComposablePatternStatus.STOPPED
            })
        
        return self.session

    
    async def _update_step_status_via_capability(
        self, 
        session, 
        step_id: str, 
        status: str,
        result: Any = None,
        error: str = None
    ):
        """Обновление статуса шага ИСКЛЮЧИТЕЛЬНО через capability PlanningSkill.
        
        ПАРАМЕТРЫ:
        - session: контекст сессии
        - step_id: ID шага для обновления
        - status: новый статус (completed/failed)
        - result: результат выполнения (опционально)
        - error: описание ошибки (опционально)
        """
        try:
            # Получение текущего плана из контекста
            current_plan_item = session.get_current_plan()
            if not current_plan_item:
                await event_bus.publish_simple(
                    event_type=EventType.WARNING,
                    source="AgentRuntime",
                    data={
                        "message": "Невозможно обновить статус шага: план не найден в контексте",
                        "context": "update_step_status_error"
                    }
                )
                return
            
            # Получение capability для обновления статуса шага
            capability = self.system.get_capability("planning.update_step_status")
            if not capability:
                await event_bus.publish_simple(
                    event_type=EventType.ERROR,
                    source="AgentRuntime",
                    data={
                        "message": "Capability 'planning.update_step_status' не найдена, невозможно обновить статус шага",
                        "capability_name": "planning.update_step_status",
                        "context": "capability_not_found"
                    }
                )
                return
            
            # Подготовка параметров для capability
            parameters = {
                "plan_id": current_plan_item.item_id,
                "step_id": step_id,
                "status": status,
                "context": f"Автоматическое обновление статуса после выполнения шага"
            }
            
            if result is not None:
                # Создаем краткое описание результата
                result_summary = str(result)
                if len(result_summary) > 500:
                    result_summary = result_summary[:500] + "..."
                parameters["result_summary"] = result_summary
            
            if error is not None:
                parameters["error"] = error
            
            # Выполнение capability для обновления статуса
            await self.executor.execute_capability(
                capability=capability,
                parameters=parameters,
                session_context=session,
                system_context = self.system

            )
        
        except Exception as e:
            await event_bus.publish_simple(
                event_type=EventType.ERROR,
                source="AgentRuntime",
                data={
                    "message": f"Ошибка при обновлении статуса шага через capability: {str(e)}",
                    "error": str(e),
                    "context": "update_step_status_capability_error"
                }
            )
```

## Преимущества предлагаемого подхода

1. **Разделение ответственностей**: Каждый компонент теперь находится в своей поддиректории с четкой ответственностью
2. **Лучшая тестируемость**: Компоненты можно тестировать изолированно
3. **Улучшенная модульность**: Каждая подсистема может развиваться независимо
4. **Соблюдение принципов SOLID**: Особенно ISP (Interface Segregation Principle) и SRP (Single Responsibility Principle)
5. **Улучшенная читаемость кода**: Логическая группировка файлов по функциональности

## План миграции

1. Создать новые поддиректории с новой структурой
2. Перенести файлы в соответствующие поддиректории
3. Обновить все импорты в проекте, чтобы использовать новые пути
4. Проверить работоспособность приложения
5. После успешной проверки обновить зависимости в других модулях

## Зависимости

- Domain слой: `core/domain/agent_runtime_models/model.py` (модели данных)
- Application слой: `core/application/agent_runtime_interfaces/`, `core/application/agent_runtime_execution/`, `core/application/agent_runtime_thinking_patterns/`, `core/application/agent_runtime_utils/`, `core/application/agent_runtime/runtime.py`

Таким образом, мы достигаем более четкой архитектуры, соответствующей принципам Clean Architecture, при этом сохраняя всю функциональность оригинального агента выполнения.