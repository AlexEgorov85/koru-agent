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
from core.models.data.execution import ExecutionResult, ExecutionStatus
from core.models.enums.common_enums import ErrorCategory
from core.models.types.llm_types import LLMRequest
from core.application.tools.file_tool import FileToolInput
from core.application.tools.sql_tool import SQLToolInput


class DataAnalysisSkill(BaseSkill):
    """Навык для анализа сырых данных по шагу и ответа на вопросы."""
    
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
            self.logger.warning("Промпт для data_analysis.analyze_step_data не загружен")

        if "data_analysis.analyze_step_data" not in self.input_contracts:
            self.logger.warning("Входная схема для data_analysis.analyze_step_data не загружена")

        if "data_analysis.analyze_step_data" not in self.output_contracts:
            self.logger.warning("Выходная схема для data_analysis.analyze_step_data не загружена")

        self.logger.info(f"DataAnalysisSkill инициализирован с capability: {list(self.supported_capabilities.keys())}")
        return True

    def _get_event_type_for_success(self) -> 'EventType':
        """Возвращает тип события для успешного выполнения навыка анализа данных."""
        from core.infrastructure.event_bus.event_bus import EventType
        return EventType.SKILL_EXECUTED

    async def _execute_impl(
        self,
        capability: Capability,
        parameters: Dict[str, Any],
        execution_context: Any
    ) -> Dict[str, Any]:
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

        # 4. Получение и рендеринг промпта (из изолированного кэша)
        prompt_content = self.get_prompt(capability.name)
        if not prompt_content:
            raise ValueError(f"Промпт для {capability.name} не загружен")

        rendered_prompt = self._render_prompt(prompt_content, prompt_vars)

        # 5. Вызов LLM для анализа
        llm_request = LLMRequest(
            prompt=rendered_prompt,
            max_tokens=analysis_config.get("max_response_tokens", 2000),
            temperature=0.1,  # Низкая температура для аналитических задач
            stop_sequences=["```", "END"]
        )

        llm_provider = self.application_context.get_llm_provider()
        llm_response = await llm_provider.generate(llm_request)

        # 6. Парсинг и валидация ответа
        answer_data = self._parse_llm_response(llm_response.content)

        # Добавляем метаданные в ответ
        if "metadata" not in answer_data:
            answer_data["metadata"] = {}

        answer_data["metadata"]["chunks_processed"] = len(chunks) if chunks else 1
        answer_data["metadata"]["total_tokens"] = llm_response.tokens_used
        answer_data["metadata"]["data_size_mb"] = data_metadata.get("size_mb", 0)

        validated_answer = self._validate_output(answer_data, capability.name)

        return validated_answer

    async def _analyze_step_data(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Основная логика анализа данных шага.

        Args:
            params: Параметры анализа

        Returns:
            Словарь с результатом анализа
        """
        start_time = time.time()

        # 1. Валидация входных параметров через кэшированную схему
        input_schema = self.get_cached_input_contract_safe("data_analysis.analyze_step_data")
        if input_schema:
            try:
                validated_params = input_schema.model_validate(params)
                params = validated_params.model_dump()
            except Exception as e:
                self.logger.error(f"Ошибка валидации параметров: {e}")
                return {
                    "error": f"Неверные параметры: {str(e)}",
                    "answer": "",
                    "confidence": 0.0,
                    "evidence": []
                }

        step_id = params.get("step_id")
        question = params.get("question")
        data_source = params.get("data_source", {})
        analysis_config = params.get("analysis_config", {})

        # 2. Загрузка данных
        try:
            raw_data, data_metadata = await self._load_data(
                data_source=data_source,
                config=analysis_config
            )
        except Exception as e:
            self.logger.error(f"Ошибка загрузки данных: {e}")
            return {
                "error": f"Ошибка загрузки данных: {str(e)}",
                "answer": "",
                "confidence": 0.0,
                "evidence": []
            }

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

        # 5. Получение промпта
        prompt_content = self.get_cached_prompt_safe("data_analysis.analyze_step_data")
        if not prompt_content:
            return {
                "error": "Промпт не найден",
                "answer": "",
                "confidence": 0.0,
                "evidence": []
            }

        rendered_prompt = self._render_prompt(prompt_content, prompt_vars)

        # 6. Вызов LLM
        try:
            llm_provider = self.application_context.get_llm_provider()
            llm_request = LLMRequest(
                prompt=rendered_prompt,
                max_tokens=analysis_config.get("max_response_tokens", 2000),
                temperature=0.1,
                stop_sequences=["```", "END"]
            )

            llm_response = await llm_provider.generate(llm_request)

            # 7. Парсинг ответа
            answer_data = self._parse_llm_response(llm_response.content)

            # 8. Добавление метаданных
            answer_data["metadata"] = answer_data.get("metadata", {})
            answer_data["metadata"]["chunks_processed"] = len(chunks) if chunks else 1
            answer_data["metadata"]["total_tokens"] = llm_response.tokens_used
            answer_data["metadata"]["processing_time_ms"] = (time.time() - start_time) * 1000
            answer_data["metadata"]["data_size_mb"] = data_metadata.get("size_mb", 0)

            # 9. Валидация выхода
            output_schema = self.get_cached_output_contract_safe("data_analysis.analyze_step_data")
            if output_schema:
                try:
                    validated_result = output_schema.model_validate(answer_data)
                    return validated_result.model_dump()
                except Exception as e:
                    self.logger.error(f"Ошибка валидации результата: {e}")

            return answer_data

        except Exception as e:
            self.logger.error(f"Ошибка анализа: {e}", exc_info=True)
            return {
                "error": f"Ошибка анализа: {str(e)}",
                "answer": "",
                "confidence": 0.0,
                "evidence": []
            }

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
