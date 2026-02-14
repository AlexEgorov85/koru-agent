# Руководство по использованию песочницы

## Обзор

Песочница (sandbox) - это специальный режим работы агента, который позволяет:
- Тестировать новые версии промптов и контрактов
- Использовать черновые (draft) версии
- Безопасно экспериментировать с изменениями

## Создание песочницы

```python
from core.application.context.application_context import ApplicationContext
from core.config.models import AgentConfig

# Создание конфигурации агента
agent_config = AgentConfig(
    prompt_versions={
        "planning": "v1.0.0",  # Основная версия
        "book_library": "v1.0.0"
    },
    input_contract_versions={
        "planning": "v1.0.0"
    },
    output_contract_versions={
        "planning": "v1.0.0"
    }
)

# Создание песочницы
sandbox_context = ApplicationContext(
    infrastructure_context=infra,
    config=agent_config,
    profile="sandbox"  # Указываем профиль песочницы
)
```

## Использование оверрайдов

### Установка оверрайда версии

```python
# Установка оверрайда для конкретного capability
sandbox_context.set_prompt_override("planning", "v1.1.0-draft")

# Инициализация контекста с новыми версиями
await sandbox_context.initialize()
```

### Проверка оверрайдов

```python
# Получение промпта - будет возвращена оверрайденная версия
prompt = sandbox_context.get_prompt("planning")  # Вернет v1.1.0-draft
```

## Горячая замена версий

Для быстрого переключения между версиями без перезапуска инфраструктуры:

```python
# Клонирование контекста с новыми версиями
new_context = await sandbox_context.clone_with_version_override(
    prompt_overrides={
        "planning": "v2.0.0-experimental",
        "book_library": "v1.2.0-alpha"
    },
    contract_overrides={
        "planning": "v2.0.0-experimental"
    }
)

# Новый контекст готов к использованию
new_prompt = new_context.get_prompt("planning")
```

## Ограничения и особенности

### Ограничения
- Оверрайды версий разрешены только в профиле `sandbox`
- В профиле `prod` попытка установки оверрайда вызовет `RuntimeError`
- В `prod` режиме разрешены только версии со статусом `active`

### Проверка статуса версии
Версии в YAML файлах должны содержать поле `status`:
```yaml
content: "Содержимое промпта"
version: "v1.1.0"
skill: "planning"
capability: "planning"
status: "draft"  # или "active", "archived"
author: "developer"
# ... другие поля
```

## Примеры сценариев

### Сценарий 1: Тестирование новой версии промпта

```python
# 1. Создаем песочницу
sandbox = ApplicationContext(infra, agent_config, profile="sandbox")

# 2. Устанавливаем оверрайд на новую версию
sandbox.set_prompt_override("planning", "v1.2.0-experimental")

# 3. Инициализируем и тестируем
await sandbox.initialize()
result = await test_agent_behavior(sandbox)
```

### Сценарий 2: А/Б тестирование версий

```python
# Создаем две песочницы с разными версиями
sandbox_a = ApplicationContext(infra, agent_config, profile="sandbox")
sandbox_b = ApplicationContext(infra, agent_config, profile="sandbox")

# Устанавливаем разные версии
sandbox_a.set_prompt_override("planning", "v1.0.0-stable")
sandbox_b.set_prompt_override("planning", "v2.0.0-improved")

# Сравниваем поведение
await sandbox_a.initialize()
await sandbox_b.initialize()

results_a = await run_test_suite(sandbox_a)
results_b = await run_test_suite(sandbox_b)
```

## Лучшие практики

1. **Используйте осмысленные суффиксы для версий в песочнице**:
   - `v1.1.0-experimental`
   - `v1.2.0-alpha`
   - `v1.0.1-draft`

2. **Не используйте песочницу для продакшн нагрузки**

3. **Регулярно очищайте тестовые версии из системы**

4. **Документируйте экспериментальные версии с понятным описанием изменений**