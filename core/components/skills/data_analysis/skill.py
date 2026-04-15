"""
Навык анализа данных с LLM и MapReduce.

АРХИТЕКТУРА:
- INPUT: text или rows (List[Dict])
- MAP: Разбиение на чанки → Параллельный LLM-анализ
- REDUCE: Объединение ответов через LLM

ИСПОЛЬЗОВАНИЕ:
    result = await skill.execute(
        capability=Capability(name="text_analysis.analyze"),
        parameters={
            "text": "Большой текст...",
            "question": "Какие ключевые темы?"
        },
        context=execution_context
    )
    
    # или rows:
    result = await skill.execute(
        parameters={
            "rows": [{"id": 1, "name": "Test"}, ...],
            "question": "Какие паттерны?"
        },
        context=execution_context
    )
"""
import asyncio
import time
import json
from typing import List, Dict, Any, Optional

from core.components.skills.skill import Skill
from core.models.data.capability import Capability
from core.models.data.execution import ExecutionStatus
from core.infrastructure.logging.event_types import LogEventType
from core.infrastructure.providers.vector.chunking_service import ChunkingService


class TextAnalysisSkill(Skill):
    name: str = "text_analysis"

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

    def get_capabilities(self) -> List[Capability]:
        return [
            Capability(
                name="text_analysis.analyze",
                description="Анализ данных с LLM. Поддерживает text и rows. Для больших данных использует MapReduce.",
                skill_name=self.name,
                supported_strategies=["react"],
                visible=True,
                meta={
                    "supports_chunking": True,
                    "mapreduce": True,
                    "input_types": ["text", "rows"],
                    "default_chunk_size_chars": 4000,
                    "default_chunk_size_rows": 50
                }
            )
        ]

    async def initialize(self) -> bool:
        return await super().initialize()

    def _get_event_type_for_success(self) -> str:
        return "skill.text_analysis.executed"

    async def _execute_impl(
        self,
        capability: Capability,
        parameters: Dict[str, Any],
        execution_context: Any
    ) -> Dict[str, Any]:
        start_time = time.time()

        params_dict = self._normalize_parameters(parameters)

        text = params_dict.get("text")
        rows = params_dict.get("rows")
        question = params_dict.get("question")

        if not question:
            raise ValueError("Параметр 'question' обязателен")

        if not text and not rows:
            raise ValueError("Параметр 'text' или 'rows' обязателен")

        meta = params_dict.get("meta", {})
        chunk_size_chars = meta.get("chunk_size_chars", 4000)
        chunk_size_rows = meta.get("chunk_size_rows", 50)
        max_concurrent = meta.get("max_concurrent", 5)

        chunking_service = ChunkingService(
            chunk_size_chars=chunk_size_chars,
            chunk_size_rows=chunk_size_rows
        )

        if rows:
            chunks = chunking_service.chunk_rows(rows)
            self._log_info(
                f"📊 [text_analysis] {len(rows)} строк → {len(chunks)} чанков",
                event_type=LogEventType.INFO
            )
        else:
            chunks = chunking_service.chunk_text(text)
            self._log_info(
                f"📄 [text_analysis] {len(text)} символов → {len(chunks)} чанков",
                event_type=LogEventType.INFO
            )

        summaries = await self._map_phase(chunks, question, execution_context, max_concurrent)

        answer = await self._reduce_phase(summaries, question, execution_context)

        processing_time = round((time.time() - start_time) * 1000, 2)

        return {
            "answer": answer,
            "execution_status": "success",
            "confidence": 0.85,
            "executed_operations": [f"map:{len(chunks)}", "reduce"],
            "metadata": {
                "mode_used": "mapreduce",
                "input_type": "rows" if rows else "text",
                "chunks_created": len(chunks),
                "chunks_analyzed": len(summaries),
                "processing_time_ms": processing_time
            }
        }

    def _normalize_parameters(self, parameters: Any) -> Dict[str, Any]:
        if hasattr(parameters, 'model_dump'):
            return parameters.model_dump()
        elif hasattr(parameters, 'dict'):
            return parameters.dict()
        elif isinstance(parameters, dict):
            return parameters
        raise ValueError(f"Неподдерживаемый тип параметров: {type(parameters)}")

    async def _map_phase(
        self,
        chunks: List[Dict[str, Any]],
        question: str,
        execution_context: Any,
        max_concurrent: int
    ) -> List[Dict[str, Any]]:
        if len(chunks) == 1:
            return [await self._analyze_chunk(chunks[0], question, execution_context)]

        semaphore = asyncio.Semaphore(max_concurrent)

        async def analyze_with_limit(chunk: Dict[str, Any]) -> Dict[str, Any]:
            async with semaphore:
                return await self._analyze_chunk(chunk, question, execution_context)

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

    async def _analyze_chunk(
        self,
        chunk: Dict[str, Any],
        question: str,
        execution_context: Any
    ) -> Dict[str, Any]:
        content = chunk.get("content", "")
        chunk_id = chunk.get("chunk_id", 0)

        if len(content) < 20:
            return {"content": "", "chunk_id": chunk_id}

        prompt = self._build_analyze_prompt(content, question)

        try:
            result = await self.executor.execute_action(
                action_name="llm.generate",
                parameters={
                    "prompt": prompt,
                    "temperature": 0.2,
                    "max_tokens": 1000
                },
                context=execution_context
            )

            if result.status == ExecutionStatus.COMPLETED:
                return {"content": result.result or "", "chunk_id": chunk_id}
            else:
                return {"content": "", "chunk_id": chunk_id, "error": "LLM failed"}

        except Exception as e:
            return {"content": "", "chunk_id": chunk_id, "error": str(e)}

    async def _reduce_phase(
        self,
        summaries: List[Dict[str, Any]],
        question: str,
        execution_context: Any
    ) -> str:
        if not summaries:
            return "Нет данных для анализа"

        valid_summaries = [s for s in summaries if s.get("content")]

        if not valid_summaries:
            return "Не удалось извлечь информацию"

        if len(valid_summaries) == 1:
            return valid_summaries[0].get("content", "")

        current = valid_summaries

        while len(current) > 1:
            merged = []

            for i in range(0, len(current), 2):
                if i + 1 < len(current):
                    pair = [current[i], current[i + 1]]
                    merged_result = await self._merge_pair(pair, question, execution_context)
                    merged.append(merged_result)
                else:
                    merged.append(current[i])

            current = merged

            self._log_info(
                f"🌲 [text_analysis] Reduce: {len(summaries)} → {len(current)}",
                event_type=LogEventType.INFO
            )

        final = current[0].get("content", "")

        if len(final) > 3000:
            final = await self._synthesize_final(final, question, execution_context)

        return final

    async def _merge_pair(
        self,
        pair: List[Dict[str, Any]],
        question: str,
        execution_context: Any
    ) -> Dict[str, Any]:
        content1 = pair[0].get("content", "")
        content2 = pair[1].get("content", "")

        combined = f"Часть 1:\n{content1}\n\nЧасть 2:\n{content2}"

        if len(combined) <= 2000:
            return {"content": combined}

        prompt = self._build_merge_prompt(content1, content2, question)

        try:
            result = await self.executor.execute_action(
                action_name="llm.generate",
                parameters={
                    "prompt": prompt,
                    "temperature": 0.3,
                    "max_tokens": 1500
                },
                context=execution_context
            )

            if result.status == ExecutionStatus.COMPLETED:
                return {"content": result.result or combined}
        except Exception as e:
            self._log_warning(f"⚠️ [text_analysis] Merge error: {e}", event_type=LogEventType.WARNING)

        return {"content": combined}

    async def _synthesize_final(
        self,
        content: str,
        question: str,
        execution_context: Any
    ) -> str:
        prompt = self._build_final_prompt(content, question)

        try:
            result = await self.executor.execute_action(
                action_name="llm.generate",
                parameters={
                    "prompt": prompt,
                    "temperature": 0.2,
                    "max_tokens": 2000
                },
                context=execution_context
            )

            if result.status == ExecutionStatus.COMPLETED:
                return result.result or content[:3000]
        except Exception:
            pass

        return content[:3000]

    def _build_analyze_prompt(self, content: str, question: str) -> str:
        truncated = content[:5000] if len(content) > 5000 else content
        return f"""Проанализируй данные и ответь на вопрос.

ВОПРОС: {question}

ДАННЫЕ:
{truncated}

Инструкции:
- Отвечай ТОЛЬКО на основе предоставленных данных
- Если информации недостаточно, укажи это
- Пиши на русском языке
- Будь краток

Ответ:"""

    def _build_merge_prompt(self, content1: str, content2: str, question: str) -> str:
        return f"""Объедини два фрагмента анализа в один связный ответ.

ВОПРОС: {question}

ФРАГМЕНТ 1:
{content1}

ФРАГМЕНТ 2:
{content2}

Инструкции:
- Объедини информацию из обоих фрагментов
- Убери дублирующиеся факты
- Сохрани все ключевые данные
- Пиши на русском языке

Объединённый анализ:"""

    def _build_final_prompt(self, content: str, question: str) -> str:
        truncated = content[:6000] if len(content) > 6000 else content
        return f"""Сократи текст анализа, сохранив ключевые факты.

ВОПРОС: {question}

ТЕКУЩИЙ АНАЛИЗ:
{truncated}

Инструкции:
- Сократи до основных фактов и выводов
- Сохрани важные цифры
- Убери повторы
- Пиши на русском языке

Сокращённый анализ:"""
