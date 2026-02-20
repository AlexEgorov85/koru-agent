"""
VectorBooksTool — универсальный инструмент для работы с книгами.

Capabilities:
- search: Семантический поиск по текстам книг
- get_document: Получение полного текста книги (SQL)
- analyze: LLM анализ (герои, темы, etc.)
- query: SQL запрос к базе книг
"""

from typing import Optional, Dict, Any, List
from core.application.tools.base_tool import BaseTool
from core.models.types.vector_types import VectorSearchResult, VectorQuery
from core.models.types.analysis import AnalysisResult


class VectorBooksTool(BaseTool):
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
        faiss_provider=None,
        sql_provider=None,
        embedding_provider=None,
        llm_provider=None,
        cache_service=None,
        chunking_strategy=None
    ):
        self.faiss_provider = faiss_provider
        self.sql_provider = sql_provider
        self.embedding_provider = embedding_provider
        self.llm_provider = llm_provider
        self.cache_service = cache_service
        self.chunking_strategy = chunking_strategy
    
    @property
    def name(self) -> str:
        return "vector_books_tool"
    
    @property
    def description(self) -> str:
        return "Все операции с книгами: поиск + текст + анализ"
    
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
        Семантический поиск по книгам.
        
        Args:
            query: Текстовый запрос
            top_k: Количество результатов
            min_score: Минимальный порог
            filters: Фильтры по метаданным
        
        Returns:
            {"results": [...], "total_found": int}
        """
        
        # 1. Генерируем вектор запроса
        query_vector = await self.embedding_provider.generate([query])
        
        # 2. Ищем в FAISS
        faiss_results = await self.faiss_provider.search(
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
        
        return {
            "results": results,
            "total_found": len(results)
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
        
        # Извлекаем book_id из document_id
        book_id = int(document_id.replace("book_", ""))
        
        # SQL запрос для получения полного текста
        chapters = await self.sql_provider.fetch("""
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
        
        # 1. Проверка кэша
        cache_key = f"analysis:{analysis_type}:{entity_id}"
        if not force_refresh and self.cache_service:
            cached = await self.cache_service.get(cache_key)
            if cached:
                return cached
        
        # 2. Получение контекста
        context = await self._get_context(entity_id)
        
        # 3. LLM анализ
        llm_prompt = f"""
{prompt}

Контекст:
{context}

Ответь в формате JSON:
{{
    "result": {{...}},
    "confidence": 0.0-1.0,
    "reasoning": "обоснование"
}}
"""
        
        llm_response = await self.llm_provider.generate_json(llm_prompt)
        
        # 4. Формируем результат
        analysis = AnalysisResult(
            entity_id=entity_id,
            analysis_type=analysis_type,
            result=llm_response.get("result", {}),
            confidence=llm_response.get("confidence", 0.5),
            reasoning=llm_response.get("reasoning")
        )
        
        # 5. Сохранение в кэш
        if self.cache_service:
            await self.cache_service.set(
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
        
        result = await self.sql_provider.fetch(sql, parameters)
        
        return {
            "data": result
        }
