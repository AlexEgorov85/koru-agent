"""
Единая конфигурация приложения (AppConfig) - унифицированный класс конфигурации.

ЗАМЕНЯЕТ:
- ComponentConfig
- AgentConfig
- Любые другие специфичные конфигурации

ЦЕЛЬ:
- Устранить дублирование конфигураций
- Обеспечить единый интерфейс для всех компонентов
- Поддерживать обратную совместимость через адаптеры
"""
import yaml
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
    def from_registry(cls, profile: str = "prod", registry_path: str = "registry.yaml"):
        """
        Загрузка AppConfig из реестра версий.

        ARGS:
        - profile: профиль (prod или sandbox)
        - registry_path: путь к файлу реестра

        RETURNS:
        - AppConfig: сконфигурированный экземпляр AppConfig
        """
        registry_file = Path(registry_path)
        if not registry_file.exists():
            raise FileNotFoundError(f"Файл реестра не найден: {registry_path}")

        with open(registry_file, 'r', encoding='utf-8') as f:
            registry_data = yaml.safe_load(f)

        # Определяем, какой профиль использовать
        active_prompts = registry_data.get('active_prompts', {})
        active_contracts = registry_data.get('active_contracts', {})

        # Если профиль песочницы и есть оверрайды, используем их
        if profile == "sandbox":
            sandbox_overrides = registry_data.get('sandbox_overrides', {})
            # Применяем оверрайды для песочницы
            active_prompts = {**active_prompts, **sandbox_overrides.get('prompts', {})}
            active_contracts = {**active_contracts, **sandbox_overrides.get('contracts', {})}

        # Разделяем контракты на входные и выходные
        input_contract_versions = {}
        output_contract_versions = {}
        for capability, versions in active_contracts.items():
            if isinstance(versions, dict):
                if 'input' in versions:
                    input_contract_versions[capability] = versions['input']
                if 'output' in versions:
                    output_contract_versions[capability] = versions['output']
            else:
                # Если версия указана напрямую, считаем её входной
                input_contract_versions[capability] = versions

        # Создаем конфигурации для компонентов
        from core.config.component_config import ComponentConfig
        service_configs = {}
        skill_configs = {}
        tool_configs = {}
        behavior_configs = {}

        # Загружаем конфигурации сервисов из реестра
        services_section = registry_data.get('services', {})
        for service_name, service_info in services_section.items():
            if isinstance(service_info, dict) and 'enabled' in service_info and service_info['enabled']:
                # Создаем конфигурацию для сервиса
                # ВАЖНО: сервис получает ТОЛЬКО свои версии промптов/контрактов, а не глобальные!
                service_config = ComponentConfig(
                    variant_id=f"{service_name}_{profile}",
                    prompt_versions=service_info.get('prompt_versions', {}),
                    input_contract_versions=service_info.get('input_contract_versions', {}),
                    output_contract_versions=service_info.get('output_contract_versions', {}),
                    side_effects_enabled=service_info.get('side_effects_enabled', profile == "prod"),
                    detailed_metrics=service_info.get('detailed_metrics', False),
                    parameters=service_info.get('parameters', {}),
                    dependencies=service_info.get('dependencies', [])
                )
                service_configs[service_name] = service_config

        # Загружаем конфигурации навыков из реестра
        skills_section = registry_data.get('skills', {})
        for skill_name, skill_info in skills_section.items():
            if isinstance(skill_info, dict) and 'enabled' in skill_info and skill_info['enabled']:
                # Создаем конфигурацию для навыка
                # ВАЖНО: навык получает ТОЛЬКО свои версии промптов, а не глобальные!
                skill_config = ComponentConfig(
                    variant_id=f"{skill_name}_{profile}",
                    prompt_versions=skill_info.get('prompt_versions', {}),
                    input_contract_versions=skill_info.get('input_contract_versions', {}),
                    output_contract_versions=skill_info.get('output_contract_versions', {}),
                    side_effects_enabled=skill_info.get('side_effects_enabled', profile == "prod"),
                    detailed_metrics=skill_info.get('detailed_metrics', False),
                    parameters=skill_info.get('parameters', {}),
                    dependencies=skill_info.get('dependencies', [])
                )
                skill_configs[skill_name] = skill_config

        # Загружаем конфигурации инструментов из реестра
        tools_section = registry_data.get('tools', {})
        for tool_name, tool_info in tools_section.items():
            if isinstance(tool_info, dict) and 'enabled' in tool_info and tool_info['enabled']:
                # Создаем конфигурацию для инструмента
                tool_config = ComponentConfig(
                    variant_id=f"{tool_name}_{profile}",
                    prompt_versions=tool_info.get('prompt_versions', {}),  # ← ПУСТОЙ словарь по умолчанию!
                    input_contract_versions=tool_info.get('input_contract_versions', {}),
                    output_contract_versions=tool_info.get('output_contract_versions', {}),
                    side_effects_enabled=tool_info.get('side_effects_enabled', profile == "prod"),
                    detailed_metrics=tool_info.get('detailed_metrics', False),
                    parameters=tool_info.get('parameters', {}),
                    dependencies=tool_info.get('dependencies', [])
                )
                tool_configs[tool_name] = tool_config

        # Загружаем конфигурации паттернов поведения из реестра
        behaviors_section = registry_data.get('behaviors', {})
        for behavior_name, behavior_info in behaviors_section.items():
            if isinstance(behavior_info, dict) and 'enabled' in behavior_info and behavior_info['enabled']:
                # Создаем конфигурацию для паттерна поведения
                behavior_config = ComponentConfig(
                    variant_id=f"{behavior_name}_{profile}",
                    prompt_versions=behavior_info.get('prompt_versions', {}),  # ← ПУСТОЙ словарь по умолчанию!
                    input_contract_versions=behavior_info.get('input_contract_versions', {}),
                    output_contract_versions=behavior_info.get('output_contract_versions', {}),
                    side_effects_enabled=behavior_info.get('side_effects_enabled', profile == "prod"),
                    detailed_metrics=behavior_info.get('detailed_metrics', False),
                    parameters=behavior_info.get('parameters', {}),
                    dependencies=behavior_info.get('dependencies', [])
                )
                behavior_configs[behavior_name] = behavior_config

        # Загружаем параметры агента из реестра
        agent_config = registry_data.get('agent', {})

        return cls(
            config_id=f"app_config_{profile}",
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
            temperature=agent_config.get('temperature', 0.7),
            enable_self_reflection=agent_config.get('enable_self_reflection', True),
            enable_context_window_management=agent_config.get('enable_context_window_management', True),
            profile=profile  # Добавляем поле профиля
        )