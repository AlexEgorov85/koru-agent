from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

from core.models.data.capability import Capability
from core.models.data.execution import ExecutionResult
from core.infrastructure.logging import EventBusLogger


class BaseBookLibraryHandler(ABC):
    """
    Базовый класс для всех обработчиков BookLibrarySkill.

    RESPONSIBILITIES:
    - Общий интерфейс для всех хендлеров
    - Предоставление доступа к executor и event_bus_logger
    - Унифицированная обработка ошибок
    """

    capability_name: str = ""

    def __init__(self, skill: 'BookLibrarySkill'):
        """
        Инициализация хендлера.

        ARGS:
        - skill: родительский skill для доступа к зависимостям
        """
        self.skill = skill
        self.executor = skill.executor
        self.application_context = skill.application_context
        self.event_bus_logger = skill.event_bus_logger

    @abstractmethod
    async def execute(self, params: Dict[str, Any]) -> Any:
        """
        Выполнение логики хендлера.

        ARGS:
        - params: входные параметры (валидированные)

        RETURNS:
        - Any: результат выполнения (Pydantic модель или dict)
        """
        pass

    def get_input_schema(self) -> Optional[Any]:
        """Получение входной схемы контракта"""
        return self.skill.get_input_contract(self.capability_name)

    def get_output_schema(self) -> Optional[Any]:
        """Получение выходной схемы контракта"""
        return self.skill.get_output_contract(self.capability_name)

    def get_prompt(self) -> Optional[Any]:
        """Получение промпта для capability"""
        return self.skill.get_prompt(self.capability_name)

    async def publish_metrics(
        self,
        success: bool,
        execution_time_ms: float,
        execution_type: str,
        rows_returned: int = 0,
        script_name: Optional[str] = None,
        error: Optional[str] = None
    ) -> None:
        """
        Публикация метрик через родительский skill.

        ARGS:
        - success: флаг успеха
        - execution_time_ms: время выполнения в мс
        - execution_type: тип выполнения (static/dynamic/vector)
        - rows_returned: количество возвращённых строк
        - script_name: имя скрипта (для static)
        - error: сообщение об ошибке
        """
        from core.infrastructure.event_bus.unified_event_bus import EventType
        await self.skill._publish_metrics(
            event_type=EventType.SKILL_EXECUTED,
            capability_name=self.capability_name,
            success=success,
            execution_time_ms=execution_time_ms,
            tokens_used=0,
            execution_type=execution_type,
            rows_returned=rows_returned,
            script_name=script_name,
            error=error
        )

    async def log_info(self, message: str) -> None:
        """Логирование информационного сообщения"""
        if self.event_bus_logger:
            await self.event_bus_logger.info(message)

    async def log_warning(self, message: str) -> None:
        """Логирование предупреждения"""
        if self.event_bus_logger:
            await self.event_bus_logger.warning(message)

    async def log_error(self, message: str) -> None:
        """Логирование ошибки"""
        if self.event_bus_logger:
            await self.event_bus_logger.error(message)

    async def log_debug(self, message: str) -> None:
        """Логирование отладочного сообщения"""
        if self.event_bus_logger:
            await self.event_bus_logger.debug(message)
