# Полное руководство по Koru AI Agent Framework

Koru AI Agent Framework - это гибкая и расширяемая система для создания, управления и выполнения AI-агентов, способных решать сложные задачи через компонуемые паттерны мышления. В этом полном руководстве описаны все аспекты фреймворка и рекомендации по его использованию под специфические задачи.

## 1. Введение

### 1.1 Обзор системы

Koru AI Agent Framework реализует архитектуру, в которой LLM не управляет системой напрямую, а принимает решения, которые строго валидируются и исполняются кодом. Это обеспечивает контролируемость, надежность и безопасность AI-агентов.

Ключевые особенности:
- **Компонуемость**: Возможность комбинировать различные паттерны мышления для решения сложных задач
- **Чистая архитектура**: Четкое разделение на доменные, прикладные и инфраструктурные слои
- **Безопасность**: Строгая валидация решений, принятых LLM
- **Расширяемость**: Легкое создание новых компонентов и адаптация под специфические задачи
- **Версионирование**: Полнофункциональная система управления версиями промтов
- **Доменная адаптация**: Агенты могут адаптироваться к различным областям задач

### 1.2 Установка

Для установки фреймворка:

```bash
git clone https://github.com/AlexEgorov85/Agent_code.git
cd Agent_code
python -m venv venv
source venv/bin/activate  # или venv\Scripts\activate на Windows
pip install -r requirements.txt
```

### 1.3 Быстрый старт

Простой пример использования:

```python
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

## 2. Архитектура

### 2.1 Принципы архитектуры

Фреймворк реализует принципы чистой архитектуры:

1. **Зависимости направлены внутрь**: Внешние слои зависят от внутренних, а не наоборот
2. **Независимость от фреймворков**: Ядро системы не зависит от конкретных фреймворков
3. **Тестируемость**: Бизнес-логика может быть протестирована без внешних зависимостей
4. **Независимость от UI**: UI может быть изменен без влияния на бизнес-логику
5. **Независимость от базы данных**: Бизнес-правила не зависят от конкретной СУБД

### 2.2 Слои системы

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

### 2.3 Примеры архитектурных компонентов

```python
# domain/models/agent_state.py
from pydantic import BaseModel
from typing import Dict, Any, List, Optional

class AgentState(BaseModel):
    """
    Явное состояние агента.
    Не содержит логики — только данные.
    """

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

## 3. Компоненты системы

### 3.1 Компонуемые агенты

Компонуемые агенты - основные исполнители логики в системе:

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

### 3.2 Паттерны мышления

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
    async def execute(self, state, context, available_capabilities):
        """Выполнить паттерн мышления"""
        pass
    
    @abstractmethod
    async def adapt_to_task(self, task_description):
        """Адаптировать паттерн к задаче"""
        pass
```

### 3.3 Атомарные действия

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
    async def execute(self, parameters):
        """Выполнить действие с параметрами"""
        pass
    
    @abstractmethod
    def validate_parameters(self, parameters):
        """Проверить параметры"""
        pass
```

### 3.4 Система промтов

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

## 4. Разработка под свои задачи

### 4.1 Создание специфических агентов

Для адаптации агентов под свои задачи:

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

### 4.2 Создание специфических паттернов

Для создания паттернов под специфические задачи:

```python
class SpecializedThinkingPattern(IThinkingPattern):
    """Специфический паттерн мышления для конкретных задач"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.name = config.get("name", "specialized_pattern")
        self._required_tools = config.get("required_tools", [])
        self._execution_strategy = config.get("execution_strategy", "sequential")
        self._supported_domains = config.get("supported_domains", [])
        self._task_keywords = config.get("task_keywords", [])
    
    async def execute(
        self,
        state: AgentState,
        context: Any,
        available_capabilities: List[str]
    ) -> Dict[str, Any]:
        """Выполнить специфический паттерн мышления"""
        try:
            # Проверить, доступны ли необходимые инструменты
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
                "pattern_used": self.name,
                "error_type": type(e).__name__
            }
    
    async def _execute_specialized_logic(self, state: AgentState, context: Any) -> Dict[str, Any]:
        """Выполнить специфическую логику паттерна"""
        # Реализация специфической логики для решения задачи
        # в зависимости от типа паттерна и конфигурации
        pass
```

### 4.3 Создание специфических инструментов

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
            
            # Прочитать файл
            with open(path, 'r', encoding='utf-8') as file:
                content = file.read()
            
            # Выполнить анализ в зависимости от типов
            analysis_results = {}
            
            for analysis_type in analysis_types:
                if analysis_type == "security":
                    analysis_results["security_analysis"] = await self._perform_security_analysis(content)
                elif analysis_type == "quality":
                    analysis_results["quality_analysis"] = await self._perform_quality_analysis(content)
                elif analysis_type == "complexity":
                    analysis_results["complexity_analysis"] = await self._perform_complexity_analysis(content)
                elif analysis_type == "dependencies":
                    analysis_results["dependency_analysis"] = await self._perform_dependency_analysis(content)
            
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

### 4.4 Создание специфических промтов

Для создания промтов под специфические задачи:

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

## 5. Безопасность

### 5.1 Проверка безопасности промтов

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
        import re
        if re.search(pattern, content):
            errors.append(f"Обнаружена потенциальная попытка выполнения системной команды: {pattern}")
    
    return errors
```

### 5.2 Безопасность путей

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

## 6. Тестирование

### 6.1 Модульное тестирование

Тестируйте каждый компонент отдельно:

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

### 6.2 Интеграционное тестирование

Тестируйте взаимодействие между компонентами:

```python
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
        
        # Выбрать подходящий промт
        code_analysis_prompts = [
            p for p in prompts 
            if p.domain == DomainType.CODE_ANALYSIS
            and p.role == PromptRole.SYSTEM
        ]
        
        assert len(code_analysis_prompts) > 0, "Должен быть хотя бы один промт анализа кода"
        
        # Выполнить задачу через агента (псевдокод, так как специфика реализации зависит от внутреннего устройства)
        result = await agent.execute_task(
            task_description="Проанализируй этот код на безопасность",
            context={
                "code": "def test(): pass",
                "language": "python"
            }
        )
        
        # Проверить результат
        assert "success" in result
```

## 7. Лучшие практики

### 7.1 Модульность и расширяемость

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

### 7.2 Обработка ошибок

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

### 7.3 Валидация входных данных

Обязательно валидируйте все входные данные:

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

## 8. Миграция

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
        result = await self.old_component.execute_task(task_description)
        
        # Адаптировать результат к новому формату
        if isinstance(result, str):
            return {"success": True, "result": result}
        elif isinstance(result, dict):
            return result
        else:
            return {"success": True, "result": str(result)}
```

Это полное руководство охватывает все аспекты Koru AI Agent Framework и предоставляет рекомендации по его использованию и адаптации под специфические задачи.