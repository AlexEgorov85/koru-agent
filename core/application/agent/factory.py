"""
Фабрика агентов - создание агентов с валидацией версий.

СОДЕРЖИТ:
- Валидацию согласованности версий до создания агента
- Использование существующего ApplicationContext
"""
from typing import Optional, List
from enum import Enum

from core.application.context.application_context import ApplicationContext
from core.application.agent.runtime import AgentRuntime
from core.application.context.agent_config import AgentConfig
from core.infrastructure.logging import EventBusLogger


class ProfileType(Enum):
    """Тип профиля агента."""
    PROD = "prod"
    SANDBOX = "sandbox"


class VersionValidationError(Exception):
    """Ошибка при несоответствии версий."""
    pass


class AgentFactory:
    """Фабрика для создания агентов с валидацией версий."""

    def __init__(self, application_context: ApplicationContext):
        """
        Инициализация фабрики агентов.

        ПАРАМЕТРЫ:
        - application_context: Прикладной контекст для использования
        """
        self.application_context = application_context
        self.event_bus_logger = None
        self._init_event_bus_logger()

    def _init_event_bus_logger(self):
        """Инициализация EventBusLogger."""
        # Используем infrastructure_context напрямую (это правильный путь для Factory)
        if hasattr(self.application_context, 'infrastructure_context'):
            event_bus = getattr(self.application_context.infrastructure_context, 'event_bus', None)
            if event_bus:
                self.event_bus_logger = EventBusLogger(
                    event_bus, 
                    session_id="system", 
                    agent_id="system",
                    component="AgentFactory"
                )

    def create_agent_sync(
        self,
        goal: str,
        config: Optional[AgentConfig] = None,
        correlation_id: Optional[str] = None
    ) -> AgentRuntime:
        """
        СИНХРОННОЕ создание изолированного агента с валидацией версий.

        ИСПОЛЬЗУЕТ asyncio.run() для async операций.
        Может вызываться из sync контекста.

        ПАРАМЕТРЫ:
        - goal: Цель агента
        - config: Конфигурация агента с версиями компонентов
        - correlation_id: ID для отслеживания сессии

        ВОЗВРАЩАЕТ:
        - AgentRuntime: Созданный агент
        """
        import asyncio
        
        # 1. Валидация версий (async → sync)
        if config:
            errors = asyncio.run(self._validate_version_consistency(config))
            if errors:
                raise VersionValidationError("\n".join(errors))

        # 2. ИСПОЛЬЗУЕМ существующий application_context
        app_context = self.application_context

        # 3. Создание агента с существующим контекстом
        agent = AgentRuntime(
            application_context=app_context,
            goal=goal,
            correlation_id=correlation_id
        )

        if self.event_bus_logger:
            self.event_bus_logger.info_sync(
                f"Создан агент с ID {app_context.id}. "
                f"Версии: из конфигурации"
            )

        return agent

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
        # 1. Валидация версий ПЕРЕД созданием агента
        if config:
            errors = await self._validate_version_consistency(config)
            if errors:
                raise VersionValidationError("\n".join(errors))

        # 2. ИСПОЛЬЗУЕМ существующий application_context
        # НЕТ НУЖДЫ создавать новый контекст - это архитектурная ошибка
        # Все компоненты уже инициализированы в существующем контексте
        app_context = self.application_context

        # 3. Создание агента с существующим контекстом
        agent = AgentRuntime(
            application_context=app_context,
            goal=goal,
            correlation_id=correlation_id
        )

        if self.event_bus_logger:
            await self.event_bus_logger.info(
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

        # Получаем инфраструктурный контекст из application_context
        infra = self.application_context.infrastructure_context

        # Проверка промптов через prompt_storage напрямую
        prompt_storage = infra.prompt_storage
        if prompt_storage:
            for capability, version in config.prompt_versions.items():
                exists = await prompt_storage.exists(capability, version)
                if not exists:
                    errors.append(f"Промпт {capability}@{version} не существует")

        # Проверка контрактов через contract_storage напрямую
        contract_storage = infra.contract_storage
        if contract_storage:
            for contract_name, version in config.contract_versions.items():
                # Проверяем как input, так и output контракты
                input_exists = await contract_storage.exists(contract_name, version, "input")
                output_exists = await contract_storage.exists(contract_name, version, "output")

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