#!/usr/bin/env python3
"""
Скрипт индексации авторов в FAISS.

Запуск:
    python scripts/vector/index_authors.py

Создаёт FAISS индекс для уникальных авторов из таблицы books.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


async def main():
    """Индексация авторов в FAISS."""
    from core.config import get_config
    from core.infrastructure.providers.vector.faiss_provider import FAISSProvider
    from core.infrastructure.providers.embedding.sentence_transformers_provider import SentenceTransformersProvider
    from core.config.vector_config import EmbeddingConfig

    print("=" * 60)
    print("INDEXING AUTHORS TO FAISS")
    print("=" * 60)

    try:
        config = get_config(profile='dev')
        
        embedding_config = EmbeddingConfig(model_name="models/embedding/all-MiniLM-L6-v2")
        embedding = SentenceTransformersProvider(embedding_config)
        await embedding.initialize()

        provider = FAISSProvider(dimension=384)
        await provider.initialize()

        import psycopg2
        conn = psycopg2.connect(
            host="localhost",
            port=5432,
            database="postgres",
            user="postgres",
            password="1"
        )
        conn.autocommit = True
        cursor = conn.cursor()
        
        cursor.execute("SELECT DISTINCT author FROM \"Lib\".books WHERE author IS NOT NULL AND author != '' ORDER BY author")
        authors = [row[0] for row in cursor.fetchall()]
        cursor.close()
        conn.close()
        
        print(f"Found authors in DB: {len(authors)}")

        all_vectors = []
        all_metadata = []

        for author in authors:
            vector = await embedding.generate_single(author)
            
            metadata = {
                "author": author,
                "search_text": author
            }
            
            all_vectors.append(vector)
            all_metadata.append(metadata)
            print(f"   {author}: {len(vector)}d vector")

        print(f"\nAdding {len(all_vectors)} vectors to FAISS...")
        await provider.add(all_vectors, all_metadata)

        count = await provider.count()
        print(f"FAISS index: {count} authors")

        storage_path = Path("data/vector")
        storage_path.mkdir(parents=True, exist_ok=True)
        await provider.save(str(storage_path / "authors_index.faiss"))
        print(f"Saved to data/vector/authors_index.faiss")

        await embedding.shutdown()

        print("\n" + "=" * 60)
        print("INDEXING COMPLETED!")
        print("=" * 60)
        return 0

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
