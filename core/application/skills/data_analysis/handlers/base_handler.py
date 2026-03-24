from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

from core.infrastructure.logging import EventBusLogger


class BaseDataAnalysisHandler(ABC):
    """Базовый класс для обработчиков DataAnalysisSkill."""

    capability_name: str = ""

    def __init__(self, skill: 'DataAnalysisSkill'):
        self.skill = skill
        self.executor = skill.executor
        self.event_bus_logger = skill.event_bus_logger

    @abstractmethod
    async def execute(self, params: Dict[str, Any]) -> Any:
        pass

    def get_input_schema(self):
        return self.skill.get_input_contract(self.capability_name)

    def get_output_schema(self):
        return self.skill.get_output_contract(self.capability_name)

    def get_prompt(self):
        return self.skill.get_prompt(self.capability_name)

    async def log_info(self, msg: str):
        if self.event_bus_logger:
            await self.event_bus_logger.info(msg)

    async def log_error(self, msg: str):
        if self.event_bus_logger:
            await self.event_bus_logger.error(msg)

    async def log_warning(self, msg: str):
        if self.event_bus_logger:
            await self.event_bus_logger.warning(msg)
