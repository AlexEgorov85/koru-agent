from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from core.models.data.capability import Capability
from core.infrastructure.logging import EventBusLogger


class BaseReActHandler(ABC):
    """Базовый класс для обработчиков ReActPattern."""

    def __init__(self, pattern: 'ReActPattern'):
        self.pattern = pattern
        self.executor = pattern.executor
        self.application_context = pattern.application_context
        self.event_bus_logger = pattern.event_bus_logger
        self.llm_orchestrator = pattern.llm_orchestrator
        self.schema_validator = pattern.schema_validator

    @abstractmethod
    async def execute(self, *args, **kwargs) -> Any:
        pass

    async def log(self, level: str, message: str, **extra_data):
        if self.event_bus_logger:
            log_method = getattr(self.event_bus_logger, level, None)
            if log_method:
                await log_method(message, **extra_data)

    async def log_info(self, message: str):
        await self.log("info", message)

    async def log_debug(self, message: str):
        await self.log("debug", message)

    async def log_warning(self, message: str):
        await self.log("warning", message)

    async def log_error(self, message: str):
        await self.log("error", message)

    def get_capabilities(self) -> List[Capability]:
        return self.pattern.capabilities if hasattr(self.pattern, 'capabilities') else []

    def get_input_schema(self, capability_name: str):
        return self.pattern.get_input_contract(capability_name)

    def get_output_schema(self, capability_name: str):
        return self.pattern.get_output_contract(capability_name)
