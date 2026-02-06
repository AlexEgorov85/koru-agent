# Полный обзор Composable AI Agent Framework

Composable AI Agent Framework - это мощная и гибкая система для создания, управления и выполнения AI-агентов, способных решать сложные задачи через компонуемые паттерны мышления. В этом разделе представлен полный обзор всех аспектов фреймворка и рекомендации по его использованию под свои задачи.

## Архитектурный обзор

### 1. Чистая архитектура (Clean Architecture)

Фреймворк реализует принципы чистой архитектуры с направленными внутрь зависимостями:

```
┌─────────────────┐
│   Infrastructure│
│        ▲        │
│        │        │
├─────────────────┤
│   Application   │
│        ▲        │
│        │        │
├─────────────────┤
│     Domain      │
│                 │
└─────────────────┘
```

- **Слой домена**: Содержит бизнес-логику и правила, не зависит от внешних слоев
- **Слой приложений**: Координирует работу компонентов домена, реализует сценарии использования
- **Слой инфраструктуры**: Реализует внешние зависимости (базы данных, внешние API, файловая система)

### 2. Компоненты системы

#### Агенты
- **Компонуемые агенты**: Основные исполнители логики, могут комбинировать различные паттерны мышления
- **Состояние агента**: Явное состояние с отслеживанием прогресса и ошибок
- **Адаптация к доменам**: Возможность адаптации к различным областям задач

#### Паттерны мышления
- **Компонуемые паттерны**: Стратегии решения задач, которые могут быть скомбинованы
- **Атомарные действия**: Минимальные неделимые операции
- **Восстановление паттернов**: Механизмы восстановления после ошибок

#### Система промтов
- **Версионирование**: Поддержка семантического версионирования промтов
- **Категоризация**: Организация промтов по доменам и ролям
- **Валидация**: Проверка безопасности и корректности промтов
- **Кэширование**: Оптимизация доступа к промтам

#### Инструменты и навыки
- **Инструменты**: Компоненты для взаимодействия с внешними системами
- **Навыки**: Компоненты более высокого уровня, объединяющие несколько инструментов
- **Безопасность**: Встроенные механизмы безопасности и валидации

## Настройка под свои задачи

### 1. Адаптация агентов

Для адаптации агентов под свои задачи:

```python
# Создание специфического агента
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
    
    def _select_specialized_pattern(self, task_description: str, context: Dict[str, Any]) -> Optional[IThinkingPattern]:
        """Выбрать подходящий специфический паттерн для задачи"""
        for pattern in self._specialized_patterns:
            if pattern.can_handle_task(task_description, context):
                return pattern
        return None
```

### 2. Создание специфических паттернов

Для создания паттернов под специфические задачи:

```python
class SpecializedThinkingPattern(IThinkingPattern):
    """Специфический паттерн мышления для конкретных задач"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.name = config.get("name", "specialized_pattern")
        self._required_tools = config.get("required_tools", [])
        self._execution_strategy = config.get("execution_strategy", "sequential")
    
    async def execute(
        self,
        state: AgentState,
        context: Any,
        available_capabilities: List[str]
    ) -> Dict[str, Any]:
        """Выполнить специфический паттерн мышления"""
        try:
            # Проверить доступность необходимых возможностей
            missing_capabilities = [
                tool for tool in self._required_tools 
                if tool not in available_capabilities
            ]
            
            if missing_capabilities:
                return {
                    "success": False,
                    "error": f"Отсутствуют необходимые возможности: {missing_capabilities}",
                    "missing_capabilities": missing_capabilities
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
                "error": f"Ошибка при выполнении паттерна: {str(e)}",
                "pattern_used": self.name
            }
    
    async def _execute_specialized_logic(self, state: AgentState, context: Any) -> Dict[str, Any]:
        """Выполнить специфическую логику паттерна"""
        # Реализация специфической логики для решения задачи
        pass
    
    async def adapt_to_task(self, task_description: str) -> Dict[str, Any]:
        """Адаптировать паттерн к конкретной задаче"""
        # Определить, может ли паттерн обработать задачу
        can_handle = self._can_handle_task(task_description)
        
        return {
            "can_handle": can_handle,
            "confidence_level": self._calculate_confidence(task_description) if can_handle else 0,
            "required_capabilities": self._required_tools,
            "estimated_complexity": self._estimate_complexity(task_description)
        }
    
    def _can_handle_task(self, task_description: str) -> bool:
        """Проверить, может ли паттерн обработать задачу"""
        # Реализация проверки возможности обработки задачи
        pass
    
    def _calculate_confidence(self, task_description: str) -> float:
        """Рассчитать уровень уверенности в обработке задачи"""
        # Реализация расчета уверенности
        pass
    
    def _estimate_complexity(self, task_description: str) -> str:
        """Оценить сложность задачи"""
        # Реализация оценки сложности
        pass
```

### 3. Настройка системы промтов

Для адаптации системы промтов под свои задачи:

```python
# Структура хранения промтов
prompts/
├── {domain}/                    # Домен задачи
│   └── {capability}/            # Капабилити
│       ├── {role}/              # Роль (system, user, assistant, tool)
│       │   ├── v{version}.md    # Файл версии промта
│       │   └── ...
│       └── _index.yaml          # Индекс капабилити (опционально)

# Пример специфического промта
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

# Инструкции для анализа безопасности кода

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
        self.middleware = []
        self.event_log = []
        self.max_log_size = 1000
    
    def subscribe(self, event_type: EventType, handler: Callable):
        """Подписаться на событие"""
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        self.subscribers[event_type].append(handler)
    
    async def publish(self, event_type: EventType, data: Dict[str, Any]):
        """Опубликовать событие"""
        # Применить middleware
        processed_data = data.copy()
        for middleware_func in self.middleware:
            processed_data = await middleware_func(event_type, processed_data)
        
        # Вызвать обработчики
        if event_type in self.subscribers:
            for handler in self.subscribers[event_type]:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(event_type, processed_data)
                    else:
                        handler(event_type, processed_data)
                except Exception as e:
                    print(f"Ошибка при обработке события {event_type}: {e}")
        
        # Залогировать событие
        self._log_event(event_type, processed_data)
    
    def add_middleware(self, middleware_func: Callable):
        """Добавить middleware для обработки событий"""
        self.middleware.append(middleware_func)
    
    def _log_event(self, event_type: EventType, data: Dict[str, Any]):
        """Залогировать событие"""
        event_entry = {
            "timestamp": time.time(),
            "type": event_type.value,
            "data": data
        }
        
        self.event_log.append(event_entry)
        
        # Ограничить размер лога
        if len(self.event_log) > self.max_log_size:
            self.event_log = self.event_log[-self.max_log_size:]
```

### 2. Менеджер доменов

Менеджер доменов адаптирует агентов к различным областям задач:

```python
class DomainManager:
    """Менеджер доменов для адаптации агентов к различным областям задач"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.domains = {}
        self.agent_domains = {}
        self.domain_capabilities = {}
        self.domain_prompts = {}
        self.security_policies = {}
    
    async def register_domain(self, domain_type: DomainType, config: Dict[str, Any]):
        """Зарегистрировать домен с конфигурацией"""
        domain_config = {
            **self.config.get("domain_defaults", {}),
            **config
        }
        
        self.domains[domain_type] = domain_config
        self.domain_capabilities[domain_type] = domain_config.get("capabilities", [])
        
        # Загрузить специфические промты домена
        await self._load_domain_prompts(domain_type, domain_config)
        
        # Установить политику безопасности домена
        if "security_policy" in domain_config:
            self.security_policies[domain_type] = domain_config["security_policy"]
    
    async def adapt_agent_to_domain(self, agent_id: str, domain_type: DomainType, capabilities: List[str]):
        """Адаптировать агента к домену с указанными возможностями"""
        if domain_type not in self.domains:
            raise ValueError(f"Домен {domain_type} не зарегистрирован")
        
        # Проверить, что указанные возможности доступны для домена
        available_capabilities = self.get_domain_capabilities(domain_type)
        for capability in capabilities:
            if capability not in available_capabilities:
                raise ValueError(f"Возможность {capability} не доступна для домена {domain_type}")
        
        # Адаптировать агента
        self.agent_domains[agent_id] = {
            "domain_type": domain_type,
            "capabilities": capabilities,
            "adaptation_time": time.time()
        }
        
        # Загрузить доменно-специфические промты и паттерны для агента
        await self._adapt_agent_components(agent_id, domain_type, capabilities)
    
    def get_domain_capabilities(self, domain_type: DomainType) -> List[str]:
        """Получить возможности домена"""
        return self.domain_capabilities.get(domain_type, [])
    
    async def _load_domain_prompts(self, domain_type: DomainType, config: Dict[str, Any]):
        """Загрузить промты для домена"""
        from application.services.prompt_loader import PromptLoader
        
        prompt_loader = PromptLoader(base_path=f"./prompts/{domain_type.value}")
        domain_prompts, errors = prompt_loader.load_all_prompts()
        
        if errors:
            print(f"Ошибки загрузки промтов для домена {domain_type}: {errors}")
        
        self.domain_prompts[domain_type] = domain_prompts
    
    async def _adapt_agent_components(self, agent_id: str, domain_type: DomainType, capabilities: List[str]):
        """Адаптировать компоненты агента к домену"""
        # В реальной реализации здесь будет адаптация
        # компонентов агента к специфике домена
        pass
```

## Практики безопасности

### 1. Валидация входных данных

Обязательно валидируйте все входные данные:

```python
def validate_prompt_parameters(self, parameters: Dict[str, Any]) -> bool:
    """Проверить параметры промта на безопасность"""
    required_fields = ["path"]  # или другие обязательные поля
    if not all(field in parameters for field in required_fields):
        return False
    
    # Проверить безопасность путей
    if "path" in parameters:
        if not self._is_safe_path(parameters["path"]):
            return False
    
    # Проверить размер данных
    data_size = len(str(parameters))
    if data_size > 10 * 1024 * 1024:  # 10MB ограничение
        return False
    
    return True

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

### 2. Управление доступом

Используйте системы управления доступом:

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

## Лучшие практики

### 1. Модульность и расширяемость

Создавайте компоненты, которые можно легко расширять:

```python
# Хорошо: модульная архитектура
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

### 2. Обработка ошибок

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
        
        # Выполнить основную логику
        result = await self._execute_extended_logic(task_description, context)
        
        # Обновить состояние при успехе
        self.state.register_progress(progressed=True)
        
        return {"success": True, **result}
    except ValidationError as e:
        self.state.register_error()
        return {
            "success": False,
            "error": f"Ошибка валидации: {str(e)}",
            "error_type": "validation_error"
        }
    except SecurityError as e:
        self.state.register_error()
        self.state.complete()  # Критическая ошибка безопасности
        return {
            "success": False,
            "error": f"Ошибка безопасности: {str(e)}",
            "error_type": "security",
            "terminated": True
        }
    except Exception as e:
        self.state.register_error()
        return {
            "success": False,
            "error": f"Внутренняя ошибка: {str(e)}",
            "error_type": "internal"
        }
```

### 3. Тестирование

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

class TestSpecializedPattern:
    @pytest.mark.asyncio
    async def test_pattern_adaptation(self):
        """Тест адаптации паттерна к задаче"""
        pattern = SpecializedThinkingPattern({
            "name": "security_analyzer",
            "required_tools": ["code_reader", "ast_parser"]
        })
        
        adaptation_result = await pattern.adapt_to_task(
            "Проанализируй код на наличие уязвимостей SQL-инъекции"
        )
        
        assert adaptation_result["can_handle"] is True
        assert adaptation_result["confidence_level"] > 0.5
        assert "security_analyzer" in adaptation_result["required_capabilities"]
    
    @pytest.mark.asyncio
    async def test_pattern_execution(self):
        """Тест выполнения специфического паттерна"""
        pattern = SpecializedThinkingPattern()
        
        result = await pattern.execute(
            state=AgentState(),
            context={"code": "print('Hello, World!')"},
            available_capabilities=["code_reader", "ast_parser"]
        )
        
        assert result["success"] is True
        assert "pattern_used" in result
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
    
    # Создать специфические инструменты
    specialized_tools = SpecializedTools()
    
    # Создать специфические паттерны
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

## Расширение функциональности

Фреймворк легко расширяется через:

1. **Новые паттерны мышления** - для новых стратегий решения задач
2. **Новые атомарные действия** - для новых возможностей взаимодействия
3. **Новые домены** - для новых областей применения
4. **Новые промты** - для новых специфичных инструкций
5. **Новые инструменты** - для интеграции с внешними системами
6. **Новые навыки** - для объединения нескольких действий

Такая архитектура позволяет адаптировать фреймворк под самые разные задачи, от анализа кода до обработки данных и генерации контента, обеспечивая модульность, безопасность и надежность системы.