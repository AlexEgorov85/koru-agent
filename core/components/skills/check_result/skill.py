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
- При инициализации: если файл отсутствует - формируется через table_description_service и сохраняется
"""
import sys
import os
import yaml
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
from core.agent.components.action_executor import ExecutionContext

from core.components.skills.check_result.handlers import (
    ExecuteScriptHandler,
    GenerateScriptHandler,
)


TABLES_CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "..", "..", "data", "skills", "check_result", "tables.yaml"
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
    - При инициализации: если файл отсутствует - формируется через table_description_service
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
        self._tables_config: Optional[List[Dict[str, str]]] = None

    async def initialize(self) -> bool:
        success = await super().initialize()
        if not success:
            return False

        # Загрузка конфигурации таблиц (с автоматическим созданием если отсутствует)
        await self._load_tables_config()

        self._handlers = {
            "check_result.execute_script": ExecuteScriptHandler(self),
            "check_result.generate_script": GenerateScriptHandler(self),
        }

        await self._publish_with_context(
            event_type="check_result.initialized",
            data={
                "capabilities": list(self._handlers.keys()),
                "tables_count": len(self._tables_config) if self._tables_config else 0
            },
            source=self.name
        )

        return True

    async def _load_tables_config(self) -> List[Dict[str, str]]:
        """
        Загрузка конфигурации таблиц.

        ЛОГИКА:
        1. Если файл tables.yaml существует - загрузить из него
        2. Если файл отсутствует:
           a. Получить описание таблиц через table_description_service
           b. Сохранить в файл tables.yaml
           c. Вернуть полученные данные
        """
        tables_path = os.path.abspath(TABLES_CONFIG_PATH)

        if os.path.exists(tables_path):
            await self._publish_with_context(
                event_type="check_result.tables_loaded",
                data={"source": "file", "path": tables_path},
                source=self.name
            )
            with open(tables_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                self._tables_config = config.get('tables', [])
                return self._tables_config

        # Файл отсутствует - формируем через сервис
        await self._publish_with_context(
            event_type="check_result.tables_generating",
            data={"reason": "file_not_found"},
            source=self.name
        )

        self._tables_config = await self._generate_tables_config()

        if self._tables_config:
            # Сохраняем в файл
            os.makedirs(os.path.dirname(tables_path), exist_ok=True)
            with open(tables_path, 'w', encoding='utf-8') as f:
                yaml.dump({"tables": self._tables_config}, f, allow_unicode=True, default_flow_style=False)
            
            await self._publish_with_context(
                event_type="check_result.tables_saved",
                data={"path": tables_path, "tables_count": len(self._tables_config)},
                source=self.name
            )
        else:
            # Fallback на таблицы по умолчанию
            self._tables_config = [
                {"schema": "Lib", "table": "books", "description": "Таблица книг"},
                {"schema": "Lib", "table": "authors", "description": "Таблица авторов"},
            ]

        return self._tables_config

    async def _generate_tables_config(self) -> List[Dict[str, str]]:
        """
        Формирование конфигурации таблиц через table_description_service.

        ВОЗВРАЩАЕТ:
        - List[Dict]: список таблиц с описанием
        """
        # Читаем текущий tables.yaml для списка таблиц
        default_tables = [
            {"schema": "Lib", "table": "books", "description": "Таблица книг"},
            {"schema": "Lib", "table": "authors", "description": "Таблица авторов"},
        ]

        result_tables = []

        for table_info in default_tables:
            schema = table_info.get("schema", "Lib")
            table_name = table_info.get("table", "")

            if not table_name:
                continue

            try:
                exec_context = ExecutionContext()
                result = await self.executor.execute_action(
                    action_name="table_description_service.execute",
                    parameters={
                        "table_name": table_name,
                        "schema_name": schema
                    },
                    context=exec_context
                )

                if result.status == ExecutionStatus.COMPLETED and result.data:
                    table_meta = result.data
                    columns = table_meta.get("columns", [])
                    column_list = ", ".join([c.get("column_name", "") for c in columns[:5]])
                    description = f"{table_name}: {column_list}..."
                else:
                    description = table_info.get("description", "")

            except Exception as e:
                await self._publish_with_context(
                    event_type="check_result.table_load_error",
                    data={"table": table_name, "error": str(e)},
                    source=self.name
                )
                description = table_info.get("description", "")

            result_tables.append({
                "schema": schema,
                "table": table_name,
                "description": description
            })

        return result_tables

    def get_tables_config(self) -> Optional[List[Dict[str, str]]]:
        """Получение конфигурации таблиц (для использования в handlers)"""
        return self._tables_config

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