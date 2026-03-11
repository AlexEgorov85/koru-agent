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
        if self._faiss_provider is None:
            infra = self.application_context.infrastructure_context
            self._faiss_providers = infra._faiss_providers
            self._embedding_provider = infra.get_embedding_provider()
            self._chunking_strategy = infra.get_chunking_strategy()
            self._sql_provider = infra.get_sql_provider('books_db')
            self._llm_provider = infra.llm_provider_factory.get_default_llm()
            
            # Получаем кэш из application context
            from core.infrastructure.cache.analysis_cache import AnalysisCache
            self._cache_service = AnalysisCache()
    
    async def shutdown(self):
        """Закрытие инструмента."""
        pass
    
    async def execute(
        self,
        capability: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Выполнение операции.
        
        Capabilities:
        - search: Семантический поиск
        - get_document: Полный текст книги
        - analyze: LLM анализ
        - query: SQL запрос
        """
        
        if capability == "search":
            return await self._search(**kwargs)
        
        elif capability == "get_document":
            return await self._get_document(**kwargs)
        
        elif capability == "analyze":
            return await self._analyze(**kwargs)
        
        elif capability == "query":
            return await self._query(**kwargs)
        
        else:
            return {"error": f"Unknown capability: {capability}"}
    
    async def _search(
        self,
        query: str,
        top_k: int = 10,
        min_score: float = 0.5,
        filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Семантический поиск по книгам с fallback на SQL.

        Args:
            query: Текстовый запрос
            top_k: Количество результатов
            min_score: Минимальный порог
            filters: Фильтры по метаданным

        Returns:
            {"results": [...], "total_found": int, "search_type": "vector"|"sql"}
        """
        import time
        start_time = time.time()

        try:
            # Получаем инфраструктуру
            self._get_infrastructure()

            # Валидация параметров
            if not query or not isinstance(query, str):
                raise ValueError("Query must be a non-empty string")
            if top_k < 1 or top_k > 100:
                raise ValueError("top_k must be between 1 and 100")
            if min_score < 0.0 or min_score > 1.0:
                raise ValueError("min_score must be between 0.0 and 1.0")

            # 1. Генерируем вектор запроса
            if not self._embedding_provider:
                raise RuntimeError("Embedding provider not initialized")
            
            query_vector = await self._embedding_provider.generate([query])
            
            if not query_vector or len(query_vector) == 0:
                raise RuntimeError("Failed to generate query vector")

            # 2. Ищем в FAISS (используем books источник)
            faiss_provider = self._faiss_providers.get('books')
            if not faiss_provider:
                if self.event_bus_logger:
                    await self.event_bus_logger.warning("FAISS provider for books not initialized, using SQL fallback")
                return await self._sql_fallback_search(query, top_k)

            # Проверка наличия индекса
            if await faiss_provider.count() == 0:
                if self.event_bus_logger:
                    await self.event_bus_logger.warning("FAISS index is empty, using SQL fallback")
                return await self._sql_fallback_search(query, top_k)

            faiss_results = await faiss_provider.search(
                query_vector[0],
                top_k=top_k,
                filters=filters
            )

            # 3. Преобразуем результаты
            results = []
            for result in faiss_results:
                if result["score"] < min_score:
                    continue

                results.append({
                    "chunk_id": result["metadata"].get("chunk_id"),
                    "document_id": result["metadata"].get("document_id"),
                    "book_id": result["metadata"].get("book_id"),
                    "chapter": result["metadata"].get("chapter"),
                    "score": result["score"],
                    "content": result["metadata"].get("content", ""),
                    "metadata": result["metadata"]
                })

            elapsed_ms = (time.time() - start_time) * 1000
            if self.event_bus_logger:
                await self.event_bus_logger.info(
                    f"Vector search completed: {len(results)} results in {elapsed_ms:.2f}ms"
                )

            return {
                "results": results,
                "total_found": len(results),
                "search_type": "vector"
            }

        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000
            if self.event_bus_logger:
                await self.event_bus_logger.error(f"Vector search failed: {e}, using SQL fallback ({elapsed_ms:.2f}ms)")
            
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
