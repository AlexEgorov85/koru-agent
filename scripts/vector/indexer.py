#!/usr/bin/env python3
"""
Универсальный индексатор для векторного поиска.

Использует централизованную конфигурацию SOURCE_CONFIG из core/config/vector_config.py.

ИСПОЛЬЗОВАНИЕ:
    # Создать пустые индексы для всех источников
    python -m scripts.vector.indexer init

    # Индексация всех источников
    python -m scripts.vector.indexer all

    # Индексация конкретного источника
    python -m scripts.vector.indexer authors
    python -m scripts.vector.indexer audits
    python -m scripts.vector.indexer violations
    python -m scripts.vector.indexer books
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

async def _init_infrastructure(profile: str = "dev", data_dir: str = "data"):
    """Инициализация инфраструктуры (embedding + FAISS)."""
    from core.config import get_config
    from core.config.vector_config import EmbeddingConfig
    from core.infrastructure.providers.vector.faiss_provider import FAISSProvider

    config = get_config(profile=profile, data_dir=data_dir)
    vs_config = config.vector_search

    # Empty infra mock для совместимости с shutdown
    class DummyInfra:
        async def shutdown(self):
            pass
    
    infra = DummyInfra()

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


def _get_db_conn(vs_config):
    """Получение подключения к БД."""
    import psycopg2
    db_config = vs_config.db_providers.get("default_db")
    if not db_config:
        raise ValueError("DB provider 'default_db' not found in config")
    
    params = db_config.parameters
    conn = psycopg2.connect(
        host=params.get("host", "localhost"),
        port=params.get("port", 5432),
        database=params.get("database", "postgres"),
        user=params.get("user", "postgres"),
        password=params.get("password", ""),
    )
    conn.autocommit = True
    return conn


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
# Универсальная функция индексации
# ===========================================================================

async def index_source(source: str, embedding, faiss_provider, vs_config, db_conn) -> int:
    """Динамическая индексация источника на основе SOURCE_CONFIG."""
    from core.config.vector_config import SOURCE_CONFIG
    from core.models.types.vector_types import RowMetadata
    
    if source not in SOURCE_CONFIG:
        raise ValueError(f"Неизвестный источник: {source}. Доступные: {list(SOURCE_CONFIG.keys())}")
    
    cfg = SOURCE_CONFIG[source]
    print(f"\n{'='*60}\n📦 ИНДЕКСАЦИЯ: {source.upper()}\n{'='*60}")
    
    # Формируем SQL динамически
    join = cfg.get("join_clause", "")
    where = cfg.get("where_clause", "")
    order = cfg.get("order_by", "")
    table_ref = f"{cfg['schema']}.{cfg['table']}"
    
    sql = f"SELECT {cfg['select_cols']} FROM {table_ref} {join} {where} {order}"
    
    cursor = db_conn.cursor()
    cursor.execute(sql)
    rows = cursor.fetchall()
    col_names = [desc[0] for desc in cursor.description] if cursor.description else cfg["metadata_fields"]
    cursor.close()
    
    print(f"🔍 Найдено записей: {len(rows)}")
    
    vectors, metadata_list = [], []
    for row in rows:
        row_dict = dict(zip(col_names, row))
        
        # Формируем поисковый текст
        search_text = " ".join(str(row_dict.get(f, "")) for f in cfg["text_fields"] if row_dict.get(f))
        
        vector = await embedding.generate_single(search_text)
        
        meta = RowMetadata(
            source=source,
            table=f"{cfg['schema']}.{cfg['table']}",
            primary_key=cfg["pk_column"],
            pk_value=row_dict[cfg["pk_column"]],
            row=row_dict,
            chunk_index=0,
            total_chunks=1,
            search_text=search_text,
            content=search_text,
        )
        
        vectors.append(vector)
        metadata_list.append(meta.model_dump())
        
        pk_val = row_dict[cfg["pk_column"]]
        preview = str(row_dict.get(cfg["text_fields"][0], ""))[:60]
        print(f"   ✅ [{pk_val}] {preview}")
    
    if vectors:
        await faiss_provider.add(vectors, metadata_list)
        await save_index(faiss_provider, vs_config, source)
    else:
        print("⚠️ Нет данных для индексации")
    return 0


# ===========================================================================
# CLI
# ===========================================================================

def build_parser():
    import argparse
    from core.config.vector_config import SOURCE_CONFIG

    parser = argparse.ArgumentParser(
        description="Универсальный индексатор для векторного поиска",
    )
    subparsers = parser.add_subparsers(dest="command", help="Команды индексации")

    # init — создание пустых индексов
    subparsers.add_parser("init", help="Создать пустые индексы для всех источников")

    # all — индексация всех источников
    subparsers.add_parser("all", help="Индексация всех источников")

    # Динамическое создание подкоманд для каждого источника из конфига
    for source in SOURCE_CONFIG.keys():
        subparsers.add_parser(source, help=f"Индексация {source}")

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
    infra, embedding, faiss_provider, vs_config = await _init_infrastructure(profile="dev")
    conn = _get_db_conn(vs_config)

    try:
        if args.command == "all":
            from core.config.vector_config import SOURCE_CONFIG
            for src in SOURCE_CONFIG.keys():
                await index_source(src, embedding, faiss_provider, vs_config, conn)
        elif args.command in SOURCE_CONFIG:
            return await index_source(args.command, embedding, faiss_provider, vs_config, conn)
        else:
            parser.print_help()
            return 1
    finally:
        conn.close()
        await infra.shutdown()


def main():
    sys.exit(asyncio.run(async_main()))


if __name__ == "__main__":
    main()
