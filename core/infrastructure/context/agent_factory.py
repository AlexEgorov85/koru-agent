"""
Фабрика агентов - создание изолированных агентов с валидацией версий.

СОДЕРЖИТ:
- Валидацию согласованности версий до создания агента
- Создание изолированных прикладных контекстов
- Управление профилями (prod/sandbox)
"""
import logging
from typing import Optional, List
from enum import Enum

from core.infrastructure.context.infrastructure_context import InfrastructureContext
from core.application.context.application_context import ApplicationContext
from core.agent_runtime.runtime import AgentRuntime
from core.config.models import AgentConfig
from core.config.app_config import AppConfig


class ProfileType(Enum):
    """Тип профиля агента."""
    PROD = "prod"
    SANDBOX = "sandbox"


class VersionValidationError(Exception):
    """Ошибка при несоответствии версий."""
    pass


class AgentFactory:
    """Фабрика для создания изолированных агентов с валидацией версий."""

    def __init__(self, infrastructure: InfrastructureContext):
        """
        Инициализация фабрики агентов.

        ПАРАМЕТРЫ:
        - infrastructure: Инфраструктурный контекст
        """
        self.infrastructure = infrastructure
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    async def create_agent(
        self,
        goal: str,
        config: Optional[AgentConfig] = None,
        profile: ProfileType = ProfileType.PROD
    ) -> AgentRuntime:
        """
        Создание изолированного агента с валидацией версий.

        ПАРАМЕТРЫ:
        - goal: Цель агента
        - config: Конфигурация агента с версиями компонентов
        - profile: Профиль (prod/sandbox)

        ВОЗВРАЩАЕТ:
        - AgentRuntime: Созданный агент
        """
        # 1. Валидация версий ПЕРЕД созданием контекста
        if config:
            errors = await self._validate_version_consistency(config)
            if errors:
                raise VersionValidationError("\n".join(errors))

        # 2. Создание изолированного прикладного контекста
        app_context = ApplicationContext(
            infrastructure=self.infrastructure,
            config=config or await self._resolve_default_config()
        )
        app_context.side_effects_enabled = (profile == ProfileType.PROD)

        await app_context.initialize()

        # 3. Создание агента
        from core.session_context.session_context import SessionContext
        agent = AgentRuntime(
            system_context=app_context,  # ApplicationContext как системный контекст
            session_context=SessionContext(),
            max_steps=10  # по умолчанию
        )

        self.logger.info(
            f"Создан агент с профилем {profile.value}. "
            f"Версии: промпты={list(config.prompt_versions.keys()) if config else 'default'}, "
            f"контракты={getattr(config, 'input_contract_versions', {}).keys() if config else 'default'}"
        )

        return agent

    async def _validate_version_consistency(self, config: AgentConfig) -> List[str]:
        """
        Проверка существования всех версий в хранилище инфраструктуры.

        ПАРАМЕТРЫ:
        - config: Конфигурация агента

        ВОЗВРАЩАЕТ:
        - List[str]: Список ошибок (пустой если всё валидно)
        """
        errors = []

        # Проверка промптов через хранилище
        prompt_storage = self.infrastructure.get_prompt_storage()
        if prompt_storage:
            for capability, version in config.prompt_versions.items():
                exists = await prompt_storage.exists(capability, version)
                if not exists:
                    errors.append(f"Промпт {capability}@{version} не существует")

        # Проверка контрактов через хранилище
        contract_storage = self.infrastructure.get_contract_storage()
        if contract_storage:
            # Проверяем контракты из общего поля
            for capability, version in getattr(config, 'input_contract_versions', {}).items():
                # Проверяем input контракт
                input_exists = await contract_storage.exists(capability, version, "input")
                if not input_exists:
                    errors.append(f"Input-контракт {capability}@{version} не существует")

            for capability, version in getattr(config, 'output_contract_versions', {}).items():
                # Проверяем output контракт
                output_exists = await contract_storage.exists(capability, version, "output")
                if not output_exists:
                    errors.append(f"Output-контракт {capability}@{version} не существует")

        return errors

    async def _resolve_default_config(self) -> AgentConfig:
        """
        Резолвинг конфигурации по умолчанию.

        ВОЗВРАЩАЕТ:
        - AgentConfig: Конфигурация по умолчанию
        """
        # В реальной системе это может загружаться из конфигурационного файла
        # или из реестра по умолчанию
        from core.config.models import AgentConfig
        return AgentConfig(
            prompt_versions={},
            input_contract_versions={},
            output_contract_versions={},
            side_effects_enabled=True,
            detailed_metrics=False
        )

    async def create_agent_from_registry(
        self,
        goal: str,
        profile: ProfileType = ProfileType.PROD
    ) -> AgentRuntime:
        """
        Создание изолированного агента с использованием конфигурации из реестра.

        ПАРАМЕТРЫ:
        - goal: Цель агента
        - profile: Профиль (prod/sandbox)

        ВОЗВРАЩАЕТ:
        - AgentRuntime: Созданный агент
        """
        # Создание прикладного контекста из реестра
        app_context = await ApplicationContext.create_from_registry(
            self.infrastructure,
            profile.value
        )

        # Создание агента
        from core.session_context.session_context import SessionContext
        agent = AgentRuntime(
            system_context=app_context,  # ApplicationContext как системный контекст
            session_context=SessionContext(),
            max_steps=10  # по умолчанию
        )

        self.logger.info(
            f"Создан агент с использованием конфигурации из реестра, профиль {profile.value}. "
            f"Версии: промпты={list(app_context.config.prompt_versions.keys())}, "
            f"контракты={list(app_context.config.input_contract_versions.keys())}"
        )

        return agent