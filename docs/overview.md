# Koru AI Agent Framework - Общий обзор

Koru AI Agent Framework - это гибкая и расширяемая система для создания, управления и выполнения AI-агентов, способных решать сложные задачи через компонуемые паттерны мышления. Фреймворк реализует архитектуру, в которой LLM не управляет системой напрямую, а принимает решения, которые строго валидируются и исполняются кодом.

## Основные особенности

### 1. Компонуемость

Koru AI Agent Framework позволяет комбинировать различные паттерны мышления для решения сложных задач:

- **Паттерны мышления**: Стратегии решения задач, которые могут быть скомбинованы
- **Атомарные действия**: Минимальные неделимые операции
- **Компонуемые агенты**: Основные исполнители логики, которые комбинируют паттерны и действия

### 2. Чистая архитектура

Фреймворк реализует принципы чистой архитектуры:

- **Зависимости направлены внутрь**: Внешние слои зависят от внутренних, а не наоборот
- **Независимость от фреймворков**: Ядро системы не зависит от конкретных фреймворков
- **Тестируемость**: Бизнес-логика может быть протестирована без внешних зависимостей
- **Независимость от UI**: UI может быть изменен без влияния на бизнес-логику
- **Независимость от базы данных**: Бизнес-правила не зависят от конкретной СУБД

### 3. Безопасность и контролируемость

Фреймворк обеспечивает безопасность через:

- **Валидацию решений**: Все решения, принятые LLM, строго валидируются
- **Контролируемое выполнение**: Действия выполняются кодом, а не напрямую LLM
- **Изоляцию выполнения**: Ограничение доступа к системным ресурсам
- **Проверку безопасности промтов**: Валидация промтов на наличие потенциально опасного содержимого

### 4. Версионирование

Полнофункциональная система управления версиями:

- **Семантическое версионирование**: Поддержка MAJOR.MINOR.PATCH формата
- **Управление промтами**: Версионирование и управление промтами
- **Совместимость**: Контроль совместимости между версиями

## Архитектура системы

### Слои системы

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

#### Слой домена (Domain Layer)
- Содержит бизнес-логику и правила
- Определяет модели предметной области
- Не зависит от внешних слоев

#### Слой приложений (Application Layer)
- Координирует работу компонентов домена
- Реализует сценарии использования
- Не содержит бизнес-логики

#### Слой инфраструктуры (Infrastructure Layer)
- Реализует внешние зависимости (базы данных, внешние API, файловая система)
- Содержит адаптеры для внешних систем
- Не влияет на бизнес-логику

## Основные компоненты

### 1. Компонуемые агенты

Компонуемые агенты - основные исполнители логики в системе:

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

## Интеграция с внешними системами

### 1. API интеграции

Фреймворк легко интегрируется с внешними API:

```python
from infrastructure.tools.api_client_tool import APIClientTool

# Создать инструмент для взаимодействия с API
api_tool = APIClientTool(
    base_url="https://api.example.com",
    headers={"Authorization": "Bearer ${API_KEY}"}
)

# Использовать инструмент в агенте
result = await api_tool.execute({
    "endpoint": "/users",
    "method": "GET",
    "params": {"limit": 100}
})
```

### 2. Базы данных

Интеграция с различными СУБД:

```python
from infrastructure.tools.sql_tool import SQLTool

# Создать инструмент для выполнения SQL-запросов
sql_tool = SQLTool(connection_string="sqlite:///example.db")

# Выполнить запрос
result = await sql_tool.execute({
    "query": "SELECT * FROM users LIMIT 10"
})
```

### 3. Файловые системы

Безопасная работа с файлами:

```python
from infrastructure.tools.file_reader_tool import FileReaderTool

# Создать инструмент для чтения файлов
file_reader = FileReaderTool(max_file_size=5 * 1024 * 1024)  # 5MB

# Прочитать файл
result = await file_reader.execute({
    "path": "./data/input.txt",
    "encoding": "utf-8"
})
```

## Безопасность и надежность

Фреймворк включает встроенные механизмы безопасности:

- **Валидация промтов**: Проверка на безопасность и корректность
- **Проверка параметров**: Контроль входных данных
- **Контроль доступа**: Ограничение доступа к ресурсам
- **Изоляция выполнения**: Предотвращение побочных эффектов
- **Обработка ошибок**: Надежная обработка исключений

### Безопасность путей

Обязательно проверяйте безопасность путей к файлам:

```python
def _is_safe_path(self, path: str) -> bool:
    """Проверить, является ли путь безопасным для использования"""
    try:
        # Преобразовать в абсолютный путь
        abs_path = Path(path).resolve()
        
        # Получить корневой каталог проекта
        project_root = Path.cwd().resolve()
        
        # Проверить, что путь находится внутри корневого каталога
        abs_path.relative_to(project_root)
        return True
    except ValueError:
        # Если путь вне корневого каталога, он небезопасен
        return False
```

## Примеры использования

### 1. Простой пример

```python
# simple_example.py
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
        task_description="Проанализируй этот Python код на безопасность",
        context={
            "code": "def hello(): pass",
            "language": "python"
        }
    )
    
    print(f"Результат: {result}")

if __name__ == "__main__":
    asyncio.run(main())
```

### 2. Сложный пример с кастомными компонентами

```python
# advanced_example.py
async def advanced_usage_example():
    """Пример сложного использования с кастомными компонентами"""
    
    # Создать фабрику агентов
    agent_factory = AgentFactory()
    
    # Создать агента с кастомными компонентами
    agent = await agent_factory.create_agent_with_components(
        agent_type="composable",
        domain=DomainType.CODE_ANALYSIS,
        custom_patterns=[
            {"type": "security_analysis", "config": {"depth": "deep"}},
            {"type": "code_quality", "config": {"standards": ["pep8", "security"]}}
        ],
        custom_tools=[
            {"type": "file_analyzer", "config": {"max_file_size": "5MB"}},
            {"type": "security_scanner", "config": {"check_types": ["sql_injection", "xss"]}}
        ]
    )
    
    # Выполнить комплексную задачу
    result = await agent.execute_task(
        task_description="Выполни полный анализ безопасности и качества этого Python кода",
        context={
            "code": """
class UserAuth:
    def authenticate(self, username, password):
        # Уязвимость: SQL-инъекция
        query = f"SELECT * FROM users WHERE username='{username}' AND password='{password}'"
        return execute_query(query)
        
    def get_user_data(self, user_id):
        # Еще одна уязвимость
        query = f"SELECT * FROM user_data WHERE id={user_id}"
        return execute_query(query)
""",
            "requirements": {
                "security_standards": ["owasp_top_10"],
                "quality_standards": ["pep8", "mypy"],
                "report_format": "detailed"
            }
        }
    )
    
    print(f"Комплексный результат анализа: {result}")
    
    return result
```

## Разработка под свои задачи

Фреймворк легко адаптируется под специфические задачи:

- Создавайте [свои паттерны мышления](./concepts/thinking_patterns.md)
- Разрабатывайте [специфические инструменты и навыки](./tools_skills/)
- Настраивайте [систему промтов](./prompts/) под свои нужды
- Адаптируйте [агентов](./core/composable_agent.md) для специфических доменов
- Расширяйте [ядро системы](./core/overview.md) под свои требования

### Пример создания специфического агента

```python
class CustomAgent(BaseAgent):
    """Специфический агент для своих задач"""
    
    def __init__(self, domain_type: DomainType, custom_config: Dict[str, Any] = None):
        super().__init__()
        self.domain_type = domain_type
        self.custom_config = custom_config or {}
        self._specialized_patterns = []
        self._custom_tools = []
        
        # Инициализировать специфические компоненты
        self._initialize_specialized_components()
    
    def _initialize_specialized_components(self):
        """Инициализировать специфические компоненты агента"""
        # Загрузить специфические паттерны
        self._load_specialized_patterns()
        
        # Загрузить специфические инструменты
        self._load_custom_tools()
    
    async def execute_task(self, task_description: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Выполнить задачу с использованием специфических компонентов"""
        # Определить подходящий специфический паттерн
        specialized_pattern = self._select_specialized_pattern(task_description, context)
        
        if specialized_pattern:
            # Выполнить задачу через специфический паттерн
            return await specialized_pattern.execute(self.state, context, self.capabilities)
        else:
            # Использовать базовую реализацию
            return await super().execute_task(task_description, context)
```

## Тестирование

Фреймворк поддерживает различные уровни тестирования:

- **Модульное тестирование**: Тестирование отдельных компонентов
- **Интеграционное тестирование**: Тестирование взаимодействия между компонентами
- **Системное тестирование**: Тестирование системы в целом

## Заключение

Koru AI Agent Framework предоставляет гибкую и расширяемую архитектуру для создания AI-агентов, решающих сложные задачи. Следуя принципам чистой архитектуры и лучшим практикам безопасности, вы можете адаптировать фреймворк под свои специфические задачи, создавая мощные и надежные решения.

Фреймворк обеспечивает:
- **Контролируемость**: Все действия и решения строго валидируются
- **Безопасность**: Защита от потенциально опасных операций
- **Расширяемость**: Легкое добавление новых компонентов
- **Модульность**: Четкое разделение на независимые компоненты
- **Тестируемость**: Возможность тестирования отдельных компонентов
- **Версионирование**: Управление версиями промтов и компонентов
- **Производительность**: Оптимизация через кэширование и асинхронность

Для получения более подробной информации о конкретных аспектах фреймворка см. соответствующие разделы документации.