"""
Навык анализа данных с LLM и MapReduce.

АРХИТЕКТУРА:
- INPUT: step_id → получение данных из контекста
- MAP: Разбиение на чанки → Параллельный LLM-анализ
- REDUCE: Иерархическое (tree) объединение ответов через LLM

УЛУЧШЕНИЯ v2:
- Schema-aware chunking: схема данных инжектится в каждый чанк
- Tree Reduce: O(log N) вместо O(N) вызовов LLM
- Early filtering: фильтрация пустых/мусорных результатов Map-фазы
- Adaptive chars_per_token: динамический расчёт для RU/EN текста
- Retry logic: tenacity для устойчивости к сбоям

ИСПОЛЬЗОВАНИЕ:
    result = await executor.execute_action(
        action_name="data_analysis.analyze_step_data",
        parameters={
            "question": "Какие ключевые темы?",
            "step_id": 1
        },
        context=execution_context
    )
"""
import asyncio
import time
import json
import logging
import re
from typing import List, Dict, Any, Optional

from core.components.skills.skill import Skill
from core.models.data.capability import Capability
from core.models.data.execution import ExecutionStatus
from core.infrastructure.logging.event_types import LogEventType

log = logging.getLogger(__name__)


class DataAnalysisSkill(Skill):
    name: str = "data_analysis"

    DEFAULT_CONTEXT_WINDOW = 8192
    DEFAULT_MAX_NEW_TOKENS = 2000
    DEFAULT_RESERVE_TOKENS = 500
    DEFAULT_MAX_CONCURRENT = 5
    DEFAULT_CHARS_PER_TOKEN = 3.0
    CHUNK_SAFETY_MARGIN = 0.85
    REDUCE_SAFETY_FACTOR = 0.7
    MERGE_BATCH_SIZE = 3
    RETRY_MAX_ATTEMPTS = 3
    RETRY_BASE_DELAY = 1.0

    @property
    def description(self) -> str:
        return "Анализ данных с LLM и MapReduce"

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
        self._context_window = self.DEFAULT_CONTEXT_WINDOW
        self._max_new_tokens = self.DEFAULT_MAX_NEW_TOKENS
        self._chars_per_token = self.DEFAULT_CHARS_PER_TOKEN
        self._schema_cache: Dict[str, str] = {}

    def _calculate_max_chars(
        self,
        prompt_chars: int,
        safety_factor: float = None
    ) -> int:
        """Расчёт максимального размера контента в символах с адаптивным CHARS_PER_TOKEN."""
        if safety_factor is None:
            safety_factor = self.CHUNK_SAFETY_MARGIN

        prompt_tokens = prompt_chars / self._chars_per_token
        available_tokens = (
            self._context_window
            - self._max_new_tokens
            - self.DEFAULT_RESERVE_TOKENS
            - prompt_tokens
        )
        max_content_tokens = max(available_tokens, 1000) * safety_factor
        return int(max_content_tokens * self._chars_per_token)

    def _detect_charset_density(self, text: str) -> float:
        """Определение плотности текста для адаптивного расчёта токенов.

        Русский текст плотнее (≈2.0-2.5 символа/токен), английкий разреженнее (≈4.0).
        """
        if not text:
            return self.DEFAULT_CHARS_PER_TOKEN

        cyrillic_ratio = sum(1 for c in text[:1000] if '\u0400' <= c <= '\u04FF') / min(len(text), 1000)

        if cyrillic_ratio > 0.3:
            return 2.2
        elif cyrillic_ratio > 0.1:
            return 2.5
        else:
            return 3.5

    def _update_llm_config(self, execution_context: Any, sample_text: str = "") -> None:
        """Обновляет LLM конфиг из контекста или использует значения по умолчанию."""
        try:
            app_ctx = getattr(execution_context, 'application_context', None)
            if app_ctx is None and hasattr(execution_context, 'session_context'):
                app_ctx = getattr(execution_context.session_context, 'application_context', None)

            if app_ctx and hasattr(app_ctx, 'infrastructure_context'):
                infra = app_ctx.infrastructure_context
                if hasattr(infra, 'resource_registry') and infra.resource_registry:
                    from core.models.enums.common_enums import ResourceType
                    default_llm_info = infra.resource_registry.get_default_resource(ResourceType.LLM)
                    if default_llm_info and default_llm_info.instance:
                        provider = default_llm_info.instance
                        self._context_window = getattr(provider, 'n_ctx', self.DEFAULT_CONTEXT_WINDOW)
                        self._max_new_tokens = getattr(provider, 'max_tokens', self.DEFAULT_MAX_NEW_TOKENS)

                        provider_model = getattr(provider, 'model_name', "") or ""
                        if any(kw in provider_model.lower() for kw in ['gpt-4', 'claude', 'gemini']):
                            self._context_window = max(self._context_window, 32000)
        except Exception:
            self._context_window = self.DEFAULT_CONTEXT_WINDOW
            self._max_new_tokens = self.DEFAULT_MAX_NEW_TOKENS

        if sample_text:
            self._chars_per_token = self._detect_charset_density(sample_text)

    def get_capabilities(self) -> List[Capability]:
        return [
            Capability(
                name="data_analysis.analyze_step_data",
                description="Анализ данных шага с LLM и MapReduce",
                skill_name=self.name,
                supported_strategies=["react"],
                visible=True,
                meta={
                    "mapreduce": True
                }
            )
        ]

    async def initialize(self) -> bool:
        return await super().initialize()

    def _get_event_type_for_success(self) -> str:
        return "skill.data_analysis.executed"

    def _get_step_data(self, execution_context: Any, step_id: int) -> Any:
        """Получает данные шага из data_context через observation_item_ids."""
        session = None

        if hasattr(execution_context, 'session_context'):
            session = execution_context.session_context
        elif hasattr(execution_context, 'step_context'):
            session = execution_context

        if session is None:
            return None

        if not hasattr(session, 'step_context') or not hasattr(session, 'data_context'):
            return None

        steps = session.step_context.steps
        if not isinstance(steps, list):
            return None

        step = next((s for s in steps if s.step_number == step_id), None)
        if step is None:
            return None

        if not hasattr(step, 'observation_item_ids') or not step.observation_item_ids:
            return None

        obs_id = step.observation_item_ids[0]
        obs_item = session.data_context.get_item(obs_id, raise_on_missing=False)

        if obs_item is None:
            return None

        return obs_item.content if hasattr(obs_item, 'content') else obs_item

    def _extract_schema(self, data: Any) -> Optional[str]:
        """Извлекает схему данных из List[Dict] для инжекта в чанки."""
        if isinstance(data, list) and data:
            if isinstance(data[0], dict):
                headers = list(data[0].keys())
                self._schema_cache['headers'] = headers
                return "СТРУКТУРА ДАННЫХ: " + ", ".join(headers)
        elif isinstance(data, str):
            lines = data.split('\n')
            if lines and '|' in lines[0]:
                header_parts = [p.strip() for p in lines[0].split('|') if p.strip()]
                if header_parts:
                    self._schema_cache['headers'] = header_parts
                    return "СТРУКТУРА ДАННЫХ: " + ", ".join(header_parts)
        return None

    def _inject_schema_to_chunks(
        self,
        chunks: List[Dict[str, Any]],
        schema: Optional[str],
        input_type: str
    ) -> List[Dict[str, Any]]:
        """Инжектирует схему в каждый чанк для сохранения семантики полей."""
        if not schema or input_type != "rows":
            return chunks

        schema_header = f"{schema}\n\nФАКТЫ:"
        for chunk in chunks:
            if not chunk.get("content", "").startswith("СТРУКТУРА"):
                chunk["content"] = schema_header + "\n" + chunk["content"]

        return chunks

    async def _execute_impl(
        self,
        capability: Capability,
        parameters: Dict[str, Any],
        execution_context: Any
    ) -> Dict[str, Any]:
        start_time = time.time()

        params_dict = self._normalize_parameters(parameters)

        question = params_dict.get("question")
        step_id = params_dict.get("step_id")

        if not question:
            raise ValueError("Параметр 'question' обязателен")
        if step_id is None:
            raise ValueError("Параметр 'step_id' обязателен")

        data = self._get_step_data(execution_context, step_id)

        if data is None:
            self._log_warning(
                f"❌ Данные шага {step_id} не найдены. "
                f"execution_context type={type(execution_context).__name__}",
                event_type=LogEventType.WARNING
            )
            raise ValueError(f"Данные шага {step_id} не найдены")

        sample_text = str(data)[:1000] if data else ""
        self._update_llm_config(execution_context, sample_text)

        max_chunk_chars = self._calculate_max_chars(len(question) + 500)

        self._log_info(
            f"⚙️ [data_analysis] LLM: context={self._context_window}, "
            f"max_new={self._max_new_tokens}, chars_per_token={self._chars_per_token:.2f}, "
            f"max_chunk_chars={max_chunk_chars}",
            event_type=LogEventType.INFO
        )

        from core.infrastructure.providers.vector.chunking_service import ChunkingService
        chunking_service = ChunkingService(
            chunk_size_chars=max_chunk_chars,
            chunk_size_rows=50
        )

        schema = self._extract_schema(data)

        if isinstance(data, list):
            chunks = chunking_service.chunk_rows(data)
            self._log_info(
                f"📊 [data_analysis] Шаг {step_id}: {len(data)} строк → {len(chunks)} чанков",
                event_type=LogEventType.INFO
            )
            input_type = "rows"
        elif isinstance(data, str):
            chunks = chunking_service.chunk_text(data)
            self._log_info(
                f"📄 [data_analysis] Шаг {step_id}: {len(data)} символов → {len(chunks)} чанков",
                event_type=LogEventType.INFO
            )
            input_type = "text"
        else:
            data_str = str(data)
            chunks = chunking_service.chunk_text(data_str)
            input_type = "unknown"

        chunks = self._inject_schema_to_chunks(chunks, schema, input_type)

        summaries = await self._map_phase(chunks, question, execution_context)

        summaries = self._filter_empty_summaries(summaries)

        if not summaries:
            answer = "Не удалось извлечь релевантную информацию из данных"
        else:
            max_batch_chars = self._calculate_max_chars(len(question) + 500)
            answer = await self._tree_reduce(summaries, question, execution_context, max_batch_chars)

        processing_time = round((time.time() - start_time) * 1000, 2)

        await self._save_result_to_context(
            execution_context=execution_context,
            question=question,
            answer=answer,
            step_id=step_id,
            metadata={
                "input_type": input_type,
                "chunks_created": len(chunks),
                "chunks_analyzed": len(summaries),
                "processing_time_ms": processing_time,
                "chars_per_token": self._chars_per_token
            }
        )

        return {
            "answer": answer,
            "execution_status": "success",
            "confidence": 0.85,
            "executed_operations": [f"map:{len(chunks)}", "reduce"],
            "metadata": {
                "mode_used": "mapreduce",
                "input_type": input_type,
                "step_id": step_id,
                "chunks_created": len(chunks),
                "chunks_analyzed": len(summaries),
                "processing_time_ms": processing_time
            }
        }

    def _filter_empty_summaries(
        self,
        summaries: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Фильтрует пустые и мусорные результаты Map-фазы."""
        noise_patterns = [
            r'^нет\s+(данных|информации|результат)',
            r'^не\s+удалось',
            r'^\s*$',
            r'^(не\s+применимо|no\s+data)',
        ]

        valid = []
        for s in summaries:
            content = self._safe_get_content(s.get("content"))
            if not content or len(content.strip()) < 20:
                continue

            content_lower = content.lower()
            is_noise = False
            for pattern in noise_patterns:
                if re.search(pattern, content_lower):
                    is_noise = True
                    break

            if not is_noise:
                valid.append(s)

        if len(valid) < len(summaries):
            log.info(f"[data_analysis] Filtered {len(summaries) - len(valid)} empty/noisy summaries")

        return valid

    def _safe_get_content(self, content: Any) -> str:
        """Безопасное извлечение строки из content (может быть dict, str, etc)."""
        if content is None:
            return ""
        if isinstance(content, str):
            return content
        if isinstance(content, dict):
            return str(content)
        return str(content)

    async def _save_result_to_context(
        self,
        execution_context: Any,
        question: str,
        answer: str,
        step_id: int,
        metadata: Dict[str, Any]
    ) -> None:
        try:
            session_context = self._get_session_context(execution_context)
            if not session_context:
                self._log_warning("Не удалось получить session_context для сохранения результата")
                return

            result_content = f"""=== РЕЗУЛЬТАТ АНАЛИЗА ===
Вопрос: {question}

Ответ:
{answer}

---
Метаданные: {metadata}
"""
            session_context.record_observation(
                observation_data=result_content,
                source="data_analysis.analyze_step_data",
                step_number=step_id + 1,
                metadata={
                    "skill": "data_analysis",
                    "question": question,
                    **metadata
                }
            )
            self._log_info(
                f"💾 Результат анализа сохранён в контекст (step={step_id + 1})",
                event_type=LogEventType.INFO
            )
        except Exception as e:
            self._log_warning(f"Не удалось сохранить результат в контекст: {e}", event_type=LogEventType.WARNING)

    def _get_session_context(self, context: Any):
        if hasattr(context, 'session_context'):
            sc = context.session_context
            if sc and hasattr(sc, 'record_observation'):
                return sc
        if hasattr(context, '_session_context'):
            sc = context._session_context
            if sc and hasattr(sc, 'record_observation'):
                return sc
        return None

    def _normalize_parameters(self, parameters: Any) -> Dict[str, Any]:
        if hasattr(parameters, 'model_dump'):
            return parameters.model_dump()
        elif hasattr(parameters, 'dict'):
            return parameters.dict()
        elif isinstance(parameters, dict):
            return parameters
        raise ValueError(f"Неподдерживаемый тип параметров: {type(parameters)}")

    def _get_active_executor(self, execution_context: Any):
        """Получает executor из execution_context."""
        if hasattr(execution_context, 'executor'):
            return execution_context.executor
        if hasattr(execution_context, 'session_context') and hasattr(execution_context.session_context, 'executor'):
            return execution_context.session_context.executor
        return self.executor

    async def _map_phase(
        self,
        chunks: List[Dict[str, Any]],
        question: str,
        execution_context: Any
    ) -> List[Dict[str, Any]]:
        if len(chunks) == 1:
            return [await self._analyze_chunk_with_retry(chunks[0], question, execution_context)]

        semaphore = asyncio.Semaphore(self.DEFAULT_MAX_CONCURRENT)

        async def analyze_with_limit(chunk: Dict[str, Any]) -> Dict[str, Any]:
            async with semaphore:
                return await self._analyze_chunk_with_retry(chunk, question, execution_context)

        tasks = [analyze_with_limit(chunk) for chunk in chunks]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        summaries = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                self._log_warning(
                    f"⚠️ [text_analysis] Ошибка анализа чанка {i}: {result}",
                    event_type=LogEventType.WARNING
                )
                summaries.append({"content": "", "chunk_id": i, "error": str(result)})
            else:
                summaries.append(result)

        return summaries

    async def _analyze_chunk_with_retry(
        self,
        chunk: Dict[str, Any],
        question: str,
        execution_context: Any
    ) -> Dict[str, Any]:
        """Анализ чанка с retry логикой."""
        last_error = None
        for attempt in range(self.RETRY_MAX_ATTEMPTS):
            try:
                result = await self._analyze_chunk(chunk, question, execution_context)
                if result.get("content"):
                    return result
                if attempt < self.RETRY_MAX_ATTEMPTS - 1:
                    await asyncio.sleep(self.RETRY_BASE_DELAY * (attempt + 1))
            except Exception as e:
                last_error = e
                if attempt < self.RETRY_MAX_ATTEMPTS - 1:
                    await asyncio.sleep(self.RETRY_BASE_DELAY * (attempt + 1))

        return {"content": "", "chunk_id": chunk.get("chunk_id", 0), "error": str(last_error)}

    async def _analyze_chunk(
        self,
        chunk: Dict[str, Any],
        question: str,
        execution_context: Any
    ) -> Dict[str, Any]:
        content = self._safe_get_content(chunk.get("content"))
        chunk_id = chunk.get("chunk_id", 0)

        if len(content) < 20:
            return {"content": "", "chunk_id": chunk_id}

        prompt = self._build_analyze_prompt(content, question, chunk_id)
        executor = self._get_active_executor(execution_context)

        try:
            result = await executor.execute_action(
                action_name="llm.generate",
                parameters={
                    "prompt": prompt,
                    "temperature": 0.2,
                    "max_tokens": 2000
                },
                context=execution_context
            )

            if result.status == ExecutionStatus.COMPLETED:
                return {"content": self._safe_get_content(result.result), "chunk_id": chunk_id}
            else:
                return {"content": "", "chunk_id": chunk_id, "error": "LLM failed"}

        except Exception as e:
            return {"content": "", "chunk_id": chunk_id, "error": str(e)}

    async def _tree_reduce(
        self,
        summaries: List[Dict[str, Any]],
        question: str,
        execution_context: Any,
        max_batch_chars: int = 3000
    ) -> str:
        """Иерархический (tree) reduce: O(log N) вместо O(N) вызовов LLM."""
        if not summaries:
            return "Нет данных для анализа"

        if len(summaries) == 1:
            return summaries[0].get("content", "")

        current_level = summaries
        iteration = 0

        while len(current_level) > 1:
            iteration += 1
            next_level = []

            for i in range(0, len(current_level), self.MERGE_BATCH_SIZE):
                batch = current_level[i:i + self.MERGE_BATCH_SIZE]

                if len(batch) == 1:
                    next_level.append(batch[0])
                else:
                    merged = await self._merge_batch(batch, question, execution_context)
                    next_level.append(merged)

            self._log_info(
                f"🌲 [data_analysis] Tree Reduce iteration {iteration}: "
                f"{len(current_level)} → {len(next_level)}",
                event_type=LogEventType.INFO
            )

            current_level = next_level

        return current_level[0].get("content", "") if current_level else ""

    async def _reduce_phase(
        self,
        summaries: List[Dict[str, Any]],
        question: str,
        execution_context: Any,
        max_batch_chars: int = 3000
    ) -> str:
        return await self._tree_reduce(summaries, question, execution_context, max_batch_chars)

    async def _batch_reduce(
        self,
        items: List[Dict[str, Any]],
        question: str,
        execution_context: Any,
        max_batch_chars: int = 3000
    ) -> str:
        if len(items) == 1:
            return items[0].get("content", "")

        batches = self._create_batches(items, max_batch_chars)

        self._log_info(
            f"🌲 [data_analysis] Reduce: {len(items)} items → {len(batches)} batches",
            event_type=LogEventType.INFO
        )

        merged_results = []
        for batch in batches:
            if len(batch) == 1:
                merged_results.append(batch[0])
            else:
                result = await self._merge_batch(batch, question, execution_context)
                merged_results.append(result)

        if len(merged_results) == 1:
            return merged_results[0].get("content", "")

        return await self._batch_reduce(merged_results, question, execution_context, max_batch_chars)

    def _create_batches(
        self,
        items: List[Dict[str, Any]],
        max_chars: int
    ) -> List[List[Dict[str, Any]]]:
        batches = []
        current_batch = []
        current_size = 0

        for item in items:
            item_content = item.get("content", "")
            item_size = len(item_content)

            if not current_batch:
                current_batch.append(item)
                current_size = item_size
            elif current_size + item_size <= max_chars:
                current_batch.append(item)
                current_size += item_size
            else:
                if current_batch:
                    batches.append(current_batch)
                current_batch = [item]
                current_size = item_size

        if current_batch:
            batches.append(current_batch)

        return batches

    async def _merge_batch_with_retry(
        self,
        batch: List[Dict[str, Any]],
        question: str,
        execution_context: Any
    ) -> Dict[str, Any]:
        """Слияние батча с retry логикой."""
        last_error = None
        for attempt in range(self.RETRY_MAX_ATTEMPTS):
            try:
                result = await self._merge_batch(batch, question, execution_context)
                if result.get("content"):
                    return result
                if attempt < self.RETRY_MAX_ATTEMPTS - 1:
                    await asyncio.sleep(self.RETRY_BASE_DELAY * (attempt + 1))
            except Exception as e:
                last_error = e
                if attempt < self.RETRY_MAX_ATTEMPTS - 1:
                    await asyncio.sleep(self.RETRY_BASE_DELAY * (attempt + 1))

        return {"content": "", "error": str(last_error)}

    async def _merge_batch(
        self,
        batch: List[Dict[str, Any]],
        question: str,
        execution_context: Any
    ) -> Dict[str, Any]:
        if len(batch) == 1:
            return batch[0]

        if len(batch) == 2:
            return await self._merge_pair(batch[0], batch[1], question, execution_context)

        contents = [self._safe_get_content(item.get("content")) for item in batch]
        combined = "\n\n---\n\n".join(contents)

        executor = self._get_active_executor(execution_context)
        prompt = self._build_merge_batch_prompt(contents, question)

        try:
            result = await executor.execute_action(
                action_name="llm.generate",
                parameters={
                    "prompt": prompt,
                    "temperature": 0.3,
                    "max_tokens": 2000
                },
                context=execution_context
            )

            if result.status == ExecutionStatus.COMPLETED:
                return {"content": self._safe_get_content(result.result) or combined}
        except Exception as e:
            self._log_warning(f"⚠️ [data_analysis] Merge batch error: {e}", event_type=LogEventType.WARNING)

        return {"content": combined}

    async def _merge_pair(
        self,
        item1: Dict[str, Any],
        item2: Dict[str, Any],
        question: str,
        execution_context: Any
    ) -> Dict[str, Any]:
        content1 = self._safe_get_content(item1.get("content"))
        content2 = self._safe_get_content(item2.get("content"))

        prompt = self._build_merge_prompt(content1, content2, question)
        executor = self._get_active_executor(execution_context)

        try:
            result = await executor.execute_action(
                action_name="llm.generate",
                parameters={
                    "prompt": prompt,
                    "temperature": 0.3,
                    "max_tokens": 2000
                },
                context=execution_context
            )

            if result.status == ExecutionStatus.COMPLETED:
                return {"content": self._safe_get_content(result.result) or f"{content1}\n\n{content2}"}
        except Exception as e:
            self._log_warning(f"⚠️ [data_analysis] Merge error: {e}", event_type=LogEventType.WARNING)

        return {"content": f"{content1}\n\n{content2}"}

    def _build_analyze_prompt(self, content: str, question: str, chunk_id: int = 0) -> str:
        system_prompt = self.get_prompt("data_analysis.analyze_step_data.system")
        user_prompt = self.get_prompt("data_analysis.analyze_step_data.user")

        if not system_prompt or not user_prompt:
            return self._build_analyze_prompt_fallback(content, question)

        system = system_prompt.content or ""
        user_template = user_prompt.content or ""

        user = self._render_prompt(user_template, {
            "question": question,
            "content": content,
            "chunk_number": str(chunk_id + 1)
        })

        return f"{system}\n\n{user}"

    def _build_merge_prompt(self, content1: str, content2: str, question: str) -> str:
        system_prompt = self.get_prompt("data_analysis.merge_step_data.system")
        user_prompt = self.get_prompt("data_analysis.merge_step_data.user")
        
        if not system_prompt or not user_prompt:
            return self._build_merge_prompt_fallback(content1, content2, question)
        
        system = system_prompt.content or ""
        user_template = user_prompt.content or ""
        
        user = self._render_prompt(user_template, {
            "question": question,
            "content1": content1,
            "content2": content2
        })
        
        return f"{system}\n\n{user}"

    def _build_merge_batch_prompt(self, contents: List[str], question: str) -> str:
        fragments = []
        for i, content in enumerate(contents, 1):
            fragments.append(f"=== ФРАГМЕНТ {i} ===\n{content}")

        combined = "\n\n".join(fragments)

        return f"""Объедини несколько фрагментов анализа в один связный ответ.

ВОПРОС: {question}

{combined}

Инструкции:
- Объедини информацию из всех фрагментов
- Убери дублирующиеся факты
- Сохрани все ключевые данные
- Пиши на русском языке
- Будь краток

Объединённый анализ:"""

    def _build_analyze_prompt_fallback(self, content: str, question: str) -> str:
        return f"""Проанализируй данные и ответь на вопрос.

ВОПРОС: {question}

ДАННЫЕ:
{content}

Инструкции:
- Отвечай ТОЛЬКО на основе предоставленных данных
- Если информации недостаточно, укажи это
- Пиши на русском языке
- Используй схему данных если она присутствует

Ответ:"""

    def _render_prompt(self, template: str, variables: Dict[str, Any]) -> str:
        result = template
        for key, value in variables.items():
            placeholder = "{" + key + "}"
            result = result.replace(placeholder, str(value))
        return result
