from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from core.infrastructure.service.base_service import BaseService, ServiceInput, ServiceOutput as BaseServiceOutput
from abc import ABC


# Конкретная реализация ServiceOutput для SQLGenerationService
class ServiceOutput(BaseServiceOutput):
    def __init__(self, data: Dict[str, Any]):
        self.data = data
from core.infrastructure.service.sql_generation.error_analyzer import SQLErrorAnalyzer, ExecutionError
from core.infrastructure.service.sql_generation.correction import SQLCorrectionEngine
from core.infrastructure.service.sql_generation.schema import (
    SQLGenerationInput, SQLGenerationOutput,
    SQLCorrectionInput, SQLCorrectionOutput
)
from core.system_context.base_system_contex import BaseSystemContext
from models.db_types import DBQueryResult
from models.llm_types import LLMRequest, StructuredOutputConfig
import logging

logger = logging.getLogger(__name__)

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
    
    @property
    def description(self) -> str:
        return "Сервис генерации и коррекции безопасных параметризованных SQL-запросов"

    def __init__(self, system_context: BaseSystemContext, name: str = None):
        super().__init__(system_context, name or "sql_generation_service")

        # Зависимости (инверсия через конструктор)
        # Используем новый централизованный SQLValidatorService
        self.validator_service = system_context.get_resource("sql_validator_service")
        self.error_analyzer = SQLErrorAnalyzer(system_context)
        self.correction_engine = SQLCorrectionEngine(system_context)
        # Заметка: для получения сервиса нужно использовать await, поэтому сохраняем системный контекст
        self.system_context = system_context
        self.prompt_service = system_context.get_resource("prompt_service")

        # Конфигурация безопасности
        self.max_correction_attempts = 3
        self.allowed_operations = ["SELECT", "WITH"]  # Запрещаем все кроме чтения
        self.max_result_rows = 1000

    async def initialize(self) -> bool:
        """Инициализация зависимостей"""
        # Проверка наличия критических сервисов
        table_service = await self.system_context.get_service("table_description_service")
        if not table_service:
            self.logger.error("table_description_service не зарегистрирован")
            return False
            
        if not self.prompt_service:
            self.logger.error("PromptService не зарегистрирован")
            return False
            
        self.logger.info("SQLGenerationService успешно инициализирован")
        return True

    async def execute(self, input_data: ServiceInput) -> ServiceOutput:
        """
        Выполнение сервиса - в данном случае делегирует генерацию или коррекцию.
        
        ARGS:
        - input_data: ServiceInput - должен быть экземпляром SQLGenerationInput или SQLCorrectionInput
        
        RETURNS:
        - ServiceOutput: результат выполнения
        """
        # Проверяем тип входных данных и вызываем соответствующий метод
        if isinstance(input_data, SQLGenerationInput):
            result = await self.generate_query(input_data)
            # Преобразуем результат в подходящий ServiceOutput
            # Для этого создадим временный класс или используем словарь
            from dataclasses import asdict
            return ServiceOutput(asdict(result))
        elif isinstance(input_data, SQLCorrectionInput):
            # Для коррекции нужно больше информации
            # Этот метод требует дополнительные параметры, которые не передаются через input_data
            raise NotImplementedError("Direct execution with SQLCorrectionInput not implemented")
        else:
            raise ValueError(f"Unsupported input type: {type(input_data)}")

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
            self.logger.error(f"Ошибка перезапуска SQLGenerationService: {str(e)}")
            return False

    async def shutdown(self) -> None:
        """Завершение работы сервиса"""
        self.logger.info("Завершение работы SQLGenerationService")
        # Здесь можно освободить ресурсы, закрыть соединения и т.д.
        # В данном случае у нас нет внешних ресурсов для освобождения

    async def generate_query(
        self, 
        input_data: SQLGenerationInput,
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
        # 1. Получение метаданных таблиц
        table_metadata = await self._get_table_metadata(input_data.tables)
        
        # 2. Формирование промпта через централизованный сервис
        prompt_vars = {
            "user_question": input_data.user_question,
            "table_descriptions": self._format_table_metadata(table_metadata),
            "allowed_operations": ", ".join(self.allowed_operations),
            "max_rows": self.max_result_rows
        }
        
        prompt = await self.prompt_service.render(
            capability_name="sql_generation.generate_safe_query",
            variables=prompt_vars
        )
        
        try:
            # 3. Создание ТИПИЗИРОВАННОГО запроса с указанием выходной модели
            request = LLMRequest(
                prompt=input_data.user_question,
                system_prompt=prompt,
                temperature=0.3,
                max_tokens=500,
                structured_output=StructuredOutputConfig(
                    output_model="SQLGenerationOutput",  # Имя модели из реестра
                    schema_def=SQLGenerationOutput.model_json_schema(),
                    max_retries=3,
                    strict_mode=True
                ),
                correlation_id=f"sql_gen_{hash(input_data.user_question)}",
                capability_name="sql_generation.generate_safe_query"
            )
            
            # 4. ЕДИНСТВЕННЫЙ ВЫЗОВ — получаем ГАРАНТИРОВАННО валидную модель
            # Типизация на уровне компиляции: ответ будет StructuredLLMResponse[SQLGenerationOutput]
            response = await self.system_context.call_llm(request)
            
            # 5. Валидация сгенерированного SQL-запроса через централизованный SQLValidatorService
            # Типизация гарантирует, что parsed_content — валидный экземпляр SQLGenerationOutput
            output = response.parsed_content
            
            # Проверяем, что валидатор доступен
            if not self.validator_service:
                raise RuntimeError("SQLValidatorService не зарегистрирован")
                
            validated = await self.validator_service.validate_query(output.sql, output.parameters)

            # 5. Формирование результата
            result = SQLGenerationResult(
                sql=validated.sql,
                parameters=validated.parameters,
                reasoning=output.reasoning,
                tables_used=output.tables_used,
                safety_score=validated.safety_score,
                generation_id=f"gen_{hash(input_data.user_question)}"
            )

            await self._publish_generation_event("generation_success", result.sql, input_data, result.safety_score)
            return result
            
        except Exception as e:
            await self._publish_generation_event("generation_failed", str(e), input_data)
            raise ValueError(f"Ошибка валидации сгенерированного SQL: {str(e)}")

    async def correct_query(
        self,
        original_query: str,
        parameters: Dict[str, Any],
        execution_error: ExecutionError,
        context: Optional[Any] = None,
        attempt: int = 1
    ) -> Optional[SQLGenerationResult]:
        """
        Автоматическая коррекция запроса на основе ошибки выполнения.
        
        СТРАТЕГИЯ КОРРЕКЦИИ:
        1. Анализ типа ошибки (синтаксис, семантика, права доступа)
        2. Выбор стратегии исправления:
           - Синтаксис → генерация нового запроса с примером правильного синтаксиса
           - Семантика → уточнение метаданных таблиц + повторная генерация
           - Права → ограничение запроса до разрешенных операций
        3. Ограничение попыток (защита от зацикливания)
        """
        if attempt > self.max_correction_attempts:
            self.logger.warning(f"Достигнут лимит попыток коррекции ({self.max_correction_attempts})")
            return None
            
        # 1. Анализ ошибки
        error_analysis = await self.error_analyzer.analyze(execution_error)
        
        # 2. Формирование промпта для коррекции
        correction_input = SQLCorrectionInput(
            original_query=original_query,
            error_message=execution_error.message,
            error_type=error_analysis.error_type,
            suggested_fix=error_analysis.suggested_fix,
            tables=error_analysis.tables_involved,
            context=str(context) if context else ""
        )
        
        prompt_vars = {
            "original_query": correction_input.original_query,
            "error_message": correction_input.error_message,
            "error_type": correction_input.error_type,
            "suggested_fix": correction_input.suggested_fix,
            "allowed_operations": ", ".join(self.allowed_operations)
        }
        
        prompt = await self.prompt_service.render(
            capability_name="sql_generation.correct_query",
            variables=prompt_vars
        )
        
        try:
            # 3. Создание ТИПИЗИРОВАННОГО запроса с указанием выходной модели для коррекции
            request = LLMRequest(
                prompt=f"Исправь ошибку: {correction_input.error_message}",
                system_prompt=prompt,
                temperature=0.2,  # Более детерминированная генерация
                max_tokens=400,
                structured_output=StructuredOutputConfig(
                    output_model="SQLCorrectionOutput",  # Имя модели из реестра
                    schema_def=SQLCorrectionOutput.model_json_schema(),
                    max_retries=2,  # Меньше попыток для коррекции
                    strict_mode=True
                ),
                correlation_id=f"sql_corr_{hash(correction_input.original_query)}",
                capability_name="sql_generation.correct_query"
            )
            
            # 4. ЕДИНСТВЕННЫЙ ВЫЗОВ — получаем ГАРАНТИРОВАННО валидную модель
            response = await self.system_context.call_llm(request)
            
            # 5. Валидация скорректированного SQL-запроса через централизованный SQLValidatorService
            correction_output = response.parsed_content
            
            # Проверяем, что валидатор доступен
            if not self.validator_service:
                raise RuntimeError("SQLValidatorService не зарегистрирован")
                
            validated = await self.validator_service.validate_query(
                correction_output.corrected_sql,
                parameters  # Сохраняем оригинальные параметры
            )

            result = SQLGenerationResult(
                sql=validated.sql,
                parameters=parameters,
                reasoning=correction_output.reasoning,
                tables_used=correction_output.tables_used or [],
                safety_score=validated.safety_score,
                generation_id=f"corr_{attempt}_{hash(original_query)}"
            )

            await self._publish_correction_event("correction_success", result, attempt, error_analysis)
            return result

        except Exception as e:
            self.logger.warning(f"Попытка коррекции #{attempt} не удалась: {str(e)}")
            await self._publish_correction_event("correction_failed", str(e), attempt, error_analysis)

            # Рекурсивная попытка с увеличенным номером
            return await self.correct_query(
                original_query,
                parameters,
                execution_error,
                context,
                attempt + 1
            )

    async def execute_with_auto_correction(
        self,
        generation_input: SQLGenerationInput,
        context: Optional[Any] = None,
        max_corrections: int = 3
    ) -> DBQueryResult:
        """
        Единый метод: генерация → выполнение → автоматическая коррекция при ошибках.
        
        ИСПОЛЬЗОВАНИЕ В НАВЫКАХ:
        ```python
        result = await sql_service.execute_with_auto_correction(
            SQLGenerationInput(
                user_question="Какие книги написал Толстой?",
                tables=["books", "authors"]
            ),
            context=session_context
        )
        ```
        """
        # 1. Генерация запроса
        generation_result = await self.generate_query(generation_input, context)
        
        # 2. Выполнение с попытками коррекции
        for attempt in range(max_corrections + 1):
            try:
                # Выполнение через внутренний безопасный интерфейс (параметризованный запрос!)
                # Используем прямое выполнение, так как запрос уже прошел валидацию в SQLValidatorService
                result = await self.system_context._execute_raw_sql_query(
                    query=generation_result.sql,
                    params=generation_result.parameters
                )
                
                if result.success:
                    await self._publish_execution_event("execution_success", result, attempt)
                    return result
                    
                # Анализ ошибки для коррекции
                execution_error = ExecutionError(
                    message=result.error or "Неизвестная ошибка выполнения",
                    query=generation_result.sql,
                    parameters=generation_result.parameters,
                    db_error_type=self._classify_db_error(result.error)
                )
                
            except Exception as e:
                execution_error = ExecutionError(
                    message=str(e),
                    query=generation_result.sql,
                    parameters=generation_result.parameters,
                    db_error_type="unknown"
                )
            
            # 3. Коррекция (если есть попытки)
            if attempt < max_corrections:
                self.logger.info(f"Попытка коррекции #{attempt + 1} после ошибки: {execution_error.message[:100]}")
                corrected = await self.correct_query(
                    generation_result.sql,
                    generation_result.parameters,
                    execution_error,
                    context,
                    attempt + 1
                )
                
                if corrected:
                    generation_result = corrected
                    continue
                else:
                    self.logger.error("Все попытки коррекции исчерпаны")
                    break
            else:
                self.logger.error(f"Достигнут лимит коррекций ({max_corrections})")
                break
        
        # Возврат ошибочного результата с метаданными для отладки
        return DBQueryResult(
            success=False,
            rows=[],
            rowcount=0,
            columns=[],
            error=f"Не удалось выполнить запрос после {max_corrections} попыток коррекции",
            execution_time=0.0,
            metadata={
                "original_query": generation_result.sql,
                "last_error": execution_error.message if 'execution_error' in locals() else "unknown",
                "correction_attempts": attempt
            }
        )

    # Вспомогательные методы (приватные)
    async def _get_table_metadata(self, table_names: List[str]) -> Dict[str, Any]:
        """Получение метаданных таблиц через существующий сервис"""
        # Используем уже зарегистрированный TableDescriptionService
        table_service = await self.system_context.get_service("table_description_service")
        if not table_service:
            raise RuntimeError("table_description_service не зарегистрирован в системном контексте")
            
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
        await self.system_context.event_bus.publish(
            event_type=f"sql_generation.{event_type}",
            data={
                "user_question": input_data.user_question,
                "tables": input_data.tables,
                "result": str(data)[:500],  # Ограничиваем для логов
                "safety_score": safety_score,
                "timestamp": self.system_context.created_at.isoformat() if hasattr(self.system_context, 'created_at') else ""
            },
            source="SQLGenerationService",
            correlation_id=f"sql_gen_{hash(input_data.user_question)}"
        )

    async def _publish_correction_event(self, event_type: str, data: Any, attempt: int, error_analysis: Any):
        """Публикация события коррекции"""
        await self.system_context.event_bus.publish(
            event_type=f"sql_correction.{event_type}",
            data={
                "attempt": attempt,
                "error_type": error_analysis.error_type if hasattr(error_analysis, 'error_type') else "unknown",
                "result": str(data)[:500],
                "timestamp": self.system_context.created_at.isoformat() if hasattr(self.system_context, 'created_at') else ""
            },
            source="SQLGenerationService",
            correlation_id=f"sql_corr_{attempt}"
        )

    async def _publish_execution_event(self, event_type: str, result: DBQueryResult, attempt: int):
        """Публикация события выполнения"""
        await self.system_context.event_bus.publish(
            event_type=f"sql_execution.{event_type}",
            data={
                "attempt": attempt,
                "rowcount": result.rowcount,
                "success": result.success,
                "execution_time": result.execution_time,
                "timestamp": self.system_context.created_at.isoformat() if hasattr(self.system_context, 'created_at') else ""
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