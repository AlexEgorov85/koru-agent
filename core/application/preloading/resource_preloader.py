"""
Предзагрузчик ресурсов — загрузка промптов, контрактов, кэшей.

ИЗОЛИРУЕТ логику предзагрузки от ApplicationContext.
"""
from typing import Dict, Any, Optional, Tuple
from core.infrastructure.logging import EventBusLogger


class ResourcePreloader:
    """
    Предзагрузка ресурсов для компонентов.
    
    ОТВЕТСТВЕННОСТЬ:
    1. Загрузка промптов из хранилища
    2. Загрузка контрактов из хранилища
    3. Кэширование ресурсов для компонентов
    
    USAGE:
    ```python
    preloader = ResourcePreloader(
        data_repository=data_repo,
        event_bus=event_bus
    )
    
    # Предзагрузка всех ресурсов
    prompts, contracts = await preloader.preload_all(config)
    
    # Предзагрузка для конкретного компонента
    await preloader.preload_for_component(component, config)
    ```
    """
    
    def __init__(self, data_repository, event_bus):
        """
        Инициализация предзагрузчика.
        
        ARGS:
        - data_repository: DataRepository для загрузки ресурсов
        - event_bus: EventBus для логирования
        """
        self._data_repository = data_repository
        self._event_bus = event_bus
        self._logger = EventBusLogger(
            event_bus,
            session_id="system",
            agent_id="preloader",
            component="ResourcePreloader"
        )
    
    async def preload_all(self, config) -> Tuple[Dict, Dict]:
        """
        Предзагрузить ВСЕ ресурсы.
        
        ARGS:
        - config: AppConfig с версиями промптов/контрактов
        
        RETURNS:
        - (prompts, contracts) словари для компонентов
        """
        await self._logger.info("Начало предзагрузки всех ресурсов")
        
        # Загрузка промптов
        all_prompts = await self._preload_all_prompts(config)
        
        # Загрузка контрактов
        all_contracts = await self._preload_all_contracts(config)
        
        await self._logger.info(
            f"Предзагрузка завершена: промптов={len(all_prompts)}, "
            f"контрактов={len(all_contracts)}"
        )
        
        return all_prompts, all_contracts
    
    async def preload_for_component(
        self,
        component_type: str,
        component_name: str,
        config
    ) -> Dict[str, Any]:
        """
        Предзагрузить ресурсы для конкретного компонента.
        
        ARGS:
        - component_type: Тип компонента (service, skill, tool, behavior)
        - component_name: Имя компонента
        - config: AppConfig с версиями ресурсов
        
        RETURNS:
        - Словарь с ресурсами (prompts, input_contracts, output_contracts)
        """
        resources = {
            "prompts": {},
            "input_contracts": {},
            "output_contracts": {}
        }
        
        # Загрузка промптов для компонента
        prompts = await self._preload_component_prompts(
            component_type, component_name, config
        )
        resources["prompts"] = prompts
        
        # Загрузка контрактов для компонента
        contracts = await self._preload_component_contracts(
            component_type, component_name, config
        )
        resources["input_contracts"] = contracts.get("input", {})
        resources["output_contracts"] = contracts.get("output", {})
        
        return resources
    
    async def _preload_all_prompts(self, config) -> Dict[Tuple, str]:
        """
        Предзагрузить все промпты.
        
        RETURNS:
        - {(capability, version): prompt_text}
        """
        prompts = {}
        
        if not self._data_repository:
            return prompts
        
        # Загрузка через DataRepository
        if hasattr(self._data_repository, 'prompts'):
            for key, prompt in self._data_repository.prompts.items():
                prompts[key] = prompt
        
        return prompts
    
    async def _preload_all_contracts(self, config) -> Dict[Tuple, Any]:
        """
        Предзагрузить все контракты.
        
        RETURNS:
        - {(capability, direction, version): contract_schema}
        """
        contracts = {}
        
        if not self._data_repository:
            return contracts
        
        # Загрузка через DataRepository
        if hasattr(self._data_repository, 'contracts'):
            for key, contract in self._data_repository.contracts.items():
                contracts[key] = contract
        
        return contracts
    
    async def _preload_component_prompts(
        self,
        component_type: str,
        component_name: str,
        config
    ) -> Dict[str, str]:
        """
        Предзагрузить промпты для компонента.
        
        ARGS:
        - component_type: Тип компонента
        - component_name: Имя компонента
        - config: AppConfig с версиями
        
        RETURNS:
        - {capability: prompt_text}
        """
        prompts = {}
        
        # Получаем версии промптов для компонента
        prompt_versions = self._get_prompt_versions_for_component(
            component_type, component_name, config
        )
        
        if not prompt_versions:
            return prompts
        
        # Загружаем каждый промпт
        for capability, version in prompt_versions.items():
            prompt = await self._load_prompt(capability, version)
            if prompt:
                prompts[capability] = prompt
        
        return prompts
    
    async def _preload_component_contracts(
        self,
        component_type: str,
        component_name: str,
        config
    ) -> Dict[str, Dict[str, Any]]:
        """
        Предзагрузить контракты для компонента.
        
        ARGS:
        - component_type: Тип компонента
        - component_name: Имя компонента
        - config: AppConfig с версиями
        
        RETURNS:
        - {"input": {capability: schema}, "output": {capability: schema}}
        """
        contracts = {"input": {}, "output": {}}
        
        # Получаем версии контрактов для компонента
        input_versions = self._get_input_contract_versions_for_component(
            component_type, component_name, config
        )
        output_versions = self._get_output_contract_versions_for_component(
            component_type, component_name, config
        )
        
        # Загружаем input контракты
        for capability, version in (input_versions or {}).items():
            contract = await self._load_contract(capability, "input", version)
            if contract:
                contracts["input"][capability] = contract
        
        # Загружаем output контракты
        for capability, version in (output_versions or {}).items():
            contract = await self._load_contract(capability, "output", version)
            if contract:
                contracts["output"][capability] = contract
        
        return contracts
    
    async def _load_prompt(self, capability: str, version: str) -> Optional[str]:
        """
        Загрузить промпт по capability и версии.
        
        ARGS:
        - capability: Имя capability
        - version: Версия промпта
        
        RETURNS:
        - Текст промпта или None
        """
        if not self._data_repository:
            return None
        
        # Пытаемся загрузить из DataRepository
        if hasattr(self._data_repository, 'get_prompt'):
            return await self._data_repository.get_prompt(capability, version)
        
        return None
    
    async def _load_contract(
        self,
        capability: str,
        direction: str,
        version: str
    ) -> Optional[Any]:
        """
        Загрузить контракт по capability, направлению и версии.
        
        ARGS:
        - capability: Имя capability
        - direction: Направление (input/output)
        - version: Версия контракта
        
        RETURNS:
        - Схема контракта или None
        """
        if not self._data_repository:
            return None
        
        # Пытаемся загрузить из DataRepository
        if hasattr(self._data_repository, 'get_contract'):
            return await self._data_repository.get_contract(
                capability, direction, version
            )
        
        return None
    
    def _get_prompt_versions_for_component(
        self,
        component_type: str,
        component_name: str,
        config
    ) -> Dict[str, str]:
        """
        Получить версии промптов для компонента.
        
        ARGS:
        - component_type: Тип компонента
        - component_name: Имя компонента
        - config: AppConfig
        
        RETURNS:
        - {capability: version}
        """
        # Получаем из config.prompt_versions
        if hasattr(config, 'prompt_versions'):
            return config.prompt_versions or {}
        
        return {}
    
    def _get_input_contract_versions_for_component(
        self,
        component_type: str,
        component_name: str,
        config
    ) -> Dict[str, str]:
        """
        Получить версии input контрактов для компонента.
        
        RETURNS:
        - {capability: version}
        """
        # Получаем из config.input_contract_versions
        if hasattr(config, 'input_contract_versions'):
            return config.input_contract_versions or {}
        
        return {}
    
    def _get_output_contract_versions_for_component(
        self,
        component_type: str,
        component_name: str,
        config
    ) -> Dict[str, str]:
        """
        Получить версии output контрактов для компонента.
        
        RETURNS:
        - {capability: version}
        """
        # Получаем из config.output_contract_versions
        if hasattr(config, 'output_contract_versions'):
            return config.output_contract_versions or {}
        
        return {}
    
    def __repr__(self) -> str:
        repo_status = "connected" if self._data_repository else "disconnected"
        return f"ResourcePreloader(repository={repo_status})"
