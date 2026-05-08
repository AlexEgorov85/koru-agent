"""
MapReduceStrategy — разбиение на чанки → параллельный анализ → объединение.

ЭТАПЫ:
1. Schema-aware chunking: схема данных инжектится в каждый чанк
2. MAP: Параллельный LLM-анализ чанков (asyncio.gather + семафор)
3. REDUCE: Иерархическое (tree) объединение ответов через LLM
4. Фильтрация пустых/мусорных результатов Map-фазы
"""
import asyncio
import re
from typing import Any, Dict, List

from core.components.skills.data_analysis.base_strategy import AbstractStrategy, AnalysisInput, AnalysisResult
from core.components.skills.data_analysis.prompts import render_prompt


class MapReduceStrategy(AbstractStrategy):
    """MapReduce: разбиение на чанки → параллельный анализ → tree reduce."""

    name = "mapreduce"

    DEFAULT_RESERVE_TOKENS = 500
    DEFAULT_MAX_CONCURRENT = 5
    CHUNK_SAFETY_MARGIN = 0.85
    MERGE_SAFETY_FACTOR = 0.7

    def can_handle(self, data: List[Dict], question: str) -> bool:
        return bool(data)

    async def execute(self, input_data: AnalysisInput) -> AnalysisResult:
        context_window = getattr(self._skill, '_context_window', 8192)
        max_new = getattr(self._skill, '_max_new_tokens', 2000)

        max_chunk_chars = self._calculate_max_chars(
            len(input_data.question) + 500, context_window, max_new
        )

        schema = self._extract_schema(input_data.data)

        chunks = self._chunk_data(input_data.data, max_chunk_chars)

        chunks = self._inject_schema(chunks, schema)

        summaries = await self._map_phase(chunks, input_data.question, input_data.execution_context)
        summaries = self._filter_empty_summaries(summaries)

        if not summaries:
            return AnalysisResult(
                answer="Не удалось извлечь релевантную информацию из данных",
                confidence=0.3,
                operations=[f"map:{len(chunks)}"],
                metadata={
                    "mode_used": "mapreduce",
                    "chunks_created": len(chunks),
                    "chunks_analyzed": 0,
                },
            )

        answer = await self._tree_reduce(
            summaries, input_data.question, input_data.execution_context,
            context_window, max_new,
        )

        return AnalysisResult(
            answer=answer,
            confidence=0.85,
            operations=[f"map:{len(chunks)}", "reduce"],
            metadata={
                "mode_used": "mapreduce",
                "chunks_created": len(chunks),
                "chunks_analyzed": len(summaries),
            },
        )

    def _calculate_max_chars(
        self, prompt_chars: int, context_window: int, max_new_tokens: int,
        safety_factor: float = None,
    ) -> int:
        if safety_factor is None:
            safety_factor = self.CHUNK_SAFETY_MARGIN
        prompt_tokens = prompt_chars / 3.0
        available = context_window - max_new_tokens - self.DEFAULT_RESERVE_TOKENS - prompt_tokens
        max_content_tokens = max(available, 1000) * safety_factor
        return int(max_content_tokens * 3.0)

    def _create_context_batches(
        self, items: List[Dict], question: str,
        context_window: int, max_new_tokens: int,
    ) -> List[List[Dict]]:
        """Группировка элементов в батчи, каждый помещается в контекстное окно."""
        prompt_overhead = len(question) + 500
        max_chars = self._calculate_max_chars(
            prompt_overhead, context_window, max_new_tokens,
            safety_factor=self.MERGE_SAFETY_FACTOR,
        )

        batches: List[List[Dict]] = []
        current: List[Dict] = []
        current_size = 0

        for item in items:
            size = len(str(item.get("content", "")))
            if not current:
                current.append(item)
                current_size = size
            elif current_size + size <= max_chars:
                current.append(item)
                current_size += size
            else:
                batches.append(current)
                current = [item]
                current_size = size

        if current:
            batches.append(current)

        return batches

    def _extract_schema(self, data: List[Dict]) -> str:
        if data and isinstance(data[0], dict):
            return "СТРУКТУРА ДАННЫХ: " + ", ".join(data[0].keys())
        return ""

    def _inject_schema(self, chunks: List[Dict], schema: str) -> List[Dict]:
        if not schema:
            return chunks
        prefix = f"{schema}\n\nФАКТЫ:"
        for chunk in chunks:
            if not chunk.get("content", "").startswith("СТРУКТУРА"):
                chunk["content"] = prefix + "\n" + chunk["content"]
        return chunks

    def _chunk_data(self, data: List[Dict], max_chunk_chars: int) -> List[Dict]:
        if not data:
            return [{"content": "", "chunk_id": 0}]

        from core.infrastructure.providers.vector.chunking_service import ChunkingService
        service = ChunkingService()
        return service.chunk_rows(data, max_chunk_chars=max_chunk_chars)

    async def _map_phase(
        self, chunks: List[Dict], question: str, execution_context: Any,
    ) -> List[Dict]:
        if not chunks:
            return []
        if len(chunks) == 1:
            return [await self._analyze_chunk(chunks[0], question, execution_context)]

        semaphore = asyncio.Semaphore(self.DEFAULT_MAX_CONCURRENT)

        async def run_with_semaphore(idx: int, chunk: Dict) -> Dict:
            async with semaphore:
                return await self._analyze_chunk(chunk, question, execution_context)

        tasks = [run_with_semaphore(i, chunk) for i, chunk in enumerate(chunks)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        valid = []
        for i, r in enumerate(results):
            if isinstance(r, Exception):
                continue
            if isinstance(r, dict) and r.get("content"):
                valid.append(r)

        return valid

    async def _analyze_chunk(self, chunk: Dict, question: str, execution_context: Any) -> Dict:
        content = str(chunk.get("content", ""))
        chunk_id = chunk.get("chunk_id", 0)

        if not content or len(content.strip()) < 20:
            return {"content": "", "chunk_id": chunk_id}

        system_prompt = self._skill.get_prompt("data_analysis.analyze_step_data.system")
        user_prompt = self._skill.get_prompt("data_analysis.analyze_step_data.user")

        if not system_prompt or not user_prompt:
            return {"content": "", "chunk_id": chunk_id}

        user = render_prompt(user_prompt.content or "", {
            "question": question,
            "content": content,
        })

        prompt = f"{system_prompt.content}\n\n{user}"
        executor = self._get_executor(execution_context)

        try:
            output_contract = self._skill.get_output_contract("data_analysis.analyze_step_data")
            if not output_contract:
                return {"content": "", "chunk_id": chunk_id}

            result = await executor.execute_action(
                action_name="llm.generate_structured",
                parameters={
                    "prompt": prompt,
                    "temperature": 0.2,
                    "structured_output": {
                        "output_model": "data_analysis.analyze_step_data.output",
                        "schema_def": output_contract,
                        "strict_mode": True,
                        "max_retries": 1,
                    },
                },
                context=execution_context,
            )

            from core.models.data.execution import ExecutionStatus
            if result.status == ExecutionStatus.COMPLETED and result.data:
                data = result.data
                if hasattr(data, 'model_dump'):
                    data = data.model_dump()
                elif not isinstance(data, dict):
                    data = {}
                text = data.get("answer", "")
                if text:
                    return {"content": str(text), "chunk_id": chunk_id}
        except Exception:
            pass

        return {"content": "", "chunk_id": chunk_id}

    def _filter_empty_summaries(self, summaries: List[Dict]) -> List[Dict]:
        noise_patterns = [
            r'^нет\s+(данных|информации|результат)',
            r'^не\s+удалось',
            r'^\s*$',
            r'^(не\s+применимо|no\s+data)',
        ]
        valid = []
        for s in summaries:
            content = str(s.get("content", ""))
            if not content or len(content.strip()) < 20:
                continue
            content_lower = content.lower()
            is_noise = any(re.search(p, content_lower) for p in noise_patterns)
            if not is_noise:
                valid.append(s)
        return valid

    async def _tree_reduce(
        self, summaries: List[Dict], question: str,
        execution_context: Any, context_window: int, max_new_tokens: int,
    ) -> str:
        """Иерархический reduce через _merge_batch с контекстно-зависимым батчингом."""
        if not summaries:
            return "Нет данных для анализа"
        if len(summaries) == 1:
            return str(summaries[0].get("content", ""))

        result = await self._merge_batch(
            summaries, question, execution_context, context_window, max_new_tokens,
        )
        return str(result.get("content", ""))

    async def _merge_batch(
        self, batch: List[Dict], question: str, execution_context: Any,
        context_window: int, max_new_tokens: int,
    ) -> Dict:
        """Контекстно-зависимое слияние: группировка → LLM → рекурсия."""
        if len(batch) == 1:
            return batch[0]

        sub_batches = self._create_context_batches(batch, question, context_window, max_new_tokens)

        if len(sub_batches) == 1:
            return await self._llm_merge(sub_batches[0], question, execution_context)

        merged = []
        for sub in sub_batches:
            if len(sub) == 1:
                merged.append(sub[0])
            else:
                result = await self._llm_merge(sub, question, execution_context)
                merged.append(result)

        return await self._merge_batch(
            merged, question, execution_context, context_window, max_new_tokens,
        )

    async def _llm_merge(
        self, items: List[Dict], question: str, execution_context: Any,
    ) -> Dict:
        """Слияние списка фрагментов через LLM с промптами из YAML."""
        contents = [str(item.get("content", "")) for item in items]

        if not contents:
            return {"content": ""}

        system_prompt = self._skill.get_prompt("data_analysis.merge_step_data.system")
        user_prompt = self._skill.get_prompt("data_analysis.merge_step_data.user")

        if not system_prompt or not user_prompt:
            return {"content": "\n\n---\n\n".join(contents)}

        fragments = "\n".join(
            f"=== ФРАГМЕНТ {i + 1} ===\n{c}" for i, c in enumerate(contents)
        )

        user = render_prompt(user_prompt.content or "", {
            "question": question,
            "fragments": fragments,
        })

        prompt = f"{system_prompt.content}\n\n{user}"

        executor = self._get_executor(execution_context)
        try:
            result = await executor.execute_action(
                action_name="llm.generate",
                parameters={"prompt": prompt, "temperature": 0.3, "max_tokens": 2000},
                context=execution_context,
            )

            from core.models.data.execution import ExecutionStatus
            if result.status == ExecutionStatus.COMPLETED and result.data:
                if isinstance(result.data, dict):
                    text = result.data.get("content", "") or result.data.get("text", "")
                else:
                    text = str(result.data)
                if text:
                    return {"content": text}
        except Exception:
            pass

        combined = "\n\n---\n\n".join(contents)
        return {"content": combined}


