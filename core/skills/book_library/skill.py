"""Навык работы с библиотекой книг с правильной валидацией параметров.

ОСНОВНЫЕ ИЗМЕНЕНИЯ:
1. Простая валидация параметров через Pydantic
2. Сохранение SQL скриптов для выполнения
3. Использование system_context.execute_sql_query
4. Удаление избыточных схем и сложных механизмов
5. Соответствие архитектуре проекта

АРХИТЕКТУРНЫЕ ПРИНЦИПЫ:
- Skills отвечают за бизнес-логику
- Все SQL запросы выполняются через system_context
- Простая валидация параметров без избыточности
- Сохранение рабочих SQL скриптов из предыдущего варианта
"""
import logging
from typing import Dict, Any, List

from core.session_context.base_session_context import BaseSessionContext
from core.skills.base_skill import BaseSkill
from core.skills.book_library.schema import AuthorSearchInput, DynamicSQLInput, FullTextInput
from models.capability import Capability
from models.execution import ExecutionResult, ExecutionStatus

logger = logging.getLogger(__name__)


class BookLibrarySkill(BaseSkill):
    """Навык для работы с библиотекой книг через архитектуру портов и адаптеров."""
    name = "book_library"
    
    def __init__(self, name: str, system_context: Any, **kwargs):
        super().__init__(name, system_context, **kwargs)
        logger.info(f"Инициализирован навык работы с библиотекой книг: {self.name}")
    
    def get_capabilities(self) -> List[Capability]:
        """Возвращает список поддерживаемых capability для работы с библиотекой."""
        return [
            Capability(
                name="book_library.get_books_by_author",
                description="Получение информации о книгах по автору",
                parameters_schema=AuthorSearchInput.model_json_schema(),
                parameters_class=AuthorSearchInput,
                skill_name=self.name
            ),
            Capability(
                name="book_library.get_full_text",
                description="Получение полного текста книги",
                parameters_schema=FullTextInput.model_json_schema(),
                parameters_class=FullTextInput,
                skill_name=self.name
            ),
            Capability(
                name="book_library.dynamic_sql_query",
                description="Генерация и выполнение SQL запроса для сложных вопросов",
                parameters_schema=DynamicSQLInput.model_json_schema(),
                parameters_class=DynamicSQLInput,
                skill_name=self.name
            )
        ]
    
    async def execute(self, capability: Capability, parameters: Dict[str, Any], context: BaseSessionContext) -> ExecutionResult:
        """Выполнение capability навыка библиотеки книг."""
        step_number = getattr(context, 'current_step', 0) + 1
        logger.debug(f"Выполнение capability '{capability.name}' на шаге {step_number}")
        
        try:
            if capability.name == "book_library.get_books_by_author":
                # Конвертация если parameters - словарь
                if isinstance(parameters, dict):
                    params_obj = AuthorSearchInput(**parameters)
                else:
                    params_obj = parameters
                
                return await self._get_books_by_author(params_obj, context, step_number)
            
            elif capability.name == "book_library.get_full_text":
                # Конвертация если parameters - словарь
                if isinstance(parameters, dict):
                    params_obj = FullTextInput(**parameters)
                else:
                    params_obj = parameters
                
                return await self._get_full_text(params_obj, context, step_number)

            elif capability.name == "book_library.dynamic_sql_query":
                # Конвертация если parameters - словарь
                if isinstance(parameters, dict):
                    params_obj = DynamicSQLInput(**parameters)
                else:
                    params_obj = parameters
                
                return await self._dynamic_sql_query(params_obj, context, step_number)
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
            logger.exception(f"Ошибка выполнения capability {capability.name}: {str(e)}")
            return self._build_error_result(
                context=context,
                error_message=str(e),
                error_type="EXECUTION_ERROR",
                step_number=step_number
            )
    
    async def _get_books_by_author(self, input_data: AuthorSearchInput, context: BaseSessionContext, step_number: int) -> ExecutionResult:
        """Получение информации о книгах по автору с правильной валидацией параметров."""
        try:
            # 1. Построение SQL запроса в зависимости от параметров
            if input_data.author_id:
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
                WHERE a.id = {input_data.author_id}
                LIMIT 50;
                """
                summary = f"Поиск книг по ID автора {input_data.author_id}"
            elif input_data.family_author or input_data.name_author:
                where_clauses = []
                if input_data.name_author:
                    where_clauses.append(f"a.first_name ILIKE '%{input_data.name_author}%'")
                if input_data.family_author:
                    where_clauses.append(f"a.last_name ILIKE '%{input_data.family_author}%'")
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
                author_name = f"{input_data.name_author or ''} {input_data.family_author or ''}".strip()
                summary = f"Поиск книг по автору '{author_name}'"
            else:
                raise ValueError("Необходимо указать author_id, name_author, family_author")
            
            # 3. Выполнение SQL запроса через system_context
            logger.debug(f"Выполнение SQL запроса: {sql[:100]}...")
            sql_result = await self.system_context.execute_sql_query(query=sql)
            
            # 4. Проверка результата и формирование ответа
            if not sql_result.success:
                raise RuntimeError(f"Ошибка выполнения SQL запроса: {sql_result.error}")
            
            books = sql_result.rows or []
            book_count = len(books)
            
            formatted_result = {
                "author": {
                    "first_name": input_data.name_author,
                    "last_name": input_data.family_author,
                    "author_id": input_data.author_id,
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
    
    async def _get_full_text(self, input_data: FullTextInput, context: BaseSessionContext, step_number: int) -> ExecutionResult:
        """Получение полного текста книги с правильной валидацией параметров."""
        try:
            # 1. Определение ID книги
            book_id = input_data.book_id
            if not book_id and input_data.book_title:
                # Поиск ID по названию
                search_sql = f"""
                SELECT id 
                FROM "Lib".books 
                WHERE title ILIKE '%{input_data.book_title}%'
                LIMIT 1;
                """
                search_result = await self.system_context.execute_sql_query(query=search_sql)
                if not search_result.success:
                    raise RuntimeError(f"Ошибка поиска книги: {search_result.error}")
                if search_result.rows and len(search_result.rows) > 0:
                    book_id = search_result.rows[0].get("id")
                else:
                    raise ValueError(f"Книга с названием '{input_data.book_title}' не найдена")
            
            if not book_id and input_data.query:
                # Поиск по текстовому запросу
                search_sql = f"""
                SELECT id, title 
                FROM "Lib".books 
                WHERE title ILIKE '%{input_data.query}%'
                LIMIT 1;
                """
                search_result = await self.system_context.execute_sql_query(query=search_sql)
                if not search_result.success:
                    raise RuntimeError(f"Ошибка поиска книги: {search_result.error}")
                if search_result.rows and len(search_result.rows) > 0:
                    book_id = search_result.rows[0].get("id")
                    logger.info(f"Найден ID книги {book_id} по запросу '{input_data.query}'")
                else:
                    raise ValueError(f"Книга по запросу '{input_data.query}' не найдена")
            
            if not book_id:
                raise ValueError("Необходимо указать book_id, book_title или query")
            
            # 3. Получение метаданных книги
            metadata_sql = f"""
            SELECT 
                b.id as book_id,
                b.title,
                b.isbn,
                b.publication_date,
                a.first_name,
                a.last_name,
                a.birth_date
            FROM "Lib".books b
            JOIN "Lib".authors a ON b.author_id = a.id
            WHERE b.id = {book_id}
            LIMIT 1;
            """
            metadata_result = await self.system_context.execute_sql_query(query=metadata_sql)
            if not metadata_result.success:
                raise RuntimeError(f"Ошибка получения метаданных: {metadata_result.error}")
            
            metadata = metadata_result.rows[0] if metadata_result.rows and len(metadata_result.rows) > 0 else {}
            
            # 4. Получение текста книги
            chapters_sql = f"""
            SELECT 
                chapter_number,
                chapter_title,
                chapter_text
            FROM "Lib".chapters
            WHERE book_id = {book_id}
            ORDER BY chapter_number
            """
            if input_data.max_chapters:
                chapters_sql += f" LIMIT {input_data.max_chapters}"
            chapters_sql += ";"
            
            chapters_result = await self.system_context.execute_sql_query(query=chapters_sql)
            if not chapters_result.success:
                raise RuntimeError(f"Ошибка получения глав: {chapters_result.error}")
            
            # 5. Формирование полного текста
            full_text = []
            for chapter in chapters_result.rows or []:
                if chapter.get("chapter_title"):
                    full_text.append(f"### {chapter['chapter_title']}\n")
                full_text.append(f"{chapter['chapter_text']}\n\n")
            
            formatted_result = {
                "book_id": book_id,
                "metadata": metadata if input_data.include_metadata else None,
                "chapters_count": len(chapters_result.rows or []),
                "full_text": "".join(full_text),
                "source": "Lib.chapters"
            }
            
            # Ограничение размера текста для безопасности
            if len(formatted_result["full_text"]) > 100000:
                formatted_result["full_text"] = formatted_result["full_text"][:100000] + "\n\n[Текст обрезан из-за ограничения размера]"
                formatted_result["text_truncated"] = True
            
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                observation_item_id=None,
                result=formatted_result,
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
    
    async def _dynamic_sql_query(self, parameters: DynamicSQLInput, context: BaseSessionContext, step_number: int) -> ExecutionResult:
        """Генерация и выполнение SQL запроса с правильной валидацией."""
        try:
            # 1. Валидация параметров
            if isinstance(parameters, dict):
                input_data = DynamicSQLInput(**parameters)
            else:
                input_data = parameters
            logger.debug(f"Валидация параметров успешна: {input_data}")

            # 2. Получение SQLGenerationService
            sql_service = await self.system_context.get_service("sql_generation_service")
            if not sql_service:
                raise RuntimeError("SQLGenerationService не зарегистрирован в системном контексте")

            # 3. Подготовка входных данных для сервиса генерации
            from core.infrastructure.service.sql_generation.schema import SQLGenerationInput
            generation_input = SQLGenerationInput(
                user_question=input_data.user_question,
                tables=input_data.context_tables,
                max_rows=input_data.max_rows,
                context=f"Цель: анализ библиотечных данных. Максимум {input_data.max_rows} строк."
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
                    "row_count": result.rowcount,
                    "column_names": result.columns if hasattr(result, 'columns') else [],
                    "reasoning": "Запрос выполнен через SQLGenerationService с автоматической коррекцией" if input_data.include_reasoning else None
                }

                return ExecutionResult(
                    status=ExecutionStatus.SUCCESS,
                    observation_item_id=None,
                    result=formatted_result,
                    summary=f"Выполнен SQL запрос, получено строк: {formatted_result['row_count']}",
                    error=None
                )
            else:
                raise RuntimeError(f"Ошибка выполнения SQL запроса через SQLGenerationService: {result.error}")

        except Exception as e:
            logger.error(f"Ошибка генерации и выполнения SQL: {str(e)}")
            return self._build_error_result(
                context=context,
                error_message=str(e),
                error_type="SQL_GENERATION_ERROR",
                step_number=step_number
            )
    
    def _build_error_result(self, context: BaseSessionContext, error_message: str, error_type: str, step_number: int) -> ExecutionResult:
        """Построение результата с ошибкой выполнения capability."""
        logger.error(f"Построение результата с ошибкой на шаге {step_number}: {error_type} - {error_message}")
        return ExecutionResult(
            status=ExecutionStatus.FAILED,
            result=None,
            observation_item_id=None,
            summary=error_message,
            error=f"{error_type}: {error_message}"
        )