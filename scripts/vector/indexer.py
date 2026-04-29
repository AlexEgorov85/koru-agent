#!/usr/bin/env python3
"""
Универсальный индексатор векторного поиска.

АРХИТЕКТУРА:
- Работает ТОЛЬКО через InfrastructureContext
- Использует профиль prod
- Все провайдеры (Embedding, FAISS, Chunking, DB) берутся из инфраструктуры
- Никаких прямых psycopg2.connect(), FAISSProvider() или ручных инициализаций
"""
import asyncio
import sys
import logging
from pathlib import Path
from typing import List, Optional

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-7s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Добавляем корень проекта в sys.path
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from core.config import get_config
from core.config.vector_config import SOURCE_CONFIG
from core.models.types.vector_types import RowMetadata
from core.infrastructure_context.infrastructure_context import InfrastructureContext

# Маппинг скиллов -> векторные источники (CLI-удобство, данные из конфига)
SKILL_SOURCES = {
    "check_result": ["audits", "violations"],
    "book_library": ["books", "authors"],
}


async def _create_empty_indexes(infra: InfrastructureContext, vs_config) -> int:
    """Создание пустых FAISS индексов через инфраструктуру."""
    logger.info("=" * 60)
    logger.info("СОЗДАНИЕ ПУСТЫХ ИНДЕКСОВ")
    logger.info("=" * 60)

    storage_path = Path(vs_config.storage.base_path)
    storage_path.mkdir(parents=True, exist_ok=True)

    for source, index_file in vs_config.indexes.items():
        faiss = infra.get_faiss_provider(source)
        if not faiss:
            logger.warning(f"  ⚠️ FAISS для '{source}' не зарегистрирован в инфраструктуре")
            continue

        index_path = storage_path / index_file
        await faiss.save(str(index_path))
        logger.info(f"  ✅ {source}: {index_path} (векторов: {await faiss.count()})")

    logger.info("[OK] ПУСТЫЕ ИНДЕКСЫ СОЗДАНЫ!")
    return 0


async def _index_source(
    source: str,
    embedding,
    faiss,
    chunking,
    db_provider,
    vs_config
) -> int:
    """Индексация одного источника через инфраструктурные провайдеры."""
    if source not in SOURCE_CONFIG:
        raise ValueError(f"Источник '{source}' отсутствует в SOURCE_CONFIG")

    cfg = SOURCE_CONFIG[source]
    logger.info(f"\n{'='*60}\n📦 ИНДЕКСАЦИЯ: {source.upper()}\n{'='*60}")

    # 1. Формирование SQL из конфига
    join = cfg.get("join_clause", "")
    where = cfg.get("where_clause", "")
    order = cfg.get("order_by", "")
    table_ref = f"{cfg['schema']}.{cfg['table']}"
    sql = f"SELECT {cfg['select_cols']} FROM {table_ref} {join} {where} {order}"

    # 2. Выполнение через DB Provider инфраструктуры
    result = await db_provider.execute_query(query=sql)
    rows = result.rows if hasattr(result, 'rows') else []
    col_names = result.columns if hasattr(result, 'columns') else cfg.get("metadata_fields", [])

    total_rows = len(rows)
    logger.info(f"🔍 Найдено записей: {total_rows}")
    logger.info(f"📐 Chunking: size={vs_config.chunking.chunk_size}")

    if total_rows == 0:
        logger.warning("⚠️ Нет данных. Пропускаю.")
        return 0

    vectors, metadata_list = [], []
    processed, skipped, total_chunks_all = 0, 0, 0
    instruction = cfg.get("instruction")

    # 3. Обработка строк
    for idx, row in enumerate(rows):
        try:
            row_dict = dict(zip(col_names, row))
            search_text = "  ".join(
                str(row_dict.get(f, "")).strip() 
                for f in cfg["text_fields"] 
                if row_dict.get(f)
            )
            if not search_text:
                skipped += 1
                continue

            doc_id = f"{source}_{row_dict[cfg['pk_column']]}"
            chunks = await chunking.split(search_text, document_id=doc_id)
            if not chunks:
                chunks = [type('Chunk', (), {'content': search_text, 'index': 0})()]

            total_chunks = len(chunks)
            for chunk in chunks:
                # 4. Генерация вектора через инфраструктурный Embedding провайдер
                vector = await embedding.generate_single(chunk.content, instruction=instruction)
                
                meta = RowMetadata(
                    source=source, table=table_ref, primary_key=cfg["pk_column"],
                    pk_value=row_dict[cfg["pk_column"]], row=row_dict,
                    chunk_index=chunk.index, total_chunks=total_chunks,
                    search_text=chunk.content, content=chunk.content,
                )
                vectors.append(vector)
                metadata_list.append(meta.model_dump())
                processed += 1

            total_chunks_all += total_chunks

            if (idx + 1) % 100 == 0 or (idx + 1) == total_rows:
                logger.info(f"   📝 Обработано: {idx + 1}/{total_rows} (векторов: {processed}, чанков: {total_chunks_all})")
        except Exception as e:
            logger.error(f"   ❌ Ошибка строки {idx}: {e}")
            skipped += 1
            continue

    # 5. Сохранение через FAISS провайдер инфраструктуры
    if vectors:
        await faiss.add(vectors, metadata_list)
        storage_path = Path(vs_config.storage.base_path)
        storage_path.mkdir(parents=True, exist_ok=True)
        index_path = storage_path / vs_config.indexes.get(source, f"{source}_index.faiss")
        await faiss.save(str(index_path))
        logger.info(f"✅ Сохранено: {index_path} | Векторов: {await faiss.count()}")
    else:
        logger.warning("⚠️ Векторы не созданы.")

    return processed


async def run_indexer(
    skill: Optional[str] = None, 
    sources: Optional[List[str]] = None, 
    create_empty: bool = False
) -> int:
    """Основная функция. Полностью управляется через InfrastructureContext (prod)."""
    # 1. Загрузка prod конфига
    config = get_config(profile="prod", data_dir="data")
    vs_config = config.vector_search
    if not vs_config or not vs_config.enabled:
        raise RuntimeError("VectorSearch отключён в prod конфигурации")

    # 2. Инициализация инфраструктуры (поднимает LLM, DB, Vector, Chunking)
    infra = InfrastructureContext(config)
    await infra.initialize()

    try:
        if create_empty:
            return await _create_empty_indexes(infra, vs_config)

        # 3. Получение провайдеров ТОЛЬКО из инфраструктуры
        embedding = infra.get_embedding_provider()
        chunking = infra.get_chunking_strategy()
        
        db_provider = infra.lifecycle_manager.get_resource("default_db")
        if not db_provider:
            raise RuntimeError("DB провайдер 'default_db' не найден в InfrastructureContext")

        # 4. Определение целей индексации
        targets = sources or list(SOURCE_CONFIG.keys())
        if skill:
            targets = SKILL_SOURCES.get(skill.lower(), targets)

        total_indexed = 0
        for src in targets:
            if src not in vs_config.indexes:
                logger.warning(f"⚠️ FAISS индекс для '{src}' не сконфигурирован, пропускаю.")
                continue
                
            faiss = infra.get_faiss_provider(src)
            if not faiss:
                logger.warning(f"⚠️ FAISS провайдер для '{src}' не инициализирован, пропускаю.")
                continue

            total_indexed += await _index_source(src, embedding, faiss, chunking, db_provider, vs_config)

        logger.info(f"\n🎉 Индексация завершена. Обработано записей: {total_indexed}")
        return 0

    finally:
        # 5. Гарантированное завершение работы всех ресурсов
        logger.info("🔌 Завершение работы InfrastructureContext...")
        await infra.shutdown()


# ===========================================================================
# CLI
# ===========================================================================
def build_parser():
    import argparse
    parser = argparse.ArgumentParser(description="Индексатор векторов (Infrastructure-only, prod)")
    parser.add_argument("--skill", type=str, help="Фильтр по скиллу")
    parser.add_argument("--sources", nargs="+", help="Явный список источников")
    parser.add_argument("--empty", action="store_true", help="Создать пустые индексы")
    parser.add_argument("--profile", type=str, default="prod", help="Профиль (по умолчанию prod)")
    return parser

async def async_main():
    args = build_parser().parse_args()
    return await run_indexer(skill=args.skill, sources=args.sources, create_empty=args.empty)

def main():
    sys.exit(asyncio.run(async_main()))

if __name__ == "__main__":
    main()