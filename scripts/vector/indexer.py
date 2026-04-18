#!/usr/bin/env python3
"""
Универсальный индексатор для векторного поиска.

Объединяет функциональность:
- index_authors.py
- initial_indexing.py

ИСПОЛЬЗОВАНИЕ:
    # Создать пустые индексы для всех источников
    python -m scripts.vector.indexer init

    # Индексация авторов из БД
    python -m scripts.vector.indexer authors

    # Индексация аудитов
    python -m scripts.vector.indexer audits

    # Индексация нарушений
    python -m scripts.vector.indexer violations
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

async def init_infrastructure(profile: str = "prod", data_dir: str = "data"):
    """Инициализация инфраструктуры (контексты + embedding + FAISS).
    
    NOTE: Не используем InfrastructureContext, так как его shutdown()
    перезаписывает FAISS файлы своими внутренними провайдерами.
    """
    from core.config import get_config
    from core.config.vector_config import EmbeddingConfig

    config = get_config(profile=profile, data_dir=data_dir)

    # Empty infra mock для совместимости с shutdown
    class DummyInfra:
        async def shutdown(self):
            pass
    
    infra = DummyInfra()
    vs_config = config.vector_search

# Выбор провайдера на основе модели
    model_name = vs_config.embedding.model_name
    if "Giga-Embeddings" in model_name or "giga" in model_name.lower():
        from core.infrastructure.providers.embedding.giga_embeddings_provider import GigaEmbeddingsProvider
        embedding = GigaEmbeddingsProvider(vs_config.embedding)
    else:
        from core.infrastructure.providers.embedding.sentence_transformers_provider import SentenceTransformersProvider
        embedding_config = EmbeddingConfig(model_name=vs_config.embedding.model_name, dimension=vs_config.embedding.dimension)
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
        status = "[OK]" if index_path.exists() else "[FAIL]"
        print(f"  {status} {source}: {index_file}")

    print("\n" + "=" * 60)
    print("[OK] ИНДЕКСЫ СОЗДАНЫ!")
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
    print(f"\n[OK] Saved: {index_path}")
    print(f"[OK] Total vectors: {count}")
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
    from core.models.types.vector_types import RowMetadata
    import psycopg2

    config = get_config(profile="dev")
    db_config = config.db_providers.get("default_db")
    if not db_config:
        print("[ERROR] DB provider 'default_db' not found in config")
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
        SELECT id, last_name, first_name, birth_date
        FROM "Lib".authors
        WHERE last_name IS NOT NULL
        ORDER BY last_name, first_name
    """)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    print(f"Найдено авторов в БД: {len(rows)}\n")

    all_vectors = []
    all_metadata = []

    for row in rows:
        row_dict = {
            "id": row[0],
            "last_name": row[1],
            "first_name": row[2],
            "birth_date": str(row[3]) if row[3] else None,
        }

        search_text = f"{row_dict['first_name']} {row_dict['last_name']}"

        vector = await embedding.generate_single(search_text)

        metadata = RowMetadata(
            source="authors",
            table="Lib.authors",
            primary_key="id",
            pk_value=row_dict["id"],
            row=row_dict,
            chunk_index=0,
            total_chunks=1,
            search_text=search_text,
            content=search_text,
        )

        all_vectors.append(vector)
        all_metadata.append(metadata.model_dump())
        print(f"   [{row_dict['id']}] {search_text}: {len(vector)}d vector")

    print(f"\n[STAT] Adding {len(all_vectors)} vectors to FAISS...")
    await faiss_provider.add(all_vectors, all_metadata)

    await save_index(faiss_provider, vs_config, "authors")


async def index_audits(embedding, faiss_provider, vs_config) -> int:
    """Индексация аудиторских проверок — по заголовкам и проверяемым объектам."""
    print("=" * 60)
    print("AUDITS INDEXING")
    print("=" * 60)

    from core.config import get_config
    from core.models.types.vector_types import RowMetadata
    import psycopg2

    config = get_config(profile="prod")
    db_config = config.db_providers.get("default_db")
    if not db_config:
        print("[ERROR] DB provider 'default_db' not found")
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
        SELECT id, title, audit_type, planned_date, actual_date, status, auditee_entity
        FROM oarb.audits
        WHERE title IS NOT NULL
        ORDER BY id
    """)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    print(f"Найдено проверок: {len(rows)}\n")

    all_vectors = []
    all_metadata = []

    for row in rows:
        row_dict = {
            "id": row[0],
            "title": row[1],
            "audit_type": row[2],
            "planned_date": str(row[3]) if row[3] else None,
            "actual_date": str(row[4]) if row[4] else None,
            "status": row[5],
            "auditee_entity": row[6],
        }

        search_parts = [row_dict["title"]]
        if row_dict["auditee_entity"]:
            search_parts.append(row_dict["auditee_entity"])
        if row_dict["audit_type"]:
            search_parts.append(row_dict["audit_type"])
        search_text = " ".join(str(p) for p in search_parts if p)

        vector = await embedding.generate_single(search_text)

        metadata = RowMetadata(
            source="audits",
            table="oarb.audits",
            primary_key="id",
            pk_value=row_dict["id"],
            row=row_dict,
            chunk_index=0,
            total_chunks=1,
            search_text=search_text,
            content=search_text,
        )

        all_vectors.append(vector)
        all_metadata.append(metadata.model_dump())
        print(f"   [{row_dict['id']}] {row_dict['title'][:60]}... | {row_dict['auditee_entity'] or '—'} | {row_dict['status']}")

    print(f"\n[STAT] Adding {len(all_vectors)} vectors to FAISS...")
    await faiss_provider.add(all_vectors, all_metadata)

    await save_index(faiss_provider, vs_config, "audits")

    print("\n" + "=" * 60)
    print("[OK] AUDITS INDEXING COMPLETED!")
    print("=" * 60)
    return 0


async def index_violations(embedding, faiss_provider, vs_config) -> int:
    """Индексация отклонений — по описанию и коду нарушения."""
    print("=" * 60)
    print("VIOLATIONS INDEXING")
    print("=" * 60)

    from core.config import get_config
    from core.models.types.vector_types import RowMetadata
    import psycopg2

    config = get_config(profile="prod")
    db_config = config.db_providers.get("default_db")
    if not db_config:
        print("[ERROR] DB provider 'default_db' not found")
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
        SELECT v.id, v.violation_code, v.description, v.recommendation,
               v.severity, v.status, v.responsible, v.deadline, v.audit_id,
               a.title as audit_title, a.status as audit_status
        FROM oarb.violations v
        JOIN oarb.audits a ON v.audit_id = a.id
        WHERE v.description IS NOT NULL
        ORDER BY v.id
    """)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    print(f"Найдено отклонений: {len(rows)}\n")

    all_vectors = []
    all_metadata = []

    for row in rows:
        row_dict = {
            "id": row[0],
            "violation_code": row[1],
            "description": row[2],
            "recommendation": row[3],
            "severity": row[4],
            "status": row[5],
            "responsible": row[6],
            "deadline": str(row[7]) if row[7] else None,
            "audit_id": row[8],
            "audit_title": row[9],
            "audit_status": row[10],
        }

        search_parts = []
        if row_dict["description"]:
            search_parts.append(row_dict["description"])
        if row_dict["violation_code"]:
            search_parts.append(row_dict["violation_code"])
        if row_dict["audit_title"]:
            search_parts.append(row_dict["audit_title"])
        search_text = " ".join(str(p) for p in search_parts if p)

        vector = await embedding.generate_single(search_text)

        metadata = RowMetadata(
            source="violations",
            table="oarb.violations",
            primary_key="id",
            pk_value=row_dict["id"],
            row=row_dict,
            chunk_index=0,
            total_chunks=1,
            search_text=search_text,
            content=search_text,
        )

        all_vectors.append(vector)
        all_metadata.append(metadata.model_dump())
        print(f"   [{row_dict['id']}] {row_dict['violation_code'] or '—'} | {row_dict['severity']} | {row_dict['status']} | {row_dict['description'][:50]}...")

    print(f"\nAdding {len(all_vectors)} vectors to FAISS...")
    await faiss_provider.add(all_vectors, all_metadata)

    await save_index(faiss_provider, vs_config, "violations")

    print("\n" + "=" * 60)
    print("VIOLATIONS INDEXING COMPLETED!")
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

    # audits
    subparsers.add_parser("audits", help="Индексация аудиторских проверок")

    # violations
    subparsers.add_parser("violations", help="Индексация отклонений")

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
    infra, embedding, faiss_provider, vs_config = await init_infrastructure(profile="dev")

    try:
        if args.command == "authors":
            return await index_authors(embedding, faiss_provider, vs_config)
        elif args.command == "audits":
            return await index_audits(embedding, faiss_provider, vs_config)
        elif args.command == "violations":
            return await index_violations(embedding, faiss_provider, vs_config)
        else:
            parser.print_help()
            return 1
    finally:
        await infra.shutdown()


def main():
    sys.exit(asyncio.run(async_main()))


if __name__ == "__main__":
    main()
