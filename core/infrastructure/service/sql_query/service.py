from typing import Dict, Any, List, Optional
from core.infrastructure.service.base_service import BaseService, ServiceInput, ServiceOutput
from models.db_types import DBQueryResult
from core.infrastructure.service.sql_generation.error_analyzer import SQLErrorAnalyzer
from core.system_context.base_system_contex import BaseSystemContext
from .schema import SQLQueryInput, SQLQueryOutput
import logging


class SQLQueryServiceInput(ServiceInput):
    """Входные данные для SQLQueryService"""
    def __init__(self, user_question: str, tables: List[str], max_rows: int = 50, context: Optional[str] = None):
        self.user_question = user_question
        self.tables = tables
        self.max_rows = max_rows
        self.context = context


class SQLQueryServiceOutput(ServiceOutput):
    """Выходные данные для SQLQueryService"""
    def __init__(self, query_result: DBQueryResult, metadata: Dict[str, Any] = None):
        self.query_result = query_result
        self.metadata = metadata or {}


class SQLQueryService(BaseService):
    """
    Сервис для безопасного выполнения SQL-запросов.
    
    ОТЛИЧИЯ ОТ SQLGenerationService:
    - Только выполнение (без генерации)
    - Принимает готовый SQL-запрос
    - Проверяет и валидирует запрос
    - Обеспечивает безопасное выполнение через параметризованные запросы
    """
    
    @property
    def description(self) -> str:
        return "Сервис для безопасного выполнения SQL-запросов с валидацией и параметризацией"

    def __init__(self, system_context: BaseSystemContext, name: str = None):
        super().__init__(system_context, name or "sql_query_service")
        
        # Зависимости
        # Используем новый централизованный SQLValidatorService
        self.validator_service = system_context.get_resource("sql_validator_service")
        self.error_analyzer = SQLErrorAnalyzer(system_context)
        
        # Сохраняем системный контекст для выполнения запросов
        self.system_context = system_context
        
        # Конфигурация безопасности
        self.allowed_operations = ["SELECT"]  # Разрешаем только операции чтения
        self.max_result_rows = 1000

    async def initialize(self) -> bool:
        """Инициализация зависимостей"""
        try:
            # Проверка наличия валидатора
            if not self.validator_service:
                self.logger.error("SQLValidatorService не зарегистрирован в системном контексте")
                return False
            
            # Инициализация анализатора ошибок
            analyzer_ok = await self.error_analyzer.initialize()
            if not analyzer_ok:
                self.logger.error("Не удалось инициализировать SQLErrorAnalyzer")
                return False
                
            self.logger.info("SQLQueryService успешно инициализирован")
            return True
        except Exception as e:
            self.logger.error(f"Ошибка инициализации SQLQueryService: {str(e)}")
            return False

    async def execute(self, input_data: SQLQueryServiceInput) -> SQLQueryServiceOutput:
        """
        Выполнение безопасного SQL-запроса.

        ARGS:
        - input_data: SQLQueryServiceInput - содержит SQL-запрос и параметры

        RETURNS:
        - SQLQueryServiceOutput: результат выполнения запроса
        """
        # Для совместимости используем метод execute_query_from_user_request
        result = await self.execute_query_from_user_request(
            user_question=input_data.user_question,
            tables=input_data.tables,
            max_rows=input_data.max_rows
        )

        # Формируем метаданные
        metadata = {
            "service": "SQLQueryService",
            "input_user_question": input_data.user_question,
            "input_tables": input_data.tables,
            "max_rows": input_data.max_rows
        }

        return SQLQueryServiceOutput(query_result=result, metadata=metadata)

    async def execute_query(
        self,
        sql_query: str,
        parameters: Dict[str, Any] = None,
        max_rows: int = 50
    ) -> DBQueryResult:
        """
        Безопасное выполнение готового SQL-запроса с валидацией.

        ПАРАМЕТРЫ:
        - sql_query: готовый SQL-запрос для выполнения
        - parameters: параметры запроса
        - max_rows: максимальное количество возвращаемых строк

        ВОЗВРАЩАЕТ:
        - DBQueryResult: результат выполнения запроса
        """
        try:
            # Валидация SQL-запроса через централизованный SQLValidatorService
            if not self.validator_service:
                return DBQueryResult(
                    success=False,
                    rows=[],
                    columns=[],
                    rowcount=0,
                    error="SQLValidatorService не доступен"
                )

            validation_result = await self.validator_service.validate_query(
                sql_query,
                parameters or {}
            )

            if not validation_result.is_valid:
                return DBQueryResult(
                    success=False,
                    rows=[],
                    columns=[],
                    rowcount=0,
                    error=f"Запрос не прошел валидацию: {validation_result.validation_errors}"
                )

            # Преобразуем именованные параметры в позиционные для PostgreSQL
            positional_params = []
            query_for_postgres = validation_result.sql
            
            # Заменяем именованные параметры ($param) на позиционные ($1, $2, ...)
            param_names = list(validation_result.parameters.keys())
            for i, param_name in enumerate(param_names):
                query_for_postgres = query_for_postgres.replace(f"${param_name}", f"${i+1}")
            
            # Создаем позиционный список параметров
            positional_params = [validation_result.parameters[name] for name in param_names]
            
            # Выполнение безопасного запроса через внутренний метод системного контекста
            # чтобы избежать циклической зависимости с SQLQueryService
            execution_result = await self.system_context._execute_raw_sql_query(
                query=query_for_postgres,
                params=positional_params,
                db_provider_name="default_db",
                max_rows=max_rows
            )

            return execution_result

        except Exception as e:
            self.logger.error(f"Ошибка выполнения SQL-запроса: {str(e)}", exc_info=True)
            return DBQueryResult(
                success=False,
                rows=[],
                columns=[],
                rowcount=0,
                error=str(e)
            )

    async def execute_query_from_user_request(
        self,
        user_question: str,
        tables: List[str],
        max_rows: int = 50
    ) -> DBQueryResult:
        """
        Выполнение SQL-запроса на основе пользовательского вопроса через интеграцию с SQLGenerationService.
        Этот метод обеспечивает совместимость с существующими вызовами.

        ПАРАМЕТРЫ:
        - user_question: текст вопроса пользователя
        - tables: список таблиц, к которым разрешен доступ
        - max_rows: максимальное количество возвращаемых строк

        ВОЗВРАЩАЕТ:
        - DBQueryResult: результат выполнения запроса
        """
        try:
            # Получаем SQLGenerationService для генерации безопасного запроса
            sql_gen_service = await self.system_context.get_service("sql_generation_service")

            if not sql_gen_service:
                return DBQueryResult(
                    success=False,
                    rows=[],
                    columns=[],
                    rowcount=0,
                    error="SQLGenerationService не доступен"
                )

            # Подготовка входных данных для SQLGenerationService
            from core.infrastructure.service.sql_generation.schema import SQLGenerationInput
            generation_input = SQLGenerationInput(
                user_question=user_question,
                tables=tables,
                max_rows=max_rows,
                context=f"Цель: выполнение безопасного SQL-запроса. Максимум {max_rows} строк."
            )

            # Выполнение через SQLGenerationService с автоматической коррекцией
            result = await sql_gen_service.execute_with_auto_correction(
                generation_input,
                context=None
            )

            return result

        except Exception as e:
            self.logger.error(f"Ошибка выполнения SQL-запроса: {str(e)}", exc_info=True)
            return DBQueryResult(
                success=False,
                rows=[],
                columns=[],
                rowcount=0,
                error=str(e)
            )

    async def execute_direct_query(
        self,
        sql_query: str,
        parameters: Dict[str, Any] = None,
        max_rows: int = 50
    ) -> DBQueryResult:
        """
        Прямое выполнение готового SQL-запроса с валидацией через SQLValidatorService.

        ПАРАМЕТРЫ:
        - sql_query: готовый SQL-запрос для выполнения
        - parameters: параметры запроса
        - max_rows: максимальное количество возвращаемых строк

        ВОЗВРАЩАЕТ:
        - DBQueryResult: результат выполнения запроса
        """
        return await self.execute_query(sql_query, parameters, max_rows)

    async def restart(self) -> bool:
        """
        Перезапуск сервиса без полной перезагрузки системного контекста.
        
        ВОЗВРАЩАЕТ:
        - bool: True если перезапуск прошел успешно, иначе False
        """
        try:
            # Сначала останавливаем текущий экземпляр
            await self.shutdown()
            
            # Затем инициализируем заново
            return await self.initialize()
        except Exception as e:
            self.logger.error(f"Ошибка перезапуска SQLQueryService: {str(e)}")
            return False

    async def shutdown(self) -> None:
        """Завершение работы сервиса"""
        self.logger.info("Завершение работы SQLQueryService")
        # Закрытие ресурсов при необходимости
        await self.error_analyzer.shutdown()