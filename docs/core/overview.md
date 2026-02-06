# Обзор Composable AI Agent Framework

Composable AI Agent Framework - это гибкая и расширяемая система для создания, управления и выполнения AI-агентов, способных решать сложные задачи через компонуемые паттерны мышления. Фреймворк реализует архитектуру, в которой LLM не управляет системой напрямую, а принимает решения, которые строго валидируются и исполняются кодом.

## Архитектурные принципы

### 1. Чистая архитектура (Clean Architecture)

Фреймворк реализует принципы чистой архитектуры:

- **Зависимости направлены внутрь**: Внешние слои зависят от внутренних, а не наоборот
- **Независимость от фреймворков**: Ядро системы не зависит от конкретных фреймворков
- **Тестируемость**: Бизнес-логика может быть протестирована без внешних зависимостей
- **Независимость от UI**: UI может быть изменен без влияния на бизнес-логику
- **Независимость от базы данных**: Бизнес-правила не зависят от конкретной СУБД

### 2. Слои системы

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

Компонуемые агенты - это основные исполнители логики в системе. Они могут комбинировать различные паттерны мышления для решения сложных задач:

```python
class ComposableAgent:
    """Компонуемый агент с возможностью комбинирования паттернов мышления"""
    
    def __init__(self, domain: DomainType, capabilities: List[str] = None):
        self.domain = domain
        self.capabilities = capabilities or []
        self.state = AgentState()
        self.event_publisher = EventPublisher()
        self.action_executor = AtomicActionExecutor()
        self.pattern_executor = PatternExecutor()
    
    async def execute_task(self, task_description: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Выполнить задачу с использованием подходящих паттернов мышления"""
        # Определить подходящий паттерн на основе задачи и контекста
        pattern = await self._select_appropriate_pattern(task_description, context)
        
        if not pattern:
            return {"success": False, "error": "Не найден подходящий паттерн для задачи"}
        
        # Выполнить паттерн
        result = await pattern.execute(self.state, context, self.capabilities)
        
        return {"success": True, "result": result}
    
    async def _select_appropriate_pattern(self, task_description: str, context: Dict[str, Any]) -> Optional[IThinkingPattern]:
        """Выбрать подходящий паттерн мышления для задачи"""
        for pattern in self.available_patterns:
            if await pattern.can_handle_task(task_description, context):
                return pattern
        return None
```

### 2. Паттерны мышления

Паттерны мышления определяют стратегии решения задач:

```python
class IThinkingPattern(ABC):
    """Интерфейс паттерна мышления"""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Уникальное имя паттерна мышления"""
        pass
    
    @abstractmethod
    async def execute(
        self,
        state: AgentState,
        context: Any,
        available_capabilities: List[str]
    ) -> Dict[str, Any]:
        """Выполнить паттерн мышления"""
        pass
    
    @abstractmethod
    async def adapt_to_task(self, task_description: str) -> Dict[str, Any]:
        """Адаптировать паттерн к задаче"""
        pass

class AnalysisPattern(IThinkingPattern):
    """Паттерн анализа для решения задач анализа"""
    
    @property
    def name(self) -> str:
        return "analysis_pattern"
    
    async def execute(
        self,
        state: AgentState,
        context: Any,
        available_capabilities: List[str]
    ) -> Dict[str, Any]:
        """Выполнить анализ"""
        # Логика выполнения анализа
        pass
    
    async def adapt_to_task(self, task_description: str) -> Dict[str, Any]:
        """Адаптировать паттерн к задаче анализа"""
        return {"analysis_type": self._determine_analysis_type(task_description)}
```

### 3. Атомарные действия

Атомарные действия - минимальные неделимые операции:

```python
class IAtomicAction(ABC):
    """Интерфейс атомарного действия"""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Имя действия"""
        pass
    
    @abstractmethod
    async def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Выполнить действие с параметрами"""
        pass
    
    @abstractmethod
    def validate_parameters(self, parameters: Dict[str, Any]) -> bool:
        """Проверить параметры"""
        pass

class FileReaderAction(IAtomicAction):
    """Действие для чтения файлов"""
    
    @property
    def name(self) -> str:
        return "file_reader"
    
    async def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Выполнить чтение файла"""
        file_path = parameters["path"]
        
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read()
            
            return {
                "success": True,
                "content": content,
                "size": len(content)
            }
        except FileNotFoundError:
            return {
                "success": False,
                "error": f"Файл не найден: {file_path}"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Ошибка при чтении файла: {str(e)}"
            }
    
    def validate_parameters(self, parameters: Dict[str, Any]) -> bool:
        """Проверить параметры"""
        return "path" in parameters and isinstance(parameters["path"], str)
```

## Система промтов

Система промтов обеспечивает гибкое управление и версионирование промтов:

### Структура хранения

Промты организованы в иерархическую структуру:

```
prompts/
├── {domain}/                    # Домен (например, code_analysis, data_processing)
│   └── {capability}/            # Капабилити (например, code_generation, data_query)
│       ├── {role}/              # Роль (system, user, assistant, tool)
│       │   ├── v{version}.md    # Файл версии промта
│       │   └── ...
│       └── _index.yaml          # Индекс капабилити (опционально)
```

### Формат файла промта

Каждый файл промта использует формат Markdown с YAML frontmatter:

```markdown
---
provider: openai
role: system
status: active
variables:
  - name: task_description
    type: string
    required: true
    description: "Описание задачи для анализа"
  - name: target_vulnerabilities
    type: array
    required: false
    description: "Целевые типы уязвимостей для поиска"
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

Ты являешься экспертом в области безопасности кода. При анализе кода следуй следующим принципам:

1. Идентифицируй потенциальные уязвимости в коде
2. Оцени уровень риска каждой уязвимости
3. Предложи конкретные рекомендации по устранению
4. Объясни, почему каждая уязвимость представляет риск

## Задача

{{task_description}}

{% if target_vulnerabilities %}
## Фокусируйся на этих типах уязвимостей:
{% for vuln in target_vulnerabilities %}
- {{vuln}}
{% endfor %}
{% endif %}
```

## Интеграция компонентов

### 1. Система событий

Система событий обеспечивает коммуникацию между компонентами:

```python
class EventBus:
    """Шина событий для коммуникации между компонентами"""
    
    def __init__(self):
        self.subscribers = {}
    
    def subscribe(self, event_type: str, handler: Callable):
        """Подписаться на событие"""
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        self.subscribers[event_type].append(handler)
    
    async def publish(self, event_type: str, data: Dict[str, Any]):
        """Опубликовать событие"""
        if event_type in self.subscribers:
            for handler in self.subscribers[event_type]:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(event_type, data)
                    else:
                        handler(event_type, data)
                except Exception as e:
                    print(f"Ошибка при обработке события {event_type}: {e}")
```

### 2. Менеджер доменов

Менеджер доменов адаптирует агентов к различным областям задач:

```python
class DomainManager:
    """Менеджер доменов для адаптации агентов к различным областям задач"""
    
    def __init__(self):
        self.domains = {}
        self.agent_domains = {}
        self.domain_capabilities = {}
    
    async def register_domain(self, domain_type: DomainType, config: Dict[str, Any]):
        """Зарегистрировать домен с конфигурацией"""
        self.domains[domain_type] = config
        self.domain_capabilities[domain_type] = config.get("capabilities", [])
    
    async def adapt_agent_to_domain(self, agent_id: str, domain_type: DomainType, capabilities: List[str]):
        """Адаптировать агента к домену с указанными возможностями"""
        if domain_type not in self.domains:
            raise ValueError(f"Домен {domain_type} не зарегистрирован")
        
        # Проверить, что указанные возможности доступны для домена
        available_capabilities = self.domain_capabilities[domain_type]
        for capability in capabilities:
            if capability not in available_capabilities:
                raise ValueError(f"Возможность {capability} не доступна для домена {domain_type}")
        
        self.agent_domains[agent_id] = {
            "domain_type": domain_type,
            "capabilities": capabilities,
            "adaptation_time": time.time()
        }
```

## Интеграция с LLM

Система интегрирована с различными LLM-провайдерами:

```python
class LLMAdapter:
    """Адаптер для интеграции с различными LLM-провайдерами"""
    
    def __init__(self, provider_type: LLMProviderType, config: Dict[str, Any]):
        self.provider_type = provider_type
        self.config = config
        self.client = self._initialize_client()
    
    def _initialize_client(self):
        """Инициализировать клиент для провайдера"""
        if self.provider_type == LLMProviderType.OPENAI:
            from openai import AsyncOpenAI
            return AsyncOpenAI(api_key=self.config["api_key"])
        elif self.provider_type == LLMProviderType.ANTHROPIC:
            from anthropic import AsyncAnthropic
            return AsyncAnthropic(api_key=self.config["api_key"])
        # Другие провайдеры...
    
    async def call_llm(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """Вызвать LLM с сообщениями"""
        params = {
            "model": self.config["model"],
            "messages": messages,
            **self.config.get("default_params", {}),
            **kwargs
        }
        
        if self.provider_type == LLMProviderType.OPENAI:
            response = await self.client.chat.completions.create(**params)
            return response.choices[0].message.content
        elif self.provider_type == LLMProviderType.ANTHROPIC:
            response = await self.client.messages.create(**params)
            return response.content[0].text
```

## Безопасность и валидация

Фреймворк включает встроенные механизмы безопасности:

### 1. Валидация промтов

Система проверяет промты на безопасность и корректность:

```python
class PromptValidator:
    """Валидатор промтов"""
    
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
            if re.search(pattern, content, re.IGNORECASE):
                errors.append(f"Обнаружена потенциальная инструкция обхода безопасности: {pattern}")
        
        # Проверить на наличие попыток выполнения системных команд
        system_command_patterns = [
            r"execute\s+system\s+command",
            r"run\s+shell\s+command",
            r"os\.",
            r"subprocess\.",
            r"import\s+os",
            r"import\s+subprocess"
        ]
        
        for pattern in system_command_patterns:
            if re.search(pattern, content):
                errors.append(f"Обнаружена потенциальная попытка выполнения системной команды: {pattern}")
        
        return errors
    
    def validate_prompt_variables(self, content: str, variables_schema: List[VariableSchema]) -> List[str]:
        """Проверить использование переменных в промте"""
        errors = []
        
        for variable in variables_schema:
            placeholder = f"{{{variable.name}}}"
            if variable.required and placeholder not in content:
                errors.append(f"Обязательная переменная '{variable.name}' не используется в промте")
        
        return errors
```

### 2. Управление доступом

Система включает механизмы управления доступом к ресурсам:

```python
class AccessControlManager:
    """Менеджер контроля доступа"""
    
    def __init__(self):
        self.permissions = {}
        self.role_assignments = {}
    
    def check_permission(self, agent_id: str, resource: str, action: str) -> bool:
        """Проверить, есть ли у агента разрешение на действие с ресурсом"""
        agent_roles = self.role_assignments.get(agent_id, [])
        
        for role in agent_roles:
            role_permissions = self.permissions.get(role, {})
            if resource in role_permissions:
                allowed_actions = role_permissions[resource]
                if action in allowed_actions or "*" in allowed_actions:
                    return True
        
        return False
    
    def validate_file_access(self, file_path: str, agent_id: str) -> bool:
        """Проверить, может ли агент получить доступ к файлу"""
        # Проверить, находится ли файл в разрешенных директориях
        allowed_directories = self._get_allowed_directories(agent_id)
        
        file_absolute_path = Path(file_path).resolve()
        
        for allowed_dir in allowed_directories:
            try:
                file_absolute_path.relative_to(Path(allowed_dir).resolve())
                return True
            except ValueError:
                continue
        
        return False
    
    def _get_allowed_directories(self, agent_id: str) -> List[str]:
        """Получить разрешенные директории для агента"""
        # В реальной реализации здесь будет логика получения
        # разрешенных директорий на основе ролей агента
        return ["./projects", "./data", "./outputs"]
```

## Примеры использования

### 1. Простой пример использования

```python
# simple_usage_example.py
from application.factories.agent_factory import AgentFactory
from domain.value_objects.domain_type import DomainType

async def simple_usage_example():
    """Простой пример использования фреймворка"""
    
    # Создать фабрику агентов
    agent_factory = AgentFactory()
    
    # Создать агента для анализа кода
    agent = await agent_factory.create_agent(
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
    
    print(f"Результат анализа: {result}")
    
    return result

if __name__ == "__main__":
    import asyncio
    asyncio.run(simple_usage_example())
```

### 2. Сложный пример с кастомными компонентами

```python
# advanced_usage_example.py
from application.factories.advanced_factory import AdvancedAgentFactory
from application.services.custom_pattern_service import CustomPatternService
from infrastructure.tools.specialized_tools import SpecializedTools

async def advanced_usage_example():
    """Пример сложного использования с кастомными компонентами"""
    
    # Создать расширенную фабрику
    factory = AdvancedAgentFactory()
    
    # Создать кастомные инструменты
    specialized_tools = SpecializedTools()
    
    # Создать кастомные паттерны
    custom_patterns = [
        await factory.create_pattern("security_analysis", config={"depth": "deep"}),
        await factory.create_pattern("code_quality", config={"standards": ["pep8", "security"]})
    ]
    
    # Создать агента с кастомными компонентами
    agent = await factory.create_agent_with_components(
        agent_type="composable",
        domain=DomainType.CODE_ANALYSIS,
        tools=[specialized_tools.security_scanner, specialized_tools.code_analyzer],
        patterns=custom_patterns
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

if __name__ == "__main__":
    import asyncio
    asyncio.run(advanced_usage_example())
```

## Лучшие практики

### 1. Модульность и расширяемость

- Создавайте компоненты, которые можно легко заменить или расширить
- Используйте интерфейсы и абстракции для слабой связанности
- Разделяйте ответственность между компонентами

### 2. Безопасность

- Валидируйте все входные данные
- Ограничивайте доступ к системным ресурсам
- Шифруйте чувствительные данные
- Используйте принцип наименьших привилегий

### 3. Обработка ошибок

- Обеспечьте надежную обработку ошибок на всех уровнях
- Реализуйте механизмы восстановления
- Логгируйте ошибки для анализа
- Используйте таймауты для предотвращения зависания

### 4. Тестирование

- Тестируйте каждый компонент отдельно
- Используйте mock-объекты для изоляции
- Покрывайте граничные случаи
- Тестируйте сценарии интеграции

## Расширение функциональности

Фреймворк легко расширяется через:

1. **Новые паттерны мышления** - для новых стратегий решения задач
2. **Новые атомарные действия** - для новых возможностей взаимодействия
3. **Новые домены** - для новых областей применения
4. **Новые промты** - для новых специфичных инструкций
5. **Новые инструменты** - для интеграции с внешними системами

Такая архитектура позволяет адаптировать фреймворк под самые разные задачи, от анализа кода до обработки данных и генерации контента.