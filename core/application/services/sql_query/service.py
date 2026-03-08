import time
from typing import Dict, Any, List, Optional
from core.application.services.base_service import BaseService, ServiceInput, ServiceOutput
from core.models.types.db_types import DBQueryResult
from core.application.services.sql_generation.error_analyzer import SQLErrorAnalyzer
from core.application.context.base_system_context import BaseSystemContext
from core.models.schemas.sql_query_schemas import SQLQueryInput, SQLQueryOutput
from core.application.context.application_context import ApplicationContext


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
    
    # Зависимости в правильном порядке
    DEPENDENCIES = ["sql_validator_service", "sql_generation"]  # Зависит от валидатора и генератора

    @property
    def description(self) -> str:
        return "Сервис для безопасного выполнения SQL-запросов с валидацией и параметризацией"

    def __init__(self, application_context: ApplicationContext, name: str = "sql_query_service", component_config=None, executor=None):
        from core.config.component_config import ComponentConfig
        # Создаем минимальный ComponentConfig, если не передан
        if component_config is None:
            component_config = ComponentConfig(
                variant_id="sql_query_service_default",
                prompt_versions={},
                input_contract_versions={},
                output_contract_versions={}
            )
        super().__init__(name, application_context, component_config=component_config, executor=executor)

        # НЕ загружаем зависимости здесь! Только инициализация внутреннего состояния
        self.error_analyzer = None

        # Конфигурация безопасности
        self.allowed_operations = ["SELECT"]  # Разрешаем только операции чтения
        self.max_result_rows = 1000

    async def _custom_initialize(self) -> bool:
        """Инициализация зависимостей"""
        try:
            # Зависимости уже загружены родительским методом
            # Доступны через: self.sql_validator_service_instance, self.sql_generation_instance

            # Инициализация анализатора ошибок
            self.error_analyzer = SQLErrorAnalyzer(self.application_context, executor=self.executor)
            if not await self.error_analyzer.initialize():
                if self.event_bus_logger:
                    await self.event_bus_logger.error("Не удалось инициализировать SQLErrorAnalyzer")
                return False

            if self.event_bus_logger:
                await self.event_bus_logger.info("SQLQueryService успешно инициализирован")
            return True
        except Exception as e:
            if self.event_bus_logger:
                await self.event_bus_logger.error(f"Ошибка инициализации SQLQueryService: {str(e)}")
            return False

    def _get_event_type_for_success(self) -> 'EventType':
        """Возвращает тип события для успешного выполнения сервиса SQL-запросов."""
        from core.infrastructure.event_bus.unified_event_bus import EventType
        return EventType.PROVIDER_REGISTERED

    async def _execute_impl(
        self,
        capability: 'Capability',
        parameters: Dict[str, Any],
        execution_context: 'ExecutionContext'
    ) -> Dict[str, Any]:
        """
        Реализация бизнес-логики сервиса SQL-запросов.

        ВАЖНО: Валидация входа/выхода и метрики выполняются в BaseComponent.execute()
        Здесь только бизнес-логика.
        """
        # Выполнение безопасного SQL-запроса
        result = await self.execute_query_from_user_request(
            user_question=parameters.get("user_question", ""),
            tables=parameters.get("tables", []),
            max_rows=parameters.get("max_rows", 50)
        )
        return {"query_result": result, "capability": capability.name}

    async def execute_query(
        self,
        sql_query: str,
        parameters: Dict[str, Any] = None,
        max_rows: int = 50
    ) -> DBQueryResult:
        """
        Безопасное выполнение готового SQL-запроса через SQLTool.

        ПАРАМЕТРЫ:
        - sql_query: готовый SQL-запрос для выполнения
        - parameters: параметры запроса
        - max_rows: максимальное количество возвращаемых строк

        ВОЗВРАЩАЕТ:
        - DBQueryResult: результат выполнения запроса
        """
        from core.application.agent.components.action_executor import ExecutionContext
        from core.application.tools.sql_tool import SQLToolInput

        try:
            # [SQL_DEBUG] 2.1. Входные параметры
            await self.event_bus_logger.info(f"[SQL_DEBUG] execute_query вызван с sql={sql_query}, parameters={parameters}, max_rows={max_rows}")
            
            # === ЭТАП 1: Валидация входных данных через схему ===
            input_schema = self.get_cached_input_contract_safe("sql_query_service.execute")
            if input_schema:
                try:
                    input_schema.model_validate({
                        "sql": sql_query,
                        "parameters": parameters,
                        "max_rows": max_rows
                    })
                except Exception as e:
                    if self.event_bus_logger:
                        await self.event_bus_logger.error(f"Валидация входных данных не пройдена: {e}")
                    return DBQueryResult(
                        success=False,
                        rows=[],
                        columns=[],
                        rowcount=0,
                        error=f"Ошибка входных данных: {str(e)}"
                    )

            # === ЭТАП 2: Валидация SQL через SQLValidatorService ===
            if not hasattr(self, 'sql_validator_service_instance') or not self.sql_validator_service_instance:
                return DBQueryResult(
                    success=False,
                    rows=[],
                    columns=[],
                    rowcount=0,
                    error="SQLValidatorService не доступен"
                )

            # Валидируем запрос
            validation_result = await self.sql_validator_service_instance.validate_query(
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

            # === ЭТАП 3: Выполнение запроса через db_provider ===
            # Получаем db_provider напрямую из infrastructure_context
            # [SQL_DEBUG] 2.2. Получение db_provider
            db_provider = None
            if hasattr(self, 'application_context') and self.application_context:
                if hasattr(self.application_context, 'infrastructure_context'):
                    db_provider = self.application_context.infrastructure_context.get_provider("default_db")
            
            await self.event_bus_logger.info(f"[SQL_DEBUG] db_provider найден: {db_provider is not None}")

            if not db_provider:
                return DBQueryResult(
                    success=False,
                    rows=[],
                    columns=[],
                    rowcount=0,
                    error="DB провайдер не найден"
                )

            # Выполняем запрос напрямую через db_provider
            start_exec_time = time.time()
            try:
                # [SQL_DEBUG] 2.3. Вызов db_provider.execute
                await self.event_bus_logger.info(f"[SQL_DEBUG] вызов db_provider.execute с SQL: {validation_result.sql}, params: {parameters}")
                
                result = await db_provider.execute(
                    sql=validation_result.sql,
                    params=parameters
                )
                execution_time = time.time() - start_exec_time
                
                await self.event_bus_logger.info(f"[SQL_DEBUG] результат db_provider.execute: success={result.success}, error={result.error}, rows={len(result.rows) if result.rows else 0}")

                # Преобразуем результат в DBQueryResult
                # [SQL_DEBUG] 2.4. Возврат DBQueryResult (успех)
                db_result = DBQueryResult(
                    success=True,
                    rows=result.rows if hasattr(result, 'rows') else [],
                    columns=result.columns if hasattr(result, 'columns') else [],
                    rowcount=result.rowcount if hasattr(result, 'rowcount') else len(result.rows) if hasattr(result, 'rows') else 0,
                    execution_time=execution_time
                )
                await self.event_bus_logger.info(f"[SQL_DEBUG] возвращаем DBQueryResult: success={db_result.success}, error={db_result.error}, rows={len(db_result.rows)}")
                return db_result
            except Exception as e:
                if self.event_bus_logger:
                    await self.event_bus_logger.error(f"Ошибка выполнения SQL: {e}")
                # [SQL_DEBUG] 2.4. Возврат DBQueryResult (ошибка исключения)
                db_result = DBQueryResult(
                    success=False,
                    rows=[],
                    columns=[],
                    rowcount=0,
                    error=f"Ошибка выполнения SQL: {str(e)}"
                )
                await self.event_bus_logger.info(f"[SQL_DEBUG] возвращаем DBQueryResult: success={db_result.success}, error={db_result.error}, rows={len(db_result.rows)}")
                return db_result

        except Exception as e:
            if self.event_bus_logger:
                await self.event_bus_logger.error(f"Ошибка выполнения SQL-запроса: {str(e)}", exc_info=True)
            # [SQL_DEBUG] 2.4. Возврат DBQueryResult (общая ошибка)
            db_result = DBQueryResult(
                success=False,
                rows=[],
                columns=[],
                rowcount=0,
                error=str(e)
            )
            await self.event_bus_logger.info(f"[SQL_DEBUG] возвращаем DBQueryResult: success={db_result.success}, error={db_result.error}, rows={len(db_result.rows)}")
            return db_result

    async def execute_query_from_user_request(
        self,
        user_question: str,
        tables: List[str],
        max_rows: int = 50
    ) -> DBQueryResult:
        """
        Выполнение SQL-запроса на основе пользовательского вопроса через интеграцию с SQLGenerationservices.
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
            # Используем components.get() напрямую вместо get_service()
            sql_gen_service = None
            if hasattr(self, '_application_context') and self._application_context:
                sql_gen_service = self._application_context.components.get(ComponentType.SERVICE, "sql_generation")

            if not sql_gen_service:
                return DBQueryResult(
                    success=False,
                    rows=[],
                    columns=[],
                    rowcount=0,
                    error="SQLGenerationService не доступен"
                )

            # Подготовка входных данных для SQLGenerationService
            from core.models.schemas.sql_generation_schemas import SQLGenerationInput
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
            if self.event_bus_logger:
                await self.event_bus_logger.error(f"Ошибка выполнения SQL-запроса: {str(e)}", exc_info=True)
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
        Прямое выполнение готового SQL-запроса с валидацией через SQLValidatorservices.

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
            if self.event_bus_logger:
                await self.event_bus_logger.error(f"Ошибка перезапуска SQLQueryService: {str(e)}")
            return False

    async def shutdown(self) -> None:
        """Завершение работы сервиса"""
        if self.event_bus_logger:
            await self.event_bus_logger.info("Завершение работы SQLQueryService")
        # Закрытие ресурсов при необходимости
        await self.error_analyzer.shutdown()