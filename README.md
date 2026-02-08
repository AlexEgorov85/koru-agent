# Koru AI Agent Framework

Koru AI Agent Framework - это гибкая и расширяемая система для создания, управления и выполнения AI-агентов, способных решать сложные задачи через компонуемые паттерны мышления. Фреймворк реализует архитектуру, в которой LLM не управляет системой напрямую, а принимает решения, которые строго валидируются и исполняются кодом.

## Статус проекта

**Продвинутый прототип** — архитектура готова, реализация требует завершения ключевых компонентов

## Основные особенности

- **Компонуемость**: Возможность комбинировать различные паттерны мышления для решения сложных задач
- **Чистая архитектура**: Архитектура, следующая принципам чистой архитектуры (Clean Architecture)
- **Безопасность**: Строгая валидация решений, принятых LLM, и контролируемое выполнение действий
- **Расширяемость**: Легкое создание новых компонентов и адаптация под специфические задачи
- **Версионирование**: Полнофункциональная система управления версиями промтов
- **Доменная адаптация**: Агенты могут адаптироваться к различным областям задач
- **Тестируемость**: Бизнес-логика может быть протестирована без внешних зависимостей
- **Надежность**: Механизм подтверждения доставки событий с автоматическими повторными попытками

## Архитектура

Фреймворк реализует принципы чистой архитектуры с направленными внутрь зависимостями:

```
┌─────────────────┐
│  Infrastructure │ ← Зависит от Application
│        ▲        │
│        │        │
├─────────────────┤
│   Application   │ ← Зависит от Domain
│        ▲        │
│        │        │
├─────────────────┤
│     Domain      │ ← Ядро системы, не зависит от внешних слоев
│                 │
└─────────────────┘
```

### Слои системы:

1. **Слой домена (Domain Layer)**: Содержит бизнес-логику и правила
2. **Слой приложений (Application Layer)**: Координирует работу компонентов домена
3. **Слой инфраструктуры (Infrastructure Layer)**: Реализует внешние зависимости

## Установка

```bash
# Клонировать репозиторий
git clone https://github.com/AlexEgorov85/koru-agent.git
cd Agent_code

# Создать виртуальное окружение
python -m venv venv
source venv/bin/activate  # или venv\Scripts\activate на Windows

# Установить зависимости
pip install -r requirements.txt
```

## Быстрый старт

```python
# example.py
import asyncio
from application.factories.agent_factory import AgentFactory
from domain.value_objects.domain_type import DomainType

async def main():
    # Создать агента
    agent = await AgentFactory().create_agent(
        agent_type="composable",
        domain=DomainType.CODE_ANALYSIS
    )

    # Выполнить задачу
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

    print(f"Результат: {result}")

if __name__ == "__main__":
    asyncio.run(main())
```

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

## Домены задач

Фреймворк поддерживает различные домены задач:

- **CODE_ANALYSIS**: Анализ кода на безопасность, качество, структуру
- **DATA_PROCESSING**: Обработка данных, выполнение SQL-запросов, анализ данных
- **CONTENT_GENERATION**: Генерация текста, отчетов, документации
- **SECURITY_ANALYSIS**: Анализ безопасности, оценка рисков, проверка соответствия
- **TESTING**: Генерация и выполнение тестов
- **INFRASTRUCTURE**: Управление системными ресурсами

## Безопасность и надежность

Фреймворк включает встроенные механизмы безопасности:

- **Валидация промтов**: Проверка на безопасность и корректность
- **Проверка параметров**: Контроль входных данных
- **Контроль доступа**: Ограничение доступа к ресурсам
- **Изоляция выполнения**: Предотвращение побочных эффектов
- **Обработка ошибок**: Надежная обработка исключений
- **Подтверждение доставки событий**: Гарантия обработки важных событий с механизмом повторных попыток

## Текущий статус реализации

### Реализовано

- ✅ **Механизм подтверждения доставки событий**: События подтверждаются обработчиками, с автоматическими повторными попытками
- ✅ **Чистая архитектура**: Полное разделение на доменный, прикладной и инфраструктурный слои
- ✅ **Система промтов**: Версионирование и управление промтами
- ✅ **Инфраструктурные компоненты**: Инструменты, навыки, адаптеры

### В разработке

- ⚠️ **Агент выполнения**: Реализация метода `execute_task()` (частично реализован)
- ⚠️ **Интеграция с навыками**: Реализация полной интеграции через `Capability`
- ⚠️ **Валидация генерируемого кода**: Проверка безопасности сгенерированного кода
- ⚠️ **Хранение снапшотов**: Файловое хранение истории выполнения

### Планы

- 📋 **Кэширование AST**: Повторный анализ файла происходит в 5x быстрее (кэш по хешу содержимого)
- 📋 **Стратегия сжатия контекста**: Агент работает с проектами >500 файлов без превышения лимита токенов
- 📋 **Полная поддержка TypeScript**: Парсинг дженериков, декораторов, пространств имён
- 📋 **Интеграция бенчмарков**: `BenchmarkRunner` вызывает `agent.execute_task()`, а не моки

Для подробной информации смотрите [ROADMAP](./ROADMAP.md).

## Расширение под свои задачи

Фреймворк легко адаптируется под специфические задачи:

1. **Создание специфических паттернов**: Для новых стратегий решения задач
2. **Разработка специфических инструментов**: Для новых возможностей взаимодействия
3. **Настройка системы промтов**: Под свои специфичные инструкции
4. **Адаптация агентов**: Для специфических доменов
5. **Расширение ядра системы**: Под свои требования

## Документация

Полная документация доступна в директории [docs/](./docs/):

- [Введение](./docs/introduction/)
- [Архитектура](./docs/architecture/)
- [Концепции](./docs/concepts/)
- [Система промтов](./docs/prompts/)
- [Инструменты и навыки](./docs/tools_skills/)
- [Ядро системы](./docs/core/)
- [Конфигурация](./docs/configuration/)
- [Тестирование](./docs/testing/)
- [Примеры](./docs/examples/)
- [Безопасность](./docs/security/)
- [Руководства](./docs/guides/)
- [Статус компонентов](./docs/components_status.md)
- [Лучшие практики](./docs/best_practices.md)
- [Оглавление](./docs/SUMMARY.md)
- [Анализ документации](./docs/documentation_analysis.md)

## Примеры использования

Смотрите примеры в директории [examples/](./examples/):

```python
# examples/composable_agent_example.py
from application.factories.agent_factory import AgentFactory
from domain.value_objects.domain_type import DomainType

async def example():
    agent = await AgentFactory().create_agent(
        agent_type="composable",
        domain=DomainType.CODE_ANALYSIS
    )

    result = await agent.execute_task(
        task_description="Проанализируй этот Python код на безопасность",
        context={
            "code": "def hello(): pass",
            "language": "python"
        }
    )

    return result
```

## Сообщество и поддержка

- GitHub: [https://github.com/AlexEgorov85/Agent_code](https://github.com/AlexEgorov85/Agent_code)
- Issues: [https://github.com/AlexEgorov85/Agent_code/issues](https://github.com/AlexEgorov85/Agent_code/issues)

Для вопросов и обсуждений создайте issue в репозитории.

## Лицензия

MIT License - смотрите файл [LICENSE](./LICENSE) для подробностей.

## 🌐 Философия: Раскрытие из ядра

**Koru** (маори) — символ раскрывающегося папоротника. Молодой побег начинается как плотное ядро и постепенно раскрывается в сложную структуру, сохраняя центральную ось.

```
        ┌──────────────┐
        │   Ядро       │  ← Контекст, архитектура, правила
        │  (Core)      │
        └──────┬───────┘
               │ Раскрытие под задачу
        ┌──────▼───────┐
        │  Слои        │  ← Навыки, инструменты, паттерны
        │  (Layers)    │     активируются по мере необходимости
        └──────────────┘
```

Спасибо за использование Koru AI Agent Framework!
