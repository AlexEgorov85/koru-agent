# 🧩 Документация компонентов

> **Версия:** 5.1.0  
> **Дата обновления:** 2026-02-17  
> **Статус:** approved

---

## 📋 Оглавление

- [Инфраструктурные компоненты](#инфраструктурные-компоненты)
- [Прикладные компоненты](#прикладные-компоненты)
- [Компоненты агента](#компоненты-агента)

---

## 🔍 Обзор

Этот раздел содержит документацию по всем компонентам системы Agent_v5.

### Инфраструктурные компоненты

| Компонент | Описание | Статус |
|-----------|----------|--------|
| [InfrastructureContext](./infrastructure/context.md) | Общий контекст инфраструктуры | 🚧 В работе |
| [Провайдеры](./infrastructure/providers.md) | LLM, Database провайдеры | 🚧 В работе |
| [Хранилища](./infrastructure/storage.md) | Хранилища промптов и контрактов | 🚧 В работе |

### Прикладные компоненты

| Компонент | Описание | Статус |
|-----------|----------|--------|
| [ApplicationContext](./application/context.md) | Изолированный контекст агента | 🚧 В работе |
| [Сервисы](./application/services.md) | Прикладные сервисы | 🚧 В работе |
| [Инструменты](./application/tools.md) | I/O инструменты | 🚧 В работе |

### Компоненты агента

| Компонент | Описание | Статус |
|-----------|----------|--------|
| [AgentRuntime](./agent/runtime.md) | Runtime агента | 🚧 В работе |
| [Паттерны поведения](./agent/behaviors.md) | ReAct, Planning, Evaluation | 🚧 В работе |
| [Навыки](./agent/skills.md) | Высокоуровневые способности | 🚧 В работе |

---

## 📐 Типы компонентов

### Сервисы (Services)

Бизнес-логика и интеграции с внешними системами.

```python
from core.application.services.base_service import BaseService

class MyService(BaseService):
    async def execute(self, params: Dict) -> Dict:
        pass
```

### Навыки (Skills)

Высокоуровневые способности агента.

```python
from core.application.skills.base_skill import BaseSkill

class MySkill(BaseSkill):
    async def execute(self, params: Dict) -> Dict:
        pass
```

### Инструменты (Tools)

I/O операции и работа с внешними системами.

```python
from core.application.tools.base_tool import BaseTool

class MyTool(BaseTool):
    async def execute(self, params: Dict) -> Dict:
        pass
```

### Паттерны поведения (Behavior Patterns)

Логика поведения агента.

```python
from core.application.behaviors.base_behavior import BehaviorPattern

class MyBehavior(BehaviorPattern):
    async def think(self, context: Dict) -> Thought:
        pass
```

---

## 🔗 Ссылки

- [Руководство по компонентам](../COMPONENTS_GUIDE.md)
- [Обзор архитектуры](../ARCHITECTURE_OVERVIEW.md)
- [API Reference](../API_REFERENCE.md)

---

*Документ автоматически поддерживается в актуальном состоянии*
