# Заключение: Полное руководство по Koru AI Agent Framework

Koru AI Agent Framework - это гибкая и расширяемая система для создания, управления и выполнения AI-агентов, способных решать сложные задачи через компонуемые паттерны мышления. В этом заключительном разделе представлен обзор всех аспектов фреймворка и рекомендации по его эффективному использованию.

## Обзор архитектуры

### 1. Чистая архитектура (Clean Architecture)

Фреймворк реализует принципы чистой архитектуры с направленными внутрь зависимостями:

```
┌─────────────────┐
│  Infrastructure │ ← Зависимости от Application
│        ▲        │
│        │        │
├─────────────────┤
│   Application   │ ← Зависимости от Domain
│        ▲        │
│        │        │
├─────────────────┤
│     Domain      │ ← Ядро системы, не зависит от внешних слоев
│                 │
└─────────────────┘
```

#### Ключевые принципы:
- **Зависимости направлены внутрь**: Внешние слои зависят от внутренних
- **Независимость от фреймворков**: Ядро не зависит от внешних библиотек
- **Тестируемость**: Бизнес-логика может быть протестирована без внешних зависимостей
- **Независимость от UI**: Интерфейс может быть изменен без влияния на бизнес-логику
- **Независимость от базы данных**: Бизнес-правила не зависят от конкретной СУБД

### 2. Основные компоненты системы

#### Агенты
- **Компонуемые агенты**: Основные исполнители логики
- **Явное состояние**: Отслеживание прогресса и ошибок
- **Адаптация к доменам**: Возможность адаптации под разные области задач

#### Паттерны мышления
- **Стратегии решения задач**: Различные подходы к решению
- **Компонуемость**: Возможность комбинирования паттернов
- **Расширяемость**: Легкое создание новых паттернов

#### Атомарные действия
- **Минимальные неделимые операции**: Базовые действия системы
- **Безопасность**: Валидация и контроль выполнения
- **Изоляция**: Ограничение воздействия на систему

#### Система промтов
- **Версионирование**: Управление версиями промтов
- **Категоризация**: Организация по доменам и ролям
- **Валидация**: Проверка безопасности и корректности
- **Кэширование**: Оптимизация доступа к промтам

## Ключевые возможности

### 1. Безопасность и контролируемость

Фреймворк обеспечивает безопасность через:

- **Валидацию решений**: Все решения, принятые LLM, строго валидируются
- **Контролируемое выполнение**: Действия выполняются кодом, а не напрямую LLM
- **Изоляцию выполнения**: Ограничение доступа к системным ресурсам
- **Проверку безопасности промтов**: Валидация промтов на наличие потенциально опасного содержимого
- **Контроль доступа**: Ограничение доступа к ресурсам на основе ролей

### 2. Расширяемость и адаптация

Фреймворк легко расширяется через:

- **Новые паттерны мышления**: Для новых стратегий решения задач
- **Новые атомарные действия**: Для новых возможностей взаимодействия
- **Новые домены**: Для новых областей применения
- **Новые промты**: Для новых специфичных инструкций
- **Новые инструменты и навыки**: Для интеграции с внешними системами

### 3. Производительность и масштабируемость

- **Асинхронность**: Все операции выполняются асинхронно
- **Кэширование**: Оптимизация повторных операций
- **Параллельное выполнение**: Поддержка параллельной обработки
- **Управление ресурсами**: Контроль использования памяти и CPU
- **Мониторинг**: Сбор метрик и статистики выполнения

## Практики разработки под свои задачи

### 1. Создание специфических агентов

Для адаптации под свои задачи создавайте специфические агенты:

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

### 2. Создание специфических паттернов

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
                "pattern_used": self.name
            }
```

### 3. Создание специфических инструментов

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

## Безопасность и надежность

### 1. Проверка безопасности

Фреймворк включает встроенные механизмы безопасности:

- **Валидация промтов**: Проверка на безопасность и корректность
- **Проверка параметров**: Контроль входных данных
- **Контроль доступа**: Ограничение доступа к ресурсам
- **Изоляция выполнения**: Предотвращение побочных эффектов
- **Обработка ошибок**: Надежная обработка исключений

### 2. Безопасность путей

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

## Тестирование и валидация

### 1. Модульное тестирование

Тестируйте каждый компонент отдельно:

```python
# test_custom_components.py
import pytest
from unittest.mock import AsyncMock

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
def login(username, password):
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

### 2. Интеграционное тестирование

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
        
        # Выполнить задачу
        result = await agent.execute_task(
            task_description="Тест интеграции",
            context={"test": "data"}
        )
        
        # Проверить результат
        assert "success" in result
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

## Миграция и обновление

### 1. Подход к миграции

Фреймворк поддерживает миграцию между версиями:

1. **Оценка изменений**: Определение, какие компоненты затронуты
2. **Тестирование**: Проверка изменений в изолированной среде
3. **Постепенное обновление**: Обновление компонентов по одному
4. **Валидация**: Проверка корректности работы после обновления

### 2. Адаптеры миграции

Для совместимости с предыдущими версиями используйте адаптеры:

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

### 2. Безопасность и валидация

Обязательно учитывайте безопасность при создании компонентов:

```python
def _validate_task_context(self, context: Dict[str, Any]) -> List[str]:
    """Проверить контекст задачи на безопасность"""
    errors = []
    
    # Проверить чувствительные поля
    sensitive_fields = ["password", "token", "api_key", "secret", "credentials"]
    for field in sensitive_fields:
        if field in context:
            errors.append(f"Чувствительное поле '{field}' обнаружено в контексте задачи")
    
    # Проверить размер контекста
    context_size = len(str(context))
    max_size = 10 * 1024 * 1024  # 10MB
    if context_size > max_size:
        errors.append(f"Контекст задачи слишком велик: {context_size} байт, максимум {max_size}")
    
    return errors
```

### 3. Обработка ошибок

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

## Интеграция с внешними системами

Фреймворк легко интегрируется с внешними системами:

- **API интеграции**: Подключение к внешним API
- **Базы данных**: Интеграция с различными СУБД
- **Файловые системы**: Безопасная работа с файлами
- **Системы мониторинга**: Интеграция с системами логирования и мониторинга
- **Системы управления задачами**: Интеграция с очередями задач

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

Спасибо за использование Koru AI Agent Framework!

</final_file_content>

IMPORTANT: For any future changes to this file, use the final_file_content shown above as your reference. This content reflects the current state of the file, including any auto-formatting (e.g., if you used single quotes but the formatter converted them to double quotes). Always base your SEARCH/REPLACE operations on this final version to ensure accuracy.