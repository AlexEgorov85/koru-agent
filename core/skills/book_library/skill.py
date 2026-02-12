"""Навык работы с библиотекой книг с использованием новой архитектуры и кэшированием структуры таблиц.

ОСНОВНЫЕ ИЗМЕНЕНИЯ:
1. Использование SQLQueryService для безопасного выполнения SQL-запросов
2. Кэширование структуры таблиц для многократного использования
3. Интеграция с новыми сервисами (SQLQueryService, SQLValidatorService)
4. Соответствие современной архитектуре проекта
"""
import logging
from typing import Dict, Any, List, Optional
from core.infrastructure.services.sql_generation.schema import SQLGenerationInput
from core.session_context.base_session_context import BaseSessionContext
from core.skills.base_skill import BaseSkill
from models.capability import Capability
from models.execution import ExecutionResult, ExecutionStatus

logger = logging.getLogger(__name__)


class BookLibrarySkill(BaseSkill):
    """Навык для работы с библиотекой книг через новую архитектуру."""
    name = "book_library"
    supported_strategies = ["react", "planning", "evaluation"]  # ← Доступен для всех стратегий

    def __init__(self, name: str, system_context: Any, cache_table_structure: bool = True, **kwargs):
        super().__init__(name, system_context, **kwargs)
        self.cache_table_structure = cache_table_structure
        self._table_structure_cache: Optional[Dict[str, Any]] = None
        
        # Получаем необходимые сервисы
        self.sql_query_service = system_context.get_resource("sql_query_service")
        self.table_description_service = system_context.get_resource("table_description_service")
        

    async def initialize(self) -> bool:
        """Инициализация навыка - загрузка структуры таблиц если включено кэширование."""
        try:
            if self.cache_table_structure:
                await self._load_table_structure()
            return True
        except Exception as e:
            logger.error(f"Ошибка инициализации BookLibrarySkill: {str(e)}")
            return False

    async def _load_table_structure(self):
        """Загрузка структуры таблиц в кэш."""
        if not self.table_description_service:
            logger.warning("table_description_service недоступен, пропускаем загрузку структуры таблиц")
            return

        try:
            # Загружаем структуру таблиц
            structure = await self.table_description_service.get_tables_structure(["books", "authors", "chapters"])
            self._table_structure_cache = structure
        except Exception as e:
            logger.error(f"Ошибка загрузки структуры таблиц: {str(e)}")
            # Не вызываем исключение, так как это не критично для работы навыка

    def get_table_structure(self) -> Optional[Dict[str, Any]]:
        """Получение закэшированной структуры таблиц."""
        return self._table_structure_cache

    def get_capabilities(self) -> List[Capability]:
        """Возвращает список поддерживаемых capability для работы с библиотекой."""
        return [
            Capability(
                name="book_library.get_books_by_author",
                description="Получение информации о книгах по автору",
                skill_name=self.name,
                supported_strategies=self.supported_strategies,
                visiable=True
            ),
            Capability(
                name="book_library.get_full_text",
                description="Получение полного текста книги",
                skill_name=self.name,
                supported_strategies=self.supported_strategies,
                visiable=True
            ),
            Capability(
                name="book_library.dynamic_sql_query",
                description="Генерация и выполнение SQL запроса для сложных вопросов",
                skill_name=self.name,
                supported_strategies=self.supported_strategies,
                visiable=True
            )
        ]

    async def execute(self, capability: Capability, parameters: Dict[str, Any], context: BaseSessionContext) -> ExecutionResult:
        """Выполнение capability навыка библиотеки книг."""
        step_number = getattr(context, 'current_step', 0) + 1
        logger.debug(f"Выполнение capability '{capability.name}' на шаге {step_number}")

        # Валидация параметров через кэшированный контракт
        validation_result = await self.contract_service.validate(
            capability_name=capability.name,
            data=parameters,
            direction="input"
        )

        if not validation_result["is_valid"]:
            error_msg = f"Ошибка валидации параметров: {validation_result['errors']}"
            logger.error(error_msg)
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                result=None,
                observation_item_id=None,
                summary=error_msg,
                error="INVALID_PARAMETERS"
            )

        validated_params = validation_result["validated_data"]

        try:
            if capability.name == "book_library.get_books_by_author":
                # В новой архитектуре мы используем кэшированные контракты и принимаем параметры как словарь
                return await self._get_books_by_author(validated_params, context, step_number)

            elif capability.name == "book_library.get_full_text":
                # В новой архитектуре мы используем кэшированные контракты и принимаем параметры как словарь
                return await self._get_full_text(validated_params, context, step_number)

            elif capability.name == "book_library.dynamic_sql_query":
                # В новой архитектуре мы используем кэшированные контракты и принимаем параметры как словарь
                return await self._dynamic_sql_query(validated_params, context, step_number)
            else:
                error_msg = f"Неподдерживаемая capability: {capability.name}"
                logger.error(error_msg)
                return self._build_error_result(
                    context=context,
                    error_message=error_msg,
                    error_type="UNSUPPORTED_CAPABILITY",
                    step_number=step_number
                )
        except Exception as e:
            logger.error(f"Неожиданная ошибка при выполнении capability {capability.name}: {str(e)}", exc_info=True)
            return self._build_error_result(
                context=context,
                error_message=f"Внутренняя ошибка при выполнении: {str(e)}",
                error_type="INTERNAL_ERROR",
                step_number=step_number
            )

    async def _get_books_by_author(self, input_data: Any, context: BaseSessionContext, step_number: int) -> ExecutionResult:
        """Получение книг по автору с использованием SQLQueryservices."""
        try:
            # 1. Построение SQL запроса
            where_clauses = []
            params = {}

            # Проверяем, является ли input_data Pydantic моделью или словарем
            if hasattr(input_data, '__dict__') or isinstance(input_data, dict):
                # Это может быть Pydantic модель или словарь
                if hasattr(input_data, 'author_id'):
                    author_id = input_data.author_id
                    name_author = getattr(input_data, 'name_author', None)
                    family_author = getattr(input_data, 'family_author', None)
                else:
                    # Это словарь
                    author_id = input_data.get('author_id')
                    name_author = input_data.get('name_author')
                    family_author = input_data.get('family_author')
            else:
                raise ValueError("input_data должен быть Pydantic моделью или словарем")

            if author_id:
                where_clauses.append("a.id = $author_id")
                params["author_id"] = author_id
            elif name_author or family_author:
                if name_author:
                    where_clauses.append("a.first_name ILIKE $name_author")
                    params["name_author"] = f"%{name_author}%"
                if family_author:
                    where_clauses.append("a.last_name ILIKE $family_author")
                    params["family_author"] = f"%{family_author}%"
            else:
                raise ValueError("Необходимо указать author_id, name_author или family_author")

            where_clause = " AND ".join(where_clauses)
            sql = f"""
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
            WHERE {where_clause}
            LIMIT 50;
            """

            # 2. Выполнение SQL запроса через SQLQueryService
            logger.debug(f"Выполнение SQL запроса через SQLQueryService: {sql[:100]}...")

            if not self.sql_query_service:
                raise RuntimeError("SQLQueryService недоступен")

            sql_result = await self.sql_query_service.execute_direct_query(
                sql_query=sql,
                parameters=params,
                max_rows=50
            )

            # 3. Проверка результата и формирование ответа
            if not sql_result.success:
                raise RuntimeError(f"Ошибка выполнения SQL запроса: {sql_result.error}")

            books = sql_result.rows or []
            book_count = len(books)

            formatted_result = {
                "author": {
                    "first_name": name_author,
                    "last_name": family_author,
                    "author_id": author_id,
                },
                "books": books,
                "total_books": book_count,
                "query_type": "author_search"
            }

            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                observation_item_id=None,
                result=formatted_result,
                summary=f"Найдено {book_count} книг",
                error=None
            )

        except Exception as e:
            logger.error(f"Ошибка получения книг по автору: {str(e)}")
            return self._build_error_result(
                context=context,
                error_message=str(e),
                error_type="AUTHOR_SEARCH_ERROR",
                step_number=step_number
            )

    async def _get_full_text(self, input_data: Any, context: BaseSessionContext, step_number: int) -> ExecutionResult:
        """Получение полного текста книги с использованием SQLQueryservices."""
        try:
            # 1. Получение метаданных книги
            # Проверяем, является ли input_data Pydantic моделью или словарем
            if hasattr(input_data, '__dict__') or isinstance(input_data, dict):
                # Это может быть Pydantic модель или словарь
                if hasattr(input_data, 'book_id'):
                    book_id = input_data.book_id
                else:
                    # Это словарь
                    book_id = input_data.get('book_id')
            else:
                raise ValueError("input_data должен быть Pydantic моделью или словарем")
            
            if not book_id:
                raise ValueError("Необходимо указать book_id для получения полного текста книги")
            
            metadata_sql = """
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
            WHERE b.id = $book_id
            LIMIT 1;
            """

            if not self.sql_query_service:
                raise RuntimeError("SQLQueryService недоступен")

            metadata_result = await self.sql_query_service.execute_direct_query(
                sql_query=metadata_sql,
                parameters={"book_id": book_id},
                max_rows=1
            )

            if not metadata_result.success or not metadata_result.rows:
                raise ValueError(f"Книга с ID {book_id} не найдена")

            metadata = metadata_result.rows[0]

            # 2. Получение глав книги
            chapters_sql = """
            SELECT
                c.chapter_number,
                c.title as chapter_title,
                c.content
            FROM "Lib".chapters c
            WHERE c.book_id = $book_id
            ORDER BY c.chapter_number;
            """

            chapters_result = await self.sql_query_service.execute_direct_query(
                sql_query=chapters_sql,
                parameters={"book_id": book_id},
                max_rows=100
            )

            if not chapters_result.success:
                raise RuntimeError(f"Ошибка получения глав книги: {chapters_result.error}")

            chapters = chapters_result.rows or []

            # 3. Формирование полного текста
            full_text = {
                "metadata": metadata,
                "chapters": chapters,
                "full_content": " ".join([chapter.get("content", "") for chapter in chapters]),
                "total_chapters": len(chapters)
            }

            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                observation_item_id=None,
                result=full_text,
                summary=f"Получен полный текст книги '{metadata.get('title', 'Без названия')}'",
                error=None
            )

        except Exception as e:
            logger.error(f"Ошибка получения полного текста книги: {str(e)}")
            return self._build_error_result(
                context=context,
                error_message=str(e),
                error_type="FULL_TEXT_ERROR",
                step_number=step_number
            )

    async def _dynamic_sql_query(self, input_data: Any, context: BaseSessionContext, step_number: int) -> ExecutionResult:
        """Генерация и выполнение SQL запроса с использованием SQLGenerationservices."""
        try:
            # 1. Валидация параметров
            # Проверяем, является ли input_data Pydantic моделью или словарем
            if hasattr(input_data, '__dict__') or isinstance(input_data, dict):
                # Это может быть Pydantic модель или словарь
                if hasattr(input_data, 'user_question'):
                    user_question = input_data.user_question
                    context_tables = getattr(input_data, 'context_tables', ["authors", "books", "chapters", "genres"])
                    max_rows = getattr(input_data, 'max_rows', 50)
                else:
                    # Это словарь
                    user_question = input_data.get('user_question')
                    context_tables = input_data.get('context_tables', ["authors", "books", "chapters", "genres"])
                    max_rows = input_data.get('max_rows', 50)
            else:
                raise ValueError("input_data должен быть Pydantic моделью или словарем")
            
            if not user_question:
                raise ValueError("Необходимо указать user_question для динамического SQL запроса")
            
            logger.debug(f"Валидация параметров успешна: user_question={user_question}, max_rows={max_rows}")

            # 2. Получение SQLGenerationService
            sql_service = await self.system_context.get_service("sql_generation_service")
            if not sql_service:
                raise RuntimeError("SQLGenerationService не зарегистрирован в системном контексте")

            # 3. Подготовка входных данных для сервиса генерации
            generation_input = SQLGenerationInput(
                user_question=user_question,
                tables=context_tables,
                max_rows=max_rows,
                context=f"Цель: анализ библиотечных данных. Максимум {max_rows} строк."
            )

            # 4. Автоматическая генерация + выполнение + коррекция через новый сервис
            result = await sql_service.execute_with_auto_correction(
                generation_input,
                context=context
            )

            if result.success:
                formatted_result = {
                    "sql": result.metadata.get("original_query", "Unknown query") if result.metadata else "Unknown query",
                    "rows": result.rows or [],
                    "columns": result.columns or [],
                    "rowcount": result.rowcount,
                    "execution_time": result.metadata.get("execution_time") if result.metadata else None,
                    "query_type": "dynamic_query"
                }

                return ExecutionResult(
                    status=ExecutionStatus.SUCCESS,
                    observation_item_id=None,
                    result=formatted_result,
                    summary=f"Выполнен динамический SQL-запрос, получено {result.rowcount} строк",
                    error=None
                )
            else:
                raise RuntimeError(f"Ошибка выполнения SQL запроса: {result.error}")

        except Exception as e:
            logger.error(f"Ошибка динамического SQL запроса: {str(e)}")
            return self._build_error_result(
                context=context,
                error_message=str(e),
                error_type="DYNAMIC_SQL_ERROR",
                step_number=step_number
            )

    async def initialize(self) -> bool:
        """Инициализация навыка - загрузка структуры таблиц если включено кэширование."""
        try:
            if self.cache_table_structure:
                await self._load_table_structure()
            return True
        except Exception as e:
            logger.error(f"Ошибка инициализации BookLibrarySkill: {str(e)}")
            return False

    async def shutdown(self):
        """Очистка ресурсов навыка."""
        # Очистка кэша структуры таблиц
        self._table_structure_cache = None
        logger.info("BookLibrarySkill остановлен")

    def _build_error_result(self, context: BaseSessionContext, error_message: str, error_type: str, step_number: int) -> ExecutionResult:
        """Построение результата ошибки."""
        logger.error(f"Ошибка на шаге {step_number}: {error_type} - {error_message}")
        return ExecutionResult(
            status=ExecutionStatus.FAILED,
            observation_item_id=None,
            result=None,
            summary=f"Ошибка: {error_message}",
            error=error_type
        )