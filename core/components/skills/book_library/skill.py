#!/usr/bin/env python3
"""
Навык работы с библиотекой книг.

ТРИ CAPABILITY:
1. book_library.search_books - динамическая генерация SQL через LLM
2. book_library.execute_script - выполнение заготовленного скрипта
3. book_library.list_scripts - получение списка доступных скриптов
4. book_library.semantic_search - семантический поиск через векторную БД

АРХИТЕКТУРА:
- skill.py: координация и маршрутизация
- handlers/: обработчики для каждой capability (разделение ответственностей)
- metrics.py: публикация метрик
- scripts_registry.py: реестр скриптов
"""
import sys
import os
from typing import Any, Dict, List, Optional
from pathlib import Path
from pydantic import BaseModel
import yaml

from core.models.data.capability import Capability

# Добавим путь к корню проекта
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core.components.skills.skill import Skill
from core.config.component_config import ComponentConfig
from core.application_context.application_context import ApplicationContext
from core.agent.components.action_executor import ActionExecutor, ExecutionContext
from core.models.data.execution import ExecutionStatus

from core.components.skills.book_library.handlers import (
    SearchBooksHandler,
    ExecuteScriptHandler,
    ListScriptsHandler,
    SemanticSearchHandler,
)
from core.infrastructure.logging.event_types import LogEventType


BOOK_LIBRARY_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(BOOK_LIBRARY_DIR))))
TABLES_CONFIG_PATH = os.path.join(PROJECT_ROOT, "data", "skills", "book_library", "tables.yaml")


# ============================================================================
# НАВЫК BOOK_LIBRARY
# ============================================================================

class BookLibrarySkill(Skill):
    """
    Навык для работы с библиотекой книг.

    Поддерживает четыре режима работы:
    1. Динамический (search_books) - генерация SQL через LLM
    2. Статический (execute_script) - выполнение заготовленных скриптов
    3. Информационный (list_scripts) - получение списка доступных скриптов
    4. Векторный (semantic_search) - семантический поиск через FAISS

    АРХИТЕКТУРА (YAML-Only):
    - Схемы валидации находятся ТОЛЬКО в YAML контрактах (data/contracts/)
    - Навык использует кэшированные схемы через get_cached_*_schema_safe()
    - Никаких Pydantic моделей в коде!
    """

    @property
    def description(self) -> str:
        return "Навык работы с библиотекой книг: поиск, выполнение скриптов, семантический поиск"

    name: str = "book_library"

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

        self._scripts_registry: Optional[Dict[str, Any]] = None

        # Инициализация обработчиков
        self._handlers = {}

    def get_capabilities(self) -> List[Capability]:
        from .scripts_registry import SCRIPTS_REGISTRY
        
        scripts_lines = ["Доступные скрипты:"]
        for name, config in SCRIPTS_REGISTRY.items():
            parameters = config.parameters
            
            required = []
            param_descriptions = {}
            
            for param_name, param_config in parameters.items():
                if param_name == "max_rows":
                    continue
                if isinstance(param_config, dict):
                    if param_config.get("required", False):
                        required.append(param_name)
                    if param_config.get("description"):
                        param_descriptions[param_name] = param_config["description"]
                else:
                    required.append(param_name)
            
            params_str = ", ".join(required) if required else "нет"
            line = f"  • `{name}` → параметры: `{params_str}`"
            scripts_lines.append(line)
            
            if param_descriptions:
                for param, desc in param_descriptions.items():
                    scripts_lines.append(f"      - `{param}`: {desc}")
        
        scripts_desc = "\n".join(scripts_lines)
        
        return [
            Capability(
                name="book_library.search_books",
                description="Динамический поиск книг с генерацией SQL через LLM (гибко, но медленно ~2000мс)",
                skill_name=self.name,
                supported_strategies=["react", "planning"],
                visiable=True,
                meta={
                    "requires_llm": True,
                    "execution_type": "dynamic"
                }
            ),
            Capability(
                name="book_library.execute_script",
                description=f"Выполнение заготовленного SQL-скрипта по имени. Быстро ~100мс.\n\n{scripts_desc}",
                skill_name=self.name,
                supported_strategies=["react", "planning"],
                visiable=True,
                meta={
                    "requires_llm": False,
                    "execution_type": "static",
                    "scripts_count": len(SCRIPTS_REGISTRY),
                    "schema": "normalized (books JOIN authors)"
                }
            ),
            Capability(
                name="book_library.list_scripts",
                description="Получение подробного списка доступных скриптов с описаниями и примерами (используйте если нужна детальная информация)",
                skill_name=self.name,
                supported_strategies=["react", "planning"],
                visiable=True,
                meta={
                    "requires_llm": False,
                    "execution_type": "informational"
                }
            ),
            Capability(
                name="book_library.semantic_search",
                description="Семантический поиск по текстам книг с использованием векторной БД (быстрый поиск по смыслу, а не ключевым словам)",
                skill_name=self.name,
                supported_strategies=["react", "planning"],
                visiable=True,
                meta={
                    "requires_llm": False,
                    "execution_type": "vector"
                }
            )
        ]

    async def initialize(self) -> bool:
        """Инициализация навыка с предзагрузкой необходимых ресурсов"""
        success = await super().initialize()
        if not success:
            return False

        # Загрузка реестра скриптов
        try:
            from .scripts_registry import get_all_scripts
            self._scripts_registry = get_all_scripts()
        except Exception as e:
            self._log_error(f"Ошибка загрузки реестра скриптов: {e}", event_type=LogEventType.ERROR)
            self._scripts_registry = {}

        # Инициализация обработчиков
        self._handlers = {
            "book_library.search_books": SearchBooksHandler(
                name="search_books",
                component_config=self.component_config,
                executor=self.executor,
                skill=self
            ),
            "book_library.execute_script": ExecuteScriptHandler(
                name="execute_script",
                component_config=self.component_config,
                executor=self.executor,
                skill=self
            ),
            "book_library.list_scripts": ListScriptsHandler(
                name="list_scripts",
                component_config=self.component_config,
                executor=self.executor,
                skill=self
            ),
            "book_library.semantic_search": SemanticSearchHandler(
                name="semantic_search",
                component_config=self.component_config,
                executor=self.executor,
                skill=self
            ),
        }

        # Загрузка конфигурации таблиц
        self._tables_config = await self._load_tables_config()

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
                event_type="book_library.tables_loaded",
                data={"source": "file", "path": tables_path},
                source=self.name
            )
            with open(tables_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                return config.get('tables', [])

        await self._publish_with_context(
            event_type="book_library.tables_generating",
            data={"reason": "file_not_found"},
            source=self.name
        )

        self._tables_config = await self._generate_tables_config()

        if self._tables_config:
            os.makedirs(os.path.dirname(tables_path), exist_ok=True)
            with open(tables_path, 'w', encoding='utf-8') as f:
                yaml.dump({"tables": self._tables_config}, f, allow_unicode=True, default_flow_style=False)
            
            await self._publish_with_context(
                event_type="book_library.tables_saved",
                data={"path": tables_path, "tables_count": len(self._tables_config)},
                source=self.name
            )
        else:
            await self._publish_with_context(
                event_type="book_library.tables_empty",
                data={"warning": "table_description_service вернул пустой результат"},
                source=self.name
            )

        return self._tables_config

    async def _generate_tables_config(self) -> List[Dict[str, str]]:
        """
        Формирование конфигурации таблиц через table_description_service.
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
                        event_type="book_library.table_load_error",
                        data={"table": table_name, "schema": schema, "error": str(e)},
                        source=self.name
                    )
                    raise RuntimeError(f"Не удалось получить описание таблицы {schema}.{table_name}: {e}")

        return result_tables

    def get_tables_config(self) -> Optional[List[Dict[str, str]]]:
        """Получение конфигурации таблиц (для использования в handlers)"""
        return self._tables_config

    def _get_event_type_for_success(self) -> str:
        """Возвращает тип события для успешного выполнения навыка библиотеки."""
        return "skill.book_library.executed"

    async def _execute_impl(
        self,
        capability: 'Capability',
        parameters: BaseModel,
        execution_context: Any
    ) -> BaseModel:
        """
        Реализация бизнес-логики навыка библиотеки (ASYNC).

        АРХИТЕКТУРА:
        - parameters: Pydantic модель из input_contract (уже валидировано в BaseComponent.execute)
        - Возвращает Pydantic модель выходного контракта
        - Валидация и оборачивание в ExecutionResult происходит в BaseComponent

        ВОЗВРАЩАЕТ:
        - BaseModel: Pydantic модель выходного контракта
        """
        if capability.name not in self._handlers:
            raise ValueError(f"Навык не поддерживает capability: {capability.name}")

        handler = self._handlers[capability.name]
        return await handler.execute(parameters, execution_context)

    def _get_allowed_scripts(self) -> Dict[str, Dict[str, Any]]:
        """
        Реестр разрешённых SQL-скриптов.

        Возвращает скрипты из scripts_registry.py — единого источника истины.
        """
        if not self._scripts_registry:
            raise RuntimeError(
                "Scripts registry не загружен! "
                "Проверьте инициализацию BookLibrarySkill."
            )

        return {name: config.to_dict() for name, config in self._scripts_registry.items()}

    async def _publish_metrics(
        self,
        capability: Optional[Any] = None,
        success: bool = False,
        execution_time_ms: float = 0.0,
        execution_context: Optional[Any] = None,
        **extra_data
    ):
        """Публикация метрик выполнения через EventBus."""
        from core.components.skills.book_library.metrics import publish_book_library_metrics
        capability_name = capability.name if capability and hasattr(capability, 'name') else extra_data.get('capability_name', str(capability) if capability else 'unknown')
        await publish_book_library_metrics(
            logger=None,
            capability_name=capability_name,
            success=success,
            execution_time_ms=execution_time_ms,
            execution_type=extra_data.get("execution_type", "unknown"),
            rows_returned=extra_data.get("rows_returned", 0),
            script_name=extra_data.get("script_name"),
            error=extra_data.get("error"),
            event_type=extra_data.get("event_type")
        )


# ============================================================================
# ФАБРИЧНЫЙ МЕТОД
# ============================================================================

def create_book_library_skill(
    name: str,
    application_context: ApplicationContext,
    component_config: ComponentConfig,
    executor: ActionExecutor
) -> BookLibrarySkill:
    """
    Фабричный метод для создания экземпляра BookLibrarySkill.

    Args:
        name: имя навыка
        application_context: контекст приложения
        component_config: конфигурация компонента
        executor: исполнитель действий

    Returns:
        BookLibrarySkill: экземпляр навыка
    """
    return BookLibrarySkill(name, component_config, executor, application_context)
