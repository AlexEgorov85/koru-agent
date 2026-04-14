"""
Навык анализа сырых данных по шагу.

АРХИТЕКТУРА:
- Режим PYTHON: детерминированный AnalyticsEngine (без LLM)
- Режим LLM: интерпретация данных через LLM с structured output
- Режим SEMANTIC: работа с текстовыми данными, чанкинг, резюме
- Режим AUTO: автовыбор на основе вопроса и профиля данных

ГАРАНТИИ:
- Нет exec/eval — только безопасные операции
- Нет прямых вызовов LLM — через ActionExecutor
- Валидация через контракты
- Метрики в EventBus
"""

import asyncio
import time
import json
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

from core.components.skills.skill import Skill
from core.models.data.capability import Capability
from core.models.data.execution import ExecutionResult, ExecutionStatus
from core.infrastructure.logging.event_types import LogEventType
from core.components.skills.data_analysis.utils.data_profiler import DataProfiler
from core.components.skills.data_analysis.analytics_engine import AnalyticsEngine


class DataAnalysisSkill(Skill):
    """Навык для анализа сырых данных по шагу и ответа на вопросы."""

    @property
    def description(self) -> str:
        return "Навык анализа сырых данных по шагу и ответа на заданный вопрос"

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
                    "modes": ["python", "llm", "semantic", "auto"],
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

        РЕЖИМЫ:
        - python: детерминированный AnalyticsEngine (без LLM)
        - llm: интерпретация данных через LLM
        - semantic: работа с текстовыми данными
        - auto: автовыбор на основе вопроса и профиля

        ВОЗВРАЩАЕТ:
            - Dict[str, Any]: Данные результата (не ExecutionResult!)
        """
        start_time = time.time()

        self._log_info(
            f"📊 [data_analysis] Начало анализа",
            event_type=LogEventType.TOOL_CALL
        )

        # 1. Валидация входных параметров
        if hasattr(parameters, 'model_dump'):
            params_dict = parameters.model_dump()
        elif hasattr(parameters, 'dict'):
            params_dict = parameters.dict()
        elif isinstance(parameters, dict):
            params_dict = parameters
        else:
            raise ValueError(f"Неподдерживаемый тип параметров: {type(parameters)}")

        step_id = params_dict.get("step_id")
        question = params_dict.get("question")
        mode = params_dict.get("mode", "auto")
        max_rows = params_dict.get("max_rows", 10000)
        max_response_chars = params_dict.get("max_response_chars", 8000)

        if not step_id:
            raise ValueError("Параметр 'step_id' обязателен")
        if not question:
            raise ValueError("Параметр 'question' обязателен")

        self._log_info(
            f"📋 [data_analysis] step_id={step_id}, question='{question[:50]}...', mode={mode}",
            event_type=LogEventType.INFO
        )

        # 2. Загрузка данных из SessionContext
        session_ctx = getattr(execution_context, 'session_context', None)
        if not session_ctx:
            raise ValueError("SessionContext не доступен")

        rows, raw_text, data_metadata = self._load_data_from_context(step_id, session_ctx, max_rows)

        if not rows and not raw_text:
            raise ValueError(f"Нет данных для step_id={step_id}. Убедитесь что шаг содержит observation с данными.")

        self._log_info(
            f"📦 [data_analysis] Загружено: {len(rows) if rows else 0} строк, {len(raw_text) if raw_text else 0} символов текста",
            event_type=LogEventType.INFO
        )

        # 3. Профилирование данных
        data_profile = {}
        if rows:
            data_profile = DataProfiler.profile_rows(rows)
        elif raw_text:
            data_profile = DataProfiler.profile_text(raw_text)

        # 4. Автовыбор режима
        if mode == "auto":
            mode = self._auto_select_mode(question, data_profile)
            self._log_info(f"🔄 [data_analysis] AUTO выбрал режим: {mode}", event_type=LogEventType.INFO)

        # 5. Выполнение анализа в выбранном режиме
        if mode == "python":
            result = await self._execute_python_mode(rows, question, data_profile, start_time)
        elif mode == "llm":
            result = await self._execute_llm_mode(rows, raw_text, question, data_profile, start_time, execution_context)
        elif mode == "semantic":
            result = await self._execute_semantic_mode(raw_text, question, data_profile, start_time, execution_context)
        else:
            raise ValueError(f"Неподдерживаемый режим: {mode}")

        # 6. Добавление метаданных
        result.setdefault("metadata", {})
        result["metadata"]["mode"] = mode
        result["metadata"]["processing_time_ms"] = (time.time() - start_time) * 1000
        result["metadata"]["rows_processed"] = len(rows) if rows else 0
        result["metadata"]["data_size_mb"] = data_metadata.get("size_mb", 0)

        if rows:
            result["metadata"]["columns"] = list(rows[0].keys()) if rows else []
        result["metadata"]["profile"] = data_profile

        # 7. Уверенность
        if "confidence" not in result:
            result["confidence"] = 0.8 if mode == "python" else 0.7

        return result

    def _auto_select_mode(self, question: str, data_profile: Dict[str, Any]) -> str:
        """
        Автовыбор режима на основе вопроса и профиля данных.

        АЛГОРИТМ:
        1. Если вопрос про числа/суммы и данные табличные → python
        2. Если вопрос про текст/смысл и данные текстовые → semantic
        3. Иначе → llm (универсальный)

        ARGS:
        - question: str — вопрос пользователя
        - data_profile: Dict — профиль данных

        RETURNS:
        - str: режим (python/llm/semantic)
        """
        if DataProfiler.should_use_python_mode(question, {"type": "tabular", "profile": data_profile}):
            return "python"

        if DataProfiler.should_use_semantic_mode(question, {"type": "text", "profile": data_profile}):
            return "semantic"

        return "llm"  # default

    async def _execute_python_mode(
        self,
        rows: List[Dict[str, Any]],
        question: str,
        data_profile: Dict[str, Any],
        start_time: float
    ) -> Dict[str, Any]:
        """
        Детерминированный режим через AnalyticsEngine.

        БЕЗ LLM — только безопасные операции:
        - filter, group_by, aggregate, sort, limit
        - describe для базовой статистики

        ARGS:
        - rows: List[Dict] — табличные данные
        - question: str — вопрос
        - data_profile: Dict — профиль
        - start_time: float — время начала

        RETURNS:
        - Dict с результатом
        """
        self._log_info("🐍 [data_analysis] PYTHON mode — AnalyticsEngine", event_type=LogEventType.INFO)

        if not rows:
            return {
                "answer": "Нет табличных данных для анализа",
                "stats": {},
                "confidence": 0.0
            }

        # describe для базовой статистики
        describe_result = AnalyticsEngine.describe(rows)

        # Попытка ответить на вопрос через агрегацию
        answer, stats = self._answer_question_via_analytics(question, rows, data_profile)

        return {
            "answer": answer,
            "stats": stats,
            "profile": data_profile,
            "confidence": 0.9
        }

    def _answer_question_via_analytics(
        self,
        question: str,
        rows: List[Dict[str, Any]],
        data_profile: Dict[str, Any]
    ) -> tuple:
        """
        Ответ на вопрос через AnalyticsEngine.

        АЛГОРИТМ:
        1. Парсим вопрос на ключевые слова
        2. Строим DSL операцию
        3. Выполняем через AnalyticsEngine
        4. Формируем ответ

        ARGS:
        - question: str — вопрос
        - rows: List[Dict] — данные
        - data_profile: Dict — профиль

        RETURNS:
        - (answer: str, stats: dict)
        """
        question_lower = question.lower()
        stats = {}
        answer_parts = []

        # Найдем числовые колонки
        numeric_cols = []
        for col in data_profile.get("columns", []):
            if col.get("type") in ("integer", "float"):
                numeric_cols.append(col["name"])

        # Сумма
        if any(kw in question_lower for kw in ["сумма", "sum", "итог", "всего"]):
            for col in numeric_cols:
                values = [r.get(col) for r in rows if r.get(col) is not None]
                if values:
                    total = sum(float(v) for v in values if isinstance(v, (int, float)))
                    stats[f"{col}_sum"] = round(total, 2)
                    answer_parts.append(f"Сумма по {col}: {total:.2f}")

        # Среднее
        if any(kw in question_lower for kw in ["средн", "avg", "mean"]):
            for col in numeric_cols:
                values = [r.get(col) for r in rows if r.get(col) is not None]
                if values:
                    numeric = [float(v) for v in values if isinstance(v, (int, float))]
                    if numeric:
                        avg = sum(numeric) / len(numeric)
                        stats[f"{col}_mean"] = round(avg, 2)
                        answer_parts.append(f"Среднее по {col}: {avg:.2f}")

        # Количество
        if any(kw in question_lower for kw in ["сколько", "count", "колич", "сколько всего"]):
            stats["row_count"] = len(rows)
            answer_parts.append(f"Всего записей: {len(rows)}")

        # Min/Max
        if any(kw in question_lower for kw in ["min", "минимум", "наименьш"]):
            for col in numeric_cols:
                values = [r.get(col) for r in rows if r.get(col) is not None]
                if values:
                    numeric = [float(v) for v in values if isinstance(v, (int, float))]
                    if numeric:
                        stats[f"{col}_min"] = min(numeric)
                        answer_parts.append(f"Минимум по {col}: {min(numeric):.2f}")

        if any(kw in question_lower for kw in ["max", "максимум", "наибольш"]):
            for col in numeric_cols:
                values = [r.get(col) for r in rows if r.get(col) is not None]
                if values:
                    numeric = [float(v) for v in values if isinstance(v, (int, float))]
                    if numeric:
                        stats[f"{col}_max"] = max(numeric)
                        answer_parts.append(f"Максимум по {col}: {max(numeric):.2f}")

        # Если ничего не нашли — даем общую статистику
        if not answer_parts:
            answer_parts.append(f"Всего записей: {len(rows)}")
            for col in numeric_cols[:3]:  # Первые 3 числовые
                values = [r.get(col) for r in rows if r.get(col) is not None]
                if values:
                    numeric = [float(v) for v in values if isinstance(v, (int, float))]
                    if numeric:
                        stats[f"{col}_sum"] = round(sum(numeric), 2)
                        stats[f"{col}_mean"] = round(sum(numeric)/len(numeric), 2)

        answer = "\n".join(answer_parts) if answer_parts else "Анализ завершен"
        return answer, stats

    async def _execute_llm_mode(
        self,
        rows: List[Dict[str, Any]],
        raw_text: Optional[str],
        question: str,
        data_profile: Dict[str, Any],
        start_time: float,
        execution_context: Any
    ) -> Dict[str, Any]:
        """
        Режим LLM — интерпретация данных через LLM.

        АРХИТЕКТУРА:
        1. Формируем промпт с профилем данных
        2. Вызываем LLM через executor с structured output
        3. Парсим ответ

        ARGS:
        - rows: List[Dict] — табличные данные
        - raw_text: str — текстовые данные
        - question: str — вопрос
        - data_profile: Dict — профиль
        - start_time: float — время начала
        - execution_context: Any — контекст

        RETURNS:
        - Dict с результатом
        """
        self._log_info("🧠 [data_analysis] LLM mode — вызов LLM", event_type=LogEventType.INFO)

        # Подготовка данных для промпта
        data_for_prompt = ""
        if rows:
            # Ограничиваем строки для экономии токенов
            sample_rows = rows[:50]
            data_for_prompt = json.dumps(sample_rows, ensure_ascii=False, indent=2)
        elif raw_text:
            # Ограничиваем текст
            data_for_prompt = raw_text[:8000]

        # Получаем промпт
        prompt_obj = self.get_prompt("data_analysis.analyze_step_data")
        if not prompt_obj:
            raise ValueError("Промпт для анализа данных не найден")

        # Рендерим промпт
        rendered_prompt = self._render_prompt(
            prompt_obj.content,
            {
                "step_id": "current",
                "question": question,
                "raw_data": data_for_prompt,
                "profile": json.dumps(data_profile, ensure_ascii=False, indent=2)
            }
        )

        # Получаем схему выхода
        output_schema = self.get_output_contract("data_analysis.analyze_step_data")

        # Вызов LLM через executor
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
                "max_tokens": 2000
            },
            context=execution_context
        )

        # Проверка на ошибку
        if llm_result.status != ExecutionStatus.COMPLETED:
            raise ValueError(f"Ошибка LLM: {llm_result.error}")

        # Получаем структурированные данные
        if hasattr(llm_result.result, 'model_dump'):
            answer_data = llm_result.result.model_dump()
        elif hasattr(llm_result.result, 'dict'):
            answer_data = llm_result.result.dict()
        else:
            answer_data = llm_result.result if llm_result.result else {}

        return answer_data

    async def _execute_semantic_mode(
        self,
        raw_text: Optional[str],
        question: str,
        data_profile: Dict[str, Any],
        start_time: float,
        execution_context: Any
    ) -> Dict[str, Any]:
        """
        Режим SEMANTIC — работа с текстовыми данными.

        АРХИТЕКТУРА:
        1. Чанкинг текста если большой
        2. Вызов LLM для каждого чанка
        3. Агрегация результатов

        ARGS:
        - raw_text: str — текстовые данные
        - question: str — вопрос
        - data_profile: Dict — профиль
        - start_time: float — время начала
        - execution_context: Any — контекст

        RETURNS:
        - Dict с результатом
        """
        self._log_info("📝 [data_analysis] SEMANTIC mode — работа с текстом", event_type=LogEventType.INFO)

        if not raw_text:
            return {
                "answer": "Нет текстовых данных для анализа",
                "confidence": 0.0
            }

        # Чанкинг если текст большой
        chunks = self._chunk_text(raw_text, max_chars=4000)
        self._log_info(f"📄 [data_analysis] Текст разбит на {len(chunks)} чанков", event_type=LogEventType.INFO)

        # Если один чанк — вызываем LLM один раз
        if len(chunks) == 1:
            return await self._analyze_text_chunk(chunks[0], question, execution_context)

        # Если много чанков — анализируем каждый и агрегируем
        answers = []
        for i, chunk in enumerate(chunks):
            self._log_info(f"📄 [data_analysis] Анализ чанка {i+1}/{len(chunks)}", event_type=LogEventType.INFO)
            result = await self._analyze_text_chunk(chunk, question, execution_context)
            answers.append(result.get("answer", ""))

        # Агрегируем ответы
        aggregated_answer = "\n\n".join(answers)

        return {
            "answer": aggregated_answer,
            "profile": data_profile,
            "confidence": 0.7
        }

    def _chunk_text(self, text: str, max_chars: int = 4000) -> List[str]:
        """
        Разбиение текста на чанки.

        СТРАТЕГИЯ:
        1. По абзацам (двойные переносы)
        2. По предложения (если абзацы большие)
        3. По символам (fallback)

        ARGS:
        - text: str — текст
        - max_chars: int — максимум символов на чанк

        RETURNS:
        - List[str] — чанки
        """
        if len(text) <= max_chars:
            return [text]

        chunks = []
        current_chunk = ""

        # По абзацам
        paragraphs = text.split('\n\n')
        for para in paragraphs:
            if len(current_chunk) + len(para) > max_chars and current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = para
            else:
                current_chunk += "\n\n" + para if current_chunk else para

        if current_chunk:
            chunks.append(current_chunk.strip())

        # Если чанки всё ещё большие — делим по предложениям
        final_chunks = []
        for chunk in chunks:
            if len(chunk) > max_chars:
                sentences = chunk.replace('. ', '.|').split('|')
                sub_chunk = ""
                for sent in sentences:
                    if len(sub_chunk) + len(sent) > max_chars and sub_chunk:
                        final_chunks.append(sub_chunk.strip())
                        sub_chunk = sent
                    else:
                        sub_chunk += sent
                if sub_chunk:
                    final_chunks.append(sub_chunk.strip())
            else:
                final_chunks.append(chunk)

        return final_chunks if final_chunks else [text]

    async def _analyze_text_chunk(
        self,
        chunk: str,
        question: str,
        execution_context: Any
    ) -> Dict[str, Any]:
        """
        Анализ одного чанка текста через LLM.

        ARGS:
        - chunk: str — текст чанка
        - question: str — вопрос
        - execution_context: Any — контекст

        RETURNS:
        - Dict с результатом
        """
        prompt_obj = self.get_prompt("data_analysis.analyze_step_data")
        if not prompt_obj:
            raise ValueError("Промпт не найден")

        rendered_prompt = self._render_prompt(
            prompt_obj.content,
            {
                "step_id": "current",
                "question": question,
                "raw_data": chunk[:8000],
                "profile": "text"
            }
        )

        output_schema = self.get_output_contract("data_analysis.analyze_step_data")

        llm_result = await self.executor.execute_action(
            action_name="llm.generate_structured",
            parameters={
                "prompt": rendered_prompt,
                "structured_output": {
                    "output_model": "data_analysis.analyze_step_data.output",
                    "schema_def": output_schema if output_schema else {},
                    "max_retries": 2,
                    "strict_mode": True
                },
                "temperature": 0.1,
                "max_tokens": 1500
            },
            context=execution_context
        )

        if llm_result.status != ExecutionStatus.COMPLETED:
            return {"answer": f"Ошибка LLM: {llm_result.error}", "confidence": 0.0}

        if hasattr(llm_result.result, 'model_dump'):
            return llm_result.result.model_dump()
        elif hasattr(llm_result.result, 'dict'):
            return llm_result.result.dict()
        return llm_result.result or {}

    # ─────────────────────────────────────────────────────────────────
    # Методы загрузки данных
    # ─────────────────────────────────────────────────────────────────

    def _load_data_from_context(
        self,
        step_id: str,
        session_ctx,
        max_rows: int = 10000
    ) -> tuple:
        """
        Загрузка сырых данных шага из SessionContext.

        АЛГОРИТМ:
        1. Найти observation по step_id
        2. Извлечь rows или text
        3. Вернуть (rows, raw_text, metadata)

        ВОЗВРАЩАЕТ:
        - (rows: List[Dict], raw_text: str, metadata: dict)
        """
        if not hasattr(session_ctx, 'data_context'):
            return [], "", {}

        items = session_ctx.data_context.get_all_items()

        for item in items:
            meta = item.metadata
            if not meta:
                continue

            add_data = meta.additional_data or {}
            meta_step_id = add_data.get("step_id")
            meta_step_number = meta.step_number

            if meta_step_id == step_id or str(meta_step_number) == str(step_id):
                content = item.content
                if content:
                    if isinstance(content, dict):
                        # rows
                        rows = content.get("rows", [])
                        if rows:
                            # Ограничиваем строки
                            rows = rows[:max_rows]
                            metadata = {
                                "source_type": "session_context",
                                "step_id": step_id,
                                "size_mb": len(json.dumps(rows).encode('utf-8')) / (1024 * 1024)
                            }
                            return rows, "", metadata

                        # text
                        raw = content.get("content", content.get("raw_data", content.get("data", "")))
                        if raw:
                            metadata = {
                                "source_type": "session_context",
                                "step_id": step_id,
                                "size_mb": len(str(raw).encode('utf-8')) / (1024 * 1024)
                            }
                            return [], str(raw), metadata

                    elif isinstance(content, list):
                        # Прямой список rows
                        rows = content[:max_rows]
                        metadata = {
                            "source_type": "session_context",
                            "step_id": step_id,
                            "size_mb": len(json.dumps(rows).encode('utf-8')) / (1024 * 1024)
                        }
                        return rows, "", metadata

        return [], "", {}

    # ─────────────────────────────────────────────────────────────────
    # Вспомогательные методы
    # ─────────────────────────────────────────────────────────────────

    def _render_prompt(self, prompt: str, variables: Dict[str, Any]) -> str:
        """Рендеринг промпта с подстановкой переменных."""
        import re
        result = prompt
        for key, value in variables.items():
            placeholder = "{" + key + "}"
            result = result.replace(placeholder, str(value))

        # Удаляем оставшиеся плейсхолдеры
        result = re.sub(r'\{[a-z_]+\}', '', result)
        return result
