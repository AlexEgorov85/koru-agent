# 🧩 Руководство по компонентам koru-agent

> **Версия:** 5.35.0
> **Дата обновления:** 2026-03-10
> **Статус:** approved
> **Владелец:** @system

---

## 📋 Оглавление

- [Обзор](#-обзор)
- [Типы компонентов](#-типы-компонентов)
- [Создание компонентов](#-создание-компонентов)
- [Конфигурация](#-конфигурация)
- [Ресурсы](#-ресурсы)
- [Тестирование](#-тестирование)
- [Справочник компонентов](#-справочник-компонентов)

---

## 🔍 Обзор

Компоненты — строительные блоки системы koru-agent.

### Назначение

- **Модульность**: Независимая разработка и тестирование
- **Повторное использование**: Компоненты в разных агентах
- **Версионирование**: Поддержка A/B тестирования
- **Изоляция**: Собственные кэши ресурсов

---

## 📐 Типы компонентов

### Сервисы (Services)

Бизнес-логика, интеграции с внешними системами.

```python
from core.application.services.base_service import BaseService

class SQLGenerationService(BaseService):
    async def generate_query(self, natural_language: str, schema: Dict) -> SQLQueryResult:
        pass
```

**Примеры**: `PromptService`, `ContractService`, `SQLGenerationService`, `SQLQueryService`

### Навыки (Skills)

Высокоуровневые способности агента.

```python
from core.application.skills.base_skill import BaseSkill

class PlanningSkill(BaseSkill):
    async def create_plan(self, goal: str, context: Dict) -> Plan:
        pass
```

**Примеры**: `PlanningSkill`, `BookLibrarySkill`, `FinalAnswerSkill`, `DataAnalysisSkill`

### Инструменты (Tools)

I/O операции, работа с внешними системами.

```python
from core.application.tools.base_tool import BaseTool

class FileTool(BaseTool):
    async def read_file(self, path: str) -> str:
        pass
```

**Примеры**: `FileTool`, `SQLTool`

### Паттерны поведения (Behavior Patterns)

Логика поведения агента.

```python
from core.application.behaviors.base_behavior import BehaviorPattern

class ReActPattern(BehaviorPattern):
    async def think(self, context: Dict) -> Thought:
        pass
```

**Примеры**: `ReActPattern`, `PlanningPattern`, `EvaluationPattern`, `FallbackPattern`

---

## 🛠️ Создание компонентов

### Шаг 1: Наследование

**До версии 5.34.0 (устаревший подход):**
```python
from core.components.base_component import BaseComponent

class MyComponent(BaseComponent):
    def __init__(self, config: ComponentConfig, application_context: ApplicationContext):
        super().__init__(config, application_context)
```

**Версия 5.34.0+ (DI через конструктор):**
```python
from core.components.base_component import BaseComponent
from core.interfaces import LLMInterface, EventBusInterface, PromptStorageInterface

class MyComponent(BaseComponent):
    def __init__(
        self,
        config: ComponentConfig,
        llm: LLMInterface,
        event_bus: EventBusInterface,
        prompt_storage: PromptStorageInterface,
        application_context: ApplicationContext = None  # DEPRECATED
    ):
        super().__init__(
            config=config,
            llm=llm,
            event_bus=event_bus,
            prompt_storage=prompt_storage,
            application_context=application_context
        )
```

### Шаг 2: Инициализация

```python
async def initialize(self) -> None:
    await super().initialize()
    # Дополнительная предзагрузка
```

### Шаг 3: Логика

**Использование внедрённых зависимостей:**
```python
async def execute(self, params: Dict) -> Dict:
    # Использование внедрённых интерфейсов
    self.llm.generate(...)  # вместо self.application_context.infrastructure_context.get_provider("llm")
    self.event_bus.publish(...)  # вместо self.infrastructure_context.event_bus
    prompt = self.prompt_storage.get("my_component.execute")  # вместо self.infrastructure_context.get_prompt_storage()
    
    self.validate_input(params)
    result = await self._process(prompt, params)
    self.validate_output(result)
    return result
```

### Шаг 4: Регистрация

```yaml
# registry.yaml
services:
  my_service:
    enabled: true
    dependencies: []
    prompt_versions:
      my_service.execute: v1.0.0
    manifest_path: data/manifests/services/my_service/manifest.yaml
```

---

## ⚙️ Конфигурация

### ComponentConfig

```python
class ComponentConfig:
    prompt_versions: Dict[str, str]
    input_contract_versions: Dict[str, str]
    output_contract_versions: Dict[str, str]
    parameters: Dict[str, Any]
    base_path: str  # Для изоляции файлового доступа
```

### Получение конфигурации

```python
# Внутри компонента
config = self.config
max_retries = self.config.parameters.get("max_retries", 3)
prompt_version = self.config.prompt_versions["my_component.execute"]
```

---

## 📦 Ресурсы

### Промпты

**Устаревший способ (до 5.34.0):**
```python
prompt_text = self.get_prompt("my_component.execute")
```

**Текущий способ (5.34.0+):**
```python
prompt_text = self.prompt_storage.get("my_component.execute")
```

### Контракты

**Устаревший способ (до 5.34.0):**
```python
input_schema = self.get_input_contract("my_component.execute")
output_schema = self.get_output_contract("my_component.execute")
```

**Текущий способ (5.34.0+):**
```python
input_schema = self.contract_storage.get_input("my_component.execute")
output_schema = self.contract_storage.get_output("my_component.execute")
```

### Валидация

```python
self.validate_input(params)
self.validate_output(result)
```

---

## 🧪 Тестирование

### Юнит-тесты

**Устаревший способ (до 5.34.0):**
```python
import pytest

@pytest.mark.asyncio
async def test_my_service():
    config = ComponentConfig(
        prompt_versions={"my_service.execute": "v1.0.0"}
    )
    service = MyService(config, application_context)
    await service.initialize()

    result = await service.execute({"param": "value"})
    assert result is not None
```

**Текущий способ (5.34.0+ с DI):**
```python
import pytest
from unittest.mock import AsyncMock, MagicMock

@pytest.mark.asyncio
async def test_my_service():
    # Создание моков интерфейсов
    llm_mock = AsyncMock(spec=LLMInterface)
    event_bus_mock = MagicMock(spec=EventBusInterface)
    prompt_storage_mock = MagicMock(spec=PromptStorageInterface)
    
    config = ComponentConfig(
        prompt_versions={"my_service.execute": "v1.0.0"}
    )
    service = MyService(
        config=config,
        llm=llm_mock,
        event_bus=event_bus_mock,
        prompt_storage=prompt_storage_mock
    )
    await service.initialize()

    result = await service.execute({"param": "value"})
    assert result is not None
```

### Тесты изоляции

```python
@pytest.mark.asyncio
async def test_component_isolation():
    config1 = ComponentConfig(base_path="/path1")
    config2 = ComponentConfig(base_path="/path2")
    
    component1 = MyService(config1, app_context1)
    component2 = MyService(config2, app_context2)
    
    await component1.initialize()
    await component2.initialize()
    
    assert component1._cached_prompts != component2._cached_prompts
```

---

## 📚 Справочник компонентов

### Инфраструктурные

| Компонент | Модуль | Описание |
|-----------|--------|----------|
| `InfrastructureContext` | `core.infrastructure.context` | Общий контекст |
| `ProviderFactory` | `core.infrastructure.providers` | Фабрика провайдеров |
| `ResourceRegistry` | `core.infrastructure.storage` | Реестр ресурсов |

### Прикладные

| Компонент | Модуль | Описание |
|-----------|--------|----------|
| `ApplicationContext` | `core.application.context` | Контекст приложения |
| `ComponentRegistry` | `core.application.components` | Реестр компонентов |
| `BehaviorManager` | `core.application.agent.components` | Управление поведениями |

### Сервисы

| Компонент | Модуль | Описание |
|-----------|--------|----------|
| `PromptService` | `core.application.services` | Управление промптами |
| `ContractService` | `core.application.services` | Управление контрактами |
| `SQLGenerationService` | `core.application.services.sql_generation` | Генерация SQL |
| `SQLQueryService` | `core.application.services.sql_query` | Выполнение SQL |
| `SQLValidatorService` | `core.application.services.sql_validator` | Валидация SQL |

### Навыки

| Компонент | Модуль | Описание |
|-----------|--------|----------|
| `PlanningSkill` | `core.application.skills.planning` | Планирование |
| `BookLibrarySkill` | `core.application.skills.book_library` | Библиотека книг |
| `FinalAnswerSkill` | `core.application.skills.final_answer` | Финальный ответ |
| `DataAnalysisSkill` | `core.application.skills.data_analysis` | Анализ данных |

### Инструменты

| Компонент | Модуль | Описание |
|-----------|--------|----------|
| `FileTool` | `core.application.tools` | Файловые операции |
| `SQLTool` | `core.application.tools` | SQL-запросы |

### Паттерны поведения

| Компонент | Модуль | Описание |
|-----------|--------|----------|
| `ReActPattern` | `core.application.behaviors.react` | ReAct-цикл |
| `PlanningPattern` | `core.application.behaviors.planning` | Планирование |
| `EvaluationPattern` | `core.application.behaviors.evaluation` | Оценка |
| `FallbackPattern` | `core.application.behaviors.fallback` | Резервное поведение |

---

## 🔗 Ссылки

- [Обзор архитектуры](./ARCHITECTURE_OVERVIEW.md)
- [Конфигурация](./CONFIGURATION_MANUAL.md)
- [API Reference](./API_REFERENCE.md)
- [BaseComponent](../core/components/base_component.py)
- [Интерфейсы](../core/interfaces/)
- [Жизненный цикл компонентов](./architecture/lifecycle.md)

---

*Документ обновлён: 2026-03-10*

*Документ автоматически сгенерирован. Не редактируйте вручную.*
