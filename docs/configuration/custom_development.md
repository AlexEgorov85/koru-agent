# Разработка системы конфигурации под свои задачи

В этом разделе описаны рекомендации и практики по адаптации и расширению системы конфигурации Koru AI Agent Framework для удовлетворения специфических требований и задач. Вы узнаете, как модифицировать существующую систему конфигурации и создавать новые компоненты для расширения функциональности системы.

## Архитектура системы конфигурации

### 1. Модели конфигурации

Модели конфигурации определяют структуру данных конфигурации:

```python
# config/models.py
from pydantic import BaseModel, Field, validator
from typing import Dict, List, Optional, Any
from enum import Enum
import json

class LLMProviderType(str, Enum):
    """Типы LLM провайдеров"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    HUGGINGFACE = "huggingface"
    CUSTOM = "custom"

class LogLevels(str, Enum):
    """Уровни логирования"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

class AgentConfig(BaseModel):
    """Конфигурация агента"""
    name: str = Field(..., description="Имя агента")
    max_iterations: int = Field(default=50, ge=1, le=1000, description="Максимальное количество итераций")
    timeout: int = Field(default=300, ge=1, description="Таймаут выполнения задачи в секундах")
    enable_logging: bool = Field(default=True, description="Включить логирование")
    max_concurrent_actions: int = Field(default=5, ge=1, le=100, description="Максимальное количество параллельных действий")
    memory_limit: str = Field(default="1GB", description="Ограничение памяти")
    retry_attempts: int = Field(default=3, ge=0, le=10, description="Количество попыток повтора при ошибках")
    error_retry_delay: float = Field(default=1.0, ge=0.1, le=10.0, description="Задержка между повторами в секундах")
    progress_threshold: int = Field(default=5, ge=1, le=100, description="Порог шагов без прогресса для срабатывания ошибки")
    allowed_domains: List[str] = Field(default_factory=list, description="Разрешенные домены для агента")

class LLMConfig(BaseModel):
    """Конфигурация LLM"""
    provider: LLMProviderType = Field(default=LLMProviderType.OPENAI, description="Тип провайдера LLM")
    model: str = Field(default="gpt-4", description="Название модели")
    api_key: Optional[str] = Field(default=None, description="API ключ")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="Температура генерации")
    max_tokens: int = Field(default=2048, ge=1, le=4096, description="Максимальное количество токенов")
    base_url: Optional[str] = Field(default=None, description="Базовый URL для API")
    request_timeout: float = Field(default=30.0, ge=1.0, le=300.0, description="Таймаут запроса к LLM")
    max_retries: int = Field(default=3, ge=0, le=10, description="Максимальное количество повторов запроса")
    custom_parameters: Dict[str, Any] = Field(default_factory=dict, description="Пользовательские параметры")

class PromptConfig(BaseModel):
    """Конфигурация системы промтов"""
    storage_path: str = Field(default="./prompts", description="Путь к хранилищу промтов")
    cache_enabled: bool = Field(default=True, description="Включить кэширование промтов")
    cache_ttl: int = Field(default=3600, ge=60, le=86400, description="Время жизни кэша в секундах")
    validation_enabled: bool = Field(default=True, description="Включить валидацию промтов")
    version_check_enabled: bool = Field(default=True, description="Включить проверку версий промтов")
    security_validation_enabled: bool = Field(default=True, description="Включить проверку безопасности промтов")
    max_file_size: int = Field(default=1048576, ge=1024, le=10485760, description="Максимальный размер файла промта в байтах")

class SystemConfig(BaseModel):
    """Конфигурация всей системы"""
    agent: AgentConfig = Field(default_factory=AgentConfig, description="Конфигурация агента")
    llm: LLMConfig = Field(default_factory=LLMConfig, description="Конфигурация LLM")
    prompts: PromptConfig = Field(default_factory=PromptConfig, description="Конфигурация промтов")
    debug_mode: bool = Field(default=False, description="Режим отладки")
    log_level: LogLevels = Field(default=LogLevels.INFO, description="Уровень логирования")
    enable_monitoring: bool = Field(default=True, description="Включить мониторинг")
    monitoring_interval: float = Field(default=5.0, ge=0.1, le=60.0, description="Интервал мониторинга в секундах")
    security_checks_enabled: bool = Field(default=True, description="Включить проверки безопасности")
    resource_limits: Dict[str, Any] = Field(default_factory=dict, description="Ограничения ресурсов")
    custom_settings: Dict[str, Any] = Field(default_factory=dict, description="Пользовательские настройки")

class CustomConfig(SystemConfig):
    """Специфическая конфигурация для конкретных задач"""
    task_specific_settings: Dict[str, Any] = Field(default_factory=dict, description="Настройки для специфических задач")
    domain_specific_config: Dict[str, Any] = Field(default_factory=dict, description="Конфигурация для специфических доменов")
    custom_validators: List[str] = Field(default_factory=list, description="Пользовательские валидаторы")
    extended_capabilities: List[str] = Field(default_factory=list, description="Расширенные возможности")
```

### 2. Загрузчик конфигурации

Загрузчик конфигурации отвечает за загрузку и валидацию конфигурации:

```python
# config/config_loader.py
import yaml
import json
import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from pydantic import ValidationError
from config.models import SystemConfig, CustomConfig
import logging

class ConfigLoadError(Exception):
    """Исключение для ошибок загрузки конфигурации"""
    pass

class ConfigValidationError(Exception):
    """Исключение для ошибок валидации конфигурации"""
    pass

class ConfigLoader:
    """Загрузчик конфигурации системы"""
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or "config.yaml"
        self.default_config_path = "config/default_config.yaml"
        self.logger = logging.getLogger(__name__)
        
    async def load_config(self, config_type: str = "system") -> SystemConfig:
        """Загрузить конфигурацию из файла"""
        config_data = {}
        errors = []
        
        # Загрузка конфигурации из основного файла
        if Path(self.config_path).exists():
            config_data, load_errors = await self._load_from_file(self.config_path)
            errors.extend(load_errors)
        elif Path(self.default_config_path).exists():
            # Загрузка конфигурации по умолчанию если основной файл не найден
            config_data, load_errors = await self._load_from_file(self.default_config_path)
            errors.extend(load_errors)
        else:
            # Если ни один файл не найден, использовать значения по умолчанию
            config_data = {}
        
        # Загрузка конфигурации из переменных окружения
        env_config = self._load_from_environment()
        config_data = self._merge_configs(config_data, env_config)
        
        # Валидация конфигурации
        try:
            if config_type == "custom":
                validated_config = CustomConfig(**config_data)
            else:
                validated_config = SystemConfig(**config_data)
            
            self.logger.info(f"Конфигурация успешно загружена из {self.config_path}")
            return validated_config
        except ValidationError as e:
            error_msg = f"Ошибка валидации конфигурации: {e}"
            self.logger.error(error_msg)
            raise ConfigValidationError(error_msg)
    
    async def _load_from_file(self, file_path: str) -> Tuple[Dict[str, Any], List[str]]:
        """Загрузить конфигурацию из файла"""
        path = Path(file_path)
        errors = []
        
        try:
            if path.suffix.lower() in ['.yaml', '.yml']:
                with open(path, 'r', encoding='utf-8') as file:
                    content = file.read()
                    # Заменить переменные окружения в формате ${VAR_NAME}
                    content = self._substitute_env_vars(content)
                    data = yaml.safe_load(content) or {}
            elif path.suffix.lower() == '.json':
                with open(path, 'r', encoding='utf-8') as file:
                    content = file.read()
                    content = self._substitute_env_vars(content)
                    data = json.loads(content)
            else:
                raise ValueError(f"Неподдерживаемый формат файла: {path.suffix}")
            
            return data, errors
        except yaml.YAMLError as e:
            errors.append(f"Ошибка парсинга YAML в {file_path}: {str(e)}")
            return {}, errors
        except json.JSONDecodeError as e:
            errors.append(f"Ошибка парсинга JSON в {file_path}: {str(e)}")
            return {}, errors
        except Exception as e:
            errors.append(f"Ошибка загрузки конфигурации из {file_path}: {str(e)}")
            return {}, errors
    
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
    
    def _merge_configs(self, base_config: Dict[str, Any], override_config: Dict[str, Any]) -> Dict[str, Any]:
        """Объединить две конфигурации"""
        merged = base_config.copy()
        
        for key, value in override_config.items():
            if isinstance(value, dict) and key in merged and isinstance(merged[key], dict):
                merged[key] = self._merge_configs(merged[key], value)
            else:
                merged[key] = value
        
        return merged
```

## Расширение системы конфигурации

### 1. Создание специфических моделей конфигурации

Для адаптации системы конфигурации под специфические задачи:

```python
# config/specialized_models.py
from config.models import SystemConfig, AgentConfig, LLMConfig, PromptConfig
from typing import Dict, Any, List
from pydantic import Field

class SpecializedAgentConfig(AgentConfig):
    """Специфическая конфигурация агента для специфических задач"""
    task_types: List[str] = Field(default_factory=list, description="Поддерживаемые типы задач")
    domain_specific_params: Dict[str, Any] = Field(default_factory=dict, description="Параметры для специфических доменов")
    security_requirements: Dict[str, Any] = Field(default_factory=dict, description="Требования безопасности")
    performance_tuning: Dict[str, Any] = Field(default_factory=dict, description="Настройки производительности")
    custom_callbacks: List[str] = Field(default_factory=list, description="Пользовательские callback-функции")
    task_priority_mapping: Dict[str, str] = Field(default_factory=dict, description="Сопоставление задач с приоритетами")

class SpecializedLLMConfig(LLMConfig):
    """Специфическая конфигурация LLM для специфических задач"""
    model_specific_params: Dict[str, Any] = Field(default_factory=dict, description="Параметры для конкретной модели")
    custom_endpoints: Dict[str, str] = Field(default_factory=dict, description="Пользовательские endpoints")
    adaptive_temperature: bool = Field(default=False, description="Использовать адаптивную температуру")
    context_window_management: Dict[str, Any] = Field(default_factory=dict, description="Управление окном контекста")
    response_formatting: Dict[str, Any] = Field(default_factory=dict, description="Форматирование ответов")

class SpecializedPromptConfig(PromptConfig):
    """Специфическая конфигурация промтов для специфических задач"""
    prompt_optimization: Dict[str, Any] = Field(default_factory=dict, description="Настройки оптимизации промтов")
    dynamic_prompt_selection: bool = Field(default=False, description="Включить динамический выбор промтов")
    prompt_security_scanning: bool = Field(default=True, description="Включить сканирование безопасности промтов")
    prompt_ab_testing: Dict[str, Any] = Field(default_factory=dict, description="Настройки A/B тестирования промтов")
    custom_prompt_validators: List[str] = Field(default_factory=list, description="Пользовательские валидаторы промтов")

class SpecializedSystemConfig(SystemConfig):
    """Специфическая конфигурация системы для специфических задач"""
    specialized_agent: SpecializedAgentConfig = Field(default_factory=SpecializedAgentConfig, description="Специфическая конфигурация агента")
    specialized_llm: SpecializedLLMConfig = Field(default_factory=SpecializedLLMConfig, description="Специфическая конфигурация LLM")
    specialized_prompts: SpecializedPromptConfig = Field(default_factory=SpecializedPromptConfig, description="Специфическая конфигурация промтов")
    task_scheduler_config: Dict[str, Any] = Field(default_factory=dict, description="Конфигурация планировщика задач")
    resource_allocator_config: Dict[str, Any] = Field(default_factory=dict, description="Конфигурация распределителя ресурсов")
    custom_workflow_config: Dict[str, Any] = Field(default_factory=dict, description="Конфигурация пользовательских рабочих процессов")
    security_policy_config: Dict[str, Any] = Field(default_factory=dict, description="Конфигурация политики безопасности")

class DomainSpecificConfig(SpecializedSystemConfig):
    """Конфигурация для специфических доменов"""
    domain_name: str = Field(..., description="Название домена")
    domain_capabilities: List[str] = Field(default_factory=list, description="Возможности домена")
    domain_rules: List[Dict[str, Any]] = Field(default_factory=list, description="Правила домена")
    domain_models: List[Dict[str, Any]] = Field(default_factory=list, description="Модели, специфичные для домена")
    domain_integrations: List[Dict[str, Any]] = Field(default_factory=list, description="Интеграции домена")
```

### 2. Создание специфического загрузчика конфигурации

Для загрузки специфических конфигураций:

```python
# config/specialized_config_loader.py
from config.config_loader import ConfigLoader, ConfigLoadError, ConfigValidationError
from config.specialized_models import SpecializedSystemConfig, DomainSpecificConfig
from typing import Dict, Any, Optional
import yaml
from pathlib import Path

class SpecializedConfigLoader(ConfigLoader):
    """Специфический загрузчик конфигурации для специфических задач"""
    
    def __init__(self, config_path: Optional[str] = None, domain_config_path: Optional[str] = None):
        super().__init__(config_path)
        self.domain_config_path = domain_config_path or "config/domain_config.yaml"
        self.specialized_config_path = "config/specialized_config.yaml"
    
    async def load_specialized_config(self) -> SpecializedSystemConfig:
        """Загрузить специфическую конфигурацию"""
        config_data = {}
        errors = []
        
        # Загрузка основной специфической конфигурации
        if Path(self.specialized_config_path).exists():
            data, load_errors = await self._load_from_file(self.specialized_config_path)
            errors.extend(load_errors)
            config_data = self._merge_configs(config_data, data)
        
        # Загрузка конфигурации домена, если указана
        if self.domain_config_path and Path(self.domain_config_path).exists():
            domain_data, domain_errors = await self._load_from_file(self.domain_config_path)
            errors.extend(domain_errors)
            
            # Объединить с основной конфигурацией
            config_data = self._merge_configs(config_data, domain_data)
        
        # Загрузка из основного файла (если указан)
        if self.config_path and Path(self.config_path).exists():
            main_data, main_errors = await self._load_from_file(self.config_path)
            errors.extend(main_errors)
            config_data = self._merge_configs(config_data, main_data)
        
        # Загрузка из переменных окружения
        env_config = self._load_from_environment()
        config_data = self._merge_configs(config_data, env_config)
        
        # Валидация специфической конфигурации
        try:
            validated_config = SpecializedSystemConfig(**config_data)
            self.logger.info("Специфическая конфигурация успешно загружена")
            return validated_config
        except ValidationError as e:
            error_msg = f"Ошибка валидации специфической конфигурации: {e}"
            self.logger.error(error_msg)
            raise ConfigValidationError(error_msg)
    
    async def load_domain_config(self, domain_name: str) -> DomainSpecificConfig:
        """Загрузить конфигурацию для конкретного домена"""
        domain_config_path = f"config/domains/{domain_name}_config.yaml"
        
        if not Path(domain_config_path).exists():
            # Попробовать найти в других местах
            alt_paths = [
                f"config/{domain_name}_config.yaml",
                f"domains/{domain_name}/config.yaml",
                f"prompts/{domain_name}/config.yaml"
            ]
            
            found_path = None
            for path in alt_paths:
                if Path(path).exists():
                    found_path = path
                    break
            
            if not found_path:
                raise ConfigLoadError(f"Конфигурация для домена {domain_name} не найдена")
            
            domain_config_path = found_path
        
        config_data = {}
        errors = []
        
        # Загрузка конфигурации домена
        data, load_errors = await self._load_from_file(domain_config_path)
        errors.extend(load_errors)
        config_data = self._merge_configs(config_data, data)
        
        # Загрузка из переменных окружения
        env_config = self._load_from_environment()
        config_data = self._merge_configs(config_data, env_config)
        
        # Добавить название домена
        config_data["domain_name"] = domain_name
        
        # Валидация конфигурации домена
        try:
            validated_config = DomainSpecificConfig(**config_data)
            self.logger.info(f"Конфигурация домена {domain_name} успешно загружена")
            return validated_config
        except ValidationError as e:
            error_msg = f"Ошибка валидации конфигурации домена {domain_name}: {e}"
            self.logger.error(error_msg)
            raise ConfigValidationError(error_msg)
    
    def _load_from_file(self, file_path: str) -> Tuple[Dict[str, Any], List[str]]:
        """Загрузить конфигурацию из файла с дополнительной обработкой"""
        path = Path(file_path)
        errors = []
        
        try:
            if path.suffix.lower() in ['.yaml', '.yml']:
                with open(path, 'r', encoding='utf-8') as file:
                    content = file.read()
                    # Заменить переменные окружения в формате ${VAR_NAME}
                    content = self._substitute_env_vars(content)
                    # Обработать включения файлов (include)
                    content = self._process_includes(content, path.parent)
                    data = yaml.safe_load(content) or {}
            elif path.suffix.lower() == '.json':
                with open(path, 'r', encoding='utf-8') as file:
                    content = file.read()
                    content = self._substitute_env_vars(content)
                    data = json.loads(content)
            else:
                raise ValueError(f"Неподдерживаемый формат файла: {path.suffix}")
            
            return data, errors
        except yaml.YAMLError as e:
            errors.append(f"Ошибка парсинга YAML в {file_path}: {str(e)}")
            return {}, errors
        except json.JSONDecodeError as e:
            errors.append(f"Ошибка парсинга JSON в {file_path}: {str(e)}")
            return {}, errors
        except Exception as e:
            errors.append(f"Ошибка загрузки конфигурации из {file_path}: {str(e)}")
            return {}, errors
    
    def _process_includes(self, content: str, base_path: Path) -> str:
        """Обработать включения файлов в формате !include path/to/file.yaml"""
        import re
        
        def include_replacement(match):
            file_path = match.group(1).strip()
            full_path = base_path / file_path
            
            if full_path.exists():
                with open(full_path, 'r', encoding='utf-8') as f:
                    included_content = f.read()
                    # Рекурсивно обработать включения в подключаемом файле
                    included_content = self._process_includes(included_content, full_path.parent)
                    return included_content
            else:
                self.logger.warning(f"Файл для включения не найден: {full_path}")
                return ""
        
        # Заменить !include directives
        pattern = r'!include\s+([^\n]+)'
        content = re.sub(pattern, include_replacement, content)
        
        return content
```

### 3. Создание валидаторов конфигурации

Для проверки корректности специфических конфигураций:

```python
# config/validators.py
from typing import Dict, Any, List
from config.models import SystemConfig
from config.specialized_models import SpecializedSystemConfig, DomainSpecificConfig

class ConfigValidator:
    """Валидатор конфигурации"""
    
    def __init__(self):
        self.validation_rules = {}
        self.custom_validators = []
    
    def validate_system_config(self, config: SystemConfig) -> List[str]:
        """Валидировать системную конфигурацию"""
        errors = []
        
        # Проверить основные параметры
        if config.agent.max_iterations <= 0:
            errors.append("max_iterations должен быть больше 0")
        
        if config.agent.timeout <= 0:
            errors.append("timeout должен быть больше 0")
        
        if config.agent.max_concurrent_actions <= 0:
            errors.append("max_concurrent_actions должен быть больше 0")
        
        # Проверить параметры LLM
        if config.llm.temperature < 0.0 or config.llm.temperature > 2.0:
            errors.append("temperature должен быть в диапазоне [0.0, 2.0]")
        
        if config.llm.max_tokens <= 0:
            errors.append("max_tokens должен быть больше 0")
        
        # Проверить параметры промтов
        if config.prompts.cache_ttl < 60 or config.prompts.cache_ttl > 86400:
            errors.append("cache_ttl должен быть в диапазоне [60, 86400]")
        
        # Выполнить пользовательские валидации
        for validator in self.custom_validators:
            validator_errors = validator(config)
            errors.extend(validator_errors)
        
        return errors
    
    def validate_specialized_config(self, config: SpecializedSystemConfig) -> List[str]:
        """Валидировать специфическую конфигурацию"""
        errors = []
        
        # Проверить специфические параметры агента
        if config.specialized_agent.task_types and not isinstance(config.specialized_agent.task_types, list):
            errors.append("task_types должен быть списком")
        
        # Проверить специфические параметры LLM
        if config.specialized_llm.adaptive_temperature and not isinstance(config.specialized_llm.context_window_management, dict):
            errors.append("context_window_management должен быть словарем при включенном adaptive_temperature")
        
        # Проверить специфические параметры промтов
        if config.specialized_prompts.dynamic_prompt_selection and not isinstance(config.specialized_prompts.prompt_ab_testing, dict):
            errors.append("prompt_ab_testing должен быть словарем при включенном dynamic_prompt_selection")
        
        # Проверить общую конфигурацию
        base_errors = self.validate_system_config(config)
        errors.extend(base_errors)
        
        return errors
    
    def validate_domain_config(self, config: DomainSpecificConfig) -> List[str]:
        """Валидировать конфигурацию домена"""
        errors = []
        
        # Проверить, что название домена задано
        if not config.domain_name or not isinstance(config.domain_name, str):
            errors.append("domain_name должен быть непустой строкой")
        
        # Проверить возможности домена
        if not isinstance(config.domain_capabilities, list):
            errors.append("domain_capabilities должен быть списком")
        
        # Проверить правила домена
        if not isinstance(config.domain_rules, list):
            errors.append("domain_rules должен быть списком")
        
        # Проверить специфическую конфигурацию
        specialized_errors = self.validate_specialized_config(config)
        errors.extend(specialized_errors)
        
        return errors
    
    def add_custom_validator(self, validator_func):
        """Добавить пользовательский валидатор"""
        self.custom_validators.append(validator_func)
    
    def validate_config_compatibility(self, config: SystemConfig, target_version: str) -> List[str]:
        """Проверить совместимость конфигурации с целевой версией"""
        errors = []
        
        # Проверить, что все обязательные параметры присутствуют для целевой версии
        # Реализация зависит от конкретных требований версии
        
        return errors

# Пример пользовательского валидатора
def security_policy_validator(config: SystemConfig) -> List[str]:
    """Проверить политику безопасности в конфигурации"""
    errors = []
    
    if config.security_checks_enabled:
        # Проверить, что API ключи не хранятся в открытом виде в конфигурации
        if config.llm.api_key and not config.llm.api_key.startswith("${"):
            errors.append("API ключ не должен храниться в открытом виде в конфигурации")
        
        # Проверить настройки безопасности
        if not config.prompts.security_validation_enabled:
            errors.append("Проверка безопасности промтов должна быть включена в режиме безопасности")
    
    return errors
```

## Интеграция специфических конфигураций

### 1. Менеджер конфигурации

Менеджер для управления различными типами конфигураций:

```python
# config/config_manager.py
from typing import Dict, Any, Optional, Union
from config.config_loader import ConfigLoader
from config.specialized_config_loader import SpecializedConfigLoader
from config.validators import ConfigValidator, security_policy_validator
from config.models import SystemConfig
from config.specialized_models import SpecializedSystemConfig, DomainSpecificConfig
import logging

class ConfigManager:
    """Менеджер конфигурации для управления различными типами конфигураций"""
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path
        self.loader = ConfigLoader(config_path)
        self.specialized_loader = SpecializedConfigLoader(config_path)
        self.validator = ConfigValidator()
        self.validator.add_custom_validator(security_policy_validator)
        
        self.system_config: Optional[SystemConfig] = None
        self.specialized_config: Optional[SpecializedSystemConfig] = None
        self.domain_configs: Dict[str, DomainSpecificConfig] = {}
        
        self.logger = logging.getLogger(__name__)
    
    async def load_system_config(self, validate: bool = True) -> SystemConfig:
        """Загрузить основную системную конфигурацию"""
        self.system_config = await self.loader.load_config()
        
        if validate:
            errors = self.validator.validate_system_config(self.system_config)
            if errors:
                error_msg = f"Ошибки валидации системной конфигурации: {'; '.join(errors)}"
                self.logger.error(error_msg)
                raise ValueError(error_msg)
        
        self.logger.info("Системная конфигурация успешно загружена и валидирована")
        return self.system_config
    
    async def load_specialized_config(self, validate: bool = True) -> SpecializedSystemConfig:
        """Загрузить специфическую конфигурацию"""
        self.specialized_config = await self.specialized_loader.load_specialized_config()
        
        if validate:
            errors = self.validator.validate_specialized_config(self.specialized_config)
            if errors:
                error_msg = f"Ошибки валидации специфической конфигурации: {'; '.join(errors)}"
                self.logger.error(error_msg)
                raise ValueError(error_msg)
        
        self.logger.info("Специфическая конфигурация успешно загружена и валидирована")
        return self.specialized_config
    
    async def load_domain_config(self, domain_name: str, validate: bool = True) -> DomainSpecificConfig:
        """Загрузить конфигурацию для конкретного домена"""
        domain_config = await self.specialized_loader.load_domain_config(domain_name)
        self.domain_configs[domain_name] = domain_config
        
        if validate:
            errors = self.validator.validate_domain_config(domain_config)
            if errors:
                error_msg = f"Ошибки валидации конфигурации домена {domain_name}: {'; '.join(errors)}"
                self.logger.error(error_msg)
                raise ValueError(error_msg)
        
        self.logger.info(f"Конфигурация домена {domain_name} успешно загружена и валидирована")
        return domain_config
    
    def get_effective_config_for_domain(self, domain_name: str) -> Union[SystemConfig, SpecializedSystemConfig]:
        """Получить эффективную конфигурацию для конкретного домена"""
        if domain_name in self.domain_configs:
            # Если есть специфическая конфигурация домена, вернуть её
            return self.domain_configs[domain_name]
        elif self.specialized_config:
            # Если есть специфическая конфигурация, вернуть её
            return self.specialized_config
        else:
            # Иначе вернуть общую системную конфигурацию
            return self.system_config
    
    async def reload_config(self, config_type: str = "system", domain_name: Optional[str] = None):
        """Перезагрузить конфигурацию"""
        if config_type == "system":
            await self.load_system_config()
        elif config_type == "specialized":
            await self.load_specialized_config()
        elif config_type == "domain" and domain_name:
            await self.load_domain_config(domain_name)
        else:
            raise ValueError(f"Неподдерживаемый тип конфигурации: {config_type}")
    
    def update_config_value(self, path: str, value: Any, config_type: str = "system"):
        """Обновить значение в конфигурации по пути (например, 'agent.max_iterations')"""
        if config_type == "system" and self.system_config:
            self._set_nested_attr(self.system_config, path, value)
        elif config_type == "specialized" and self.specialized_config:
            self._set_nested_attr(self.specialized_config, path, value)
        elif config_type == "domain" and self.domain_configs:
            for domain_config in self.domain_configs.values():
                self._set_nested_attr(domain_config, path, value)
        else:
            raise ValueError(f"Невозможно обновить значение: {config_type} конфигурация не загружена")
    
    def _set_nested_attr(self, obj, path: str, value: Any):
        """Установить вложенное значение по пути"""
        parts = path.split('.')
        current = obj
        
        for part in parts[:-1]:
            if hasattr(current, part):
                current = getattr(current, part)
            else:
                # Создать атрибут, если его нет
                setattr(current, part, {})
                current = getattr(current, part)
        
        if hasattr(current, parts[-1]):
            setattr(current, parts[-1], value)
        else:
            # Если атрибута нет, попробовать через словарь
            if isinstance(current, dict):
                current[parts[-1]] = value
            else:
                setattr(current, parts[-1], value)
    
    def get_config_value(self, path: str, config_type: str = "system", default=None):
        """Получить значение из конфигурации по пути"""
        if config_type == "system" and self.system_config:
            return self._get_nested_attr(self.system_config, path, default)
        elif config_type == "specialized" and self.specialized_config:
            return self._get_nested_attr(self.specialized_config, path, default)
        elif config_type == "domain" and self.domain_configs:
            # Попробовать получить из любой конфигурации домена
            for domain_config in self.domain_configs.values():
                value = self._get_nested_attr(domain_config, path, default)
                if value != default:
                    return value
            return default
        else:
            return default
    
    def _get_nested_attr(self, obj, path: str, default=None):
        """Получить вложенное значение по пути"""
        parts = path.split('.')
        current = obj
        
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part, default)
            elif hasattr(current, part):
                current = getattr(current, part)
            else:
                return default
        
        return current
```

### 2. Использование специфических конфигураций

Пример использования специфических конфигураций:

```python
# config_usage_example.py
from config.config_manager import ConfigManager
from domain.value_objects.domain_type import DomainType

async def config_usage_example():
    """Пример использования системы конфигурации"""
    
    # Создать менеджер конфигурации
    config_manager = ConfigManager("config/app_config.yaml")
    
    # Загрузить основную системную конфигурацию
    system_config = await config_manager.load_system_config()
    print(f"Системная конфигурация загружена: {system_config.agent.name}")
    
    # Загрузить специфическую конфигурацию
    try:
        specialized_config = await config_manager.load_specialized_config()
        print(f"Специфическая конфигурация загружена: {specialized_config.domain_name}")
    except Exception as e:
        print(f"Специфическая конфигурация не найдена: {e}")
        specialized_config = None
    
    # Загрузить конфигурацию для конкретного домена
    try:
        code_analysis_config = await config_manager.load_domain_config("code_analysis")
        print(f"Конфигурация домена code_analysis загружена")
    except Exception as e:
        print(f"Конфигурация домена code_analysis не найдена: {e}")
    
    # Получить эффективную конфигурацию для домена
    effective_config = config_manager.get_effective_config_for_domain("code_analysis")
    print(f"Эффективная конфигурация для code_analysis: {effective_config.agent.name}")
    
    # Обновить значение в конфигурации
    config_manager.update_config_value("agent.max_iterations", 100, "system")
    print(f"Обновлено max_iterations: {config_manager.get_config_value('agent.max_iterations', 'system')}")
    
    return system_config

# Использование конфигурации в агентах
async def agent_with_custom_config_example():
    """Пример использования конфигурации в агентах"""
    
    # Создать менеджер конфигурации
    config_manager = ConfigManager()
    
    # Загрузить конфигурацию для домена анализа кода
    code_analysis_config = await config_manager.load_domain_config("code_analysis")
    
    # Создать агента с использованием специфической конфигурации
    from application.factories.agent_factory import AgentFactory
    
    agent_factory = AgentFactory()
    agent = await agent_factory.create_agent_with_config(code_analysis_config.specialized_agent)
    
    # Выполнить задачу с использованием настроек из конфигурации
    result = await agent.execute_task(
        task_description="Проанализируй этот Python код на наличие уязвимостей",
        context={
            "code": "def hello(): pass",
            "analysis_type": "security"
        }
    )
    
    print(f"Результат выполнения с настройками из конфигурации: {result}")
    
    return result

# Использование в сервисах
async def service_with_custom_config_example():
    """Пример использования конфигурации в сервисах"""
    
    # Создать менеджер конфигурации
    config_manager = ConfigManager()
    
    # Загрузить специфическую конфигурацию
    specialized_config = await config_manager.load_specialized_config()
    
    # Создать сервис с использованием настроек из конфигурации
    from application.services.prompt_loader import PromptLoader
    
    prompt_loader = PromptLoader(base_path=specialized_config.specialized_prompts.storage_path)
    
    # Настроить сервис в соответствии с конфигурацией
    if specialized_config.specialized_prompts.cache_enabled:
        # Включить кэширование с TTL из конфигурации
        prompt_loader.enable_caching(ttl=specialized_config.specialized_prompts.cache_ttl)
    
    if specialized_config.specialized_prompts.validation_enabled:
        # Включить валидацию
        prompt_loader.enable_validation()
    
    # Загрузить промты
    prompts, errors = prompt_loader.load_all_prompts()
    
    print(f"Загружено промтов: {len(prompts)}, ошибок: {len(errors)}")
    
    return prompts
```

## Лучшие практики

### 1. Модульность и расширяемость

Создавайте конфигурации, которые можно легко расширять:

```python
# Хорошо: модульные и расширяемые конфигурации
class BaseConfig(BaseModel):
    """Базовая конфигурация"""
    pass

class ExtendedConfig(BaseConfig):
    """Расширенная конфигурация"""
    pass

class SpecializedConfig(ExtendedConfig):
    """Специализированная конфигурация"""
    pass

# Плохо: монолитная конфигурация
class MonolithicConfig(BaseModel):
    """Монолитная конфигурация - сложно расширять и тестировать"""
    pass
```

### 2. Безопасность и конфиденциальность

Обязательно учитывайте безопасность при работе с конфигурациями:

```python
def validate_security_settings(config: SystemConfig) -> List[str]:
    """Проверить настройки безопасности"""
    errors = []
    
    # Проверить, что чувствительные данные не хранятся в открытом виде
    if config.llm.api_key and not config.llm.api_key.startswith("${"):
        errors.append("API ключ должен быть задан через переменную окружения (начинаться с ${)")
    
    # Проверить включение проверок безопасности
    if config.security_checks_enabled and not config.prompts.security_validation_enabled:
        errors.append("Проверка безопасности промтов должна быть включена при включенных security_checks")
    
    return errors
```

### 3. Валидация и тестирование

Обеспечьте надежную валидацию конфигураций:

```python
# config/test_config.py
import pytest
from config.config_manager import ConfigManager
from config.models import SystemConfig

class TestConfigModels:
    def test_agent_config_validation(self):
        """Тест валидации конфигурации агента"""
        # Проверить, что валидация срабатывает при некорректных данных
        with pytest.raises(ValidationError):
            AgentConfig(max_iterations=-1)  # Отрицательное значение
        
        # Проверить корректную валидацию
        config = AgentConfig(max_iterations=50)
        assert config.max_iterations == 50
    
    def test_llm_config_validation(self):
        """Тест валидации конфигурации LLM"""
        # Проверить диапазон температуры
        with pytest.raises(ValidationError):
            LLMConfig(temperature=3.0)  # Слишком высокое значение
        
        config = LLMConfig(temperature=0.7)
        assert config.temperature == 0.7

class TestConfigLoader:
    @pytest.mark.asyncio
    async def test_config_loading_from_file(self):
        """Тест загрузки конфигурации из файла"""
        # Создать временный файл конфигурации
        import tempfile
        import yaml
        
        config_data = {
            "agent": {
                "name": "test_agent",
                "max_iterations": 100
            },
            "llm": {
                "provider": "openai",
                "model": "gpt-4"
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            temp_config_path = f.name
        
        try:
            # Загрузить конфигурацию
            loader = ConfigLoader(temp_config_path)
            config = await loader.load_config()
            
            # Проверить значения
            assert config.agent.name == "test_agent"
            assert config.agent.max_iterations == 100
            assert config.llm.provider == LLMProviderType.OPENAI
            assert config.llm.model == "gpt-4"
        finally:
            # Удалить временный файл
            import os
            os.unlink(temp_config_path)
    
    @pytest.mark.asyncio
    async def test_config_loading_from_env(self):
        """Тест загрузки конфигурации из переменных окружения"""
        import os
        
        # Установить переменные окружения
        original_max_iter = os.environ.get('AGENT_MAX_ITERATIONS')
        original_provider = os.environ.get('AGENT_LLM_PROVIDER')
        
        os.environ['AGENT_MAX_ITERATIONS'] = '200'
        os.environ['AGENT_LLM_PROVIDER'] = 'anthropic'
        
        try:
            # Загрузить конфигурацию
            loader = ConfigLoader()
            config = await loader.load_config()
            
            # Проверить, что переменные окружения были учтены
            assert config.agent.max_iterations == 200
            assert config.llm.provider == LLMProviderType.ANTHROPIC
        finally:
            # Восстановить оригинальные значения
            if original_max_iter is not None:
                os.environ['AGENT_MAX_ITERATIONS'] = original_max_iter
            elif 'AGENT_MAX_ITERATIONS' in os.environ:
                del os.environ['AGENT_MAX_ITERATIONS']
            
            if original_provider is not None:
                os.environ['AGENT_LLM_PROVIDER'] = original_provider
            elif 'AGENT_LLM_PROVIDER' in os.environ:
                del os.environ['AGENT_LLM_PROVIDER']

class TestConfigManager:
    @pytest.mark.asyncio
    async def test_config_manager_operations(self):
        """Тест операций менеджера конфигурации"""
        # Создать менеджер
        manager = ConfigManager()
        
        # Загрузить системную конфигурацию
        system_config = await manager.load_system_config(validate=False)
        
        # Проверить получение значений
        original_max_iter = system_config.agent.max_iterations
        assert manager.get_config_value("agent.max_iterations", "system") == original_max_iter
        
        # Обновить значение
        new_max_iter = original_max_iter + 50
        manager.update_config_value("agent.max_iterations", new_max_iter, "system")
        
        # Проверить, что значение обновилось
        assert manager.get_config_value("agent.max_iterations", "system") == new_max_iter
```

Эти примеры показывают, как адаптировать и расширять систему конфигурации Koru AI Agent Framework под специфические задачи, обеспечивая модульность, безопасность и надежность системы.