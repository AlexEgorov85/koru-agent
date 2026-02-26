"""
DocumentIndexingService — сервис индексации документов.

Используется для:
- Первичной индексации книг
- Переиндексации обновлённых книг
- Удаления книг из индекса
"""

from typing import List, Optional, Dict, Any
from core.models.types.vector_types import VectorChunk


class DocumentIndexingService:
    """
    Сервис индексации документов.
    
    Пример использования:
        service = DocumentIndexingService(sql, faiss, embedding, chunking)
        await service.index_book(book_id=1)
    """
    
    def __init__(
        self,
        sql_provider,
        faiss_provider,
        embedding_provider,
        chunking_strategy
    ):
        self.sql_provider = sql_provider
        self.faiss_provider = faiss_provider
        self.embedding_provider = embedding_provider
        self.chunking_strategy = chunking_strategy
    
    async def index_book(self, book_id: int) -> Dict[str, Any]:
        """
        Индексация книги.
        
        Args:
            book_id: ID книги
        
        Returns:
            {"book_id": int, "chunks_indexed": int, "vectors_added": int}
        """
        
        # 1. Получаем текст из SQL
        chapters = await self.sql_provider.fetch("""
            SELECT chapter, content
            FROM book_texts
            WHERE book_id = ?
            ORDER BY chapter
        """, (book_id,))
        
        if not chapters:
            return {"error": f"Book {book_id} not found"}
        
        # 2. Разбиваем на чанки
        all_chunks: List[VectorChunk] = []
        for chapter in chapters:
            chunks = await self.chunking_strategy.split(
                content=chapter["content"],
                document_id=f"book_{book_id}",
                metadata={
                    "book_id": book_id,
                    "chapter": chapter["chapter"]
                }
            )
            all_chunks.extend(chunks)
        
        # 3. Генерируем векторы
        vectors = await self.embedding_provider.generate(
            [chunk.content for chunk in all_chunks]
        )
        
        # 4. Формируем метаданные
        metadata = []
        for chunk in all_chunks:
            meta = {
                "chunk_id": chunk.id,
                "document_id": chunk.document_id,
                "book_id": book_id,
                "chapter": chunk.metadata.get("chapter"),
                "chunk_index": chunk.index,
                "content": chunk.content
            }
            metadata.append(meta)
        
        # 5. Добавляем в FAISS
        vector_ids = await self.faiss_provider.add(vectors, metadata)
        
        # 6. Помечаем книгу как проиндексированную
        await self.sql_provider.execute("""
            UPDATE books SET indexed_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (book_id,))
        
        return {
            "book_id": book_id,
            "chunks_indexed": len(all_chunks),
            "vectors_added": len(vector_ids)
        }
    
    async def reindex_book(self, book_id: int) -> Dict[str, Any]:
        """
        Переиндексация книги (удаление + добавление).
        
        Args:
            book_id: ID книги
        
        Returns:
            {"book_id": int, "deleted": int, "indexed": int}
        """
        
        # 1. Удаляем старые векторы
        deleted = await self.faiss_provider.delete_by_filter({
            "book_id": book_id
        })
        
        # 2. Индексируем заново
        result = await self.index_book(book_id)
        
        return {
            "book_id": book_id,
            "deleted": deleted,
            "indexed": result.get("chunks_indexed", 0)
        }
    
    async def delete_book(self, book_id: int) -> Dict[str, Any]:
        """
        Удаление книги из индекса.
        
        Args:
            book_id: ID книги
        
        Returns:
            {"book_id": int, "deleted": int}
        """
        
        deleted = await self.faiss_provider.delete_by_filter({
            "book_id": book_id
        })
        
        return {
            "book_id": book_id,
            "deleted": deleted
        }
    
    async def index_all_books(self) -> List[Dict[str, Any]]:
        """
        Индексация всех книг.
        
        Returns:
            Список результатов индексации
        """
        
        # Получаем все книги
        books = await self.sql_provider.fetch("SELECT id FROM books")
        
        results = []
        for book in books:
            try:
                result = await self.index_book(book["id"])
                results.append(result)
            except Exception as e:
                results.append({
                    "book_id": book["id"],
                    "error": str(e)
                })
        
        return results
