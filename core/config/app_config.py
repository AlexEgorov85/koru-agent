"""
Единая конфигурация приложения (AppConfig) - унифицированный класс конфигурации.

ЗАМЕНЯЕТ:
- SystemConfig (из models.py)
- ComponentConfig
- AgentConfig  
- LoggingConfig
- registry.yaml зависимость

ЦЕЛЬ:
- Устранить дублирование конфигураций (5+ систем → 1)
- Обеспечить единый интерфейс для всех компонентов
- Авто-обнаружение ресурсов через файловую систему
- Экономия ~3000 строк кода
"""
from pathlib import Path
from typing import Dict, Optional, List, Any
from pydantic import BaseModel, Field, field_validator
from pydantic.config import ConfigDict

from core.config.vector_config import VectorSearchConfig


# === ВСТРОЕННЫЕ КОНФИГУРАЦИИ (бывшие отдельные классы) ===

class LLMProviderConfig(BaseModel):
    """Конфигурация LLM провайдера (встроена из models.py)"""
    model_config = ConfigDict(validate_assignment=True)

    provider_type: str = Field(default="llama_cpp", description="Тип провайдера (vllm, llama_cpp, openai)")
    model_name: str = Field(default="qwen-4b", description="Название модели")
    parameters: Dict[str, Any] = Field(default={}, description="Параметры провайдера")
    enabled: bool = Field(default=True, description="Включен ли провайдер")
    fallback_providers: List[str] = Field(default_factory=list, description="Резервные провайдеры")
    timeout_seconds: float = Field(default=120.0, ge=0.0, description="Таймаут ожидания ответа от LLM")
    
    # Обратная совместимость
    type_provider: Optional[str] = Field(default=None, description="Устаревшее поле, используйте provider_type")

    def __init__(self, **data):
        if 'type_provider' in data and 'provider_type' not in data:
            data['provider_type'] = data['type_provider']
        super().__init__(**data)

    @field_validator('provider_type')
    @classmethod
    def validate_provider_type(cls, v):
        valid_types = ['vllm', 'llama_cpp', 'openai', 'anthropic', 'gemini']
        if v.lower() not in valid_types:
            raise ValueError(f"Неподдерживаемый тип LLM провайдера: {v}. Допустимые: {valid_types}")
        return v.lower()


class DBProviderConfig(BaseModel):
    """Конфигурация БД провайдера (встроена из models.py)"""
    model_config = ConfigDict(validate_assignment=True)

    provider_type: str = Field(default="postgres", description="Тип провайдера")
    enabled: bool = Field(default=True, description="Включена ли БД")
    parameters: Dict[str, Any] = Field(default={}, description="Параметры провайдера")
    
    # Обратная совместимость
    type_provider: Optional[str] = Field(default=None, description="Устаревшее поле")

    def __init__(self, **data):
        if 'type_provider' in data and 'provider_type' not in data:
            data['provider_type'] = data['type_provider']
        super().__init__(**data)


class LoggingConfig(BaseModel):
    """Конфигурация логирования (встроена из infrastructure/logging/config.py)"""
    model_config = ConfigDict(validate_assignment=True)

    level: str = Field(default="INFO", description="Уровень логирования")
    format: str = Field(default="%(asctime)s - %(name)s - %(levelname)s - %(message)s", description="Формат логов")
    log_dir: str = Field(default="logs", description="Директория для логов")
    file_output_enabled: bool = Field(default=True, description="Включен ли вывод в файл")
    event_logging_enabled: bool = Field(default=True, description="Включено ли логирование событий")
    max_log_size_mb: int = Field(default=10, description="Макс. размер файла логов (MB)")
    backup_count: int = Field(default=5, description="Кол-во резервных файлов логов")


# === ОСНОВНАЯ КОНФИГУРАЦИЯ ===

class AppConfig(BaseModel):
    """
    ЕДИНАЯ КОНФИГУРАЦИЯ ПРИЛОЖЕНИЯ
    
    Объединяет ВСЕ системы конфигурации:
    - llm_providers: LLM провайдеры
    - db_providers: БД провайдеры  
    - logging: логирование
    - skills/tools/services/behaviors: компоненты
    - agent_parameters: параметры агента
    
    Авто-обнаружение через ResourceDiscovery заменяет registry.yaml
    """

    # === ИДЕНТИФИКАЦИЯ ===
    config_id: str = Field(default="app_config", description="Уникальный ID конфигурации")
    profile: str = Field(default="prod", description="Профиль (prod/sandbox/dev)")
    
    # === БАЗОВЫЕ ПАРАМЕТРЫ (из BaseModelConfig) ===
    debug: bool = Field(default=False, description="Режим отладки")
    log_level: str = Field(default="INFO", description="Уровень логирования")
    log_dir: str = Field(default="logs", description="Директория логов")
    data_dir: str = Field(default="data", description="Директория данных")

    # === LLM И БД ПРОВАЙДЕРЫ ===
    llm_providers: Dict[str, LLMProviderConfig] = Field(default_factory=dict, description="LLM провайдеры")
    db_providers: Dict[str, DBProviderConfig] = Field(default_factory=dict, description="БД провайдеры")

    # === ЛОГИРОВАНИЕ ===
    logging: LoggingConfig = Field(default_factory=LoggingConfig, description="Конфигурация логирования")

    # === ВЕКТОРНЫЙ ПОИСК ===
    vector_search: Optional[VectorSearchConfig] = Field(default_factory=VectorSearchConfig, description="Конфигурация векторного поиска")

    # === ВЕРСИИ РЕСУРСОВ (из промптов/контрактов) ===
    prompt_versions: Dict[str, str] = Field(default_factory=dict, description="Версии промптов: {capability: version}")
    input_contract_versions: Dict[str, str] = Field(default_factory=dict, description="Версии входных контрактов")
    output_contract_versions: Dict[str, str] = Field(default_factory=dict, description="Версии выходных контрактов")
    contract_versions: Dict[str, str] = Field(default_factory=dict, description="Объединенные версии контрактов")

    # === КОМПОНЕНТЫ ===
    service_configs: Dict[str, Any] = Field(default_factory=dict, description="Конфигурации сервисов")
    skill_configs: Dict[str, Any] = Field(default_factory=dict, description="Конфигурации навыков")
    tool_configs: Dict[str, Any] = Field(default_factory=dict, description="Конфигурации инструментов")
    behavior_configs: Dict[str, Any] = Field(default_factory=dict, description="Конфигурации поведений")

    # === ПАРАМЕТРЫ АГЕНТА ===
    max_steps: int = Field(default=10, ge=1, le=50, description="Макс. количество шагов")
    max_retries: int = Field(default=3, ge=0, le=10, description="Макс. количество попыток")
    temperature: float = Field(default=0.7, ge=0.0, le=1.0, description="Температура модели")
    llm_timeout_seconds: float = Field(default=120.0, ge=0.0, description="Таймаут LLM (сек)")
    side_effects_enabled: bool = Field(default=True, description="Разрешены ли побочные эффекты")
    detailed_metrics: bool = Field(default=False, description="Подробная метрика")
    enable_self_reflection: bool = Field(default=True, description="Включить саморефлексию")
    enable_context_window_management: bool = Field(default=True, description="Управление окном контекста")

    # Pydantic v2 config
    model_config = ConfigDict(extra="allow", frozen=False)

    def __init__(self, **data):
        super().__init__(**data)
        # Авто-объединение контрактов для обратной совместимости
        if not self.contract_versions:
            all_contracts = {}
            all_contracts.update(self.input_contract_versions)
            all_contracts.update(self.output_contract_versions)
            object.__setattr__(self, 'contract_versions', all_contracts)

    # === МЕТОДЫ ДОСТУПА К ВЕРСИЯМ ===
    
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

    # === ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ ===
    
    @property
    def primary_llm(self) -> Optional[LLMProviderConfig]:
        """Получение основного LLM провайдера"""
        for provider in self.llm_providers.values():
            if provider.enabled:
                return provider
        return None

    @property
    def default_db(self) -> Optional[DBProviderConfig]:
        """Получение основной БД"""
        for db in self.db_providers.values():
            if db.enabled:
                return db
        return None

    # === АВТО-ОБНАРУЖЕНИЕ (ЗАМЕНЯЕТ registry.yaml) ===
    
    @classmethod
    def from_discovery(cls, profile: str = "prod", data_dir: str = "data", discovery=None):
        """
        Загрузка AppConfig через авто-обнаружение ресурсов.

        ЗАМЕНЯЕТ:
        - registry.yaml
        - ConfigLoader
        - DynamicConfigManager
        - RegistryLoader

        ARGS:
        - profile: профиль (prod/sandbox/dev)
        - data_dir: директория данных
        - discovery: опционально, существующий ResourceDiscovery

        RETURNS:
        - AppConfig: сконфигурированный экземпляр
        """
        from core.infrastructure.discovery.resource_discovery import ResourceDiscovery
        from core.config.component_config import ComponentConfig
        import yaml

        # === ЗАГРУЗКА LLM/DB ПРОВАЙДЕРОВ ИЗ YAML ФАЙЛА ===
        llm_providers = {}
        db_providers = {}
        
        # ✅ ПРАВИЛЬНЫЙ ПУТЬ: от корня проекта
        config_file = Path(__file__).parent / "defaults" / f"{profile}.yaml"
        
        print(f"🔧 AppConfig.from_discovery: поиск конфигурации {config_file} (существует: {config_file.exists()})")
        
        if config_file.exists():
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    yaml_config = yaml.safe_load(f)
                
                print(f"🔧 AppConfig.from_discovery: загружено {len(yaml_config)} секций из {config_file}")
                
                # Загружаем LLM провайдеры
                if yaml_config and 'llm_providers' in yaml_config:
                    print(f"🔧 AppConfig.from_discovery: найдено {len(yaml_config['llm_providers'])} LLM провайдеров")
                    for name, provider_data in yaml_config['llm_providers'].items():
                        llm_providers[name] = LLMProviderConfig(
                            provider_type=provider_data.get('provider_type', 'llama_cpp'),
                            model_name=provider_data.get('model_name', 'unknown'),
                            enabled=provider_data.get('enabled', False),
                            parameters=provider_data.get('parameters', {}),
                            timeout_seconds=provider_data.get('timeout_seconds', 300.0)
                        )
                    print(f"🔧 AppConfig.from_discovery: загружено LLM провайдеров: {list(llm_providers.keys())}")
                
                # Загружаем DB провайдеры
                if yaml_config and 'db_providers' in yaml_config:
                    print(f"🔧 AppConfig.from_discovery: найдено {len(yaml_config['db_providers'])} DB провайдеров")
                    for name, provider_data in yaml_config['db_providers'].items():
                        db_providers[name] = DBProviderConfig(
                            provider_type=provider_data.get('provider_type', 'postgres'),
                            enabled=provider_data.get('enabled', False),
                            parameters=provider_data.get('parameters', {})
                        )
            except Exception as e:
                print(f"⚠️ Не удалось загрузить конфигурацию из {config_file}: {e}")
                import traceback
                traceback.print_exc()
        else:
            print(f"⚠️ Конфигурационный файл не найден: {config_file}")

        # Используем переданный ResourceDiscovery или создаём новый
        if discovery is None:
            discovery = ResourceDiscovery(base_dir=Path(data_dir), profile=profile)

        # Сканируем ресурсы (кэширование предотвращает повторную загрузку)
        prompts = discovery.discover_prompts()
        contracts = discovery.discover_contracts()

        # Собираем active версии промптов
        active_prompts = {}
        for prompt in prompts:
            if prompt.status.value == 'active':
                active_prompts[prompt.capability] = prompt.version

        # Собираем active версии контрактов
        input_contract_versions = {}
        output_contract_versions = {}
        for contract in contracts:
            if contract.status.value == 'active':
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

        for prompt in prompts:
            if prompt.status.value != 'active':
                continue

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

                component_resources[component_name]['prompts'][prompt.capability] = prompt.version

        for contract in contracts:
            if contract.status.value != 'active' or contract.capability == 'behavior':
                continue

            parts = contract.capability.split('.')
            prefix = parts[0] if parts else contract.capability

            if hasattr(contract, 'component_type') and contract.component_type:
                comp_type = contract.component_type.value
            else:
                comp_type = 'skill'
                if prefix == 'behavior':
                    comp_type = 'behavior'
                elif prefix == 'service':
                    comp_type = 'service'
                elif prefix == 'tool':
                    comp_type = 'tool'

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

                if contract.direction.value == 'input':
                    component_resources[component_name]['input_contracts'][contract.capability] = contract.version
                else:
                    component_resources[component_name]['output_contracts'][contract.capability] = contract.version

        # Создаем ComponentConfig для каждого компонента
        for component_name, resources in component_resources.items():
            comp_type = resources['type']
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
            llm_providers=llm_providers,  # ← Загружено из YAML
            db_providers=db_providers,    # ← Загружено из YAML
        )
