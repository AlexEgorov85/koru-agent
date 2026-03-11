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
from core.models.data.execution import ExecutionResult, ExecutionStatus


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
            "book_library.list_scripts": self._list_scripts,
            "book_library.semantic_search": self._semantic_search  # новая capability для векторного поиска
        }

        # Кэш реестра скриптов
        self._scripts_registry = None

        # Проверка инициализации event_bus_logger
        if self.event_bus_logger is None:
            self._print_fallback = True
        else:
            self._print_fallback = False

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
                description="Выполнение заготовленного SQL-скрипта по имени. 10 скриптов: get_all_books, get_books_by_author (поиск по фамилии), get_books_by_genre, get_books_by_year_range, get_book_by_id, count_books_by_author, get_books_by_title_pattern, get_distinct_authors, get_distinct_genres, get_genre_statistics. Нормализованная схема: Lib.books JOIN Lib.authors. Быстро ~100мс.",
                skill_name=self.name,
                supported_strategies=["react", "planning"],
                visiable=True,
                meta={
                    "contract_version": "v1.0.0",
                    "prompt_version": "v1.1.0",
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
                    "contract_version": "v1.0.0",
                    "prompt_version": None,
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
                    "contract_version": "v1.0.0",
                    "prompt_version": "v1.0.0",
                    "requires_llm": False,
                    "execution_type": "vector"
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
    ) -> Any:
        """
        Реализация бизнес-логики навыка библиотеки (ASYNC).

        ВАЖНО: Валидация входа/выхода и метрики выполняются в BaseComponent.execute()
        Здесь только бизнес-логика.

        ВОЗВРАЩАЕТ:
        - Pydantic модель (выходной контракт) или Dict (fallback)
        """
        if capability.name not in self.supported_capabilities:
            raise ValueError(f"Навык не поддерживает capability: {capability.name}")

        # Конвертируем Pydantic модель в dict если нужно
        if hasattr(parameters, 'model_dump'):
            params_dict = parameters.model_dump()
        elif isinstance(parameters, dict):
            params_dict = parameters
        else:
            params_dict = {}

        # Выполняем действие — возвращает Pydantic модель или Dict
        result = await self.supported_capabilities[capability.name](params_dict)

        # Возвращаем результат напрямую (Pydantic модель или Dict)
        return result

    async def _search_books_dynamic(self, params: Dict[str, Any]) -> Any:
        """
        Динамическая генерация SQL через LLM.

        ПРЕИМУЩЕСТВА:
        - Гибкость для сложных запросов
        - Адаптация к формулировке пользователя

        НЕДОСТАТКИ:
        - Требует LLM вызов (медленнее)
        - Требует валидации сгенерированного SQL
        
        ВОЗВРАЩАЕТ:
        - Pydantic модель (выходной контракт) или Dict (fallback)
        """
        start_time = time.time()
        await self.event_bus_logger.info(f"Запуск динамического поиска книг: {params}")

        # 1. Валидация входных параметров
        # ✅ ПРИМЕЧАНИЕ: BaseComponent.execute() уже валидировал параметры через validate_input_typed()
        # params уже может быть Pydantic моделью BookLibrarySearchInput
        from pydantic import BaseModel
        if isinstance(params, BaseModel):
            # params уже валидированная Pydantic модель — используем атрибуты
            await self.event_bus_logger.debug(f"Получены типизированные параметры: {type(params).__name__}")
            query_val = getattr(params, 'query', '')
            max_results_val = getattr(params, 'max_results', 10)
        else:
            # Fallback для обратной совместимости (dict)
            input_schema = self.get_cached_input_contract_safe("book_library.search_books")
            if input_schema:
                try:
                    validated_params = input_schema.model_validate(params)
                    params = validated_params
                    query_val = getattr(params, 'query', '')
                    max_results_val = getattr(params, 'max_results', 10)
                except Exception as e:
                    await self.event_bus_logger.error(f"Ошибка валидации параметров: {e}")
                    raise ValueError(f"Неверные параметры: {str(e)}")
            else:
                await self.event_bus_logger.error("Контракт book_library.search_books.input не загружен в кэш")
                raise ValueError("Внутренняя ошибка: контракт не загружен")

        # 2. Получение промпта С КОНТРАКТАМИ для генерации SQL
        prompt_with_contract = self.get_prompt_with_contract("book_library.search_books")
        if not prompt_with_contract:
            raise ValueError("Промпт для поиска книг не найден")

        # 3. Генерация SQL через sql_generation
        sql_query = ""
        
        # Проверяем доступность LLM перед вызовом (чтобы избежать 30-секундного timeout)
        llm_available = False
        if hasattr(self.application_context, 'infrastructure_context'):
            llm_provider = self.application_context.infrastructure_context.get_provider("default_llm")
            llm_available = llm_provider is not None
        
        if not llm_available:
            # LLM недоступен — сразу используем fallback
            await self.event_bus_logger.warning("LLM недоступен, используем SQL fallback")
        else:
            try:
                exec_context = ExecutionContext()

                # Генерируем SQL запрос через сервис генерации
                gen_result = await self.executor.execute_action(
                    action_name="sql_generation.generate_query",
                    parameters={
                        "natural_language_request": query_val,
                        "table_schema": """
                            "Lib".books (
                                id INTEGER PRIMARY KEY,
                                title TEXT NOT NULL,
                                author_id INTEGER REFERENCES "Lib".authors(id),
                                isbn TEXT,
                                publication_date DATE,
                                genre TEXT
                            ),
                            "Lib".authors (
                                id INTEGER PRIMARY KEY,
                                first_name TEXT,
                                last_name TEXT,
                                birth_date DATE
                            )
                        """.strip(),
                        "prompt": prompt_with_contract  # Передаём промпт с контрактами
                    },
                    context=exec_context
                )

                from core.models.data.execution import ExecutionStatus
                if gen_result.status == ExecutionStatus.COMPLETED and gen_result.data:
                    # gen_result.data может быть dict или Pydantic моделью
                    if hasattr(gen_result.data, 'model_dump'):
                        data_dict = gen_result.data.model_dump()
                    else:
                        data_dict = gen_result.data
                    sql_query = data_dict.get('sql_query', '') if isinstance(data_dict, dict) else getattr(gen_result.data, 'sql_query', '')
                    await self.event_bus_logger.info(f"Сгенерированный SQL: {sql_query}")
                else:
                    await self.event_bus_logger.warning(f"Генерация SQL не удалась: {gen_result.error}")

            except Exception as e:
                await self.event_bus_logger.error(f"Ошибка генерации SQL: {e}")

        # Fallback: простой SQL запрос если генерация не удалась
        if not sql_query:
            # Нормализованная схема с JOIN между books и authors
            sql_query = f"""
                SELECT
                    b.id as book_id,
                    b.title as book_title,
                    b.isbn,
                    b.publication_date,
                    a.id as author_id,
                    a.first_name,
                    a.last_name,
                    a.birth_date
                FROM "Lib".books b
                JOIN "Lib".authors a ON b.author_id = a.id
                WHERE b.title ILIKE '%{query_val}%' OR a.last_name ILIKE '%{query_val}%' OR a.first_name ILIKE '%{query_val}%'
                LIMIT {max_results_val}
            """
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
                    "max_rows": max_results_val
                },
                context=exec_context
            )

            from core.models.data.execution import ExecutionStatus
            if query_result.status == ExecutionStatus.COMPLETED and query_result.data:
                rows = query_result.data.get('rows', [])
                execution_time = query_result.data.get('execution_time', 0.0)
                await self.event_bus_logger.info(f"Найдено строк: {len(rows)}")

        except Exception as e:
            await self.event_bus_logger.error(f"Ошибка выполнения SQL: {e}")
            raise RuntimeError(f"Ошибка выполнения SQL запроса: {e}")

        # ПРОВЕРКА: Если результаты пустые — это не ошибка, но нужно сообщить
        if not rows:
            await self.event_bus_logger.warning(
                f"⚠️ SQL запрос не вернул результатов. "
                f"Возможные причины: "
                f"1) В базе нет данных по запросу '{params.get('query', 'N/A')[:100]}', "
                f"2) Ошибка в сгенерированном SQL, "
                f"3) База данных пуста"
            )

        # Формируем результат
        total_time = time.time() - start_time

        result = {
            "rows": rows,
            "rowcount": len(rows),
            "execution_time": total_time,
            "execution_type": "dynamic",
            "sql_query": sql_query,
            "warning": "Результатов не найдено" if not rows else None
        }

        # 5. Публикация метрик через EventBus
        try:
            from core.infrastructure.event_bus.unified_event_bus import EventType
            await self._publish_metrics(
                event_type=EventType.ACTION_COMPLETED,
                capability_name="book_library.search_books",
                success=True,
                execution_time_ms=total_time * 1000,
                tokens_used=0,
                execution_type="dynamic",
                rows_returned=len(rows),
                script_name=None
            )
        except Exception as e:
            await self.event_bus_logger.debug(f"Ошибка публикации метрик: {e}")

        # ✅ Возвращаем Pydantic модель напрямую
        output_schema = self.get_cached_output_contract_safe("book_library.search_books")
        if output_schema:
            validated_result = output_schema.model_validate(result)
            return validated_result  # ← Pydantic модель
        else:
            # Fallback: возвращаем dict если схема не загружена
            return result

    async def _execute_script_static(self, params: Dict[str, Any]) -> Any:
        """
        Выполнение заготовленного SQL-скрипта по имени.

        ПРЕИМУЩЕСТВА:
        - Быстрое выполнение (нет LLM вызова)
        - Безопасность (скрипт проверен заранее)
        - Предсказуемость результата

        НЕДОСТАТКИ:
        - Ограничено заранее определёнными запросами

        ВОЗВРАЩАЕТ:
        - Pydantic модель (выходной контракт) или Dict (fallback)
        """
        start_time = time.time()
        
        # [BOOK_DEBUG] 1.1. Входные параметры
        await self.event_bus_logger.info(f"[BOOK_DEBUG] _execute_script_static: входные params = {params}")
        
        await self.event_bus_logger.info(f"Запуск статического скрипта: {params}")

        # 1. Валидация входных параметров
        # Поддержка dict и Pydantic модели
        script_name = params.get('script_name') if isinstance(params, dict) else getattr(params, 'script_name', None)
        
        # [BOOK_DEBUG] 1.2. Проверка наличия script_name
        await self.event_bus_logger.info(f"[BOOK_DEBUG] script_name = {script_name}")
        
        if not script_name:
            raise ValueError("Требуется параметр 'script_name'")

        # 2. Проверка, что скрипт существует в реестре
        allowed_scripts = self._get_allowed_scripts()
        if script_name not in allowed_scripts:
            available_scripts = list(allowed_scripts.keys())
            raise ValueError(f"Скрипт '{script_name}' не найден. Доступные: {available_scripts}")

        # 3. Получение SQL-скрипта из реестра
        script_config = allowed_scripts[script_name]
        
        # [BOOK_DEBUG] 1.3. Получение конфигурации скрипта
        await self.event_bus_logger.info(f"[BOOK_DEBUG] script_config для '{script_name}': {script_config}")
        
        sql_query = script_config['sql']
        max_rows = params.get('max_rows', script_config.get('max_rows', 100)) if isinstance(params, dict) else getattr(params, 'max_rows', script_config.get('max_rows', 100))

        # 4. Валидация параметров для скрипта
        # [BOOK_DEBUG] 1.4. Извлечение script_params
        # Поддержка как вложенной (parameters: {}), так и плоской структуры
        script_params = params.get('parameters', {}) if isinstance(params, dict) else getattr(params, 'parameters', {})
        await self.event_bus_logger.info(f"[BOOK_DEBUG] script_params (из parameters) = {script_params}")

        # Если script_params пуст, возможно, параметры переданы на верхнем уровне (плоская структура)
        if not script_params:
            flat_params = {k: v for k, v in params.items() if k not in ['script_name', 'max_rows']}
            await self.event_bus_logger.info(f"[BOOK_DEBUG] попытка использовать плоские параметры: {flat_params}")
            script_params = flat_params
        
        # Также добавляем max_rows из верхнего уровня если есть
        if isinstance(params, dict) and 'max_rows' in params:
            script_params['max_rows'] = params['max_rows']
        elif hasattr(params, 'max_rows'):
            script_params['max_rows'] = getattr(params, 'max_rows')
            
        if script_config.get('required_parameters'):
            missing_params = set(script_config['required_parameters']) - set(script_params.keys())
            if missing_params:
                raise ValueError(f"Отсутствуют обязательные параметры: {missing_params}")

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
                param_value = script_params[param_name]
                # Для параметров ILIKE (author, title_pattern) добавляем % если нет wildcard
                if param_name in ['author', 'title_pattern']:
                    if '%' not in param_value:
                        param_value = f'%{param_value}%'
                sql_params[str(param_index)] = param_value
                param_index += 1

        # Добавляем max_rows как последний параметр если он есть в SQL
        if '$' + str(param_index) in sql_query or 'LIMIT $' + str(param_index) in sql_query:
            sql_params[str(param_index)] = max_rows

        # [BOOK_DEBUG] 1.5. Формирование sql_params
        await self.event_bus_logger.info(f"[BOOK_DEBUG] сформированные sql_params (для БД): {sql_params}")

        # 6. Выполнение SQL через sql_query_service ЧЕРЕЗ EXECUTOR
        rows = []
        execution_time = 0.0
        try:
            exec_context = ExecutionContext()

            query_result = await self.executor.execute_action(
                action_name="sql_query_service.execute",
                parameters={
                    "sql_query": sql_query,
                    "parameters": sql_params
                },
                context=exec_context
            )

            from core.models.data.execution import ExecutionStatus
            if query_result.status == ExecutionStatus.COMPLETED and query_result.data:
                result_data = query_result.data
                rows = result_data.rows if hasattr(result_data, 'rows') else result_data.get('rows', [])
                execution_time = result_data.execution_time if hasattr(result_data, 'execution_time') else result_data.get('execution_time', 0.0)
                await self.event_bus_logger.info(f"[BOOK_DEBUG] Успешное выполнение, rows={len(rows)}")
            else:
                error_msg = query_result.error or "Неизвестная ошибка"
                await self.event_bus_logger.error(f"[BOOK_DEBUG] Ошибка выполнения SQL: {error_msg}")
                raise RuntimeError(f"Ошибка выполнения SQL: {error_msg}")

        except Exception as e:
            await self.event_bus_logger.error(f"Ошибка выполнения скрипта '{script_name}': {e}")
            raise  # Пробрасываем исключение вверх, execute() обработает

        # Формируем результат
        total_time = time.time() - start_time

        result_data = {
            "rows": rows,
            "rowcount": len(rows),
            "execution_time": total_time,
            "execution_type": "static",
            "script_name": script_name
        }

        # 7. Публикация метрик через EventBus
        try:
            from core.infrastructure.event_bus.unified_event_bus import EventType
            await self._publish_metrics(
                event_type=EventType.ACTION_COMPLETED,
                capability_name="book_library.execute_script",
                success=True,
                execution_time_ms=total_time * 1000,
                tokens_used=0,
                execution_type="static",
                rows_returned=len(rows),
                script_name=script_name
            )
        except Exception as e:
            await self.event_bus_logger.debug(f"Ошибка публикации метрик: {e}")

        # ✅ Возвращаем Pydantic модель напрямую
        output_schema = self.get_cached_output_contract_safe("book_library.execute_script")
        if output_schema:
            validated_result = output_schema.model_validate(result_data)
            return validated_result  # ← Pydantic модель
        else:
            # Fallback: возвращаем dict если схема не загружена
            return result_data

    async def _list_scripts(self, params: Dict[str, Any] = None) -> Dict[str, Any]:
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

        # Возвращаем ExecutionResult (no side effect - только чтение)
        return ExecutionResult.success(
            data=result_data,  # ← Pydantic модель!
            metadata={"scripts_count": len(scripts_list)},
            side_effect=False
        )

    async def _semantic_search(self, params: Dict[str, Any]) -> Any:
        """
        Семантический поиск через векторную БД.

        ПРЕИМУЩЕСТВА:
        - Быстрый поиск по смыслу (не ключевым словам)
        - Находит релевантные фрагменты текста книг
        - Не требует LLM вызова (~100-500мс)

        НЕДОСТАТКИ:
        - Требует предварительно созданный FAISS индекс
        - Возвращает чанки текста, а не метаданные книг

        ВОЗВРАЩАЕТ:
        - Pydantic модель (выходной контракт) или Dict (fallback)
        """
        import time
        from core.models.data.execution import ExecutionStatus
        from core.models.data.capability import Capability

        start_time = time.time()
        await self.event_bus_logger.info(f"Запуск семантического поиска книг: {params}")

        # 1. Валидация входных параметров
        query = params.get('query') if isinstance(params, dict) else getattr(params, 'query', None)
        top_k = params.get('top_k', 10) if isinstance(params, dict) else getattr(params, 'top_k', 10)
        min_score = params.get('min_score', 0.5) if isinstance(params, dict) else getattr(params, 'min_score', 0.5)

        if not query:
            raise ValueError("Параметр 'query' обязателен для семантического поиска")

        # 2. Проверка доступности векторного поиска
        infra = self.application_context.infrastructure_context
        if not infra.is_vector_search_ready('books'):
            await self.event_bus_logger.warning("Vector Search для книг не готов, используем SQL fallback")
            # Используем SQL fallback напрямую
            return await self._semantic_search_sql_fallback(query, top_k, start_time)

        # 3. Получение инструмента vector_books_tool через компоненты
        from core.models.enums.common_enums import ComponentType

        vector_tool = self.application_context.components.get(
            ComponentType.TOOL,
            "vector_books_tool"
        )
        if not vector_tool:
            await self.event_bus_logger.error("Инструмент vector_books_tool не зарегистрирован, используем SQL fallback")
            return await self._semantic_search_sql_fallback(query, top_k, start_time)

        # 4. Создание контекста выполнения
        exec_context = ExecutionContext(
            session_context=self.application_context.session_context,
            user_context=None
        )

        # 5. Выполнение capability "search" инструмента vector_books
        try:
            result = await vector_tool.execute(
                capability=Capability(
                    name="vector_books.search",
                    description="Семантический поиск по книгам",
                    skill_name="vector_books_tool"
                ),
                parameters={
                    "query": query,
                    "top_k": top_k,
                    "min_score": min_score
                },
                execution_context=exec_context
            )
        except Exception as e:
            await self.event_bus_logger.error(f"Ошибка выполнения vector_books.search: {e}, используем SQL fallback")
            return await self._semantic_search_sql_fallback(query, top_k, start_time)

        # 6. Обработка результата
        if result.status != ExecutionStatus.COMPLETED:
            await self.event_bus_logger.warning(f"Векторный поиск не завершён: {result.error}, используем SQL fallback")
            return await self._semantic_search_sql_fallback(query, top_k, start_time)

        # Извлекаем данные из результата
        search_data = result.data if hasattr(result, 'data') else result
        if hasattr(search_data, 'model_dump'):
            search_data = search_data.model_dump()

        # 7. Формируем результат с добавлением execution_type
        total_time = time.time() - start_time
        search_type = search_data.get("search_type", "vector")
        result_data = {
            "results": search_data.get("results", []),
            "total_found": search_data.get("total_found", 0),
            "execution_type": "vector",
            "search_type": search_type  # vector | sql | none
        }

        await self.event_bus_logger.info(
            f"Семантический поиск завершён: найдено {result_data['total_found']} результатов "
            f"за {total_time*1000:.2f}мс (тип: {search_type})"
        )

        # 8. Публикация метрик через EventBus
        try:
            from core.infrastructure.event_bus.unified_event_bus import EventType
            await self._publish_metrics(
                event_type=EventType.ACTION_COMPLETED,
                capability_name="book_library.semantic_search",
                success=True,
                execution_time_ms=total_time * 1000,
                tokens_used=0,
                execution_type="vector",
                rows_returned=result_data["total_found"],
                script_name=None
            )
        except Exception as e:
            await self.event_bus_logger.debug(f"Ошибка публикации метрик: {e}")

        # 9. Валидация через выходной контракт
        output_schema = self.get_cached_output_contract_safe("book_library.semantic_search")
        if output_schema:
            try:
                validated_result = output_schema.model_validate(result_data)
                return validated_result  # ← Pydantic модель
            except Exception as e:
                await self.event_bus_logger.error(f"Ошибка валидации через контракт: {e}")

        # Fallback: возвращаем dict если схема не загружена
        return result_data

    async def _semantic_search_sql_fallback(self, query: str, top_k: int, start_time: float) -> Any:
        """
        SQL fallback для семантического поиска.
        Используется когда векторный индекс недоступен.
        """
        await self.event_bus_logger.info(f"Выполнение SQL fallback для семантического поиска: {query}")
        
        # Используем executor для SQL запроса
        exec_context = ExecutionContext()
        
        safe_query = query.replace("'", "''")
        sql = f"""
            SELECT 
                b.id as book_id,
                b.title as book_title,
                b.isbn,
                b.publication_date,
                a.first_name,
                a.last_name,
                0.5 as score
            FROM "Lib".books b
            JOIN "Lib".authors a ON b.author_id = a.id
            WHERE b.title ILIKE '%{safe_query}%' 
               OR a.last_name ILIKE '%{safe_query}%' 
               OR a.first_name ILIKE '%{safe_query}%'
            ORDER BY score DESC
            LIMIT {top_k}
        """
        
        try:
            query_result = await self.executor.execute_action(
                action_name="sql_query.execute",
                parameters={
                    "sql": sql,
                    "parameters": {},
                    "max_rows": top_k
                },
                context=exec_context
            )
            
            rows = []
            if query_result.status == ExecutionStatus.COMPLETED and query_result.data:
                rows = query_result.data.get('rows', [])
            
            # Преобразуем результаты в формат семантического поиска
            results = []
            for row in rows:
                results.append({
                    "book_id": row.get("book_id"),
                    "document_id": f"book_{row.get('book_id')}",
                    "chapter": None,
                    "chunk_id": None,
                    "score": 0.5,
                    "content": f"{row.get('book_title')} by {row.get('last_name')} {row.get('first_name')}",
                    "metadata": {
                        "title": row.get("book_title"),
                        "author": f"{row.get('last_name')} {row.get('first_name')}",
                        "isbn": row.get("isbn"),
                        "publication_date": row.get("publication_date")
                    }
                })
            
            total_time = time.time() - start_time
            result_data = {
                "results": results,
                "total_found": len(results),
                "execution_type": "vector",
                "search_type": "sql"
            }
            
            await self.event_bus_logger.info(
                f"SQL fallback завершён: найдено {len(results)} результатов "
                f"за {total_time*1000:.2f}мс"
            )
            
            # Валидация через выходной контракт
            output_schema = self.get_cached_output_contract_safe("book_library.semantic_search")
            if output_schema:
                try:
                    validated_result = output_schema.model_validate(result_data)
                    return validated_result
                except Exception as e:
                    await self.event_bus_logger.error(f"Ошибка валидации через контракт: {e}")
            
            return result_data
            
        except Exception as e:
            await self.event_bus_logger.error(f"SQL fallback failed: {e}")
            total_time = time.time() - start_time
            return {
                "results": [],
                "total_found": 0,
                "execution_type": "vector",
                "search_type": "none",
                "error": str(e)
            }

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
        event_type,  # EventType для совместимости с BaseComponent
        capability_name: str,  # имя capability
        success: bool,  # флаг успеха
        execution_time_ms: float,  # время выполнения
        tokens_used: int = 0,  # количество токенов (для совместимости)
        error: Optional[str] = None,  # сообщение об ошибке
        error_type: Optional[str] = None,  # тип ошибки
        error_category: Optional[str] = None,  # категория ошибки
        # Специфичные параметры book_library
        execution_type: Optional[str] = None,  # static | dynamic
        rows_returned: int = 0,  # количество строк
        script_name: Optional[str] = None,  # имя скрипта
        result: Optional[dict] = None  # результат выполнения
    ):
        """
        Публикация метрик выполнения через EventBus.
        """
        try:
            # Используем event_bus_logger для публикации событий
            if self.event_bus_logger:
                # Публикуем событие о выполнении
                await self.event_bus_logger.info(
                    f"Метрика: {capability_name} | execution_type={execution_type} | "
                    f"execution_time={execution_time_ms:.2f}ms | rows={rows_returned} | "
                    f"success={success} | script={script_name}"
                )
                
                # Для static скриптов публикуем дополнительную метрику
                if execution_type == "static" and script_name:
                    await self.event_bus_logger.info(
                        f"Static скрипт выполнен: {script_name} | status={'success' if success else 'failed'}"
                    )
                elif execution_type == "dynamic":
                    await self.event_bus_logger.info(
                        f"Dynamic поиск выполнен | status={'success' if success else 'failed'}"
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
