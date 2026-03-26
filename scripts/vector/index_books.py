#!/usr/bin/env python3
"""
Скрипт индексации книг в FAISS.

Запуск:
    python scripts/vector/index_books.py

Создаёт FAISS индекс для книг из тестовых данных.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


async def main():
    """Индексация книг в FAISS."""
    from core.config import get_config
    from core.infrastructure_context.infrastructure_context import InfrastructureContext
    from core.infrastructure.providers.vector.faiss_provider import FAISSProvider

    print("=" * 60)
    print("ИНДЕКСАЦИЯ КНИГ В FAISS")
    print("=" * 60)

    test_books = [
        {
            "id": 1,
            "title": "Евгений Онегин",
            "author": "А.С. Пушкин",
            "chapters": [
                {"chapter": 1, "content": "Мой дядя самых честных правил, Когда не в шутку занемог..."},
                {"chapter": 2, "content": "Онегин, добрый мой приятель, родился на брегах Невы..."},
                {"chapter": 3, "content": "Где любит? где не любит? юный взгляд так беспокойно轮的..."},
            ]
        },
        {
            "id": 2,
            "title": "Капитанская дочка",
            "author": "А.С. Пушкин",
            "chapters": [
                {"chapter": 1, "content": "С一家人 в() очной() стороне() сторожили меня..."},
                {"chapter": 2, "content": "Отец мой, Андрей Петрович Гринев, служил при графе Минихе..."},
            ]
        },
        {
            "id": 3,
            "title": "Преступление и наказание",
            "author": "Ф.М. Достоевский",
            "chapters": [
                {"chapter": 1, "content": "В начале июля, в чрезвычайно жаркое время..."},
            ]
        },
    ]

    try:
        config = get_config(profile='dev')
        infra = InfrastructureContext(config)
        await infra.initialize()

        embedding = infra.get_embedding_provider()
        if not embedding:
            print("ERROR: Embedding провайдер не инициализирован")
            return 1

        provider = infra.get_faiss_provider('books')
        if not provider:
            provider = FAISSProvider(dimension=384)
            await provider.initialize()

        all_vectors = []
        all_metadata = []

        for book in test_books:
            print(f"\n[B] {book['title']} ({book['author']})")
            
            for chapter in book['chapters']:
                text = chapter['content']
                vector = await embedding.generate_single(text)
                
                metadata = {
                    "book_id": book['id'],
                    "title": book['title'],
                    "author": book['author'],
                    "chapter": chapter['chapter'],
                    "content": text[:100] + "..." if len(text) > 100 else text
                }
                
                all_vectors.append(vector)
                all_metadata.append(metadata)
                print(f"   Глава {chapter['chapter']}: {len(vector)}d вектор")

        print(f"\n📊 Добавление {len(all_vectors)} векторов в FAISS...")
        await provider.add(all_vectors, all_metadata)

        count = await provider.count()
        print(f"✅ FAISS индекс: {count} векторов")

        storage_path = Path("data/vector")
        storage_path.mkdir(parents=True, exist_ok=True)
        await provider.save(str(storage_path / "books_index.faiss"))
        print(f"✅ Сохранено в data/vector/books_index.faiss")

        await infra.shutdown()

        print("\n" + "=" * 60)
        print("✅ ИНДЕКСАЦИЯ ЗАВЕРШЕНА!")
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
