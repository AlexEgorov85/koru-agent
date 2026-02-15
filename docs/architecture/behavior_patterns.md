# Паттерны поведения (Behavior Patterns)

## Архитектурные гарантии

1. **Полная изоляция через `ApplicationContext`**  
   - Все паттерны получают доступ к системным ресурсам только через `ApplicationContext`
   - Запрещены прямые импорты и обращения к `AgentRuntime.system`
   - Все зависимости инжектятся через конструктор

2. **Версионирование как у промптов (v1.0.0)**  
   - Каждый паттерн имеет версию в формате семантического версионирования
   - Версии хранятся в `data/behaviors/{type}/{pattern_id}.yaml`
   - Поддерживается одновременная работа разных версий паттернов

3. **Единый интерфейс `BehaviorPatternInterface`**  
   - Все паттерны реализуют один и тот же интерфейс
   - Единая точка входа для анализа и принятия решений
   - Упрощает тестирование и замену паттернов

4. **Горячая перезагрузка через `BehaviorStorage`**  
   - Возможность обновления паттернов без перезапуска системы
   - Поддержка статусов: `draft`, `active`, `deprecated`, `archived`
   - Автоматическая валидация при загрузке

5. **Контрактная валидация вход/выход**  
   - Каждый паттерн имеет определенные контракты для входных и выходных данных
   - Валидация происходит через `ContractService`
   - Защита от некорректных данных на границах компонентов

## Структура метаданных
```yaml
version: "1.0.0"
pattern_id: "react.v1.0.0"
name: "ReAct"
description: "Reasoning + Acting без планирования"
supported_skills: ["book_library", "sql_query"]
required_capabilities: ["generic.execute"]
context_requirements:
  min_steps: 0
  max_steps: 10
status: "active"  # draft|active|deprecated|archived
```

## Принципы проектирования

### 1. Изоляция состояния
Каждый паттерн должен быть полностью изолирован от других. Не должно быть общего состояния между экземплярами паттернов, даже если они одного типа но разных версий.

### 2. Независимость от инфраструктуры
Паттерны не должны зависеть от конкретных реализаций LLM, хранилищ данных или других инфраструктурных компонентов. Вместо этого они должны использовать абстракции, предоставляемые через `ApplicationContext`.

### 3. Верифицируемое поведение
Поведение каждого паттерна должно быть предсказуемым и поддаваться тестированию. Все внешние зависимости должны быть легко мокируемыми для целей тестирования.

### 4. Безопасность версий
Система должна обеспечивать безопасное управление несколькими версиями одного и того же паттерна. Переход с одной версии на другую не должен приводить к потере согласованности данных или состояния сессии.

## Пример реализации BehaviorPatternInterface

```python
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum

class BehaviorDecisionType(Enum):
    ACT = "act"      # Выполнить действие
    STOP = "stop"    # Завершить выполнение
    SWITCH = "switch"  # Переключить паттерн
    RETRY = "retry"  # Повторить шаг

@dataclass
class BehaviorDecision:
    action: BehaviorDecisionType
    capability_name: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None
    next_pattern: Optional[str] = None  # Для SWITCH
    reason: str = ""
    confidence: float = 1.0

class BehaviorPatternInterface(ABC):
    pattern_id: str  # e.g., "react.v1.0.0"
    
    @abstractmethod
    async def analyze_context(
        self,
        session_context: 'SessionContext',
        available_capabilities: List['Capability'],
        context_analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Анализ контекста без принятия решений"""
        pass
    
    @abstractmethod
    async def generate_decision(
        self,
        session_context: 'SessionContext',
        available_capabilities: List['Capability'],
        context_analysis: Dict[str, Any]
    ) -> BehaviorDecision:
        """Генерация решения на основе анализа"""
        pass
    
    def _filter_capabilities(
        self,
        capabilities: List['Capability'],
        required_skills: List[str]
    ) -> List['Capability']:
        """Единая точка фильтрации (устраняет дублирование)"""
        return [
            cap for cap in capabilities
            if cap.skill_name in required_skills
            and self.pattern_id.split('.')[0] in (cap.supported_strategies or [])
        ]
```

## Миграция со старых стратегий

С версии 5.1.0 устаревает интерфейс `AgentStrategyInterface` в пользу `BehaviorPatternInterface`. 
Ключевые различия:

| Старый интерфейс | Новый интерфейс |
|------------------|-----------------|
| `next_step(runtime)` | `analyze_context()` + `generate_decision()` |
| Прямой доступ к `runtime.system` | Изоляция через `ApplicationContext` |
| Отсутствие версионирования | Версионирование как у промптов |
| Циклические зависимости | Четкие границы между паттернами |

Для плавной миграции используйте [миграционный гайд](../guides/behavior_patterns_migration.md).
```