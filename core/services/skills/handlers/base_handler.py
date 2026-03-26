"""
Универсальный базовый класс для всех обработчиков навыков (Skill Handlers).

ARCHITECTURE:
- Наследуется всеми Skill handlers (book_library, data_analysis, final_answer, planning, etc.)
- Не содержит бизнес-логики конкретного навыка
- Предоставляет общие утилиты для всех хендлеров
- Устраняет дублирование кода между навыками

RESPONSIBILITIES:
- Общий интерфейс для всех хендлеров
- Доступ к executor и event_bus_logger
- Унифицированная обработка ошибок
- Публикация метрик
- Валидация входных/выходных данных через контракты
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Type, TYPE_CHECKING

from pydantic import BaseModel

from core.models.data.capability import Capability
from core.models.data.execution import ExecutionResult
from core.agent.components.action_executor import ActionExecutor, ExecutionContext
from core.infrastructure.logging import EventBusLogger

if TYPE_CHECKING:
    from core.services.skills.base_skill import BaseSkill


class BaseSkillHandler(ABC):
    """
    УНИВЕРСАЛЬНЫЙ БАЗОВЫЙ КЛАСС ДЛЯ ВСЕХ ОБРАБОТЧИКОВ НАВЫКОВ.
    
    RESPONSIBILITIES:
    - Общий интерфейс для всех хендлеров
    - Доступ к executor и event_bus_logger
    - Унифицированная обработка ошибок
    - Публикация метрик
    - Валидация входных/выходных данных через контракты
    
    ARCHITECTURE:
    - Наследуется всеми Skill handlers (book_library, data_analysis, etc.)
    - Не содержит бизнес-логики конкретного навыка
    - Предоставляет общие утилиты для всех хендлеров
    """

    # ← НОВОЕ: Уникальное имя capability для этого хендлера
    capability_name: str = ""

    def __init__(
        self,
        skill: 'BaseSkill',  # Родительский навык (BookLibrarySkill, DataAnalysisSkill, etc.)
    ):
        """
        Инициализация хендлера.
        
        ARGS:
        - skill: родительский навык для доступа к зависимостям
        """
        self.skill = skill
        self.executor: ActionExecutor = skill.executor
        self.application_context = skill.application_context
        self.event_bus_logger: EventBusLogger = skill.event_bus_logger

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

    # === ОБЩИЕ УТИЛИТЫ ДЛЯ ВСЕХ ХЕНДЛЕРОВ ===

    def get_input_schema(self) -> Optional[Type[BaseModel]]:
        """Получение входной схемы контракта"""
        return self.skill.get_input_contract(self.capability_name)

    def get_output_schema(self) -> Optional[Type[BaseModel]]:
        """Получение выходной схемы контракта"""
        return self.skill.get_output_contract(self.capability_name)

    def get_prompt(self) -> Optional[str]:
        """Получение промпта для capability"""
        prompt_obj = self.skill.get_prompt(self.capability_name)
        return prompt_obj.content if prompt_obj else None

    def get_prompt_with_contract(self) -> Optional[str]:
        """Получение промпта для capability (метод для обратной совместимости)."""
        return self.get_prompt()

    async def publish_metrics(
        self,
        success: bool,
        execution_time_ms: float,
        execution_type: str = "unknown",
        rows_returned: int = 0,
        tokens_used: int = 0,
        error: Optional[str] = None,
        **kwargs
    ) -> None:
        """
        Публикация метрик через родительский skill.
        
        УНИВЕРСАЛЬНЫЙ МЕТОД — работает для всех навыков!
        
        ARGS:
        - success: флаг успеха
        - execution_time_ms: время выполнения в мс
        - execution_type: тип выполнения (static/dynamic/vector/unknown)
        - rows_returned: количество возвращённых строк
        - tokens_used: количество использованных токенов
        - error: сообщение об ошибке
        - **kwargs: дополнительные параметры (script_name, etc.)
        """
        await self.skill._publish_metrics(
            event_type=self.skill._get_event_type_for_success(),
            capability_name=self.capability_name,
            success=success,
            execution_time_ms=execution_time_ms,
            tokens_used=tokens_used,
            execution_type=execution_type,
            rows_returned=rows_returned,
            error=error,
            **kwargs
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

    def _validate_input(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Валидация входных параметров через входной контракт.
        
        RETURNS:
        - Валидированные параметры (Pydantic модель или dict)
        
        RAISES:
        - ValueError если валидация не пройдена
        """
        input_schema = self.get_input_schema()
        if input_schema:
            try:
                return input_schema.model_validate(params)
            except Exception as e:
                raise ValueError(f"Валидация входных параметров не пройдена: {e}")
        return params

    def _validate_output(self, result: Dict[str, Any]) -> Any:
        """
        Валидация результата через выходной контракт.
        
        RETURNS:
        - Валидированный результат (Pydantic модель или dict)
        """
        output_schema = self.get_output_schema()
        if output_schema:
            return output_schema.model_validate(result)
        return result
