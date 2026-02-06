# Обзор конфигурации системы

Система конфигурации Composable AI Agent Framework обеспечивает гибкую настройку всех компонентов фреймворка. Конфигурация позволяет адаптировать поведение системы под различные сценарии использования, окружения и требования.

## Определение

Конфигурация системы - это набор параметров, определяющих поведение компонентов фреймворка. Она включает настройки агентов, паттернов мышления, инструментов, промтов, а также других компонентов системы.

## Архитектура системы конфигурации

Система конфигурации включает следующие компоненты:

### 1. Загрузчик конфигурации
- Отвечает за загрузку конфигурации из различных источников
- Поддерживает различные форматы (JSON, YAML, TOML, переменные окружения)
- Обеспечивает валидацию конфигурации

### 2. Модели конфигурации
- Определяют структуру конфигурационных данных
- Обеспечивают типизацию и валидацию параметров
- Используют Pydantic для валидации данных

### 3. Сервисы конфигурации
- Управление конфигурацией во время выполнения
- Обеспечивают доступ к параметрам конфигурации
- Поддерживают перезагрузку конфигурации

## Загрузчик конфигурации

Загрузчик конфигурации реализован в `config/config_loader.py`:

```python
import yaml
import json
import os
from pathlib import Path
from typing import Dict, Any, Optional
from pydantic import ValidationError
from config.models import SystemConfig

class ConfigLoader:
    """Загрузчик конфигурации системы"""
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or "config.yaml"
        self.default_config_path = "config/default_config.yaml"
    
    async def load_config(self) -> SystemConfig:
        """Загрузить конфигурацию из файла"""
        config_data = {}
        
        # Загрузка конфигурации из основного файла
        if Path(self.config_path).exists():
            config_data = await self._load_from_file(self.config_path)
        
        # Загрузка конфигурации по умолчанию если основной файл не найден
        elif Path(self.default_config_path).exists():
            config_data = await self._load_from_file(self.default_config_path)
        
        # Загрузка конфигурации из переменных окружения
        env_config = self._load_from_environment()
        config_data = self._merge_configs(config_data, env_config)
        
        # Валидация конфигурации
        try:
            validated_config = SystemConfig(**config_data)
            return validated_config
        except ValidationError as e:
            raise ValueError(f"Ошибка валидации конфигурации: {e}")
    
    async def _load_from_file(self, file_path: str) -> Dict[str, Any]:
        """Загрузить конфигурацию из файла"""
        path = Path(file_path)
        
        if path.suffix.lower() in ['.yaml', '.yml']:
            with open(path, 'r', encoding='utf-8') as file:
                return yaml.safe_load(file) or {}
        elif path.suffix.lower() == '.json':
            with open(path, 'r', encoding='utf-8') as file:
                return json.load(file)
        else:
            raise ValueError(f"Неподдерживаемый формат файла: {path.suffix}")
    
    def _load_from_environment(self) -> Dict[str, Any]:
        """Загрузить конфигурацию из переменных окружения"""
        config = {}
        
        # Загрузка переменных, начинающихся с PREFIX_
        prefix = "AGENT_"
        for key, value in os.environ.items():
            if key.startswith(prefix):
                # Преобразование ключа в формат конфигурации
                config_key = key[len(prefix):].lower().replace('_', '.')
                config[config_key] = self._convert_env_value(value)
        
        return config
    
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
            return [item.strip() for item in value.split(',')]
        
        # Вернуть строку
        return value
    
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

## Модели конфигурации

Модели конфигурации определены в `config/models.py` используют Pydantic для валидации:

```python
from pydantic import BaseModel, Field
from typing import Dict, List, Optional
from enum import Enum

class LLMProviderType(str, Enum):
    """Типы LLM провайдеров"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    HUGGINGFACE = "huggingface"
    CUSTOM = "custom"

class AgentConfig(BaseModel):
    """Конфигурация агента"""
    name: str = Field(..., description="Имя агента")
    max_iterations: int = Field(default=50, description="Максимальное количество итераций")
    timeout: int = Field(default=300, description="Таймаут выполнения задачи в секундах")
    enable_logging: bool = Field(default=True, description="Включить логирование")
    max_concurrent_actions: int = Field(default=5, description="Максимальное количество параллельных действий")
    memory_limit: str = Field(default="1GB", description="Ограничение памяти")
    retry_attempts: int = Field(default=3, description="Количество попыток повтора при ошибках")

class LLMConfig(BaseModel):
    """Конфигурация LLM"""
    provider: LLMProviderType = Field(default=LLMProviderType.OPENAI, description="Тип провайдера LLM")
    model: str = Field(default="gpt-4", description="Название модели")
    api_key: Optional[str] = Field(default=None, description="API ключ")
    temperature: float = Field(default=0.7, description="Температура генерации")
    max_tokens: int = Field(default=2048, description="Максимальное количество токенов")
    base_url: Optional[str] = Field(default=None, description="Базовый URL для API")

class PromptConfig(BaseModel):
    """Конфигурация системы промтов"""
    storage_path: str = Field(default="./prompts", description="Путь к хранилищу промтов")
    cache_enabled: bool = Field(default=True, description="Включить кэширование промтов")
    cache_ttl: int = Field(default=3600, description="Время жизни кэша в секундах")
    validation_enabled: bool = Field(default=True, description="Включить валидацию промтов")

class SystemConfig(BaseModel):
    """Конфигурация всей системы"""
    agent: AgentConfig = Field(default_factory=AgentConfig, description="Конфигурация агента")
    llm: LLMConfig = Field(default_factory=LLMConfig, description="Конфигурация LLM")
    prompts: PromptConfig = Field(default_factory=PromptConfig, description="Конфигурация промтов")
    debug_mode: bool = Field(default=False, description="Режим отладки")
    log_level: str = Field(default="INFO", description="Уровень логирования")
    enable_monitoring: bool = Field(default=True, description="Включить мониторинг")
```

## Типы конфигурации

### 1. Конфигурация агента
- Определяет параметры работы агента
- Управляет ограничениями и поведением
- Настройка максимального количества итераций и времени выполнения

### 2. Конфигурация LLM
- Определяет параметры взаимодействия с LLM
- Управляет выбором модели и провайдера
- Настройка температуры, токенов и других параметров генерации

### 3. Конфигурация промтов
- Управляет хранилищем и кэшированием промтов
- Настройка валидации и версионирования промтов

### 4. Системная конфигурация
- Общие параметры работы системы
- Настройки логирования и мониторинга
- Режимы отладки и безопасности

## Примеры конфигурационных файлов

### YAML-конфигурация
```yaml
# config.yaml
agent:
  name: "default_agent"
  max_iterations: 100
  timeout: 600
  enable_logging: true
  max_concurrent_actions: 3
  memory_limit: "2GB"
  retry_attempts: 5

llm:
  provider: "openai"
  model: "gpt-4-turbo"
  api_key: "${OPENAI_API_KEY}"  # Будет загружен из переменной окружения
  temperature: 0.5
  max_tokens: 4096
  base_url: null

prompts:
  storage_path: "./custom_prompts"
  cache_enabled: true
  cache_ttl: 7200
  validation_enabled: true

debug_mode: false
log_level: "INFO"
enable_monitoring: true
```

### JSON-конфигурация
```json
{
  "agent": {
    "name": "json_configured_agent",
    "max_iterations": 75,
    "timeout": 450,
    "enable_logging": true,
    "max_concurrent_actions": 4
  },
  "llm": {
    "provider": "anthropic",
    "model": "claude-3-opus",
    "temperature": 0.6,
    "max_tokens": 4096
  },
  "prompts": {
    "storage_path": "./prompts",
    "cache_enabled": true
  },
  "debug_mode": true,
  "log_level": "DEBUG"
}
```

## Использование конфигурации

Конфигурация используется следующим образом:

```python
from config.config_loader import ConfigLoader
from application.factories.agent_factory import AgentFactory

# Загрузка конфигурации
config_loader = ConfigLoader("config.yaml")
config = await config_loader.load_config()

# Использование конфигурации для создания агента
agent_factory = AgentFactory()
agent = await agent_factory.create_agent_with_config(config.agent)

# Использование конфигурации LLM
llm_config = config.llm
if llm_config.api_key is None:
    # Загрузка из переменной окружения
    llm_config.api_key = os.getenv("LLM_API_KEY")
```

## Приоритеты источников конфигурации

Система поддерживает несколько источников конфигурации с определенным приоритетом:

1. **Переменные окружения** (наивысший приоритет)
2. **Файл конфигурации** (средний приоритет)
3. **Конфигурация по умолчанию** (наименьший приоритет)

Это позволяет переопределять параметры конфигурации в зависимости от окружения (разработка, тестирование, продакшн).

## Валидация конфигурации

Система включает механизмы валидации конфигурации:

- **Типизация**: Проверка типов параметров с использованием Pydantic
- **Ограничения**: Проверка диапазонов значений и форматов
- **Обязательные поля**: Проверка наличия обязательных параметров
- **Кастомные валидаторы**: Пользовательские проверки сложных условий

## Преимущества системы конфигурации

- **Гибкость**: Поддержка различных источников и форматов конфигурации
- **Типобезопасность**: Использование Pydantic для валидации типов
- **Переопределяемость**: Возможность переопределения параметров в зависимости от окружения
- **Документированность**: Явные описания всех параметров
- **Безопасность**: Поддержка переменных окружения для чувствительных данных
- **Масштабируемость**: Легкое добавление новых параметров конфигурации

## Интеграция с другими компонентами

Система конфигурации интегрирована с:
- **Агентами**: Настройка параметров работы агентов
- **Системой промтов**: Конфигурация хранилища и кэширования
- **LLM провайдерами**: Настройка параметров взаимодействия
- **Системой логирования**: Управление уровнями и форматами логирования
- **Системой безопасности**: Настройка ограничений и политик доступа