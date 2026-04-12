"""
Универсальный базовый класс для всех обработчиков навыков (Skill Handlers).

ARCHITECTURE:
- Наследуется всеми Skill handlers (book_library, data_analysis, final_answer, planning, etc.)
- Не содержит бизнес-логики конкретного навыка
- Предоставляет общие утилиты для всех хендлеров
- Устраняет дублирование кода между навыками
- Теперь наследуется от Component для консистентного логирования

RESPONSIBILITIES:
- Общий интерфейс для всех хендлеров
- Доступ к executor и event_bus через Component
- Унифицированная обработка ошибок
- Публикация метрик
- Валидация входных/выходных данных через контракты
"""
from abc import ABC, abstractmethod
from typing import Any, Optional, Type, Dict
from pydantic import BaseModel

from core.models.data.capability import Capability
from core.models.data.execution import ExecutionResult, ExecutionStatus
from core.agent.components.action_executor import ActionExecutor, ExecutionContext
from core.config.component_config import ComponentConfig
from core.agent.components.component import Component


class SkillHandler(Component, ABC):
    """
    УНИВЕРСАЛЬНЫЙ БАЗОВЫЙ КЛАСС ДЛЯ ВСЕХ ОБРАБОТЧИКОВ НАВЫКОВ.
    
    АРХИТЕКТУРА:
    - Все входные/выходные данные — Pydantic модели из YAML контрактов
    - Валидация происходит в Component.execute() ДО вызова хендлера
    - Хендлер работает с типизированными данными
    - Наследует Component для консистентного логирования
    
    RESPONSIBILITIES:
    - Общий интерфейс для всех хендлеров
    - Доступ к executor через Component
    - Унифицированная обработка ошибок
    - Публикация метрик
    """
    
    capability_name: str = ""

    def __init__(
        self,
        name: Optional[str] = None,
        component_config: Optional[ComponentConfig] = None,
        executor: Optional[ActionExecutor] = None,
        skill: Optional[Any] = None,
        application_context: Optional[Any] = None
    ):
        """
        Инициализация хендлера.

        ОБРАТНАЯ СОВМЕСТИМОСТЬ: Если вызван как SkillHandler(skill) —
        берёт component_config, executor, application_context из skill.

        ARGS:
        - name: Имя хендлера (обычно capability_name)
        - component_config: Конфигурация компонента
        - executor: ActionExecutor для взаимодействия
        - skill: Родительский навык
        - application_context: ApplicationContext
        """
        # Обратная совместимость: SkillHandler(skill) — когда передан 1 позиционный аргумент
        if name is not None and component_config is None and executor is None and skill is None:
            skill = name
            if hasattr(skill, 'component_config'):
                component_config = skill.component_config
            if hasattr(skill, 'executor'):
                executor = skill.executor
            if hasattr(skill, 'application_context'):
                application_context = skill.application_context
            name = getattr(self, 'capability_name', None) or getattr(skill, 'name', 'handler')

        super().__init__(
            name=name or self.capability_name or "handler",
            component_type="handler",
            component_config=component_config,
            executor=executor,
            application_context=application_context
        )
        
        # Сохраняем ссылку на родительский навык
        self.skill = skill

    async def _execute_impl(
        self,
        capability: Capability,
        parameters: Dict[str, Any],
        execution_context: Optional[ExecutionContext] = None
    ) -> Any:
        """
        Выполнение логики хендлера.

        ДЕФОЛТНАЯ РЕАЛИЗАЦИЯ: делегирует execute() для обратной совместимости.
        Подклассы могут переопределить.

        ARGS:
        - capability: Capability для выполнения
        - parameters: Параметры из input_contract
        - execution_context: Контекст выполнения

        RETURNS:
        - Any: Результат выполнения (Pydantic модель или dict)
        """
        if hasattr(self, 'execute') and callable(self.execute):
            return await self.execute(parameters, execution_context)
        raise NotImplementedError(
            f"Хендлер {self.__class__.__name__} не реализует ни _execute_impl, ни execute()"
        )

    async def log_info(self, message: str, event_type=None, **extra_data):
        """Логирование информационного сообщения."""
        if event_type is None:
            from core.infrastructure.logging.event_types import LogEventType
            event_type = LogEventType.INFO
        self._log_info(message, event_type=event_type, **extra_data)

    async def log_warning(self, message: str, event_type=None, **extra_data):
        """Логирование предупреждения."""
        if event_type is None:
            from core.infrastructure.logging.event_types import LogEventType
            event_type = LogEventType.WARNING
        self._log_warning(message, event_type=event_type, **extra_data)

    # === ОБЩИЕ УТИЛИТЫ ДЛЯ ВСЕХ ХЕНДЛЕРОВ ===
    
    def get_input_schema(self) -> Optional[Type[BaseModel]]:
        """Получение входной схемы контракта."""
        return self.get_input_contract(self.capability_name)
    
    def get_output_schema(self) -> Optional[Type[BaseModel]]:
        """Получение выходной схемы контракта."""
        return self.get_output_contract(self.capability_name)

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
        Публикация метрик через parent skill.
        
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
        if self.skill and hasattr(self.skill, '_publish_metrics'):
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
    
    def _validate_input(self, params: Dict[str, Any]) -> Any:
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
        """Форматирование метаданных таблицы в строку для LLM."""
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
    
    async def get_table_descriptions(self, tables_config: list, format_for_llm: bool = False) -> str:
        """
        Получить описание таблиц из конфигурации навыка.
        
        ARGS:
        - tables_config: список таблиц с колонками из skill._tables_config
        - format_for_llm: если True — форматировать для LLM, иначе — raw dict
        
        RETURNS:
        - str: описание таблиц
        """
        if not tables_config:
            return ""
        
        if format_for_llm:
            # Проверяем есть ли колонки (значит table_description_service отработал)
            has_columns = any(t.get("columns") for t in tables_config)
            if has_columns:
                return self._get_default_schema_fallback(tables_config)
            else:
                # Колонки пустые — fallback без колонок
                return ",\n".join(
                    f'"{t.get("schema", "public")}"."{t.get("table", "unknown")}"'
                    for t in tables_config
                )
        else:
            return str(tables_config)
    
    def _get_default_schema_fallback(self, tables_config: list) -> str:
        """Fallback: возвращает схему с колонками если сервис недоступен."""
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
