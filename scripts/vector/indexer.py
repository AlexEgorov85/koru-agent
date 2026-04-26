#!/usr/bin/env python3
"""
Универсальный индексатор для векторного поиска.
Поддерживает индексацию по скиллам, батчинг, прогресс и интеграцию с AppConfig.

ИСПОЛЬЗОВАНИЕ:
  # Индексация источников для навыка check_result (audits, violations)
  python -m scripts.vector.indexer --skill check_result

  # Индексация конкретных источников
  python -m scripts.vector.indexer --sources books authors

  # Создание пустых индексов (для инициализации)
  python -m scripts.vector.indexer --empty

  # Индексация всех источников из конфига
  python -m scripts.vector.indexer
  
  # Устаревший CLI (совместимость)
  python -m scripts.vector.indexer init
  python -m scripts.vector.indexer all
  python -m scripts.vector.indexer audits
"""
import asyncio
import sys
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

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

# Маппинг скиллов -> требуемые векторные источники
SKILL_SOURCES = {
    "check_result": ["audits", "violations"],
    "book_library": ["books", "authors"],
    # Добавляйте новые скиллы по мере появления
}

async def _init_infrastructure(profile: str = "dev", data_dir: str = "data"):
    """Инициализация инфраструктуры (embedding + FAISS)."""
    from core.config.vector_config import EmbeddingConfig
    from core.infrastructure.providers.vector.faiss_provider import FAISSProvider

    config = get_config(profile=profile, data_dir=data_dir)
    vs_config = config.vector_search

    # Empty infra mock для совместимости с shutdown
    class DummyInfra:
        async def shutdown(self):
            pass
    
    infra = DummyInfra()

    # Выбор провайдера на основе модели или явного пути
    model_name = vs_config.embedding.model_name
    emb_cfg = vs_config.embedding
    local_path = emb_cfg.local_model_path

    if "qwen3" in model_name.lower() or local_path:
        from core.infrastructure.providers.embedding.qwen3_embedding_provider import Qwen3EmbeddingProvider
        embedding = Qwen3EmbeddingProvider(emb_cfg)
    elif "Giga-Embeddings" in model_name or "giga" in model_name.lower():
        from core.infrastructure.providers.embedding.giga_embeddings_provider import GigaEmbeddingsProvider
        embedding = GigaEmbeddingsProvider(emb_cfg)
    else:
        from core.infrastructure.providers.embedding.sentence_transformers_provider import SentenceTransformersProvider
        embedding_config = EmbeddingConfig(model_name=model_name, dimension=vs_config.embedding.dimension)
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
    logger.info("=" * 60)
    logger.info("СОЗДАНИЕ ПУСТЫХ ИНДЕКСОВ")
    logger.info("=" * 60)

    from core.infrastructure.providers.vector.faiss_provider import FAISSProvider

    storage_path = Path(vs_config.storage.base_path)
    storage_path.mkdir(parents=True, exist_ok=True)

    for source, index_file in vs_config.indexes.items():
        logger.info(f"\n  {source}:")

        provider = FAISSProvider(
            dimension=vs_config.embedding.dimension,
            config=vs_config.faiss,
        )
        await provider.initialize()

        index_path = storage_path / index_file
        await provider.save(str(index_path))

        count = await provider.count()
        logger.info(f"     Создан: {index_path}")
        logger.info(f"     Векторов: {count}")

    # Статистика
    logger.info("\n" + "=" * 60)
    logger.info("СТАТИСТИКА")
    logger.info("=" * 60)

    for source, index_file in vs_config.indexes.items():
        index_path = storage_path / index_file
        status = "[OK]" if index_path.exists() else "[FAIL]"
        logger.info(f"  {status} {source}: {index_file}")

    logger.info("\n" + "=" * 60)
    logger.info("[OK] ИНДЕКСЫ СОЗДАНЫ!")
    logger.info("=" * 60)
    return 0


async def save_index(provider, vs_config, source: str) -> Path:
    """Сохранение FAISS индекса в файл."""
    storage_path = Path(vs_config.storage.base_path)
    storage_path.mkdir(parents=True, exist_ok=True)

    index_file = vs_config.indexes.get(source, f"{source}_index.faiss")
    index_path = storage_path / index_file
    await provider.save(str(index_path))

    count = await provider.count()
    logger.info(f"\n[OK] Saved: {index_path}")
    logger.info(f"[OK] Total vectors: {count}")
    return index_path


# ===========================================================================
# Универсальная функция индексации
# ===========================================================================

async def index_source(source: str, embedding, faiss_provider, vs_config, db_conn) -> int:
    """Динамическая индексация источника на основе SOURCE_CONFIG с прогрессом и обработкой ошибок."""
    if source not in SOURCE_CONFIG:
        raise ValueError(f"Неизвестный источник: {source}. Доступные: {list(SOURCE_CONFIG.keys())}")
    
    cfg = SOURCE_CONFIG[source]
    logger.info(f"\n{'='*60}\n📦 ИНДЕКСАЦИЯ: {source.upper()}\n{'='*60}")
    
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
    
    total_rows = len(rows)
    logger.info(f"🔍 Найдено записей: {total_rows}")
    
    if total_rows == 0:
        logger.warning("⚠️ Нет данных для индексации. Пропускаю.")
        return 0
    
    vectors, metadata_list = [], []
    processed = 0
    skipped = 0
    
    for idx, row in enumerate(rows):
        try:
            row_dict = dict(zip(col_names, row))
            
            # Формируем поисковый текст только из непустых полей
            search_text = " ".join(str(row_dict.get(f, "")).strip() for f in cfg["text_fields"] if row_dict.get(f))
            
            if not search_text:
                skipped += 1
                continue
            
            vector = await embedding.generate_single(search_text)
            
            meta = RowMetadata(
                source=source,
                table=table_ref,
                primary_key=cfg["pk_column"],
                pk_value=row_dict[cfg["pk_column"]],
                row=row_dict,
                chunk_index=0,
                total_chunks=1,
                search_text=search_text,
                content=search_text,
            )
            
            # ✅ КРИТИЧЕСКИ ВАЖНО: model_dump() возвращает словарь с данными, а не список ключей
            meta_dict = meta.model_dump()
            
            # Отладочный вывод первой записи для проверки
            if len(vectors) == 0:
                logger.info(f"💡 Пример метаданных (первая запись):")
                sample_keys = list(meta_dict.keys())[:5]
                logger.info(f"   Ключи: {sample_keys}")
                # Проверяем, что значения не пустые
                first_val = meta_dict.get('row', {})
                if isinstance(first_val, dict) and first_val:
                    logger.info(f"   Пример данных в row: {list(first_val.values())[:3]}")
            
            vectors.append(vector)
            metadata_list.append(meta_dict)
            processed += 1
            
            # Прогресс каждые 100 строк
            if (idx + 1) % 100 == 0 or (idx + 1) == total_rows:
                logger.info(f"   📝 Обработано: {idx + 1}/{total_rows} (векторов: {processed}, пропущено: {skipped})")
                
        except Exception as e:
            logger.error(f"   ❌ Ошибка при обработке строки {idx}: {e}")
            skipped += 1
            continue
    
    if vectors:
        await faiss_provider.add(vectors, metadata_list)
        await save_index(faiss_provider, vs_config, source)
        logger.info(f"✅ Индексация завершена: {processed} векторов, пропущено: {skipped}")
    else:
        logger.warning("⚠️ Не удалось создать валидные векторы. Индекс не сохранён.")
    
    return processed


# ===========================================================================
# Основная функция запуска
# ===========================================================================

async def run_indexer(skill: Optional[str] = None, sources: Optional[List[str]] = None, create_empty: bool = False):
    """Основная функция запуска индексации."""
    config = get_config(profile="dev")
    vs_config = config.vector_search

    if not vs_config or not vs_config.enabled:
        logger.error("❌ VectorSearch отключён в конфигурации. Проверьте vector_search.enabled")
        return 1

    if create_empty:
        logger.info("🛠️ Режим создания пустых индексов. Данные из БД не загружаются.")
        return await create_empty_indexes(vs_config)

    embedding = None
    db_conn = None
    
    try:
        # Инициализация embedding провайдера
        model_name = vs_config.embedding.model_name
        emb_cfg = vs_config.embedding
        
        if "qwen3" in model_name.lower() or emb_cfg.local_model_path:
            from core.infrastructure.providers.embedding.qwen3_embedding_provider import Qwen3EmbeddingProvider
            if emb_cfg.device == "cuda":
                import torch
                if not torch.cuda.is_available():
                    logger.warning("⚠️ CUDA недоступна. Переключаю embedding на CPU.")
                    emb_cfg.device = "cpu"
            embedding = Qwen3EmbeddingProvider(emb_cfg)
        elif "giga" in model_name.lower():
            from core.infrastructure.providers.embedding.giga_embeddings_provider import GigaEmbeddingsProvider
            embedding = GigaEmbeddingsProvider(emb_cfg)
        else:
            from core.infrastructure.providers.embedding.sentence_transformers_provider import SentenceTransformersProvider
            embedding = SentenceTransformersProvider(emb_cfg)
        
        await embedding.initialize()
        logger.info(f"✅ Embedding провайдер инициализирован: {model_name}")

        # Подключение к БД
        db_conn = _get_db_conn(vs_config)
        logger.info(f"🔌 Подключение к БД установлено")

        # Определение целевых источников
        targets = sources or []
        
        if skill:
            skill = skill.lower()
            if skill in SKILL_SOURCES:
                targets = SKILL_SOURCES[skill]
                logger.info(f"🎯 Режим скилла '{skill}'. Источники: {targets}")
            else:
                logger.warning(f"⚠️ Скилл '{skill}' не найден в конфигурации. Использую все источники.")
                targets = list(SOURCE_CONFIG.keys())
        
        if not targets:
            targets = list(SOURCE_CONFIG.keys())
            logger.info(f"🌐 Индексирую все источники: {targets}")

        # Индексация каждого источника
        total_indexed = 0
        for src in targets:
            # Создаём новый FAISS провайдер для каждого источника
            from core.infrastructure.providers.vector.faiss_provider import FAISSProvider
            faiss_provider = FAISSProvider(dimension=vs_config.embedding.dimension, config=vs_config.faiss)
            await faiss_provider.initialize()
            
            count = await index_source(src, embedding, faiss_provider, vs_config, db_conn)
            total_indexed += count

        logger.info(f"\n{'='*60}")
        logger.info(f"🎉 Индексация завершена! Всего обработано: {total_indexed} записей.")
        logger.info(f"{'='*60}")
        return 0
        
    finally:
        if db_conn:
            db_conn.close()
            logger.info("🔌 Соединение с БД закрыто.")
        if embedding:
            await embedding.shutdown() if hasattr(embedding, 'shutdown') else None


# ===========================================================================
# CLI
# ===========================================================================

def build_parser():
    import argparse
    from core.config.vector_config import SOURCE_CONFIG

    parser = argparse.ArgumentParser(
        description="Универсальный индексатор для векторного поиска",
    )
    
    # Новый стиль аргументов
    parser.add_argument("--skill", type=str, help="Индексировать источники для конкретного скилла (напр. check_result)")
    parser.add_argument("--sources", nargs="+", help="Явный список источников для индексации")
    parser.add_argument("--empty", action="store_true", help="Создать только пустые индексы (без данных)")
    parser.add_argument("--profile", type=str, default="dev", help="Профиль конфигурации (dev/prod/sandbox)")
    
    # Старый стиль подкоманд (для совместимости)
    subparsers = parser.add_subparsers(dest="command", help="Команды индексации (устаревший стиль)")
    subparsers.add_parser("init", help="Создать пустые индексы для всех источников")
    subparsers.add_parser("all", help="Индексация всех источников")
    for source in SOURCE_CONFIG.keys():
        subparsers.add_parser(source, help=f"Индексация {source}")

    return parser


async def async_main():
    parser = build_parser()
    args = parser.parse_args()

    # Переопределяем профиль через env, если нужно
    import os
    os.environ.setdefault("APP_PROFILE", args.profile)

    # Новый стиль аргументов имеет приоритет
    if args.skill or args.sources or args.empty:
        return await run_indexer(skill=args.skill, sources=args.sources, create_empty=args.empty)
    
    # Старый стиль подкоманд (для совместимости)
    if not args.command:
        # Если нет ни новых ни старых аргументов - индексируем всё
        return await run_indexer(skill=None, sources=None, create_empty=False)

    if args.command == "init":
        config = get_config(profile="dev")
        vs_config = config.vector_search
        return await create_empty_indexes(vs_config)

    # Для всех остальных команд нужна инфраструктура
    infra, embedding, faiss_provider, vs_config = await _init_infrastructure(profile="dev")
    conn = _get_db_conn(vs_config)

    try:
        if args.command == "all":
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
