#!/usr/bin/env python3
"""
Полная переиндексация всех векторных БД.
"""
import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


async def main():
    from core.config import get_config
    from core.infrastructure_context.infrastructure_context import InfrastructureContext
    from core.infrastructure.providers.embedding.sentence_transformers_provider import SentenceTransformersProvider
    from core.infrastructure.providers.vector.faiss_provider import FAISSProvider
    from core.config.vector_config import EmbeddingConfig, VectorSearchConfig
    import psycopg2
    import numpy as np

    config = get_config(profile="dev", data_dir="data")
    vs_config = config.vector_search

    # Инициализация embedding
    embedding = SentenceTransformersProvider(vs_config.embedding)
    await embedding.initialize()
    print(f"✅ Embedding модель: {vs_config.embedding.model_name} ({vs_config.embedding.dimension}d)")

    # Путь к хранилищу
    storage_path = Path(vs_config.storage.base_path)
    storage_path.mkdir(parents=True, exist_ok=True)

    # Подключение к БД
    db_config = config.db_providers.get("default_db")
    if not db_config:
        print("❌ DB провайдер 'default_db' не найден")
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
    print("✅ Подключение к БД: PostgreSQL")

    # =========================================================================
    # 1. ИНДЕКСАЦИЯ АВТОРОВ
    # =========================================================================
    print("\n" + "=" * 60)
    print("1. ИНДЕКСАЦИЯ АВТОРОВ")
    print("=" * 60)

    cursor.execute("""
        SELECT DISTINCT a.last_name as author_name
        FROM "Lib".authors a
        WHERE a.last_name IS NOT NULL
        ORDER BY author_name
    """)
    authors = [row[0] for row in cursor.fetchall()]
    print(f"Найдено авторов: {len(authors)}")

    authors_provider = FAISSProvider(dimension=vs_config.embedding.dimension, config=vs_config.faiss)
    await authors_provider.initialize()

    authors_vectors = []
    authors_metadata = []
    for author in authors:
        vector = await embedding.generate_single(author)
        authors_vectors.append(vector)
        authors_metadata.append({"author": author, "search_text": author})
        print(f"   {author}")

    await authors_provider.add(authors_vectors, authors_metadata)
    authors_index_path = storage_path / vs_config.indexes["authors"]
    await authors_provider.save(str(authors_index_path))
    count = await authors_provider.count()
    print(f"✅ Сохранено authors_index: {count} векторов")
    await authors_provider.shutdown()

    # =========================================================================
    # 2. ИНДЕКСАЦИЯ АУДИТОРСКИХ ПРОВЕРОК
    # =========================================================================
    print("\n" + "=" * 60)
    print("2. ИНДЕКСАЦИЯ АУДИТОРСКИХ ПРОВЕРОК")
    print("=" * 60)

    cursor.execute("""
        SELECT id, title, audit_type, status, auditee_entity
        FROM audits
        WHERE title IS NOT NULL
        ORDER BY id
    """)
    audits = cursor.fetchall()
    print(f"Найдено проверок: {len(audits)}")

    audits_provider = FAISSProvider(dimension=vs_config.embedding.dimension, config=vs_config.faiss)
    await audits_provider.initialize()

    audits_vectors = []
    audits_metadata = []
    for row in audits:
        audit_id, title, audit_type, status, auditee_entity = row
        search_parts = [title]
        if auditee_entity:
            search_parts.append(auditee_entity)
        if audit_type:
            search_parts.append(audit_type)
        search_text = " ".join(str(p) for p in search_parts if p)

        vector = await embedding.generate_single(search_text)
        audits_vectors.append(vector)
        audits_metadata.append({
            "audit_id": audit_id,
            "title": title,
            "audit_type": audit_type or "",
            "status": status or "",
            "auditee_entity": auditee_entity or "",
            "search_text": search_text,
        })
        print(f"   [{audit_id}] {title[:60]}... | {auditee_entity or '—'} | {status}")

    await audits_provider.add(audits_vectors, audits_metadata)
    audits_index_path = storage_path / vs_config.indexes["audits"]
    await audits_provider.save(str(audits_index_path))
    count = await audits_provider.count()
    print(f"✅ Сохранено audits_index: {count} векторов")
    await audits_provider.shutdown()

    # =========================================================================
    # 4. ИНДЕКСАЦИЯ ОТКЛОНЕНИЙ
    # =========================================================================
    print("\n" + "=" * 60)
    print("4. ИНДЕКСАЦИЯ ОТКЛОНЕНИЙ")
    print("=" * 60)

    cursor.execute("""
        SELECT v.id, v.violation_code, v.description, v.severity, v.status,
               v.responsible, a.title as audit_title
        FROM violations v
        JOIN audits a ON v.audit_id = a.id
        WHERE v.description IS NOT NULL
        ORDER BY v.id
    """)
    violations = cursor.fetchall()
    print(f"Найдено отклонений: {len(violations)}")

    violations_provider = FAISSProvider(dimension=vs_config.embedding.dimension, config=vs_config.faiss)
    await violations_provider.initialize()

    violations_vectors = []
    violations_metadata = []
    for row in violations:
        viol_id, viol_code, description, severity, status, responsible, audit_title = row
        search_parts = []
        if description:
            search_parts.append(description)
        if viol_code:
            search_parts.append(viol_code)
        if audit_title:
            search_parts.append(audit_title)
        search_text = " ".join(str(p) for p in search_parts if p)

        vector = await embedding.generate_single(search_text)
        violations_vectors.append(vector)
        violations_metadata.append({
            "violation_id": viol_id,
            "violation_code": viol_code or "",
            "description": description or "",
            "severity": severity or "",
            "status": status or "",
            "responsible": responsible or "",
            "audit_title": audit_title or "",
            "search_text": search_text,
        })
        print(f"   [{viol_id}] {viol_code or '—'} | {severity} | {status} | {description[:50]}...")

    await violations_provider.add(violations_vectors, violations_metadata)
    violations_index_path = storage_path / vs_config.indexes["violations"]
    await violations_provider.save(str(violations_index_path))
    count = await violations_provider.count()
    print(f"✅ Сохранено violations_index: {count} векторов")
    await violations_provider.shutdown()

    # =========================================================================
    # ИТОГО
    # =========================================================================
    cursor.close()
    conn.close()
    await embedding.shutdown()

    print("\n" + "=" * 60)
    print("ИТОГОВАЯ СТАТИСТИКА")
    print("=" * 60)

    import json
    for source, index_file in vs_config.indexes.items():
        metadata_path = storage_path / index_file.replace(".faiss", "_metadata.json")
        if metadata_path.exists():
            with open(metadata_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                count = len(data.get("metadata", {}))
                print(f"  ✅ {source}: {count} векторов")
        else:
            print(f"  ❌ {source}: файл не найден")

    print("\n" + "=" * 60)
    print("✅ ВСЕ ИНДЕКСЫ ПЕРЕСОЗДАНЫ!")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
