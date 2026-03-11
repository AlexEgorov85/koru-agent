"""
VectorBooksTool — универсальный инструмент для работы с книгами.

Capabilities:
- search: Семантический поиск по текстам книг
- get_document: Получение полного текста книги (SQL)
- analyze: LLM анализ (герои, темы, etc.)
- query: SQL запрос к базе книг
"""

import asyncio
from typing import Optional, Dict, Any, List
from core.application.tools.base_tool import BaseTool
from core.application.context.application_context import ApplicationContext
from core.config.component_config import ComponentConfig
from core.models.types.vector_types import VectorSearchResult, VectorQuery
from core.models.types.analysis import AnalysisResult
from core.infrastructure.logging import EventBusLogger


class VectorBooksTool(BaseTool):
    """
    Универсальный инструмент для работы с книгами.

    Использует:
    - FAISS для семантического поиска
    - SQL для получения полного текста
    - LLM для анализа
    - Cache для кэширования результатов анализа
    """

    # Явная декларация зависимостей
    DEPENDENCIES = []  # Нет зависимостей (использует инфраструктуру напрямую)

    def __init__(
        self,
        name: str,
        application_context: ApplicationContext,
        component_config: Optional[ComponentConfig] = None,
        executor=None,
        **kwargs
    ):
        # Вызываем родительский конструктор
        super().__init__(name, application_context, component_config=component_config, executor=executor, **kwargs)

        # Провайдеры будут получены из инфраструктуры при выполнении
        self._faiss_provider = None
        self._sql_provider = None
        self._embedding_provider = None
        self._llm_provider = None
        self._cache_service = None
        self._chunking_strategy = None
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

    @property
    def description(self) -> str:
        return "Все операции с книгами: поиск + текст + анализ"

    def _get_infrastructure(self):
        """Получение провайдеров из инфраструктуры."""
        if self._embedding_provider is None:
            infra = self.application_context.infrastructure_context
            self._faiss_providers = infra._faiss_providers
            self._embedding_provider = infra.get_embedding_provider()
            self._chunking_strategy = infra.get_chunking_strategy()
            # Используем resource_registry для SQL провайдера
            self._sql_provider = infra.resource_registry.get_resource('default_db').instance if infra.resource_registry else None

            # Если embedding провайдер не инициализирован, загружаем модель онлайн
            if not self._embedding_provider:
                try:
                    from sentence_transformers import SentenceTransformer
                    import numpy as np
                    
                    class SimpleEmbeddingProvider:
                        def __init__(self, model):
                            self.model = model
                        async def generate(self, texts):
                            embeddings = self.model.encode(texts, convert_to_numpy=True)
                            if isinstance(embeddings, np.ndarray):
                                embeddings = embeddings.tolist()
                            return embeddings
                    
                    self._embedding_provider = SimpleEmbeddingProvider(
                        SentenceTransformer('all-MiniLM-L6-v2')
                    )
                    if self.event_bus_logger:
                        self.event_bus_logger.debug_sync("✅ Embedding загружен онлайн")
                except Exception as e:
                    if self.event_bus_logger:
                        self.event_bus_logger.error_sync(f"❌ Ошибка загрузки embedding: {e}")

            # Получаем кэш из application context
            from core.infrastructure.cache.analysis_cache import AnalysisCache
            self._cache_service = AnalysisCache()
    
    async def shutdown(self):
        """Закрытие инструмента."""
        pass
    
    def _execute_impl(
        self,
        capability: 'Capability',
        parameters: Dict[str, Any],
        execution_context: 'ExecutionContext'
    ) -> Dict[str, Any]:
        """
        Выполнение операции (как FileTool и SQLTool).

        Capabilities:
        - vector_books.search: Семантический поиск (с fallback на SQL)
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
        if self.event_bus_logger:
            self.event_bus_logger.debug_sync(f"VectorBooksTool: getting infrastructure...")
        self._get_infrastructure()
        if self.event_bus_logger:
            self.event_bus_logger.debug_sync(f"VectorBooksTool: infrastructure ready, embedding={self._embedding_provider is not None}")

        # Запускаем async операцию в event loop
        # TIMEOUT: 5 минут (300 секунд) для всех операций
        import asyncio
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        if self.event_bus_logger:
            self.event_bus_logger.debug_sync(f"VectorBooksTool: event loop={loop}, operation={operation}")

        if operation == "search":
            query = params_dict.get('query', '')
            top_k = params_dict.get('top_k', 10)
            min_score = params_dict.get('min_score', 0.5)
            if self.event_bus_logger:
                self.event_bus_logger.debug_sync(f"VectorBooksTool._search: query='{query[:50]}...', top_k={top_k}")
            
            try:
                future = asyncio.run_coroutine_threadsafe(
                    self._search(query=query, top_k=top_k, min_score=min_score),
                    loop
                )
                if self.event_bus_logger:
                    self.event_bus_logger.debug_sync(f"VectorBooksTool: waiting for result (timeout=300s)...")
                result = future.result(timeout=300.0)
                if self.event_bus_logger:
                    self.event_bus_logger.debug_sync(f"VectorBooksTool: search completed, results={len(result) if result else 0}")
                return result
            except Exception as e:
                if self.event_bus_logger:
                    self.event_bus_logger.error_sync(f"VectorBooksTool: search error: {e}")
                import traceback
                if self.event_bus_logger:
                    self.event_bus_logger.error_sync(f"Traceback: {traceback.format_exc()}")
                return {"error": str(e)}

        elif operation == "get_document":
            book_id = params_dict.get('book_id')
            future = asyncio.run_coroutine_threadsafe(
                self._get_document(book_id=book_id),
                loop
            )
            return future.result(timeout=300.0)

        elif operation == "analyze":
            text = params_dict.get('text', '')
            analysis_type = params_dict.get('analysis_type', 'summary')
            future = asyncio.run_coroutine_threadsafe(
                self._analyze(text=text, analysis_type=analysis_type),
                loop
            )
            return future.result(timeout=300.0)

        elif operation == "query":
            sql = params_dict.get('sql', '')
            params = params_dict.get('parameters', {})
            future = asyncio.run_coroutine_threadsafe(
                self._query(sql=sql, parameters=params),
                loop
            )
            return future.result(timeout=300.0)

        else:
            error_msg = f"Unknown operation: {operation}"
            if self.event_bus_logger:
                self.event_bus_logger.error_sync(error_msg)
            return {"error": error_msg}
    
    async def _search(
        self,
        query: str,
        top_k: int = 10,
        min_score: float = 0.5,
        filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Семантический поиск по книгам.
        РАБОТАЕТ КАК test_vector_db.py — напрямую, без сложной инфраструктуры.
        """
        import time
        import numpy as np
        start_time = time.time()
        
        if self.event_bus_logger:
            self.event_bus_logger.debug_sync(f"⏱️ [_search] START | query='{query[:50]}...'")

        try:
            # 1. Загружаем модель и генерируем вектор (как в тесте)
            if self.event_bus_logger:
                self.event_bus_logger.debug_sync(f"⏱️ [_search] Loading model...")
            
            from sentence_transformers import SentenceTransformer
            model = SentenceTransformer('all-MiniLM-L6-v2')
            
            if self.event_bus_logger:
                self.event_bus_logger.debug_sync(f"⏱️ [_search] Generating embedding...")
            embedding_start = time.time()
            query_vector = model.encode([query], convert_to_numpy=True)
            if self.event_bus_logger:
                self.event_bus_logger.debug_sync(f"⏱️ [_search] Embedding done: {time.time() - embedding_start:.2f}s")

            # 2. Получаем FAISS индекс напрямую из инфраструктуры
            if self.event_bus_logger:
                self.event_bus_logger.debug_sync(f"⏱️ [_search] Getting FAISS...")
            
            infra = self.application_context.infrastructure_context
            faiss = infra._faiss_providers.get('books')
            
            if not faiss:
                return {"error": "FAISS books provider not found", "search_type": "error"}
            
            count = await faiss.count()
            if count == 0:
                if self.event_bus_logger:
                    self.event_bus_logger.debug_sync("⏱️ [_search] FAISS empty, using SQL fallback")
                return await self._sql_fallback_search(query, top_k)

            # 3. Поиск в FAISS (напрямую как в тесте)
            if self.event_bus_logger:
                self.event_bus_logger.debug_sync(f"⏱️ [_search] Searching FAISS ({count} vectors)...")
            
            faiss_search_start = time.time()
            faiss_results = await faiss.search(query_vector[0].tolist(), top_k=top_k)
            if self.event_bus_logger:
                self.event_bus_logger.debug_sync(f"⏱️ [_search] FAISS done: {time.time() - faiss_search_start:.2f}s | results={len(faiss_results)}")

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
            if self.event_bus_logger:
                self.event_bus_logger.debug_sync(f"⏱️ [_search] COMPLETE: {total_time:.2f}s, found={len(results)}")

            return {
                "results": results,
                "total_found": len(results),
                "search_type": "vector",
                "query": query,
                "execution_time": total_time
            }

        except Exception as e:
            if self.event_bus_logger:
                self.event_bus_logger.error_sync(f"⏱️ [_search] ERROR: {e}")
            import traceback
            if self.event_bus_logger:
                self.event_bus_logger.error_sync(f"Traceback: {traceback.format_exc()}")
            
            # Fallback на SQL
            return await self._sql_fallback_search(query, top_k)
            
            # Fallback на SQL поиск при любой ошибке
            try:
                return await self._sql_fallback_search(query, top_k)
            except Exception as sql_error:
                if self.event_bus_logger:
                    await self.event_bus_logger.error(f"SQL fallback also failed: {sql_error}")
                return {
                    "results": [],
                    "total_found": 0,
                    "search_type": "none",
                    "error": str(e)
                }

    async def _sql_fallback_search(self, query: str, top_k: int = 10) -> Dict[str, Any]:
        """
        SQL fallback для векторного поиска.
        Ищет по названию книги и фамилии автора.
        """
        if not self._sql_provider:
            raise RuntimeError("SQL provider not initialized")

        # Экранирование запроса для LIKE
        safe_query = query.replace("'", "''")
        
        sql = f"""
            SELECT 
                b.id as book_id,
                b.title as book_title,
                b.isbn,
                b.publication_date,
                a.first_name,
                a.last_name,
                0.5 as score
            FROM "Lib".books b
            JOIN "Lib".authors a ON b.author_id = a.id
            WHERE b.title ILIKE '%{safe_query}%' 
               OR a.last_name ILIKE '%{safe_query}%' 
               OR a.first_name ILIKE '%{safe_query}%'
            ORDER BY score DESC
            LIMIT {top_k}
        """
        
        rows = await self._sql_provider.fetch(sql, ())
        
        results = []
        for row in rows:
            results.append({
                "book_id": row.get("book_id"),
                "document_id": f"book_{row.get('book_id')}",
                "chapter": None,
                "chunk_id": None,
                "score": 0.5,
                "content": f"{row.get('book_title')} by {row.get('last_name')} {row.get('first_name')}",
                "metadata": {
                    "title": row.get("book_title"),
                    "author": f"{row.get('last_name')} {row.get('first_name')}",
                    "isbn": row.get("isbn"),
                    "publication_date": row.get("publication_date")
                }
            })
        
        if self.event_bus_logger:
            await self.event_bus_logger.info(f"SQL fallback search: {len(results)} results")
        
        return {
            "results": results,
            "total_found": len(results),
            "search_type": "sql"
        }
    
    async def _get_document(
        self,
        document_id: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Получение полного текста книги из SQL.

        Args:
            document_id: ID документа (например, "book_1")

        Returns:
            {"book_id": int, "chapters": [...]}
        """
        
        # Получаем инфраструктуру
        self._get_infrastructure()
        
        # Извлекаем book_id из document_id
        book_id = int(document_id.replace("book_", ""))
        
        # SQL запрос для получения полного текста
        chapters = await self._sql_provider.fetch("""
            SELECT chapter, content
            FROM book_texts
            WHERE book_id = ?
            ORDER BY chapter
        """, (book_id,))
        
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
        prompt_template = self.get_prompt(capability_name)
        
        if not prompt_template:
            if self.event_bus_logger:
                await self.event_bus_logger.warning(f"Промпт {capability_name} не загружен, используем fallback")
            else:
                self.logger.warning(f"Промпт {capability_name} не загружен, используем fallback")
            # Fallback шаблон
            prompt_template = "{prompt}\n\nКонтекст:\n{context}\n\nОтветь в формате JSON:\n{{\n    \"result\": {{...}},\n    \"confidence\": 0.0-1.0,\n    \"reasoning\": \"обоснование\"\n}}"
        
        # Рендерим промпт
        llm_prompt = prompt_template.format(prompt=prompt, context=context)

        # Получаем output контракт для структурированного вывода
        output_schema = self.get_output_contract(capability_name)
        
        if output_schema:
            # Используем структурированный вывод с контрактом
            from core.models.types.llm_types import LLMRequest, StructuredOutputConfig
            
            llm_request = LLMRequest(
                prompt=llm_prompt,
                structured_output=StructuredOutputConfig(
                    output_model="VectorBooksAnalysis",
                    schema_def=output_schema,
                    max_retries=3,
                    strict_mode=False
                )
            )

            # Вызов через executor (который использует orchestrator)
            result = await self.executor.execute_action(
                action_name="llm.generate_structured",
                llm_provider=self._llm_provider,
                parameters={
                    'prompt': llm_prompt,
                    'structured_output': StructuredOutputConfig(
                        output_model="VectorBooksAnalysis",
                        schema_def=output_schema,
                        max_retries=3,
                        strict_mode=False
                    )
                }
            )
            
            # Извлекаем результат
            if result.get('success'):
                result_data = result['data']['parsed_content']
            else:
                raise ValueError(f"LLM error: {result.get('error')}")
        else:
            # Fallback: простой JSON вывод через executor (единообразно)
            fallback_result = await self.executor.execute_action(
                action_name="llm.generate",
                llm_provider=self._llm_provider,
                parameters={
                    'prompt': llm_prompt,
                    'temperature': 0.1,
                    'max_tokens': 500
                }
            )
            result_data = fallback_result['data']['content']

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
            
            results = await self.faiss_provider.search(
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
