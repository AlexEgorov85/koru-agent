"""
Навык анализа данных с LLM и MapReduce.

АРХИТЕКТУРА:
- INPUT: step_id → получение данных из контекста
- MAP: Разбиение на чанки → Параллельный LLM-анализ
- REDUCE: Объединение ответов через LLM

ИСПОЛЬЗОВАНИЕ:
    result = await executor.execute_action(
        action_name="text_analysis.analyze",
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
from typing import List, Dict, Any, Optional

from core.components.skills.skill import Skill
from core.models.data.capability import Capability
from core.models.data.execution import ExecutionStatus
from core.infrastructure.logging.event_types import LogEventType
from core.infrastructure.providers.vector.chunking_service import ChunkingService


class TextAnalysisSkill(Skill):
    name: str = "text_analysis"

    DEFAULT_CHUNK_SIZE_CHARS = 4000
    DEFAULT_CHUNK_SIZE_ROWS = 50
    DEFAULT_MAX_CONCURRENT = 5

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
        self._chunking_service = ChunkingService(
            chunk_size_chars=self.DEFAULT_CHUNK_SIZE_CHARS,
            chunk_size_rows=self.DEFAULT_CHUNK_SIZE_ROWS
        )

    def get_capabilities(self) -> List[Capability]:
        return [
            Capability(
                name="text_analysis.analyze",
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
        return "skill.text_analysis.executed"

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

        if isinstance(data, list):
            chunks = self._chunking_service.chunk_rows(data)
            self._log_info(
                f"📊 [text_analysis] Шаг {step_id}: {len(data)} строк → {len(chunks)} чанков",
                event_type=LogEventType.INFO
            )
            input_type = "rows"
        elif isinstance(data, str):
            chunks = self._chunking_service.chunk_text(data)
            self._log_info(
                f"📄 [text_analysis] Шаг {step_id}: {len(data)} символов → {len(chunks)} чанков",
                event_type=LogEventType.INFO
            )
            input_type = "text"
        else:
            data_str = str(data)
            chunks = self._chunking_service.chunk_text(data_str)
            input_type = "unknown"

        summaries = await self._map_phase(chunks, question, execution_context)
        answer = await self._reduce_phase(summaries, question, execution_context)

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
                "processing_time_ms": processing_time
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
                source="text_analysis.analyze",
                step_number=step_id + 1,
                metadata={
                    "skill": "text_analysis",
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

    async def _map_phase(
        self,
        chunks: List[Dict[str, Any]],
        question: str,
        execution_context: Any
    ) -> List[Dict[str, Any]]:
        if len(chunks) == 1:
            return [await self._analyze_chunk(chunks[0], question, execution_context)]

        semaphore = asyncio.Semaphore(self.DEFAULT_MAX_CONCURRENT)

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
                    "max_tokens": 2000
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

        return await self._tree_reduce(valid_summaries, question, execution_context)

    async def _tree_reduce(
        self,
        items: List[Dict[str, Any]],
        question: str,
        execution_context: Any
    ) -> str:
        if len(items) == 1:
            return items[0].get("content", "")

        if len(items) == 2:
            result = await self._merge_pair(items, question, execution_context)
            return result.get("content", "")

        merged = []
        for i in range(0, len(items), 2):
            if i + 1 < len(items):
                pair = [items[i], items[i + 1]]
                merged_result = await self._merge_pair(pair, question, execution_context)
                merged.append(merged_result)
            else:
                merged.append(items[i])

        self._log_info(
            f"🌲 [text_analysis] Reduce: {len(items)} → {len(merged)}",
            event_type=LogEventType.INFO
        )

        return await self._tree_reduce(merged, question, execution_context)

    async def _merge_pair(
        self,
        pair: List[Dict[str, Any]],
        question: str,
        execution_context: Any
    ) -> Dict[str, Any]:
        content1 = pair[0].get("content", "")
        content2 = pair[1].get("content", "")

        prompt = self._build_merge_prompt(content1, content2, question)

        try:
            result = await self.executor.execute_action(
                action_name="llm.generate",
                parameters={
                    "prompt": prompt,
                    "temperature": 0.3,
                    "max_tokens": 2000
                },
                context=execution_context
            )

            if result.status == ExecutionStatus.COMPLETED:
                return {"content": result.result or f"{content1}\n\n{content2}"}
        except Exception as e:
            self._log_warning(f"⚠️ [text_analysis] Merge error: {e}", event_type=LogEventType.WARNING)

        return {"content": f"{content1}\n\n{content2}"}

    def _build_analyze_prompt(self, content: str, question: str) -> str:
        prompt_obj = self.get_prompt("text_analysis.analyze")
        if not prompt_obj:
            return self._build_analyze_prompt_fallback(content, question)
        
        return self._render_prompt(prompt_obj.content, {
            "question": question,
            "content": content
        })

    def _build_merge_prompt(self, content1: str, content2: str, question: str) -> str:
        prompt_obj = self.get_prompt("text_analysis.merge")
        if not prompt_obj:
            return self._build_merge_prompt_fallback(content1, content2, question)
        
        return self._render_prompt(prompt_obj.content, {
            "question": question,
            "content1": content1,
            "content2": content2
        })

    def _build_analyze_prompt_fallback(self, content: str, question: str) -> str:
        return f"""Проанализируй данные и ответь на вопрос.

ВОПРОС: {question}

ДАННЫЕ:
{content}

Инструкции:
- Отвечай ТОЛЬКО на основе предоставленных данных
- Если информации недостаточно, укажи это
- Пиши на русском языке

Ответ:"""

    def _build_merge_prompt_fallback(self, content1: str, content2: str, question: str) -> str:
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

    def _build_final_prompt_fallback(self, content: str, question: str) -> str:
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

    def _render_prompt(self, template: str, variables: Dict[str, Any]) -> str:
        result = template
        for key, value in variables.items():
            placeholder = "{" + key + "}"
            result = result.replace(placeholder, str(value))
        return result
