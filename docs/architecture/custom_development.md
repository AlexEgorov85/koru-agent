# Разработка архитектуры под свои задачи

В этом разделе описаны рекомендации и практики по адаптации и расширению архитектуры Koru AI Agent Framework для удовлетворения специфических требований и задач. Вы узнаете, как модифицировать существующую архитектуру и создавать новые компоненты для расширения функциональности системы.

## Архитектурные принципы

### 1. Чистая архитектура (Clean Architecture)

Koru AI Agent Framework реализует принципы чистой архитектуры:

- **Зависимости направлены внутрь**: Внешние слои зависят от внутренних, а не наоборот
- **Независимость от фреймворков**: Ядро системы не зависит от конкретных фреймворков
- **Тестируемость**: Бизнес-логика может быть протестирована без внешних зависимостей
- **Независимость от UI**: UI может быть изменен без влияния на бизнес-логику
- **Независимость от базы данных**: Бизнес-правила не зависят от конкретной СУБД

### 2. Слои архитектуры

#### Слой домена (Domain Layer)

Слой домена содержит бизнес-логику и правила:

```python
# domain/models/agent_state.py
from pydantic import BaseModel, field_validator
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

# domain/abstractions/thinking_pattern.py
from abc import ABC, abstractmethod
from typing import Any, List, Dict
from domain.models.agent.agent_state import AgentState

class IThinkingPattern(ABC):
    """Интерфейс для компонуемых паттернов мышления."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Уникальное имя паттерна мышления."""
        pass
    
    @abstractmethod
    async def execute(
        self,
        state: AgentState,
        context: Any,
        available_capabilities: List[str]
    ) -> Dict[str, Any]:
        """Выполнить паттерн мышления."""
        pass
    
    @abstractmethod
    async def adapt_to_task(self, task_description: str) -> Dict[str, Any]:
        """Адаптировать паттерн к задаче (выбор домена, настройка параметров)."""
        pass
```

#### Слой приложений (Application Layer)

Слой приложений координирует работу компонентов домена:

```python
# application/services/prompt_loader.py
import os
import yaml
import re
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from domain.models.prompt.prompt_version import PromptVersion, PromptStatus, PromptRole
from domain.value_objects.domain_type import DomainType
from domain.value_objects.provider_type import LLMProviderType
from domain.models.prompt.prompt_version import VariableSchema
import logging

class PromptLoadingError(Exception):
    """Исключение для ошибок загрузки промтов"""
    pass

class PromptLoader:
    """
    Загрузчик промтов из файловой системы.
    
    Поддерживает структуру:
    prompts/
    ├── {domain}/
    │   └── {capability}/
    │       ├── {role}/
    │       │   └── v{version}.md
    │       └── _index.yaml
    """
    
    def __init__(self, base_path: str = "prompts"):
        self.base_path = Path(base_path)
        self.logger = logging.getLogger(__name__)
        
    def load_all_prompts(self) -> Tuple[List[PromptVersion], List[str]]:
        """
        Загружает все промты из файловой системы.
        Поддерживает структуру: prompts/{domain}/{capability}/{role}/v{version}.md
        
        Returns:
            Tuple[List[PromptVersion], List[str]]: Кортеж из списка загруженных промтов и списка ошибок
        """
        if not self.base_path.exists():
            return [], [f"Директория {self.base_path} не существует"]
            
        prompt_versions = []
        errors = []
        
        # Рекурсивно пройтись по всем поддиректориям
        for domain_dir in self.base_path.iterdir():
            if not domain_dir.is_dir():
                continue
                
            for capability_dir in domain_dir.iterdir():
                if not capability_dir.is_dir():
                    continue
                    
                # Проверим, есть ли подкаталоги ролей (system, user, assistant, tool)
                role_dirs = [
                    subdir for subdir in capability_dir.iterdir() 
                    if subdir.is_dir() and subdir.name in ["system", "user", "assistant", "tool"]
                ]
                
                if role_dirs:
                    # Новая структура: capability_dir содержит подкаталоги ролей
                    for role_dir in role_dirs:
                        # Загрузить все версии из этого подкаталога роли
                        versions, version_errors = self._load_capability_versions_from_role_dir(
                            domain_dir.name, capability_dir.name, role_dir
                        )
                        prompt_versions.extend(versions)
                        errors.extend(version_errors)
                else:
                    # Старая структура: все файлы версий находятся прямо в capability_dir
                    versions, version_errors = self._load_capability_versions_from_dir(
                        domain_dir.name, capability_dir
                    )
                    prompt_versions.extend(versions)
                    errors.extend(version_errors)
                
        return prompt_versions, errors
    
    def _load_capability_versions_from_role_dir(
        self, 
        domain: str, 
        capability: str, 
        role_dir: Path
    ) -> Tuple[List[PromptVersion], List[str]]:
        """Загружает все версии для одной capability из подкаталога роли"""
        versions = []
        errors = []
        
        for file_path in role_dir.glob("v*.md"):
            try:
                version = self._load_prompt_version(domain, capability, role_dir.name, file_path)
                if version:
                    versions.append(version)
            except Exception as e:
                errors.append(f"Ошибка загрузки промта из {file_path}: {str(e)}")
                
        return versions, errors
    
    def _load_capability_versions_from_dir(
        self, 
        domain: str, 
        capability_dir: Path
    ) -> Tuple[List[PromptVersion], List[str]]:
        """Загружает все версии для одной capability из директории"""
        # Извлекаем capability_name из имени директории
        capability = capability_dir.name
        versions = []
        errors = []
        
        for file_path in capability_dir.glob("v*.md"):
            try:
                version = self._load_prompt_version_from_legacy_path(domain, capability, file_path)
                if version:
                    versions.append(version)
            except Exception as e:
                errors.append(f"Ошибка загрузки промта из {file_path}: {str(e)}")
                
        return versions, errors
```

#### Слой инфраструктуры (Infrastructure Layer)

Слой инфраструктуры реализует внешние зависимости:

```python
# infrastructure/tools/file_reader_tool.py
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from pathlib import Path
import os

class ITool(ABC):
    """Интерфейс инструмента"""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Имя инструмента"""
        pass
    
    @abstractmethod
    async def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Выполнить инструмент с указанными параметрами"""
        pass
    
    @abstractmethod
    def validate_parameters(self, parameters: Dict[str, Any]) -> bool:
        """Проверить корректность параметров"""
        pass

class FileReaderTool(ITool):
    """Инструмент для чтения файлов"""
    
    def __init__(self, max_file_size: int = 10 * 1024 * 1024):  # 10MB
        self.max_file_size = max_file_size
        self._name = "file_reader"
    
    @property
    def name(self) -> str:
        return self._name
    
    async def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Выполнить чтение файла"""
        if not self.validate_parameters(parameters):
            return {
                "success": False,
                "error": "Некорректные параметры"
            }
        
        file_path = parameters["path"]
        encoding = parameters.get("encoding", "utf-8")
        
        try:
            # Проверка безопасности пути
            if not self._is_safe_path(file_path):
                return {
                    "success": False,
                    "error": "Небезопасный путь к файлу"
                }
            
            path = Path(file_path)
            
            # Проверка существования файла
            if not path.exists():
                return {
                    "success": False,
                    "error": f"Файл не найден: {file_path}"
                }
            
            # Проверка размера файла
            file_size = path.stat().st_size
            if file_size > self.max_file_size:
                return {
                    "success": False,
                    "error": f"Файл слишком большой: {file_size} байт, максимум {self.max_file_size}"
                }
            
            # Чтение файла
            with open(path, 'r', encoding=encoding) as file:
                content = file.read()
            
            return {
                "success": True,
                "content": content,
                "size": file_size,
                "encoding": encoding
            }
        except UnicodeDecodeError:
            return {
                "success": False,
                "error": f"Не удалось декодировать файл с кодировкой {encoding}"
            }
        except PermissionError:
            return {
                "success": False,
                "error": f"Нет доступа к файлу: {file_path}"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Ошибка при чтении файла: {str(e)}"
            }
    
    def validate_parameters(self, parameters: Dict[str, Any]) -> bool:
        """Проверить параметры"""
        if "path" not in parameters:
            return False
        
        path = parameters["path"]
        if not isinstance(path, str) or not path.strip():
            return False
        
        return True
    
    def _is_safe_path(self, path: str) -> bool:
        """Проверить, является ли путь безопасным для чтения"""
        try:
            # Преобразовать в абсолютный путь
            abs_path = Path(path).resolve()
            
            # Получить корневой каталог (где запущен фреймворк)
            root_path = Path.cwd().resolve()
            
            # Проверить, что путь находится внутри корневого каталога
            abs_path.relative_to(root_path)
            return True
        except ValueError:
            # Если путь вне корневого каталога, он небезопасен
            return False
```

## Расширение архитектуры

### 1. Создание специфических слоев

Для адаптации архитектуры под специфические задачи:

#### Специфический слой домена

```python
# domain/models/specialized_task.py
from pydantic import BaseModel
from typing import List, Dict, Any
from enum import Enum

class TaskPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class SpecializedTask(BaseModel):
    """Специфическая задача с расширенными атрибутами"""
    id: str
    description: str
    domain: str
    priority: TaskPriority = TaskPriority.MEDIUM
    dependencies: List[str] = []
    resources_needed: Dict[str, Any] = {}
    timeout: int = 300  # seconds
    retry_count: int = 3
    metadata: Dict[str, Any] = {}

# domain/abstractions/specialized_pattern.py
from abc import ABC, abstractmethod
from typing import Any, Dict
from domain.abstractions.thinking_pattern import IThinkingPattern
from domain.models.specialized_task import SpecializedTask

class ISpecializedPattern(IThinkingPattern):
    """Интерфейс для специфических паттернов мышления"""
    
    @abstractmethod
    async def execute_specialized(
        self,
        task: SpecializedTask,
        context: Any
    ) -> Dict[str, Any]:
        """Выполнить специфический паттерн с расширенной логикой"""
        pass
    
    @abstractmethod
    def can_handle_task(self, task: SpecializedTask) -> bool:
        """Проверить, может ли паттерн обработать задачу"""
        pass
```

#### Специфический слой приложений

```python
# application/services/specialized_task_service.py
from typing import List, Dict, Any
from domain.models.specialized_task import SpecializedTask, TaskPriority
from domain.abstractions.specialized_pattern import ISpecializedPattern

class SpecializedTaskService:
    """Сервис для работы со специфическими задачами"""
    
    def __init__(self, patterns: List[ISpecializedPattern]):
        self.patterns = patterns
        self.task_queue = []
        self.completed_tasks = []
        self.failed_tasks = []
    
    async def execute_task(self, task: SpecializedTask) -> Dict[str, Any]:
        """Выполнить специфическую задачу"""
        
        # Найти подходящий паттерн
        pattern = self._find_pattern_for_task(task)
        
        if not pattern:
            return {
                "success": False,
                "error": f"Не найден подходящий паттерн для задачи {task.id}"
            }
        
        try:
            # Выполнить задачу с помощью паттерна
            result = await pattern.execute_specialized(task, {})
            
            # Обновить статус задачи
            self.completed_tasks.append(task.id)
            
            return {
                "success": True,
                "result": result,
                "task_id": task.id
            }
        except Exception as e:
            self.failed_tasks.append(task.id)
            
            return {
                "success": False,
                "error": f"Ошибка при выполнении задачи {str(e)}",
                "task_id": task.id
            }
    
    def _find_pattern_for_task(self, task: SpecializedTask) -> ISpecializedPattern:
        """Найти подходящий паттерн для задачи"""
        for pattern in self.patterns:
            if pattern.can_handle_task(task):
                return pattern
        
        return None
    
    def prioritize_tasks(self) -> List[SpecializedTask]:
        """Приоритизировать задачи"""
        # Сортировать задачи по приоритету
        priority_order = {
            TaskPriority.CRITICAL: 0,
            TaskPriority.HIGH: 1,
            TaskPriority.MEDIUM: 2,
            TaskPriority.LOW: 3
        }
        
        return sorted(
            self.task_queue,
            key=lambda t: priority_order[t.priority]
        )
    
    def add_task(self, task: SpecializedTask):
        """Добавить задачу в очередь"""
        self.task_queue.append(task)
```

#### Специфический слой инфраструктуры

```python
# infrastructure/adapters/specialized_event_publisher.py
from typing import Any, Dict
from domain.abstractions.event_system import IEventPublisher
from infrastructure.gateways.event_bus_adapter import EventBusAdapter

class SpecializedEventPublisher(IEventPublisher):
    """Специфический публикатор событий с дополнительными возможностями"""
    
    def __init__(self, event_bus: EventBusAdapter, config: Dict[str, Any] = None):
        self.event_bus = event_bus
        self.config = config or {}
        self._filters = []
        self._processors = []
        self._rate_limiter = self._setup_rate_limiter()
        
        # Инициализировать фильтры и процессоры
        self._initialize_components()
    
    def _initialize_components(self):
        """Инициализировать компоненты публикатора"""
        # Добавить фильтры
        if self.config.get("filter_sensitive_data", True):
            self._filters.append(self._filter_sensitive_data)
        
        # Добавить процессоры
        if self.config.get("enable_monitoring", True):
            self._processors.append(self._monitor_event)
    
    async def publish(self, event_type: str, data: Dict[str, Any]):
        """Расширенная публикация события с фильтрацией и обработкой"""
        
        # Проверить ограничение частоты
        if not await self._rate_limiter.allow_request():
            return  # Отбросить событие из-за превышения лимита
        
        # Применить фильтры
        filtered_data = data.copy()
        for filter_func in self._filters:
            filtered_data = filter_func(event_type, filtered_data)
            if filtered_data is None:
                return  # Событие отфильтровано
        
        # Применить процессоры
        processed_data = filtered_data.copy()
        for processor_func in self._processors:
            processed_data = await processor_func(event_type, processed_data)
        
        # Опубликовать событие
        await self.event_bus.publish(event_type, processed_data)
    
    def _filter_sensitive_data(self, event_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Фильтровать чувствительные данные из события"""
        if not data:
            return data
        
        filtered_data = data.copy()
        
        # Удалить чувствительные поля
        sensitive_fields = ["password", "token", "api_key", "secret", "credentials"]
        for field in sensitive_fields:
            if field in filtered_data:
                filtered_data[field] = "***FILTERED***"
        
        return filtered_data
    
    async def _monitor_event(self, event_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Отслеживать событие для мониторинга"""
        # В реальной реализации здесь будет отправка данных
        # в систему мониторинга (Prometheus, Grafana и т.д.)
        pass
    
    def _setup_rate_limiter(self):
        """Настроить ограничение частоты"""
        # В реальной реализации здесь будет создание rate limiter
        # например, с использованием алгоритма token bucket
        return RateLimiter(
            requests_per_second=self.config.get("max_requests_per_second", 100),
            burst_capacity=self.config.get("burst_capacity", 200)
        )
    
    def add_filter(self, filter_func):
        """Добавить фильтр"""
        self._filters.append(filter_func)
    
    def add_processor(self, processor_func):
        """Добавить процессор"""
        self._processors.append(processor_func)

class RateLimiter:
    """Простой rate limiter"""
    
    def __init__(self, requests_per_second: int, burst_capacity: int):
        self.requests_per_second = requests_per_second
        self.burst_capacity = burst_capacity
        self.available_tokens = burst_capacity
        self.last_refill_time = time.time()
    
    async def allow_request(self) -> bool:
        """Проверить, разрешен ли запрос"""
        current_time = time.time()
        time_passed = current_time - self.last_refill_time
        
        # Обновить токены
        tokens_to_add = time_passed * self.requests_per_second
        self.available_tokens = min(
            self.burst_capacity,
            self.available_tokens + tokens_to_add
        )
        self.last_refill_time = current_time
        
        if self.available_tokens >= 1:
            self.available_tokens -= 1
            return True
        else:
            return False
```

### 2. Создание специфических фабрик

Фабрики для создания специфических компонентов:

```python
# application/factories/specialized_factory.py
from typing import Dict, Any, Type
from domain.abstractions.thinking_pattern import IThinkingPattern
from domain.abstractions.event_system import IEventPublisher
from infrastructure.gateways.event_bus_adapter import EventBusAdapter

class SpecializedFactory:
    """Фабрика для создания специфических компонентов"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self._pattern_registry = {}
        self._publisher_registry = {}
        self._adapter_registry = {}
    
    def register_pattern_type(self, name: str, pattern_class: Type[IThinkingPattern]):
        """Зарегистрировать тип паттерна"""
        self._pattern_registry[name] = pattern_class
    
    def register_publisher_type(self, name: str, publisher_class: Type[IEventPublisher]):
        """Зарегистрировать тип публикатора"""
        self._publisher_registry[name] = publisher_class
    
    def create_pattern(self, pattern_type: str, **kwargs) -> IThinkingPattern:
        """Создать паттерн"""
        if pattern_type not in self._pattern_registry:
            raise ValueError(f"Тип паттерна '{pattern_type}' не зарегистрирован")
        
        pattern_class = self._pattern_registry[pattern_type]
        config = {**self.config.get("pattern_defaults", {}), **kwargs}
        
        return pattern_class(**config)
    
    def create_event_publisher(self, publisher_type: str, **kwargs) -> IEventPublisher:
        """Создать публикатор событий"""
        if publisher_type not in self._publisher_registry:
            raise ValueError(f"Тип публикатора '{publisher_type}' не зарегистрирован")
        
        publisher_class = self._publisher_registry[publisher_type]
        config = {**self.config.get("publisher_defaults", {}), **kwargs}
        
        if publisher_type == "specialized":
            event_bus = EventBusAdapter()
            return publisher_class(event_bus, config)
        else:
            return publisher_class(**config)
    
    def create_component(self, component_type: str, **kwargs):
        """Создать обобщенный компонент"""
        # Реализация создания компонентов на основе типа
        pass
```

## Интеграция специфических компонентов

### 1. Интеграция с существующими слоями

Специфические компоненты интегрируются с существующими слоями:

```python
# application/orchestration/specialized_orchestrator.py
from typing import List, Dict, Any
from application.services.specialized_task_service import SpecializedTaskService
from domain.models.specialized_task import SpecializedTask
from domain.abstractions.specialized_pattern import ISpecializedPattern

class SpecializedOrchestrator:
    """Оркестратор для специфических задач"""
    
    def __init__(
        self,
        task_service: SpecializedTaskService,
        patterns: List[ISpecializedPattern]
    ):
        self.task_service = task_service
        self.patterns = patterns
        self.active_sessions = {}
        self.resource_manager = ResourceManager()
    
    async def execute_session(self, session_id: str, tasks: List[SpecializedTask]) -> Dict[str, Any]:
        """Выполнить сессию со специфическими задачами"""
        
        # Инициализировать сессию
        self.active_sessions[session_id] = {
            "tasks": tasks,
            "status": "running",
            "start_time": time.time()
        }
        
        results = []
        
        try:
            # Приоритизировать задачи
            prioritized_tasks = self.task_service.prioritize_tasks()
            
            # Выполнить задачи по очереди
            for task in prioritized_tasks:
                # Проверить доступность ресурсов
                if not await self.resource_manager.check_resources(task.resources_needed):
                    results.append({
                        "task_id": task.id,
                        "success": False,
                        "error": "Недостаточно ресурсов для выполнения задачи"
                    })
                    continue
                
                # Выполнить задачу
                result = await self.task_service.execute_task(task)
                results.append(result)
                
                # Обновить использование ресурсов
                await self.resource_manager.update_usage(task.resources_needed)
        
        except Exception as e:
            return {
                "success": False,
                "error": f"Ошибка при выполнении сессии: {str(e)}",
                "session_id": session_id
            }
        finally:
            # Завершить сессию
            session_info = self.active_sessions[session_id]
            session_info["status"] = "completed"
            session_info["end_time"] = time.time()
            session_info["duration"] = session_info["end_time"] - session_info["start_time"]
            session_info["results"] = results
        
        return {
            "success": True,
            "session_id": session_id,
            "results": results,
            "summary": self._generate_session_summary(results)
        }
    
    def _generate_session_summary(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Сгенерировать сводку по сессии"""
        total_tasks = len(results)
        successful_tasks = len([r for r in results if r.get("success", False)])
        failed_tasks = total_tasks - successful_tasks
        
        return {
            "total_tasks": total_tasks,
            "successful_tasks": successful_tasks,
            "failed_tasks": failed_tasks,
            "success_rate": successful_tasks / total_tasks if total_tasks > 0 else 0
        }

class ResourceManager:
    """Менеджер ресурсов для оркестратора"""
    
    def __init__(self):
        self.available_resources = {}
        self.used_resources = {}
        self.resource_limits = {}
    
    async def check_resources(self, required_resources: Dict[str, Any]) -> bool:
        """Проверить доступность ресурсов"""
        for resource, amount in required_resources.items():
            available = self.available_resources.get(resource, 0)
            used = self.used_resources.get(resource, 0)
            limit = self.resource_limits.get(resource, float('inf'))
            
            if (used + amount) > min(available, limit):
                return False
        
        return True
    
    async def update_usage(self, resources: Dict[str, Any]):
        """Обновить использование ресурсов"""
        for resource, amount in resources.items():
            current_used = self.used_resources.get(resource, 0)
            self.used_resources[resource] = current_used + amount
    
    def release_resources(self, resources: Dict[str, Any]):
        """Освободить ресурсы после выполнения задачи"""
        for resource, amount in resources.items():
            current_used = self.used_resources.get(resource, 0)
            self.used_resources[resource] = max(0, current_used - amount)
```

### 2. Использование специфических компонентов

Пример использования специфических компонентов:

```python
# specialized_usage_example.py
from application.factories.specialized_factory import SpecializedFactory
from application.orchestration.specialized_orchestrator import SpecializedOrchestrator
from domain.models.specialized_task import SpecializedTask, TaskPriority

async def specialized_architecture_example():
    """Пример использования специфической архитектуры"""
    
    # Создать фабрику
    factory = SpecializedFactory({
        "pattern_defaults": {
            "timeout": 300,
            "retry_count": 3
        },
        "publisher_defaults": {
            "max_requests_per_second": 50,
            "burst_capacity": 100
        }
    })
    
    # Зарегистрировать специфические типы
    factory.register_pattern_type("security_analysis", SecurityAnalysisPattern)
    factory.register_publisher_type("specialized", SpecializedEventPublisher)
    
    # Создать паттерны
    security_pattern = factory.create_pattern(
        "security_analysis",
        config={
            "scan_depth": "deep",
            "vulnerability_types": ["sql_injection", "xss", "csrf"]
        }
    )
    
    # Создать публикатор событий
    event_publisher = factory.create_event_publisher("specialized")
    
    # Создать задачи
    tasks = [
        SpecializedTask(
            id="task_1",
            description="Анализ безопасности Python-кода",
            domain="code_analysis",
            priority=TaskPriority.HIGH,
            resources_needed={"cpu": 2, "memory": "2GB"},
            timeout=600
        ),
        SpecializedTask(
            id="task_2",
            description="Проверка SQL-запросов на инъекции",
            domain="data_processing",
            priority=TaskPriority.CRITICAL,
            dependencies=["task_1"],
            resources_needed={"cpu": 1, "memory": "1GB"},
            timeout=300
        )
    ]
    
    # Создать сервис задач
    task_service = SpecializedTaskService([security_pattern])
    
    # Добавить задачи в сервис
    for task in tasks:
        task_service.add_task(task)
    
    # Создать оркестратор
    orchestrator = SpecializedOrchestrator(task_service, [security_pattern])
    
    # Выполнить сессию
    result = await orchestrator.execute_session("session_12345", tasks)
    
    print(f"Результат выполнения сессии: {result}")
    
    return result

# Интеграция с существующими агентами
async def integrate_with_existing_agents():
    """Интеграция специфических компонентов с существующими агентами"""
    
    # Создать фабрику агентов
    agent_factory = AgentFactory()
    
    # Создать агента
    agent = await agent_factory.create_agent(
        agent_type="composable",
        domain=DomainType.CODE_ANALYSIS
    )
    
    # Создать специфическую задачу
    specialized_task = SpecializedTask(
        id="security_scan_001",
        description="Полный скан безопасности кодовой базы",
        domain="code_analysis",
        priority=TaskPriority.CRITICAL,
        resources_needed={"cpu": 4, "memory": "8GB", "disk": "100GB"},
        timeout=3600,
        metadata={
            "scan_type": "comprehensive",
            "target_framework": "django",
            "exclude_paths": ["node_modules", "venv"]
        }
    )
    
    # Создать оркестратор для специфических задач
    factory = SpecializedFactory()
    task_service = SpecializedTaskService([])
    orchestrator = SpecializedOrchestrator(task_service, [])
    
    # Выполнить специфическую задачу через оркестратор
    result = await orchestrator.execute_session(
        "security_scan_session",
        [specialized_task]
    )
    
    print(f"Результат специфической задачи: {result}")
    
    # Интегрировать результат с агентом
    agent_context = {
        "specialized_analysis_result": result,
        "original_task": "Perform comprehensive security analysis"
    }
    
    agent_result = await agent.execute_task(
        task_description="Проанализируй результаты сканирования безопасности и сформируй отчет",
        context=agent_context
    )
    
    print(f"Результат агента: {agent_result}")
    
    return agent_result
```

## Лучшие практики

### 1. Модульность и расширяемость

Создавайте архитектурные компоненты, которые можно легко расширять:

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

# Плохо: монолитная архитектура
class MonolithicPattern:
    """Монолитный паттерн - сложно расширять и тестировать"""
    pass
```

### 2. Зависимости и инъекция

Используйте внедрение зависимостей для слабой связанности:

```python
# Хорошо: внедрение зависимостей
class TaskProcessor:
    def __init__(self, event_publisher: IEventPublisher, resource_manager: ResourceManager):
        self.event_publisher = event_publisher
        self.resource_manager = resource_manager

# Плохо: жесткая связанность
class TaskProcessor:
    def __init__(self):
        self.event_publisher = SpecializedEventPublisher()  # Жестко закодированная зависимость
        self.resource_manager = ResourceManager()
```

### 3. Конфигурирование

Обеспечьте гибкость через конфигурацию:

```python
class ConfigurableComponent:
    """Компонент с гибкой конфигурацией"""
    
    def __init__(self, config: Dict[str, Any]):
        self.timeout = config.get("timeout", 300)
        self.retry_count = config.get("retry_count", 3)
        self.enable_logging = config.get("enable_logging", True)
        self.resource_limits = config.get("resource_limits", {})
```

### 4. Тестирование архитектуры

Создавайте тесты для архитектурных компонентов:

```python
# test_architecture_components.py
import pytest
from unittest.mock import AsyncMock, Mock

class TestSpecializedTaskService:
    @pytest.mark.asyncio
    async def test_execute_task_success(self):
        """Тест успешного выполнения задачи"""
        # Создать моки паттернов
        mock_pattern = AsyncMock()
        mock_pattern.can_handle_task.return_value = True
        mock_pattern.execute_specialized.return_value = {"result": "success"}
        
        # Создать сервис
        service = SpecializedTaskService([mock_pattern])
        
        # Создать задачу
        task = SpecializedTask(
            id="test_task",
            description="Test task",
            domain="test"
        )
        
        # Выполнить задачу
        result = await service.execute_task(task)
        
        # Проверить результат
        assert result["success"] is True
        assert result["task_id"] == "test_task"
        assert "result" in result
    
    @pytest.mark.asyncio
    async def test_execute_task_no_pattern(self):
        """Тест выполнения задачи без подходящего паттерна"""
        # Создать сервис без подходящих паттернов
        mock_pattern = AsyncMock()
        mock_pattern.can_handle_task.return_value = False
        
        service = SpecializedTaskService([mock_pattern])
        
        task = SpecializedTask(
            id="test_task",
            description="Test task",
            domain="test"
        )
        
        result = await service.execute_task(task)
        
        assert result["success"] is False
        assert "Не найден подходящий паттерн" in result["error"]

class TestSpecializedOrchestrator:
    @pytest.mark.asyncio
    async def test_session_execution(self):
        """Тест выполнения сессии"""
        # Создать моки
        mock_task_service = AsyncMock()
        mock_task_service.prioritize_tasks.return_value = []
        mock_task_service.execute_task.return_value = {"success": True}
        
        mock_pattern = AsyncMock()
        
        # Создать оркестратор
        orchestrator = SpecializedOrchestrator(mock_task_service, [mock_pattern])
        
        # Создать задачи
        tasks = [
            SpecializedTask(
                id="task_1",
                description="Test task 1",
                domain="test"
            )
        ]
        
        # Выполнить сессию
        result = await orchestrator.execute_session("test_session", tasks)
        
        # Проверить результат
        assert result["success"] is True
        assert result["session_id"] == "test_session"
        assert "summary" in result
```

Эти примеры показывают, как адаптировать и расширять архитектуру Koru AI Agent Framework под специфические задачи, обеспечивая модульность, гибкость и тестируемость системы.