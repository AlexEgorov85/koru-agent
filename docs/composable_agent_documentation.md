# Документация: ComposableAgent - Чистая реализация ComposableAgentInterface

## Обзор

ComposableAgent - это чистая реализация интерфейса ComposableAgentInterface, предназначенная для поддержки компонуемых паттернов мышления агента. Агент позволяет динамически собирать и выполнять сложные поведения из атомарных действий, адаптируясь к различным доменам задач.

## Архитектура

### Основные компоненты

1. **ComposableAgent** - основная реализация интерфейса
2. **SimpleComposableAgent** - упрощенная версия с дополнительными удобствами
3. **DomainManager** - управление доменами и адаптацией поведения

### Интерфейс ComposableAgentInterface

Интерфейс определяет следующие методы:

- `execute_atomic_action()` - выполнение атомарного действия
- `execute_composable_pattern()` - выполнение компонуемого паттерна
- `adapt_to_domain()` - адаптация к домену
- `get_available_domains()` - получение списка доступных доменов

## Классы

### ComposableAgent

Основной класс, реализующий ComposableAgentInterface. Поддерживает выполнение атомарных действий и компонуемых паттернов, адаптацию к доменам и управление контекстом выполнения.

#### Методы

- `__init__(name: str, description: str = "")` - инициализация агента
- `async execute_atomic_action(action: AtomicAction, context: Any, parameters: Optional[Dict[str, Any]] = None)` - выполнение атомарного действия
- `async execute_composable_pattern(pattern: ComposablePattern, context: Any, parameters: Optional[Dict[str, Any]] = None)` - выполнение компонуемого паттерна
- `adapt_to_domain(domain: str)` - адаптация к домену
- `get_available_domains()` - получение списка доступных доменов

#### Примеры использования

```python
from core.composable_agent import ComposableAgent

# Создание агента
agent = ComposableAgent("MyAgent", "Agent for processing tasks")

# Выполнение атомарного действия
result = await agent.execute_atomic_action(think_action, context, {"param": "value"})

# Выполнение компонуемого паттерна
result = await agent.execute_composable_pattern(pattern, context, {"param": "value"})

# Адаптация к домену
agent.adapt_to_domain("code_analysis")
```

### SimpleComposableAgent

Упрощенная версия ComposableAgent с дополнительными удобствами, включая метод `simple_execute` для автоматического определения типа выполняемого элемента (атомарное действие или компонуемый паттерн).

#### Методы

- `__init__(name: str, description: str = "", initial_domain: Optional[str] = None)` - инициализация агента с опциональным начальным доменом
- `async simple_execute(actions_or_pattern: Any, context: Any, parameters: Optional[Dict[str, Any]] = None)` - упрощенное выполнение

#### Примеры использования

```python
from core.composable_agent import SimpleComposableAgent

# Создание простого агента
agent = SimpleComposableAgent("SimpleAgent", "Simple agent for basic tasks", "general")

# Выполнение через упрощенный метод
result = await agent.simple_execute(pattern, context)
```

## Поддерживаемые домены

ComposableAgent поддерживает следующие домены по умолчанию:

- `general` - общий домен для универсальных задач
- `code_analysis` - домен для задач анализа кода
- `database_query` - домен для работы с базами данных
- `research` - исследовательский домен
- `planning` - домен планирования
- `problem_solving` - домен решения проблем
- `data_analysis` - домен анализа данных

Агент может динамически регистрировать новые домены при необходимости.

## Атомарные действия и компонуемые паттерны

ComposableAgent работает с двумя основными типами элементов:

1. **Атомарные действия** - базовые единицы поведения (THINK, ACT, OBSERVE и т.д.)
2. **Компонуемые паттерны** - составные структуры из атомарных действий

### Создание компонуемых паттернов

```python
from core.composable_patterns.base import PatternBuilder

builder = PatternBuilder("анализ_задачи")
pattern = (builder
          .add_observe()  # Наблюдение за задачей
          .add_think()    # Размышление над задачей
          .add_act()      # Выполнение действия
          .build())
```

## Интеграция системой

ComposableAgent интегрирован с существующей архитектурой агента и может использовать:

- Системный контекст (SystemContext)
- Контекст сессии (SessionContext)
- Менеджер доменов (DomainManager)
- Атомарные действия и компонуемые паттерны

## Примеры

### Полный пример использования

```python
import asyncio
from core.composable_agent import ComposableAgent, SimpleComposableAgent
from core.composable_patterns.base import PatternBuilder
from core.atomic_actions.base import AtomicAction
from core.agent_runtime.model import StrategyDecision, StrategyDecisionType

class MockAtomicAction(AtomicAction):
    def __init__(self, name: str = "mock_action"):
        super().__init__(name, "Mock atomic action for demonstration")

    async def execute(self, runtime, context, parameters=None):
        return StrategyDecision(action=StrategyDecisionType.CONTINUE, reason="mock_action_executed")

class MockComposablePattern(ComposablePattern):
    def __init__(self, name: str = "mock_pattern"):
        super().__init__(name, "Mock composable pattern for demonstration")

    async def execute(self, runtime, context, parameters=None):
        return StrategyDecision(action=StrategyDecisionType.CONTINUE, reason="mock_pattern_executed")

async def main():
    # Создание агента
    agent = ComposableAgent("ExampleAgent", "Агент для демонстрации возможностей")
    
    # Адаптация к домену
    agent.adapt_to_domain("code_analysis")
    
    # Подготовка контекста
    context = {"task": "Анализировать производительность алгоритма сортировки"}
    
    # Создание мок-паттерна
    mock_pattern = MockComposablePattern("демонстрационный_паттерн")
    
    # Выполнение компонуемого паттерна
    result = await agent.execute_composable_pattern(mock_pattern, context)
    print(f"Результат: {result.action.value} - {result.reason}")

if __name__ == "__main__":
    asyncio.run(main())
```

## Тестирование

Для тестирования ComposableAgent созданы модульные тесты в `tests/unit/core/test_composable_agent.py`, которые проверяют все основные функции реализации, включая:

- Инициализацию агента
- Выполнение атомарных действий
- Выполнение компонуемых паттернов
- Адаптацию к доменам
- Получение списка доступных доменов
- Работу упрощенной версии агента

## Заключение

ComposableAgent предоставляет гибкую и расширяемую реализацию ComposableAgentInterface, позволяющую создавать сложные поведения агента из простых атомарных действий. Архитектура поддерживает динамическую адаптацию к различным доменам задач и позволяет легко расширять функциональность за счет компонуемых паттернов мышления.