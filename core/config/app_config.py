"""
Единая конфигурация приложения (AppConfig) - унифицированный класс конфигурации.

ЗАМЕНЯЕТ:
- ComponentConfig
- AgentConfig
- Любые другие специфичные конфигурации

ЦЕЛЬ:
- Устранить дублирование конфигураций
- Обеспечить единый интерфейс для всех компонентов
- Авто-обнаружение ресурсов через файловую систему
"""
from pathlib import Path
from typing import Dict, Optional, List, Any
from pydantic import BaseModel, Field
from pydantic.config import ConfigDict
from enum import Enum


class AppConfig(BaseModel):
    """
    Единая конфигурация приложения с поддержкой всех необходимых параметров.

    ОСОБЕННОСТИ:
    - Объединяет все типы конфигураций в одну структуру
    - Поддерживает версионирование промптов и контрактов
    - Включает параметры поведения и производительности
    """

    # Идентификатор конфигурации
    config_id: str = Field(default="default_app_config", description="Уникальный идентификатор конфигурации")

    # Версии компонентов
    prompt_versions: Dict[str, str] = Field(default_factory=dict, description="Версии промптов: {capability: version}")
    input_contract_versions: Dict[str, str] = Field(default_factory=dict, description="Версии входных контрактов: {capability: version}")
    output_contract_versions: Dict[str, str] = Field(default_factory=dict, description="Версии выходных контрактов: {capability: version}")

    # Объединенные контракты (для обратной совместимости)
    contract_versions: Dict[str, str] = Field(default_factory=dict, description="Объединенные версии контрактов (для обратной совместимости)")

    # Параметры поведения
    side_effects_enabled: bool = Field(default=True, description="Включены ли побочные эффекты")
    detailed_metrics: bool = Field(default=False, description="Включена ли подробная метрика")

    # Параметры производительности
    max_steps: int = Field(default=10, description="Максимальное количество шагов")
    max_retries: int = Field(default=3, description="Максимальное количество попыток")
    llm_timeout_seconds: float = Field(default=120.0, ge=0.0, description="Таймаут ожидания ответа от LLM в секундах (глобальный)")

    # Температура модели
    temperature: float = Field(default=0.7, ge=0.0, le=1.0, description="Температура модели")


    # Включить саморефлексию
    enable_self_reflection: bool = Field(default=True, description="Включить саморефлексию")

    # Включить управление окном контекста
    enable_context_window_management: bool = Field(default=True, description="Включить управление окном контекста")

    # Профиль (prod/sandbox)
    profile: str = Field(default="prod", description="Профиль работы (prod или sandbox)")

    # Конфигурации компонентов для новых архитектурных требований
    # Используем строковые аннотации для избежания циклических зависимостей
    service_configs: Dict[str, Any] = Field(default_factory=dict, description="Конфигурации сервисов: {service_name: ComponentConfig}")
    skill_configs: Dict[str, Any] = Field(default_factory=dict, description="Конфигурации навыков: {skill_name: ComponentConfig}")
    tool_configs: Dict[str, Any] = Field(default_factory=dict, description="Конфигурации инструментов: {tool_name: ComponentConfig}")
    behavior_configs: Dict[str, Any] = Field(default_factory=dict, description="Конфигурации паттернов поведения: {behavior_name: ComponentConfig}")

    # LLM провайдеры (для InfrastructureContext)
    llm_providers: Dict[str, Any] = Field(default_factory=dict, description="LLM провайдеры: {provider_name: config}")

    # Используем ConfigDict вместо класса Config для Pydantic v2+
    model_config = ConfigDict(
        # Разрешаем произвольные атрибуты для обратной совместимости
        extra="allow",
        # Пока что разрешаем изменение, можно будет заморозить позже
        frozen=False
    )


    def __init__(self, **data):
        """
        Инициализация AppConfig с автоматическим объединением контрактов.
        
        Если переданы input_contract_versions и output_contract_versions, 
        они автоматически объединяются в contract_versions для обратной совместимости.
        """
        super().__init__(**data)
        
        # Автоматически объединяем контракты для обратной совместимости
        if not self.contract_versions:
            all_contracts = {}
            all_contracts.update(self.input_contract_versions)
            all_contracts.update(self.output_contract_versions)
            # Обновляем через model_dump и model_validate для соблюдения валидации
            object.__setattr__(self, 'contract_versions', all_contracts)


    def get_all_contract_versions(self) -> Dict[str, str]:
        """
        Получение всех версий контрактов (входных и выходных).
        
        RETURNS:
        - Dict[str, str]: объединенный словарь всех версий контрактов
        """
        all_contracts = {}
        all_contracts.update(self.input_contract_versions)
        all_contracts.update(self.output_contract_versions)
        return all_contracts


    def get_prompt_version(self, capability: str) -> Optional[str]:
        """
        Получение версии промпта для указанной capability.
        
        ARGS:
        - capability: имя capability
        
        RETURNS:
        - str: версия промпта или None если не найдена
        """
        return self.prompt_versions.get(capability)


    def get_input_contract_version(self, capability: str) -> Optional[str]:
        """
        Получение версии входного контракта для указанной capability.
        
        ARGS:
        - capability: имя capability
        
        RETURNS:
        - str: версия входного контракта или None если не найдена
        """
        return self.input_contract_versions.get(capability)


    def get_output_contract_version(self, capability: str) -> Optional[str]:
        """
        Получение версии выходного контракта для указанной capability.
        
        ARGS:
        - capability: имя capability
        
        RETURNS:
        - str: версия выходного контракта или None если не найдена
        """
        return self.output_contract_versions.get(capability)


    def update_prompt_version(self, capability: str, version: str):
        """
        Обновление версии промпта для указанной capability.
        
        ARGS:
        - capability: имя capability
        - version: новая версия
        """
        updated_versions = self.prompt_versions.copy()
        updated_versions[capability] = version
        object.__setattr__(self, 'prompt_versions', updated_versions)


    def update_input_contract_version(self, capability: str, version: str):
        """
        Обновление версии входного контракта для указанной capability.
        
        ARGS:
        - capability: имя capability
        - version: новая версия
        """
        updated_versions = self.input_contract_versions.copy()
        updated_versions[capability] = version
        object.__setattr__(self, 'input_contract_versions', updated_versions)


    def update_output_contract_version(self, capability: str, version: str):
        """
        Обновление версии выходного контракта для указанной capability.

        ARGS:
        - capability: имя capability
        - version: новая версия
        """
        updated_versions = self.output_contract_versions.copy()
        updated_versions[capability] = version
        object.__setattr__(self, 'output_contract_versions', updated_versions)

    @classmethod
    def from_discovery(cls, profile: str = "prod", data_dir: str = "data"):
        """
        Загрузка AppConfig через авто-обнаружение ресурсов (без registry.yaml и манифестов).

        ARGS:
        - profile: профиль (prod или sandbox)
        - data_dir: директория данных

        RETURNS:
        - AppConfig: сконфигурированный экземпляр AppConfig
        """
        from core.infrastructure.discovery.resource_discovery import ResourceDiscovery
        from core.config.component_config import ComponentConfig

        # Инициализируем ResourceDiscovery
        discovery = ResourceDiscovery(base_dir=Path(data_dir), profile=profile)

        # Сканируем ресурсы
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

        # Создаем конфигурации для компонентов на основе обнаруженных промптов/контрактов
        service_configs = {}
        skill_configs = {}
        tool_configs = {}
        behavior_configs = {}

        # Определяем компоненты по префиксам capability
        component_prefixes = {
            'skill': skill_configs,
            'service': service_configs,
            'tool': tool_configs,
            'behavior': behavior_configs,
        }

        # Собираем уникальные префиксы из промптов
        seen_components = set()
        for prompt in prompts:
            if prompt.status.value != 'active':
                continue

            # Определяем тип компонента из префикса capability
            parts = prompt.capability.split('.')
            if len(parts) >= 2:
                prefix = parts[0]  # например, 'book_library', 'planning'

                # Определяем тип по директории промпта
                comp_type = prompt.component_type.value if hasattr(prompt, 'component_type') else 'skill'

                if comp_type in component_prefixes:
                    # Для behavior используем имя из parts[1] + '_pattern' (например, 'react' -> 'react_pattern')
                    if comp_type == 'behavior':
                        component_name = f"{parts[1]}_pattern" if len(parts) >= 2 else f"{prefix}_pattern"
                    else:
                        component_name = prefix

                    # Проверяем, что компонент ещё не был добавлен
                    if component_name not in seen_components:
                        seen_components.add(component_name)

                        # Создаем минимальную конфигурацию компонента
                        component_config = ComponentConfig(
                            variant_id=f"{component_name}_{profile}",
                            side_effects_enabled=(profile == "prod"),
                            detailed_metrics=False,
                            parameters={},
                            dependencies=[]  # Зависимости определяются из DEPENDENCIES в коде компонента
                        )

                        component_prefixes[comp_type][component_name] = component_config

        # Загружаем параметры агента из manifests если есть
        # Или используем значения по умолчанию
        agent_config = {}

        return cls(
            config_id=f"app_config_{profile}_discovery",
            prompt_versions=active_prompts,
            input_contract_versions=input_contract_versions,
            output_contract_versions=output_contract_versions,
            service_configs=service_configs,
            skill_configs=skill_configs,
            tool_configs=tool_configs,
            behavior_configs=behavior_configs,
            side_effects_enabled=agent_config.get('side_effects_enabled', profile == "prod"),
            detailed_metrics=agent_config.get('detailed_metrics', False),
            max_steps=agent_config.get('max_steps', 10),
            max_retries=agent_config.get('max_retries', 3),
            llm_timeout_seconds=agent_config.get('llm_timeout_seconds', 120.0),
            temperature=agent_config.get('temperature', 0.7),
            enable_self_reflection=agent_config.get('enable_self_reflection', True),
            enable_context_window_management=agent_config.get('enable_context_window_management', True),
            profile=profile,
        )