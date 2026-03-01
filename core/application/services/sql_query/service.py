from typing import Dict, Any, List, Optional
from core.application.services.base_service import BaseService, ServiceInput, ServiceOutput
from core.models.types.db_types import DBQueryResult
from core.application.services.sql_generation.error_analyzer import SQLErrorAnalyzer
from core.application.context.base_system_context import BaseSystemContext
from core.models.schemas.sql_query_schemas import SQLQueryInput, SQLQueryOutput
from core.application.context.application_context import ApplicationContext
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
    
    # Зависимости в правильном порядке
    DEPENDENCIES = ["sql_validator_service", "sql_generation_service"]  # Зависит от валидатора и генератора

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
            # Доступны через: self.sql_validator_service_instance, self.sql_generation_service_instance

            # Инициализация анализатора ошибок
            self.error_analyzer = SQLErrorAnalyzer(self.application_context)
            if not await self.error_analyzer.initialize():
                self.logger.error("Не удалось инициализировать SQLErrorAnalyzer")
                return False

            # Дополнительная валидация - проверяем зависимости
            # Они должны быть установлены методом _resolve_dependencies родительского класса
            validator_service = getattr(self, 'sql_validator_service_instance', None)
            generation_service = getattr(self, 'sql_generation_service_instance', None)

            if not validator_service:
                self.logger.warning("sql_validator_service не загружен, пытаемся получить напрямую")
                # Попробуем получить зависимость напрямую из контекста
                validator_service = self.application_context.get_service('sql_validator_service')
                if validator_service:
                    self.logger.info("sql_validator_service получен из контекста, устанавливаем вручную")
                    setattr(self, 'sql_validator_service_instance', validator_service)
                    if not hasattr(self, '_dependencies'):
                        self._dependencies = {}
                    self._dependencies['sql_validator_service'] = validator_service

            if not generation_service:
                self.logger.warning("sql_generation_service не загружен, пытаемся получить напрямую")
                # Попробуем получить зависимость напрямую из контекста
                generation_service = self.application_context.get_service('sql_generation_service')
                if generation_service:
                    self.logger.info("sql_generation_service получен из контекста, устанавливаем вручную")
                    setattr(self, 'sql_generation_service_instance', generation_service)
                    if not hasattr(self, '_dependencies'):
                        self._dependencies = {}
                    self._dependencies['sql_generation_service'] = generation_service

            self.logger.info("SQLQueryService успешно инициализирован")
            return True
        except Exception as e:
            self.logger.error(f"Ошибка инициализации SQLQueryService: {str(e)}")
            return False

    def _get_event_type_for_success(self) -> 'EventType':
        """Возвращает тип события для успешного выполнения сервиса SQL-запросов."""
        from core.infrastructure.event_bus.event_bus import EventType
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
        from core.models.data.execution import ExecutionContext
        from core.application.tools.sql_tool import SQLToolInput
        
        try:
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
                    self.logger.error(f"Валидация входных данных не пройдена: {e}")
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

            # === ЭТАП 3: Выполнение через SQLTool через ActionExecutor ===
            # Используем executor для вызова инструмента
            exec_context = ExecutionContext()
            
            tool_result = await self.executor.execute_action(
                action_name="sql_tool.execute_query",
                parameters={
                    "sql": validation_result.sql,
                    "parameters": parameters,
                    "max_rows": max_rows
                },
                context=exec_context
            )

            # === ЭТАП 4: Валидация выходных данных через схему ===
            output_schema = self.get_cached_output_contract_safe("sql_query_service.execute")
            if output_schema and tool_result.success and tool_result.data:
                try:
                    output_schema.model_validate({
                        "rows": tool_result.data.get('rows', []),
                        "columns": tool_result.data.get('columns', []),
                        "rowcount": tool_result.data.get('rowcount', 0),
                        "execution_time": tool_result.data.get('execution_time', 0)
                    })
                except Exception as e:
                    self.logger.error(f"Валидация выходных данных не пройдена: {e}")

            # Преобразуем результат в DBQueryResult
            if tool_result.success and tool_result.data:
                return DBQueryResult(
                    success=True,
                    rows=tool_result.data.get('rows', []),
                    columns=tool_result.data.get('columns', []),
                    rowcount=tool_result.data.get('rowcount', 0),
                    execution_time=tool_result.data.get('execution_time', 0)
                )
            else:
                return DBQueryResult(
                    success=False,
                    rows=[],
                    columns=[],
                    rowcount=0,
                    error=tool_result.error or "Неизвестная ошибка при выполнении запроса"
                )

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
            sql_gen_service = self.application_context.get_service("sql_generation_service")

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
            self.logger.error(f"Ошибка перезапуска SQLQueryService: {str(e)}")
            return False

    async def shutdown(self) -> None:
        """Завершение работы сервиса"""
        self.logger.info("Завершение работы SQLQueryService")
        # Закрытие ресурсов при необходимости
        await self.error_analyzer.shutdown()