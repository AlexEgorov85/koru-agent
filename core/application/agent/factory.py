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
from core.application.agent.runtime import AgentRuntime
from core.application.context.agent_config import AgentConfig


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
        correlation_id: Optional[str] = None
    ) -> AgentRuntime:
        """
        Создание изолированного агента с валидацией версий.

        ПАРАМЕТРЫ:
        - goal: Цель агента
        - config: Конфигурация агента с версиями компонентов
        - correlation_id: ID для отслеживания сессии

        ВОЗВРАЩАЕТ:
        - AgentRuntime: Созданный агент
        """
        # 1. Валидация версий ПЕРЕД созданием контекста
        if config:
            errors = await self._validate_version_consistency(config)
            if errors:
                raise VersionValidationError("\n".join(errors))

        # 2. Создание изолированного прикладного контекста
        # Преобразуем AgentConfig в AppConfig для ApplicationContext
        from core.config.app_config import AppConfig
        app_config = AppConfig(
            config_id=config.config_id if config else "default_app_config",
            created_at=getattr(config, 'created_at', None),
            source=getattr(config, 'source', 'auto_resolved'),
            prompt_versions=getattr(config, 'prompt_versions', {}),
            contract_versions=getattr(config, 'contract_versions', {}),
            max_steps=getattr(config, 'max_steps', 10),
            max_retries=getattr(config, 'max_retries', 3),
            temperature=getattr(config, 'temperature', 0.7),
            allow_inactive_resources=getattr(config, 'allow_inactive_resources', False)
        )

        app_context = ApplicationContext(
            infrastructure_context=self.infrastructure,
            config=app_config,
            profile="prod"  # или использовать profile из config, если он там есть
        )

        await app_context.initialize()

        # 3. Создание агента
        agent = AgentRuntime(
            application_context=app_context,
            goal=goal
        )

        self.logger.info(
            f"Создан агент с ID {app_context.id}. "
            f"Версии: из конфигурации"
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

        # Проверка промптов через инфраструктурное хранилище
        prompt_storage = self.infrastructure.get_resource("prompt_storage")
        if prompt_storage:
            for capability, version in config.prompt_versions.items():
                exists = await prompt_storage.check_version_exists(capability, version)
                if not exists:
                    errors.append(f"Промпт {capability}@{version} не существует")

        # Проверка контрактов через инфраструктурное хранилище
        contract_storage = self.infrastructure.get_resource("contract_storage")
        if contract_storage:
            for contract_name, version in config.contract_versions.items():
                # Проверяем как input, так и output контракты
                input_exists = await contract_storage.check_version_exists(contract_name, version, "input")
                output_exists = await contract_storage.check_version_exists(contract_name, version, "output")
                
                if not input_exists:
                    errors.append(f"Input-контракт {contract_name}@{version} не существует")
                if not output_exists:
                    errors.append(f"Output-контракт {contract_name}@{version} не существует")

        return errors

    async def _resolve_default_config(self) -> AgentConfig:
        """
        Резолвинг конфигурации по умолчанию.

        ВОЗВРАЩАЕТ:
        - AgentConfig: Конфигурация по умолчанию
        """
        # В реальной системе это может загружаться из конфигурационного файла
        # или из реестра по умолчанию
        return AgentConfig(
            prompt_versions={},
            contract_versions={},
            max_steps=10,
            max_retries=3,
            temperature=0.7,
            allow_inactive_resources=False
        )