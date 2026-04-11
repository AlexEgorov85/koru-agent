"""
VectorBooksTool — универсальный инструмент для работы с книгами.

Capabilities:
- search: Семантический поиск по текстам книг
- get_document: Получение полного текста книги (SQL)
- analyze: LLM анализ (герои, темы, etc.)
- query: SQL запрос к базе книг
"""
from typing import Optional, Dict, Any, List
from core.components.tools.tool import Tool
from core.application_context.application_context import ApplicationContext
from core.config.component_config import ComponentConfig
from core.models.types.vector_types import VectorSearchResult, VectorQuery
from core.models.types.analysis import AnalysisResult
from core.infrastructure.logging.event_types import LogEventType


class VectorBooksTool(Tool):
    """
    Универсальный инструмент для работы с книгами.

    Использует:
    - FAISS для семантического поиска
    - SQL для получения полного текста
    - LLM для анализа
    - Cache для кэширования результатов анализа
    """

    def __init__(
        self,
        name: str,
        component_config: ComponentConfig,
        executor,
        application_context: Optional[ApplicationContext] = None
    ):
        super().__init__(
            name=name,
            component_config=component_config,
            executor=executor,
            application_context=application_context
        )
        
        # ← НОВОЕ: Инициализация атрибутов инфраструктуры
        self._embedding_provider = None
        self._faiss_provider = None
        self._chunking_strategy = None
        self._sql_provider = None
        self._cache_service = None

    @property
    def description(self) -> str:
        return "Все операции с книгами: поиск + текст + анализ"

    def _get_infrastructure(self):
        """Получение провайдеров из инфраструктуры."""
        if self._embedding_provider is None:
            infra = self.application_context.infrastructure_context
            self._embedding_provider = infra.get_embedding_provider()
            self._faiss_provider = infra.get_faiss_provider('books')
            self._chunking_strategy = infra.get_chunking_strategy()
            self._sql_provider = infra.resource_registry.get_resource('default_db').instance if infra.resource_registry else None

            if not self._embedding_provider:
                from core.errors.exceptions import InfrastructureError
                raise InfrastructureError(
                    "Embedding провайдер не инициализирован. "
                    "Убедитесь что SentenceTransformersProvider настроен в InfrastructureContext."
                )

            from core.infrastructure.cache.analysis_cache import AnalysisCache
            self._cache_service = AnalysisCache()
    
    async def shutdown(self):
        """Закрытие инструмента."""
        await super().shutdown()

    async def _execute_impl(
        self,
        capability: 'Capability',
        parameters: Dict[str, Any],
        execution_context: 'ExecutionContext'
    ) -> Dict[str, Any]:
        """
        Выполнение операции (ASYNC версия для vector_books).

        Capabilities:
        - vector_books.search: Семантический поиск
        - vector_books.get_document: Полный текст книги (SQL)
        - vector_books.analyze: LLM анализ
        - vector_books.query: SQL запрос
        """
        # Извлекаем operation из capability.name
        if hasattr(capability, 'name'):
            cap_name = capability.name
            if '.' in cap_name:
                _, operation = cap_name.split('.', 1)
            else:
                operation = cap_name
        else:
            operation = str(capability)

        # Поддержка Pydantic модели и dict
        from pydantic import BaseModel
        if isinstance(parameters, BaseModel):
            params_dict = parameters.model_dump() if hasattr(parameters, 'model_dump') else parameters.dict()
        else:
            params_dict = parameters

        # Получаем инфраструктуру (загружаем embedding если нужно)
        self._log_debug(f"VectorBooksTool: getting infrastructure...", event_type=LogEventType.DEBUG)
        self._get_infrastructure()
        self._log_debug(f"VectorBooksTool: infrastructure ready, embedding={self._embedding_provider is not None}", event_type=LogEventType.DEBUG)

        # Выполняем async операцию напрямую (используем Pydantic модели)
        if operation == "search":
            query = params_dict.get('query', '')
            top_k = params_dict.get('top_k', 10)
            min_score = params_dict.get('min_score', 0.5)
            source = params_dict.get('source', 'books')
            self._log_debug(f"VectorBooksTool._search: query='{query[:50]}...', top_k={top_k}, source={source}", event_type=LogEventType.DEBUG)

            return await self._search(query=query, top_k=top_k, min_score=min_score, source=source)

        elif operation == "get_document":
            document_id = params_dict.get('document_id')
            return await self._get_document(document_id=document_id)

        elif operation == "analyze":
            entity_id = params_dict.get('entity_id', '')
            analysis_type = params_dict.get('analysis_type', 'summary')
            prompt = params_dict.get('prompt', '')
            force_refresh = params_dict.get('force_refresh', False)
            return await self._analyze(
                entity_id=entity_id, 
                analysis_type=analysis_type, 
                prompt=prompt,
                force_refresh=force_refresh
            )

        elif operation == "query":
            sql = params_dict.get('sql', '')
            params = params_dict.get('parameters', {})
            return await self._query(sql=sql, parameters=params)

        else:
            error_msg = f"Unknown operation: {operation}"
            self._log_error(error_msg, event_type=LogEventType.ERROR)
            return {"error": error_msg}
    
    async def _search(
        self,
        query: str,
        top_k: int = 10,
        min_score: float = 0.5,
        filters: Optional[Dict[str, Any]] = None,
        source: str = "books"
    ) -> Dict[str, Any]:
        """
        Семантический поиск по книгам.
        РАБОТАЕТ КАК test_vector_db.py — напрямую, без сложной инфраструктуры.
        """
        import time
        import numpy as np
        start_time = time.time()

        self._log_debug(f"[_search] START | query='{query[:50]}...'", event_type=LogEventType.DEBUG)

        try:
            # 1. Генерируем вектор через _embedding_provider
            self._log_debug(f"[_search] Using embedding provider...", event_type=LogEventType.DEBUG)

            if not self._embedding_provider:
                return {"error": "Embedding provider not initialized", "search_type": "error"}

            embedding_start = time.time()
            query_vector_list = await self._embedding_provider.generate([query])
            query_vector = np.array(query_vector_list[0], dtype=np.float32) if query_vector_list else None
            self._log_debug(f"[_search] Embedding done", event_type=LogEventType.DEBUG)

            # 2. Получаем FAISS индекс через метод доступа
            self._log_debug(f"[_search] Getting FAISS...", event_type=LogEventType.DEBUG)

            infra = self.application_context.infrastructure_context
            faiss = infra.get_faiss_provider(source)

            if not faiss:
                return {"error": f"FAISS {source} provider not found", "search_type": "error"}

            count = await faiss.count()
            if count == 0:
                from core.errors.exceptions import DataNotFoundError
                raise DataNotFoundError(
                    f"FAISS индекс пуст для коллекции '{source}'. "
                    f"Необходимо проиндексировать данные перед поиском.",
                    query=query
                )

            # 3. Поиск в FAISS (напрямую как в тесте)
            self._log_debug(f"[_search] Searching FAISS ({count} vectors)...", event_type=LogEventType.DEBUG)

            faiss_search_start = time.time()
            faiss_results = await faiss.search(query_vector.tolist() if query_vector is not None else [], top_k=top_k)
            self._log_debug(f"[_search] FAISS done | results={len(faiss_results)}", event_type=LogEventType.DEBUG)

            # 4. Преобразуем результаты
            results = []
            for result in faiss_results:
                if result.get("score", 0) < min_score:
                    continue
                results.append({
                    "chunk_id": result.get("metadata", {}).get("chunk_id"),
                    "document_id": result.get("metadata", {}).get("document_id"),
                    "book_id": result.get("metadata", {}).get("book_id"),
                    "chapter": result.get("metadata", {}).get("chapter"),
                    "score": result.get("score"),
                    "content": result.get("metadata", {}).get("content", ""),
                    "metadata": result.get("metadata")
                })

            total_time = time.time() - start_time
            self._log_debug(f"[_search] COMPLETE: {total_time:.2f}s, found={len(results)}", event_type=LogEventType.DEBUG)

            # Возвращаем только поля из output контракта (additionalProperties: false)
            return {
                "results": results,
                "total_found": len(results)
            }

        except Exception as e:
            self._log_error(f"[_search] ERROR: {e}", event_type=LogEventType.ERROR)
            import traceback
            self._log_error(f"Traceback: {traceback.format_exc()}", event_type=LogEventType.ERROR)

            # ❌ УДАЛЕНО: Fallback на SQL при любой ошибке
            # ✅ ТЕПЕРЬ: Выбрасываем VectorSearchError
            from core.errors.exceptions import VectorSearchError
            raise VectorSearchError(
                f"Векторный поиск не удался: {e}. "
                f"Проверьте что FAISS индекс создан, загружен и содержит данные.",
                component="vector_books_tool.search"
            )

    # ❌ УДАЛЕНО: _sql_fallback_search
    # ✅ ТЕПЕРЬ: Векторный поиск должен работать, иначе DataNotFoundError/VectorSearchError

    async def _get_document(
        self,
        document_id: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Получение полного текста книги из FAISS индекса.
        
        NOTE: Данные книг хранятся в FAISS индексе, не в PostgreSQL.

        Args:
            document_id: ID документа (например, "book_1")

        Returns:
            {"book_id": int, "chapters": [{"chapter": int, "content": str}, ...]}
        """
        
        import json
        import os
        from pathlib import Path
        
        book_id = int(document_id.replace("book_", ""))
        
        data_dir = Path(self.application_context.infrastructure_context.config.data_dir)
        metadata_path = data_dir / "vector" / "books_index_metadata.json"
        
        chapters_dict: Dict[int, List[str]] = {}
        
        if os.path.exists(metadata_path):
            with open(metadata_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            for idx, chunk_info in data.get("metadata", {}).items():
                if chunk_info.get("document_id") == document_id:
                    chapter = chunk_info.get("chapter", 0)
                    content = chunk_info.get("content", "")
                    if chapter not in chapters_dict:
                        chapters_dict[chapter] = []
                    chapters_dict[chapter].append(content)
        
        chapters = [
            {"chapter": ch, "content": "".join(chunks)}
            for ch, chunks in sorted(chapters_dict.items())
        ]
        
        return {
            "book_id": book_id,
            "chapters": chapters
        }
    
    async def _analyze(
        self,
        entity_id: str,
        analysis_type: str,
        prompt: str,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        Универсальный LLM анализ.

        Примеры:
        - analyze(entity_id="book_1", analysis_type="character", prompt="Кто главный герой?")
        - analyze(entity_id="book_1", analysis_type="theme", prompt="Какие основные темы?")

        Args:
            entity_id: ID сущности
            analysis_type: Тип анализа
            prompt: Промпт для LLM
            force_refresh: Игнорировать кэш

        Returns:
            AnalysisResult.to_dict()
        """

        # Получаем инфраструктуру
        self._get_infrastructure()

        # 1. Проверка кэша
        cache_key = f"analysis:{analysis_type}:{entity_id}"
        if not force_refresh and self._cache_service:
            cached = await self._cache_service.get(cache_key)
            if cached:
                return cached

        # 2. Получение контекста
        context = await self._get_context(entity_id)

        # 3. LLM анализ — используем промпт из component_config
        # Получаем шаблон промпта из кэша (загружен при инициализации)
        capability_name = "vector_books.analyze"
        prompt_obj = self.get_prompt(capability_name)
        prompt_template = prompt_obj.content if prompt_obj else ""

        if not prompt_template:
            from core.errors.exceptions import SkillExecutionError
            raise SkillExecutionError(
                f"Промпт для {capability_name} не загружен! Проверьте YAML в data/prompts/",
                component="vector_books_tool"
            )

        # Рендерим промпт
        llm_prompt = prompt_template.format(prompt=prompt, context=context)

        # Получаем output контракт для структурированного вывода
        output_schema = self.get_output_contract(capability_name)
        
        if not output_schema:
            from core.errors.exceptions import SkillExecutionError
            raise SkillExecutionError(
                f"Контракт для {capability_name} не загружен! Проверьте YAML в data/contracts/",
                component="vector_books_tool"
            )

        # Вызов LLM через executor с structured output
        result = await self.executor.execute_action(
            action_name="llm.generate_structured",
            llm_provider=self._llm_provider,
            parameters={
                'prompt': llm_prompt,
                'structured_output': {
                    'output_model': 'VectorBooksAnalysis',
                    'schema_def': output_schema,
                    'max_retries': 3,
                    'strict_mode': False
                }
            }
        )
        
        if not result.get('success'):
            raise RuntimeError(f"LLM error: {result.get('error')}")

        result_data = result['data']['parsed_content']

        # 4. Формируем результат
        analysis = AnalysisResult(
            entity_id=entity_id,
            analysis_type=analysis_type,
            result=result_data.get("result", {}),
            confidence=result_data.get("confidence", 0.5),
            reasoning=result_data.get("reasoning", "")
        )

        # 5. Сохранение в кэш
        if self._cache_service:
            await self._cache_service.set(
                cache_key,
                analysis.to_dict(),
                ttl_hours=168  # 7 дней
            )

        return analysis.to_dict()
    
    async def _get_context(self, entity_id: str) -> str:
        """Получение контекста для анализа."""
        
        # Если это книга, получаем несколько чанков
        if entity_id.startswith("book_"):
            book_id = int(entity_id.replace("book_", ""))
            
            results = await self._faiss_provider.search(
                query_vector=[0.0] * 384,  # Пустой вектор для получения любых чанков
                top_k=5,
                filters={"book_id": book_id}
            )
            
            context = "\n\n".join([
                f"[Глава {r['metadata'].get('chapter', '?')}]\n{r['metadata'].get('content', '')}"
                for r in results
            ])
            
            return context
        
        return ""
    
    async def _query(
        self,
        sql: str,
        parameters: Optional[tuple] = None
    ) -> Dict[str, Any]:
        """
        SQL запрос к базе книг.

        Args:
            sql: SQL запрос
            parameters: Параметры запроса

        Returns:
            {"data": [...]}
        """
        
        # Получаем инфраструктуру
        self._get_infrastructure()
        
        result = await self._sql_provider.fetch(sql, parameters)
        
        return {
            "data": result
        }
