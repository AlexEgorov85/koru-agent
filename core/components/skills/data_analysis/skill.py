"""
Навык анализа сырых данных по шагу.

Архитектурные гарантии:
- Использует BaseComponent для изолированных кэшей
- Доступ к инструментам только через ActionExecutor
- Валидация входных/выходных данных через контракты
- Поддержка профилей prod/sandbox через AppConfig
"""

import asyncio
import time
import json
import re
from typing import List, Dict, Any, Optional
from pathlib import Path
from pydantic import BaseModel

from core.components.skills.skill import Skill
from core.models.data.capability import Capability
from core.models.data.execution import ExecutionResult, ExecutionStatus
from core.infrastructure.logging.event_types import LogEventType


class DataAnalysisSkill(Skill):
    """Навык для анализа сырых данных по шагу и ответа на вопросы."""

    @property
    def description(self) -> str:
        return "Навык анализа сырых данных по шагу и ответа на заданный вопрос"

    # Все вызовы инструментов выполняются через executor

    name: str = "data_analysis"
    
    def __init__(
        self,
        name: str,
        component_config: Any,
        executor: Any,
        application_context: Any = None,
    ):
        super().__init__(
            name=name,
            component_config=component_config,
            executor=executor,
            application_context=application_context
        )

    def get_capabilities(self) -> List[Capability]:
        """Возвращает список capability навыка."""
        return [
            Capability(
                name="data_analysis.analyze_step_data",
                description="Анализ сырых данных по шагу и ответ на заданный вопрос с поддержкой больших данных",
                skill_name=self.name,
                supported_strategies=["react", "planning"],
                visiable=True,
                meta={
                    "supports_chunking": True,
                    "aggregation_methods": ["summary", "statistical", "extractive", "generative"]
                }
            )
        ]

    async def initialize(self) -> bool:
        """Инициализация навыка с предзагрузкой ресурсов."""
        success = await super().initialize()
        if not success:
            return False

        # Проверяем наличие необходимых ресурсов
        if "data_analysis.analyze_step_data" not in self.prompts:
            self._log_warning("Промпт для data_analysis.analyze_step_data не загружен", event_type=LogEventType.WARNING)

        if "data_analysis.analyze_step_data" not in self.input_contracts:
            self._log_warning("Входная схема для data_analysis.analyze_step_data не загружена", event_type=LogEventType.WARNING)

        if "data_analysis.analyze_step_data" not in self.output_contracts:
            self._log_warning("Выходная схема для data_analysis.analyze_step_data не загружена", event_type=LogEventType.WARNING)

        return True

    def _get_event_type_for_success(self) -> str:
        """Возвращает тип события для успешного выполнения навыка анализа данных."""
        return "skill.data_analysis.executed"

    async def _execute_impl(
        self,
        capability: Capability,
        parameters: Dict[str, Any],
        execution_context: Any
    ) -> Dict[str, Any]:
        """
        Реализация бизнес-логики анализа данных (АСИНХРОННАЯ).

        ВАЖНО: Валидация входа/выхода и метрики выполняются в BaseComponent.execute()
        Здесь только бизнес-логика.

        ВОЗВРАЩАЕТ:
            - Dict[str, Any]: Данные результата (не ExecutionResult!)
        """
        # Маппинг capability на методы реализации
        capability_handlers = {
            "data_analysis.analyze_step_data": self._analyze_step_data
        }
        
        if capability.name not in capability_handlers:
            raise ValueError(f"Навык не поддерживает capability: {capability.name}")
        
        # Вызываем обработчик capability
        return await capability_handlers[capability.name](parameters, execution_context)

    async def _analyze_step_data(self, params: Dict[str, Any], execution_context: Any) -> ExecutionResult:
        """
        Основная логика анализа данных шага.

        АРХИТЕКТУРА:
        1. Берём сырые данные из SessionContext (по step_id)
        2. Fallback: parameters.data_source если в контексте нет
        3. Анализируем через LLM

        Args:
            params: Параметры анализа
            execution_context: ExecutionContext с SessionContext

        Returns:
            Словарь с результатом анализа
        """
        start_time = time.time()

        # 1. Валидация входных параметров
        from pydantic import BaseModel
        if isinstance(params, BaseModel):
            self._log_debug(f"Получены типизированные параметры: {type(params).__name__}", event_type=LogEventType.DEBUG)
        else:
            input_schema = self.get_input_contract("data_analysis.analyze_step_data")
            if input_schema:
                try:
                    validated_params = input_schema.model_validate(params)
                    params = validated_params
                except Exception as e:
                    self._log_error(f"Ошибка валидации параметров: {e}", event_type=LogEventType.ERROR)
                    from core.errors.exceptions import ValidationError
                    raise ValidationError(f"Неверные параметры: {str(e)}")

        step_id = params.step_id if isinstance(params, BaseModel) else params.get("step_id")
        question = params.question if isinstance(params, BaseModel) else params.get("question")
        analysis_config = params.analysis_config if isinstance(params, BaseModel) else params.get("analysis_config", {})

        if isinstance(analysis_config, BaseModel):
            analysis_config = analysis_config.model_dump()

        # 2. Загрузка данных: ПРИОРИТЕТ — SessionContext, fallback — parameters
        raw_data = None
        data_metadata = {}

        # 2a. Пробуем взять данные из SessionContext
        session_ctx = getattr(execution_context, 'session_context', None)
        if session_ctx and step_id:
            raw_data, data_metadata = self._load_data_from_context(step_id, session_ctx)

        # 2b. Fallback: parameters.data_source
        if not raw_data:
            data_source = params.data_source if isinstance(params, BaseModel) else params.get("data_source", {})
            if isinstance(data_source, BaseModel):
                data_source = data_source.model_dump()

            if data_source:
                try:
                    raw_data, data_metadata = await self._load_data(
                        data_source=data_source,
                        config=analysis_config
                    )
                except Exception as e:
                    self._log_error(f"Ошибка загрузки данных: {e}", event_type=LogEventType.ERROR)
                    source_type = data_source.get("type") if isinstance(data_source, dict) else getattr(data_source, 'type', 'unknown')
                    from core.errors.exceptions import DataError
                    raise DataError(
                        f"Не удалось загрузить данные: {str(e)}. "
                        f"Проверьте что источник данных доступен и содержит данные.",
                        source=source_type
                    )

        # 2c. Если данных нет вообще
        if not raw_data:
            from core.errors.exceptions import DataError
            raise DataError(
                f"Нет данных для анализа. "
                f"Убедитесь что шаг {step_id} содержит observation с сырыми данными "
                f"или передайте data_source в parameters.",
                source="none"
            )

        # 3. Чанкинг при необходимости
        chunks = await self._chunk_data_if_needed(
            data=raw_data,
            config=analysis_config,
            metadata=data_metadata
        )

        # 4. Подготовка промпта
        prompt_vars = {
            "step_id": step_id,
            "question": question,
            "aggregation_method": analysis_config.get("aggregation_method", "summary")
        }

        if chunks:
            prompt_vars["chunks"] = chunks
        else:
            prompt_vars["raw_data"] = raw_data

        # 5. Получение промпта
        prompt_obj = self.get_prompt("data_analysis.analyze_step_data")
        if not prompt_obj:
            from core.errors.exceptions import PromptNotFoundError
            raise PromptNotFoundError(
                prompt="data_analysis.analyze_step_data",
                message="Промпт для анализа данных не найден. Проверьте что промпт загружен в репозиторий."
            )

        rendered_prompt = self._render_prompt(prompt_obj.content, prompt_vars)

        # 6. Получаем схему выхода для structured output
        output_schema = self.get_output_contract("data_analysis.analyze_step_data")

        # 7. Вызов LLM С STRUCTURED OUTPUT через executor
        try:
            llm_result = await self.executor.execute_action(
                action_name="llm.generate_structured",
                parameters={
                    "prompt": rendered_prompt,
                    "structured_output": {
                        "output_model": "data_analysis.analyze_step_data.output",
                        "schema_def": output_schema if output_schema else {},
                        "max_retries": 3,
                        "strict_mode": True
                    },
                    "temperature": 0.1,
                    "max_tokens": analysis_config.get("max_response_tokens", 2000)
                },
                context=execution_context
            )

            # Проверка на ошибку
            from core.models.data.execution import ExecutionStatus
            if llm_result.status != ExecutionStatus.COMPLETED:
                # ❌ УДАЛЕНО: ExecutionResult.failure
                # ✅ ТЕПЕРЬ: Выбрасываем StructuredOutputError
                from core.errors.exceptions import StructuredOutputError
                raise StructuredOutputError(
                    message=f"Ошибка LLM при анализе данных: {llm_result.error}",
                    model_name="data_analysis",
                    attempts=llm_result.metadata.get("attempts", 0) if isinstance(llm_result.metadata, dict) else 0,
                    validation_errors=[{"error": llm_result.metadata.get("error_type", "unknown") if isinstance(llm_result.metadata, dict) else "unknown"}]
                )

            # 8. Получаем структурированные данные (Pydantic model_dump())
            if hasattr(llm_result.result, 'model_dump'):
                answer_data = llm_result.result.model_dump()
            elif hasattr(llm_result.result, 'dict'):
                answer_data = llm_result.result.dict()
            else:
                answer_data = llm_result.result if llm_result.result else {}

            # Логирование успешного structured output
            self._log_info(
                f"Анализ шага выполнен с structured output (попыток: {llm_result.metadata.get('parsing_attempts', 1) if isinstance(llm_result.metadata, dict) else 1})",
                event_type=LogEventType.INFO
            )

            # 9. Добавление метаданных
            answer_data["metadata"] = answer_data.get("metadata", {}) if isinstance(answer_data, dict) else {}
            if isinstance(answer_data, dict):
                answer_data["metadata"]["chunks_processed"] = len(chunks) if chunks else 1
                answer_data["metadata"]["total_tokens"] = llm_result.metadata.get("tokens_used", 0) if isinstance(llm_result.metadata, dict) else 0
                answer_data["metadata"]["processing_time_ms"] = (time.time() - start_time) * 1000
                answer_data["metadata"]["data_size_mb"] = data_metadata.get("size_mb", 0)
                answer_data["metadata"]["parsing_attempts"] = llm_result.metadata.get("parsing_attempts", 1) if isinstance(llm_result.metadata, dict) else 1
                answer_data["metadata"]["structured_output"] = True

            # 10. Валидация выхода (уже валидно через structured output)
            # Пропускаем повторную валидацию, так как structured output уже проверил данные
            pass

            # Возвращаем dict (НЕ ExecutionResult!) — BaseComponent сам обернёт
            return {
                **answer_data,
                "metadata": {
                    "chunks_processed": len(chunks) if chunks else 1,
                    "total_tokens": llm_result.metadata.get("tokens_used", 0) if isinstance(llm_result.metadata, dict) else 0,
                    "processing_time_ms": (time.time() - start_time) * 1000,
                    "data_size_mb": data_metadata.get("size_mb", 0),
                    "parsing_attempts": llm_result.metadata.get("parsing_attempts", 1) if isinstance(llm_result.metadata, dict) else 1,
                    "structured_output": True
                }
            }

        except Exception as e:
            self._log_error(f"Ошибка анализа: {e}", event_type=LogEventType.ERROR)
            # ❌ УДАЛЕНО: ExecutionResult.failure
            # ✅ ТЕПЕРЬ: Выбрасываем SkillExecutionError
            from core.errors.exceptions import SkillExecutionError
            raise SkillExecutionError(
                f"Не удалось выполнить анализ данных: {str(e)}. "
                f"Проверьте что данные доступны и LLM провайдер работает.",
                component="data_analysis"
            )

    # ─────────────────────────────────────────────────────────────────
    # Методы загрузки данных
    # ─────────────────────────────────────────────────────────────────

    def _load_data_from_context(self, step_id: str, session_ctx) -> tuple:
        """
        Загрузка сырых данных шага из SessionContext.

        АЛГОРИТМ:
        1. Найти observation по step_id (в additional_data.step_id или step_number)
        2. Извлечь content (raw data)
        3. Вернуть как строку

        ВОЗВРАЩАЕТ:
        - (raw_data: str, metadata: dict) или (None, {}) если данных нет
        """
        if not hasattr(session_ctx, 'data_context'):
            self._log_debug("SessionContext не имеет data_context", event_type=LogEventType.DEBUG)
            return None, {}

        # Ищем observation по step_id
        items = session_ctx.data_context.get_all_items()
        for item in items:
            meta = item.metadata
            if not meta:
                continue

            # Проверяем match по step_id
            add_data = meta.additional_data or {}
            meta_step_id = add_data.get("step_id")
            meta_step_number = meta.step_number

            if meta_step_id == step_id or str(meta_step_number) == str(step_id):
                content = item.content
                if content:
                    # content может быть dict или str
                    if isinstance(content, dict):
                        # Извлекаем сырые данные из observation
                        raw = content.get("content", content.get("raw_data", content.get("data", "")))
                        if not raw and "rows" in content:
                            # Конвертируем rows в CSV
                            rows = content["rows"]
                            if rows:
                                cols = list(rows[0].keys())
                                lines = [",".join(str(c) for c in cols)]
                                for row in rows:
                                    lines.append(",".join(str(v) for v in row.values()))
                                raw = "\n".join(lines)
                        content = raw
                    if content and len(str(content)) > 0:
                        data_str = str(content)
                        metadata = {
                            "source_type": "session_context",
                            "step_id": step_id,
                            "size_mb": len(data_str.encode('utf-8')) / (1024 * 1024)
                        }
                        self._log_info(
                            f"Данные загруены из SessionContext: step={step_id}, {len(data_str)} символов",
                            event_type=LogEventType.INFO
                        )
                        return data_str, metadata

        self._log_debug(f"Данные для step_id={step_id} не найдены в SessionContext", event_type=LogEventType.DEBUG)
        return None, {}

    async def _load_data(
        self,
        data_source: Any,
        config: Any
    ) -> tuple:
        """Загрузка данных из указанного источника."""
        source_type = data_source.get("type") if isinstance(data_source, dict) else getattr(data_source, 'type', None)
        if not source_type:
            raise ValueError("Не указан тип источника данных (type)")
        metadata = {"source_type": source_type}

        if source_type == "database":
            return await self._load_from_database(data_source, config, metadata)
        elif source_type == "memory":
            return await self._load_from_memory(data_source, metadata)
        else:
            raise ValueError(f"Неподдерживаемый тип источника данных: {source_type}")

    async def _load_from_database(
        self,
        data_source: Dict[str, Any],
        config: Dict[str, Any],
        metadata: Dict[str, Any]
    ) -> tuple:
        """Загрузка данных из БД через SQLTool."""
        table_name = data_source.get("path")
        query = data_source.get("query")

        if not table_name and not query:
            raise ValueError("Укажите table_name или query для загрузки из БД")

        # Формирование запроса
        if query:
            sql = query
        else:
            max_rows = config.get("max_rows", 10000)
            sql = f"SELECT * FROM {table_name} LIMIT {max_rows}"

        # Выполнение запроса через executor
        from core.agent.components.action_executor import ExecutionContext
        exec_context = ExecutionContext()
        
        result = await self.executor.execute_action(
            action_name="sql_tool.execute",
            parameters={
                "sql": sql,
                "max_rows": config.get("max_rows", 10000)
            },
            context=exec_context
        )

        from core.models.data.execution import ExecutionStatus
        if result.status != ExecutionStatus.COMPLETED or not result.data:
            raise RuntimeError(f"Ошибка выполнения запроса: {result.error or 'пустой результат'}")

        # Конвертация результатов в CSV-like строку
        rows = result.data.get("rows", [])
        columns = result.data.get("columns", list(rows[0].keys()) if rows else [])

        lines = [",".join(str(c) for c in columns)]
        for row in rows:
            if isinstance(row, dict):
                lines.append(",".join(str(v) for v in row.values()))
            else:
                lines.append(",".join(str(v) for v in row))

        content = "\n".join(lines)
        metadata["row_count"] = len(rows)
        metadata["table_name"] = table_name
        metadata["size_mb"] = len(content.encode('utf-8')) / (1024 * 1024)

        return content, metadata

    async def _load_from_memory(
        self,
        data_source: Dict[str, Any],
        metadata: Dict[str, Any]
    ) -> tuple:
        """Загрузка данных из памяти (контекста сессии)."""
        data = data_source.get("content", "")
        metadata["size_mb"] = len(data.encode('utf-8')) / (1024 * 1024)
        metadata["source_type"] = "memory"
        return data, metadata

    # ─────────────────────────────────────────────────────────────────
    # Методы обработки больших данных
    # ─────────────────────────────────────────────────────────────────

    async def _chunk_data_if_needed(
        self,
        data: str,
        config: Dict[str, Any],
        metadata: Dict[str, Any]
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Разбиение данных на чанки если они превышают лимит.

        Эвристика: ~4 символа ≈ 1 токен
        """
        chunk_size = config.get("chunk_size", 2000)
        max_chunks = config.get("max_chunks", 50)

        estimated_tokens = len(data) // 4

        if estimated_tokens <= chunk_size:
            metadata["chunking_applied"] = False
            return None

        # Разбиение на чанки по строкам
        chunks = []
        lines = data.split('\n')
        current_chunk = []
        current_tokens = 0

        for line in lines:
            line_tokens = len(line) // 4
            if current_tokens + line_tokens > chunk_size and current_chunk:
                chunks.append({
                    "content": "\n".join(current_chunk),
                    "token_estimate": current_tokens,
                    "line_range": [len(chunks)*chunk_size//4, (len(chunks)+1)*chunk_size//4]
                })
                current_chunk = [line]
                current_tokens = line_tokens
            else:
                current_chunk.append(line)
                current_tokens += line_tokens

            if len(chunks) >= max_chunks:
                self._log_warning(f"Достигнут лимит чанков ({max_chunks})", event_type=LogEventType.WARNING)
                break

        if current_chunk:
            chunks.append({
                "content": "\n".join(current_chunk),
                "token_estimate": current_tokens,
                "line_range": [len(chunks)*chunk_size//4, len(data)//4]
            })

        metadata["chunks_created"] = len(chunks)
        metadata["chunking_applied"] = True

        return chunks

    # ─────────────────────────────────────────────────────────────────
    # Вспомогательные методы
    # ─────────────────────────────────────────────────────────────────

    def _render_prompt(self, prompt: str, variables: Dict[str, Any]) -> str:
        """Рендеринг промпта с подстановкой переменных.

        СТАНДАРТ: {key} (одинарные скобки) — единообразно с base_behavior_pattern.
        Если переменная не передана — плейсхолдер удаляется.
        """
        import re
        result = prompt
        for key, value in variables.items():
            placeholder = "{" + key + "}"
            if isinstance(value, list):
                if value:
                    formatted = "\n\n".join(
                        f"### Чанк {i+1}\n{chunk.get('content', '')}"
                        for i, chunk in enumerate(value)
                    )
                else:
                    formatted = "Данные отсутствуют (чанки не созданы)."
                result = result.replace(placeholder, formatted)
            elif isinstance(value, dict):
                formatted = "\n".join(f"{k}: {v}" for k, v in value.items())
                result = result.replace(placeholder, formatted)
            else:
                result = result.replace(placeholder, str(value))

        # Удаляем оставшиеся плейсхолдеры (непереданные переменные)
        result = re.sub(r'\{[a-z_]+\}', '', result)
        # Удаляем Jinja2-подобные конструкции если они остались
        result = re.sub(r'\{%.*?%\}', '', result)
        return result

    def _parse_llm_response(self, content: str) -> Dict[str, Any]:
        """Парсинг JSON-ответа от LLM."""
        from core.infrastructure.providers.llm.json_parser import extract_json_from_response

        try:
            json_str = extract_json_from_response(content)
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            self.logger.warning(f"Ошибка парсинга JSON: {e}")
              # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            return {
                "answer": content.strip(),
                "confidence": 0.5,
                "evidence": [],
                "metadata": {"parse_error": str(e)}
            }

    def _validate_analysis_result(
        self,
        data: Dict[str, Any],
        capability_name: str
    ) -> Dict[str, Any]:
        """Валидация выходных данных через контракт."""
        # Минимальная валидация обязательных полей
        required_fields = ["answer", "confidence"]
        for field in required_fields:
            if field not in data:
                raise ValueError(f"Отсутствует обязательное поле: {field}")

        # Валидация confidence
        confidence = data.get("confidence", 0)
        if not isinstance(confidence, (int, float)) or not (0 <= confidence <= 1):
            data["confidence"] = max(0, min(1, float(confidence)))

        return data

