#!/usr/bin/env python3
"""
Навык проверки результатов.

ТРИ CAPABILITY:
1. check_result.execute_script - выполнение заготовленного скрипта
2. check_result.generate_script - генерация SQL через LLM и выполнение
3. check_result.vector_search - семантический поиск по текстам актов

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

from core.models.data.capability import Capability
from core.models.enums.common_enums import ExecutionStatus

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core.components.skills.skill import Skill
from core.config.component_config import ComponentConfig
from core.application_context.application_context import ApplicationContext
from core.agent.components.action_executor import ActionExecutor
from core.agent.components.action_executor import ExecutionContext

from core.components.skills.check_result.handlers import (
    ExecuteScriptHandler,
    GenerateScriptHandler,
    VectorSearchHandler,
)
from core.models.data.capability import Capability


CHECK_RESULT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(CHECK_RESULT_DIR))))
TABLES_CONFIG_PATH = os.path.join(PROJECT_ROOT, "data", "skills", "check_result", "tables.yaml")


class CheckResultSkill(Skill):
    """
    Навык проверки результатов.

    Поддерживает три режима работы:
    1. execute_script - выполнение заготовленных скриптов
    2. generate_script - генерация SQL через LLM и выполнение
    3. vector_search - семантический поиск по текстам актов
    """

    @property
    def description(self) -> str:
        return "Навык проверки результатов: выполнение и генерация SQL скриптов"

    name: str = "check_result"

    def __init__(
        self,
        name: str,
        component_config: ComponentConfig,
        executor: ActionExecutor,
        application_context: ApplicationContext = None,
    ):
        super().__init__(
            name=name,
            component_config=component_config,
            executor=executor,
            application_context=application_context
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
            "check_result.vector_search": VectorSearchHandler(self),
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
            {"schema": "oarb", "table": "audits"},
            {"schema": "oarb", "table": "audit_reports"},
            {"schema": "oarb", "table": "report_items"},
            {"schema": "oarb", "table": "violations"},
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

    def _get_event_type_for_success(self) -> str:
        return "skill.check_result.executed"

    def get_capabilities(self) -> List[Capability]:
        # Импортируем реестр скриптов из handler
        from .handlers.execute_script_handler import SCRIPTS_REGISTRY
        
        # Формируем детальное описание для execute_script со списком скриптов
        scripts_lines = [
            "📜 ДОСТУПНЫЕ СКРИПТЫ (вызывай ТОЛЬКО эти script_name):"
        ]
        for name, meta in SCRIPTS_REGISTRY.items():
            # Собираем все параметры (required + optional)
            required = meta.get("required_parameters", [])
            optional = meta.get("optional_parameters", [])
            param_descriptions = meta.get("param_descriptions", {})
            all_params = [p for p in required + optional if p != "max_rows"]
            
            # Формат: - script_name (параметры: [a, b], обязательные: [a])
            params_str = ", ".join(all_params) if all_params else "нет"
            req_str = ", ".join(required) if required else "нет"
            
            scripts_lines.append(f"  • `{name}` → параметры: `{params_str}` | обязательные: `{req_str}`")
            
            # Добавляем описания параметров если есть
            if param_descriptions:
                for param, desc in param_descriptions.items():
                    scripts_lines.append(f"      - `{param}`: {desc}")
        
        execute_script_desc = "\n".join(scripts_lines)

        return [
            Capability(
                name="check_result.execute_script",
                description=execute_script_desc,  # ← Список скриптов ВСТРОЕН сюда
                skill_name=self.name,
                supported_strategies=["react"],
                visiable=True
            ),
            Capability(
                name="check_result.generate_script",
                description="Генерация произвольного SQL-скрипта через LLM и его выполнение",
                skill_name=self.name,
                supported_strategies=["react"],
                visiable=True
            ),
            Capability(
                name="check_result.vector_search",
                description=(
                    "Семантический поиск по текстам актов аудиторской проверки и отклонениям "
                    "с использованием FAISS векторной БД. "
                    "Найди фрагменты, где упоминаются определённые нарушения, формулировки, "
                    "ответственные лица или ключевые понятия. "
                    "Параметры: query (текст запроса), source (audits|violations), "
                    "top_k (кол-во результатов), min_score (порог схожести 0.0-1.0)"
                ),
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
        capability,
        success: bool,
        execution_time_ms: float,
        execution_context: Optional[Any] = None,
        **extra_data
    ) -> None:
        """Публикация метрик выполнения навыка в EventBus."""
        capability_name = capability.name if hasattr(capability, 'name') else str(capability)
        event_type = extra_data.get("event_type", "check_result.metrics")
        await self._publish_with_context(
            event_type=event_type,
            data={
                "capability_name": capability_name,
                "success": success,
                "execution_time_ms": execution_time_ms,
                "execution_type": extra_data.get("execution_type", "unknown"),
                "rows_returned": extra_data.get("rows_returned", 0),
                "script_name": extra_data.get("script_name"),
                "error": extra_data.get("error")
            },
            source=self.name
        )


def create_check_result_skill(
    application_context: ApplicationContext,
    component_config: ComponentConfig,
    executor: ActionExecutor,
) -> CheckResultSkill:
    """Фабрика для создания экземпляра CheckResultSkill."""
    return CheckResultSkill(
        name="check_result",
        application_context=application_context,
        component_config=component_config,
        executor=executor,
    )