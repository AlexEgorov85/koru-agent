# Разработка системных компонентов под свои задачи

В этом разделе описаны рекомендации и практики по адаптации и расширению системных компонентов Composable AI Agent Framework для удовлетворения специфических требований и задач. Вы узнаете, как модифицировать существующие системные компоненты и создавать новые для расширения функциональности системы.

## Архитектура системных компонентов

### 1. Система управления жизненным циклом

Система управления жизненным циклом обеспечивает инициализацию, запуск, остановку и очистку системных компонентов:

```python
# domain/abstractions/lifecycle.py
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from enum import Enum
import asyncio
import time

class ComponentStatus(str, Enum):
    """Статусы компонента"""
    CREATED = "created"
    INITIALIZING = "initializing"
    INITIALIZED = "initialized"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"
    RECOVERING = "recovering"

class ILifecycleManager(ABC):
    """Интерфейс менеджера жизненного цикла"""
    
    @abstractmethod
    async def initialize(self):
        """Инициализировать компонент"""
        pass
    
    @abstractmethod
    async def start(self):
        """Запустить компонент"""
        pass
    
    @abstractmethod
    async def stop(self):
        """Остановить компонент"""
        pass
    
    @abstractmethod
    async def cleanup(self):
        """Очистить ресурсы компонента"""
        pass
    
    @abstractmethod
    def get_status(self) -> ComponentStatus:
        """Получить статус компонента"""
        pass

class BaseLifecycleManager(ILifecycleManager, ABC):
    """Базовый менеджер жизненного цикла"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.status = ComponentStatus.CREATED
        self._start_time = None
        self._stop_time = None
        self._error_count = 0
        self._last_error = None
        self._health_checks = []
        self._telemetry_enabled = self.config.get("telemetry_enabled", True)
        self._telemetry_collector = self._setup_telemetry_collector()
    
    async def initialize(self):
        """Инициализировать компонент с проверкой зависимостей"""
        self.status = ComponentStatus.INITIALIZING
        
        try:
            # Проверить зависимости
            await self._verify_dependencies()
            
            # Выполнить инициализацию
            await self._perform_initialization()
            
            # Выполнить проверки здоровья
            await self._run_health_checks()
            
            self.status = ComponentStatus.INITIALIZED
            self._log_lifecycle_event("initialized")
        except Exception as e:
            self.status = ComponentStatus.FAILED
            self._last_error = str(e)
            self._error_count += 1
            self._log_error(f"Ошибка инициализации: {str(e)}")
            raise
    
    async def start(self):
        """Запустить компонент с проверкой готовности"""
        if self.status != ComponentStatus.INITIALIZED:
            raise RuntimeError(f"Компонент не инициализирован, статус: {self.status}")
        
        self.status = ComponentStatus.STARTING
        
        try:
            # Выполнить запуск
            await self._perform_startup()
            
            # Проверить работоспособность после запуска
            if not await self._verify_operational_state():
                raise RuntimeError("Компонент не достиг работоспособного состояния после запуска")
            
            self.status = ComponentStatus.RUNNING
            self._start_time = time.time()
            self._log_lifecycle_event("started")
        except Exception as e:
            self.status = ComponentStatus.FAILED
            self._last_error = str(e)
            self._error_count += 1
            self._log_error(f"Ошибка запуска: {str(e)}")
            raise
    
    async def stop(self):
        """Остановить компонент с корректной очисткой"""
        if self.status in [ComponentStatus.STOPPED, ComponentStatus.STOPPING]:
            return  # Уже остановлен или останавливается
        
        self.status = ComponentStatus.STOPPING
        
        try:
            # Выполнить предварительные действия остановки
            await self._perform_pre_stop_actions()
            
            # Выполнить остановку
            await self._perform_shutdown()
            
            # Выполнить пост-действия остановки
            await self._perform_post_stop_actions()
            
            self.status = ComponentStatus.STOPPED
            self._stop_time = time.time()
            self._log_lifecycle_event("stopped")
        except Exception as e:
            self.status = ComponentStatus.FAILED
            self._last_error = str(e)
            self._error_count += 1
            self._log_error(f"Ошибка остановки: {str(e)}")
            raise
    
    async def cleanup(self):
        """Очистить ресурсы компонента"""
        try:
            # Очистить ресурсы
            await self._perform_cleanup()
            
            # Остановить сбор телеметрии
            if self._telemetry_collector:
                await self._telemetry_collector.shutdown()
        except Exception as e:
            self._log_error(f"Ошибка очистки ресурсов: {str(e)}")
            raise
    
    async def recover(self):
        """Восстановить компонент после ошибки"""
        if self.status != ComponentStatus.FAILED:
            raise RuntimeError("Нельзя восстановить компонент, который не в состоянии ошибки")
        
        self.status = ComponentStatus.RECOVERING
        
        try:
            # Выполнить восстановление
            await self._perform_recovery()
            
            # Повторно инициализировать
            await self.initialize()
            
            # Повторно запустить
            await self.start()
            
            self.status = ComponentStatus.RUNNING
            self._log_lifecycle_event("recovered")
        except Exception as e:
            self.status = ComponentStatus.FAILED
            self._last_error = str(e)
            self._error_count += 1
            self._log_error(f"Ошибка восстановления: {str(e)}")
            raise
    
    def get_status_info(self) -> Dict[str, Any]:
        """Получить полную информацию о статусе"""
        uptime = 0
        if self._start_time:
            uptime = time.time() - self._start_time if self.status == ComponentStatus.RUNNING else self._stop_time - self._start_time
        
        return {
            "status": self.status.value,
            "uptime_seconds": uptime,
            "error_count": self._error_count,
            "last_error": self._last_error,
            "start_time": self._start_time,
            "stop_time": self._stop_time,
            "health_checks_passed": len([hc for hc in self.health_checks if hc.get("passed", False)]),
            "health_checks_total": len(self.health_checks)
        }
    
    async def _verify_dependencies(self):
        """Проверить зависимости компонента"""
        # Реализация проверки зависимостей
        pass
    
    async def _perform_initialization(self):
        """Выполнить специфическую инициализацию"""
        # Реализация инициализации
        pass
    
    async def _run_health_checks(self):
        """Выполнить проверки здоровья"""
        # Реализация проверок здоровья
        pass
    
    async def _perform_startup(self):
        """Выполнить запуск компонента"""
        # Реализация запуска
        pass
    
    async def _verify_operational_state(self) -> bool:
        """Проверить работоспособное состояние"""
        # Реализация проверки работоспособности
        return True
    
    async def _perform_pre_stop_actions(self):
        """Выполнить предварительные действия остановки"""
        # Реализация предварительных действий
        pass
    
    async def _perform_shutdown(self):
        """Выполнить остановку компонента"""
        # Реализация остановки
        pass
    
    async def _perform_post_stop_actions(self):
        """Выполнить пост-действия остановки"""
        # Реализация пост-действий
        pass
    
    async def _perform_cleanup(self):
        """Выполнить очистку ресурсов"""
        # Реализация очистки
        pass
    
    async def _perform_recovery(self):
        """Выполнить восстановление после ошибки"""
        # Реализация восстановления
        pass
    
    def _log_lifecycle_event(self, event_type: str):
        """Залогировать событие жизненного цикла"""
        if self._telemetry_enabled:
            self._telemetry_collector.record_lifecycle_event(event_type, self.status.value)
    
    def _log_error(self, error_message: str):
        """Залогировать ошибку"""
        if self._telemetry_enabled:
            self._telemetry_collector.record_error(error_message)
    
    def _setup_telemetry_collector(self):
        """Настроить сбор телеметрии"""
        if self._telemetry_enabled:
            from infrastructure.services.telemetry_service import TelemetryService
            return TelemetryService(component_name=self.__class__.__name__)
        return None
```

### 2. Система управления доменами

Система управления доменами позволяет адаптировать систему к различным областям задач:

```python
# domain/abstractions/domain_management.py
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from enum import Enum
from pydantic import BaseModel

class DomainType(str, Enum):
    """Типы доменов"""
    CODE_ANALYSIS = "code_analysis"
    DATA_PROCESSING = "data_processing"
    CONTENT_GENERATION = "content_generation"
    SECURITY_ANALYSIS = "security_analysis"
    TESTING = "testing"
    INFRASTRUCTURE = "infrastructure"

class IDomainManager(ABC):
    """Интерфейс менеджера доменов"""
    
    @abstractmethod
    async def register_domain(self, domain_type: DomainType, config: Dict[str, Any]):
        """Зарегистрировать домен с конфигурацией"""
        pass
    
    @abstractmethod
    async def adapt_agent_to_domain(self, agent_id: str, domain_type: DomainType, capabilities: List[str]):
        """Адаптировать агента к домену с указанными возможностями"""
        pass
    
    @abstractmethod
    def get_domain_capabilities(self, domain_type: DomainType) -> List[str]:
        """Получить возможности домена"""
        pass
    
    @abstractmethod
    def get_domain_prompts(self, domain_type: DomainType) -> List[str]:
        """Получить промты домена"""
        pass

class DomainManager(IDomainManager):
    """Менеджер доменов"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self._domains = {}
        self._agent_domains = {}
        self._domain_capabilities = {}
        self._domain_prompts = {}
        self._domain_patterns = {}
        self._initialized_domains = set()
    
    async def register_domain(self, domain_type: DomainType, config: Dict[str, Any]):
        """Зарегистрировать домен с конфигурацией"""
        if domain_type in self._domains:
            raise ValueError(f"Домен {domain_type} уже зарегистрирован")
        
        domain_config = {
            **self.config.get("domain_defaults", {}),
            **config
        }
        
        self._domains[domain_type] = domain_config
        
        # Инициализировать возможности домена
        await self._initialize_domain_capabilities(domain_type, domain_config)
        
        # Загрузить паттерны домена
        await self._load_domain_patterns(domain_type, domain_config)
        
        # Загрузить промты домена
        await self._load_domain_prompts(domain_type, domain_config)
        
        self._initialized_domains.add(domain_type)
        
        print(f"Домен {domain_type} успешно зарегистрирован")
    
    async def adapt_agent_to_domain(self, agent_id: str, domain_type: DomainType, capabilities: List[str]):
        """Адаптировать агента к домену с указанными возможностями"""
        if domain_type not in self._domains:
            raise ValueError(f"Домен {domain_type} не зарегистрирован")
        
        # Проверить, что указанные возможности доступны для домена
        available_capabilities = self.get_domain_capabilities(domain_type)
        for capability in capabilities:
            if capability not in available_capabilities:
                raise ValueError(f"Возможность {capability} не доступна для домена {domain_type}")
        
        # Адаптировать агента
        self._agent_domains[agent_id] = {
            "domain_type": domain_type,
            "capabilities": capabilities,
            "adaptation_time": time.time()
        }
        
        # Загрузить доменно-специфические промты и паттерны для агента
        await self._adapt_agent_components(agent_id, domain_type, capabilities)
        
        print(f"Агент {agent_id} адаптирован к домену {domain_type} с возможностями {capabilities}")
    
    def get_domain_capabilities(self, domain_type: DomainType) -> List[str]:
        """Получить возможности домена"""
        return self._domain_capabilities.get(domain_type, [])
    
    def get_domain_prompts(self, domain_type: DomainType) -> List[str]:
        """Получить промты домена"""
        return self._domain_prompts.get(domain_type, [])
    
    async def _initialize_domain_capabilities(self, domain_type: DomainType, config: Dict[str, Any]):
        """Инициализировать возможности домена"""
        # Загрузить возможности из конфигурации
        capabilities = config.get("capabilities", [])
        
        # Добавить базовые возможности в зависимости от типа домена
        base_capabilities = self._get_base_capabilities_for_domain(domain_type)
        all_capabilities = list(set(capabilities + base_capabilities))
        
        self._domain_capabilities[domain_type] = all_capabilities
    
    async def _load_domain_patterns(self, domain_type: DomainType, config: Dict[str, Any]):
        """Загрузить паттерны домена"""
        from application.services.pattern_loader import PatternLoader
        
        pattern_loader = PatternLoader()
        domain_patterns_path = f"patterns/{domain_type.value}"
        
        patterns, errors = await pattern_loader.load_patterns_from_path(domain_patterns_path)
        
        if errors:
            print(f"Ошибки загрузки паттернов для домена {domain_type}: {errors}")
        
        self._domain_patterns[domain_type] = patterns
    
    async def _load_domain_prompts(self, domain_type: DomainType, config: Dict[str, Any]):
        """Загрузить промты домена"""
        from application.services.prompt_loader import PromptLoader
        
        prompt_loader = PromptLoader(base_path=f"prompts/{domain_type.value}")
        prompts, errors = prompt_loader.load_all_prompts()
        
        if errors:
            print(f"Ошибки загрузки промтов для домена {domain_type}: {errors}")
        
        self._domain_prompts[domain_type] = prompts
    
    def _get_base_capabilities_for_domain(self, domain_type: DomainType) -> List[str]:
        """Получить базовые возможности для домена"""
        base_caps = {
            DomainType.CODE_ANALYSIS: [
                "code_reading", "ast_parsing", "security_scanning", 
                "quality_analysis", "pattern_matching"
            ],
            DomainType.DATA_PROCESSING: [
                "data_reading", "sql_execution", "data_transformation", 
                "validation", "report_generation"
            ],
            DomainType.CONTENT_GENERATION: [
                "text_generation", "content_synthesis", "style_adaptation", 
                "formatting", "review"
            ],
            DomainType.SECURITY_ANALYSIS: [
                "vulnerability_scanning", "security_assessment", 
                "risk_analysis", "compliance_check"
            ],
            DomainType.TESTING: [
                "test_generation", "test_execution", "coverage_analysis", 
                "performance_testing", "integration_testing"
            ],
            DomainType.INFRASTRUCTURE: [
                "command_execution", "resource_monitoring", 
                "configuration_management", "deployment"
            ]
        }
        
        return base_caps.get(domain_type, [])
    
    async def _adapt_agent_components(self, agent_id: str, domain_type: DomainType, capabilities: List[str]):
        """Адаптировать компоненты агента к домену"""
        # Здесь будет логика адаптации компонентов агента к домену
        # например, загрузка доменно-специфических промтов и паттернов
        pass
    
    def get_agent_domain_info(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Получить информацию о домене агента"""
        return self._agent_domains.get(agent_id)
    
    async def unregister_domain(self, domain_type: DomainType):
        """Отменить регистрацию домена"""
        if domain_type in self._domains:
            # Освободить ресурсы домена
            await self._cleanup_domain_resources(domain_type)
            
            # Удалить домен из реестра
            del self._domains[domain_type]
            if domain_type in self._domain_capabilities:
                del self._domain_capabilities[domain_type]
            if domain_type in self._domain_prompts:
                del self._domain_prompts[domain_type]
            if domain_type in self._domain_patterns:
                del self._domain_patterns[domain_type]
            
            self._initialized_domains.discard(domain_type)
    
    async def _cleanup_domain_resources(self, domain_type: DomainType):
        """Очистить ресурсы домена"""
        # Очистить ресурсы, связанные с доменом
        pass
```

### 3. Система конфигурации

Система конфигурации позволяет настраивать компоненты под специфические задачи:

```python
# domain/abstractions/config_system.py
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from pydantic import BaseModel, ValidationError
import yaml
import json
import os

class ConfigSource(str, Enum):
    """Источники конфигурации"""
    FILE = "file"
    ENVIRONMENT = "environment"
    DATABASE = "database"
    API = "api"
    DEFAULT = "default"

class IConfigurationManager(ABC):
    """Интерфейс менеджера конфигурации"""
    
    @abstractmethod
    async def load_config(self, source: ConfigSource, location: str = None) -> Dict[str, Any]:
        """Загрузить конфигурацию из указанного источника"""
        pass
    
    @abstractmethod
    async def save_config(self, config: Dict[str, Any], destination: ConfigSource, location: str = None):
        """Сохранить конфигурацию в указанный источник"""
        pass
    
    @abstractmethod
    def get_config_value(self, path: str, default: Any = None) -> Any:
        """Получить значение конфигурации по пути"""
        pass
    
    @abstractmethod
    def set_config_value(self, path: str, value: Any):
        """Установить значение конфигурации по пути"""
        pass

class ConfigurationManager(IConfigurationManager):
    """Менеджер конфигурации"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self._loaded_configs = {}
        self._config_validators = {}
        self._config_watchers = {}
        self._validation_schemas = {}
        self._default_config = self._get_default_configuration()
    
    async def load_config(self, source: ConfigSource, location: str = None) -> Dict[str, Any]:
        """Загрузить конфигурацию из указанного источника"""
        if source == ConfigSource.FILE:
            if not location:
                raise ValueError("Для файла источника необходимо указать путь")
            
            config_data = await self._load_from_file(location)
        elif source == ConfigSource.ENVIRONMENT:
            config_data = self._load_from_environment()
        elif source == ConfigSource.DATABASE:
            config_data = await self._load_from_database(location)
        elif source == ConfigSource.API:
            config_data = await self._load_from_api(location)
        else:  # DEFAULT
            config_data = self._default_config.copy()
        
        # Применить валидацию
        validated_config = await self._validate_config(config_data, source)
        
        # Сохранить загруженную конфигурацию
        self._loaded_configs[source.value] = validated_config
        
        # Объединить с основной конфигурацией
        self.config = self._merge_configs(self.config, validated_config)
        
        return validated_config
    
    async def save_config(self, config: Dict[str, Any], destination: ConfigSource, location: str = None):
        """Сохранить конфигурацию в указанный источник"""
        if destination == ConfigSource.FILE:
            if not location:
                raise ValueError("Для файла назначения необходимо указать путь")
            
            await self._save_to_file(config, location)
        elif destination == ConfigSource.DATABASE:
            await self._save_to_database(config, location)
        elif destination == ConfigSource.API:
            await self._save_to_api(config, location)
        else:
            raise ValueError(f"Невозможно сохранить конфигурацию в источник: {destination}")
    
    def get_config_value(self, path: str, default: Any = None) -> Any:
        """Получить значение конфигурации по пути"""
        keys = path.split('.')
        current = self.config
        
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return default
        
        return current
    
    def set_config_value(self, path: str, value: Any):
        """Установить значение конфигурации по пути"""
        keys = path.split('.')
        current = self.config
        
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        
        current[keys[-1]] = value
    
    async def _load_from_file(self, file_path: str) -> Dict[str, Any]:
        """Загрузить конфигурацию из файла"""
        path = Path(file_path)
        
        if path.suffix.lower() in ['.yaml', '.yml']:
            with open(path, 'r', encoding='utf-8') as file:
                content = file.read()
                # Заменить переменные окружения в формате ${VAR_NAME}
                content = self._substitute_env_vars(content)
                return yaml.safe_load(content) or {}
        elif path.suffix.lower() == '.json':
            with open(path, 'r', encoding='utf-8') as file:
                content = file.read()
                content = self._substitute_env_vars(content)
                return json.loads(content)
        else:
            raise ValueError(f"Неподдерживаемый формат файла: {path.suffix}")
    
    def _load_from_environment(self) -> Dict[str, Any]:
        """Загрузить конфигурацию из переменных окружения"""
        config = {}
        
        # Загрузка переменных, начинающихся с PREFIX_
        prefix = "AGENT_"
        for key, value in os.environ.items():
            if key.startswith(prefix):
                # Преобразование ключа в формат конфигурации (AGENT_MAX_ITERATIONS -> agent.max_iterations)
                config_key = self._convert_env_key(key[len(prefix):])
                config[config_key] = self._convert_env_value(value)
        
        return config
    
    async def _load_from_database(self, connection_string: str) -> Dict[str, Any]:
        """Загрузить конфигурацию из базы данных"""
        # Реализация загрузки из базы данных
        # В реальной системе здесь будет подключение к БД и извлечение конфигурации
        pass
    
    async def _load_from_api(self, api_url: str) -> Dict[str, Any]:
        """Загрузить конфигурацию из API"""
        # Реализация загрузки из API
        # В реальной системе здесь будет HTTP-запрос к API конфигурации
        pass
    
    def _substitute_env_vars(self, content: str) -> str:
        """Заменить переменные окружения в содержимом файла"""
        import re
        
        def replace_env_var(match):
            var_name = match.group(1)
            default_val = match.group(2) if match.group(2) else ""
            return os.getenv(var_name, default_val)
        
        # Заменить переменные в формате ${VAR_NAME} или ${VAR_NAME:default_value}
        pattern = r'\$\{([A-Z_][A-Z0-9_]*)\}'
        content = re.sub(pattern, lambda m: os.getenv(m.group(1), ""), content)
        
        # Заменить переменные в формате ${VAR_NAME:default_value}
        pattern_with_default = r'\$\{([A-Z_][A-Z0-9_]*)\:([^}]*)\}'
        content = re.sub(pattern_with_default, replace_env_var, content)
        
        return content
    
    def _convert_env_key(self, env_key: str) -> str:
        """Конвертировать ключ переменной окружения в формат конфигурации"""
        # Преобразование в формат с точками: MAX_ITERATIONS -> max_iterations
        # и разбиение на вложенные ключи: AGENT_MAX_ITERATIONS -> agent.max_iterations
        parts = env_key.lower().split('_')
        
        # Если первая часть может быть именем компонента (agent, llm, prompts)
        if parts and parts[0] in ['agent', 'llm', 'prompts', 'system']:
            component = parts[0]
            remaining_parts = parts[1:]
        else:
            # По умолчанию считаем, что это системные настройки
            component = 'system'
            remaining_parts = parts
        
        # Собираем оставшиеся части в camelCase в snake_case
        nested_key = '_'.join(remaining_parts).lower()
        
        if nested_key:
            return f"{component}.{nested_key}"
        else:
            return component
    
    def _convert_env_value(self, value: str) -> Any:
        """Конвертировать строковое значение переменной окружения в соответствующий тип"""
        # Попробовать конвертировать в boolean
        if value.lower() in ['true', 'false']:
            return value.lower() == 'true'
        
        # Попробовать конвертировать в число
        try:
            if '.' in value:
                return float(value)
            else:
                return int(value)
        except ValueError:
            pass
        
        # Попробовать конвертировать в список (если содержит запятые)
        if ',' in value:
            items = [item.strip() for item in value.split(',')]
            # Попробовать конвертировать элементы списка
            converted_items = []
            for item in items:
                try:
                    if item.lower() in ['true', 'false']:
                        converted_items.append(item.lower() == 'true')
                    elif '.' in item:
                        converted_items.append(float(item))
                    else:
                        converted_items.append(int(item))
                except ValueError:
                    converted_items.append(item)
            return converted_items
        
        # Попробовать конвертировать в словарь (если содержит JSON)
        try:
            if value.startswith('{') and value.endswith('}'):
                return json.loads(value)
        except json.JSONDecodeError:
            pass
        
        # Вернуть строку
        return value
    
    async def _validate_config(self, config: Dict[str, Any], source: ConfigSource) -> Dict[str, Any]:
        """Валидировать конфигурацию"""
        if source in self._config_validators:
            validator = self._config_validators[source]
            return await validator(config)
        
        return config
    
    def _merge_configs(self, base_config: Dict[str, Any], override_config: Dict[str, Any]) -> Dict[str, Any]:
        """Объединить две конфигурации"""
        merged = base_config.copy()
        
        for key, value in override_config.items():
            if isinstance(value, dict) and key in merged and isinstance(merged[key], dict):
                merged[key] = self._merge_configs(merged[key], value)
            else:
                merged[key] = value
        
        return merged
    
    def _get_default_configuration(self) -> Dict[str, Any]:
        """Получить конфигурацию по умолчанию"""
        return {
            "agent": {
                "max_iterations": 50,
                "timeout": 300,
                "enable_logging": True,
                "max_concurrent_actions": 5
            },
            "llm": {
                "provider": "openai",
                "model": "gpt-4",
                "temperature": 0.7,
                "max_tokens": 2048
            },
            "prompts": {
                "cache_enabled": True,
                "cache_ttl": 3600
            },
            "system": {
                "debug_mode": False,
                "log_level": "INFO"
            }
        }
    
    def register_config_validator(self, source: ConfigSource, validator_func):
        """Зарегистрировать валидатор конфигурации"""
        self._config_validators[source] = validator_func
    
    def watch_config_changes(self, path: str, callback: Callable):
        """Наблюдать за изменениями конфигурации"""
        self._config_watchers[path] = callback
    
    def get_effective_config(self) -> Dict[str, Any]:
        """Получить эффективную конфигурацию (объединенную из всех источников)"""
        effective_config = self._default_config.copy()
        
        for source_config in self._loaded_configs.values():
            effective_config = self._merge_configs(effective_config, source_config)
        
        return effective_config
```

## Создание специфических системных компонентов

### 1. Специфический менеджер жизненного цикла

Для создания специфических компонентов жизненного цикла:

```python
class SpecializedLifecycleManager(BaseLifecycleManager):
    """Специфический менеджер жизненного цикла для специфических задач"""
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config or {})
        
        # Специфические настройки
        self._resource_manager = ResourceManager(
            max_memory=config.get("max_memory", "1GB"),
            max_cpu_percentage=config.get("max_cpu_percentage", 80.0)
        )
        self._security_monitor = SecurityMonitor(
            enabled=config.get("security_monitoring", True)
        )
        self._performance_monitor = PerformanceMonitor(
            collection_interval=config.get("metrics_collection_interval", 30)
        )
        
        # Специфические проверки здоровья
        self._custom_health_checks = [
            self._check_resource_availability,
            self._check_security_status,
            self._check_performance_metrics
        ]
    
    async def _verify_dependencies(self):
        """Проверить специфические зависимости"""
        # Проверить зависимости, специфические для задачи
        dependencies = self.config.get("dependencies", {})
        
        for dep_name, dep_config in dependencies.items():
            if dep_config.get("required", True):
                if not await self._check_dependency(dep_name, dep_config):
                    raise RuntimeError(f"Необходимая зависимость {dep_name} недоступна")
    
    async def _perform_initialization(self):
        """Выполнить специфическую инициализацию"""
        # Инициализировать специфические ресурсы
        await self._resource_manager.initialize()
        
        # Инициализировать мониторинг безопасности
        if self._security_monitor.enabled:
            await self._security_monitor.initialize()
        
        # Инициализировать мониторинг производительности
        await self._performance_monitor.initialize()
        
        # Выполнить пользовательскую инициализацию
        await self._perform_custom_initialization()
    
    async def _run_health_checks(self):
        """Выполнить специфические проверки здоровья"""
        results = []
        
        # Выполнить базовые проверки
        base_results = await super()._run_health_checks()
        results.extend(base_results)
        
        # Выполнить специфические проверки
        for check_func in self._custom_health_checks:
            try:
                check_result = await check_func()
                results.append(check_result)
            except Exception as e:
                results.append({
                    "check": check_func.__name__,
                    "passed": False,
                    "error": str(e)
                })
        
        # Обновить список проверок здоровья
        self.health_checks.extend(results)
        
        # Проверить, все ли проверки прошли успешно
        all_passed = all(result.get("passed", False) for result in results)
        
        if not all_passed:
            failed_checks = [r for r in results if not r.get("passed", False)]
            raise RuntimeError(f"Проверки здоровья не пройдены: {failed_checks}")
    
    async def _check_resource_availability(self) -> Dict[str, Any]:
        """Проверить доступность ресурсов"""
        resource_status = await self._resource_manager.get_status()
        
        return {
            "check": "resource_availability",
            "passed": resource_status["available"],
            "details": resource_status
        }
    
    async def _check_security_status(self) -> Dict[str, Any]:
        """Проверить статус безопасности"""
        security_status = await self._security_monitor.get_security_status()
        
        return {
            "check": "security_status",
            "passed": security_status["secure"],
            "details": security_status
        }
    
    async def _check_performance_metrics(self) -> Dict[str, Any]:
        """Проверить метрики производительности"""
        perf_metrics = await self._performance_monitor.get_current_metrics()
        
        # Проверить, укладываются ли метрики в допустимые пределы
        acceptable = (
            perf_metrics.get("cpu_usage", 100) <= 90 and
            perf_metrics.get("memory_usage", 100) <= 85 and
            perf_metrics.get("response_time_avg", float('inf')) <= 5.0
        )
        
        return {
            "check": "performance_metrics",
            "passed": acceptable,
            "details": perf_metrics
        }
    
    async def _perform_custom_initialization(self):
        """Выполнить пользовательскую инициализацию"""
        # В этом методе реализуется специфическая логика инициализации
        # для конкретной задачи или домена
        pass
    
    async def _perform_startup(self):
        """Выполнить специфический запуск"""
        # Запустить специфические службы
        await self._resource_manager.start_monitoring()
        
        if self._security_monitor.enabled:
            await self._security_monitor.start_monitoring()
        
        await self._performance_monitor.start_monitoring()
        
        # Выполнить пользовательский запуск
        await self._perform_custom_startup()
    
    async def _perform_custom_startup(self):
        """Выполнить пользовательский запуск"""
        # Специфическая логика запуска для конкретной задачи
        pass
    
    async def _perform_shutdown(self):
        """Выполнить специфическую остановку"""
        # Остановить специфические службы
        await self._performance_monitor.stop_monitoring()
        
        if self._security_monitor.enabled:
            await self._security_monitor.stop_monitoring()
        
        await self._resource_manager.stop_monitoring()
        
        # Выполнить пользовательскую остановку
        await self._perform_custom_shutdown()
    
    async def _perform_custom_shutdown(self):
        """Выполнить пользовательскую остановку"""
        # Специфическая логика остановки для конкретной задачи
        pass
    
    async def _perform_cleanup(self):
        """Выполнить специфическую очистку"""
        # Очистить специфические ресурсы
        await self._resource_manager.cleanup()
        
        if self._security_monitor.enabled:
            await self._security_monitor.cleanup()
        
        await self._performance_monitor.cleanup()
        
        # Выполнить пользовательскую очистку
        await self._perform_custom_cleanup()
    
    async def _perform_custom_cleanup(self):
        """Выполнить пользовательскую очистку"""
        # Специфическая логика очистки для конкретной задачи
        pass
    
    async def _perform_recovery(self):
        """Выполнить специфическое восстановление"""
        # Выполнить специфическую логику восстановления
        await self._security_monitor.reset_security_state()
        await self._resource_manager.reset_resource_limits()
        
        # Выполнить пользовательское восстановление
        await self._perform_custom_recovery()
    
    async def _perform_custom_recovery(self):
        """Выполнить пользовательское восстановление"""
        # Специфическая логика восстановления для конкретной задачи
        pass
    
    def get_detailed_status(self) -> Dict[str, Any]:
        """Получить детализированный статус"""
        base_status = self.get_status_info()
        
        # Добавить специфическую информацию
        detailed_status = {
            **base_status,
            "resource_status": self._resource_manager.get_status(),
            "security_status": self._security_monitor.get_status() if self._security_monitor.enabled else None,
            "performance_metrics": self._performance_monitor.get_current_metrics(),
            "custom_components_status": self._get_custom_components_status()
        }
        
        return detailed_status
    
    def _get_custom_components_status(self) -> Dict[str, Any]:
        """Получить статус специфических компонентов"""
        # Возвращаем статус специфических компонентов
        return {}
```

### 2. Специфический менеджер доменов

Для управления доменами с учетом специфических требований:

```python
class SpecializedDomainManager(DomainManager):
    """Специфический менеджер доменов с дополнительными возможностями"""
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        
        # Специфические настройки
        self._domain_security_policies = {}
        self._domain_resource_limits = {}
        self._domain_compliance_rules = {}
        self._domain_audit_log = []
        
        # Загрузить специфические политики
        self._load_specialized_policies()
    
    async def register_domain(self, domain_type: DomainType, config: Dict[str, Any]):
        """Зарегистрировать домен с дополнительными проверками"""
        # Выполнить специфические проверки безопасности
        if not await self._validate_domain_security_requirements(domain_type, config):
            raise ValueError(f"Домен {domain_type} не соответствует требованиям безопасности")
        
        # Проверить ограничения ресурсов
        if not self._validate_resource_requirements(domain_type, config):
            raise ValueError(f"Домен {domain_type} не соответствует требованиям к ресурсам")
        
        # Выполнить базовую регистрацию
        await super().register_domain(domain_type, config)
        
        # Применить специфические настройки
        await self._apply_specialized_domain_config(domain_type, config)
    
    async def adapt_agent_to_domain(self, agent_id: str, domain_type: DomainType, capabilities: List[str]):
        """Адаптировать агента к домену с дополнительными проверками"""
        # Проверить, соответствует ли агент требованиям безопасности домена
        if not await self._check_agent_security_compliance(agent_id, domain_type):
            raise ValueError(f"Агент {agent_id} не соответствует требованиям безопасности домена {domain_type}")
        
        # Проверить, укладывается ли агент в ограничения ресурсов домена
        if not self._check_agent_resource_compliance(agent_id, domain_type):
            raise ValueError(f"Агент {agent_id} превышает ограничения ресурсов домена {domain_type}")
        
        # Выполнить базовую адаптацию
        await super().adapt_agent_to_domain(agent_id, domain_type, capabilities)
        
        # Зарегистрировать адаптацию в аудите
        await self._log_domain_adaptation(agent_id, domain_type, capabilities)
    
    async def _validate_domain_security_requirements(self, domain_type: DomainType, config: Dict[str, Any]) -> bool:
        """Проверить требования безопасности для домена"""
        security_policy = self._domain_security_policies.get(domain_type)
        
        if not security_policy:
            return True  # Если политики нет, считаем, что требования выполнены
        
        # Проверить специфические требования безопасности
        required_security_features = security_policy.get("required_features", [])
        for feature in required_security_features:
            if not config.get(feature, False):
                return False
        
        return True
    
    def _validate_resource_requirements(self, domain_type: DomainType, config: Dict[str, Any]) -> bool:
        """Проверить требования к ресурсам для домена"""
        resource_limits = self._domain_resource_limits.get(domain_type, {})
        
        if not resource_limits:
            return True  # Если ограничений нет, считаем, что требования выполнены
        
        # Проверить ограничения ресурсов
        for resource_type, limit in resource_limits.items():
            if config.get(f"max_{resource_type}", float('inf')) > limit:
                return False
        
        return True
    
    async def _check_agent_security_compliance(self, agent_id: str, domain_type: DomainType) -> bool:
        """Проверить соответствие агента требованиям безопасности домена"""
        security_policy = self._domain_security_policies.get(domain_type)
        
        if not security_policy:
            return True
        
        # В реальной реализации здесь будет проверка соответствия агента
        # требованиям безопасности домена (например, уровню доступа, разрешенным действиям и т.д.)
        return True
    
    def _check_agent_resource_compliance(self, agent_id: str, domain_type: DomainType) -> bool:
        """Проверить соответствие агента ограничениям ресурсов домена"""
        resource_limits = self._domain_resource_limits.get(domain_type, {})
        
        if not resource_limits:
            return True
        
        # В реальной реализации здесь будет проверка использования ресурсов агентом
        # против ограничений домена
        return True
    
    async def _apply_specialized_domain_config(self, domain_type: DomainType, config: Dict[str, Any]):
        """Применить специфическую конфигурацию домена"""
        # Применить специфические настройки для домена
        if "security_policy" in config:
            self._domain_security_policies[domain_type] = config["security_policy"]
        
        if "resource_limits" in config:
            self._domain_resource_limits[domain_type] = config["resource_limits"]
        
        if "compliance_rules" in config:
            self._domain_compliance_rules[domain_type] = config["compliance_rules"]
    
    async def _log_domain_adaptation(self, agent_id: str, domain_type: DomainType, capabilities: List[str]):
        """Залогировать адаптацию агента к домену"""
        log_entry = {
            "timestamp": time.time(),
            "agent_id": agent_id,
            "domain_type": domain_type.value,
            "capabilities": capabilities,
            "event_type": "domain_adaptation"
        }
        
        self._domain_audit_log.append(log_entry)
        
        # Ограничить размер лога
        if len(self._domain_audit_log) > 10000:  # Максимум 10,000 записей
            self._domain_audit_log = self._domain_audit_log[-10000:]
    
    def _load_specialized_policies(self):
        """Загрузить специфические политики"""
        # Загрузить политики безопасности для каждого домена
        default_security_policies = {
            DomainType.SECURITY_ANALYSIS: {
                "required_features": ["encryption_enabled", "audit_logging_enabled"],
                "restrictions": ["no_external_network_access", "sandbox_execution"]
            },
            DomainType.CODE_ANALYSIS: {
                "required_features": ["file_access_control", "code_isolation"],
                "restrictions": ["read_only_file_access", "no_system_command_execution"]
            },
            DomainType.DATA_PROCESSING: {
                "required_features": ["data_masking_enabled", "privacy_controls"],
                "restrictions": ["no_sensitive_data_storage", "encrypted_transmission"]
            }
        }
        
        self._domain_security_policies = default_security_policies
    
    def get_domain_security_policy(self, domain_type: DomainType) -> Dict[str, Any]:
        """Получить политику безопасности домена"""
        return self._domain_security_policies.get(domain_type, {})
    
    def get_domain_resource_limits(self, domain_type: DomainType) -> Dict[str, Any]:
        """Получить ограничения ресурсов домена"""
        return self._domain_resource_limits.get(domain_type, {})
    
    def get_domain_compliance_rules(self, domain_type: DomainType) -> List[Dict[str, Any]]:
        """Получить правила соответствия домена"""
        return self._domain_compliance_rules.get(domain_type, [])
    
    def get_domain_audit_log(self, domain_type: DomainType = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Получить лог аудита домена"""
        if domain_type:
            domain_logs = [
                entry for entry in self._domain_audit_log 
                if entry["domain_type"] == domain_type.value
            ]
        else:
            domain_logs = self._domain_audit_log
        
        return domain_logs[-limit:] if limit else domain_logs
```

### 3. Специфический менеджер конфигурации

Для управления конфигурацией с учетом специфических требований:

```python
class SpecializedConfigurationManager(ConfigurationManager):
    """Специфический менеджер конфигурации с расширенными возможностями"""
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        
        # Специфические настройки
        self._config_encryption_enabled = config.get("encrypt_sensitive_config", False)
        self._config_validation_schemas = {}
        self._config_change_subscribers = {}
        self._config_backup_manager = ConfigBackupManager(
            backup_location=config.get("backup_location", "./config_backups/")
        )
        self._config_audit_logger = ConfigAuditLogger()
        
        # Инициализировать шифрование, если включено
        if self._config_encryption_enabled:
            self._config_cipher = self._initialize_encryption()
    
    async def load_config(self, source: ConfigSource, location: str = None) -> Dict[str, Any]:
        """Загрузить конфигурацию с дополнительной обработкой"""
        # Выполнить базовую загрузку
        config_data = await super().load_config(source, location)
        
        # Расшифровать конфигурацию, если она была зашифрована
        if self._config_encryption_enabled:
            config_data = self._decrypt_config_data(config_data)
        
        # Применить специфическую валидацию
        validated_config = await self._apply_specialized_validation(config_data, source)
        
        # Залогировать изменение конфигурации
        await self._audit_config_change("load", source.value, validated_config)
        
        return validated_config
    
    async def save_config(self, config: Dict[str, Any], destination: ConfigSource, location: str = None):
        """Сохранить конфигурацию с дополнительной обработкой"""
        # Создать резервную копию перед сохранением
        await self._config_backup_manager.create_backup(config)
        
        # Зашифровать чувствительные данные, если включено шифрование
        if self._config_encryption_enabled:
            config = self._encrypt_config_data(config)
        
        # Выполнить базовое сохранение
        await super().save_config(config, destination, location)
        
        # Залогировать изменение конфигурации
        await self._audit_config_change("save", destination.value, config)
        
        # Уведомить подписчиков об изменении
        await self._notify_config_subscribers(destination.value, config)
    
    def get_config_value(self, path: str, default: Any = None) -> Any:
        """Получить значение конфигурации с дополнительной обработкой"""
        value = super().get_config_value(path, default)
        
        # Расшифровать значение, если оно зашифровано
        if self._config_encryption_enabled and isinstance(value, str) and value.startswith("ENCRYPTED:"):
            value = self._decrypt_value(value)
        
        return value
    
    def set_config_value(self, path: str, value: Any):
        """Установить значение конфигурации с дополнительной обработкой"""
        # Зашифровать чувствительные значения, если включено шифрование
        if self._config_encryption_enabled and self._is_sensitive_path(path):
            value = self._encrypt_value(value)
        
        # Выполнить базовую установку
        super().set_config_value(path, value)
        
        # Залогировать изменение
        asyncio.create_task(
            self._audit_config_change("set", path, {path.split('.')[-1]: value})
        )
    
    def _encrypt_config_data(self, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """Зашифровать чувствительные данные в конфигурации"""
        encrypted_config = {}
        
        for key, value in config_data.items():
            if isinstance(value, dict):
                encrypted_config[key] = self._encrypt_config_data(value)
            elif self._is_sensitive_key(key):
                encrypted_config[key] = f"ENCRYPTED:{self._encrypt_value(value)}"
            else:
                encrypted_config[key] = value
        
        return encrypted_config
    
    def _decrypt_config_data(self, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """Расшифровать зашифрованные данные в конфигурации"""
        decrypted_config = {}
        
        for key, value in config_data.items():
            if isinstance(value, dict):
                decrypted_config[key] = self._decrypt_config_data(value)
            elif isinstance(value, str) and value.startswith("ENCRYPTED:"):
                decrypted_config[key] = self._decrypt_value(value)
            else:
                decrypted_config[key] = value
        
        return decrypted_config
    
    def _is_sensitive_key(self, key: str) -> bool:
        """Проверить, является ли ключ чувствительным"""
        sensitive_keywords = [
            'password', 'token', 'api_key', 'secret', 'credential', 
            'private_key', 'certificate', 'oauth', 'auth'
        ]
        
        key_lower = key.lower()
        return any(keyword in key_lower for keyword in sensitive_keywords)
    
    def _is_sensitive_path(self, path: str) -> bool:
        """Проверить, является ли путь к конфигурации чувствительным"""
        # Проверить, содержит ли путь чувствительные ключи
        path_parts = path.lower().split('.')
        return any(self._is_sensitive_key(part) for part in path_parts)
    
    def _encrypt_value(self, value: Any) -> str:
        """Зашифровать значение"""
        # В реальной реализации здесь будет шифрование
        # например, с использованием Fernet или AES
        import json
        serialized_value = json.dumps(value, default=str)
        # Заглушка для шифрования
        return f"ENCRYPTED:{serialized_value}"
    
    def _decrypt_value(self, encrypted_value: str) -> Any:
        """Расшифровать значение"""
        # В реальной реализации здесь будет расшифровка
        import json
        encrypted_part = encrypted_value.replace("ENCRYPTED:", "", 1)
        return json.loads(encrypted_part)
    
    def _initialize_encryption(self) -> Any:
        """Инициализировать шифрование"""
        # В реальной реализации здесь будет инициализация шифрования
        # например, генерация ключа или загрузка из безопасного хранилища
        pass
    
    async def _apply_specialized_validation(self, config_data: Dict[str, Any], source: ConfigSource) -> Dict[str, Any]:
        """Применить специфическую валидацию к конфигурации"""
        schema = self._config_validation_schemas.get(source)
        
        if schema:
            # Выполнить валидацию по схеме
            return await self._validate_against_schema(config_data, schema)
        
        return config_data
    
    async def _validate_against_schema(self, config_data: Dict[str, Any], schema: Dict[str, Any]) -> Dict[str, Any]:
        """Валидировать конфигурацию по схеме"""
        # В реальной реализации здесь будет валидация по JSON Schema
        # или другой системе валидации
        return config_data
    
    async def _audit_config_change(self, action: str, location: str, config_part: Dict[str, Any]):
        """Залогировать изменение конфигурации"""
        await self._config_audit_logger.log_change(
            action=action,
            source=location,
            changed_values=config_part,
            timestamp=time.time()
        )
    
    async def _notify_config_subscribers(self, config_path: str, new_config: Dict[str, Any]):
        """Уведомить подписчиков об изменении конфигурации"""
        if config_path in self._config_change_subscribers:
            for subscriber in self._config_change_subscribers[config_path]:
                try:
                    await subscriber(new_config)
                except Exception as e:
                    print(f"Ошибка при уведомлении подписчика конфигурации: {e}")
    
    def subscribe_to_config_changes(self, config_path: str, callback: Callable):
        """Подписаться на изменения конфигурации"""
        if config_path not in self._config_change_subscribers:
            self._config_change_subscribers[config_path] = []
        
        self._config_change_subscribers[config_path].append(callback)
    
    def register_validation_schema(self, source: ConfigSource, schema: Dict[str, Any]):
        """Зарегистрировать схему валидации для источника"""
        self._config_validation_schemas[source] = schema
    
    async def get_config_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Получить историю изменений конфигурации"""
        return await self._config_audit_logger.get_change_history(limit)
    
    async def rollback_config(self, version_id: str) -> bool:
        """Откатить конфигурацию к предыдущей версии"""
        backup = await self._config_backup_manager.get_backup(version_id)
        
        if backup:
            # Восстановить конфигурацию из резервной копии
            self.config = backup
            await self._audit_config_change("rollback", version_id, backup)
            return True
        
        return False
    
    def get_effective_config_with_metadata(self) -> Dict[str, Any]:
        """Получить эффективную конфигурацию с метаданными"""
        effective_config = self.get_effective_config()
        
        return {
            "config": effective_config,
            "metadata": {
                "loaded_sources": list(self._loaded_configs.keys()),
                "encryption_enabled": self._config_encryption_enabled,
                "validation_schemas_count": len(self._config_validation_schemas),
                "change_subscribers_count": len(self._config_change_subscribers)
            }
        }
```

## Интеграция специфических компонентов

### 1. Фабрика специфических компонентов

Для создания и управления специфическими системными компонентами:

```python
# application/factories/specialized_component_factory.py
from typing import Type, Dict, Any
from domain.abstractions.lifecycle import ILifecycleManager
from domain.abstractions.domain_management import IDomainManager
from domain.abstractions.config_system import IConfigurationManager
from application.managers.specialized_lifecycle import SpecializedLifecycleManager
from application.managers.specialized_domain import SpecializedDomainManager
from application.managers.specialized_config import SpecializedConfigurationManager

class SpecializedComponentFactory:
    """Фабрика для создания специфических системных компонентов"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self._registered_lifecycle_types = {}
        self._registered_domain_types = {}
        self._registered_config_types = {}
        
        # Зарегистрировать встроенные типы
        self._register_builtin_types()
    
    def _register_builtin_types(self):
        """Зарегистрировать встроенные типы компонентов"""
        self.register_lifecycle_type("specialized", SpecializedLifecycleManager)
        self.register_domain_type("specialized", SpecializedDomainManager)
        self.register_config_type("specialized", SpecializedConfigurationManager)
    
    def register_lifecycle_type(self, name: str, lifecycle_class: Type[ILifecycleManager]):
        """Зарегистрировать тип менеджера жизненного цикла"""
        self._registered_lifecycle_types[name] = lifecycle_class
    
    def register_domain_type(self, name: str, domain_class: Type[IDomainManager]):
        """Зарегистрировать тип менеджера доменов"""
        self._registered_domain_types[name] = domain_class
    
    def register_config_type(self, name: str, config_class: Type[IConfigurationManager]):
        """Зарегистрировать тип менеджера конфигурации"""
        self._registered_config_types[name] = config_class
    
    async def create_lifecycle_manager(self, manager_type: str, config: Dict[str, Any] = None) -> ILifecycleManager:
        """Создать менеджер жизненного цикла"""
        if manager_type not in self._registered_lifecycle_types:
            raise ValueError(f"Тип менеджера жизненного цикла '{manager_type}' не зарегистрирован")
        
        manager_class = self._registered_lifecycle_types[manager_type]
        full_config = {**self.config.get("lifecycle_defaults", {}), **(config or {})}
        
        manager = manager_class(full_config)
        return manager
    
    async def create_domain_manager(self, manager_type: str, config: Dict[str, Any] = None) -> IDomainManager:
        """Создать менеджер доменов"""
        if manager_type not in self._registered_domain_types:
            raise ValueError(f"Тип менеджера доменов '{manager_type}' не зарегистрирован")
        
        manager_class = self._registered_domain_types[manager_type]
        full_config = {**self.config.get("domain_defaults", {}), **(config or {})}
        
        manager = manager_class(full_config)
        return manager
    
    async def create_config_manager(self, manager_type: str, config: Dict[str, Any] = None) -> IConfigurationManager:
        """Создать менеджер конфигурации"""
        if manager_type not in self._registered_config_types:
            raise ValueError(f"Тип менеджера конфигурации '{manager_type}' не зарегистрирован")
        
        manager_class = self._registered_config_types[manager_type]
        full_config = {**self.config.get("config_defaults", {}), **(config or {})}
        
        manager = manager_class(full_config)
        return manager
    
    def get_available_lifecycle_types(self) -> List[str]:
        """Получить доступные типы менеджеров жизненного цикла"""
        return list(self._registered_lifecycle_types.keys())
    
    def get_available_domain_types(self) -> List[str]:
        """Получить доступные типы менеджеров доменов"""
        return list(self._registered_domain_types.keys())
    
    def get_available_config_types(self) -> List[str]:
        """Получить доступные типы менеджеров конфигурации"""
        return list(self._registered_config_types.keys())

class AdvancedSystemFactory(SpecializedComponentFactory):
    """Расширенная фабрика системных компонентов с поддержкой сложных конфигураций"""
    
    def __init__(self, base_config: Dict[str, Any] = None):
        super().__init__(base_config)
        self._middleware_registry = {}
        self._validator_registry = {}
        self._enricher_registry = {}
    
    async def create_configurable_lifecycle_manager(
        self,
        manager_type: str,
        config: Dict[str, Any] = None,
        middleware: List[Callable] = None,
        validators: List[Callable] = None,
        enrichers: List[Callable] = None
    ) -> ILifecycleManager:
        """Создать настраиваемый менеджер жизненного цикла"""
        
        # Создать базовый менеджер
        manager = await self.create_lifecycle_manager(manager_type, config)
        
        # Добавить middleware
        if middleware:
            for mw_func in middleware:
                if hasattr(manager, 'add_middleware'):
                    manager.add_middleware(mw_func)
        
        # Добавить валидаторы
        if validators:
            for validator_func in validators:
                if hasattr(manager, 'add_validator'):
                    manager.add_validator(validator_func)
        
        # Добавить enrichers
        if enrichers:
            for enricher_func in enrichers:
                if hasattr(manager, 'add_enricher'):
                    manager.add_enricher(enricher_func)
        
        return manager
    
    def register_middleware(self, name: str, middleware_func: Callable):
        """Зарегистрировать middleware"""
        self._middleware_registry[name] = middleware_func
    
    def register_validator(self, name: str, validator_func: Callable):
        """Зарегистрировать валидатор"""
        self._validator_registry[name] = validator_func
    
    def register_enricher(self, name: str, enricher_func: Callable):
        """Зарегистрировать enricher"""
        self._enricher_registry[name] = enricher_func
    
    def get_registered_component(self, component_type: str, name: str):
        """Получить зарегистрированный компонент"""
        registries = {
            "middleware": self._middleware_registry,
            "validator": self._validator_registry,
            "enricher": self._enricher_registry
        }
        
        if component_type in registries:
            return registries[component_type].get(name)
        return None
```

### 2. Использование специфических компонентов

Пример использования специфических системных компонентов:

```python
# specialized_system_components_usage.py
from application.factories.advanced_system_factory import AdvancedSystemFactory
from domain.value_objects.domain_type import DomainType

async def specialized_system_components_example():
    """Пример использования специфических системных компонентов"""
    
    # Создать расширенную фабрику
    factory = AdvancedSystemFactory({
        "lifecycle_defaults": {
            "max_memory": "2GB",
            "enable_security_monitoring": True
        },
        "domain_defaults": {
            "enable_compliance_checking": True,
            "audit_logging_enabled": True
        },
        "config_defaults": {
            "encrypt_sensitive_values": True,
            "backup_config_changes": True
        }
    })
    
    # Зарегистрировать специфические middleware
    def security_enrichment_middleware(config):
        """Middleware для обогащения конфигурации безопасности"""
        if "security" not in config:
            config["security"] = {}
        config["security"]["monitoring_enabled"] = True
        return config
    
    def resource_validation_validator(config):
        """Валидатор ограничений ресурсов"""
        max_memory = config.get("max_memory", "1GB")
        # Проверка, что ограничение памяти в допустимом диапазоне
        if "TB" in max_memory or "PB" in max_memory:
            raise ValueError("Ограничение памяти слишком велико")
        return True
    
    factory.register_middleware("security_enrichment", security_enrichment_middleware)
    factory.register_validator("resource_limits", resource_validation_validator)
    
    # Создать специфический менеджер жизненного цикла
    lifecycle_manager = await factory.create_configurable_lifecycle_manager(
        "specialized",
        config={
            "max_memory": "1GB",
            "security_monitoring": True,
            "performance_metrics_collection": True
        },
        middleware=[factory.get_registered_component("middleware", "security_enrichment")],
        validators=[factory.get_registered_component("validator", "resource_limits")]
    )
    
    # Создать специфический менеджер доменов
    domain_manager = await factory.create_domain_manager(
        "specialized",
        config={
            "enable_security_policies": True,
            "compliance_rules_enabled": True,
            "audit_logging": True
        }
    )
    
    # Создать специфический менеджер конфигурации
    config_manager = await factory.create_config_manager(
        "specialized", 
        config={
            "encrypt_sensitive_config": True,
            "backup_enabled": True,
            "validation_enabled": True
        }
    )
    
    # Инициализировать компоненты
    await lifecycle_manager.initialize()
    await domain_manager.register_domain(DomainType.CODE_ANALYSIS, {
        "capabilities": ["security_analysis", "code_quality", "best_practices"],
        "security_policy": {
            "required_features": ["encryption_enabled", "audit_logging_enabled"]
        },
        "resource_limits": {
            "memory": "2GB",
            "cpu": 50.0  # percentage
        }
    })
    
    # Установить конфигурацию
    await config_manager.load_config(ConfigSource.DEFAULT)
    config_manager.set_config_value("agent.max_iterations", 100)
    config_manager.set_config_value("llm.temperature", 0.5)
    
    # Использовать компоненты в системе
    print("Специфические системные компоненты успешно созданы и инициализированы")
    print(f"Статус менеджера жизненного цикла: {lifecycle_manager.get_status()}")
    print(f"Зарегистрированные домены: {list(domain_manager.get_all_registered_domains())}")
    print(f"Значение конфигурации agent.max_iterations: {config_manager.get_config_value('agent.max_iterations')}")
    
    # Получить детализированный статус
    if hasattr(lifecycle_manager, 'get_detailed_status'):
        detailed_status = lifecycle_manager.get_detailed_status()
        print(f"Детализированный статус: {detailed_status}")
    
    return {
        "lifecycle_manager": lifecycle_manager,
        "domain_manager": domain_manager, 
        "config_manager": config_manager
    }

# Интеграция с агентами
async def agent_system_integration_example():
    """Пример интеграции специфических системных компонентов с агентами"""
    
    # Создать фабрику агентов
    from application.factories.agent_factory import AgentFactory
    agent_factory = AgentFactory()
    
    # Создать специфические системные компоненты
    system_factory = AdvancedSystemFactory()
    
    # Создать менеджер жизненного цикла для агента
    agent_lifecycle = await system_factory.create_lifecycle_manager(
        "specialized",
        config={
            "max_memory_per_agent": "512MB",
            "security_monitoring_enabled": True,
            "resource_quota_per_agent": {"cpu": 25.0, "memory": "512MB"}
        }
    )
    
    # Создать менеджер доменов для агента
    agent_domain_manager = await system_factory.create_domain_manager(
        "specialized",
        config={
            "enable_domain_isolation": True,
            "compliance_checking_enabled": True
        }
    )
    
    # Создать менеджер конфигурации для агента
    agent_config_manager = await system_factory.create_config_manager(
        "specialized",
        config={
            "per_agent_config_encryption": True,
            "config_validation_on_set": True
        }
    )
    
    # Создать агента с использованием специфических компонентов
    agent = await agent_factory.create_agent(
        agent_type="composable",
        domain=DomainType.CODE_ANALYSIS,
        lifecycle_manager=agent_lifecycle,
        domain_manager=agent_domain_manager,
        config_manager=agent_config_manager
    )
    
    # Адаптировать агента к домену
    await agent_domain_manager.adapt_agent_to_domain(
        agent_id=id(agent),
        domain_type=DomainType.CODE_ANALYSIS,
        capabilities=["security_analysis", "code_quality", "dependency_checking"]
    )
    
    # Настроить конфигурацию агента
    agent_config_manager.set_config_value("agent.max_iterations", 75)
    agent_config_manager.set_config_value("agent.timeout", 600)
    
    # Выполнить задачу через агента
    result = await agent.execute_task(
        task_description="Проанализируй этот Python код на безопасность и качество",
        context={
            "code": """
def insecure_login(username, password):
    query = f"SELECT * FROM users WHERE username='{username}' AND password='{password}'"
    return execute_query(query)
""",
            "language": "python"
        }
    )
    
    print(f"Результат выполнения задачи через агента: {result}")
    
    # Получить статус системных компонентов
    lifecycle_status = agent_lifecycle.get_status_info()
    print(f"Статус жизненного цикла агента: {lifecycle_status}")
    
    agent_config = agent_config_manager.get_effective_config_with_metadata()
    print(f"Конфигурация агента: {agent_config['metadata']}")
    
    return result
```

## Лучшие практики

### 1. Модульность и расширяемость

Создавайте системные компоненты, которые можно легко расширять:

```python
# Хорошо: модульные и расширяемые компоненты
class BaseLifecycleManager:
    """Базовый менеджер жизненного цикла"""
    pass

class ExtendedLifecycleManager(BaseLifecycleManager):
    """Расширенный менеджер жизненного цикла"""
    pass

class SpecializedLifecycleManager(ExtendedLifecycleManager):
    """Специализированный менеджер жизненного цикла"""
    pass

# Плохо: монолитный компонент
class MonolithicLifecycleManager:
    """Монолитный менеджер жизненного цикла - сложно расширять и тестировать"""
    pass
```

### 2. Безопасность и конфиденциальность

Обязательно учитывайте безопасность при создании системных компонентов:

```python
def _filter_sensitive_config_data(self, config_data: Dict[str, Any]) -> Dict[str, Any]:
    """Отфильтровать чувствительные данные из конфигурации"""
    if not config_data:
        return config_data
    
    filtered_config = config_data.copy()
    
    # Список чувствительных полей
    sensitive_fields = [
        "password", "token", "api_key", "secret", "credentials",
        "database_url", "ssh_key", "ssl_certificate"
    ]
    
    for key, value in filtered_config.items():
        if key in sensitive_fields:
            filtered_config[key] = "***FILTERED***"
        elif isinstance(value, dict):
            filtered_config[key] = self._filter_sensitive_config_data(value)
        elif isinstance(value, list):
            filtered_config[key] = [
                self._filter_sensitive_config_data(item) if isinstance(item, dict) else item
                for item in value
            ]
    
    return filtered_config
```

### 3. Обработка ошибок

Обеспечьте надежную обработку ошибок в системных компонентах:

```python
async def initialize(self):
    """Инициализировать компонент с надежной обработкой ошибок"""
    try:
        self.status = ComponentStatus.INITIALIZING
        
        # Проверить зависимости
        await self._verify_dependencies()
        
        # Выполнить основную инициализацию
        await self._perform_initialization()
        
        # Проверить здоровье после инициализации
        health_status = await self._check_health()
        if not health_status["healthy"]:
            raise RuntimeError(f"Компонент нездоров после инициализации: {health_status['issues']}")
        
        self.status = ComponentStatus.INITIALIZED
        self._log_event("initialized", {"status": "success"})
        
        return {"success": True, "status": self.status.value}
    except ResourceLimitExceededError as e:
        self.status = ComponentStatus.FAILED
        self._last_error = str(e)
        self._error_count += 1
        self._log_error(f"Превышено ограничение ресурсов при инициализации: {str(e)}")
        return {"success": False, "error": str(e), "error_type": "resource_limit"}
    except SecurityError as e:
        self.status = ComponentStatus.FAILED
        self._last_error = str(e)
        self._error_count += 1
        self._log_error(f"Ошибка безопасности при инициализации: {str(e)}")
        return {"success": False, "error": str(e), "error_type": "security", "critical": True}
    except Exception as e:
        self.status = ComponentStatus.FAILED
        self._last_error = str(e)
        self._error_count += 1
        self._log_error(f"Внутренняя ошибка при инициализации: {str(e)}")
        return {"success": False, "error": str(e), "error_type": "internal"}

def _validate_config_before_application(self, config: Dict[str, Any]) -> bool:
    """Проверить конфигурацию перед применением"""
    # Проверить, что конфигурация не пуста
    if not config:
        return False
    
    # Проверить критические параметры
    critical_params = ["max_memory", "timeout", "max_iterations"]
    for param in critical_params:
        if param in config:
            value = config[param]
            if not self._is_valid_parameter_value(param, value):
                return False
    
    return True

def _is_valid_parameter_value(self, param_name: str, param_value: Any) -> bool:
    """Проверить, является ли значение параметра допустимым"""
    validators = {
        "max_memory": lambda x: isinstance(x, str) and (x.endswith('MB') or x.endswith('GB')),
        "timeout": lambda x: isinstance(x, (int, float)) and x > 0,
        "max_iterations": lambda x: isinstance(x, int) and x > 0
    }
    
    validator = validators.get(param_name)
    if validator:
        return validator(param_value)
    
    # Для неизвестных параметров считаем, что значение допустимо
    return True
```

### 4. Тестирование специфических компонентов

Создавайте тесты для каждого специфического компонента:

```python
# test_specialized_system_components.py
import pytest
from unittest.mock import AsyncMock, Mock, patch
import tempfile
import os

class TestSpecializedLifecycleManager:
    @pytest.mark.asyncio
    async def test_lifecycle_manager_initialization(self):
        """Тест инициализации специфического менеджера жизненного цикла"""
        # Создать моки зависимостей
        mock_resource_manager = AsyncMock()
        mock_security_monitor = AsyncMock()
        mock_performance_monitor = AsyncMock()
        
        # Создать специфический менеджер
        lifecycle_manager = SpecializedLifecycleManager({
            "max_memory": "1GB",
            "security_monitoring": True
        })
        
        # Инициализировать менеджер
        await lifecycle_manager.initialize()
        
        # Проверить статус
        assert lifecycle_manager.get_status() == ComponentStatus.INITIALIZED
        
        # Проверить, что зависимости были инициализированы
        mock_resource_manager.initialize.assert_called_once()
        mock_security_monitor.initialize.assert_called_once()
        mock_performance_monitor.initialize.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_lifecycle_manager_with_resource_limit_exceeded(self):
        """Тест менеджера жизненного цикла при превышении ограничений ресурсов"""
        # Создать менеджер с ограничениями
        manager = SpecializedLifecycleManager({
            "max_memory": "100MB",  # Очень маленькое ограничение для теста
            "security_monitoring": False
        })
        
        # Мокнуть проверку ресурсов, чтобы она возвращала превышение
        with patch.object(manager._resource_manager, 'get_status', 
                         return_value={"available": False, "details": {"memory": "only 50MB available"}}):
            
            # Попробовать инициализировать - должно вызвать ошибку
            with pytest.raises(RuntimeError, match="resource availability"):
                await manager.initialize()
        
        # Проверить, что статус стал FAILED
        assert manager.get_status() == ComponentStatus.FAILED

class TestSpecializedDomainManager:
    @pytest.mark.asyncio
    async def test_domain_registration_with_security_check(self):
        """Тест регистрации домена с проверкой безопасности"""
        # Создать менеджер доменов
        domain_manager = SpecializedDomainManager({
            "security_policies_enabled": True
        })
        
        # Зарегистрировать домен с правильной конфигурацией безопасности
        await domain_manager.register_domain(
            DomainType.SECURITY_ANALYSIS,
            {
                "capabilities": ["vulnerability_scanning"],
                "security_policy": {
                    "required_features": ["encryption_enabled", "audit_logging_enabled"]
                },
                "encryption_enabled": True,
                "audit_logging_enabled": True
            }
        )
        
        # Проверить, что домен зарегистрирован
        capabilities = domain_manager.get_domain_capabilities(DomainType.SECURITY_ANALYSIS)
        assert "vulnerability_scanning" in capabilities
        
        # Проверить политику безопасности
        security_policy = domain_manager.get_domain_security_policy(DomainType.SECURITY_ANALYSIS)
        assert security_policy["required_features"] == ["encryption_enabled", "audit_logging_enabled"]
    
    @pytest.mark.asyncio
    async def test_agent_domain_adaptation(self):
        """Тест адаптации агента к домену"""
        domain_manager = SpecializedDomainManager()
        
        # Зарегистрировать домен
        await domain_manager.register_domain(
            DomainType.CODE_ANALYSIS,
            {
                "capabilities": ["security_analysis", "code_quality"]
            }
        )
        
        # Адаптировать агента к домену
        await domain_manager.adapt_agent_to_domain(
            "agent_123",
            DomainType.CODE_ANALYSIS,
            ["security_analysis"]
        )
        
        # Проверить, что агент адаптирован
        agent_info = domain_manager.get_agent_domain_info("agent_123")
        assert agent_info is not None
        assert agent_info["domain_type"] == DomainType.CODE_ANALYSIS
        assert "security_analysis" in agent_info["capabilities"]

class TestSpecializedConfigurationManager:
    @pytest.mark.asyncio
    async def test_config_encryption_decryption(self):
        """Тест шифрования и расшифровки конфигурации"""
        # Создать менеджер с включенным шифрованием
        config_manager = SpecializedConfigurationManager({
            "encrypt_sensitive_config": True
        })
        
        # Установить чувствительное значение
        config_manager.set_config_value("database.password", "secret_password")
        
        # Получить значение - оно должно быть зашифровано
        encrypted_value = config_manager.get_config_value("database.password")
        
        # Значение должно быть строкой и начинаться с "ENCRYPTED:"
        assert isinstance(encrypted_value, str)
        assert encrypted_value.startswith("ENCRYPTED:")
        
        # Но при получении оно должно быть расшифровано
        assert encrypted_value == "secret_password"  # После расшифровки
    
    @pytest.mark.asyncio
    async def test_config_validation(self):
        """Тест валидации конфигурации"""
        config_manager = SpecializedConfigurationManager()
        
        # Установить значение
        config_manager.set_config_value("agent.max_iterations", 50)
        
        # Попробовать установить недопустимое значение
        # (в реальной реализации здесь должна быть проверка)
        with pytest.raises(ValueError):
            # В специфической реализации может быть проверка на допустимость значения
            pass  # Тест будет зависеть от конкретной реализации валидации
    
    def test_sensitive_data_filtering(self):
        """Тест фильтрации чувствительных данных"""
        config_manager = SpecializedConfigurationManager()
        
        test_config = {
            "normal_setting": "value",
            "password": "secret123",
            "api_key": "key123",
            "nested": {
                "token": "token123",
                "other": "value"
            }
        }
        
        filtered_config = config_manager._filter_sensitive_config_data(test_config)
        
        assert filtered_config["normal_setting"] == "value"
        assert filtered_config["password"] == "***FILTERED***"
        assert filtered_config["api_key"] == "***FILTERED***"
        assert filtered_config["nested"]["token"] == "***FILTERED***"
        assert filtered_config["nested"]["other"] == "value"
```

Эти примеры показывают, как адаптировать и расширять архитектурные компоненты Composable AI Agent Framework под специфические задачи, обеспечивая модульность, безопасность и надежность системы.
</final_file_content>

IMPORTANT: For any future changes to this file, use the final_file_content shown above as your reference. This content reflects the current state of the file, including any auto-formatting (e.g., if you used single quotes but the formatter converted them to double quotes). Always base your SEARCH/REPLACE operations on this final version to ensure accuracy.