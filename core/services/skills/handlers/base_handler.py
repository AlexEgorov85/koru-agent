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
from typing import Dict, Any, Optional, Type, TYPE_CHECKING, Tuple

from pydantic import BaseModel

from core.models.data.capability import Capability
from core.models.data.execution import ExecutionResult, ExecutionStatus
from core.agent.components.action_executor import ActionExecutor, ExecutionContext
from core.infrastructure.logging import EventBusLogger
  # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()

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
        self._event_bus = skill._event_bus if hasattr(skill, '_event_bus') else None

    @abstractmethod
    async def execute(
        self,
        params: Dict[str, Any],
        execution_context: Any = None
    ) -> ExecutionResult:
        """
        Выполнение логики хендлера.
        
        СТАНДАРТНАЯ СИГНАТУРА:
        - params: входные параметры (валидированные)
        - execution_context: ExecutionContext для доступа к session_context
        
        RETURNS:
        - ExecutionResult: результат выполнения
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
        if self._event_bus:
            await self._event_bus.publish(
                event_type="book_library.info",
                data={"message": message},
                source="book_library"
            )

    async def log_warning(self, message: str) -> None:
        """Логирование предупреждения"""
        if self._event_bus:
            await self._event_bus.publish(
                event_type="book_library.warning",
                data={"message": message},
                source="book_library"
            )

    async def log_error(self, message: str) -> None:
        """Логирование ошибки"""
        if self._event_bus:
            await self._event_bus.publish(
                event_type="book_library.error",
                data={"message": message},
                source="book_library"
            )

    async def log_debug(self, message: str) -> None:
        """Логирование отладочного сообщения"""
        if self._event_bus:
            await self._event_bus.publish(
                event_type="book_library.debug",
                data={"message": message},
                source="book_library"
            )

    async def user_message(self, message: str, icon: str = "ℹ️") -> None:
        """Сообщение пользователю (выводится в терминал)"""
        if self.event_bus_logger:
            await self.event_bus_logger.user_message(message, icon=icon)

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

    # === ОБЩИЕ МЕТОДЫ ДЛЯ УСТРАНЕНИЯ ДУБЛИРОВАНИЯ ===

    def _extract_params(
        self,
        params: Dict[str, Any],
        field_names: Tuple[str, ...] = ('query', 'max_results'),
        defaults: Tuple[Any, ...] = ('', 10)
    ) -> Tuple[Any, ...]:
        """
        Извлечение параметров из dict или Pydantic модели.

        УНИВЕРСАЛЬНЫЙ МЕТОД — работает для всех хендлеров!

        ARGS:
        - params: входные параметры (dict или Pydantic модель)
        - field_names: имена полей для извлечения (например, ('query', 'max_results'))
        - defaults: значения по умолчанию для каждого поля

        RETURNS:
        - Tuple: значения извлеченных параметров в порядке field_names

        RAISES:
        - ValueError: если валидация не пройдена или контракт не загружен
        """
        if isinstance(params, BaseModel):
            return tuple(getattr(params, name, default) for name, default in zip(field_names, defaults))
        else:
            input_schema = self.get_input_schema()
            if input_schema:
                try:
                    validated_params = input_schema.model_validate(params)
                    return tuple(
                        getattr(validated_params, name, default)
                        for name, default in zip(field_names, defaults)
                    )
                except Exception as e:
                    raise ValueError(f"Ошибка валидации параметров: {e}")
            else:
                raise ValueError(
                    f"Входной контракт для {self.capability_name} не загружен. "
                    f"Убедитесь что компонент инициализирован корректно."
                )

    async def _execute_sql(
        self,
        sql: str,
        max_rows: int = 50,
        parameters: Optional[Dict[str, Any]] = None
    ) -> Tuple[list, float]:
        """
        Выполнение SQL запроса через sql_query сервис.

        УНИВЕРСАЛЬНЫЙ МЕТОД — работает для всех хендлеров!

        ARGS:
        - sql: SQL запрос для выполнения
        - max_rows: максимальное количество возвращаемых строк
        - parameters: параметры для параметризованного запроса

        RETURNS:
        - Tuple: (rows, execution_time)

        RAISES:
        - RuntimeError: если выполнение SQL завершилось с ошибкой
        """
        rows = []
        execution_time = 0.0

        try:
            exec_context = ExecutionContext()
            result = await self.executor.execute_action(
                action_name="sql_query.execute",
                parameters={
                    "sql": sql,
                    "parameters": parameters or {},
                    "max_rows": max_rows
                },
                context=exec_context
            )

            if result.status == ExecutionStatus.COMPLETED and result.data:
                rows = result.data.rows if hasattr(result.data, 'rows') else []
                execution_time = result.data.execution_time if hasattr(result.data, 'execution_time') else 0.0
                await self.log_info(f"Найдено строк: {len(rows)}")
            else:
                raise RuntimeError(f"Ошибка выполнения SQL: {result.error}")

        except Exception as e:
            await self.log_error(f"Ошибка выполнения SQL: {e}")
            raise RuntimeError(f"Ошибка выполнения SQL запроса: {e}")

        return rows, execution_time
