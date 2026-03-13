"""
Единая конфигурация приложения (AppConfig).

ЦЕНТРАЛИЗУЕТ:
- DatabaseSettings, LLMSettings, AgentSettings (env vars)
- LLMProviderConfig, DBProviderConfig (discovery)
- LoggingConfig (логирование)
- Component configs (skills, services, tools, behaviors)

ИСПОЛЬЗОВАНИЕ:
```python
# Режим 1: Env vars (автоматическая загрузка из .env)
from core.config.app_config import AppConfig
config = AppConfig()

# Режим 2: Discovery (авто-обнаружение ресурсов)
config = AppConfig.from_discovery(profile="dev")

# Доступ к настройкам
config.database.host       # из DatabaseSettings
config.llm.provider        # из LLMSettings
config.agent.max_steps     # из AgentSettings
config.llm_providers       # из discovery
config.logging.level       # из LoggingConfig
```
"""
from pathlib import Path
from typing import Dict, Optional, List, Any, Literal, Union
from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic.config import ConfigDict
from pydantic_settings import BaseSettings, SettingsConfigDict

from core.config.vector_config import VectorSearchConfig
from core.config.logging_config import LoggingConfig


# ============================================================
# РАЗДЕЛ 1: Settings классы для поддержки env vars
# ============================================================

class DatabaseSettings(BaseSettings):
    """Настройки подключения к базе данных (env vars: AGENT_DB_*)."""

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
    pool_size: int = Field(default=10, ge=1, le=100, description="Размер пула")
    timeout: float = Field(default=30.0, ge=0.0, description="Таймаут (сек)")
    sslmode: Literal["disable", "require", "verify-ca", "verify-full"] = Field(
        default="disable", description="Режим SSL"
    )

    @field_validator('port')
    @classmethod
    def validate_port(cls, v):
        if not 1024 <= v <= 65535:
            raise ValueError("Port must be between 1024 and 65535")
        return v

    @property
    def dsn(self) -> str:
        return f"postgresql://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"

    @property
    def is_postgres(self) -> bool:
        return True

    def __repr__(self) -> str:
        return f"DatabaseSettings(host={self.host!r}, port={self.port}, database={self.database!r})"


class LLMSettings(BaseSettings):
    """Настройки LLM провайдера (env vars: AGENT_LLM_*)."""

    model_config = SettingsConfigDict(
        env_prefix='AGENT_LLM_',
        env_file='.env',
        extra='ignore'
    )

    provider: Literal["vllm", "llama", "openai", "anthropic", "gemini"] = Field(
        default="llama", description="Тип LLM провайдера"
    )
    model: str = Field(default="mistral-7b-instruct", description="Имя модели")
    model_path: Optional[str] = Field(default=None, description="Путь к модели")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="Температура")
    max_tokens: Optional[int] = Field(default=None, ge=1, description="Макс. токенов")
    top_p: float = Field(default=0.9, ge=0.0, le=1.0, description="Top-p sampling")
    timeout_seconds: float = Field(default=120.0, ge=0.0, description="Таймаут (сек)")
    api_key: Optional[str] = Field(default=None, description="API ключ")
    api_base_url: Optional[str] = Field(default=None, description="Базовый URL API")
    enable_caching: bool = Field(default=True, description="Кэширование")

    @field_validator('temperature')
    @classmethod
    def validate_temperature(cls, v):
        if v < 0 or v > 2:
            raise ValueError("Temperature must be between 0 and 2")
        return v

    @property
    def is_local(self) -> bool:
        return self.provider in ("vllm", "llama")

    @property
    def is_cloud(self) -> bool:
        return self.provider in ("openai", "anthropic", "gemini")

    def __repr__(self) -> str:
        return f"LLMSettings(provider={self.provider!r}, model={self.model!r}, temperature={self.temperature})"


class AgentSettings(BaseSettings):
    """Настройки агента (env vars: AGENT_*)."""

    model_config = SettingsConfigDict(
        env_prefix='AGENT_',
        env_file='.env',
        extra='ignore'
    )

    max_steps: int = Field(default=10, ge=1, le=100, description="Макс. шагов")
    max_retries: int = Field(default=3, ge=0, le=10, description="Макс. попыток")
    timeout_seconds: float = Field(default=300.0, ge=0.0, description="Таймаут (сек)")
    enable_self_reflection: bool = Field(default=True, description="Саморефлексия")
    enable_context_window_management: bool = Field(default=True, description="Управление контекстом")
    enable_benchmark: bool = Field(default=False, description="Бенчмарки")
    profile: Literal["dev", "prod", "sandbox"] = Field(default="dev", description="Профиль")

    @field_validator('max_steps')
    @classmethod
    def validate_max_steps(cls, v):
        if v < 1 or v > 100:
            raise ValueError("max_steps must be between 1 and 100")
        return v

    def __repr__(self) -> str:
        return f"AgentSettings(max_steps={self.max_steps}, profile={self.profile!r})"


# ============================================================
# РАЗДЕЛ 2: Provider конфигурации для discovery
# ============================================================

class LLMProviderConfig(BaseModel):
    """Конфигурация LLM провайдера (для discovery)."""
    model_config = ConfigDict(validate_assignment=True)

    provider_type: str = Field(default="llama_cpp", description="Тип провайдера")
    model_name: str = Field(default="qwen-4b", description="Название модели")
    parameters: Dict[str, Any] = Field(default={}, description="Параметры")
    enabled: bool = Field(default=True, description="Включен")
    fallback_providers: List[str] = Field(default_factory=list, description="Резервные")
    timeout_seconds: float = Field(default=120.0, ge=0.0, description="Таймаут (сек)")
    type_provider: Optional[str] = Field(default=None, description="Устаревшее")

    def __init__(self, **data):
        if 'type_provider' in data and 'provider_type' not in data:
            data['provider_type'] = data['type_provider']
        super().__init__(**data)

    @field_validator('provider_type')
    @classmethod
    def validate_provider_type(cls, v):
        valid_types = ['vllm', 'llama_cpp', 'openai', 'anthropic', 'gemini']
        if v.lower() not in valid_types:
            raise ValueError(f"Неподдерживаемый тип: {v}. Допустимые: {valid_types}")
        return v.lower()


class DBProviderConfig(BaseModel):
    """Конфигурация БД провайдера (для discovery)."""
    model_config = ConfigDict(validate_assignment=True)

    provider_type: str = Field(default="postgres", description="Тип провайдера")
    enabled: bool = Field(default=True, description="Включена")
    parameters: Dict[str, Any] = Field(default={}, description="Параметры")
    type_provider: Optional[str] = Field(default=None, description="Устаревшее")

    def __init__(self, **data):
        if 'type_provider' in data and 'provider_type' not in data:
            data['provider_type'] = data['type_provider']
        super().__init__(**data)


# ============================================================
# РАЗДЕЛ 3: Основная конфигурация (AppConfig)
# ============================================================

class AppConfig(BaseSettings):
    """
    ЕДИНАЯ КОНФИГУРАЦИЯ ПРИЛОЖЕНИЯ
    
    Поддерживает два режима:
    1. Env vars — загрузка из переменных окружения (.env)
    2. Discovery — авто-обнаружение ресурсов через файловую систему
    
    ОБЪЕДИНЯЕТ:
    - database: DatabaseSettings (из env vars)
    - llm: LLMSettings (из env vars)
    - agent: AgentSettings (из env vars)
    - llm_providers: Dict (из discovery)
    - db_providers: Dict (из discovery)
    - logging: LoggingConfig
    - component configs (skills, services, tools, behaviors)
    """

    model_config = SettingsConfigDict(
        env_prefix='AGENT_',
        env_file='.env',
        env_nested_delimiter='__',
        extra='allow',
        validate_assignment=True,
    )

    # === ИДЕНТИФИКАЦИЯ ===
    config_id: str = Field(default="app_config", description="ID конфигурации")
    profile: Literal["dev", "prod", "sandbox"] = Field(default="dev", description="Профиль")

    # === БАЗОВЫЕ ПАРАМЕТРЫ ===
    debug: bool = Field(default=False, description="Режим отладки")
    log_level: str = Field(default="INFO", description="Уровень логирования")
    log_dir: str = Field(default="logs", description="Директория логов")
    data_dir: str = Field(default="data", description="Директория данных")

    # === ENV VARS SETTINGS ===
    database: DatabaseSettings = Field(default_factory=DatabaseSettings, description="БД")
    llm: LLMSettings = Field(default_factory=LLMSettings, description="LLM")
    agent: AgentSettings = Field(default_factory=AgentSettings, description="Агент")

    # === DISCOVERY PROVIDERS ===
    llm_providers: Dict[str, LLMProviderConfig] = Field(default_factory=dict, description="LLM провайдеры")
    db_providers: Dict[str, DBProviderConfig] = Field(default_factory=dict, description="БД провайдеры")

    # === ЛОГИРОВАНИЕ ===
    logging: LoggingConfig = Field(default_factory=LoggingConfig, description="Логирование")

    # === ВЕКТОРНЫЙ ПОИСК ===
    vector_search: Optional[VectorSearchConfig] = Field(default_factory=VectorSearchConfig, description="Векторный поиск")

    # === ВЕРСИИ РЕСУРСОВ ===
    prompt_versions: Dict[str, str] = Field(default_factory=dict, description="Версии промптов")
    input_contract_versions: Dict[str, str] = Field(default_factory=dict, description="Входные контракты")
    output_contract_versions: Dict[str, str] = Field(default_factory=dict, description="Выходные контракты")
    contract_versions: Dict[str, str] = Field(default_factory=dict, description="Все контракты")

    # === КОМПОНЕНТЫ ===
    service_configs: Dict[str, Any] = Field(default_factory=dict, description="Сервисы")
    skill_configs: Dict[str, Any] = Field(default_factory=dict, description="Навыки")
    tool_configs: Dict[str, Any] = Field(default_factory=dict, description="Инструменты")
    behavior_configs: Dict[str, Any] = Field(default_factory=dict, description="Поведения")

    # === ПАРАМЕТРЫ АГЕНТА ===
    max_steps: int = Field(default=10, ge=1, le=50, description="Макс. шагов")
    max_retries: int = Field(default=3, ge=0, le=10, description="Макс. попыток")
    temperature: float = Field(default=0.7, ge=0.0, le=1.0, description="Температура")
    llm_timeout_seconds: float = Field(default=120.0, ge=0.0, description="Таймаут LLM")
    side_effects_enabled: bool = Field(default=True, description="Побочные эффекты")
    detailed_metrics: bool = Field(default=False, description="Детальная метрика")
    enable_self_reflection: bool = Field(default=True, description="Саморефлексия")
    enable_context_window_management: bool = Field(default=True, description="Управление контекстом")

    # === VALIDATORS ===

    @model_validator(mode='after')
    def sync_profile(self):
        """Синхронизация профиля между уровнями."""
        self.agent.profile = self.profile
        return self

    @model_validator(mode='after')
    def sync_contracts(self):
        """Синхронизация версий контрактов."""
        if not self.contract_versions:
            all_contracts = {}
            all_contracts.update(self.input_contract_versions)
            all_contracts.update(self.output_contract_versions)
            object.__setattr__(self, 'contract_versions', all_contracts)
        return self

    @field_validator('data_dir', 'log_dir')
    @classmethod
    def validate_paths(cls, v):
        """Проверка и создание директорий."""
        path = Path(v)
        path.mkdir(parents=True, exist_ok=True)
        return str(path)

    # === МЕТОДЫ ДОСТУПА ===

    def get_prompt_version(self, capability: str) -> Optional[str]:
        return self.prompt_versions.get(capability)

    def get_input_contract_version(self, capability: str) -> Optional[str]:
        return self.input_contract_versions.get(capability)

    def get_output_contract_version(self, capability: str) -> Optional[str]:
        return self.output_contract_versions.get(capability)

    def get_all_contract_versions(self) -> Dict[str, str]:
        all_contracts = {}
        all_contracts.update(self.input_contract_versions)
        all_contracts.update(self.output_contract_versions)
        return all_contracts

    def update_prompt_version(self, capability: str, version: str):
        updated = self.prompt_versions.copy()
        updated[capability] = version
        object.__setattr__(self, 'prompt_versions', updated)

    def update_input_contract_version(self, capability: str, version: str):
        updated = self.input_contract_versions.copy()
        updated[capability] = version
        object.__setattr__(self, 'input_contract_versions', updated)

    def update_output_contract_version(self, capability: str, version: str):
        updated = self.output_contract_versions.copy()
        updated[capability] = version
        object.__setattr__(self, 'output_contract_versions', updated)

    @property
    def primary_llm(self) -> Optional[LLMProviderConfig]:
        """Получение основного LLM провайдера."""
        for provider in self.llm_providers.values():
            if provider.enabled:
                return provider
        return None

    @property
    def default_db(self) -> Optional[DBProviderConfig]:
        """Получение основной БД."""
        for db in self.db_providers.values():
            if db.enabled:
                return db
        return None

    def validate_all(self) -> List[str]:
        """Валидация всей конфигурации."""
        errors = []
        if self.llm.is_cloud and not self.llm.api_key:
            errors.append(f"LLM provider '{self.llm.provider}' requires api_key")
        if not Path(self.data_dir).exists():
            errors.append(f"Data directory does not exist: {self.data_dir}")
        return errors

    def __repr__(self) -> str:
        return (
            f"AppConfig(profile={self.profile!r}, "
            f"database={self.database.database!r}, "
            f"llm={self.llm.provider!r})"
        )

    # === АВТО-ОБНАРУЖЕНИЕ (discovery режим) ===

    @classmethod
    def from_discovery(cls, profile: str = "prod", data_dir: str = "data", discovery=None):
        """
        Загрузка AppConfig через авто-обнаружение ресурсов.

        [REFACTOR v5.4.0] Профиль определяет разрешённые статусы:
        - prod → только status: active
        - sandbox → status: active + draft
        - dev → status: active + draft + inactive

        ЗАМЕНЯЕТ: registry.yaml, ConfigLoader, DynamicConfigManager, RegistryLoader
        """
        from core.infrastructure.discovery.resource_discovery import ResourceDiscovery
        from core.models.data.prompt import PromptStatus
        from core.config.component_config import ComponentConfig
        import yaml

        # === ЗАГРУЗКА LLM/DB ПРОВАЙДЕРОВ ИЗ YAML ===
        llm_providers = {}
        db_providers = {}
        config_file = Path(__file__).parent / "defaults" / f"{profile}.yaml"

        if config_file.exists():
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    yaml_config = yaml.safe_load(f)

                if yaml_config and 'llm_providers' in yaml_config:
                    for name, provider_data in yaml_config['llm_providers'].items():
                        llm_providers[name] = LLMProviderConfig(
                            provider_type=provider_data.get('provider_type', 'llama_cpp'),
                            model_name=provider_data.get('model_name', 'unknown'),
                            enabled=provider_data.get('enabled', False),
                            parameters=provider_data.get('parameters', {}),
                            timeout_seconds=provider_data.get('timeout_seconds', 300.0)
                        )

                if yaml_config and 'db_providers' in yaml_config:
                    for name, provider_data in yaml_config['db_providers'].items():
                        db_providers[name] = DBProviderConfig(
                            provider_type=provider_data.get('provider_type', 'postgres'),
                            enabled=provider_data.get('enabled', False),
                            parameters=provider_data.get('parameters', {})
                        )
            except Exception as e:
                print(f"⚠️ Не удалось загрузить конфигурацию из {config_file}: {e}")

        # === СКАНИРОВАНИЕ РЕСУРСОВ ===
        # [REFACTOR v5.4.0] ResourceDiscovery фильтрует по статусу в зависимости от профиля
        if discovery is None:
            discovery = ResourceDiscovery(base_dir=Path(data_dir), profile=profile)

        # discover_prompts() и discover_contracts() уже фильтруют по статусу профиля
        prompts = discovery.discover_prompts()
        contracts = discovery.discover_contracts()

        # Собираем версии (ResourceDiscovery уже отфильтровал по статусу)
        active_prompts = {p.capability: p.version for p in prompts}
        input_contract_versions = {}
        output_contract_versions = {}

        for contract in contracts:
            if contract.direction.value == 'input':
                input_contract_versions[contract.capability] = contract.version
            else:
                output_contract_versions[contract.capability] = contract.version

        # Создаем конфигурации компонентов
        service_configs = {}
        skill_configs = {}
        tool_configs = {}
        behavior_configs = {}

        component_prefixes = {
            'skill': skill_configs,
            'service': service_configs,
            'tool': tool_configs,
            'behavior': behavior_configs,
        }

        component_resources: Dict[str, Dict[str, Dict[str, str]]] = {}
        service_name_map = {
            'contract': 'contract_service',
            'sql_query': 'sql_query_service',
            'sql_validator': 'sql_validator_service',
            'table_description': 'table_description_service',
            'prompt': 'prompt_service',
        }

        # Собираем промпты по компонентам
        for prompt in prompts:
            parts = prompt.capability.split('.')
            prefix = parts[0] if parts else prompt.capability
            comp_type = prompt.component_type.value if hasattr(prompt, 'component_type') else 'skill'

            if comp_type in component_prefixes:
                if comp_type == 'behavior':
                    component_name = f"{parts[1]}_pattern" if len(parts) >= 2 else f"{prefix}_pattern"
                elif comp_type == 'service':
                    component_name = service_name_map.get(prefix, prefix)
                else:
                    component_name = prefix

                if component_name not in component_resources:
                    component_resources[component_name] = {
                        'type': comp_type,
                        'prompts': {},
                        'input_contracts': {},
                        'output_contracts': {}
                    }
                # ← НОВОЕ: Если промпт уже есть, выбираем последнюю версию
                existing_version = component_resources[component_name]['prompts'].get(prompt.capability)
                if existing_version is None or prompt.version > existing_version:
                    component_resources[component_name]['prompts'][prompt.capability] = prompt.version

        # Собираем контракты по компонентам
        for contract in contracts:
            if contract.status.value != 'active' or contract.capability == 'behavior':
                continue
            parts = contract.capability.split('.')
            prefix = parts[0] if parts else contract.capability
            comp_type = 'skill'
            if hasattr(contract, 'component_type') and contract.component_type:
                comp_type = contract.component_type.value
            elif prefix in ('behavior', 'service', 'tool'):
                comp_type = prefix

            if comp_type == 'behavior':
                component_name = f"{parts[1]}_pattern" if len(parts) >= 2 else f"{prefix}_pattern"
            else:
                component_name = prefix

            if comp_type in component_prefixes:
                if component_name not in component_resources:
                    component_resources[component_name] = {
                        'type': comp_type,
                        'prompts': {},
                        'input_contracts': {},
                        'output_contracts': {}
                    }
                # ← НОВОЕ: Выбираем последнюю версию контракта
                contract_dict = component_resources[component_name]['input_contracts'] if contract.direction.value == 'input' else component_resources[component_name]['output_contracts']
                existing_version = contract_dict.get(contract.capability)
                if existing_version is None or contract.version > existing_version:
                    contract_dict[contract.capability] = contract.version

        # Создаем ComponentConfig для каждого компонента
        for component_name, resources in component_resources.items():
            comp_type = resources['type']
            print(f"[DEBUG] {comp_type}.{component_name}: prompts={len(resources['prompts'])}, input={len(resources['input_contracts'])}, output={len(resources['output_contracts'])}")
            component_config = ComponentConfig(
                variant_id=f"{component_name}_{profile}",
                side_effects_enabled=(profile == "prod"),
                detailed_metrics=False,
                parameters={},
                dependencies=[],
                prompt_versions=resources['prompts'],
                input_contract_versions=resources['input_contracts'],
                output_contract_versions=resources['output_contracts']
            )
            component_prefixes[comp_type][component_name] = component_config

        # Добавляем обязательные сервисы и инструменты
        defaults = {
            'service_configs': {
                'prompt_service': {},
                'sql_generation': {},
                'table_description_service': {},
                'sql_query_service': {},
                'sql_validator_service': {},
            },
            'tool_configs': {
                'file_tool': {},
                'sql_tool': {},
                'vector_books_tool': {
                    'prompt_versions': {},
                    'input_contract_versions': {
                        "vector_books.search": "v1.0.0",
                        "vector_books.get_document": "v1.0.0",
                        "vector_books.analyze": "v1.0.0",
                        "vector_books.query": "v1.0.0"
                    },
                    'output_contract_versions': {
                        "vector_books.search": "v1.0.0",
                        "vector_books.get_document": "v1.0.0",
                        "vector_books.analyze": "v1.0.0",
                        "vector_books.query": "v1.0.0"
                    }
                }
            }
        }

        for comp_dict, defaults_dict in [(service_configs, defaults['service_configs']),
                                          (tool_configs, defaults['tool_configs'])]:
            for name, override in defaults_dict.items():
                if name not in comp_dict:
                    comp_dict[name] = ComponentConfig(
                        variant_id=f"{name}_{profile}",
                        side_effects_enabled=(profile == "prod"),
                        detailed_metrics=False,
                        parameters={},
                        dependencies=[],
                        **override
                    )

        return cls(
            config_id=f"app_config_{profile}_discovery",
            profile=profile,
            debug=(profile == "dev"),
            log_level="DEBUG" if profile == "dev" else "INFO",
            prompt_versions=active_prompts,
            input_contract_versions=input_contract_versions,
            output_contract_versions=output_contract_versions,
            service_configs=service_configs,
            skill_configs=skill_configs,
            tool_configs=tool_configs,
            behavior_configs=behavior_configs,
            side_effects_enabled=(profile == "prod"),
            detailed_metrics=False,
            max_steps=10,
            max_retries=3,
            llm_timeout_seconds=120.0,
            temperature=0.7,
            enable_self_reflection=True,
            enable_context_window_management=True,
            llm_providers=llm_providers,
            db_providers=db_providers,
        )


# ============================================================
# РАЗДЕЛ 4: Factory функции
# ============================================================

def get_config(profile: Optional[str] = None) -> AppConfig:
    """Получить конфигурацию приложения."""
    if profile:
        return AppConfig(profile=profile)
    return AppConfig()


def get_database_config() -> DatabaseSettings:
    """Получить настройки базы данных."""
    return DatabaseSettings()


def get_llm_config() -> LLMSettings:
    """Получить настройки LLM."""
    return LLMSettings()


def get_agent_config() -> AgentSettings:
    """Получить настройки агента."""
    return AgentSettings()


# ============================================================
# Экспорт для обратной совместимости
# ============================================================

__all__ = [
    'AppConfig',
    'DatabaseSettings',
    'LLMSettings',
    'AgentSettings',
    'LLMProviderConfig',
    'DBProviderConfig',
    'LoggingConfig',
    'get_config',
    'get_database_config',
    'get_llm_config',
    'get_agent_config',
]
