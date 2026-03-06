"""
Иерархическая конфигурация через Pydantic Settings.

ИСТОЧНИКИ (по приоритету):
1. Переменные окружения (AGENT_*)
2. Файл .env
3. YAML файлы конфигурации

ИСПОЛЬЗОВАНИЕ:
```python
from core.config.settings import AppConfig

config = AppConfig()

# Доступ к настройкам
db_host = config.database.host
llm_model = config.llm.model
agent_max_steps = config.agent.max_steps
```
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator, model_validator
from typing import Literal, Dict, Optional, List
from pathlib import Path


# ============================================================
# Database Settings
# ============================================================

class DatabaseSettings(BaseSettings):
    """
    Настройки подключения к базе данных.
    
    ENV VARS:
    - AGENT_DB_HOST, AGENT_DB_PORT, AGENT_DB_NAME
    - AGENT_DB_USER, AGENT_DB_PASSWORD
    - AGENT_DB_POOL_SIZE, AGENT_DB_TIMEOUT
    """
    
    model_config = SettingsConfigDict(
        env_prefix='AGENT_DB_',
        env_file='.env',
        extra='ignore'
    )
    
    host: str = Field(default="localhost", description="Хост БД")
    port: int = Field(default=5432, description="Порт БД")
    database: str = Field(default="agent_db", description="Имя базы данных")
    username: str = Field(default="postgres", description="Пользователь БД")
    password: str = Field(default="", description="Пароль БД")
    
    # Пул соединений
    pool_size: int = Field(default=10, ge=1, le=100, description="Размер пула соединений")
    timeout: float = Field(default=30.0, ge=0.0, description="Таймаут подключения в секундах")
    
    # SSL
    sslmode: Literal["disable", "require", "verify-ca", "verify-full"] = Field(
        default="disable",
        description="Режим SSL"
    )
    
    @field_validator('port')
    @classmethod
    def validate_port(cls, v):
        """Проверка порта."""
        if not 1024 <= v <= 65535:
            raise ValueError("Port must be between 1024 and 65535")
        return v
    
    @property
    def dsn(self) -> str:
        """
        Data Source Name для подключения.
        
        RETURNS:
        - Строка подключения PostgreSQL
        """
        return (
            f"postgresql://{self.username}:{self.password}"
            f"@{self.host}:{self.port}/{self.database}"
        )
    
    @property
    def is_postgres(self) -> bool:
        """Проверка что это PostgreSQL."""
        return True
    
    def __repr__(self) -> str:
        # Скрываем пароль
        return (
            f"DatabaseSettings(host={self.host!r}, port={self.port}, "
            f"database={self.database!r}, user={self.username!r})"
        )


# ============================================================
# LLM Settings
# ============================================================

class LLMProviderType(str):
    """Типы LLM провайдеров."""
    VLLM = "vllm"
    LLAMA = "llama"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"


class LLMSettings(BaseSettings):
    """
    Настройки LLM провайдера.
    
    ENV VARS:
    - AGENT_LLM_PROVIDER, AGENT_LLM_MODEL
    - AGENT_LLM_TEMPERATURE, AGENT_LLM_MAX_TOKENS
    - AGENT_LLM_TIMEOUT, AGENT_LLM_API_KEY
    """
    
    model_config = SettingsConfigDict(
        env_prefix='AGENT_LLM_',
        env_file='.env',
        extra='ignore'
    )
    
    # Провайдер
    provider: Literal["vllm", "llama", "openai", "anthropic", "gemini"] = Field(
        default="llama",
        description="Тип LLM провайдера"
    )
    
    # Модель
    model: str = Field(
        default="mistral-7b-instruct",
        description="Имя модели или путь к файлу"
    )
    model_path: Optional[str] = Field(
        default=None,
        description="Путь к файлу модели (для llama/vllm)"
    )
    
    # Параметры генерации
    temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="Температура генерации"
    )
    max_tokens: Optional[int] = Field(
        default=None,
        ge=1,
        description="Максимальное количество токенов"
    )
    top_p: float = Field(
        default=0.9,
        ge=0.0,
        le=1.0,
        description="Top-p sampling"
    )
    
    # Таймауты
    timeout_seconds: float = Field(
        default=120.0,
        ge=0.0,
        description="Таймаут ожидания ответа"
    )
    
    # API ключи (для облачных провайдеров)
    api_key: Optional[str] = Field(
        default=None,
        description="API ключ (для OpenAI/Anthropic/Gemini)"
    )
    api_base_url: Optional[str] = Field(
        default=None,
        description="Базовый URL API (для совместимых провайдеров)"
    )
    
    # Кэширование
    enable_caching: bool = Field(
        default=True,
        description="Включить кэширование ответов"
    )
    
    @field_validator('temperature')
    @classmethod
    def validate_temperature(cls, v):
        """Проверка температуры."""
        if v < 0 or v > 2:
            raise ValueError("Temperature must be between 0 and 2")
        return v
    
    @property
    def is_local(self) -> bool:
        """Проверка что это локальная модель."""
        return self.provider in ("vllm", "llama")
    
    @property
    def is_cloud(self) -> bool:
        """Проверка что это облачный провайдер."""
        return self.provider in ("openai", "anthropic", "gemini")
    
    def __repr__(self) -> str:
        return (
            f"LLMSettings(provider={self.provider!r}, model={self.model!r}, "
            f"temperature={self.temperature})"
        )


# ============================================================
# Agent Settings
# ============================================================

class AgentSettings(BaseSettings):
    """
    Настройки агента.
    
    ENV VARS:
    - AGENT_MAX_STEPS, AGENT_MAX_RETRIES
    - AGENT_TIMEOUT, AGENT_ENABLE_SELF_REFLECTION
    """
    
    model_config = SettingsConfigDict(
        env_prefix='AGENT_',
        env_file='.env',
        extra='ignore'
    )
    
    # Ограничения
    max_steps: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Максимальное количество шагов"
    )
    max_retries: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Максимальное количество попыток"
    )
    timeout_seconds: float = Field(
        default=300.0,
        ge=0.0,
        description="Общий таймаут выполнения"
    )
    
    # Функции
    enable_self_reflection: bool = Field(
        default=True,
        description="Включить саморефлексию"
    )
    enable_context_window_management: bool = Field(
        default=True,
        description="Включить управление окном контекста"
    )
    enable_benchmark: bool = Field(
        default=False,
        description="Включить бенчмарки"
    )
    
    # Профиль
    profile: Literal["dev", "prod", "sandbox"] = Field(
        default="dev",
        description="Профиль работы"
    )
    
    @field_validator('max_steps')
    @classmethod
    def validate_max_steps(cls, v):
        """Проверка max_steps."""
        if v < 1 or v > 100:
            raise ValueError("max_steps must be between 1 and 100")
        return v
    
    def __repr__(self) -> str:
        return (
            f"AgentSettings(max_steps={self.max_steps}, "
            f"profile={self.profile!r})"
        )


# ============================================================
# Logging Settings
# ============================================================

class LoggingSettings(BaseSettings):
    """
    Настройки логирования.
    
    ENV VARS:
    - AGENT_LOG_LEVEL, AGENT_LOG_FORMAT
    - AGENT_LOG_FILE_ENABLED, AGENT_LOG_FILE_PATH
    """
    
    model_config = SettingsConfigDict(
        env_prefix='AGENT_LOG_',
        env_file='.env',
        extra='ignore'
    )
    
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        description="Уровень логирования"
    )
    format: Literal["simple", "detailed", "json"] = Field(
        default="simple",
        description="Формат логов"
    )
    
    # Файловое логирование
    file_enabled: bool = Field(
        default=True,
        description="Включить логирование в файл"
    )
    file_path: str = Field(
        default="logs/agent.log",
        description="Путь к файлу логов"
    )
    file_max_size_mb: int = Field(
        default=100,
        ge=1,
        description="Максимальный размер файла (MB)"
    )
    file_backup_count: int = Field(
        default=5,
        ge=0,
        description="Количество резервных файлов"
    )
    
    # Консольное логирование
    console_enabled: bool = Field(
        default=True,
        description="Включить логирование в консоль"
    )
    
    def __repr__(self) -> str:
        return f"LoggingSettings(level={self.level!r}, format={self.format!r})"


# ============================================================
# Main App Configuration
# ============================================================

class AppConfig(BaseSettings):
    """
    Основная конфигурация приложения.
    
    ОБЪЕДИНЯЕТ:
    - DatabaseSettings
    - LLMSettings
    - AgentSettings
    - LoggingSettings
    
    ENV VARS:
    - AGENT_PROFILE (общий профиль)
    - Все префиксные переменные (AGENT_DB_*, AGENT_LLM_*, etc.)
    
    USAGE:
    ```python
    config = AppConfig()
    
    # Доступ к вложенным настройкам
    config.database.host
    config.llm.model
    config.agent.max_steps
    config.logging.level
    ```
    """
    
    model_config = SettingsConfigDict(
        env_prefix='AGENT_',
        env_file='.env',
        env_nested_delimiter='__',
        extra='allow'  # Разрешаем дополнительные поля для обратной совместимости
    )
    
    # Идентификатор
    config_id: str = Field(
        default="app_config",
        description="Уникальный идентификатор конфигурации"
    )
    
    # Профиль
    profile: Literal["dev", "prod", "sandbox"] = Field(
        default="dev",
        description="Профиль работы"
    )
    
    # Вложенные настройки
    database: DatabaseSettings = Field(
        default_factory=DatabaseSettings,
        description="Настройки базы данных"
    )
    llm: LLMSettings = Field(
        default_factory=LLMSettings,
        description="Настройки LLM"
    )
    agent: AgentSettings = Field(
        default_factory=AgentSettings,
        description="Настройки агента"
    )
    logging: LoggingSettings = Field(
        default_factory=LoggingSettings,
        description="Настройки логирования"
    )
    
    # Директории
    data_dir: Path = Field(
        default=Path("data"),
        description="Директория данных"
    )
    logs_dir: Path = Field(
        default=Path("logs"),
        description="Директория логов"
    )
    
    # Версии компонентов (для обратной совместимости)
    prompt_versions: Dict[str, str] = Field(
        default_factory=dict,
        description="Версии промптов"
    )
    input_contract_versions: Dict[str, str] = Field(
        default_factory=dict,
        description="Версии входных контрактов"
    )
    output_contract_versions: Dict[str, str] = Field(
        default_factory=dict,
        description="Версии выходных контрактов"
    )
    
    @model_validator(mode='after')
    def sync_profile(self):
        """Синхронизация профиля между уровнями."""
        # Синхронизируем профиль agent с основным
        self.agent.profile = self.profile
        return self
    
    @field_validator('data_dir', 'logs_dir')
    @classmethod
    def validate_paths(cls, v):
        """Проверка и создание директорий."""
        path = Path(v)
        path.mkdir(parents=True, exist_ok=True)
        return path
    
    def validate_all(self) -> List[str]:
        """
        Валидация всей конфигурации.
        
        RETURNS:
        - Список ошибок валидации (пустой если всё ок)
        """
        errors = []
        
        # Проверка LLM
        if self.llm.is_cloud and not self.llm.api_key:
            errors.append(f"LLM provider '{self.llm.provider}' requires api_key")
        
        # Проверка paths
        if not self.data_dir.exists():
            errors.append(f"Data directory does not exist: {self.data_dir}")
        
        # Проверка profile
        if self.profile == "prod" and self.logging.level == "DEBUG":
            errors.append("DEBUG logging not recommended for production")
        
        return errors
    
    def __repr__(self) -> str:
        return (
            f"AppConfig(profile={self.profile!r}, "
            f"database={self.database.database!r}, "
            f"llm={self.llm.provider!r})"
        )


# ============================================================
# Factory Functions
# ============================================================

def get_config(profile: Optional[str] = None) -> AppConfig:
    """
    Получить конфигурацию приложения.
    
    ARGS:
    - profile: Профиль (dev/prod/sandbox). Переопределяет env vars.
    
    RETURNS:
    - AppConfig с загруженными настройками
    """
    config = AppConfig()
    
    # Переопределяем профиль если указан
    if profile:
        config.profile = profile
        config.agent.profile = profile
    
    return config


def get_database_config() -> DatabaseSettings:
    """Получить настройки базы данных."""
    return DatabaseSettings()


def get_llm_config() -> LLMSettings:
    """Получить настройки LLM."""
    return LLMSettings()


def get_agent_config() -> AgentSettings:
    """Получить настройки агента."""
    return AgentSettings()
