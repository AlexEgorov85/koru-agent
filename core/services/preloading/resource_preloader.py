"""
Предзагрузчик ресурсов — загрузка промптов и контрактов для компонентов.

[REFACTOR v5.4.0] Архитектура загрузки ресурсов:
1. ResourcePreloader загружает ресурсы через DataRepository
2. Заполняет component_config.resolved_* объектами Prompt/Contract
3. Компонент получает готовые ресурсы и только копирует их в свой кэш

ИЗОЛИРУЕТ логику предзагрузки от ApplicationContext.
"""
from typing import Dict, Any, Optional, Tuple
from core.models.data.prompt import Prompt
from core.models.data.contract import Contract
from pydantic import BaseModel
from core.infrastructure.logging import EventBusLogger
  # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()


class ResourcePreloader:
    """
    Предзагрузка ресурсов для компонентов.

    ОТВЕТСТВЕННОСТЬ:
    1. Загрузка промптов из DataRepository (объекты Prompt)
    2. Загрузка контрактов из DataRepository (объекты Contract)
    3. Заполнение component_config.resolved_* для компонентов

    АРХИТЕКТУРА:
    - Компоненты НЕ загружают ресурсы сами
    - ResourcePreloader вызывается из ComponentFactory
    - Ресурсы хранятся как объекты (не словари)

    USAGE:
    ```python
    preloader = ResourcePreloader(
        data_repository=data_repo,
        event_bus=event_bus
    )

    # Предзагрузка для конкретного компонента
    resources = await preloader.preload_for_component(
        component_name="my_skill",
        config=component_config
    )

    # resources["prompts"] → Dict[str, Prompt]
    # resources["input_contracts"] → Dict[str, Contract]
    # resources["output_contracts"] → Dict[str, Contract]
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

    async def preload_for_component(
        self,
        component_name: str,
        component_config
    ) -> Dict[str, Any]:
        """
        Предзагрузить ресурсы для конкретного компонента.

        [REFACTOR v5.4.0] Загружает объекты Prompt/Contract через DataRepository
        и возвращает их для заполнения component_config.resolved_*.

        ARGS:
        - component_name: Имя компонента
        - component_config: ComponentConfig с версиями ресурсов

        RETURNS:
        - Dict с ресурсами:
          - "prompts": Dict[str, Prompt]
          - "input_contracts": Dict[str, Contract]
          - "output_contracts": Dict[str, Contract]
        """
        resources = {
            "prompts": {},
            "input_contracts": {},
            "output_contracts": {}
        }

        await self._logger.info(f"Начало предзагрузки ресурсов для {component_name}")
          # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()

        # Загрузка промптов для компонента
        prompts = await self._preload_component_prompts(component_config)
        resources["prompts"] = prompts

        # Загрузка input контрактов для компонента
        input_contracts = await self._preload_component_contracts(
            component_config, "input"
        )
        resources["input_contracts"] = input_contracts

        # Загрузка output контрактов для компонента
        output_contracts = await self._preload_component_contracts(
            component_config, "output"
        )
        resources["output_contracts"] = output_contracts

        await self._logger.info(
          # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            f"Предзагрузка для {component_name} завершена: "
            f"промптов={len(prompts)}, input_contracts={len(input_contracts)}, "
            f"output_contracts={len(output_contracts)}"
        )

        return resources

    async def _preload_component_prompts(
        self,
        component_config
    ) -> Dict[str, Prompt]:
        """
        Предзагрузить промпты для компонента.

        ARGS:
        - component_config: ComponentConfig с prompt_versions

        RETURNS:
        - Dict[str, Prompt]: {capability_name: Prompt object}
        
        NO FALLBACK: Если промпт указан в prompt_versions, он ДОЛЖЕН загрузиться.
        """
        prompts = {}

        # Получаем версии промптов из component_config
        prompt_versions = getattr(component_config, 'prompt_versions', {})
        prompts_required = getattr(component_config, 'prompts_required', True)

        if not prompt_versions:
            if prompts_required:
                raise ValueError(
                    f"prompt_versions не указан в component_config, но prompts_required=True! "
                    f"Компонент требует промпты."
                )
            # Промпты не указаны - значит компоненту они не нужны
            return prompts

        # Если указаны - они ДОЛЖНЫ загрузиться (NO FALLBACK)
        for capability, version in prompt_versions.items():
            prompt = await self._load_prompt(capability, version)
            prompts[capability] = prompt

        return prompts

    async def _preload_component_contracts(
        self,
        component_config,
        direction: str
    ) -> Dict[str, Contract]:
        """
        Предзагрузить контракты для компонента.

        ARGS:
        - component_config: ComponentConfig с contract_versions
        - direction: Направление ("input" или "output")

        RETURNS:
        - Dict[str, Contract]: {capability_name: Contract object}
        """
        contracts = {}

        # Получаем версии контрактов из component_config
        if direction == "input":
            contract_versions = getattr(
                component_config, 'input_contract_versions', {}
            )
        else:
            contract_versions = getattr(
                component_config, 'output_contract_versions', {}
            )

        if not contract_versions:
            await self._logger.debug(f"{direction} контракты не указаны в component_config")
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            return contracts

        # Загружаем каждый контракт через DataRepository
        for capability, version in contract_versions.items():
            contract = await self._load_contract(capability, version, direction)
            if contract:
                contracts[capability] = contract
                await self._logger.debug(
                  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                    f"Загружен {direction} контракт '{capability}' v{version} "
                    f"(статус: {contract.status.value})"
                )
            else:
                await self._logger.warning(
                  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                    f"Не удалось загрузить {direction} контракт '{capability}' v{version}"
                )

        return contracts

    async def _load_prompt(
        self,
        capability: str,
        version: str
    ) -> Prompt:
        """
        Загрузить промпт по capability и версии.

        ARGS:
        - capability: Имя capability
        - version: Версия промпта

        RETURNS:
        - Prompt object

        RAISES:
        - ValueError: Если промпт не найден
        """
        if not self._data_repository:
            raise ValueError(f"DataRepository не подключён для загрузки {capability}@{version}")

        try:
            prompt = self._data_repository.get_prompt(capability, version)
            if prompt is None:
                raise ValueError(f"Промпт '{capability}' v{version} не найден в хранилище")
            return prompt
        except KeyError as e:
            raise ValueError(f"Промпт '{capability}' v{version} не найден: {e}")
        except ValueError:
            raise
        except Exception as e:
            raise ValueError(f"Ошибка загрузки промпта {capability}@{version}: {e}")

    async def _load_contract(
        self,
        capability: str,
        version: str,
        direction: str
    ) -> Optional[Contract]:
        """
        Загрузить контракт по capability, версии и направлению.

        ARGS:
        - capability: Имя capability
        - version: Версия контракта
        - direction: Направление ("input" или "output")

        RETURNS:
        - Contract object или None
        """
        if not self._data_repository:
            await self._logger.error("DataRepository не подключён")
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            return None

        try:
            # DataRepository возвращает объект Contract
            contract = self._data_repository.get_contract(
                capability, version, direction
            )
            return contract
        except KeyError as e:
            await self._logger.warning(f"Контракт не найден: {e}")
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            return None
        except Exception as e:
            await self._logger.error(
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                f"Ошибка загрузки контракта {capability}@{version} ({direction}): {e}"
            )
            return None

    def __repr__(self) -> str:
        repo_status = "connected" if self._data_repository else "disconnected"
        return f"ResourcePreloader(repository={repo_status})"
