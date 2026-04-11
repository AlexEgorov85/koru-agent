"""
Фабрика агентов - создание агентов с валидацией версий.

СОДЕРЖИТ:
- Валидацию согласованности версий до создания агента
- Использование существующего ApplicationContext
"""
import logging
from typing import Optional, List
from enum import Enum

from core.application_context.application_context import ApplicationContext
from core.agent.runtime import AgentRuntime
from core.config.agent_config import AgentConfig
from core.infrastructure.logging.event_types import LogEventType


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

    def _get_logger(self) -> logging.Logger:
        """Получение логгера из log_session infra."""
        infra = self.application_context.infrastructure_context
        if infra.log_session and infra.log_session.app_logger:
            return infra.log_session.app_logger
        return logging.getLogger(__name__)

    async def create_agent(
        self,
        goal: str,
        config: Optional[AgentConfig] = None,
        correlation_id: Optional[str] = None,
        agent_id: Optional[str] = "agent_001",
        dialogue_history=None  # ← НОВОЕ: общая история диалога для копирования
    ) -> AgentRuntime:
        """
        Создание изолированного агента с валидацией версий.

        ПАРАМЕТРЫ:
        - goal: Цель агента
        - config: Конфигурация агента с версиями компонентов
        - correlation_id: ID для отслеживания сессии
        - agent_id: ID агента для логирования
        - dialogue_history: Общая история диалога (копируется в новый SessionContext)

        ВОЗВРАЩАЕТ:
        - AgentRuntime: Созданный агент
        """
        # 1. Валидация версий ПЕРЕД созданием агента
        if config:
            errors = await self._validate_version_consistency(config)
            if errors:
                raise VersionValidationError("\n".join(errors))

        # 2. ИСПОЛЬЗУЕМ существующий application_context
        app_context = self.application_context

        # 3. Создание агента — SessionContext всегда новый, но с копией истории
        agent = AgentRuntime(
            application_context=app_context,
            goal=goal,
            correlation_id=correlation_id,
            agent_id=agent_id,
            dialogue_history=dialogue_history,
            agent_config=config
        )

        self._get_logger().info(
            f"Создан агент с ID {app_context.id}. Версии: из конфигурации",
            extra={"event_type": LogEventType.SYSTEM_INIT}
        )

        return agent

    async def _validate_version_consistency(self, config: AgentConfig) -> List[str]:
        """
        Проверка существования всех версий через ResourceLoader.

        ПАРАМЕТРЫ:
        - config: Конфигурация агента

        ВОЗВРАЩАЕТ:
        - List[str]: Список ошибок (пустой если всё валидно)
        """
        errors = []

        # Получаем ResourceLoader из infrastructure_context
        infra = self.application_context.infrastructure_context
        loader = infra.resource_loader
        if not loader:
            errors.append("ResourceLoader не инициализирован")
            return errors

        # Проверка промптов через ResourceLoader
        for capability, version in config.prompt_versions.items():
            prompt = loader.get_prompt(capability, version)
            if not prompt:
                errors.append(f"Промпт {capability}@{version} не существует")

        # Проверка контрактов через ResourceLoader
        for contract_name, version in config.contract_versions.items():
            if not loader.get_contract(contract_name, version, "input"):
                errors.append(f"Input-контракт {contract_name}@{version} не существует")
            if not loader.get_contract(contract_name, version, "output"):
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