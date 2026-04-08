#!/usr/bin/env python3
"""
Навык проверки результатов.

ТРИ CAPABILITY:
1. check_result.execute_script - выполнение заготовленного скрипта
2. check_result.generate_script - генерация SQL через LLM и выполнение

АРХИТЕКТУРА:
- skill.py: координация и маршрутизация
- handlers/: обработчики для каждой capability
- Конфигурация таблиц в data/skills/check_result/tables.yaml
"""
import sys
from typing import Dict, Any, List, Optional
from pathlib import Path
from pydantic import BaseModel

from core.infrastructure.event_bus.unified_event_bus import EventType
from core.models.data.capability import Capability

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core.components.skills.base_skill import BaseSkill
from core.config.component_config import ComponentConfig
from core.application_context.application_context import ApplicationContext
from core.agent.components.action_executor import ActionExecutor

from core.components.skills.check_result.handlers import (
    ExecuteScriptHandler,
    GenerateScriptHandler,
)


class CheckResultSkill(BaseSkill):
    """
    Навык проверки результатов.

    Поддерживает два режима работы:
    1. execute_script - выполнение заготовленных скриптов
    2. generate_script - генерация SQL через LLM и выполнение

    АРХИТЕКТУРА (YAML-Only):
    - Схемы валидации в YAML контрактах (data/contracts/)
    - Конфигурация таблиц в data/skills/check_result/tables.yaml
    """

    @property
    def description(self) -> str:
        return "Навык проверки результатов: выполнение и генерация SQL скриптов"

    DEPENDENCIES = ["sql_tool", "sql_generation", "sql_query_service", "table_description_service"]
    name: str = "check_result"

    def __init__(
        self,
        name: str,
        application_context: ApplicationContext,
        component_config: ComponentConfig,
        executor: ActionExecutor,
        event_bus = None
    ):
        super().__init__(
            name,
            application_context,
            component_config=component_config,
            executor=executor,
            event_bus=event_bus
        )

        self._handlers: Dict[str, Any] = {}

    def get_capabilities(self) -> List[Capability]:
        return [
            Capability(
                name="check_result.execute_script",
                description="Выполнение заготовленного SQL-скрипта по имени (быстро, без LLM)",
                skill_name=self.name,
                supported_strategies=["react", "planning"],
                visiable=True,
                meta={
                    "requires_llm": False,
                    "execution_type": "static"
                }
            ),
            Capability(
                name="check_result.generate_script",
                description="Генерация SQL скрипта через LLM и выполнение (гибко, медленнее)",
                skill_name=self.name,
                supported_strategies=["react", "planning"],
                visiable=True,
                meta={
                    "requires_llm": True,
                    "execution_type": "dynamic"
                }
            ),
        ]

    async def initialize(self) -> bool:
        success = await super().initialize()
        if not success:
            return False

        self._handlers = {
            "check_result.execute_script": ExecuteScriptHandler(self),
            "check_result.generate_script": GenerateScriptHandler(self),
        }

        await self._publish_with_context(
            event_type="check_result.initialized",
            data={"capabilities": list(self._handlers.keys())},
            source=self.name
        )

        return True

    def _get_event_type_for_success(self) -> EventType:
        return EventType.SKILL_EXECUTED

    async def _execute_impl(
        self,
        capability: 'Capability',
        parameters: BaseModel,
        execution_context: Any
    ) -> BaseModel:
        if capability.name not in self._handlers:
            raise ValueError(f"Навык не поддерживает capability: {capability.name}")

        handler = self._handlers[capability.name]
        return await handler.execute(parameters, execution_context)

    async def _publish_metrics(
        self,
        event_type,
        capability_name: str,
        success: bool,
        execution_time_ms: float,
        tokens_used: int = 0,
        error: Optional[str] = None,
        error_type: Optional[str] = None,
        error_category: Optional[str] = None,
        execution_type: Optional[str] = None,
        rows_returned: int = 0,
        script_name: Optional[str] = None,
        result: Optional[dict] = None
    ) -> None:
        """Публикация метрик выполнения навыка в EventBus."""
        await self._publish_with_context(
            event_type="check_result.metrics",
            data={
                "capability_name": capability_name,
                "success": success,
                "execution_time_ms": execution_time_ms,
                "execution_type": execution_type,
                "rows_returned": rows_returned,
                "script_name": script_name,
                "error": error
            },
            source=self.name
        )


def create_check_result_skill(
    application_context: ApplicationContext,
    component_config: ComponentConfig,
    executor: ActionExecutor,
    event_bus=None
) -> CheckResultSkill:
    """Фабрика для создания экземпляра CheckResultSkill."""
    return CheckResultSkill(
        name="check_result",
        application_context=application_context,
        component_config=component_config,
        executor=executor,
        event_bus=event_bus
    )