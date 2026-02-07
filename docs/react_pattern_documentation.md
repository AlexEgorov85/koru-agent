# ReAct Паттерн в Koru AI Agent Framework

## Обзор

ReAct (Reasoning + Acting) паттерн - это ключевой компонент фреймворка, реализующий цикл рассуждения и действия для решения сложных задач. Паттерн позволяет агенту чередовать этапы анализа ситуации (Reasoning) и выполнения действий (Acting), основываясь на полученных наблюдениях.

## Архитектура

### Основные компоненты

1. **ReActPattern** - компонуемый паттерн, реализующий логику ReAct цикла
2. **ComposablePatternAdapter** - адаптер для интеграции компонуемых паттернов с IThinkingPattern
3. **ReActState** - модель состояния для отслеживания прогресса выполнения
4. **PatternRecoveryManager** - общий менеджер восстановления после ошибок
5. **Промты** - системные инструкции для LLM

### Состояние ReAct цикла

Класс `ReActState` управляет состоянием выполнения задачи:

- `goal` - основная цель задачи
- `steps` - история выполненных шагов (рассуждения, действия, наблюдения)
- `current_step` - текущий номер шага
- `is_completed` - флаг завершения задачи
- `context` - дополнительные данные контекста
- `metrics` - метрики выполнения

Каждый шаг представлен классом `ReActStep` с типом действия:
- `THOUGHT` - рассуждение
- `ACTION` - действие
- `OBSERVATION` - наблюдение
- `REASONING` - логика рассуждения

## Функциональность

### Основной цикл

ReAct паттерн реализует следующий цикл:

1. **Получение цели** - извлекает задачу из контекста
2. **Формирование промта** - создает системный и пользовательский промты
3. **Обращение к LLM** - отправляет запрос к языковой модели
4. **Обработка ответа** - парсит и валидирует ответ от LLM
5. **Выполнение действия** - выполняет выбранное действие
6. **Обработка наблюдения** - анализирует результат действия
7. **Повтор** - возврат к шагу 2 до достижения цели или лимита итераций

### Интеграция с LLM

Паттерн интегрируется с LLM через провайдер, передаваемый при инициализации. Поддерживается:

- Формирование контекста с историей предыдущих шагов
- Обработка структурированных ответов в формате JSON
- Обработка ошибок при обращении к LLM
- Резервная логика при недоступности LLM

### Обработка наблюдений

Метод `process_observation` позволяет паттерну обрабатывать результаты выполненных действий:

- Сохраняет наблюдения в истории выполнения
- Анализирует результаты для планирования следующих шагов
- Обновляет внутреннее состояние на основе наблюдений

### Восстановление после ошибок

ReAct паттерн интегрируется с общим механизмом восстановления, предоставляемым `PatternRecoveryManager`:

- **Создание чекпоинтов** - сохранение состояния паттерна в определенные моменты
- **Восстановление из чекпоинта** - восстановление предыдущего состояния при необходимости
- **Откат к безопасному паттерну** - переключение на резервный паттерн мышления при критических ошибках
- **Интеграция с атомарными действиями** - восстановление работает на уровне отдельных атомарных действий

## Компонуемая архитектура

### Использование компонуемых паттернов

ReAct паттерн реализован как компонуемый паттерн (`ComposablePattern`), что позволяет:

- Легко комбинировать с другими паттернами
- Использовать напрямую с интерфейсом `IThinkingPattern` (так как теперь implements этот интерфейс)
- Интегрировать в систему компонуемых агентов

### Прямая интеграция с IThinkingPattern

Теперь `ComposablePattern` реализует тот же интерфейс, что и `IThinkingPattern`, что позволяет:

- Использовать компонуемые паттерны напрямую в системе
- Устранить необходимость в адаптере
- Обеспечить полную совместимость с существующим кодом

## Параметры настройки

Паттерн поддерживает настраиваемые параметры:

- `max_iterations` - максимальное количество итераций цикла
- `llm_provider` - провайдер языковой модели
- `prompt_renderer` - рендерер промтов

## Использование

### Инициализация компонуемого паттерна

```python
from application.agent.composable_patterns.patterns import ReActPattern

# Создание компонуемого паттерна с LLM провайдером
react_pattern = ReActPattern(
    llm_provider=llm_provider,
    prompt_renderer=prompt_renderer,
    max_iterations=10
)
```

### Использование в системе

```python
from domain.models.agent.agent_state import AgentState

# Паттерн можно использовать напрямую как IThinkingPattern
state = AgentState()
class Context:
    goal = "Решить задачу X"

context = Context()
capabilities = ['read_file', 'write_file', 'search']

# Выполнение задачи
result = await react_pattern.execute(state, context, capabilities)

# Адаптация к задаче
adaptation = await react_pattern.adapt_to_task("Опишите задачу")
```

### Выполнение задачи

```python
from domain.models.agent.agent_state import AgentState

state = AgentState()
class Context:
    goal = "Решить задачу X"

context = Context()
capabilities = ['read_file', 'write_file', 'search']

result = await react_pattern.execute(state, context, capabilities)
```

### Обработка наблюдений

```python
observation = {
    'result': 'Результат выполнения действия',
    'success': True
}

# Через компонуемый паттерн
obs_result = react_pattern.process_observation(observation)

# Через адаптер
adapter_result = await adapter.process_observation(observation, context)
```

### Управление состоянием

```python
# Получить текущее состояние (через компонуемый паттерн)
current_state = react_pattern.get_state()

# Восстановить состояние (через компонуемый паттерн)
react_pattern.restore_state(saved_state)

# Получить состояние через адаптер
adapter_state = await adapter.get_state()

# Восстановить состояние через адаптер
await adapter.restore_state(saved_state)
```

## Промты

ReAct паттерн использует специализированные промты, расположенные в `prompts/react/react_cycle/`:

- `system_v1.0.0.md` - системные инструкции для LLM
- `user_v1.0.0.md` - пользовательские инструкции
- `_index.yaml` - описание и метаданные промтов

## Тестирование

Для паттерна доступны модульные тесты в `tests/application/agent/thinking_patterns/test_react_pattern_enhanced.py`, покрывающие:

- Инициализацию и основные методы компонуемого паттерна
- Интеграцию с LLM
- Обработку ошибок
- Управление состоянием
- Работу с наблюдениями
- Функциональность адаптера

## Примеры использования

### Простой пример компонуемого паттерна

```python
from application.agent.composable_patterns.patterns import ReActPattern
from domain.models.agent.agent_state import AgentState

def example():
    # Создаем паттерн (без LLM для демонстрации резервной логики)
    pattern = ReActPattern(max_iterations=5)
    
    # Подготовим контекст задачи
    class Context:
        goal = "Найти все файлы Python в проекте"
    
    state = AgentState()
    context = Context()
    capabilities = ["file_search", "file_read", "code_analysis"]
    
    composable_context = {
        "state": state,
        "context": context,
        "available_capabilities": capabilities,
        "step": state.step
    }
    
    # Выполняем задачу
    result = pattern.execute(composable_context)
    
    print(f"Действие: {result['action']}")
    print(f"Рассуждение: {result['thought']}")
    
    return result

# Запуск примера
# example()
```

### Пример с использованием адаптера

```python
from application.agent.composable_patterns.patterns import ReActPattern
from application.agent.adapters.composable_to_classic import ComposablePatternAdapter
from domain.models.agent.agent_state import AgentState

async def example_with_adapter():
    # Создаем компонуемый паттерн
    composable_pattern = ReActPattern(max_iterations=5)
    
    # Создаем адаптер
    adapter = ComposablePatternAdapter(composable_pattern)
    
    # Подготовим контекст задачи
    class Context:
        goal = "Найти все файлы Python в проекте"
    
    state = AgentState()
    context = Context()
    capabilities = ["file_search", "file_read", "code_analysis"]
    
    # Выполняем задачу через адаптер
    result = await adapter.execute(state, context, capabilities)
    
    print(f"Действие: {result['action']}")
    print(f"Рассуждение: {result['thought']}")
    
    return result

# Запуск примера
# asyncio.run(example_with_adapter())
```

## Интеграция с шиной событий

ReAct паттерн интегрируется с общей шиной событий через атомарные действия:

- Каждое атомарное действие (Think, Act, Observe) публикует события в шину
- Исполнитель атомарных действий также публикует события о начале и завершении действий
- События позволяют отслеживать прогресс, обнаруживать ошибки и мониторить производительность
- Поддерживается полная история выполнения с детализацией на уровне атомарных действий

## Использование существующих компонентов

ReAct паттерн использует следующие существующие компоненты системы:

- **PatternRecoveryManager** - общий менеджер восстановления после ошибок (вместо создания специализированного)
- **AtomicActionExecutor** - исполнитель атомарных действий
- **Система промтов** - для генерации инструкций для LLM
- **ReActState** - модель состояния для отслеживания прогресса
- **Сессионный контекст** - для передачи данных между действиями
- **Pydantic модели** - для структурированных ответов от LLM

## Заключение

Компонуемый ReAct паттерн предоставляет мощный и гибкий механизм для решения сложных задач через чередование рассуждений и действий. Архитектура паттерна обеспечивает:

- **Компонуемость** - возможность комбинирования с другими паттернами
- **Совместимость** - интеграция с существующей системой через адаптер
- **Надежность** - через встроенное восстановление
- **Гибкость** - через настраиваемые параметры
- **Расширяемость** - через интеграцию с системой промтов
- **Безопасность** - через валидацию принимаемых решений
- **Отслеживаемость** - через детальную историю выполнения
- **Интеграция с событиями** - через публикацию событий в шину