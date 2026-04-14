"""
BatchProcessor — групповая обработка чанков с LLM.

ОТВЕТСТВЕННОСТЬ:
- Группировка чанков в батчи (10-20 чанков на батч)
- Параллельная обработка батчей через LLM
- Сбор промежуточных summary
- Контроль памяти: результаты не накапливаются

АРХИТЕКТУРА:
- ActionExecutor для LLM вызовов
- Batched processing без накопления всех результатов
- Aggregation функция для merge результатов батча

ПРИМЕР:
>>> processor = BatchProcessor(executor, context)
>>> results = await processor.process_batches(chunks, analyze_fn)
"""
import asyncio
from typing import List, Dict, Any, Callable, Optional
from core.infrastructure.logging.event_types import LogEventType


class BatchProcessor:
    """
    Процессор батчей для обработки больших объёмов данных.

    АРХИТЕКТУРА:
    - chunk_size: количество чанков в одном батче
    - max_concurrent: максимум параллельных LLM вызовов
    - aggregation_fn: функция для объединения результатов батча
    """

    def __init__(
        self,
        executor: Any,
        execution_context: Any,
        chunk_size: int = 15,
        max_concurrent: int = 3
    ):
        self.executor = executor
        self.execution_context = execution_context
        self.chunk_size = chunk_size
        self.max_concurrent = max_concurrent

    async def process_batches(
        self,
        items: List[Any],
        process_fn: Callable[[Any], Any],
        aggregation_fn: Optional[Callable[[List[Any]], Any]] = None
    ) -> List[Any]:
        """
        Обработка элементов батчами.

        ARGS:
        - items: List[Any] — элементы для обработки
        - process_fn: Callable — функция обработки одного элемента
        - aggregation_fn: Callable — опциональная функция агрегации результатов батча

        RETURNS:
        - List[Any] — результаты обработки

        EXAMPLE:
        >>> async def process_chunk(chunk):
        ...     return await llm.analyze(chunk)
        >>> results = await bp.process_batches(chunks, process_chunk)
        """
        if not items:
            return []

        batches = self._create_batches(items)

        self._log_info(
            f"📦 [BatchProcessor] {len(items)} элементов → {len(batches)} батчей",
            event_type=LogEventType.INFO
        )

        all_results = []
        semaphore = asyncio.Semaphore(self.max_concurrent)

        async def process_single_batch(batch_idx: int, batch: List[Any]) -> List[Any]:
            async with semaphore:
                self._log_info(
                    f"📦 [BatchProcessor] Обработка батча {batch_idx + 1}/{len(batches)} ({len(batch)} элементов)",
                    event_type=LogEventType.DEBUG
                )

                batch_results = []
                for item in batch:
                    try:
                        result = await process_fn(item)
                        batch_results.append(result)
                    except Exception as e:
                        self._log_warning(
                            f"⚠️ [BatchProcessor] Ошибка обработки элемента: {e}",
                            event_type=LogEventType.WARNING
                        )
                        batch_results.append(None)

                if aggregation_fn and batch_results:
                    aggregated = aggregation_fn(batch_results)
                    return [aggregated]

                return batch_results

        tasks = [
            process_single_batch(idx, batch)
            for idx, batch in enumerate(batches)
        ]

        batch_results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in batch_results:
            if isinstance(result, Exception):
                self._log_warning(
                    f"⚠️ [BatchProcessor] Ошибка батча: {result}",
                    event_type=LogEventType.WARNING
                )
            elif result:
                all_results.extend(result)

        self._log_info(
            f"✅ [BatchProcessor] Обработано: {len(all_results)} результатов",
            event_type=LogEventType.INFO
        )

        return all_results

    def _create_batches(self, items: List[Any]) -> List[List[Any]]:
        """Разделение элементов на батчи."""
        batches = []
        for i in range(0, len(items), self.chunk_size):
            batches.append(items[i:i + self.chunk_size])
        return batches

    def _log_info(self, message: str, event_type: LogEventType) -> None:
        import logging
        log = logging.getLogger(__name__)
        log.info(message, extra={"event_type": event_type})

    def _log_warning(self, message: str, event_type: LogEventType) -> None:
        import logging
        log = logging.getLogger(__name__)
        log.warning(message, extra={"event_type": event_type})