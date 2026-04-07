#!/usr/bin/env python3
"""
Скрипт пересоздания векторной БД книг.

Запуск:
    python scripts/vector/rebuild_books_index.py

Пересоздаёт FAISS индекс для всех книг из SQL базы.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


async def main():
    """Пересоздание векторной БД книг."""
    from core.config import get_config
    from core.infrastructure_context.infrastructure_context import InfrastructureContext
    from core.infrastructure.providers.vector.faiss_provider import FAISSProvider
    from core.infrastructure.providers.vector.chunking_strategy import SemanticChunkingStrategy
    from core.components.services.document_indexing_service import DocumentIndexingService

    print("=" * 60)
    print("ПЕРЕСОЗДАНИЕ ВЕКТОРНОЙ БД КНИГ")
    print("=" * 60)

    try:
        # 1. Инициализация
        print("\n1. Инициализация контекстов...")
        config = get_config(profile='dev', data_dir='data')
        config.log_level = 'WARNING'
        
        infra = InfrastructureContext(config)
        await infra.initialize()
        print("✅ Контексты инициализированы")

        # 2. Получаем провайдеры
        print("\n2. Получение провайдеров...")
        
        db_provider = infra.db_providers.get('books_db')
        if not db_provider:
            print("❌ DB provider 'books_db' не найден")
            return 1
        print(f"✅ DB provider: {db_provider}")

        embedding = infra.get_embedding_provider()
        if not embedding:
            print("❌ Embedding провайдер не инициализирован")
            return 1
        print(f"✅ Embedding: {type(embedding).__name__}")

        faiss_config = config.vector_search
        faiss_provider = FAISSProvider(
            dimension=faiss_config.embedding.dimension,
            config=faiss_config.faiss
        )
        await faiss_provider.initialize()
        print(f"✅ FAISS: dimension={faiss_config.embedding.dimension}")

        # 3. Создаём сервис индексации
        print("\n3. Создание DocumentIndexingService...")
        chunking = SemanticChunkingStrategy(
            embedding_model=embedding,
            max_chunk_size=500,
            chunk_overlap=50
        )
        
        indexing_service = DocumentIndexingService(
            sql_provider=db_provider,
            faiss_provider=faiss_provider,
            embedding_provider=embedding,
            chunking_strategy=chunking
        )
        print("✅ DocumentIndexingService создан")

        # 4. Получаем список всех книг
        print("\n4. Получение списка книг...")
        books_result = await db_provider.fetch(
            "SELECT id, title, author FROM books ORDER BY id"
        )
        
        if not books_result:
            print("❌ Книги не найдены в БД")
            return 1
        
        print(f"✅ Найдено книг: {len(books_result)}")

        # 5. Индексация каждой книги
        print("\n5. Индексация книг...")
        total_chunks = 0
        
        for book in books_result:
            book_id = book['id']
            title = book['title']
            author = book['author']
            
            print(f"\n  📖 [{book_id}] {title} ({author})")
            
            try:
                result = await indexing_service.index_book(book_id)
                
                if 'error' in result:
                    print(f"     ❌ Ошибка: {result['error']}")
                else:
                    chunks = result.get('chunks_indexed', 0)
                    total_chunks += chunks
                    print(f"     ✅ Проиндексировано чанков: {chunks}")
                    
            except Exception as e:
                print(f"     ❌ Исключение: {e}")

        # 6. Сохранение индекса
        print("\n6. Сохранение FAISS индекса...")
        storage_path = Path(faiss_config.storage.base_path)
        storage_path.mkdir(parents=True, exist_ok=True)
        
        index_file = storage_path / faiss_config.indexes['books']
        await faiss_provider.save(str(index_file))
        
        count = await faiss_provider.count()
        print(f"✅ Сохранено в: {index_file}")
        print(f"✅ Всего векторов: {count}")

        # 7. Статистика
        print("\n" + "=" * 60)
        print("СТАТИСТИКА")
        print("=" * 60)
        print(f"  Книг обработано: {len(books_result)}")
        print(f"  Чанков проиндексировано: {total_chunks}")
        print(f"  Векторов в индексе: {count}")
        print(f"  Файл индекса: {index_file}")

        # 8. Завершение
        await infra.shutdown()

        print("\n" + "=" * 60)
        print("✅ ПЕРЕСОЗДАНИЕ ЗАВЕРШЕНО!")
        print("=" * 60)

        return 0

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
