# Миграция с AgentStrategyInterface на BehaviorPatternInterface

Этот гайд поможет вам обновить ваш код с устаревшего интерфейса стратегий (`AgentStrategyInterface`) до нового интерфейса паттернов поведения (`BehaviorPatternInterface`).

## Обзор изменений

### Было:
- `AgentStrategyInterface` с методом `next_step(runtime)`
- Прямой доступ к `runtime.system` и его методам
- Циклические зависимости между стратегиями
- Отсутствие версионирования стратегий

### Стало:
- `BehaviorPatternInterface` с методами `analyze_context()` и `generate_decision()`
- Изоляция через `ApplicationContext`
- Версионирование паттернов как у промптов
- Горячая перезагрузка паттернов
- Контрактная валидация

## Пошаговая миграция

### 1. Замена интерфейса

**Было:**
```python
from core.agent_runtime.strategies.base import AgentStrategyInterface
from core.agent_runtime.model import StrategyDecision, StrategyDecisionType

class MyStrategy(AgentStrategyInterface):
    name = "my_strategy"
    
    async def next_step(self, runtime) -> StrategyDecision:
        # Логика стратегии с доступом к runtime
        available_caps = runtime.system.list_capabilities()
        # ...
```

**Стало:**
```python
from core.application.behaviors.base import BehaviorPatternInterface, BehaviorDecision, BehaviorDecisionType
from models.capability import Capability

class MyBehaviorPattern(BehaviorPatternInterface):
    pattern_id = "my_pattern.v1.0.0"
    
    def __init__(self, prompt_service: 'PromptService'):
        self._prompt_service = prompt_service
    
    async def analyze_context(
        self,
        session_context: 'SessionContext',
        available_capabilities: List[Capability],
        context_analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        # Анализ контекста без принятия решений
        return {
            "available_capabilities": self._filter_capabilities(
                available_capabilities,
                required_skills=["my_skill"]
            ),
            "goal": session_context.get_goal(),
            "progress": session_context.get_progress()
        }
    
    async def generate_decision(
        self,
        session_context: 'SessionContext',
        available_capabilities: List[Capability],
        context_analysis: Dict[str, Any]
    ) -> BehaviorDecision:
        # Генерация решения на основе анализа
        # Получение промпта через изолированный сервис
        prompt = await self._prompt_service.render(
            capability_name="my_pattern.reasoning",
            variables=context_analysis
        )
        
        # Логика принятия решения
        return BehaviorDecision(
            action=BehaviorDecisionType.ACT,
            capability_name="my_skill.do_something",
            parameters={"input": "data"},
            reason="selected_by_my_pattern"
        )
```

### 2. Удаление прямого доступа к системе

**Было:**
```python
# Прямой доступ к системным ресурсам
caps = runtime.system.list_capabilities()
cap = runtime.system.get_capability("some.capability")
result = await runtime.system.call_llm_with_params(...)
```

**Стало:**
```python
# Доступ через параметры методов и сервисы
# Все необходимые данные передаются параметрами
# LLM вызовы осуществляются через session_context.get_llm_provider()
llm_provider = session_context.get_llm_provider()
response = await llm_provider.generate(prompt=...)
```

### 3. Создание файла метаданных паттерна

Создайте файл в `data/behaviors/{type}/{version}.yaml`:

```yaml
version: "1.0.0"
pattern_id: "my_pattern.v1.0.0"
name: "My Pattern"
description: "Описание моего паттерна поведения"
supported_skills: ["my_skill", "another_skill"]
required_capabilities: ["my_skill.do_something"]
context_requirements:
  min_steps: 0
  max_steps: 10
status: "active"  # draft|active|deprecated|archived
quality_metrics:
  success_rate: 0.90
  avg_decision_time_ms: 500
created_at: "2026-02-15T10:00:00Z"
```

### 4. Обновление использования в рантайме

**Было:**
```python
# В AgentRuntime
self.strategy = self.get_strategy("my_strategy")
decision = await self.strategy.next_step(self)
```

**Стало:**
```python
# В AgentRuntime теперь используется BehaviorManager
decision = await self.behavior_manager.generate_next_decision(
    session_context=self.session,
    available_capabilities=available_caps
)
```

## Чек-лист миграции

- [x] Удалена старая система стратегий на основе `AgentStrategyInterface`
- [x] Заменен интерфейс с `AgentStrategyInterface` на `BehaviorPatternInterface`
- [x] Удален прямой доступ к `runtime.system.*`
- [ ] Создан файл метаданных паттерна в `data/behaviors/`
- [ ] Обновлены все зависимости и импорты
- [ ] Проверена изоляция состояния паттерна
- [ ] Проверена совместимость с `ApplicationContext`
- [ ] Обновлены тесты для нового интерфейса
- [ ] Проверена работа механизма переключения паттернов

## Распространенные проблемы и решения

### Проблема: "AttributeError: 'MyPattern' object has no attribute 'system'"
**Решение:** Не используйте прямой доступ к системным ресурсам. Передавайте все необходимые зависимости через конструктор.

### Проблема: "Невозможно получить список capability"
**Решение:** Список capability теперь передается параметром в `generate_decision()`.

### Проблема: "LLM вызовы не работают"
**Решение:** Используйте `session_context.get_llm_provider()` вместо `runtime.system.call_llm_with_params()`.

## Поддержка

Все старые стратегии полностью удалены из системы. Система теперь использует только паттерны поведения. 
Если у вас возникли вопросы по миграции, обратитесь в #architecture-team или создайте тикет в JIRA с меткой `behavior-pattern-migration`.