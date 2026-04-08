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
from pydantic import BaseModel

from core.models.data.capability import Capability
from core.models.data.execution import ExecutionResult, ExecutionStatus
from core.agent.components.action_executor import ActionExecutor, ExecutionContext
from core.infrastructure.logging import EventBusLogger
from core.components.skills.base_skill import BaseSkill
from typing import Any, Optional, Type, Tuple, Union, List, Dict


class BaseSkillHandler(ABC):
    """
    УНИВЕРСАЛЬНЫЙ БАЗОВЫЙ КЛАСС ДЛЯ ВСЕХ ОБРАБОТЧИКОВ НАВЫКОВ.
    
    АРХИТЕКТУРА:
    - Все входные/выходные данные — Pydantic модели из YAML контрактов
    - Валидация происходит в BaseComponent.execute() ДО вызова хендлера
    - Хендлер работает с типизированными данными
    
    RESPONSIBILITIES:
    - Общий интерфейс для всех хендлеров
    - Доступ к executor и event_bus_logger
    - Унифицированная обработка ошибок
    - Публикация метрик
    """

    capability_name: str = ""

    def __init__(self, skill: BaseSkill):
        self.skill = skill
        self.executor: ActionExecutor = skill.executor
        self.application_context = skill.application_context
        self._event_bus = getattr(skill, '_event_bus', None)
        self.event_bus_logger = getattr(skill, 'event_bus_logger', None)

    @abstractmethod
    async def execute(
        self,
        params: BaseModel,
        execution_context: Any = None
    ) -> BaseModel:
        """
        Выполнение логики хендлера.
        
        АРХИТЕКТУРА:
        - params: Pydantic модель из input_contract (уже валидировано)
        - execution_context: ExecutionContext для доступа к session_context
        
        RETURNS:
        - BaseModel: Pydantic модель для выходного контракта
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
        if hasattr(self.skill, '_publish_with_context'):
            await self.skill._publish_with_context(
                event_type="book_library.info",
                data={"message": message},
                source="book_library"
            )

    async def log_warning(self, message: str) -> None:
        """Логирование предупреждения"""
        if hasattr(self.skill, '_publish_with_context'):
            await self.skill._publish_with_context(
                event_type="book_library.warning",
                data={"message": message},
                source="book_library"
            )

    async def log_error(self, message: str) -> None:
        """Логирование ошибки"""
        if hasattr(self.skill, '_publish_with_context'):
            await self.skill._publish_with_context(
                event_type="book_library.error",
                data={"message": message},
                source="book_library"
            )

    async def log_debug(self, message: str) -> None:
        """Логирование отладочного сообщения"""
        if hasattr(self.skill, '_publish_with_context'):
            await self.skill._publish_with_context(
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

    def _format_table_metadata(self, metadata: Dict[str, Any]) -> str:
        """Форматирование метаданных таблицы в строку для LLM"""
        schema_name = metadata.get("schema_name", "public")
        table_name = metadata.get("table_name", "unknown")
        description = metadata.get("description", "")
        columns = metadata.get("columns", [])

        cols_str = []
        for col in columns:
            col_name = col.get("column_name", "")
            data_type = col.get("data_type", "unknown")
            nullable = "NOT NULL" if col.get("is_nullable") == "NO" else ""
            default = f"DEFAULT {col.get('column_default')}" if col.get("column_default") else ""
            cols_str.append(f"{col_name} {data_type} {nullable} {default}".strip())

        result = f'"{schema_name}"."{table_name}" (\n'
        result += ",\n".join(f"    {c}" for c in cols_str)
        result += "\n)"
        if description:
            result += f" -- {description}"
        return result

    def _get_default_schema_fallback(self, tables_config: List[Dict[str, str]]) -> str:
        """Fallback: возвращает схему с колонками если сервис недоступен"""
        schema_parts = []
        for t in tables_config:
            schema = t.get("schema", "public")
            table = t.get("table", "unknown")
            description = t.get("description", "")
            columns = t.get("columns", [])
            
            if columns:
                cols_str = []
                for col in columns:
                    col_name = col.get("column_name", "")
                    data_type = col.get("data_type", "unknown")
                    nullable = "NOT NULL" if col.get("is_nullable") == "NO" else ""
                    default = f"DEFAULT {col.get('column_default')}" if col.get("column_default") else ""
                    cols_str.append(f"{col_name} {data_type} {nullable} {default}".strip())
                
                result = f'"{schema}"."{table}" (\n'
                result += ",\n".join(f"    {c}" for c in cols_str)
                result += "\n)"
            else:
                result = f'"{schema}"."{table}"'
            
            if description:
                result += f" -- {description}"
            schema_parts.append(result)
        
        return ",\n\n".join(schema_parts)
