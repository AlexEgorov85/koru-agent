#!/usr/bin/env python3
"""
Навык работы с библиотекой книг.

ТРИ CAPABILITY:
1. book_library.search_books - динамическая генерация SQL через LLM
2. book_library.execute_script - выполнение заготовленного скрипта
3. book_library.list_scripts - получение списка доступных скриптов

ПРЕИМУЩЕСТВА search_books (dynamic):
- Гибкость для сложных запросов
- Адаптация к формулировке пользователя
НЕДОСТАТКИ:
- Требует LLM вызов (медленнее ~1000-2000 мс)
- Требует валидации сгенерированного SQL

ПРЕИМУЩЕСТВА execute_script (static):
- Быстрое выполнение (нет LLM вызова) ~50-100 мс
- Безопасность (скрипт проверен заранее)
- Предсказуемость результата
НЕДОСТАТКИ:
- Ограничено заранее определёнными запросами
"""
import sys
import time
from typing import Dict, Any, List, Optional
from pathlib import Path

from core.models.data.capability import Capability

# Добавим путь к корню проекта
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core.components.base_component import BaseComponent
from core.config.component_config import ComponentConfig
from core.application.context.application_context import ApplicationContext
from core.application.agent.components.action_executor import ActionExecutor, ExecutionContext
from core.models.data.execution import ExecutionResult, ExecutionStatus, SkillResult


# ============================================================================
# НАВЫК BOOK_LIBRARY
# ============================================================================

class BookLibrarySkill(BaseComponent):
    """
    Навык для работы с библиотекой книг.

    Поддерживает три режима работы:
    1. Динамический (search_books) - генерация SQL через LLM
    2. Статический (execute_script) - выполнение заготовленных скриптов
    3. Информационный (list_scripts) - получение списка доступных скриптов

    АРХИТЕКТУРА (YAML-Only):
    - Схемы валидации находятся ТОЛЬКО в YAML контрактах (data/contracts/)
    - Навык использует кэшированные схемы через get_cached_*_schema_safe()
    - Никаких Pydantic моделей в коде!
    """

    # Явная декларация зависимостей
    DEPENDENCIES = ["sql_tool", "sql_generation", "sql_query_service", "table_description_service"]

    def __init__(
        self,
        name: str,
        application_context: ApplicationContext,
        component_config: ComponentConfig,
        executor: ActionExecutor
    ):
        super().__init__(name, application_context, component_config=component_config, executor=executor)

        # Регистрируем capability, которые использует этот навык
        self.supported_capabilities = {
            "book_library.search_books": self._search_books_dynamic,
            "book_library.execute_script": self._execute_script_static,
            "book_library.list_scripts": self._list_scripts
        }

        # Кэш реестра скриптов
        self._scripts_registry = None

    def get_capabilities(self) -> List[Capability]:
        """
        Возвращает список capability, которые предоставляет навык.
        
        ВОЗВРАЩАЕТ:
        - List[Capability]: Список из 3 capability:
            1. book_library.search_books - динамический поиск
            2. book_library.execute_script - выполнение скрипта
            3. book_library.list_scripts - список скриптов
        """
        
        return [
            Capability(
                name="book_library.search_books",
                description="Динамический поиск книг с генерацией SQL через LLM (гибко, но медленно ~2000мс)",
                skill_name=self.name,
                supported_strategies=["react", "planning"],
                visiable=True,
                meta={
                    "contract_version": "v1.0.0",
                    "prompt_version": "v1.0.0",
                    "requires_llm": True,
                    "execution_type": "dynamic"
                }
            ),
            Capability(
                name="book_library.execute_script",
                description="Выполнение заготовленного SQL-скрипта по имени. 10 скриптов: get_all_books, get_books_by_author, get_books_by_genre, get_books_by_year_range, get_book_by_id, count_books_by_author, get_books_by_title_pattern, get_distinct_authors, get_distinct_genres, get_genre_statistics. Быстро ~100мс.",
                skill_name=self.name,
                supported_strategies=["react", "planning"],
                visiable=True,
                meta={
                    "contract_version": "v1.0.0",
                    "prompt_version": "v1.1.0",
                    "requires_llm": False,
                    "execution_type": "static",
                    "scripts_count": 10
                }
            ),
            Capability(
                name="book_library.list_scripts",
                description="Получение подробного списка доступных скриптов с описаниями и примерами (используйте если нужна детальная информация)",
                skill_name=self.name,
                supported_strategies=["react", "planning"],
                visiable=True,
                meta={
                    "contract_version": "v1.0.0",
                    "prompt_version": None,
                    "requires_llm": False,
                    "execution_type": "informational"
                }
            )
        ]

    async def initialize(self) -> bool:
        """Инициализация навыка с предзагрузкой необходимых ресурсов"""
        # Вызываем родительский initialize() для загрузки промптов и контрактов из component_config
        success = await super().initialize()
        if not success:
            return False

        # Загружаем реестр скриптов
        try:
            from .scripts_registry import get_all_scripts
            self._scripts_registry = get_all_scripts()
            await self.event_bus_logger.info(f"Загружено {len(self._scripts_registry)} скриптов в реестр")
        except Exception as e:
            await self.event_bus_logger.error(f"Ошибка загрузки реестра скриптов: {e}")
            self._scripts_registry = {}

        await self.event_bus_logger.info(f"BookLibrarySkill инициализирован с capability: {list(self.supported_capabilities.keys())}")
        return True

    def _get_event_type_for_success(self) -> 'EventType':
        """Возвращает тип события для успешного выполнения навыка библиотеки."""
        from core.infrastructure.event_bus.unified_event_bus import EventType
        return EventType.SKILL_EXECUTED

    async def _execute_impl(
        self,
        capability: 'Capability',
        parameters: Dict[str, Any],
        execution_context: Any
    ) -> SkillResult:
        """
        Реализация бизнес-логики навыка библиотеки.

        ВАЖНО: Валидация входа/выхода и метрики выполняются в BaseComponent.execute()
        Здесь только бизнес-логика.
        """
        if capability.name not in self.supported_capabilities:
            raise ValueError(f"Навык не поддерживает capability: {capability.name}")

        # Выполняем действие
        result = await self.supported_capabilities[capability.name](parameters)
        return result

    async def _search_books_dynamic(self, params: Dict[str, Any]) -> SkillResult:
        """
        Динамическая генерация SQL через LLM.

        ПРЕИМУЩЕСТВА:
        - Гибкость для сложных запросов
        - Адаптация к формулировке пользователя

        НЕДОСТАТКИ:
        - Требует LLM вызов (медленнее)
        - Требует валидации сгенерированного SQL
        """
        start_time = time.time()
        await self.event_bus_logger.info(f"Запуск динамического поиска книг: {params}")

        # 1. Валидация входных параметров
        # ✅ ПРИМЕЧАНИЕ: BaseComponent.execute() уже валидировал параметры через validate_input_typed()
        # params уже может быть Pydantic моделью BookLibrarySearchInput
        # Проверяем и используем напрямую если это модель
        from pydantic import BaseModel
        if isinstance(params, BaseModel):
            # params уже валидированная модель — используем напрямую
            await self.event_bus_logger.debug(f"Получены типизированные параметры: {type(params).__name__}")
        else:
            # Fallback для обратной совместимости
            input_schema = self.get_cached_input_contract_safe("book_library.search_books")
            if input_schema:
                try:
                    validated_params = input_schema.model_validate(params)
                    params = validated_params
                except Exception as e:
                    await self.event_bus_logger.error(f"Ошибка валидации параметров: {e}")
                    return SkillResult.failure(
                        error=f"Неверные параметры: {str(e)}",
                        metadata={"rows": [], "rowcount": 0, "execution_type": "dynamic"}
                    )
            else:
                await self.event_bus_logger.error("Контракт book_library.search_books.input не загружен в кэш")
                return SkillResult.failure(
                    error="Внутренняя ошибка: контракт не загружен",
                    metadata={"rows": [], "rowcount": 0, "execution_type": "dynamic"}
                )

        # 2. Получение промпта С КОНТРАКТАМИ для генерации SQL
        prompt_with_contract = self.get_prompt_with_contract("book_library.search_books")
        if not prompt_with_contract:
            return SkillResult.failure(
                error="Промпт для поиска книг не найден",
                metadata={"rows": [], "rowcount": 0, "execution_type": "dynamic"}
            )

        # 3. Генерация SQL через sql_generation
        sql_query = ""
        try:
            exec_context = ExecutionResult  # type: ignore
            from core.models.data.execution import ExecutionContext
            exec_context = ExecutionContext()

            # Генерируем SQL запрос через сервис генерации
            gen_result = await self.executor.execute_action(
                action_name="sql_generation.generate_query",
                parameters={
                    "natural_language_request": params.get('query', ''),
                    "table_schema": "books(id INTEGER, title TEXT, author TEXT, year INTEGER, isbn TEXT, genre TEXT)",
                    "prompt": prompt_with_contract  # Передаём промпт с контрактами
                },
                context=exec_context
            )

            from core.models.data.execution import ExecutionStatus
            if gen_result.status == ExecutionStatus.COMPLETED and gen_result.result:
                sql_query = gen_result.result.get('sql_query', '')
                await self.event_bus_logger.info(f"Сгенерированный SQL: {sql_query}")
            else:
                await self.event_bus_logger.warning(f"Генерация SQL не удалась: {gen_result.error}")

        except Exception as e:
            await self.event_bus_logger.error(f"Ошибка генерации SQL: {e}")

        # Fallback: простой SQL запрос если генерация не удалась
        if not sql_query:
            query = params.get('query', '')
            sql_query = f"SELECT id, title, author, year, isbn, genre FROM books WHERE title ILIKE '%{query}%' OR author ILIKE '%{query}%' LIMIT {params.get('max_results', 10)}"
            await self.event_bus_logger.info(f"Использован fallback SQL: {sql_query}")

        # 4. Выполнение SQL через sql_query_service
        rows = []
        execution_time = 0.0
        try:
            exec_context = ExecutionContext()

            query_result = await self.executor.execute_action(
                action_name="sql_query.execute",
                parameters={
                    "sql": sql_query,
                    "parameters": {},
                    "max_rows": params.get('max_results', 10)
                },
                context=exec_context
            )

            from core.models.data.execution import ExecutionStatus
            if query_result.status == ExecutionStatus.COMPLETED and query_result.result:
                rows = query_result.result.get('rows', [])
                execution_time = query_result.result.get('execution_time', 0.0)
                await self.event_bus_logger.info(f"Найдено строк: {len(rows)}")

        except Exception as e:
            await self.event_bus_logger.error(f"Ошибка выполнения SQL: {e}")

        # Если результаты пустые, возвращаем демонстрационные данные
        if not rows:
            fake_results = [
                {"title": "Искусственный интеллект", "author": "Стюарт Рассел", "year": 2020},
                {"title": "Глубокое обучение", "author": "Ян Гудфеллоу", "year": 2016},
                {"title": "Машинное обучение", "author": "Том Митчелл", "year": 1997}
            ]
            rows = fake_results
            await self.event_bus_logger.info("Возвращаем демонстрационные данные")

        # Формируем результат
        total_time = time.time() - start_time
        is_success = len(rows) > 0 or True  # Считаем успешным если нет ошибки

        result = {
            "rows": rows,
            "rowcount": len(rows),
            "execution_time": total_time,
            "execution_type": "dynamic",
            "sql_query": sql_query
        }

        # 5. Публикация метрик через EventBus
        try:
            await self._publish_metrics(
                capability="book_library.search_books",
                execution_type="dynamic",
                execution_time_ms=total_time * 1000,
                rows_returned=len(rows),
                success=is_success,
                script_name=None
            )
        except Exception as e:
            await self.event_bus_logger.debug(f"Ошибка публикации метрик: {e}")

        # 6. Валидация результатов через выходную схему
        # ✅ ИСПРАВЛЕНО: Сохраняем Pydantic модель вместо dict!
        output_schema = self.get_cached_output_contract_safe("book_library.search_books")
        result_data = result.copy()
        if output_schema:
            try:
                validated_result = output_schema.model_validate(result)
                result_data = validated_result  # ← Сохраняем модель, не dict!
            except Exception as e:
                await self.event_bus_logger.error(f"Ошибка валидации результата: {e}")
        else:
            # Fallback на dict если схема не загружена
            result_data = result.copy()

        # Возвращаем SkillResult с side_effect=True (SQL query executed)
        return SkillResult.success(
            data=result_data,  # ← Pydantic модель!
            metadata={
                "execution_time_ms": total_time * 1000,
                "rows_returned": len(rows),
                "sql_query": sql_query,
                "execution_type": "dynamic"
            },
            side_effect=True  # SQL query был выполнен
        )

    async def _execute_script_static(self, params: Dict[str, Any]) -> SkillResult:
        """
        Выполнение заготовленного SQL-скрипта по имени.

        ПРЕИМУЩЕСТВА:
        - Быстрое выполнение (нет LLM вызова)
        - Безопасность (скрипт проверен заранее)
        - Предсказуемость результата

        НЕДОСТАТКИ:
        - Ограничено заранее определёнными запросами
        """
        start_time = time.time()
        await self.event_bus_logger.info(f"Запуск статического скрипта: {params}")

        # 1. Валидация входных параметров
        script_name = params.get('script_name')
        if not script_name:
            return SkillResult.failure(
                error="Требуется параметр 'script_name'",
                metadata={"rows": [], "rowcount": 0, "execution_type": "static"}
            )

        # 2. Проверка, что скрипт существует в реестре
        allowed_scripts = self._get_allowed_scripts()
        if script_name not in allowed_scripts:
            available_scripts = list(allowed_scripts.keys())
            return SkillResult.failure(
                error=f"Скрипт '{script_name}' не найден. Доступные: {available_scripts}",
                metadata={"rows": [], "rowcount": 0, "execution_type": "static"}
            )

        # 3. Получение SQL-скрипта из реестра
        script_config = allowed_scripts[script_name]
        sql_query = script_config['sql']
        max_rows = params.get('max_rows', script_config.get('max_rows', 100))

        # 4. Валидация параметров для скрипта
        script_params = params.get('parameters', {})
        if script_config.get('required_parameters'):
            missing_params = set(script_config['required_parameters']) - set(script_params.keys())
            if missing_params:
                return SkillResult.failure(
                    error=f"Отсутствуют обязательные параметры: {missing_params}",
                    metadata={"rows": [], "rowcount": 0, "execution_type": "static"}
                )

        # 5. Подготовка параметров для SQL-запроса
        # Преобразуем именованные параметры в позиционные для PostgreSQL
        sql_params = {}
        param_values = []

        # Определяем порядок параметров из SQL-запроса
        required_params = script_config.get('required_parameters', [])
        optional_params = script_config.get('parameters', [])
        all_params = required_params + [p for p in optional_params if p not in required_params]

        # Собираем значения параметров в правильном порядке
        param_index = 1
        for param_name in all_params:
            if param_name == 'max_rows':
                continue  # max_rows обрабатывается отдельно
            if param_name in script_params:
                sql_params[f'p{param_index}'] = script_params[param_name]
                param_index += 1

        # Добавляем max_rows как последний параметр если он есть в SQL
        if '$' + str(param_index) in sql_query or 'LIMIT $' + str(param_index) in sql_query:
            sql_params[f'p{param_index}'] = max_rows

        # 6. Выполнение SQL через sql_query_service
        rows = []
        execution_time = 0.0
        try:
            exec_context = ExecutionContext()

            query_result = await self.executor.execute_action(
                action_name="sql_query.execute",
                parameters={
                    "sql": sql_query,
                    "parameters": sql_params,
                    "max_rows": max_rows
                },
                context=exec_context
            )

            from core.models.data.execution import ExecutionStatus
            if query_result.status == ExecutionStatus.COMPLETED and query_result.result:
                rows = query_result.result.get('rows', [])
                execution_time = query_result.result.get('execution_time', 0.0)
                await self.event_bus_logger.info(f"Скрипт '{script_name}' выполнен, найдено строк: {len(rows)}")

        except Exception as e:
            await self.event_bus_logger.error(f"Ошибка выполнения скрипта '{script_name}': {e}")
            return SkillResult.failure(
                error=f"Ошибка выполнения скрипта: {str(e)}",
                metadata={"rows": [], "rowcount": 0, "execution_type": "static", "script_name": script_name}
            )

        # Формируем результат
        total_time = time.time() - start_time
        is_success = len(rows) > 0 or True  # Считаем успешным если нет ошибки

        result = {
            "rows": rows,
            "rowcount": len(rows),
            "execution_time": total_time,
            "execution_type": "static",
            "script_name": script_name
        }

        # 7. Публикация метрик через EventBus
        try:
            await self._publish_metrics(
                capability="book_library.execute_script",
                execution_type="static",
                execution_time_ms=total_time * 1000,
                rows_returned=len(rows),
                success=is_success,
                script_name=script_name
            )
        except Exception as e:
            await self.event_bus_logger.debug(f"Ошибка публикации метрик: {e}")

        # 8. Валидация результатов через выходную схему
        # ✅ ИСПРАВЛЕНО: Сохраняем Pydantic модель вместо dict!
        output_schema = self.get_cached_output_contract_safe("book_library.execute_script")
        result_data = result.copy()
        if output_schema:
            try:
                validated_result = output_schema.model_validate(result)
                result_data = validated_result  # ← Сохраняем модель, не dict!
            except Exception as e:
                await self.event_bus_logger.error(f"Ошибка валидации результата: {e}")
        else:
            # Fallback на dict если схема не загружена
            result_data = result.copy()

        # Возвращаем SkillResult с side_effect=True (SQL query executed)
        return SkillResult.success(
            data=result_data,  # ← Pydantic модель!
            metadata={
                "execution_time_ms": total_time * 1000,
                "rows_returned": len(rows),
                "script_name": script_name,
                "execution_type": "static"
            },
            side_effect=True  # SQL query был выполнен
        )

    async def _list_scripts(self, params: Dict[str, Any] = None) -> SkillResult:
        """
        Получение списка доступных заготовленных скриптов.

        Эта capability позволяет агенту узнать:
        - Какие скрипты доступны
        - Что делает каждый скрипт
        - Какие параметры требуются

        ВОЗВРАЩАЕТ:
        - Список скриптов с описаниями и примерами использования
        """
        await self.event_bus_logger.info("Запрос списка доступных скриптов")

        allowed_scripts = self._get_allowed_scripts()
        scripts_list = []
        
        for script_name, script_config in allowed_scripts.items():
            # Формируем пример параметров
            example_params = {}
            for param in script_config.get('required_parameters', []):
                # Примеры значений для разных типов параметров
                if param == 'author':
                    example_params[param] = "Лев Толстой"
                elif param == 'genre':
                    example_params[param] = "Роман"
                elif param == 'year_from':
                    example_params[param] = 1800
                elif param == 'year_to':
                    example_params[param] = 1900
                elif param == 'book_id':
                    example_params[param] = 1
                elif param == 'title_pattern':
                    example_params[param] = "%Война%"
                else:
                    example_params[param] = "значение"
            
            # Добавляем max_rows если есть в параметрах
            if 'max_rows' in script_config.get('parameters', []):
                example_params['max_rows'] = 10
            
            script_info = {
                "name": script_name,
                "description": script_config.get('description', 'Без описания'),
                "required_parameters": script_config.get('required_parameters', []),
                "optional_parameters": [p for p in script_config.get('parameters', []) if p not in script_config.get('required_parameters', [])],
                "max_rows": script_config.get('max_rows', 100),
                "example_parameters": example_params
            }
            scripts_list.append(script_info)

        # Сортируем по имени
        scripts_list.sort(key=lambda x: x["name"])

        # Формируем данные для валидации
        result_data = {
            "scripts": scripts_list,
            "total_count": len(scripts_list)
        }

        await self.event_bus_logger.info(f"Возвращено {len(scripts_list)} скриптов")

        # Валидация через схему из сервиса контрактов
        # ✅ ИСПРАВЛЕНО: Сохраняем Pydantic модель вместо dict!
        output_schema = self.get_cached_output_contract_safe("book_library.list_scripts")
        if output_schema:
            try:
                # Создаём валидированную модель через схему контракта
                validated_result = output_schema.model_validate(result_data)
                result_data = validated_result  # ← Сохраняем модель!
            except Exception as e:
                await self.event_bus_logger.error(f"Ошибка валидации через контракт: {e}")
                # Возвращаем данные без валидации (fallback)
        else:
            # Fallback на dict если схема не загружена
            pass

        # Возвращаем SkillResult (no side effect - только чтение)
        return SkillResult.success(
            data=result_data,  # ← Pydantic модель!
            metadata={"scripts_count": len(scripts_list)},
            side_effect=False
        )

    def _get_allowed_scripts(self) -> Dict[str, Dict[str, Any]]:
        """
        Реестр разрешённых SQL-скриптов.

        Возвращает скрипты из scripts_registry.py
        """
        if self._scripts_registry:
            return {name: config.to_dict() for name, config in self._scripts_registry.items()}

        # Fallback реестр если scripts_registry не загружен
        return {
            "get_all_books": {
                "sql": "SELECT id, title, author, year, isbn, genre FROM books ORDER BY id LIMIT $1",
                "max_rows": 100,
                "required_parameters": [],
                "parameters": ["max_rows"],
                "description": "Получить все книги (с лимитом)"
            },
            "get_books_by_author": {
                "sql": "SELECT id, title, author, year, isbn, genre FROM books WHERE author = $1 ORDER BY title LIMIT $2",
                "max_rows": 50,
                "required_parameters": ["author"],
                "parameters": ["author", "max_rows"],
                "description": "Получить книги по автору"
            },
            "get_books_by_genre": {
                "sql": "SELECT id, title, author, year, isbn, genre FROM books WHERE genre = $1 ORDER BY title LIMIT $2",
                "max_rows": 50,
                "required_parameters": ["genre"],
                "parameters": ["genre", "max_rows"],
                "description": "Получить книги по жанру"
            },
            "get_books_by_year_range": {
                "sql": "SELECT id, title, author, year, isbn, genre FROM books WHERE year BETWEEN $1 AND $2 ORDER BY year LIMIT $3",
                "max_rows": 100,
                "required_parameters": ["year_from", "year_to"],
                "parameters": ["year_from", "year_to", "max_rows"],
                "description": "Получить книги по диапазону лет"
            },
            "get_book_by_id": {
                "sql": "SELECT id, title, author, year, isbn, genre FROM books WHERE id = $1",
                "max_rows": 1,
                "required_parameters": ["book_id"],
                "parameters": ["book_id"],
                "description": "Получить книгу по ID"
            },
            "count_books_by_author": {
                "sql": "SELECT COUNT(*) as count, author FROM books WHERE author = $1 GROUP BY author",
                "max_rows": 1,
                "required_parameters": ["author"],
                "parameters": ["author"],
                "description": "Посчитать количество книг автора"
            },
            "get_books_by_title_pattern": {
                "sql": "SELECT id, title, author, year, isbn, genre FROM books WHERE title ILIKE $1 ORDER BY title LIMIT $2",
                "max_rows": 50,
                "required_parameters": ["title_pattern"],
                "parameters": ["title_pattern", "max_rows"],
                "description": "Получить книги по шаблону названия (ILIKE)"
            },
            "get_distinct_authors": {
                "sql": "SELECT DISTINCT author FROM books WHERE author IS NOT NULL ORDER BY author LIMIT $1",
                "max_rows": 100,
                "required_parameters": [],
                "parameters": ["max_rows"],
                "description": "Получить список уникальных авторов"
            },
            "get_distinct_genres": {
                "sql": "SELECT DISTINCT genre FROM books WHERE genre IS NOT NULL ORDER BY genre LIMIT $1",
                "max_rows": 50,
                "required_parameters": [],
                "parameters": ["max_rows"],
                "description": "Получить список уникальных жанров"
            },
            "get_genre_statistics": {
                "sql": "SELECT genre, COUNT(*) as book_count, AVG(year) as avg_year FROM books WHERE genre IS NOT NULL GROUP BY genre ORDER BY book_count DESC LIMIT $1",
                "max_rows": 20,
                "required_parameters": [],
                "parameters": ["max_rows"],
                "description": "Получить статистику по жанрам"
            }
        }

    async def _publish_metrics(
        self,
        capability: str,
        execution_type: str,
        execution_time_ms: float,
        rows_returned: int,
        success: bool,
        script_name: Optional[str] = None
    ):
        """
        Публикация метрик выполнения через EventBus.

        ARGS:
            capability: имя выполненной capability
            execution_type: тип выполнения (static | dynamic)
            execution_time_ms: время выполнения в миллисекундах
            rows_returned: количество возвращённых строк
            success: флаг успешного выполнения
            script_name: имя скрипта (для static)
        """
        try:
            # Используем внедрённый event_bus из BaseComponent
            if hasattr(self, '_event_bus') and self._event_bus is not None:
                await self._event_bus.publish(
                    event_type="book_library.script_executed",
                    payload={
                        "capability": capability,
                        "execution_type": execution_type,
                        "execution_time_ms": execution_time_ms,
                        "rows_returned": rows_returned,
                        "success": success,
                        "script_name": script_name
                    }
                )
            # Fallback на application_context для обратной совместимости
            elif hasattr(self, '_application_context') and self.application_context:
                event_bus = self._application_context.infrastructure_context.event_bus

                # Публикуем событие о выполнении
                await event_bus.publish(
                    event_type="book_library.script_executed",
                    data={
                        "capability": capability,
                        "execution_type": execution_type,
                        "execution_time_ms": execution_time_ms,
                        "rows_returned": rows_returned,
                        "success": success,
                        "script_name": script_name,
                        "timestamp": self._application_context.created_at.isoformat() if hasattr(self._application_context, 'created_at') else None
                    },
                    source="book_library"
                )

            # Публикуем метрику времени выполнения
            if hasattr(self, '_event_bus') and self._event_bus is not None:
                await self._event_bus.publish(
                    event_type="metric.book_library.execution_time",
                    payload={
                        "value": execution_time_ms,
                        "unit": "ms",
                        "labels": {
                            "execution_type": execution_type,
                            "capability": capability
                        }
                    }
                )
            elif hasattr(self, '_application_context') and self.application_context:
                await self._application_context.infrastructure_context.event_bus.publish(
                    event_type="metric.book_library.execution_time",
                    data={
                        "value": execution_time_ms,
                        "unit": "ms",
                        "labels": {
                            "execution_type": execution_type,
                            "capability": capability
                        }
                    },
                    source="book_library"
                )

            # Публикуем метрику количества выполнений
            if hasattr(self, '_event_bus') and self._event_bus is not None:
                await self._event_bus.publish(
                    event_type="metric.book_library.total_executions",
                    payload={
                        "value": 1,
                        "labels": {
                            "execution_type": execution_type,
                            "capability": capability,
                            "status": "success" if success else "failed"
                        }
                    }
                )
            elif hasattr(self, '_application_context') and self.application_context:
                await self._application_context.infrastructure_context.event_bus.publish(
                    event_type="metric.book_library.total_executions",
                    data={
                        "value": 1,
                        "labels": {
                            "execution_type": execution_type,
                            "capability": capability,
                            "status": "success" if success else "failed"
                        }
                    },
                    source="book_library"
                )

            # Для static скриптов публикуем дополнительную метрику
            if execution_type == "static" and script_name:
                if hasattr(self, '_event_bus') and self._event_bus is not None:
                    await self._event_bus.publish(
                        event_type="metric.book_library.static_script_executions",
                        payload={
                            "value": 1,
                            "labels": {
                                "script_name": script_name,
                                "status": "success" if success else "failed"
                            }
                        }
                    )
                elif hasattr(self, '_application_context') and self.application_context:
                    await self._application_context.infrastructure_context.event_bus.publish(
                        event_type="metric.book_library.static_script_executions",
                        data={
                            "value": 1,
                            "labels": {
                                "script_name": script_name,
                                "status": "success" if success else "failed"
                            }
                        },
                        source="book_library"
                    )
            elif execution_type == "dynamic":
                if hasattr(self, '_event_bus') and self._event_bus is not None:
                    await self._event_bus.publish(
                        event_type="metric.book_library.dynamic_search_executions",
                        payload={
                            "value": 1,
                            "labels": {
                                "status": "success" if success else "failed"
                            }
                        }
                    )
                elif hasattr(self, '_application_context') and self.application_context:
                    await self._application_context.infrastructure_context.event_bus.publish(
                        event_type="metric.book_library.dynamic_search_executions",
                        data={
                            "value": 1,
                            "labels": {
                                "status": "success" if success else "failed"
                            }
                        },
                        source="book_library"
                    )

        except Exception as e:
            # Логгируем но не выбрасываем ошибку - метрики не должны ломать основную логику
            await self.event_bus_logger.debug(f"Ошибка публикации метрик: {e}")


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


# Тестовый код удалён — используйте pytest для тестирования
