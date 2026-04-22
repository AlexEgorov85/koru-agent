from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
from core.components.services.service import Service
from abc import ABC
from core.utils.async_utils import safe_async_call
import logging
from core.infrastructure.logging.event_types import LogEventType

log = logging.getLogger(__name__)


# Конкретная реализация ServiceOutput для SQLGenerationService
class SQLGenerationServiceOutput:
    def __init__(self, data: Dict[str, Any]):
        self.data = data
from core.components.services.sql_generation.error_analyzer import SQLErrorAnalyzer, ExecutionError
from core.components.services.sql_generation.correction import SQLCorrectionEngine
from core.models.sql_schemas import (
    SQLCorrectionInput, SQLGenerationInput, SQLGenerationOutput,
)
from core.application_context.application_context import ApplicationContext
from core.models.types.db_types import DBQueryResult


class SQLGenerationResult(BaseModel):
    """Результат генерации с метаданными для анализа ошибок и самоанализом"""
    sql: str = ""
    parameters: Dict[str, Any] = Field(default_factory=dict)
    reasoning: str = ""
    tables_used: List[str] = Field(default_factory=list)
    safety_score: float = 0.0
    generation_id: str = ""
    analysis_understanding: str = ""
    analysis_schema: str = ""
    analysis_strategy: str = ""
    analysis_validation: str = ""
    analysis_security: str = ""
    analysis_optimization: str = ""
    confidence_score: float = 0.0
    potential_issues: List[str] = Field(default_factory=list)
    final_check: str = ""

class SQLGenerationService(Service):
    """
    Централизованный сервис генерации и коррекции безопасных SQL-запросов.

    АРХИТЕКТУРНЫЕ ПРИНЦИПЫ:
    - Единая точка генерации для всех навыков
    - Обязательная параметризация всех запросов
    - Автоматическая коррекция на основе ошибок выполнения
    - Интеграция с существующими сервисами (таблицы, промпты)
    - Полная изоляция от инъекций через валидацию
    """

    @property
    def description(self) -> str:
        return "Сервис генерации и коррекции безопасных параметризованных SQL-запросов"

    def __init__(self, application_context: ApplicationContext = None, name: str = "sql_generation", component_config=None, executor=None):
        from core.config.component_config import ComponentConfig
        # NO FALLBACK: ComponentConfig должен быть передан извне
        # Если не передан - это ошибка конфигурации
        if component_config is None:
            raise ValueError(
                f"SQLGenerationService требует component_config! "
                f"Проверьте что компонент инициализируется через ComponentFactory"
            )

        super().__init__(
            name=name,
            component_config=component_config,
            executor=executor,
            application_context=application_context
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
        """Инициализация внутреннего состояния"""
        try:
            # Инициализация анализатора ошибок
            self.error_analyzer = SQLErrorAnalyzer(
                self.application_context,
                executor=self.executor
            )
            if not await self.error_analyzer.initialize():
                await self._publish_with_context(
                    event_type="sql_generation.init_failed",
                    data={"component": "SQLErrorAnalyzer"},
                    source="sql_generation"
                )
                return False

            # Инициализация движка коррекции
            self.correction_engine = SQLCorrectionEngine(
                self.application_context,
                executor=self.executor
            )

            return True
        except Exception as e:
            self._log_error(f"Ошибка инициализации SQLGenerationService: {str(e)}")
            return False

    async def _load_service_prompts(self):
        """Загрузка промптов, специфичных для сервиса генерации SQL"""
        # Промпты уже загружены в базовом классе через ComponentConfig
        # Используем кэшированные промпты из компонента
        pass

    def get_required_prompt_names(self):
        """Возвращает список имен промптов, необходимых для сервиса"""
        return ["sql_generation.generate_safe_query", "sql_generation.correct_query"]

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
        # Маршрутизация по имени capability
        cap_name = capability.name

        if "execute_with_auto_correction" in cap_name:
            # Генерация с автокоррекцией (вызов из sql_query_service)
            input_data = SQLGenerationInput(**parameters)
            result = safe_async_call(self.execute_with_auto_correction(input_data=input_data))
            return {"success": result.success, "sql": result.sql if hasattr(result, 'sql') else None, "error": result.error}
        else:
            # Обычная генерация SQL
            result = safe_async_call(self.generate_query(SQLGenerationInput(**parameters)))
            return result.model_dump()

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
            self._log_error(f"Ошибка перезапуска SQLGenerationService: {str(e)}")
            return False

    async def shutdown(self) -> None:
        """Завершение работы сервиса"""
        # Здесь можно освободить ресурсы, закрыть соединения и т.д.
        # В данном случае у нас нет внешних ресурсов для освобождения

    async def execute_with_auto_correction(
        self,
        input_data: SQLGenerationInput,
        context: Optional[Any] = None
    ) -> 'DBQueryResult':
        """
        Генерация SQL с автоматической коррекцией.

        Вызывается из sql_query_service через executor.
        """
        from core.models.types.db_types import DBQueryResult

        try:
            # Генерируем SQL
            result = await self.generate_query(input_data=input_data, context=context)

            if not result.sql:
                return DBQueryResult(
                    success=False,
                    rows=[],
                    columns=[],
                    rowcount=0,
                    error="SQL не сгенерирован"
                )

            return DBQueryResult(
                success=True,
                rows=[],
                columns=[],
                rowcount=0,
                error=None
            )

        except Exception as e:
            from core.models.types.db_types import DBQueryResult
            return DBQueryResult(
                success=False,
                rows=[],
                columns=[],
                rowcount=0,
                error=f"Ошибка генерации SQL: {str(e)}"
            )

    async def generate_query(
        self,
        natural_language_query: str = None,
        table_schema: str = None,
        available_scripts: str = None,
        available_tables: str = None,
        hints: str = None,
        input_data: SQLGenerationInput = None,
        context: Optional[Any] = None,
        **kwargs
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
            available_scripts = available_scripts or getattr(input_data, 'available_scripts', None)
            available_tables = available_tables or getattr(input_data, 'available_tables', '')
            hints = hints or getattr(input_data, 'hints', None)
        elif natural_language_query is None or table_schema is None:
            raise ValueError("generate_query requires either natural_language_query and table_schema, or input_data")

        # 1. Получение метаданных таблиц
        # table_metadata = await self._get_table_metadata(input_data.tables)

        # 2. Формирование промпта через централизованный сервис
        hints_value = hints if hints is not None else ""
        prompt_vars = {
            "natural_language_query": natural_language_query,
            "table_schema": table_schema if isinstance(table_schema, str) else str(table_schema),
            "available_scripts": available_scripts or "Скрипты не доступны",
            "available_tables": available_tables or "",
            "allowed_operations": ", ".join(self.allowed_operations),
            "max_rows": self.max_result_rows,
            "hints": hints_value
        }

        # Используем кэшированный промпт из компонента
        prompt_key = "sql_generation.generate_query"
        prompt_obj = self.get_prompt(prompt_key)
        
        # ПРОВЕРКА: Промпт ДОЛЖЕН быть загружен — без fallback!
        if not prompt_obj or not prompt_obj.content:
            raise ValueError(f"Промпт '{prompt_key}' не загружен! Проверьте что промпт указан в ComponentConfig")

        prompt = prompt_obj.content

        # Заменяем переменные в кэшированном промпте
        for var_name, var_value in prompt_vars.items():
            placeholder = f"{{{var_name}}}"  # Формат {variable_name}
            prompt = prompt.replace(placeholder, str(var_value))

        # Логирование для отладки
        self._log_debug(f"SQL Generation prompt length: {len(prompt)}")
        self._log_debug(f"SQL Generation prompt: {prompt}.")

        try:
            # 4. ВЫЗОВ LLM ЧЕРЕЗ EXECUTOR
            from core.components.action_executor import ExecutionContext
            exec_context = ExecutionContext()
            output = None  # Будет заполнен structured output или fallback

            try:
                llm_result = await self.executor.execute_action(
                    action_name="llm.generate_structured",
                    parameters={
                        "prompt": prompt,
                        "system_prompt": """Ты — эксперт по безопасной генерации SQL-запросов.
Перед генерацией SQL ОБЯЗАТЕЛЬНО ответь на 6 аналитических вопросов.
Верни СТРОГО JSON объект без дополнительного текста.
СХЕМА: {\"analysis_understanding\": str, \"analysis_schema\": str, \"analysis_strategy\": str, \"analysis_validation\": str, \"analysis_security\": str, \"analysis_optimization\": str, \"generated_sql\": str, \"confidence_score\": float, \"potential_issues\": list, \"final_check\": str}""",
                        "temperature": 0.2,
                        "max_tokens": 3000,
                        "structured_output": {
                            "output_model": "SQLGenerationOutput",
                            "schema_def": SQLGenerationOutput.model_json_schema(),
                            "max_retries": 3,
                            "strict_mode": False
                        }
                    },
                    context=exec_context
                )
            except Exception as llm_exc:
                raise ValueError(f"LLM generate_structured failed: {llm_exc}")

            from core.models.data.execution import ExecutionStatus
            if llm_result.status != ExecutionStatus.COMPLETED or not llm_result.data:
                errors = llm_result.error if hasattr(llm_result, 'error') else 'unknown error'

                # Логируем ошибку structured output
                self._log_warning(
                    f"Structured output не удался: {errors}. Пробуем fallback..."
                )

                # FALLBACK: пробуем обычный llm.generate с ручным парсингом JSON
                llm_result2 = await self.executor.execute_action(
                    action_name="llm.generate",
                    parameters={
                        "prompt": prompt,
                        "system_prompt": "Ты — SQL генератор. Верни СТРОГО JSON объект без дополнительного текста.",
                        "temperature": 0.2,
                        "max_tokens": 2000,
                    },
                    context=exec_context
                )

                if llm_result2.status != ExecutionStatus.COMPLETED or not llm_result2.data:
                    raise ValueError(f"SQL generation failed (both structured and fallback): {errors}")

                # Парсим JSON через JsonParsingService
                if isinstance(llm_result2.data, dict):
                    raw_text = llm_result2.data.get('content', '') or llm_result2.data.get('text', '') or llm_result2.data.get('response', '')
                else:
                    raw_text = llm_result2.data if isinstance(llm_result2.data, str) else str(llm_result2.data)

                # Логируем сырой ответ
                self._log_debug(f"Fallback LLM response: {raw_text}")

                if not raw_text or len(raw_text.strip()) < 10:
                    raise ValueError(
                        f"LLM returned empty or too short response for SQL generation. "
                        f"Response length: {len(raw_text.strip()) if raw_text else 0} chars. "
                        f"Проверьте что модель загружена корректно и промпт содержит схему БД."
                    )

                # Используем JsonParsingService для извлечения и парсинга JSON
                parse_result = await self.executor.execute_action(
                    action_name="json_parsing.parse_json",
                    parameters={"raw": raw_text},
                    context=ExecutionContext()
                )

                if parse_result and parse_result.data and parse_result.data.get("status") == "success":
                    output = parse_result.data.get("parsed_data", {})
                    self._log_info(f"Fallback JSON распарсен через JsonParsingService")
                else:
                    error_msg = parse_result.data.get("error_message", "Unknown error") if parse_result and parse_result.data else "Unknown error"
                    raise ValueError(
                        f"Could not parse JSON from LLM response: {error_msg}. "
                        f"Response length: {len(raw_text)} chars. "
                        f"First 300 chars: {raw_text[:300]}"
                    )

            # Извлекаем parsed_content из результата
            result_data = llm_result.data

            # Проверяем нужно ли использовать fallback (llm_result.failed но есть output из fallback)
            use_fallback_output = isinstance(output, dict) and 'generated_sql' in output

            if use_fallback_output:
                pass  # Fallback уже заполнил output
            elif hasattr(result_data, 'parsed_content'):
                output = result_data.parsed_content
            elif isinstance(result_data, dict) and 'parsed_content' in result_data:
                output = result_data['parsed_content']
            else:
                output = result_data

            # Валидация SQL через безопасный метод
            generated_sql = getattr(output, 'generated_sql', None) or (output.get('generated_sql') if isinstance(output, dict) else None)

            self._log_debug(f"Extracted SQL: {generated_sql}")

            validated = await self._validate_sql_safely(generated_sql, {})

            # Проверяем что запрос валиден
            if not validated.is_valid or not validated.sql:
                error_msg = "; ".join(validated.validation_errors) if hasattr(validated, 'validation_errors') else "Validation failed"
                raise RuntimeError(f"SQL validation failed: {error_msg}")

            # Извлекаем поля самоанализа из результата
            if isinstance(output, dict):
                analysis_understanding = output.get('analysis_understanding', '')
                analysis_schema = output.get('analysis_schema', '')
                analysis_strategy = output.get('analysis_strategy', '')
                analysis_validation = output.get('analysis_validation', '')
                analysis_security = output.get('analysis_security', '')
                analysis_optimization = output.get('analysis_optimization', '')
                confidence_score = output.get('confidence_score', 0.0)
                potential_issues = output.get('potential_issues', [])
                final_check = output.get('final_check', '')
            else:
                analysis_understanding = getattr(output, 'analysis_understanding', '')
                analysis_schema = getattr(output, 'analysis_schema', '')
                analysis_strategy = getattr(output, 'analysis_strategy', '')
                analysis_validation = getattr(output, 'analysis_validation', '')
                analysis_security = getattr(output, 'analysis_security', '')
                analysis_optimization = getattr(output, 'analysis_optimization', '')
                confidence_score = getattr(output, 'confidence_score', 0.0)
                potential_issues = getattr(output, 'potential_issues', [])
                final_check = getattr(output, 'final_check', '')

            # Логируем поля самоанализа
            log.info(f"SQL Generation Analysis: understanding={analysis_understanding[:50]}...", extra={"event_type": LogEventType.LLM_RESPONSE})
            log.info(f"SQL confidence_score={confidence_score}, potential_issues={len(potential_issues)}", extra={"event_type": LogEventType.LLM_RESPONSE})

            # 5. Формирование результата
            result = SQLGenerationResult(
                sql=validated.sql,
                parameters=validated.parameters,
                reasoning=analysis_strategy,
                tables_used=[],
                safety_score=validated.safety_score,
                generation_id=f"gen_{hash(natural_language_query)}",
                analysis_understanding=analysis_understanding,
                analysis_schema=analysis_schema,
                analysis_strategy=analysis_strategy,
                analysis_validation=analysis_validation,
                analysis_security=analysis_security,
                analysis_optimization=analysis_optimization,
                confidence_score=confidence_score,
                potential_issues=potential_issues,
                final_check=final_check
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
                self._log_warning(
                    f"SQL generation attempt {attempt + 1} failed: {str(e)}"
                )

                if self.correction_engine and attempt < max_correction_attempts - 1:
                    try:
                        from core.components.services.sql_generation.error_analyzer import ExecutionError

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

                        self._log_info(f"Applied correction: {corrected.corrected_sql}")

                    except Exception as correction_error:
                        self._log_warning(f"Correction failed: {str(correction_error)}")

        from core.errors.exceptions import SQLValidationError
        raise SQLValidationError(
            f"Не удалось сгенерировать корректный SQL после {max_correction_attempts} попыток. "
            f"Последняя ошибка: {str(last_error)}",
            sql=""
        )

    # Вспомогательные методы (приватные)
    async def _get_table_metadata(self, table_names: List[str]) -> Dict[str, Any]:
        """Получение метаданных таблиц через executor"""
        from core.components.action_executor import ExecutionContext
        from core.models.data.execution import ExecutionStatus

        metadata_list = []
        exec_context = ExecutionContext()

        for table_name in table_names:
            parts = table_name.split(".")
            schema_name = parts[0] if len(parts) > 1 else "public"
            actual_table_name = parts[-1]

            result = await self.executor.execute_action(
                action_name="table_description_service.get_table",
                parameters={
                    "schema_name": schema_name,
                    "table_name": actual_table_name,
                    "context": None,
                    "step_number": 0
                },
                context=exec_context
            )

            if result.status == ExecutionStatus.COMPLETED and result.data:
                metadata_list.append(result.data)
            else:
                raise RuntimeError(f"Не удалось получить метаданные таблицы {table_name}: {result.error}")

        return {"tables": metadata_list}

    async def _publish_generation_event(self, event_type: str, data: Any, input_data: SQLGenerationInput, safety_score: float = 0.0):
        """Публикация события генерации через EventBus"""
        # Используем внедрённый event_bus из BaseComponent
        if hasattr(self, '_event_bus') and self._event_bus is not None:
            await self._publish_with_context(
                event_type=f"sql_generation.{event_type}",
                data={
                    "user_question": input_data.natural_language_query,
                    "table_schema": input_data.table_schema if input_data.table_schema else "",
                    "result": str(data),
                    "safety_score": safety_score
                }
            )
        # Fallback на infrastructure_context для обратной совместимости
        elif hasattr(self, '_application_context') and self._application_context:
            await self._application_context.infrastructure_context.event_bus.publish(
                event_type=f"sql_generation.{event_type}",
                data={
                    "user_question": input_data.natural_language_query,
                    "table_schema": input_data.table_schema if input_data.table_schema else "",
                    "result": str(data),
                    "safety_score": safety_score,
                    "timestamp": self._application_context.created_at.isoformat() if hasattr(self._application_context, 'created_at') else ""
                },
                source="SQLGenerationService",
                correlation_id=f"sql_gen_{hash(input_data.natural_language_query)}"
            )

    async def _publish_correction_event(self, event_type: str, data: Any, attempt: int, error_analysis: Any):
        """Публикация события коррекции"""
        if hasattr(self, '_event_bus') and self._event_bus is not None:
            await self._publish_with_context(
                event_type=f"sql_correction.{event_type}",
                data={
                    "attempt": attempt,
                    "error_type": error_analysis.error_type if hasattr(error_analysis, 'error_type') else "unknown",
                    "result": str(data)
                }
            )
        elif hasattr(self, '_application_context') and self._application_context:
            await self._application_context.infrastructure_context.event_bus.publish(
                event_type=f"sql_correction.{event_type}",
                data={
                    "attempt": attempt,
                    "error_type": error_analysis.error_type if hasattr(error_analysis, 'error_type') else "unknown",
                    "result": str(data),
                    "timestamp": self._application_context.created_at.isoformat() if hasattr(self._application_context, 'created_at') else ""
                },
                source="SQLGenerationService",
                correlation_id=f"sql_corr_{attempt}"
            )

    async def _publish_execution_event(self, event_type: str, result: DBQueryResult, attempt: int):
        """Публикация события выполнения"""
        # Используем внедрённый event_bus из BaseComponent
        if hasattr(self, '_event_bus') and self._event_bus is not None:
            await self._publish_with_context(
                event_type=f"sql_execution.{event_type}",
                data={
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

    async def _validate_sql_safely(self, sql: str, parameters: Dict[str, Any]) -> 'ValidatedSQL':
        """
        Безопасная обёртка для валидации SQL через SQLValidatorService.

        Вызов осуществляется через executor согласно архитектурным правилам.
        """
        from core.components.services.sql_validator.service import ValidatedSQL
        from core.components.action_executor import ExecutionContext
        from core.models.data.execution import ExecutionStatus

        exec_context = ExecutionContext()

        result = await self.executor.execute_action(
            action_name="sql_validator_service.validate_query",
            parameters={
                "sql_query": sql,
                "parameters": parameters
            },
            context=exec_context
        )

        if result.status == ExecutionStatus.COMPLETED and result.data:
            return result.data

        # Fallback при ошибке валидации
        return ValidatedSQL(
            sql=sql,
            parameters=parameters,
            is_valid=False,
            validation_errors=[result.error] if result.error else ["Validation failed"],
            safety_score=0.0
        )