# Koru AI Agent Framework - Документация

Добро пожаловать в документацию Koru AI Agent Framework - гибкой и расширяемой системы для создания, управления и выполнения AI-агентов, способных решать сложные задачи через компонуемые паттерны мышления.

## Обзор

Koru AI Agent Framework реализует архитектуру, в которой LLM не управляет системой напрямую, а принимает решения, которые строго валидируются и исполняются кодом. Это обеспечивает контролируемость, надежность и безопасность AI-агентов.

### Основные особенности

- **Компонуемость**: Возможность комбинировать различные паттерны мышления для решения сложных задач
- **Чистая архитектура**: Архитектура, следующая принципам чистой архитектуры (Clean Architecture)
- **Безопасность**: Строгая валидация решений, принятых LLM, и контролируемое выполнение действий
- **Расширяемость**: Легкое создание новых компонентов и адаптация под специфические задачи
- **Версионирование**: Полнофункциональная система управления версиями промтов
- **Доменная адаптация**: Агенты могут адаптироваться к различным областям задач
- **Тестируемость**: Бизнес-логика может быть протестирована без внешних зависимостей

## Структура документации

### [1. Введение](./introduction/)
- [Установка и настройка](./introduction/installation.md) - Пошаговое руководство по установке фреймворка
- [Быстрый старт](./introduction/quickstart.md) - Примеры использования для новичков

### [2. Архитектура](./architecture/)
- [Обзор архитектуры](./architecture/overview.md) - Основные принципы и слои системы
- [Слои системы](./architecture/layers.md) - Подробное описание каждого слоя
- [Система событий](./architecture/event_bus.md) - Коммуникация между компонентами
- [Потоки данных](./architecture/data_flow.md) - Как данные перемещаются по системе
- [Разработка под свои задачи](./architecture/custom_development.md) - Как адаптировать архитектуру под специфические нужды

### [3. Концепции](./concepts/)
- [Паттерны мышления](./concepts/thinking_patterns.md) - Стратегии решения задач
- [Компонуемые агенты](./concepts/composable_agents.md) - Основные исполнители логики
- [Атомарные действия](./concepts/atomic_actions.md) - Минимальные неделимые операции
- [Управление доменами](./concepts/domain_management.md) - Адаптация к различным областям задач
- [Разработка под свои задачи](./concepts/custom_development.md) - Создание специфических концепций

### [4. Система промтов](./prompts/)
- [Обзор системы](./prompts/overview.md) - Архитектура и возможности
- [Структура хранения](./prompts/structure.md) - Как организованы промты
- [Версионирование](./prompts/versioning.md) - Управление версиями промтов
- [Роли промтов](./prompts/roles.md) - Различные типы промтов и их назначение
- [Валидация](./prompts/validation.md) - Проверка безопасности и корректности
- [Интеграция с агентами](./prompts/integration_with_agents.md) - Использование промтов агентами
- [Примеры и сценарии](./prompts/examples_and_use_cases.md) - Практические примеры
- [Разработка под свои задачи](./prompts/custom_development.md) - Создание специфических промтов

### [5. Инструменты и навыки](./tools_skills/)
- [Обзор инструментов](./tools_skills/tools_overview.md) - Система инструментов
- [Создание навыков](./tools_skills/skills_creation.md) - Как создавать навыки
- [Разработка инструментов](./tools_skills/tools_development.md) - Создание инструментов
- [Разработка под свои задачи](./tools_skills/custom_development.md) - Адаптация под специфические нужды

### [6. Ядро системы](./core/)
- [Обзор ядра](./core/overview.md) - Центральные компоненты системы
- [Компонуемые агенты](./core/composable_agent.md) - Подробное описание агентов
- [Атомарные действия](./core/atomic_actions.md) - Реализация минимальных операций
- [Управление доменами](./core/domain_management.md) - Интеграция с доменами
- [Разработка под свои задачи](./core/custom_development.md) - Создание специфических компонентов ядра
- [Разработка агентов под свои задачи](./core/custom_agent_development.md) - Адаптация агентов

### [7. Конфигурация](./configuration/)
- [Обзор конфигурации](./configuration/overview.md) - Система управления конфигурацией
- [Загрузчик конфигурации](./configuration/config_loader.md) - Загрузка из различных источников
- [Модели конфигурации](./configuration/config_models.md) - Структура конфигурационных данных
- [Разработка под свои задачи](./configuration/custom_development.md) - Настройка под специфические нужды

### [8. Тестирование](./testing/)
- [Обзор тестирования](./testing/overview.md) - Стратегии и подходы к тестированию

### [9. Примеры](./examples/)
- [Обзор примеров](./examples/overview.md) - Практические примеры использования
- [Сценарии использования](./examples/usage_scenarios.md) - Примеры для конкретных задач

### [10. Безопасность](./security/)
- [Руководство по безопасности](./security/guide.md) - Рекомендации по обеспечению безопасности
- [Проверка безопасности](./security/validation.md) - Методы проверки безопасности компонентов

### [11. Руководства](./guides/)
- [Руководство по миграции](./migration_guide.md) - Как обновлять фреймворк до новых версий
- [Лучшие практики](./best_practices_guide.md) - Рекомендации по использованию фреймворка
- [Полное руководство](./complete_guide.md) - Комплексное руководство по всем аспектам фреймворка

## Начало работы

Для начала работы с фреймворком:

1. [Установите фреймворк](./introduction/installation.md) следуя инструкциям по установке
2. Ознакомьтесь с [руководством по быстрому старту](./introduction/quickstart.md) для базового понимания
3. Изучите [архитектуру системы](./architecture/overview.md) для понимания принципов работы
4. Попробуйте [примеры использования](./examples/overview.md) для практических навыков

## Основные компоненты

### 1. Компонуемые агенты

Компонуемые агенты - это основные исполнители логики в системе:

```python
from application.factories.agent_factory import AgentFactory
from domain.value_objects.domain_type import DomainType

# Создание агента
agent = await AgentFactory().create_agent(
    agent_type="composable",
    domain=DomainType.CODE_ANALYSIS
)

# Выполнение задачи
result = await agent.execute_task(
    task_description="Проанализируй этот Python код на наличие уязвимостей безопасности",
    context={
        "code": """
def login(username, password):
    query = f"SELECT * FROM users WHERE username='{username}' AND password='{password}'"
    return execute_query(query)
""",
        "language": "python"
    }
)
```

### 2. Паттерны мышления

Паттерны мышления определяют стратегии решения задач:

```python
from domain.abstractions.thinking_pattern import IThinkingPattern

class SecurityAnalysisPattern(IThinkingPattern):
    @property
    def name(self) -> str:
        return "security_analysis_pattern"
    
    async def execute(self, state, context, available_capabilities):
        # Логика выполнения анализа безопасности
        pass
```

### 3. Атомарные действия

Атомарные действия - минимальные неделимые операции:

```python
from domain.abstractions.atomic_action import IAtomicAction

class FileReaderAction(IAtomicAction):
    @property
    def name(self) -> str:
        return "file_reader"
    
    async def execute(self, parameters):
        # Логика чтения файла
        pass
```

### 4. Система промтов

Система промтов обеспечивает гибкое управление и версионирование:

```python
# Структура хранения:
# prompts/{domain}/{capability}/{role}/v{version}.md

# Пример промта:
"""
---
provider: openai
role: system
status: active
variables:
  - name: task_description
    type: string
    required: true
    description: "Описание задачи для анализа"
---

# Инструкции для агента анализа безопасности

Ты являешься экспертом в области безопасности кода...
"""
```

## Безопасность и надежность

Фреймворк включает встроенные механизмы безопасности:

- **Валидация промтов**: Проверка на безопасность и корректность
- **Проверка параметров**: Контроль входных данных
- **Контроль доступа**: Ограничение доступа к ресурсам
- **Изоляция выполнения**: Предотвращение побочных эффектов
- **Обработка ошибок**: Надежная обработка исключений

## Сообщество и поддержка

- GitHub: [https://github.com/AlexEgorov85/Agent_code](https://github.com/AlexEgorov85/Agent_code)
- Документация: [https://github.com/AlexEgorov85/Agent_code/tree/main/docs](https://github.com/AlexEgorov85/Agent_code/tree/main/docs)

Для вопросов и обсуждений создайте issue в репозитории или обратитесь к соответствующему разделу документации.