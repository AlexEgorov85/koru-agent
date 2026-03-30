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
from typing import Dict, Any, List, Optional
from pathlib import Path

from core.infrastructure.event_bus.unified_event_bus import EventType
from core.models.data.capability import Capability

# Добавим путь к корню проекта
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core.services.skills.base_skill import BaseSkill
from core.config.component_config import ComponentConfig
from core.application_context.application_context import ApplicationContext
from core.agent.components.action_executor import ActionExecutor

from core.services.skills.book_library.handlers import (
    SearchBooksHandler,
    ExecuteScriptHandler,
    ListScriptsHandler,
    SemanticSearchHandler,
)


# ============================================================================
# НАВЫК BOOK_LIBRARY
# ============================================================================

class BookLibrarySkill(BaseSkill):
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

    DEPENDENCIES = ["sql_tool", "sql_generation", "sql_query_service", "table_description_service"]
    name: str = "book_library"

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

        self._scripts_registry: Optional[Dict[str, Any]] = None

        # Инициализация обработчиков
        self._handlers = {}

        if self.event_bus_logger is None:
            self._print_fallback = True
        else:
            self._print_fallback = False

    def get_capabilities(self) -> List[Capability]:
        """
        Возвращает список capability, которые предоставляет навык.

        ВОЗВРАЩАЕТ:
        - List[Capability]: Список из 4 capability
        """
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
                description="Выполнение заготовленного SQL-скрипта по имени. 10 скриптов: get_all_books, get_books_by_author (поиск по фамилии), get_books_by_genre, get_books_by_year_range, get_book_by_id, count_books_by_author, get_books_by_title_pattern, get_distinct_authors, get_distinct_genres, get_genre_statistics. Нормализованная схема: Lib.books JOIN Lib.authors. Быстро ~100мс.",
                skill_name=self.name,
                supported_strategies=["react", "planning"],
                visiable=True,
                meta={
                    "requires_llm": False,
                    "execution_type": "static",
                    "scripts_count": 10,
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
            if self.event_bus_logger:
                await self.event_bus_logger.error(f"Ошибка загрузки реестра скриптов: {e}")
                  # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
                  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            else:
                self.logger.error(f"Ошибка загрузки реестра скриптов: {e}")
                  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            self._scripts_registry = {}

        # Инициализация обработчиков
        self._handlers = {
            "book_library.search_books": SearchBooksHandler(self),
            "book_library.execute_script": ExecuteScriptHandler(self),
            "book_library.list_scripts": ListScriptsHandler(self),
            "book_library.semantic_search": SemanticSearchHandler(self),
        }

        return True

    def _get_event_type_for_success(self) -> EventType:
        """Возвращает тип события для успешного выполнения навыка библиотеки."""
        return EventType.SKILL_EXECUTED

    async def _execute_impl(
        self,
        capability: 'Capability',
        parameters: Dict[str, Any],
        execution_context: Any
    ) -> Any:
        """
        Реализация бизнес-логики навыка библиотеки (ASYNC).

        Делегирует выполнение соответствующему обработчику.

        ВАЖНО: Валидация входа/выхода и метрики выполняются в BaseComponent.execute()
        Здесь только бизнес-логика.

        ВОЗВРАЩАЕТ:
        - Pydantic модель (выходной контракт) или Dict (fallback)
        """
        if capability.name not in self._handlers:
            raise ValueError(f"Навык не поддерживает capability: {capability.name}")

        # Делегирование к обработчику
        handler = self._handlers[capability.name]

        # Конвертируем Pydantic модель в dict если нужно
        if hasattr(parameters, 'model_dump'):
            params_dict = parameters.model_dump()
        elif isinstance(parameters, dict):
            params_dict = parameters
        else:
            params_dict = {}

        return await handler.execute(params_dict, execution_context)

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
    ):
        """Публикация метрик выполнения через EventBus."""
        from core.services.skills.book_library.metrics import publish_book_library_metrics
        await publish_book_library_metrics(
            logger=self.event_bus_logger,
            capability_name=capability_name,
            success=success,
            execution_time_ms=execution_time_ms,
            execution_type=execution_type,
            rows_returned=rows_returned,
            script_name=script_name,
            error=error
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
    return BookLibrarySkill(name, application_context, component_config, executor)
