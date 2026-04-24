"""
VectorSearchTool — универсальный инструмент для семантического поиска.

Capabilities:
- search: Семантический поиск по векторному индексу (любой source)
- get_document: Получение полного текста документа (SQL/FAISS)
- analyze: LLM анализ фрагментов
- query: SQL запрос к базе данных

ИСТОЧНИКИ (source):
- books: Индекс книг
- authors: Индекс авторов
- genres: Индекс жанров
- audits: Индекс аудиторских проверок
- violations: Индекс отклонений
"""

NO_LIMIT = None

class VectorSearchDefaults:
    """Константы для типичных сценариев поиска."""
    TOP_K_DEFAULT = 10
    TOP_K_ALL = None
    MIN_SCORE_DEFAULT = 0.5
    MIN_SCORE_LENIENT = 0.3
    MIN_SCORE_STRICT = 0.7

from typing import Optional, Dict, Any, List
from core.components.tools.tool import Tool
from core.application_context.application_context import ApplicationContext
from core.config.component_config import ComponentConfig
from core.models.types.vector_types import VectorSearchResult, VectorQuery
from core.models.types.analysis import AnalysisResult
from core.infrastructure.event_bus.unified_event_bus import EventType


class VectorSearchTool(Tool):
    """
    Универсальный инструмент для семантического поиска через FAISS.

    Использует:
    - FAISS для семантического поиска (любой source)
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
        self._sql_provider = None
        self._cache_service = None
        # FAISS провайдеры кэшируются по source
        self._faiss_providers: Dict[str, Any] = {}
        self._chunking_strategies: Dict[str, Any] = {}

    @property
    def description(self) -> str:
        return "Универсальный семантический поиск через FAISS (books, authors, audits, violations, ...)"

    def get_capabilities(self) -> List['Capability']:
        """
        Возвращает возможности инструмента — скрытые из {{available_tools}}.

        vector_search — внутренний инструмент для прямого вызова через executor,
        не для ReAct-планирования. LLM не должен видеть его в списке доступных.
        """
        from core.models.data.capability import Capability

        capabilities = []
        allowed_ops = self.get_allowed_operations()

        if not allowed_ops and self.component_config:
            if hasattr(self.component_config, 'input_contract_versions'):
                for cap_name in self.component_config.input_contract_versions.keys():
                    if cap_name.startswith(f"{self.name}.") or cap_name.startswith(self.name.replace("_tool", ".")):
                        allowed_ops.append(cap_name)

        for op_name in allowed_ops:
            cap_full_name = op_name if '.' in op_name else f"{self.name}.{op_name}"
            capabilities.append(Capability(
                name=cap_full_name,
                description=f"Операция '{op_name}' инструмента {self.name}",
                skill_name=self.name,
                supported_strategies=["react"],
                visiable=False  # Скрыт из {{available_tools}} — только прямой вызов
            ))

        return capabilities

    def _get_infrastructure(self):
        """Получение провайдеров из инфраструктуры.

        NOTE: FAISS провайдеры не кэшируются здесь — они получаются динамически
        по source в _get_faiss_for_source().
        """
        if self._embedding_provider is None:
            infra = self.application_context.infrastructure_context
            self._embedding_provider = infra.get_embedding_provider()

            if not self._embedding_provider:
                from core.errors.exceptions import InfrastructureError
                raise InfrastructureError(
                    "Embedding провайдер не инициализирован. "
                    "Убедитесь что SentenceTransformersProvider настроен в InfrastructureContext.",
                    component="vector_search_tool"
                )

            # SQL провайдер
            if self._sql_provider is None:
                self._sql_provider = infra.resource_registry.get_resource('default_db').instance if infra.resource_registry else None

            # Cache сервис
            if self._cache_service is None:
                from core.infrastructure.cache.analysis_cache import AnalysisCache
                self._cache_service = AnalysisCache()

    def _get_faiss_for_source(self, source: str):
        """
        Получение FAISS провайдера для конкретного источника.

        ARGS:
        - source: имя источника (books, authors, audits, violations, ...)

        RETURNS:
        - FAISS провайдер для данного источника
        """
        if source not in self._faiss_providers:
            infra = self.application_context.infrastructure_context
            faiss = infra.get_faiss_provider(source)

            if not faiss:
                from core.errors.exceptions import InfrastructureError
                raise InfrastructureError(
                    f"FAISS провайдер для источника '{source}' не найден. "
                    f"Убедитесь что он зарегистрирован в InfrastructureContext.",
                    component="vector_search_tool"
                )

            self._faiss_providers[source] = faiss

        return self._faiss_providers[source]
    
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
        Выполнение операции (ASYNC версия для vector_search).

        Capabilities:
        - vector_search.search: Семантический поиск (любой source)
        - vector_search.get_document: Полный текст документа (SQL/FAISS)
        - vector_search.analyze: LLM анализ
        - vector_search.query: SQL запрос
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
        self._log_debug(f"VectorSearchTool: getting infrastructure...", event_type=EventType.DEBUG)
        self._get_infrastructure()
        self._log_debug(f"VectorSearchTool: infrastructure ready, embedding={self._embedding_provider is not None}", event_type=EventType.DEBUG)

        # Выполняем async операцию напрямую
        if operation == "search":
            query = params_dict.get('query', '')
            top_k = params_dict.get('top_k', 10)
            min_score = params_dict.get('min_score', 0.5)
            source = params_dict.get('source', 'books')
            self._log_debug(f"VectorSearchTool._search: query='{query[:50]}...', top_k={top_k}, source={source}", event_type=EventType.DEBUG)

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
            self._log_error(error_msg, event_type=EventType.ERROR)
            return {"error": error_msg}
    
    async def _search(
        self,
        query: str,
        top_k: Optional[int] = 10,
        min_score: float = 0.5,
        filters: Optional[Dict[str, Any]] = None,
        source: str = "books"
    ) -> Dict[str, Any]:
        """
        Семантический поиск через FAISS.

        ARGS:
            query: Текст запроса
            top_k: Количество результатов (None = без лимита, только min_score)
            min_score: Минимальный порог релевантности (0-1)
            filters: Фильтры по метаданным
            source: Источник данных (books/authors/audits/violations)

        RETURNS:
            {"results": [...], "total_found": int}
        """
        import time
        import numpy as np
        start_time = time.time()

        self._log_debug(f"[_search] START | query='{query[:50]}...', source={source}", event_type=EventType.DEBUG)

        try:
            # 1. Генерируем вектор через embedding_provider
            self._log_debug(f"[_search] Generating embedding...", event_type=EventType.DEBUG)

            if not self._embedding_provider:
                return {"error": "Embedding provider not initialized", "search_type": "error"}

            embedding_start = time.time()
            query_vector_list = await self._embedding_provider.generate([query])
            query_vector = np.array(query_vector_list[0], dtype=np.float32) if query_vector_list else None
            self._log_debug(f"[_search] Embedding done", event_type=EventType.DEBUG)

            # 2. Получаем FAISS индекс для указанного source
            self._log_debug(f"[_search] Getting FAISS for source='{source}'...", event_type=EventType.DEBUG)

            faiss = self._get_faiss_for_source(source)

            count = await faiss.count()
            if count == 0:
                from core.errors.exceptions import DataNotFoundError
                raise DataNotFoundError(
                    f"FAISS индекс пуст для коллекции '{source}'. "
                    f"Необходимо проиндексировать данные перед поиском.",
                    query=query
                )

            # 3. Поиск в FAISS
            self._log_debug(f"[_search] Searching FAISS ({count} vectors)...", event_type=EventType.DEBUG)

            faiss_search_start = time.time()
            faiss_results = await faiss.search(query_vector.tolist() if query_vector is not None else [], top_k=top_k)
            self._log_debug(f"[_search] FAISS done | results={len(faiss_results)}", event_type=EventType.DEBUG)

            results = []
            for result in faiss_results:
                if result.get("score", 0) < min_score:
                    continue

                meta = result.get("metadata", {})

                result_item = {
                    "score": result.get("score"),
                    "content": meta.get("content", ""),
                    "source": meta.get("source"),
                    "table": meta.get("table"),
                    "pk_value": meta.get("pk_value"),
                    "row": meta.get("row", {}),
                    "chunk_index": meta.get("chunk_index", 0),
                    "total_chunks": meta.get("total_chunks", 1),
                    "search_text": meta.get("search_text", ""),
                }

                results.append(result_item)

            total_time = time.time() - start_time
            self._log_debug(f"[_search] COMPLETE: {total_time:.2f}s, found={len(results)}", event_type=EventType.DEBUG)

            return {
                "results": results,
                "total_found": len(results)
            }

        except Exception as e:
            self._log_error(f"[_search] ERROR: {e}", event_type=EventType.ERROR)
            import traceback
            self._log_error(f"Traceback: {traceback.format_exc()}", event_type=EventType.ERROR)

            from core.errors.exceptions import VectorSearchError
            raise VectorSearchError(
                f"Векторный поиск не удался: {e}. "
                f"Проверьте что FAISS индекс создан, загружен и содержит данные.",
                component="vector_search_tool.search"
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
        - analyze(entity_id="audit_5", analysis_type="summary", prompt="Какие ключевые нарушения?")

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
        capability_name = "vector_search.analyze"
        prompt_obj = self.get_prompt(capability_name)
        prompt_template = prompt_obj.content if prompt_obj else ""

        if not prompt_template:
            from core.errors.exceptions import SkillExecutionError
            raise SkillExecutionError(
                f"Промпт для {capability_name} не загружен! Проверьте YAML в data/prompts/",
                component="vector_search_tool"
            )

        # Рендерим промпт
        llm_prompt = prompt_template.format(prompt=prompt, context=context)

        # Получаем output контракт для структурированного вывода
        output_schema = self.get_output_contract(capability_name)

        if not output_schema:
            from core.errors.exceptions import SkillExecutionError
            raise SkillExecutionError(
                f"Контракт для {capability_name} не загружен! Проверьте YAML в data/contracts/",
                component="vector_search_tool"
            )

        # Вызов LLM через executor с structured output
        result = await self.executor.execute_action(
            action_name="llm.generate_structured",
            llm_provider=self._llm_provider,
            parameters={
                'prompt': llm_prompt,
                'structured_output': {
                    'output_model': 'VectorSearchAnalysis',
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

        # Определяем source и ID из entity_id
        if entity_id.startswith("book_"):
            source = "books"
            entity_num = int(entity_id.replace("book_", ""))
            filter_key = "book_id"
        elif entity_id.startswith("audit_"):
            source = "audits"
            entity_num = int(entity_id.replace("audit_", ""))
            filter_key = "audit_id"
        elif entity_id.startswith("violation_"):
            source = "violations"
            entity_num = int(entity_id.replace("violation_", ""))
            filter_key = "violation_id"
        else:
            return ""

        # Получаем FAISS для этого source
        faiss = self._get_faiss_for_source(source)

        results = await faiss.search(
            query_vector=[0.0] * 384,  # Пустой вектор для получения любых чанков
            top_k=5,
        )

        # Фильтруем по entity_id
        filtered = [r for r in results if r.get("metadata", {}).get(filter_key) == entity_num]

        if not filtered:
            return ""

        context_parts = []
        for r in filtered[:5]:
            metadata = r.get("metadata", {})
            chapter = metadata.get("chapter")
            content = metadata.get("content", "")
            if chapter is not None:
                context_parts.append(f"[Глава/Раздел {chapter}]\n{content}")
            else:
                context_parts.append(content)

        return "\n\n".join(context_parts)
    
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
