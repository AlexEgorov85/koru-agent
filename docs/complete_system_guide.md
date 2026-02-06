# Полное руководство по Composable AI Agent Framework

Composable AI Agent Framework - это гибкая и расширяемая система для создания, управления и выполнения AI-агентов, способных решать сложные задачи через компонуемые паттерны мышления. В этом полном руководстве описаны все аспекты фреймворка и рекомендации по его использованию под специфические задачи.

## 1. Введение

### 1.1 Обзор системы

Composable AI Agent Framework реализует архитектуру, в которой LLM не управляет системой напрямую, а принимает решения, которые строго валидируются и исполняются кодом. Это обеспечивает контролируемость, надежность и безопасность AI-агентов.

### 1.2 Основные особенности

- **Компонуемость**: Возможность комбинировать различные паттерны мышления для решения сложных задач
- **Чистая архитектура**: Архитектура, следующая принципам чистой архитектуры (Clean Architecture)
- **Безопасность**: Строгая валидация решений, принятых LLM, и контролируемое выполнение действий
- **Расширяемость**: Легкое создание новых компонентов и адаптация под специфические задачи
- **Версионирование**: Полнофункциональная система управления версиями промтов
- **Доменная адаптация**: Агенты могут адаптироваться к различным областям задач
- **Тестируемость**: Бизнес-логика может быть протестирована без внешних зависимостей

### 1.3 Установка и настройка

```bash
# Клонировать репозиторий
git clone https://github.com/AlexEgorov85/Agent_code.git
cd Agent_code

# Создать виртуальное окружение
python -m venv venv
source venv/bin/activate  # или venv\Scripts\activate на Windows

# Установить зависимости
pip install -r requirements.txt
```

## 2. Архитектура системы

### 2.1 Чистая архитектура (Clean Architecture)

Фреймворк реализует принципы чистой архитектуры:

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
│     Domain      │ ← Ядро системы, не зависит ни от чего
│                 │
└─────────────────┘
```

#### Слои системы:

- **Слой домена (Domain Layer)**: Содержит бизнес-логику и правила
- **Слой приложений (Application Layer)**: Координирует работу компонентов домена
- **Слой инфраструктуры (Infrastructure Layer)**: Реализует внешние зависимости

### 2.2 Компоненты системы

#### Агенты

Компонуемые агенты - основные исполнители логики:

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

#### Паттерны мышления

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

#### Атомарные действия

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

#### Система промтов

Система промтов обеспечивает гибкое управление и версионирование:

```
prompts/
├── {domain}/                    # Домен (например, code_analysis)
│   └── {capability}/            # Капабилити (например, security_analysis)
│       ├── {role}/              # Роль (system, user, assistant, tool)
│       │   ├── v{version}.md    # Файл версии промта
│       │   └── ...
│       └── _index.yaml          # Индекс капабилити (опционально)
```

## 3. Концепции

### 3.1 Паттерны мышления

Паттерны мышления - это стратегии решения задач, которые могут быть скомпонованы:

- **Адаптивные**: Паттерны могут адаптироваться к специфическим задачам
- **Расширяемые**: Возможность создания новых паттернов для специфических нужд
- **Валидируемые**: Строгая проверка безопасности и корректности

### 3.2 Компонуемые агенты

Компонуемые агенты позволяют комбинировать различные паттерны мышления:

- **Явное состояние**: Агенты имеют четко определенное состояние с отслеживанием прогресса и ошибок
- **Адаптация к доменам**: Агенты могут адаптироваться к различным областям задач
- **Компонуемость**: Возможность комбинировать паттерны мышления для сложных задач
- **Контролируемость**: Все действия и решения строго валидируются и контролируются

### 3.3 Атомарные действия

Атомарные действия - минимальные неделимые операции:

- **Файловые операции**: Чтение, запись, анализ файлов
- **Сетевые операции**: HTTP-запросы, взаимодействие с API
- **Базы данных**: Выполнение SQL-запросов, работа с данными
- **Системные операции**: Выполнение команд, управление процессами

### 3.4 Управление доменами

Система управления доменами позволяет адаптировать агентов к различным областям задач:

- **Код-анализ**: Анализ безопасности, качества, структуры кода
- **Обработка данных**: Работа с базами данных, файлами, API
- **Генерация контента**: Создание текста, отчетов, документации
- **Тестирование**: Генерация и выполнение тестов
- **Инфраструктура**: Управление системными ресурсами

## 4. Система промтов

### 4.1 Структура хранения

Промты организованы в иерархическую структуру:

- **Домены**: Группировка по областям задач
- **Капабилити**: Группировка по возможностям
- **Роли**: Типы промтов (system, user, assistant, tool)
- **Версии**: Управление версиями промтов

### 4.2 Формат файла промта

Каждый файл промта использует формат Markdown с YAML frontmatter:

```yaml
---
provider: openai
role: system
status: active
variables:
  - name: task_description
    type: string
    required: true
    description: "Описание задачи для анализа"
expected_response:
  type: object
  properties:
    findings:
      type: array
      items:
        type: object
        properties:
          type:
            type: string
          severity:
            type: string
          description:
            type: string
---

# Инструкции для агента анализа безопасности

Ты являешься экспертом в области безопасности кода...
```

### 4.3 Версионирование

Система использует семантическое версионирование (SemVer):

- `MAJOR.MINOR.PATCH` (например, `1.2.3`)
- `MAJOR` - значительные изменения, нарушающие обратную совместимость
- `MINOR` - добавление новой функциональности с сохранением совместимости
- `PATCH` - исправление ошибок без изменения функциональности

## 5. Инструменты и навыки

### 5.1 Инструменты

Инструменты обеспечивают доступ к внешним системам:

```python
from domain.abstractions.tool import ITool

class FileReaderTool(ITool):
    """Инструмент для чтения файлов"""
    
    @property
    def name(self) -> str:
        return "file_reader"
    
    async def execute(self, parameters):
        # Логика чтения файла
        pass
```

### 5.2 Навыки

Навыки объединяют несколько инструментов для решения сложных задач:

```python
from domain.abstractions.skill import ISkill

class CodeAnalysisSkill(ISkill):
    """Навык анализа кода"""
    
    async def execute(self, context):
        # Логика выполнения анализа кода
        # может использовать несколько инструментов
        pass
```

## 6. Ядро системы

### 6.1 Состояние агента

Явное состояние агента с отслеживанием прогресса:

```python
from domain.models.agent.agent_state import AgentState

class AgentState(BaseModel):
    step: int = 0
    error_count: int = 0
    no_progress_steps: int = 0
    finished: bool = False
    metrics: Dict[str, Any] = {}
    history: List[str] = []
    current_plan_step: Optional[str] = None

    def register_error(self):
        self.error_count += 1

    def register_progress(self, progressed: bool):
        if progressed:
            self.no_progress_steps = 0
        else:
            self.no_progress_steps += 1

    def complete(self):
        """Отмечает агента как завершившего выполнение."""
        self.finished = True
```

### 6.2 Управление доменами

Агенты могут адаптироваться к различным доменам задач:

```python
from domain.value_objects.domain_type import DomainType

# Домены задач
DOMAIN_TYPES = [
    DomainType.CODE_ANALYSIS,      # Анализ кода
    DomainType.DATA_PROCESSING,    # Обработка данных
    DomainType.CONTENT_GENERATION, # Генерация контента
    DomainType.SECURITY_ANALYSIS,  # Анализ безопасности
    DomainType.TESTING,            # Тестирование
    DomainType.INFRASTRUCTURE      # Инфраструктура
]
```

## 7. Конфигурация

### 7.1 Система конфигурации

Фреймворк включает гибкую систему конфигурации:

```yaml
# config.yaml
agent:
  max_iterations: 50
  timeout: 300
  enable_logging: true
  max_concurrent_actions: 5

llm:
  provider: openai
  model: gpt-4
  api_key: "${OPENAI_API_KEY}"
  temperature: 0.7
  max_tokens: 2048

prompts:
  storage_path: "./prompts"
  cache_enabled: true
  cache_ttl: 3600
  validation_enabled: true

debug_mode: false
log_level: "INFO"
enable_monitoring: true
```

### 7.2 Загрузка конфигурации

Конфигурация может загружаться из различных источников:

- YAML/JSON файлов
- Переменных окружения
- Базы данных
- Внешних API

## 8. Тестирование

### 8.1 Модульное тестирование

Тестируйте каждый компонент отдельно:

```python
# test_agent.py
import pytest
from unittest.mock import AsyncMock

class TestAgent:
    @pytest.mark.asyncio
    async def test_agent_task_execution(self):
        """Тест выполнения задачи агентом"""
        # Создать агента
        agent = await AgentFactory().create_agent(
            agent_type="composable",
            domain=DomainType.CODE_ANALYSIS
        )
        
        # Выполнить задачу
        result = await agent.execute_task(
            task_description="Тестовая задача",
            context={"test": "data"}
        )
        
        # Проверить результат
        assert result["success"] is True
```

### 8.2 Интеграционное тестирование

Тестируйте взаимодействие между компонентами:

```python
# test_integration.py
class TestAgentPromptIntegration:
    @pytest.mark.asyncio
    async def test_agent_prompt_integration(self):
        """Тест интеграции агента с системой промтов"""
        # Создать агента
        agent = await AgentFactory().create_agent(
            agent_type="composable",
            domain=DomainType.CODE_ANALYSIS
        )
        
        # Загрузить промты
        from application.services.prompt_loader import PromptLoader
        prompt_loader = PromptLoader(base_path="./prompts")
        prompts, errors = prompt_loader.load_all_prompts()
        
        # Выполнить задачу
        result = await agent.execute_task(
            task_description="Тест интеграции",
            context={"test": "data"}
        )
        
        # Проверить результат
        assert "success" in result
```

## 9. Примеры использования

### 9.1 Простой пример

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

### 9.2 Сложный пример

```python
# advanced_example.py
async def advanced_usage_example():
    """Пример сложного использования с кастомными компонентами"""
    
    # Создать специфические компоненты
    from application.factories.specialized_factory import SpecializedFactory
    factory = SpecializedFactory()
    
    # Создать специфический агент
    agent = await factory.create_agent_with_config(
        agent_type="composable",
        domain=DomainType.CODE_ANALYSIS,
        config={
            "specialized_patterns": [
                {
                    "type": "security_analysis",
                    "parameters": {"depth": "deep"}
                }
            ],
            "custom_tools": [
                {
                    "type": "file_analyzer",
                    "parameters": {
                        "max_file_size": 5 * 1024 * 1024,
                        "supported_formats": [".py", ".js", ".ts"]
                    }
                }
            ]
        }
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

## 10. Безопасность

### 10.1 Проверка безопасности промтов

Система проверяет промты на наличие потенциально опасного содержимого:

```python
def validate_prompt_content(self, content: str) -> List[str]:
    """Проверить содержимое промта на безопасность"""
    errors = []
    
    # Проверить на наличие инструкций обхода безопасности
    security_bypass_patterns = [
        r"ignore\s+previous\s+instructions",
        r"disregard\s+safety\s+guidelines",
        r"bypass\s+security\s+measures"
    ]
    
    for pattern in security_bypass_patterns:
        import re
        if re.search(pattern, content, re.IGNORECASE):
            errors.append(f"Обнаружена потенциальная инструкция обхода безопасности: {pattern}")
    
    return errors
```

### 10.2 Безопасность путей

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

## 11. Разработка под свои задачи

### 11.1 Создание специфических агентов

Для адаптации под свои задачи создавайте специфические агенты:

```python
class CustomAgent(BaseAgent):
    """Специфический агент для конкретных задач"""
    
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

### 11.2 Создание специфических паттернов

Для создания паттернов под специфические задачи:

```python
class SpecializedThinkingPattern(IThinkingPattern):
    """Специфический паттерн мышления для конкретных задач"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.name = self.config.get("name", "specialized_pattern")
        self._required_tools = self.config.get("required_tools", [])
        self._execution_strategy = self.config.get("execution_strategy", "sequential")
    
    async def execute(
        self,
        state: AgentState,
        context: Any,
        available_capabilities: List[str]
    ) -> Dict[str, Any]:
        """Выполнить специфический паттерн мышления"""
        try:
            # Проверить доступность необходимых инструментов
            missing_tools = [
                tool for tool in self._required_tools
                if tool not in available_capabilities
            ]
            
            if missing_tools:
                return {
                    "success": False,
                    "error": f"Отсутствуют необходимые инструменты: {missing_tools}",
                    "missing_tools": missing_tools,
                    "pattern_used": self.name
                }
            
            # Выполнить специфическую логику
            result = await self._execute_specialized_logic(state, context)
            
            return {
                "success": True,
                "result": result,
                "pattern_used": self.name
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Ошибка при выполнении паттерна {self.name}: {str(e)}",
                "pattern_used": self.name
            }
```

### 11.3 Создание специфических инструментов

Для создания инструментов под специфические задачи:

```python
class CustomFileAnalyzerTool(ITool):
    """Специфический инструмент для анализа файлов"""
    
    def __init__(self, max_file_size: int = 10 * 1024 * 1024, supported_formats: List[str] = None):
        super().__init__()
        self.max_file_size = max_file_size
        self.supported_formats = supported_formats or [
            '.py', '.js', '.ts', '.java', '.cs', '.cpp', '.c', 
            '.html', '.css', '.json', '.yaml', '.xml'
        ]
        self._required_permissions = ["read_file", "analyze_content"]
    
    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="custom_file_analyzer",
            description="Анализирует файлы на наличие специфических проблем",
            parameters_schema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Путь к файлу для анализа"
                    },
                    "analysis_types": {
                        "type": "array",
                        "items": {"type": "string"},
                        "enum": ["security", "quality", "complexity", "dependencies"],
                        "default": ["security", "quality"],
                        "description": "Типы анализа для выполнения"
                    }
                },
                "required": ["file_path"]
            },
            return_schema={
                "type": "object",
                "properties": {
                    "success": {"type": "boolean"},
                    "analysis_results": {
                        "type": "object",
                        "properties": {
                            "security_findings": {"type": "array"},
                            "quality_issues": {"type": "array"},
                            "complexity_metrics": {"type": "object"},
                            "dependency_issues": {"type": "array"}
                        }
                    },
                    "file_info": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string"},
                            "size": {"type": "integer"},
                            "extension": {"type": "string"}
                        }
                    },
                    "error": {"type": "string"}
                }
            },
            category="analysis",
            permissions=["read_file", "analyze_content"]
        )
    
    async def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Выполнить анализ файла"""
        if not self.validate_parameters(parameters):
            return {
                "success": False,
                "error": "Некорректные параметры"
            }
        
        file_path = parameters["file_path"]
        analysis_types = parameters.get("analysis_types", ["security", "quality"])
        
        try:
            # Проверить безопасность пути
            if not self._is_safe_path(file_path):
                return {
                    "success": False,
                    "error": "Небезопасный путь к файлу"
                }
            
            path = Path(file_path)
            
            # Проверить существование файла и его размер
            if not path.exists():
                return {
                    "success": False,
                    "error": f"Файл не найден: {file_path}"
                }
            
            file_size = path.stat().st_size
            if file_size > self.max_file_size:
                return {
                    "success": False,
                    "error": f"Файл слишком большой: {file_size} байт, максимум {self.max_file_size}"
                }
            
            # Проверить расширение файла
            if path.suffix.lower() not in self.supported_formats:
                return {
                    "success": False,
                    "error": f"Формат файла {path.suffix} не поддерживается"
                }
            
            # Прочитать файл
            with open(path, 'r', encoding='utf-8') as file:
                content = file.read()
            
            # Выполнить анализ в зависимости от типов
            analysis_results = {}
            
            for analysis_type in analysis_types:
                if analysis_type == "security":
                    analysis_results["security_findings"] = await self._perform_security_analysis(content)
                elif analysis_type == "quality":
                    analysis_results["quality_issues"] = await self._perform_quality_analysis(content)
                elif analysis_type == "complexity":
                    analysis_results["complexity_metrics"] = await self._perform_complexity_analysis(content)
                elif analysis_type == "dependencies":
                    analysis_results["dependency_issues"] = await self._perform_dependency_analysis(content)
            
            return {
                "success": True,
                "analysis_results": analysis_results,
                "file_info": {
                    "path": str(path),
                    "size": file_size,
                    "extension": path.suffix.lower()
                }
            }
        except UnicodeDecodeError:
            return {
                "success": False,
                "error": f"Не удалось декодировать файл с кодировкой utf-8: {file_path}"
            }
        except PermissionError:
            return {
                "success": False,
                "error": f"Нет доступа к файлу: {file_path}"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Ошибка при анализе файла: {str(e)}"
            }
    
    def validate_parameters(self, parameters: Dict[str, Any]) -> bool:
        """Проверить параметры"""
        if "file_path" not in parameters:
            return False
        
        file_path = parameters["file_path"]
        if not isinstance(file_path, str) or not file_path.strip():
            return False
        
        # Проверить типы анализа, если указаны
        if "analysis_types" in parameters:
            analysis_types = parameters["analysis_types"]
            if not isinstance(analysis_types, list):
                return False
            
            valid_types = {"security", "quality", "complexity", "dependencies"}
            if not all(atype in valid_types for atype in analysis_types):
                return False
        
        return True
```

## 12. Миграция

При обновлении фреймворка до новых версий:

1. **Оценка изменений**: Определите, какие компоненты затронуты
2. **Тестирование**: Протестируйте изменения в изолированной среде
3. **Постепенное обновление**: Обновляйте компоненты по одному
4. **Валидация**: Проверьте корректность работы после обновления

### Пример миграции:

```python
class MigrationAdapter:
    """Адаптер для миграции между версиями компонентов"""
    
    def __init__(self, old_component):
        self.old_component = old_component
    
    async def execute_task(self, task_description: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Адаптировать вызов к новому интерфейсу"""
        # Вызвать старую реализацию
        old_result = await self.old_component.execute_task(task_description)
        
        # Адаптировать результат к новому формату
        if isinstance(old_result, str):
            return {"success": True, "result": old_result}
        elif isinstance(old_result, dict):
            return old_result
        else:
            return {"success": True, "result": str(old_result)}
```

## 13. Лучшие практики

### 13.1 Модульность и расширяемость

Создавайте компоненты, которые можно легко расширять:

```python
# Хорошо: модульные и расширяемые компоненты
class BasePattern:
    """Базовый паттерн"""
    pass

class AnalysisPattern(BasePattern):
    """Паттерн анализа"""
    pass

class SecurityAnalysisPattern(AnalysisPattern):
    """Паттерн анализа безопасности"""
    pass

# Плохо: монолитный паттерн
class MonolithicPattern:
    """Монолитный паттерн - сложно расширять и тестировать"""
    pass
```

### 13.2 Безопасность и валидация

Обязательно учитывайте безопасность при создании компонентов:

```python
def validate_input_safety(self, parameters: Dict[str, Any]) -> List[str]:
    """Проверить параметры на безопасность"""
    errors = []
    
    # Проверить чувствительные поля
    sensitive_fields = ["password", "token", "api_key", "secret", "credentials"]
    for field in sensitive_fields:
        if field in parameters:
            errors.append(f"Чувствительное поле '{field}' обнаружено в параметрах")
    
    # Проверить размер параметров
    params_size = len(str(parameters))
    max_size = 10 * 1024 * 1024  # 10MB
    if params_size > max_size:
        errors.append(f"Параметры слишком велики: {params_size} байт, максимум {max_size}")
    
    return errors
```

### 13.3 Обработка ошибок

Обеспечьте надежную обработку ошибок:

```python
async def execute_task(self, task_description: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
    """Выполнить задачу с надежной обработкой ошибок"""
    try:
        # Проверить ограничения
        if self.state.error_count > self.max_error_threshold:
            return {
                "success": False,
                "error": "Превышено максимальное количество ошибок",
                "needs_reset": True
            }
        
        # Проверить безопасность задачи
        if not self._check_task_security(task_description, context):
            return {
                "success": False,
                "error": "Задача не соответствует политике безопасности",
                "security_violation": True
            }
        
        # Выполнить основную логику
        result = await self._execute_extended_logic(task_description, context)
        
        # Обновить состояние при успехе
        self.state.register_progress(progressed=True)
        
        return {"success": True, **result}
    except SecurityError as e:
        self.state.register_error()
        self.state.complete()  # Критическая ошибка безопасности
        return {
            "success": False,
            "error": f"Ошибка безопасности: {str(e)}",
            "error_type": "security",
            "terminated": True
        }
    except ResourceLimitExceededError as e:
        self.state.register_error()
        return {
            "success": False,
            "error": f"Превышено ограничение ресурсов: {str(e)}",
            "error_type": "resource_limit"
        }
    except Exception as e:
        self.state.register_error()
        return {
            "success": False,
            "error": f"Внутренняя ошибка: {str(e)}",
            "error_type": "internal"
        }
```

### 13.4 Тестирование

Создавайте тесты для каждого компонента:

```python
# test_custom_components.py
import pytest
from unittest.mock import AsyncMock, Mock
import tempfile
import os

class TestCustomAgent:
    @pytest.mark.asyncio
    async def test_custom_agent_task_execution(self):
        """Тест выполнения задачи специфическим агентом"""
        # Создать специфический агент
        agent = CustomAgent(domain_type=DomainType.CODE_ANALYSIS)
        
        # Выполнить задачу
        result = await agent.execute_task(
            task_description="Проанализируй этот Python код на безопасность",
            context={
                "code": """
def vulnerable_login(username, password):
    query = f"SELECT * FROM users WHERE username='{username}' AND password='{password}'"
    return execute_query(query)
""",
                "language": "python"
            }
        )
        
        # Проверить результат
        assert "success" in result
        assert result["success"] is True
        assert "findings" in result or "result" in result
```

## Заключение

Composable AI Agent Framework предоставляет гибкую и расширяемую архитектуру для создания AI-агентов, решающих сложные задачи. Следуя принципам чистой архитектуры и лучшим практикам безопасности, вы можете адаптировать фреймворк под свои специфические задачи, создавая мощные и надежные решения.

Для получения более подробной информации о конкретных аспектах фреймворка см. соответствующие разделы документации.

</final_file_content>

IMPORTANT: For any future changes to this file, use the final_file_content shown above as your reference. This content reflects the current state of the file, including any auto-formatting (e.g., if you used single quotes but the formatter converted them to double quotes). Always base your SEARCH/REPLACE operations on this final version to ensure accuracy.