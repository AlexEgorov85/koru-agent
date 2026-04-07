import time
from typing import Dict, Any, List, Optional
from core.infrastructure.event_bus.unified_event_bus import EventType
from core.models.data.capability import Capability
from core.components.services.base_service import BaseService, ServiceInput, ServiceOutput
from core.models.types.db_types import DBQueryResult
from core.components.services.sql_generation.error_analyzer import SQLErrorAnalyzer
from core.application_context.base_system_context import BaseSystemContext
from core.models.sql_schemas import SQLGenerationInput, SQLQueryInput, SQLQueryOutput
from core.application_context.application_context import ApplicationContext
from core.utils.async_utils import safe_async_call


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
    DEPENDENCIES = ["sql_generation"]

    @property
    def description(self) -> str:
        return "Сервис для безопасного выполнения SQL-запросов с валидацией и параметризацией"

    def __init__(self, application_context: ApplicationContext, name: str = "sql_query_service", component_config=None, executor=None, event_bus=None):
        from core.config.component_config import ComponentConfig
        # Создаем минимальный ComponentConfig, если не передан
        if component_config is None:
            component_config = ComponentConfig(
                variant_id="sql_query_service_default",
                prompt_versions={},
                input_contract_versions={},
                output_contract_versions={}
            )
        super().__init__(
            name=name,
            application_context=application_context,
            component_config=component_config,
            executor=executor,
            event_bus=event_bus
        )

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
            self.error_analyzer = SQLErrorAnalyzer(
                self.application_context, 
                executor=self.executor,
                event_bus=self._event_bus
            )
            if not await self.error_analyzer.initialize():
                await self._publish_with_context(
                    event_type="sql_query.init_failed",
                    data={"component": "SQLErrorAnalyzer"},
                    source="sql_query"
                )
                return False

            await self._publish_with_context(
                event_type="sql_query.initialized",
                data={"service": "sql_query"},
                source="sql_query"
            )
            return True
        except Exception as e:
            await self._publish_with_context(
                event_type="sql_query.init_failed",
                data={"error": str(e)},
                source="sql_query"
            )
            return False
                  # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
                  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            return False

    def _get_event_type_for_success(self) -> EventType:
        """Возвращает тип события для успешного выполнения сервиса SQL-запросов."""
        return EventType.PROVIDER_REGISTERED

    def _execute_impl(
        self,
        capability: Capability,
        parameters: Dict[str, Any],
        execution_context: 'ExecutionContext'
    ) -> Dict[str, Any]:
        """
        Реализация бизнес-логики сервиса SQL-запросов (СИНХРОННАЯ).

        ВАЖНО: Валидация входа/выхода и метрики выполняются в BaseComponent.execute()
        Здесь только бизнес-логика.
        """
        result = safe_async_call(self.execute_query_from_user_request(
            user_question=parameters.get("user_question", ""),
            tables=parameters.get("tables", []),
            max_rows=parameters.get("max_rows", 50),
            execution_context=execution_context
        ))
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
        from core.agent.components.action_executor import ExecutionContext
        from core.components.services.tools.sql_tool import SQLToolInput

        try:
            await self._publish_with_context(
                event_type="sql_query.execute_called",
                data={"sql": sql_query, "max_rows": max_rows},
                source="sql_query"
            )
            
            # === ЭТАП 1: Валидация входных данных через схему ===
            input_schema = self.get_input_contract("sql_query_service.execute")
            if input_schema:
                try:
                    input_schema.model_validate({
                        "sql": sql_query,
                        "parameters": parameters,
                        "max_rows": max_rows
                    })
                except Exception as e:
                    await self._publish_with_context(
                        event_type="sql_query.validation_error",
                        data={"error": str(e)},
                        source="sql_query"
                    )
                    return DBQueryResult(
                        success=False,
                        rows=[],
                        columns=[],
                        rowcount=0,
                        error=f"Ошибка входных данных: {str(e)}"
                    )

            # === ЭТАП 2: Валидация SQL через SQLValidatorService (через executor) ===
            # Конвертируем параметры из списка в dict для валидатора
            params_for_validation = parameters
            if isinstance(parameters, (list, tuple)):
                # Конвертируем список в dict с ключами '1', '2', ...
                params_for_validation = {str(i+1): val for i, val in enumerate(parameters)}
            elif parameters is None:
                params_for_validation = {}
            
            await self._publish_with_context(
                event_type="sql_query.validating",
                data={"sql": sql_query},
                source="sql_query"
            )

            from core.agent.components.action_executor import ExecutionContext
            from core.models.data.execution import ExecutionStatus

            exec_context = ExecutionContext()
            validation_result_exec = await self.executor.execute_action(
                action_name="sql_validator_service.validate_query",
                parameters={
                    "sql_query": sql_query,
                    "parameters": params_for_validation
                },
                context=exec_context
            )

            if validation_result_exec.status != ExecutionStatus.COMPLETED or not validation_result_exec.data:
                return DBQueryResult(
                    success=False,
                    rows=[],
                    columns=[],
                    rowcount=0,
                    error=f"Валидация не удалась: {validation_result_exec.error}"
                )

            validation_result = validation_result_exec.data
            
            await self._publish_with_context(
                event_type="sql_query.validated",
                data={"is_valid": validation_result.is_valid},
                source="sql_query"
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
            db_provider = None
            if hasattr(self, 'application_context') and self.application_context:
                if hasattr(self.application_context, 'infrastructure_context'):
                    infra = self.application_context.infrastructure_context
                    db_provider = infra.resource_registry.get_resource("default_db").instance if infra.resource_registry else None
            
            await self._publish_with_context(
                event_type="sql_query.db_provider_found",
                data={"found": db_provider is not None},
                source="sql_query"
            )

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
                await self._publish_with_context(
                    event_type="sql_query.executing",
                    data={"sql": validation_result.sql},
                    source="sql_query"
                )

                result = await db_provider.execute_query(
                    query=validation_result.sql,
                    params=parameters
                )
                execution_time = time.time() - start_exec_time

                db_result = DBQueryResult(
                    success=True,
                    rows=result.rows if hasattr(result, 'rows') else [],
                    columns=result.columns if hasattr(result, 'columns') else [],
                    rowcount=result.rowcount if hasattr(result, 'rowcount') else len(result.rows) if hasattr(result, 'rows') else 0,
                    execution_time=execution_time
                )
                await self._publish_with_context(
                    event_type="sql_query.executed",
                    data={"success": db_result.success, "rows": len(db_result.rows)},
                    source="sql_query"
                )
                return db_result
            except Exception as e:
                await self._publish_with_context(
                    event_type="sql_query.execution_error",
                    data={"error": str(e)},
                    source="sql_query"
                )
                db_result = DBQueryResult(
                    success=False,
                    rows=[],
                    columns=[],
                    rowcount=0,
                    error=f"Ошибка выполнения SQL: {str(e)}"
                )
                return db_result

        except Exception as e:
            await self._publish_with_context(
                event_type="sql_query.error",
                data={"error": str(e)},
                source="sql_query"
            )
            db_result = DBQueryResult(
                success=False,
                rows=[],
                columns=[],
                rowcount=0,
                error=str(e)
            )
            return db_result

    async def execute_query_from_user_request(
        self,
        user_question: str,
        tables: List[str],
        max_rows: int = 50,
        execution_context: 'ExecutionContext' = None
    ) -> DBQueryResult:
        """
        Выполнение SQL-запроса на основе пользовательского вопроса через интеграцию с SQLGenerationservices.
        Этот метод обеспечивает совместимость с существующими вызовами.

        ПАРАМЕТРЫ:
        - user_question: текст вопроса пользователя
        - tables: список таблиц, к которым разрешен доступ
        - max_rows: максимальное количество возвращаемых строк
        - execution_context: контекст выполнения для логирования

        ВОЗВРАЩАЕТ:
        - DBQueryResult: результат выполнения запроса
        """
        try:
            await self._publish_with_context(
                event_type="sql_query.execute_from_request",
                data={"user_question": user_question, "tables": tables, "max_rows": max_rows},
                source="sql_query",
                execution_context=execution_context
            )
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
            await self._publish_with_context(
                event_type="sql_query.user_request_error",
                data={"error": str(e)},
                source="sql_query"
            )
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
            await self.shutdown()
            return await self.initialize()
        except Exception as e:
            await self._publish_with_context(
                event_type="sql_query.restart_failed",
                data={"error": str(e)},
                source="sql_query"
            )
            return False

    async def shutdown(self) -> None:
        """Завершение работы сервиса"""
        await self._publish_with_context(
            event_type="sql_query.shutdown",
            data={"service": "sql_query"},
            source="sql_query"
        )
        await self.error_analyzer.shutdown()