# Лучшие практики Koru AI Agent Framework

В этом разделе описаны рекомендации и лучшие практики по использованию Koru AI Agent Framework. Эти практики помогут вам эффективно разрабатывать, настраивать и использовать фреймворк для решения ваших задач.

## Архитектурные практики

### 1. Чистая архитектура

Следуйте принципам чистой архитектуры:

#### Зависимости направлены внутрь

- Внешние слои зависят от внутренних, а не наоборот
- Ядро системы не зависит от конкретных фреймворков или внешних библиотек
- Внешние зависимости инжектируются через интерфейсы

```python
# Правильно: зависимости направлены внутрь
from domain.abstractions.event_types import IEventPublisher

class AgentService:
    def __init__(self, event_publisher: IEventPublisher):
        self.event_publisher = event_publisher  # Зависит от абстракции

# Неправильно: жесткая зависимость от реализации
class AgentService:
    def __init__(self):
        self.event_publisher = ConcreteEventPublisher()  # Зависит от реализации
```

#### Слабая связанность

- Используйте интерфейсы и абстракции
- Избегайте жестких зависимостей между компонентами
- Применяйте принцип инверсии зависимостей

```python
# Хорошо: слабая связанность через интерфейсы
class Agent:
    def __init__(self, action_executor: IAtomicActionExecutor):
        self.action_executor = action_executor

# Плохо: жесткая связанность
class Agent:
    def __init__(self):
        self.action_executor = SpecificActionExecutor()  # Жесткая связь
```

### 2. Модульность и расширяемость

Создавайте модульные и расширяемые компоненты:

#### Открытость/закрытость

- Компоненты должны быть открыты для расширения, но закрыты для модификации
- Используйте наследование или композицию для расширения функциональности

```python
# Хорошо: открыт для расширения
class BasePattern(IThinkingPattern):
    async def execute(self, state, context, capabilities):
        # Базовая логика
        pass

class SecurityAnalysisPattern(BasePattern):
    # Расширение базовой функциональности
    pass

# Плохо: трудно расширять
class MonolithicPattern:
    def execute(self, task_type, state, context):
        if task_type == "security":
            # Логика безопасности
            pass
        elif task_type == "code_analysis":
            # Логика анализа кода
            pass
        # и т.д. - трудно расширять
```

#### Единая ответственность

- Каждый класс должен иметь одну причину для изменения
- Разделяйте обязанности между классами

```python
# Хорошо: каждый класс отвечает за свою область
class PromptValidator:
    """Отвечает только за валидацию промтов"""
    pass

class PromptRenderer:
    """Отвечает только за рендеринг промтов"""
    pass

class PromptLoader:
    """Отвечает только за загрузку промтов"""
    pass

# Плохо: монолитный класс
class PromptManager:
    """Отвечает за валидацию, рендеринг, загрузку и т.д."""
    pass
```

## Практики безопасности

### 1. Валидация входных данных

Обязательно валидируйте все входные данные:

```python
def validate_prompt_parameters(self, parameters: Dict[str, Any]) -> bool:
    """Проверить параметры промта на безопасность"""
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
    
    # Проверить пути к файлам на безопасность
    if "path" in parameters:
        if not self._is_safe_path(parameters["path"]):
            errors.append("Небезопасный путь к файлу")
    
    return len(errors) == 0

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
```

### 3. Обработка чувствительных данных

Фильтруйте и защищайте чувствительные данные:

```python
def filter_sensitive_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
    """Отфильтровать чувствительные данные"""
    if not data:
        return data
    
    filtered_data = data.copy()
    
    sensitive_fields = [
        "password", "token", "api_key", "secret", "credentials",
        "private_key", "certificate", "oauth_token", "email", "phone"
    ]
    
    for field in sensitive_fields:
        if field in filtered_data:
            filtered_data[field] = "***FILTERED***"
    
    return filtered_data
```

## Практики производительности

### 1. Асинхронность

Используйте асинхронные операции для повышения производительности:

```python
# Хорошо: асинхронные операции
async def execute_multiple_tasks(tasks: List[Task]) -> List[Result]:
    """Выполнить несколько задач параллельно"""
    results = await asyncio.gather(*[
        task.execute() for task in tasks
    ])
    return results

# Плохо: синхронное выполнение
def execute_multiple_tasks(tasks: List[Task]) -> List[Result]:
    """Выполнить несколько задач последовательно"""
    results = []
    for task in tasks:
        results.append(task.execute())  # Блокирует выполнение
    return results
```

### 2. Кэширование

Используйте кэширование для улучшения производительности:

```python
import functools
import time

class CacheManager:
    """Менеджер кэширования"""
    
    def __init__(self, ttl: int = 3600):  # 1 час по умолчанию
        self.ttl = ttl
        self.cache = {}
    
    def get(self, key: str):
        """Получить значение из кэша"""
        if key in self.cache:
            cached_value, timestamp = self.cache[key]
            if time.time() - timestamp < self.ttl:
                return cached_value
            else:
                del self.cache[key]  # Удалить устаревшее значение
        return None
    
    def set(self, key: str, value):
        """Установить значение в кэш"""
        self.cache[key] = (value, time.time())
    
    def invalidate(self, key: str):
        """Инвалидировать кэш для ключа"""
        if key in self.cache:
            del self.cache[key]

# Использование декоратора для кэширования
def cached_method(ttl: int = 3600):
    def decorator(func):
        cache = {}
        
        async def wrapper(*args, **kwargs):
            # Создать ключ кэша на основе аргументов
            cache_key = str(args) + str(sorted(kwargs.items()))
            
            if cache_key in cache:
                cached_result, timestamp = cache[cache_key]
                if time.time() - timestamp < ttl:
                    return cached_result
                else:
                    del cache[cache_key]
            
            # Выполнить функцию и закэшировать результат
            result = await func(*args, **kwargs)
            cache[cache_key] = (result, time.time())
            
            return result
        
        return wrapper
    return decorator
```

### 3. Управление ресурсами

Контролируйте использование ресурсов:

```python
class ResourceManager:
    """Менеджер ресурсов"""
    
    def __init__(self, max_memory: str = "1GB", max_cpu: float = 80.0):
        self.max_memory = self._parse_memory_size(max_memory)
        self.max_cpu = max_cpu
        self.current_usage = {"memory": 0, "cpu": 0}
    
    def check_resource_availability(self, required_resources: Dict[str, Any]) -> bool:
        """Проверить доступность ресурсов"""
        current_memory = self._get_current_memory_usage()
        requested_memory = required_resources.get("memory", 0)
        
        if (current_memory + requested_memory) > self.max_memory:
            return False
        
        current_cpu = self._get_current_cpu_usage()
        requested_cpu = required_resources.get("cpu", 0)
        
        if (current_cpu + requested_cpu) > self.max_cpu:
            return False
        
        return True
    
    def _parse_memory_size(self, memory_str: str) -> int:
        """Разобрать строку размера памяти в байты"""
        units = {"B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3, "TB": 1024**4}
        
        for unit, multiplier in units.items():
            if memory_str.upper().endswith(unit):
                number = float(memory_str[:-len(unit)])
                return int(number * multiplier)
        
        # Если единица измерения не указана, предполагаем байты
        return int(memory_str)
```

## Практики тестирования

### 1. Модульное тестирование

Тестируйте каждый компонент отдельно:

```python
# test_agent_service.py
import pytest
from unittest.mock import AsyncMock, Mock
from domain.models.agent.agent_state import AgentState

class TestAgentService:
    @pytest.mark.asyncio
    async def test_agent_execution_success(self):
        """Тест успешного выполнения задачи агентом"""
        # Создать моки зависимостей
        mock_event_publisher = AsyncMock()
        mock_action_executor = AsyncMock()
        mock_pattern_executor = AsyncMock()
        
        # Создать сервис
        agent_service = AgentService(
            event_publisher=mock_event_publisher,
            action_executor=mock_action_executor,
            pattern_executor=mock_pattern_executor
        )
        
        # Настроить возвращаемые значения
        mock_pattern_executor.execute_pattern.return_value = {
            "success": True,
            "result": "Test result"
        }
        
        # Выполнить задачу
        result = await agent_service.execute_task(
            task_description="Test task",
            context={"test": "data"}
        )
        
        # Проверить результат
        assert result["success"] is True
        assert result["result"] == "Test result"
        
        # Проверить, что были вызваны зависимости
        mock_event_publisher.publish.assert_called_once()
        mock_pattern_executor.execute_pattern.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_agent_execution_with_error(self):
        """Тест выполнения задачи с ошибкой"""
        # Создать моки зависимостей
        mock_event_publisher = AsyncMock()
        mock_action_executor = AsyncMock()
        mock_pattern_executor = AsyncMock()
        
        # Настроить выброс исключения
        mock_pattern_executor.execute_pattern.side_effect = Exception("Test error")
        
        # Создать сервис
        agent_service = AgentService(
            event_publisher=mock_event_publisher,
            action_executor=mock_action_executor,
            pattern_executor=mock_pattern_executor
        )
        
        # Выполнить задачу - должна возникнуть ошибка
        result = await agent_service.execute_task(
            task_description="Test task with error",
            context={}
        )
        
        # Проверить, что результат содержит ошибку
        assert result["success"] is False
        assert "Test error" in result["error"]
```

### 2. Интеграционное тестирование

Тестируйте взаимодействие между компонентами:

```python
# test_integration.py
import pytest
from application.factories.agent_factory import AgentFactory
from domain.value_objects.domain_type import DomainType

class TestAgentIntegration:
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
        
        # Выполнить задачу с использованием промта
        result = await agent.execute_task(
            task_description="Проанализируй этот Python код",
            context={
                "code": "def hello(): pass",
                "language": "python"
            }
        )
        
        # Проверить результат
        assert "success" in result
        # В зависимости от реализации, проверить другие поля результата
```

## Практики документирования

### 1. Документирование компонентов

Документируйте все компоненты системы:

```python
class SecurityAnalysisPattern(IThinkingPattern):
    """
    Паттерн анализа безопасности кода.
    
    Этот паттерн реализует стратегию анализа кода на наличие
    уязвимостей безопасности. Поддерживает анализ различных
    языков программирования и проверку на соответствие
    стандартам безопасности.
    
    Примеры проверок:
    - SQL-инъекции
    - XSS-уязвимости
    - Небезопасное хранение данных
    - Проблемы с аутентификацией
    """
    
    @property
    def name(self) -> str:
        """Уникальное имя паттерна анализа безопасности."""
        return "security_analysis_pattern"
    
    async def execute(
        self,
        state: AgentState,
        context: Any,
        available_capabilities: List[str]
    ) -> Dict[str, Any]:
        """
        Выполнить анализ безопасности кода.
        
        Args:
            state: Текущее состояние агента
            context: Контекст выполнения (обычно содержит код для анализа)
            available_capabilities: Доступные возможности агента
            
        Returns:
            Словарь с результатами анализа, содержащий:
            - success: флаг успешности выполнения
            - findings: список обнаруженных уязвимостей
            - summary: краткое резюме анализа
        """
        pass
```

### 2. Примеры использования

Предоставляйте примеры использования для каждого компонента:

```python
# examples/security_analysis_example.py
"""
Пример использования паттерна анализа безопасности.

Этот пример демонстрирует, как использовать паттерн анализа безопасности
для проверки Python-кода на наличие уязвимостей.
"""

from application.factories.agent_factory import AgentFactory
from domain.value_objects.domain_type import DomainType

async def security_analysis_example():
    """
    Пример анализа безопасности кода.
    
    Создает агента для анализа безопасности и выполняет
    проверку фрагмента кода на наличие уязвимостей.
    """
    
    # Создать агента для анализа кода
    agent = await AgentFactory().create_agent(
        agent_type="composable",
        domain=DomainType.CODE_ANALYSIS
    )
    
    # Определить код для анализа
    vulnerable_code = """
def login(username, password):
    query = f"SELECT * FROM users WHERE username='{username}' AND password='{password}'"
    return execute_query(query)
"""
    
    # Выполнить анализ безопасности
    result = await agent.execute_task(
        task_description="Проанализируй этот код на наличие уязвимостей безопасности",
        context={
            "code": vulnerable_code,
            "language": "python",
            "analysis_type": "security"
        }
    )
    
    print("Результаты анализа безопасности:")
    if result.get("success"):
        findings = result.get("findings", [])
        for finding in findings:
            print(f"- {finding['type']}: {finding['description']}")
    else:
        print(f"Ошибка при анализе: {result.get('error')}")
    
    return result

if __name__ == "__main__":
    import asyncio
    asyncio.run(security_analysis_example())
```

## Практики мониторинга и логирования

### 1. Структурированное логирование

Используйте структурированное логирование:

```python
import logging
import json
from datetime import datetime

class StructuredLogger:
    """Структурированный логгер"""
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)
    
    def log_event(self, event_type: str, data: dict, level: str = "INFO"):
        """Залогировать событие в структурированном формате"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "event_type": event_type,
            "level": level,
            "data": data
        }
        
        log_message = json.dumps(log_entry, ensure_ascii=False)
        
        if level == "ERROR":
            self.logger.error(log_message)
        elif level == "WARNING":
            self.logger.warning(log_message)
        elif level == "DEBUG":
            self.logger.debug(log_message)
        else:
            self.logger.info(log_message)

# Использование в компонентах
class AgentService:
    def __init__(self):
        self.logger = StructuredLogger(self.__class__.__name__)
    
    async def execute_task(self, task_description: str, context: dict):
        """Выполнить задачу с логированием"""
        self.logger.log_event("task_started", {
            "task_description": task_description[:50],  # Первые 50 символов
            "context_keys": list(context.keys()) if context else []
        })
        
        try:
            # Выполнить задачу
            result = await self._execute_task_logic(task_description, context)
            
            self.logger.log_event("task_completed", {
                "task_description": task_description[:50],
                "success": True,
                "result_keys": list(result.keys()) if result else []
            })
            
            return result
        except Exception as e:
            self.logger.log_event("task_failed", {
                "task_description": task_description[:50],
                "error": str(e),
                "error_type": type(e).__name__
            }, level="ERROR")
            
            raise
```

### 2. Метрики и мониторинг

Собирайте метрики для мониторинга:

```python
class MetricsCollector:
    """Сборщик метрик"""
    
    def __init__(self):
        self.metrics = {
            "tasks_completed": 0,
            "tasks_failed": 0,
            "average_execution_time": 0,
            "total_execution_time": 0,
            "error_rate": 0
        }
        self.execution_times = []
    
    def record_task_completion(self, execution_time: float):
        """Записать завершение задачи"""
        self.metrics["tasks_completed"] += 1
        self.execution_times.append(execution_time)
        self.metrics["total_execution_time"] += execution_time
        
        if self.metrics["tasks_completed"] > 0:
            self.metrics["average_execution_time"] = (
                self.metrics["total_execution_time"] / self.metrics["tasks_completed"]
            )
    
    def record_task_failure(self):
        """Записать провал задачи"""
        self.metrics["tasks_failed"] += 1
        self.metrics["error_rate"] = (
            self.metrics["tasks_failed"] / 
            max(1, self.metrics["tasks_completed"] + self.metrics["tasks_failed"])
        )
    
    def get_current_metrics(self) -> Dict[str, Any]:
        """Получить текущие метрики"""
        current_metrics = self.metrics.copy()
        current_metrics["execution_times"] = self.execution_times.copy()
        current_metrics["current_error_rate"] = self.metrics["error_rate"]
        
        return current_metrics
```

## Практики разработки под свои задачи

### 1. Планирование адаптации

Перед адаптацией фреймворка под свои задачи:

1. **Анализ требований**: Определите, какие функции вам необходимы
2. **Оценка существующих компонентов**: Проверьте, можно ли использовать существующие компоненты
3. **Определение расширений**: Определите, какие компоненты нужно расширить или создать
4. **Планирование архитектуры**: Спроектируйте, как новые компоненты будут интегрироваться

### 2. Создание специфических компонентов

При создании специфических компонентов:

- Следуйте существующим интерфейсам и абстракциям
- Обеспечьте совместимость с системой событий
- Реализуйте надлежащую валидацию и безопасность
- Документируйте новые компоненты
- Пишите тесты для новых компонентов

### 3. Интеграция с существующей системой

При интеграции новых компонентов:

- Используйте фабрики для создания компонентов
- Регистрируйте компоненты в соответствующих реестрах
- Обеспечьте корректное управление жизненным циклом
- Интегрируйте с системой событий и логирования

### 4. Обработка ошибок

Обеспечьте надежную обработку ошибок:

```python
async def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
    """Выполнить компонент с надежной обработкой ошибок"""
    try:
        # Проверить ограничения
        if self.state.error_count > self.max_error_threshold:
            return {
                "success": False,
                "error": "Превышено максимальное количество ошибок",
                "needs_reset": True
            }
        
        # Выполнить основную логику
        result = await self._execute_extended_logic(parameters)
        
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

Эти лучшие практики помогут вам эффективно использовать Koru AI Agent Framework и адаптировать его под ваши специфические задачи, обеспечивая надежность, безопасность и производительность системы.