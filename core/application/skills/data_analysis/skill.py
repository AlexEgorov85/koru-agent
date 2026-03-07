"""
Навык анализа сырых данных по шагу.

Архитектурные гарантии:
- Использует BaseComponent для изолированных кэшей
- Доступ к инструментам только через ApplicationContext
- Валидация входных/выходных данных через контракты
- Поддержка профилей prod/sandbox через AppConfig
"""

import asyncio
import time
import json
import re
from typing import List, Dict, Any, Optional
from pathlib import Path

from core.application.skills.base_skill import BaseSkill
from core.models.data.capability import Capability
from core.models.data.execution import ExecutionResult, ExecutionStatus, SkillResult
from core.models.enums.common_enums import ErrorCategory
from core.models.types.llm_types import LLMRequest
from core.application.tools.file_tool import FileToolInput
from core.application.tools.sql_tool import SQLToolInput
from core.infrastructure.logging import EventBusLogger


class DataAnalysisSkill(BaseSkill):
    """Навык для анализа сырых данных по шагу и ответа на вопросы."""

    # Явная декларация зависимостей
    DEPENDENCIES = ["file_tool", "sql_tool"]

    name: str = "data_analysis"
    
    def __init__(
        self,
        name: str,
        application_context: Any,
        component_config: Any,
        executor: Any
    ):
        super().__init__(name, application_context, component_config=component_config, executor=executor)

        # Регистрируем поддерживаемые capability
        self.supported_capabilities = {
            "data_analysis.analyze_step_data": self._analyze_step_data
        }
        # EventBusLogger для асинхронного логирования
        self.event_bus_logger = None
        self._init_event_bus_logger()

    def _init_event_bus_logger(self):
        """Инициализация EventBusLogger для асинхронного логирования."""
        # Используем внедрённый event_bus из BaseComponent
        if hasattr(self, '_event_bus') and self._event_bus is not None:
            self.event_bus_logger = EventBusLogger(
                self._event_bus,
                session_id="system",
                agent_id="system",
                component=self.__class__.__name__
            )
        # Fallback на application_context для обратной совместимости
        elif hasattr(self, '_application_context') and self._application_context:
            event_bus = getattr(self._application_context.infrastructure_context, 'event_bus', None)
            if event_bus:
                self.event_bus_logger = EventBusLogger(
                    event_bus,
                    session_id="system",
                    agent_id="system",
                    component=self.__class__.__name__
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
                    "contract_version": "v1.0.0",
                    "prompt_version": "v1.0.0",
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
            if self.event_bus_logger:
                await self.event_bus_logger.warning("Промпт для data_analysis.analyze_step_data не загружен")
            else:
                self.logger.warning("Промпт для data_analysis.analyze_step_data не загружен")

        if "data_analysis.analyze_step_data" not in self.input_contracts:
            if self.event_bus_logger:
                await self.event_bus_logger.warning("Входная схема для data_analysis.analyze_step_data не загружена")
            else:
                self.logger.warning("Входная схема для data_analysis.analyze_step_data не загружена")

        if "data_analysis.analyze_step_data" not in self.output_contracts:
            if self.event_bus_logger:
                await self.event_bus_logger.warning("Выходная схема для data_analysis.analyze_step_data не загружена")
            else:
                self.logger.warning("Выходная схема для data_analysis.analyze_step_data не загружена")

        if self.event_bus_logger:
            await self.event_bus_logger.info(f"DataAnalysisSkill инициализирован с capability: {list(self.supported_capabilities.keys())}")
        else:
            self.logger.info(f"DataAnalysisSkill инициализирован с capability: {list(self.supported_capabilities.keys())}")
        return True

    def _get_event_type_for_success(self) -> 'EventType':
        """Возвращает тип события для успешного выполнения навыка анализа данных."""
        from core.infrastructure.event_bus.unified_event_bus import EventType
        return EventType.SKILL_EXECUTED

    async def _execute_impl(
        self,
        capability: Capability,
        parameters: Dict[str, Any],
        execution_context: Any
    ) -> SkillResult:
        """
        Реализация бизнес-логики анализа данных.

        ВАЖНО: Валидация входа/выхода и метрики выполняются в BaseComponent.execute()
        Здесь только бизнес-логика.
        """
        step_id = parameters.get("step_id")
        question = parameters.get("question")
        data_source = parameters.get("data_source", {})
        analysis_config = parameters.get("analysis_config", {})

        # 1. Загрузка данных из источника
        raw_data, data_metadata = await self._load_data(
            data_source=data_source,
            config=analysis_config
        )

        # 2. Обработка больших данных через чанкинг при необходимости
        chunks = await self._chunk_data_if_needed(
            data=raw_data,
            config=analysis_config,
            metadata=data_metadata
        )

        # 3. Подготовка переменных для промпта
        prompt_vars = {
            "step_id": step_id,
            "question": question,
            "data_source": data_source,
            "aggregation_method": analysis_config.get("aggregation_method", "summary")
        }

        if chunks:
            prompt_vars["chunks"] = chunks
        else:
            prompt_vars["raw_data"] = raw_data[:10000]  # Ограничение для безопасности

        # 4. Получение и рендеринг промпта С КОНТРАКТАМИ (из изолированного кэша)
        prompt_with_contract = self.get_prompt_with_contract(capability.name)
        if not prompt_with_contract:
            raise ValueError(f"Промпт для {capability.name} не загружен")

        rendered_prompt = self._render_prompt(prompt_with_contract, prompt_vars)

        # 5. Получаем схему выхода для structured output
        output_schema = self.get_output_contract(capability.name)

        # 6. Вызов LLM для анализа С STRUCTURED OUTPUT через executor
        llm_result = await self.executor.execute_action(
            action_name="llm.generate_structured",
            parameters={
                "prompt": rendered_prompt,
                "structured_output": {
                    "output_model": f"{capability.name}.output",
                    "schema_def": output_schema,
                    "max_retries": 3,
                    "strict_mode": True
                },
                "temperature": 0.1,  # Низкая температура для аналитических задач
                "max_tokens": analysis_config.get("max_response_tokens", 2000)
            },
            context=execution_context
        )

        # === ПРОВЕРКА НА ОШИБКУ ===
        from core.models.data.execution import ExecutionStatus
        if llm_result.status != ExecutionStatus.COMPLETED:
            error_msg = llm_result.error
            error_type = llm_result.metadata.get("error_type", "unknown") if isinstance(llm_result.metadata, dict) else "unknown"
            if self.event_bus_logger:
                await self.event_bus_logger.error(f"LLM structured output ошибка при анализе данных: {error_msg} (тип: {error_type})")
            else:
                self.logger.error(f"LLM structured output ошибка при анализе данных: {error_msg} (тип: {error_type})")
            return SkillResult.failure(
                error=f"Ошибка LLM: {error_msg}",
                metadata={
                    "chunks_processed": len(chunks) if chunks else 1,
                    "total_tokens": 0,
                    "data_size_mb": data_metadata.get("size_mb", 0),
                    "error_type": error_type,
                    "attempts": llm_result.metadata.get("attempts", 0) if isinstance(llm_result.metadata, dict) else 0
                }
            )

        # 7. Получаем структурированные данные (Pydantic model_dump())
        answer_data = llm_result.result.get("parsed_content", {}) if llm_result.result else {}

        # Логирование успешного structured output
        if self.event_bus_logger:
            await self.event_bus_logger.info(
                f"Анализ данных выполнен с structured output (попыток: {llm_result.metadata.get('parsing_attempts', 1) if isinstance(llm_result.metadata, dict) else 1})"
            )
        else:
            self.logger.info(
                f"Анализ данных выполнен с structured output (попыток: {llm_result.metadata.get('parsing_attempts', 1) if isinstance(llm_result.metadata, dict) else 1})"
            )

        # Добавляем метаданные в ответ
        if "metadata" not in answer_data:
            answer_data["metadata"] = {}

        answer_data["metadata"]["chunks_processed"] = len(chunks) if chunks else 1
        answer_data["metadata"]["total_tokens"] = llm_result.metadata.get("tokens_used", 0) if isinstance(llm_result.metadata, dict) else 0
        answer_data["metadata"]["data_size_mb"] = data_metadata.get("size_mb", 0)
        answer_data["metadata"]["parsing_attempts"] = llm_result.metadata.get("parsing_attempts", 1) if isinstance(llm_result.metadata, dict) else 1
        answer_data["metadata"]["structured_output"] = True

        # 8. Валидация выхода (уже валидно через structured output, но проверяем для безопасности)
        validated_answer = self._validate_output(answer_data, capability.name)

        # Возвращаем SkillResult с side_effect=True (file/DB access possible)
        return SkillResult.success(
            data=validated_answer,
            metadata={
                "chunks_processed": len(chunks) if chunks else 1,
                "data_size_mb": data_metadata.get("size_mb", 0),
                "structured_output": True
            },
            side_effect=True  # Data analysis может читать файлы/БД
        )

    async def _analyze_step_data(self, params: Dict[str, Any]) -> SkillResult:
        """
        Основная логика анализа данных шага.

        Args:
            params: Параметры анализа

        Returns:
            Словарь с результатом анализа
        """
        start_time = time.time()

        # 1. Валидация входных параметров
        # ✅ ПРИМЕЧАНИЕ: BaseComponent.execute() уже валидировал параметры через validate_input_typed()
        # params уже может быть Pydantic моделью DataAnalysisInput
        from pydantic import BaseModel
        if isinstance(params, BaseModel):
            # params уже валидированная модель — используем напрямую
            if self.event_bus_logger:
                await self.event_bus_logger.debug(f"Получены типизированные параметры: {type(params).__name__}")
        else:
            # Fallback для обратной совместимости
            input_schema = self.get_cached_input_contract_safe("data_analysis.analyze_step_data")
            if input_schema:
                try:
                    validated_params = input_schema.model_validate(params)
                    params = validated_params
                except Exception as e:
                    if self.event_bus_logger:
                        await self.event_bus_logger.error(f"Ошибка валидации параметров: {e}")
                    else:
                        self.logger.error(f"Ошибка валидации параметров: {e}")
                    return SkillResult.failure(
                        error=f"Неверные параметры: {str(e)}",
                        metadata={"answer": "", "confidence": 0.0, "evidence": []}
                    )

        step_id = params.get("step_id") if not isinstance(params, BaseModel) else getattr(params, 'step_id', None)
        question = params.get("question") if not isinstance(params, BaseModel) else getattr(params, 'question', None)
        data_source = params.get("data_source", {}) if not isinstance(params, BaseModel) else getattr(params, 'data_source', {})
        analysis_config = params.get("analysis_config", {}) if not isinstance(params, BaseModel) else getattr(params, 'analysis_config', {})

        # 2. Загрузка данных
        try:
            raw_data, data_metadata = await self._load_data(
                data_source=data_source,
                config=analysis_config
            )
        except Exception as e:
            if self.event_bus_logger:
                await self.event_bus_logger.error(f"Ошибка загрузки данных: {e}")
            else:
                self.logger.error(f"Ошибка загрузки данных: {e}")
            return SkillResult.failure(
                error=f"Ошибка загрузки данных: {str(e)}",
                metadata={"answer": "", "confidence": 0.0, "evidence": []}
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
            "data_source": data_source,
            "aggregation_method": analysis_config.get("aggregation_method", "summary")
        }

        if chunks:
            prompt_vars["chunks"] = chunks
        else:
            prompt_vars["raw_data"] = raw_data[:10000]

        # 5. Получение промпта С КОНТРАКТАМИ
        prompt_with_contract = self.get_prompt_with_contract("data_analysis.analyze_step_data")
        if not prompt_with_contract:
            return SkillResult.failure(
                error="Промпт не найден",
                metadata={"answer": "", "confidence": 0.0, "evidence": []}
            )

        rendered_prompt = self._render_prompt(prompt_with_contract, prompt_vars)

        # 6. Получаем схему выхода для structured output
        output_schema = self.get_cached_output_contract_safe("data_analysis.analyze_step_data")

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
                return SkillResult.failure(
                    error=f"Ошибка LLM: {llm_result.error}",
                    metadata={
                        "error_type": llm_result.metadata.get("error_type", "unknown") if isinstance(llm_result.metadata, dict) else "unknown",
                        "attempts": llm_result.metadata.get("attempts", 0) if isinstance(llm_result.metadata, dict) else 0,
                        "answer": "",
                        "confidence": 0.0,
                        "evidence": []
                    }
                )

            # 8. Получаем структурированные данные (Pydantic model_dump())
            answer_data = llm_result.result.get("parsed_content", {}) if llm_result.result else {}

            # Логирование успешного structured output
            if self.event_bus_logger:
                await self.event_bus_logger.info(
                    f"Анализ шага выполнен с structured output (попыток: {llm_result.metadata.get('parsing_attempts', 1) if isinstance(llm_result.metadata, dict) else 1})"
                )
            else:
                self.logger.info(
                    f"Анализ шага выполнен с structured output (попыток: {llm_result.metadata.get('parsing_attempts', 1) if isinstance(llm_result.metadata, dict) else 1})"
                )

            # 9. Добавление метаданных
            answer_data["metadata"] = answer_data.get("metadata", {})
            answer_data["metadata"]["chunks_processed"] = len(chunks) if chunks else 1
            answer_data["metadata"]["total_tokens"] = llm_result.metadata.get("tokens_used", 0) if isinstance(llm_result.metadata, dict) else 0
            answer_data["metadata"]["processing_time_ms"] = (time.time() - start_time) * 1000
            answer_data["metadata"]["data_size_mb"] = data_metadata.get("size_mb", 0)
            answer_data["metadata"]["parsing_attempts"] = llm_result.metadata.get("parsing_attempts", 1) if isinstance(llm_result.metadata, dict) else 1
            answer_data["metadata"]["structured_output"] = True

            # 10. Валидация выхода (уже валидно через structured output)
            # ✅ ИСПРАВЛЕНО: Сохраняем Pydantic модель вместо dict!
            if output_schema:
                try:
                    validated_result = output_schema.model_validate(answer_data)
                    answer_data = validated_result  # ← Сохраняем модель!
                except Exception as e:
                    if self.event_bus_logger:
                        await self.event_bus_logger.error(f"Ошибка валидации результата: {e}")
                    else:
                        self.logger.error(f"Ошибка валидации результата: {e}")
            else:
                # Fallback на dict если схема не загружена
                pass

            # Возвращаем SkillResult с side_effect=True
            return SkillResult.success(
                data=answer_data,  # ← Pydantic модель!
                metadata={
                    "chunks_processed": len(chunks) if chunks else 1,
                    "processing_time_ms": (time.time() - start_time) * 1000,
                    "data_size_mb": data_metadata.get("size_mb", 0),
                    "structured_output": True
                },
                side_effect=True
            )

        except Exception as e:
            if self.event_bus_logger:
                await self.event_bus_logger.error(f"Ошибка анализа: {e}", exc_info=True)
            else:
                self.logger.error(f"Ошибка анализа: {e}", exc_info=True)
            return SkillResult.failure(
                error=f"Ошибка анализа: {str(e)}",
                metadata={"answer": "", "confidence": 0.0, "evidence": []}
            )

    # ─────────────────────────────────────────────────────────────────
    # Методы загрузки данных
    # ─────────────────────────────────────────────────────────────────

    async def _load_data(
        self,
        data_source: Dict[str, Any],
        config: Dict[str, Any]
    ) -> tuple:
        """Загрузка данных из указанного источника."""
        source_type = data_source.get("type")
        metadata = {"source_type": source_type}

        if source_type == "file":
            return await self._load_from_file(data_source, config, metadata)
        elif source_type == "database":
            return await self._load_from_database(data_source, config, metadata)
        elif source_type == "memory":
            return await self._load_from_memory(data_source, metadata)
        else:
            raise ValueError(f"Неподдерживаемый тип источника данных: {source_type}")

    async def _load_from_file(
        self,
        data_source: Dict[str, Any],
        config: Dict[str, Any],
        metadata: Dict[str, Any]
    ) -> tuple:
        """Загрузка данных из файла через FileTool."""
        file_path = data_source.get("path")
        if not file_path:
            raise ValueError("Путь к файлу не указан")

        # Получение инструмента через ApplicationContext
        file_tool = self.application_context.components.get(
            type(self.application_context.components._components.get(type(self.application_context.components._components.keys()[0]).__call__()) if self.application_context.components._components else None), 
            "file_tool"
        )
        
        # Альтернативный способ получения инструмента
        from core.models.enums.common_enums import ComponentType
        file_tool = self.application_context.components.get(ComponentType.TOOL, "file_tool")
        
        if not file_tool:
            raise RuntimeError("FileTool не доступен")

        # Чтение файла
        input_data = FileToolInput(operation="read", path=file_path)
        result = await file_tool.execute(input_data)

        if not result.success:
            raise RuntimeError(f"Ошибка чтения файла: {result.error}")

        content = result.data.get("content", "")
        metadata["size_mb"] = len(content.encode('utf-8')) / (1024 * 1024)
        metadata["file_path"] = file_path

        return content, metadata

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

        from core.models.enums.common_enums import ComponentType
        sql_tool = self.application_context.components.get(ComponentType.TOOL, "sql_tool")
        
        if not sql_tool:
            raise RuntimeError("SQLTool не доступен")

        # Формирование запроса
        if query:
            sql = query
        else:
            max_rows = config.get("max_rows", 10000)
            sql = f"SELECT * FROM {table_name} LIMIT {max_rows}"

        input_data = SQLToolInput(
            sql=sql,
            parameters=None,
            max_rows=config.get("max_rows", 10000)
        )
        result = await sql_tool.execute(input_data)

        if not result.rows:
            raise RuntimeError(f"Ошибка выполнения запроса: пустой результат")

        # Конвертация результатов в CSV-like строку
        rows = result.rows
        columns = result.columns if hasattr(result, 'columns') and result.columns else list(rows[0].keys()) if rows else []

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
                if self.event_bus_logger:
                    await self.event_bus_logger.warning(f"Достигнут лимит чанков ({max_chunks})")
                else:
                    self.logger.warning(f"Достигнут лимит чанков ({max_chunks})")
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
        """Рендеринг промпта с подстановкой переменных."""
        result = prompt
        for key, value in variables.items():
            placeholder = f"{{{{ {key} }}}}"
            if isinstance(value, list):
                formatted = "\n\n".join(
                    f"### Чанк {i+1}\n{chunk.get('content', '')}"
                    for i, chunk in enumerate(value)
                )
                result = result.replace(f"{{% if chunks %}}{placeholder}{{% endif %}}", formatted)
                result = result.replace(placeholder, formatted)
            else:
                result = result.replace(placeholder, str(value))
        
        # Удаляем Jinja2-подобные конструкции если они остались
        result = re.sub(r'\{%.*?%\}', '', result)
        return result

    def _parse_llm_response(self, content: str) -> Dict[str, Any]:
        """Парсинг JSON-ответа от LLM."""
        try:
            # Извлечение JSON из markdown-блоков
            if "```json" in content:
                json_str = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                json_str = content.split("```")[1].split("```")[0].strip()
            else:
                # Попытка найти JSON по скобкам
                match = re.search(r'\{[\s\S]*\}', content)
                json_str = match.group(0) if match else content.strip()

            return json.loads(json_str)
        except json.JSONDecodeError as e:
            self.logger.warning(f"Ошибка парсинга JSON: {e}")
            return {
                "answer": content.strip(),
                "confidence": 0.5,
                "evidence": [],
                "metadata": {"parse_error": str(e)}
            }

    def _validate_output(
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
