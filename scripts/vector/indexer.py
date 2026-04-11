#!/usr/bin/env python3
"""
Универсальный индексатор для векторного поиска.

Объединяет функциональность:
- index_authors.py
- index_books.py
- rebuild_books_index.py
- initial_indexing.py

ИСПОЛЬЗОВАНИЕ:
    # Создать пустые индексы для всех источников
    python -m scripts.vector.indexer init

    # Индексация авторов из БД
    python -m scripts.vector.indexer authors

    # Индексация книг из БД (полная, с чанками)
    python -m scripts.vector.indexer books --full

    # Индексация книг из БД (упрощённая, по заголовкам)
    python -m scripts.vector.indexer books

    # Индексация произвольной таблицы
    python -m scripts.vector.indexer table --table "Lib.genres" --column "name" --source genres
"""
import asyncio
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional

project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


# ===========================================================================
# Утилиты
# ===========================================================================

async def init_infrastructure(profile: str = "dev", data_dir: str = "data"):
    """Инициализация инфраструктуры (контексты + embedding + FAISS)."""
    from core.config import get_config
    from core.infrastructure_context.infrastructure_context import InfrastructureContext
    from core.infrastructure.providers.embedding.sentence_transformers_provider import SentenceTransformersProvider
    from core.infrastructure.providers.vector.faiss_provider import FAISSProvider
    from core.config.vector_config import EmbeddingConfig

    config = get_config(profile=profile, data_dir=data_dir)

    infra = InfrastructureContext(config)
    await infra.initialize()

    vs_config = config.vector_search

    # Embedding
    embedding = infra.get_embedding_provider()
    if not embedding:
        embedding_config = EmbeddingConfig(model_name=vs_config.embedding.model_name)
        embedding = SentenceTransformersProvider(embedding_config)
        await embedding.initialize()

    # FAISS провайдер (базовый)
    faiss_provider = FAISSProvider(
        dimension=vs_config.embedding.dimension,
        config=vs_config.faiss,
    )
    await faiss_provider.initialize()

    return infra, embedding, faiss_provider, vs_config


async def create_empty_indexes(vs_config) -> int:
    """Создание пустых FAISS индексов для всех источников."""
    print("=" * 60)
    print("СОЗДАНИЕ ПУСТЫХ ИНДЕКСОВ")
    print("=" * 60)

    from core.infrastructure.providers.vector.faiss_provider import FAISSProvider

    storage_path = Path(vs_config.storage.base_path)
    storage_path.mkdir(parents=True, exist_ok=True)

    for source, index_file in vs_config.indexes.items():
        print(f"\n  {source}:")

        provider = FAISSProvider(
            dimension=vs_config.embedding.dimension,
            config=vs_config.faiss,
        )
        await provider.initialize()

        index_path = storage_path / index_file
        await provider.save(str(index_path))

        count = await provider.count()
        print(f"     Создан: {index_path}")
        print(f"     Векторов: {count}")

    # Статистика
    print("\n" + "=" * 60)
    print("СТАТИСТИКА")
    print("=" * 60)

    for source, index_file in vs_config.indexes.items():
        index_path = storage_path / index_file
        status = "✅" if index_path.exists() else "❌"
        print(f"  {status} {source}: {index_file}")

    print("\n" + "=" * 60)
    print("✅ ИНДЕКСЫ СОЗДАНЫ!")
    print("=" * 60)
    return 0


async def save_index(provider, vs_config, source: str) -> Path:
    """Сохранение FAISS индекса в файл."""
    storage_path = Path(vs_config.storage.base_path)
    storage_path.mkdir(parents=True, exist_ok=True)

    index_file = vs_config.indexes.get(source, f"{source}_index.faiss")
    index_path = storage_path / index_file
    await provider.save(str(index_path))

    count = await provider.count()
    print(f"\n✅ Сохранено: {index_path}")
    print(f"✅ Всего векторов: {count}")
    return index_path


# ===========================================================================
# Стратегии индексации
# ===========================================================================

async def index_authors(embedding, faiss_provider, vs_config) -> int:
    """Индексация уникальных авторов из таблицы authors."""
    print("=" * 60)
    print("ИНДЕКСАЦИЯ АВТОРОВ")
    print("=" * 60)

    from core.config import get_config
    from core.infrastructure_context.infrastructure_context import InfrastructureContext
    import psycopg2

    config = get_config(profile="dev")
    db_config = config.db_providers.get("books_db")
    if not db_config:
        print("❌ DB провайдер 'books_db' не найден в конфигурации")
        return 1

    params = db_config.parameters
    conn = psycopg2.connect(
        host=params.get("host", "localhost"),
        port=params.get("port", 5432),
        database=params.get("database", "postgres"),
        user=params.get("user", "postgres"),
        password=params.get("password", ""),
    )
    conn.autocommit = True
    cursor = conn.cursor()

    cursor.execute("""
        SELECT DISTINCT a.last_name as author_name
        FROM "Lib".authors a
        WHERE a.last_name IS NOT NULL
        ORDER BY author_name
    """)
    authors = [row[0] for row in cursor.fetchall()]
    cursor.close()
    conn.close()

    print(f"Найдено авторов в БД: {len(authors)}\n")

    all_vectors = []
    all_metadata = []

    for author in authors:
        vector = await embedding.generate_single(author)
        metadata = {"author": author, "search_text": author}
        all_vectors.append(vector)
        all_metadata.append(metadata)
        print(f"   {author}: {len(vector)}d vector")

    print(f"\n📊 Добавление {len(all_vectors)} векторов в FAISS...")
    await faiss_provider.add(all_vectors, all_metadata)

    await save_index(faiss_provider, vs_config, "authors")

    print("\n" + "=" * 60)
    print("✅ ИНДЕКСАЦИЯ АВТОРОВ ЗАВЕРШЕНА!")
    print("=" * 60)
    return 0


async def index_books_simple(embedding, faiss_provider, vs_config) -> int:
    """Упрощённая индексация книг — по заголовкам из БД."""
    print("=" * 60)
    print("ИНДЕКСАЦИЯ КНИГ (по заголовкам)")
    print("=" * 60)

    from core.config import get_config
    from core.infrastructure_context.infrastructure_context import InfrastructureContext

    config = get_config(profile="dev")
    db_config = config.db_providers.get("books_db")
    if not db_config:
        print("❌ DB провайдер 'books_db' не найден")
        return 1

    params = db_config.parameters

    import psycopg2
    conn = psycopg2.connect(
        host=params.get("host", "localhost"),
        port=params.get("port", 5432),
        database=params.get("database", "postgres"),
        user=params.get("user", "postgres"),
        password=params.get("password", ""),
    )
    conn.autocommit = True
    cursor = conn.cursor()

    cursor.execute("""
        SELECT b.id, b.title, b.author_id, a.last_name, a.first_name
        FROM "Lib".books b
        JOIN "Lib".authors a ON b.author_id = a.id
        ORDER BY b.id
    """)
    rows = cursor.fetchall()
    books = [
        {
            "id": r[0],
            "title": r[1],
            "author_id": r[2],
            "last_name": r[3],
            "first_name": r[4],
        }
        for r in rows
    ]
    cursor.close()
    conn.close()

    print(f"Найдено книг в БД: {len(books)}\n")

    all_vectors = []
    all_metadata = []

    for book in books:
        text = f"{book['title']} {book['first_name']} {book['last_name']}"
        vector = await embedding.generate_single(text)
        metadata = {
            "book_id": book["id"],
            "title": book["title"],
            "author": f"{book['first_name']} {book['last_name']}",
            "search_text": text,
        }
        all_vectors.append(vector)
        all_metadata.append(metadata)
        print(f"   [{book['id']}] {book['title']} — {book['first_name']} {book['last_name']}")

    print(f"\n📊 Добавление {len(all_vectors)} векторов в FAISS...")
    await faiss_provider.add(all_vectors, all_metadata)

    await save_index(faiss_provider, vs_config, "books")

    print("\n" + "=" * 60)
    print("✅ ИНДЕКСАЦИЯ КНИГ ЗАВЕРШЕНА!")
    print("=" * 60)
    return 0


async def index_books_full(embedding, faiss_provider, vs_config) -> int:
    """Полная индексация книг — с чанками содержимого."""
    from core.infrastructure.providers.vector.chunking_strategy import SemanticChunkingStrategy
    from core.components.services.document_indexing_service import DocumentIndexingService

    print("=" * 60)
    print("ПОЛНАЯ ИНДЕКСАЦИЯ КНИГ (с чанками)")
    print("=" * 60)

    from core.config import get_config
    from core.infrastructure_context.infrastructure_context import InfrastructureContext

    config = get_config(profile="dev", data_dir="data")

    infra = InfrastructureContext(config)
    await infra.initialize()

    db_provider = infra.db_providers.get("books_db")
    if not db_provider:
        print("❌ DB провайдер 'books_db' не найден")
        await infra.shutdown()
        return 1

    # Chunking + DocumentIndexingService
    chunking = SemanticChunkingStrategy(
        embedding_model=embedding,
        max_chunk_size=500,
        chunk_overlap=50,
    )

    indexing_service = DocumentIndexingService(
        sql_provider=db_provider,
        faiss_provider=faiss_provider,
        embedding_provider=embedding,
        chunking_strategy=chunking,
    )

    # Список книг
    books_result = await db_provider.fetch("SELECT id, title, author FROM books ORDER BY id")
    if not books_result:
        print("❌ Книги не найдены в БД")
        await infra.shutdown()
        return 1

    print(f"Найдено книг: {len(books_result)}\n")

    total_chunks = 0
    for book in books_result:
        book_id = book["id"]
        title = book["title"]
        author = book["author"]
        print(f"  📖 [{book_id}] {title} ({author})")

        try:
            result = await indexing_service.index_book(book_id)
            if "error" in result:
                print(f"     ❌ Ошибка: {result['error']}")
            else:
                chunks = result.get("chunks_indexed", 0)
                total_chunks += chunks
                print(f"     ✅ Чанков: {chunks}")
        except Exception as e:
            print(f"     ❌ Исключение: {e}")

    await save_index(faiss_provider, vs_config, "books")

    print("\n" + "=" * 60)
    print("СТАТИСТИКА")
    print("=" * 60)
    print(f"  Книг обработано: {len(books_result)}")
    print(f"  Чанков проиндексировано: {total_chunks}")

    await infra.shutdown()

    print("\n" + "=" * 60)
    print("✅ ПОЛНАЯ ИНДЕКСАЦИЯ ЗАВЕРШЕНА!")
    print("=" * 60)
    return 0


async def index_table(table: str, column: str, source: str, embedding, faiss_provider, vs_config) -> int:
    """Индексация произвольной таблицы."""
    print("=" * 60)
    print(f"ИНДЕКСАЦИЯ ТАБЛИЦЫ: {table}.{column}")
    print("=" * 60)

    from core.config import get_config
    from core.infrastructure_context.infrastructure_context import InfrastructureContext
    import psycopg2

    config = get_config(profile="dev")
    db_config = config.db_providers.get("books_db")
    if not db_config:
        print("❌ DB провайдер 'books_db' не найден")
        return 1

    params = db_config.parameters
    conn = psycopg2.connect(
        host=params.get("host", "localhost"),
        port=params.get("port", 5432),
        database=params.get("database", "postgres"),
        user=params.get("user", "postgres"),
        password=params.get("password", ""),
    )
    conn.autocommit = True
    cursor = conn.cursor()

    cursor.execute(f'SELECT id, "{column}" FROM {table} WHERE "{column}" IS NOT NULL ORDER BY id')
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    print(f"Найдено записей: {len(rows)}\n")

    all_vectors = []
    all_metadata = []

    for row in rows:
        row_id, text = row
        vector = await embedding.generate_single(str(text))
        metadata = {"id": row_id, source: str(text), "search_text": str(text)}
        all_vectors.append(vector)
        all_metadata.append(metadata)
        print(f"   [{row_id}] {str(text)[:60]}...")

    print(f"\n📊 Добавление {len(all_vectors)} векторов в FAISS...")
    await faiss_provider.add(all_vectors, all_metadata)

    await save_index(faiss_provider, vs_config, source)

    print("\n" + "=" * 60)
    print(f"✅ ИНДЕКСАЦИЯ {source} ЗАВЕРШЕНА!")
    print("=" * 60)
    return 0


# ===========================================================================
# CLI
# ===========================================================================

def build_parser():
    import argparse

    parser = argparse.ArgumentParser(
        description="Универсальный индексатор для векторного поиска",
    )
    subparsers = parser.add_subparsers(dest="command", help="Команды индексации")

    # init — создание пустых индексов
    subparsers.add_parser("init", help="Создать пустые индексы для всех источников")

    # authors
    subparsers.add_parser("authors", help="Индексация авторов из таблицы authors")

    # books
    books_parser = subparsers.add_parser("books", help="Индексация книг из БД")
    books_parser.add_argument(
        "--full", action="store_true",
        help="Полная индексация с чанками содержимого (медленнее, но точнее)"
    )

    # table — произвольная таблица
    table_parser = subparsers.add_parser("table", help="Индексация произвольной таблицы")
    table_parser.add_argument("--table", required=True, help="Имя таблицы (например, Lib.genres)")
    table_parser.add_argument("--column", required=True, help="Столбец для индексации")
    table_parser.add_argument("--source", required=True, help="Имя источника для FAISS")

    return parser


async def async_main():
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    if args.command == "init":
        from core.config import get_config
        config = get_config(profile="dev")
        vs_config = config.vector_search
        return await create_empty_indexes(vs_config)

    # Для всех остальных команд нужна инфраструктура
    infra, embedding, faiss_provider, vs_config = await init_infrastructure()

    try:
        if args.command == "authors":
            return await index_authors(embedding, faiss_provider, vs_config)
        elif args.command == "books":
            if args.full:
                return await index_books_full(embedding, faiss_provider, vs_config)
            else:
                return await index_books_simple(embedding, faiss_provider, vs_config)
        elif args.command == "table":
            return await index_table(args.table, args.column, args.source, embedding, faiss_provider, vs_config)
        else:
            parser.print_help()
            return 1
    finally:
        await infra.shutdown()


def main():
    sys.exit(asyncio.run(async_main()))


if __name__ == "__main__":
    main()
