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
from core.models.enums.common_enums import ExecutionStatus

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
from core.models.data.capability import Capability


CHECK_RESULT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(CHECK_RESULT_DIR))))
TABLES_CONFIG_PATH = os.path.join(PROJECT_ROOT, "data", "skills", "check_result", "tables.yaml")


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
            os.makedirs(os.path.dirname(tables_path), exist_ok=True)
            with open(tables_path, 'w', encoding='utf-8') as f:
                yaml.dump({"tables": self._tables_config}, f, allow_unicode=True, default_flow_style=False)

            await self._publish_with_context(
                event_type="check_result.tables_saved",
                data={"path": tables_path, "tables_count": len(self._tables_config)},
                source=self.name
            )
        else:
            await self._publish_with_context(
                event_type="check_result.tables_empty",
                data={"warning": "table_description_service вернул пустой результат"},
                source=self.name
            )

        return self._tables_config

    async def _generate_tables_config(self) -> List[Dict[str, str]]:
        """
        Формирование конфигурации таблиц через table_description_service.

        ОПТИМИЗАЦИЯ: Один запрос на схему вместо N запросов на таблицы.
        
        ВОЗВРАЩАЕТ:
        - List[Dict]: список таблиц с полным описанием колонок
        """
        default_tables = [
            {"schema": "Lib", "table": "books", "description": "Таблица книг"},
            {"schema": "Lib", "table": "authors", "description": "Таблица авторов"},
        ]

        tables_by_schema: Dict[str, List[str]] = {}
        for t in default_tables:
            schema = t.get("schema", "Lib")
            table = t.get("table", "")
            if table:
                if schema not in tables_by_schema:
                    tables_by_schema[schema] = []
                tables_by_schema[schema].append(table)

        result_tables = []

        for schema, tables in tables_by_schema.items():
            for table_name in tables:
                try:
                    exec_context = ExecutionContext()
                    
                    result = await self.executor.execute_action(
                        action_name="table_description_service.get_table",
                        parameters={
                            "table_name": table_name,
                            "schema_name": schema
                        },
                        context=exec_context
                    )

                    if result.status == ExecutionStatus.COMPLETED and result.data:
                        data = result.data
                        if hasattr(data, 'model_dump'):
                            data = data.model_dump()
                        
                        metadata = data.get("metadata", {})
                        
                        result_tables.append({
                            "schema": schema,
                            "table": table_name,
                            "description": metadata.get("description", ""),
                            "columns": metadata.get("columns", [])
                        })
                    else:
                        raise RuntimeError(f"Не удалось получить описание таблицы {schema}.{table_name}: {result.error}")

                except Exception as e:
                    await self._publish_with_context(
                        event_type="check_result.table_load_error",
                        data={"table": table_name, "schema": schema, "error": str(e)},
                        source=self.name
                    )
                    raise RuntimeError(f"Не удалось получить описание таблицы {schema}.{table_name}: {e}")

        return result_tables

    def get_tables_config(self) -> Optional[List[Dict[str, str]]]:
        """Получение конфигурации таблиц (для использования в handlers)"""
        return self._tables_config

    def _get_event_type_for_success(self) -> EventType:
        return EventType.SKILL_EXECUTED

    def get_capabilities(self) -> List[Capability]:
        return [
            Capability(
                name="check_result.execute_script",
                description="Выполнение заготовленного SQL скрипта",
                skill_name=self.name,
                supported_strategies=["react"],
                visiable=True
            ),
            Capability(
                name="check_result.generate_script",
                description="Генерация SQL скрипта через LLM и выполнение",
                skill_name=self.name,
                supported_strategies=["react"],
                visiable=True
            ),
        ]

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