# Руководство по быстрому старту

Добро пожаловать в Composable AI Agent Framework! Это краткое руководство поможет вам быстро начать работу с фреймворком и выполнить первую задачу.

## Установка

Для начала работы с фреймворком выполните установку:

```bash
# Клонируйте репозиторий
git clone https://github.com/AlexEgorov85/Agent_code.git
cd Agent_code

# Создайте виртуальное окружение
python -m venv venv
source venv/bin/activate  # или venv\Scripts\activate на Windows

# Установите зависимости
pip install -r requirements.txt
```

## Первая задача

Создайте простой скрипт для выполнения первой задачи:

```python
# first_task.py
import asyncio
from application.factories.agent_factory import AgentFactory
from domain.value_objects.domain_type import DomainType

async def main():
    # Создайте фабрику агентов
    agent_factory = AgentFactory()
    
    # Создайте агента для анализа кода
    agent = await agent_factory.create_agent(
        agent_type="composable",
        domain=DomainType.CODE_ANALYSIS
    )
    
    # Выполните простую задачу
    result = await agent.execute_task(
        task_description="Проанализируй этот Python код на наличие очевидных проблем безопасности",
        context={
            "code": """
def login(username, password):
    query = f"SELECT * FROM users WHERE username='{username}' AND password='{password}'"
    return execute_query(query)
""",
            "language": "python"
        }
    )
    
    print(f"Результат выполнения задачи: {result}")

if __name__ == "__main__":
    asyncio.run(main())
```

Запустите скрипт:

```bash
python first_task.py
```

## Основные понятия

### Агенты
Агенты - это основные исполнители задач. Они могут адаптироваться к различным доменам задач:

```python
from domain.value_objects.domain_type import DomainType

# Агенты для разных доменов
code_agent = await agent_factory.create_agent(
    agent_type="composable",
    domain=DomainType.CODE_ANALYSIS
)

data_agent = await agent_factory.create_agent(
    agent_type="composable", 
    domain=DomainType.DATA_PROCESSING
)

content_agent = await agent_factory.create_agent(
    agent_type="composable",
    domain=DomainType.CONTENT_GENERATION
)
```

### Паттерны мышления
Паттерны мышления определяют стратегии решения задач:

```python
# Агент может использовать различные паттерны мышления
result = await agent.execute_composable_pattern(
    pattern_name="security_analysis",
    context={
        "code": "your_code_here",
        "analysis_type": "vulnerability_scan"
    }
)
```

### Промты
Система промтов обеспечивает гибкое управление инструкциями:

```python
# Структура хранения промтов:
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

## Настройка под свои задачи

### 1. Создание специфического агента

Для адаптации под свои задачи вы можете создать специфический агент:

```python
class CustomAgent:
    """Специфический агент для своих задач"""
    
    def __init__(self, domain_type: DomainType, custom_config: dict = None):
        self.domain_type = domain_type
        self.config = custom_config or {}
        self.state = AgentState()
        
        # Настройка специфических компонентов
        self._setup_custom_components()
    
    def _setup_custom_components(self):
        """Настроить специфические компоненты"""
        # Загрузить специфические паттерны
        # Настроить специфические инструменты
        # И т.д.
        pass
    
    async def execute_task(self, task_description: str, context: dict = None):
        """Выполнить задачу с использованием специфических компонентов"""
        # Специфическая логика выполнения задачи
        pass
```

### 2. Использование специфических паттернов

Создавайте свои паттерны мышления для специфических задач:

```python
class CustomThinkingPattern:
    """Специфический паттерн мышления"""
    
    @property
    def name(self) -> str:
        return "custom_analysis_pattern"
    
    async def execute(self, state, context, available_capabilities):
        """Выполнить специфическую логику анализа"""
        # Ваша специфическая логика
        pass
```

## Следующие шаги

После успешного запуска первого примера рекомендуется:

1. Изучить [архитектуру фреймворка](./architecture/overview.md)
2. Ознакомиться с [концепциями](./concepts/thinking_patterns.md)
3. Посмотреть [больше примеров](./examples/overview.md)
4. Узнать о [системе промтов](./prompts/overview.md)
5. Изучить [безопасность](./security/guide.md)

## Помощь и поддержка

- GitHub репозиторий: [https://github.com/AlexEgorov85/Agent_code](https://github.com/AlexEgorov85/Agent_code)
- Полная документация: [https://github.com/AlexEgorov85/Agent_code/tree/main/docs](https://github.com/AlexEgorov85/Agent_code/tree/main/docs)

Если у вас возникли проблемы, создайте issue в репозитории GitHub.