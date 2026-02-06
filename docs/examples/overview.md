# Обзор примеров и сценариев использования

В этом разделе представлены примеры использования Composable AI Agent Framework и различные сценарии, демонстрирующие возможности фреймворка. Примеры охватывают различные домены и показывают, как можно использовать компоненты фреймворка для решения реальных задач.

## Типы примеров

### 1. Базовые примеры
- Простые примеры использования отдельных компонентов
- Демонстрация основных возможностей фреймворка
- Образцы кода для начинающих пользователей

### 2. Комплексные сценарии
- Примеры использования нескольких компонентов вместе
- Решение реальных задач с использованием паттернов мышления
- Интеграция инструментов и атомарных действий

### 3. Доменно-специфические примеры
- Примеры для конкретных доменов (анализ кода, обработка данных и т.д.)
- Адаптация агентов к специфическим требованиям
- Использование доменно-специфических промтов и паттернов

## Структура примеров

Примеры организованы следующим образом:

```
examples/
├── basic/                    # Базовые примеры
│   ├── simple_agent_example.py
│   └── prompt_usage_example.py
├── advanced/                 # Продвинутые примеры
│   ├── complex_thinking_pattern_example.py
│   └── multi_domain_example.py
├── agent_step_display_example.py
├── atomic_action_executor_example.py
├── composable_agent_example.py
├── event_bus_example.py
├── sql_generator_example.py
└── ...

docs/examples/
├── overview.md              # Этот файл
├── usage_scenarios.md       # Сценарии использования
└── customization.md         # Настройка под свои задачи
```

## Базовые примеры

### 1. Простой пример агента

```python
# examples/basic/simple_agent_example.py
from application.factories.agent_factory import AgentFactory
from domain.value_objects.domain_type import DomainType
from domain.models.agent.agent_state import AgentState

async def simple_agent_example():
    """Простой пример создания и использования агента"""
    
    # Создание фабрики агентов
    agent_factory = AgentFactory()
    
    # Создание агента
    agent = await agent_factory.create_agent(
        agent_type="simple_composable",
        domain=DomainType.CODE_ANALYSIS
    )
    
    # Определение задачи
    task_description = "Проанализируй этот Python код наличие уязвимостей"
    
    # Адаптация агента к задаче
    await agent.adapt_to_task(task_description)
    
    # Выполнение задачи
    result = await agent.execute_task(task_description)
    
    print(f"Результат выполнения задачи: {result}")
    
    return result

if __name__ == "__main__":
    import asyncio
    asyncio.run(simple_agent_example())
```

### 2. Пример использования промтов

```python
# examples/basic/prompt_usage_example.py
from application.services.prompt_loader import PromptLoader
from domain.value_objects.domain_type import DomainType
from domain.value_objects.provider_type import LLMProviderType
from domain.models.prompt.prompt_version import PromptRole

async def prompt_usage_example():
    """Пример использования системы промтов"""
    
    # Создание загрузчика промтов
    prompt_loader = PromptLoader(base_path="./prompts")
    
    # Загрузка всех промтов
    prompts, errors = prompt_loader.load_all_prompts()
    
    print(f"Загружено промтов: {len(prompts)}")
    print(f"Ошибок: {len(errors)}")
    
    # Фильтрация промтов для конкретного домена
    code_analysis_prompts = [
        prompt for prompt in prompts 
        if prompt.domain == DomainType.CODE_ANALYSIS
    ]
    
    print(f"Промтов для анализа кода: {len(code_analysis_prompts)}")
    
    # Пример использования конкретного промта
    if code_analysis_prompts:
        sample_prompt = code_analysis_prompts[0]
        print(f"Пример промта: {sample_prompt.id}")
        print(f"Домен: {sample_prompt.domain}")
        print(f"Роль: {sample_prompt.role}")
        print(f"Версия: {sample_prompt.semantic_version}")
        
        # Проверка переменных
        if sample_prompt.variables_schema:
            print("Переменные промта:")
            for var in sample_prompt.variables_schema:
                print(f"  - {var.name}: {var.type} ({'required' if var.required else 'optional'})")
    
    return prompts

if __name__ == "__main__":
    import asyncio
    asyncio.run(prompt_usage_example())
```

## Комплексные сценарии

### 1. Сценарий анализа кода

```python
# examples/advanced/code_analysis_scenario.py
from application.factories.agent_factory import AgentFactory
from domain.value_objects.domain_type import DomainType
from infrastructure.tools.file_reader_tool import FileReaderTool
from infrastructure.tools.ast_parser_tool import ASTParserTool
from application.services.prompt_loader import PromptLoader

async def code_analysis_scenario():
    """Сценарий анализа кода с использованием нескольких компонентов"""
    
    # Создание агента для анализа кода
    agent_factory = AgentFactory()
    agent = await agent_factory.create_agent(
        agent_type="composable",
        domain=DomainType.CODE_ANALYSIS
    )
    
    # Загрузка инструментов
    file_reader = FileReaderTool()
    ast_parser = ASTParserTool()
    
    # Загрузка промтов для анализа кода
    prompt_loader = PromptLoader(base_path="./prompts")
    prompts, _ = prompt_loader.load_all_prompts()
    
    code_analysis_prompts = [
        prompt for prompt in prompts 
        if prompt.domain == DomainType.CODE_ANALYSIS
        and prompt.capability_name == "security_analysis"
    ]
    
    # Чтение файла с кодом
    code_file_path = "./examples/sample_code.py"
    read_result = await file_reader.execute({"path": code_file_path})
    
    if not read_result["success"]:
        print(f"Ошибка чтения файла: {read_result['error']}")
        return
    
    code_content = read_result["content"]
    
    # Парсинг AST
    ast_result = await ast_parser.execute({
        "code": code_content,
        "language": "python"
    })
    
    # Адаптация агента к задаче анализа
    task_description = f"Проанализируй этот Python код наличие уязвимостей: {code_content}"
    await agent.adapt_to_task(task_description)
    
    # Выполнение анализа с использованием паттерна
    analysis_result = await agent.execute_composable_pattern(
        pattern_name="security_analysis",
        context={
            "code": code_content,
            "ast": ast_result,
            "prompts": code_analysis_prompts
        }
    )
    
    print(f"Результат анализа: {analysis_result}")
    
    return analysis_result

if __name__ == "__main__":
    import asyncio
    asyncio.run(code_analysis_scenario())
```

### 2. Сценарий обработки данных

```python
# examples/advanced/data_processing_scenario.py
from application.factories.agent_factory import AgentFactory
from domain.value_objects.domain_type import DomainType
from infrastructure.tools.sql_tool import SQLTool
from application.services.prompt_loader import PromptLoader

async def data_processing_scenario():
    """Сценарий обработки данных с использованием SQL-инструментов"""
    
    # Создание агента для обработки данных
    agent_factory = AgentFactory()
    agent = await agent_factory.create_agent(
        agent_type="composable",
        domain=DomainType.DATA_PROCESSING
    )
    
    # Подключение к базе данных (в реальном примере используйте реальные credentials)
    sql_tool = SQLTool(connection_string="sqlite:///example.db")
    
    # Определение задачи
    task_description = "Проанализируй данные в таблице users и найди аномалии"
    
    # Адаптация агента к задаче
    await agent.adapt_to_task(task_description)
    
    # Выполнение SQL-запроса для получения данных
    query_result = await sql_tool.execute({
        "query": "SELECT * FROM users LIMIT 100"
    })
    
    if not query_result["success"]:
        print(f"Ошибка выполнения запроса: {query_result['error']}")
        return
    
    # Выполнение анализа данных с использованием паттерна
    analysis_result = await agent.execute_composable_pattern(
        pattern_name="data_analysis",
        context={
            "data": query_result["results"],
            "query": "SELECT * FROM users LIMIT 100"
        }
    )
    
    print(f"Результат анализа данных: {analysis_result}")
    
    return analysis_result

if __name__ == "__main__":
    import asyncio
    asyncio.run(data_processing_scenario())
```

## Доменно-специфические примеры

### 1. Пример для домена анализа кода

```python
# examples/domains/code_analysis_example.py
from application.factories.agent_factory import AgentFactory
from domain.value_objects.domain_type import DomainType
from infrastructure.tools.file_reader_tool import FileReaderTool
from infrastructure.tools.ast_parser_tool import ASTParserTool
from application.orchestration.atomic_actions import AtomicActionExecutor

async def code_analysis_domain_example():
    """Пример использования фреймворка для домена анализа кода"""
    
    # Создание агента для анализа кода
    agent = await AgentFactory().create_agent(
        agent_type="composable",
        domain=DomainType.CODE_ANALYSIS
    )
    
    # Загрузка инструментов
    file_reader = FileReaderTool()
    ast_parser = ASTParserTool()
    
    # Исполнитель атомарных действий
    action_executor = AtomicActionExecutor()
    
    # Регистрация действий
    action_executor.register_action(file_reader)
    action_executor.register_action(ast_parser)
    
    # Анализ файла
    target_file = "./src/main.py"
    
    # Шаг 1: Чтение файла
    read_result = await action_executor.execute_action(
        "file_reader",
        {"path": target_file}
    )
    
    if not read_result["success"]:
        print(f"Не удалось прочитать файл: {read_result['error']}")
        return
    
    # Шаг 2: Парсинг AST
    ast_result = await action_executor.execute_action(
        "ast_parser",
        {
            "code": read_result["content"],
            "language": "python"
        }
    )
    
    # Шаг 3: Анализ с использованием паттерна мышления
    analysis_result = await agent.execute_composable_pattern(
        pattern_name="code_vulnerability_analysis",
        context={
            "code": read_result["content"],
            "ast": ast_result,
            "target_file": target_file
        }
    )
    
    # Вывод результатов
    print("Результаты анализа:")
    for finding in analysis_result.get("findings", []):
        print(f"- {finding['type']}: {finding['description']}")
    
    return analysis_result

if __name__ == "__main__":
    import asyncio
    asyncio.run(code_analysis_domain_example())
```

## Примеры интеграции с различными компонентами

### 1. Интеграция с системой событий

```python
# examples/integration/event_system_example.py
from infrastructure.gateways.event_bus_adapter import EventBusAdapter
from application.factories.agent_factory import AgentFactory
from domain.value_objects.domain_type import DomainType

async def event_system_example():
    """Пример интеграции с системой событий"""
    
    # Создание шины событий
    event_bus = EventBusAdapter()
    
    # Подписка на события агента
    async def handle_agent_state_change(event_data):
        print(f"Состояние агента изменилось: {event_data}")
    
    event_bus.subscribe("agent_state_changed", handle_agent_state_change)
    
    # Создание агента
    agent = await AgentFactory().create_agent(
        agent_type="composable",
        domain=DomainType.CODE_ANALYSIS
    )
    
    # Установка публикатора событий для агента
    agent.set_event_publisher(event_bus)
    
    # Выполнение задачи
    task_result = await agent.execute_task(
        "Проанализируй этот код на наличие проблем с безопасностью"
    )
    
    print(f"Результат задачи: {task_result}")
    
    return task_result

if __name__ == "__main__":
    import asyncio
    asyncio.run(event_system_example())
```

### 2. Интеграция с системой конфигурации

```python
# examples/integration/configuration_example.py
from config.config_loader import ConfigLoader
from application.factories.agent_factory import AgentFactory

async def configuration_example():
    """Пример использования системы конфигурации"""
    
    # Загрузка конфигурации
    config_loader = ConfigLoader("config.yaml")
    config = await config_loader.load_config()
    
    # Создание агента с использованием конфигурации
    agent_factory = AgentFactory()
    agent = await agent_factory.create_agent_with_config(config.agent)
    
    # Выполнение задачи с использованием настроек из конфигурации
    task_result = await agent.execute_task(
        "Выполни анализ кода в соответствии с настройками безопасности"
    )
    
    print(f"Результат задачи: {task_result}")
    print(f"Использованная модель LLM: {config.llm.model}")
    print(f"Уровень логирования: {config.log_level}")
    
    return task_result

if __name__ == "__main__":
    import asyncio
    asyncio.run(configuration_example())
```

## Создание собственных сценариев

Для создания собственных сценариев использования рекомендуется:

1. **Определить домен задачи**: Определите, к какому домену относится ваша задача
2. **Выбрать подходящие компоненты**: Определите, какие компоненты фреймворка потребуются
3. **Создать агента**: Используйте фабрику агентов для создания подходящего агента
4. **Настроить инструменты**: Подключите необходимые инструменты и атомарные действия
5. **Определить паттерны мышления**: Выберите подходящие паттерны для решения задачи
6. **Реализовать логику**: Напишите код, который координирует работу компонентов

## Практические рекомендации

### 1. Начинайте с простого
- Начинайте с базовых примеров и постепенно усложняйте сценарии
- Используйте готовые паттерны мышления до создания своих
- Тестируйте каждый компонент по отдельности перед интеграцией

### 2. Используйте доменно-специфические компоненты
- Адаптируйте агентов к конкретным доменам задач
- Используйте доменно-специфические промты и паттерны
- Логируйте выполнение для отладки и анализа

### 3. Обрабатывайте ошибки
- Реализуйте надлежащую обработку ошибок
- Используйте механизмы восстановления после сбоев
- Логируйте ошибки для последующего анализа

### 4. Оптимизируйте производительность
- Используйте кэширование для часто используемых данных
- Ограничивайте количество параллельных операций
- Используйте асинхронные операции там, где это возможно

## Преимущества использования примеров

- **Обучение**: Примеры помогают понять, как использовать различные компоненты
- **Идеи**: Примеры дают представление о возможных применениях фреймворка
- **База для разработки**: Примеры служат основой для создания собственных решений
- **Тестирование**: Примеры могут использоваться для проверки корректности установки
- **Документация**: Примеры служат практической документацией к API

## Интеграция с другими системами

Примеры показывают, как интегрировать фреймворк с различными внешними системами:

- **Базы данных**: Использование SQL-инструментов для работы с данными
- **Файловые системы**: Использование инструментов для работы с файлами
- **Внешние API**: Интеграция с различными внешними сервисами
- **Системы мониторинга**: Интеграция с системами логирования и мониторинга
- **Системы управления задачами**: Интеграция с очередями задач и планировщиками