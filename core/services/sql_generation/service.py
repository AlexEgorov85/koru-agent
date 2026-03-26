from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from core.models.enums.common_enums import ComponentType
from core.services.base_service import BaseService, ServiceInput, ServiceOutput as BaseServiceOutput
from abc import ABC


# Конкретная реализация ServiceOutput для SQLGenerationService
class SQLGenerationServiceOutput(BaseServiceOutput):
    def __init__(self, data: Dict[str, Any]):
        self.data = data
from core.services.sql_generation.error_analyzer import SQLErrorAnalyzer, ExecutionError
from core.services.sql_generation.correction import SQLCorrectionEngine
from core.models.schemas.sql_generation_schemas import (
    SQLGenerationInput, SQLGenerationOutput,
    SQLCorrectionInput, SQLCorrectionOutput
)
from core.application_context.application_context import ApplicationContext
from core.models.types.db_types import DBQueryResult


@dataclass
class SQLGenerationResult:
    """Результат генерации с метаданными для анализа ошибок"""
    sql: str
    parameters: Dict[str, Any]
    reasoning: str
    tables_used: List[str]
    safety_score: float  # 0.0-1.0 оценка безопасности
    generation_id: str   # Для трассировки в событиях

class SQLGenerationService(BaseService):
    """
    Централизованный сервис генерации и коррекции безопасных SQL-запросов.

    АРХИТЕКТУРНЫЕ ПРИНЦИПЫ:
    - Единая точка генерации для всех навыков
    - Обязательная параметризация всех запросов
    - Автоматическая коррекция на основе ошибок выполнения
    - Интеграция с существующими сервисами (таблицы, промпты)
    - Полная изоляция от инъекций через валидацию
    """

    # Явная декларация зависимостей
    DEPENDENCIES = ["table_description_service", "prompt_service", "contract_service"]

    @property
    def description(self) -> str:
        return "Сервис генерации и коррекции безопасных параметризованных SQL-запросов"

    def __init__(self, application_context: ApplicationContext = None, name: str = "sql_generation", component_config=None, executor=None, event_bus=None):
        from core.config.component_config import ComponentConfig
        # Создаем минимальный ComponentConfig, если не передан
        if component_config is None:
            component_config = ComponentConfig(
                variant_id="sql_generation_default",
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
        # Зависимости будут загружены в _resolve_dependencies() при вызове initialize()
        self.error_analyzer = None
        self.correction_engine = None

        # Конфигурация безопасности
        self.max_correction_attempts = 3
        self.allowed_operations = ["SELECT", "WITH"]  # Запрещаем все кроме чтения
        self.max_result_rows = 1000

    async def _custom_initialize(self) -> bool:
        """Инициализация зависимостей и внутреннего состояния"""
        try:
            # Зависимости уже загружены родительским методом
            # Доступны через: self.table_description_service_instance

            # Инициализация анализатора ошибок
            # В новой архитектуре SQLErrorAnalyzer может использовать application_context
            self.error_analyzer = SQLErrorAnalyzer(self.application_context, executor=self.executor)
            if not await self.error_analyzer.initialize():
                if self.event_bus_logger:
                    await self.event_bus_logger.error("Не удалось инициализировать SQLErrorAnalyzer")
                return False

            # Инициализация движка коррекции
            self.correction_engine = SQLCorrectionEngine(self.application_context, executor=self.executor)

            # Проверка критических зависимостей
            if not self.table_description_service_instance:
                if self.event_bus_logger:
                    await self.event_bus_logger.error("table_description_service не загружен (архитектурная ошибка)")
                return False

            return True
        except Exception as e:
            if self.event_bus_logger:
                await self.event_bus_logger.error(f"Ошибка инициализации SQLGenerationService: {str(e)}")
            return False

    async def _load_service_prompts(self):
        """Загрузка промптов, специфичных для сервиса генерации SQL"""
        # Промпты уже загружены в базовом классе через ComponentConfig
        # Используем кэшированные промпты из компонента
        pass

    def get_required_prompt_names(self):
        """Возвращает список имен промптов, необходимых для сервиса"""
        return ["sql_generation.generate_safe_query", "sql_generation.correct_query"]

    def _get_event_type_for_success(self) -> 'EventType':
        """Возвращает тип события для успешного выполнения сервиса генерации SQL."""
        from core.infrastructure.event_bus.unified_event_bus import EventType
        return EventType.PROVIDER_REGISTERED

    def _execute_impl(
        self,
        capability: 'Capability',
        parameters: Dict[str, Any],
        execution_context: 'ExecutionContext'
    ) -> Dict[str, Any]:
        """
        Реализация бизнес-логики сервиса генерации SQL (СИНХРОННАЯ).

        ВАЖНО: Валидация входа/выхода и метрики выполняются в BaseComponent.execute()
        Здесь только бизнес-логика.
        """
        # Генерация SQL-запроса на основе параметров (синхронное ожидание)
        result = self._safe_async_call(self.generate_query(SQLGenerationInput(**parameters)))
        from dataclasses import asdict
        return asdict(result)

    def _safe_async_call(self, coro, timeout=30.0):
        """Безопасный вызов async из sync контекста."""
        import asyncio
        
        # Проверяем есть ли running loop
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # Нет loop → используем asyncio.run()
            return asyncio.run(coro)
        
        # Есть running loop → мы внутри async функции
        # Используем asyncio.create_task() и ждём результат
        # Это работает только если мы в том же event loop
        async def wait_for_coro():
            task = asyncio.create_task(coro)
            return await asyncio.wait_for(task, timeout=timeout)
        
        # Запускаем в том же loop через call_soon_threadsafe
        future = asyncio.run_coroutine_threadsafe(wait_for_coro(), loop)
        return future.result(timeout=timeout)

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
                await self.event_bus_logger.error(f"Ошибка перезапуска SQLGenerationService: {str(e)}")
            return False

    async def shutdown(self) -> None:
        """Завершение работы сервиса"""
        # Здесь можно освободить ресурсы, закрыть соединения и т.д.
        # В данном случае у нас нет внешних ресурсов для освобождения

    async def generate_query(
        self,
        natural_language_query: str = None,
        table_schema: str = None,
        input_data: SQLGenerationInput = None,
        context: Optional[Any] = None
    ) -> SQLGenerationResult:
        """
        Генерация безопасного параметризованного SQL-запроса.

        ПРОЦЕСС:
        1. Получение метаданных таблиц через TableDescriptionService
        2. Формирование промпта через PromptService
        3. Генерация через LLM с выходной схемой
        4. Валидация безопасности через SQLValidatorService
        5. Публикация события генерации

        ВОЗВРАЩАЕТ:
        - Параметризованный запрос + параметры (никакой конкатенации!)
        """
        # Поддержка обоих способов вызова: через параметры или через input_data
        if input_data is not None:
            natural_language_query = input_data.natural_language_query
            table_schema = input_data.table_schema
        elif natural_language_query is None or table_schema is None:
            raise ValueError("generate_query requires either natural_language_query and table_schema, or input_data")

        # 1. Получение метаданных таблиц
        # table_metadata = await self._get_table_metadata(input_data.tables)

        # 2. Формирование промпта через централизованный сервис
        prompt_vars = {
            "user_question": natural_language_query,
            "table_descriptions": table_schema if isinstance(table_schema, str) else str(table_schema),
            "allowed_operations": ", ".join(self.allowed_operations),
            "max_rows": self.max_result_rows
        }

        # Используем кэшированный промпт из компонента
        prompt_key = "sql_generation.generate_safe_query"
        prompt_obj = self.get_prompt(prompt_key)
        prompt = prompt_obj.content if prompt_obj else ""

        # Заменяем переменные в кэшированном промпте
        for var_name, var_value in prompt_vars.items():
            placeholder = f"{{{var_name}}}"  # Формат {variable_name}
            prompt = prompt.replace(placeholder, str(var_value))

        # Логирование для отладки
        if self.event_bus_logger:
            await self.event_bus_logger.debug(f"SQL Generation prompt length: {len(prompt)}")
            await self.event_bus_logger.debug(f"SQL Generation prompt[:200]: {prompt[:200]}...")

        try:
            # 4. ВЫЗОВ LLM ЧЕРЕЗ EXECUTOR
            # Используем executor для вызова LLM
            from core.agent.components.action_executor import ExecutionContext
            exec_context = ExecutionContext()
            
            llm_result = await self.executor.execute_action(
                action_name="llm.generate_structured",
                parameters={
                    "prompt": natural_language_query,
                    "system_prompt": prompt,
                    "temperature": 0.3,
                    "max_tokens": 500,
                    "structured_output": {
                        "output_model": "SQLGenerationOutput",
                        "schema_def": SQLGenerationOutput.model_json_schema(),
                        "max_retries": 3,
                        "strict_mode": True
                    }
                },
                context=exec_context
            )

            from core.models.data.execution import ExecutionStatus
            if llm_result.status != ExecutionStatus.COMPLETED or not llm_result.data:
                errors = llm_result.error if hasattr(llm_result, 'error') else 'unknown error'
                raise ValueError(f"SQL generation failed: {errors}")

            # Извлекаем parsed_content из результата
            result_data = llm_result.data
            if hasattr(result_data, 'parsed_content'):
                output = result_data.parsed_content
            elif isinstance(result_data, dict) and 'parsed_content' in result_data:
                output = result_data['parsed_content']
            else:
                # Fallback: пытаемся использовать data напрямую
                output = result_data

            # Валидация SQL через безопасный метод (с fallback)
            validated = await self._validate_sql_safely(output.generated_sql, {})

            # Проверяем что запрос валиден
            if not validated.is_safe or not validated.sql:
                error_msg = "; ".join(validated.validation_errors) if hasattr(validated, 'validation_errors') else "Validation failed"
                raise RuntimeError(f"SQL validation failed: {error_msg}")

            # 5. Формирование результата
            result = SQLGenerationResult(
                sql=validated.sql,
                parameters=validated.parameters,
                reasoning=getattr(output, 'explanation', ''),
                tables_used=[],
                safety_score=validated.safety_score,
                generation_id=f"gen_{hash(natural_language_query)}"
            )

            # Создаём временный объект для публикации события
            temp_input = SQLGenerationInput(natural_language_query=natural_language_query, table_schema=table_schema)
            await self._publish_generation_event("generation_success", result.sql, temp_input, result.safety_score)
            return result

        except Exception as e:
            temp_input = SQLGenerationInput(natural_language_query=natural_language_query, table_schema=table_schema)
            await self._publish_generation_event("generation_failed", str(e), temp_input)
            # ❌ УДАЛЕНО: ValueError без контекста
            # ✅ ТЕПЕРЬ: Выбрасываем SQLValidationError
            from core.errors.exceptions import SQLValidationError
            raise SQLValidationError(
                f"Ошибка валидации сгенерированного SQL: {str(e)}. "
                f"Проверьте что SQLValidatorService доступен и запрос корректен.",
                sql=""  # SQL может быть недоступен при ошибке
            )

    async def generate_query_with_correction(
        self,
        natural_language_query: str = None,
        table_schema: str = None,
        input_data: SQLGenerationInput = None,
        context: Optional[Any] = None,
        max_correction_attempts: int = 3
    ) -> SQLGenerationResult:
        """
        Генерация SQL с авто-коррекцией при ошибках.

        ПРОЦЕСС:
        1. Генерируем SQL запрос
        2. Если ошибка валидации - пытаемся корректировать
        3. Повторяем до max_correction_attempts или успеха
        """
        last_error = None

        for attempt in range(max_correction_attempts):
            try:
                result = await self.generate_query(
                    natural_language_query=natural_language_query,
                    table_schema=table_schema,
                    input_data=input_data,
                    context=context
                )
                return result

            except Exception as e:
                last_error = e
                if self.event_bus_logger:
                    await self.event_bus_logger.warning(
                        f"SQL generation attempt {attempt + 1} failed: {str(e)}"
                    )

                if self.correction_engine and attempt < max_correction_attempts - 1:
                    try:
                        from core.services.sql_generation.error_analyzer import ExecutionError

                        error = ExecutionError(
                            message=str(e),
                            query="",
                            parameters={},
                            db_error_type="validation_error"
                        )

                        analysis = await self.correction_engine.error_analyzer.analyze(error)

                        correction_input = SQLCorrectionInput(
                            original_query=str(e),
                            error_type=analysis.get("error_type", "other_error"),
                            error_message=str(e),
                            suggested_fix=analysis.get("suggested_fix", ""),
                            db_schema=table_schema or ""
                        )

                        corrected = await self.correction_engine.correct_query(correction_input)

                        if self.event_bus_logger:
                            await self.event_bus_logger.info(f"Applied correction: {corrected.corrected_sql}")

                    except Exception as correction_error:
                        if self.event_bus_logger:
                            await self.event_bus_logger.warning(f"Correction failed: {str(correction_error)}")

        from core.errors.exceptions import SQLValidationError
        raise SQLValidationError(
            f"Не удалось сгенерировать корректный SQL после {max_correction_attempts} попыток. "
            f"Последняя ошибка: {str(last_error)}",
            sql=""
        )

    # Вспомогательные методы (приватные)
    async def _get_table_metadata(self, table_names: List[str]) -> Dict[str, Any]:
        """Получение метаданных таблиц через существующий сервис"""
        # Используем components.get() напрямую вместо get_service()
        if hasattr(self, '_application_context') and self._application_context:
            table_service = self._application_context.components.get(ComponentType.SERVICE, "table_description_service")
        else:
            table_service = None
            
        if not table_service:
            raise RuntimeError("table_description_service не зарегистрирован в прикладном контексте")

        metadata_list = []
        for table_name in table_names:
            # Извлекаем схему и имя таблицы (поддержка "schema.table")
            parts = table_name.split(".")
            schema_name = parts[0] if len(parts) > 1 else "public"
            actual_table_name = parts[-1]

            metadata = await table_service.get_table_metadata(
                schema_name=schema_name,
                table_name=actual_table_name,
                context=None,  # Контекст будет передан извне при необходимости
                step_number=0
            )
            metadata_list.append(metadata)

        return {"tables": metadata_list}

    def _format_table_metadata(self, metadata: Dict[str, Any]) -> str:
        """Форматирование метаданных для промпта"""
        # Реализация форматирования в компактном виде для LLM
        formatted = []
        for table in metadata.get("tables", []):
            cols = [f"{col['column_name']} ({col['data_type']})" for col in table.get("columns", [])[:5]]  # Ограничиваем 5 колонками
            formatted.append(f"Таблица {table['schema_name']}.{table['table_name']}:\n  Колонки: {', '.join(cols)}\n  Описание: {table.get('description', 'Без описания')}")
        return "\n\n".join(formatted)

    async def _publish_generation_event(self, event_type: str, data: Any, input_data: SQLGenerationInput, safety_score: float = 0.0):
        """Публикация события генерации через EventBus"""
        # Используем внедрённый event_bus из BaseComponent
        if hasattr(self, '_event_bus') and self._event_bus is not None:
            await self._event_bus.publish(
                event_type=f"sql_generation.{event_type}",
                payload={
                    "user_question": input_data.natural_language_query,
                    "table_schema": input_data.table_schema[:200] if input_data.table_schema else "",
                    "result": str(data)[:500],
                    "safety_score": safety_score
                }
            )
        # Fallback на infrastructure_context для обратной совместимости
        elif hasattr(self, '_application_context') and self._application_context:
            await self._application_context.infrastructure_context.event_bus.publish(
                event_type=f"sql_generation.{event_type}",
                data={
                    "user_question": input_data.natural_language_query,
                    "table_schema": input_data.table_schema[:200] if input_data.table_schema else "",
                    "result": str(data)[:500],
                    "safety_score": safety_score,
                    "timestamp": self._application_context.created_at.isoformat() if hasattr(self._application_context, 'created_at') else ""
                },
                source="SQLGenerationService",
                correlation_id=f"sql_gen_{hash(input_data.natural_language_query)}"
            )

    async def _publish_correction_event(self, event_type: str, data: Any, attempt: int, error_analysis: Any):
        """Публикация события коррекции"""
        if hasattr(self, '_event_bus') and self._event_bus is not None:
            await self._event_bus.publish(
                event_type=f"sql_correction.{event_type}",
                payload={
                    "attempt": attempt,
                    "error_type": error_analysis.error_type if hasattr(error_analysis, 'error_type') else "unknown",
                    "result": str(data)[:500]
                }
            )
        elif hasattr(self, '_application_context') and self._application_context:
            await self._application_context.infrastructure_context.event_bus.publish(
                event_type=f"sql_correction.{event_type}",
                data={
                    "attempt": attempt,
                    "error_type": error_analysis.error_type if hasattr(error_analysis, 'error_type') else "unknown",
                    "result": str(data)[:500],
                    "timestamp": self._application_context.created_at.isoformat() if hasattr(self._application_context, 'created_at') else ""
                },
                source="SQLGenerationService",
                correlation_id=f"sql_corr_{attempt}"
            )

    async def _publish_execution_event(self, event_type: str, result: DBQueryResult, attempt: int):
        """Публикация события выполнения"""
        # Используем внедрённый event_bus из BaseComponent
        if hasattr(self, '_event_bus') and self._event_bus is not None:
            await self._event_bus.publish(
                event_type=f"sql_execution.{event_type}",
                payload={
                    "attempt": attempt,
                    "rowcount": result.rowcount,
                    "success": result.success,
                    "execution_time": result.execution_time
                }
            )
        # Fallback на infrastructure_context для обратной совместимости
        elif hasattr(self, '_application_context') and self._application_context:
            await self._application_context.infrastructure_context.event_bus.publish(
                event_type=f"sql_execution.{event_type}",
                data={
                    "attempt": attempt,
                    "rowcount": result.rowcount,
                    "success": result.success,
                    "execution_time": result.execution_time,
                    "timestamp": self._application_context.created_at.isoformat() if hasattr(self._application_context, 'created_at') else ""
                },
                source="SQLGenerationService",
                correlation_id=f"sql_exec_{attempt}"
            )

    def _classify_db_error(self, error_message: Optional[str]) -> str:
        """Классификация ошибок БД для анализа"""
        if not error_message:
            return "unknown"
            
        error_lower = error_message.lower()
        if "syntax" in error_lower or "parse" in error_lower:
            return "syntax_error"
        elif "permission" in error_lower or "privilege" in error_lower:
            return "permission_error"
        elif "column" in error_lower or "relation" in error_lower:
            return "schema_error"
        elif "timeout" in error_lower:
            return "timeout_error"
        return "other_error"