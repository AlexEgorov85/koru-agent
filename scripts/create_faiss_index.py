"""
Скрипт для создания FAISS индексов из SQL данных.

ИСПОЛЬЗОВАНИЕ:
    python scripts/create_faiss_index.py --source authors --table authors --column last_name
    python scripts/create_faiss_index.py --source genres --table genres --column name
    python scripts/create_faiss_index.py --source books --table books --column title

АРГУМЕНТЫ:
    --source: Имя source для индекса (authors, genres, books)
    --table: Имя таблицы в БД
    --column: Имя колонки для векторизации
    --schema: Схема БД (по умолчанию Lib)
    --dimension: Размерность эмбеддинга (по умолчанию 384)
    --batch-size: Размер батча для обработки (по умолчанию 100)

ПРИМЕРЫ:
    # Создать индекс авторов
    python scripts/create_faiss_index.py --source authors --table authors --column last_name --schema Lib

    # Создать индекс жанров
    python scripts/create_faiss_index.py --source genres --table genres --column name --schema Lib

    # Создать индекс книг (по названию)
    python scripts/create_faiss_index.py --source books --table books --column title --schema Lib
"""

import argparse
import asyncio
import os
import sys
from typing import List, Dict, Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def create_faiss_index(
    source: str,
    table: str,
    column: str,
    schema: str = "Lib",
    dimension: int = 384,
    batch_size: int = 100
) -> None:
    """
    Создание FAISS индекса из SQL данных.

    ARGS:
        source: Имя source для индекса
        table: Имя таблицы в БД
        column: Имя колонки для векторизации
        schema: Схема БД
        dimension: Размерность эмбеддинга
        batch_size: Размер батча
    """
    print(f"Создание FAISS индекса: source={source}, table={schema}.{table}, column={column}")

    # Импорт внутри функции для избежания проблем с путями
    from core.infrastructure.providers.vector.faiss_provider import FAISSProvider
    from core.infrastructure.providers.embedding.sentence_transformers_provider import SentenceTransformersProvider
    from core.config.vector_config import FAISSConfig
    from core.models.data.execution import ExecutionStatus

    # Инициализация FAISS провайдера
    faiss_config = FAISSConfig(index_type="Flat")
    faiss_provider = FAISSProvider(dimension=dimension, config=faiss_config)
    await faiss_provider.initialize()
    print(f"FAISS провайдер инициализирован: dimension={dimension}")

    # Инициализация embedding провайдера
    embedding_provider = SentenceTransformersProvider()
    await embedding_provider.initialize()
    print("Embedding провайдер инициализирован")

    # Получение данных из БД
    print(f"Загрузка данных из {schema}.{table}...")
    
    # Здесь должен быть код для получения данных из БД
    # Для примера используем mock данные
    sample_data = await _fetch_data_from_db(schema, table, column)
    
    if not sample_data:
        print(f"Нет данных для индексации в таблице {schema}.{table}")
        return

    print(f"Загружено {len(sample_data)} записей")

    # Векторизация и добавление в индекс
    print("Векторизация данных...")
    
    for i in range(0, len(sample_data), batch_size):
        batch = sample_data[i:i + batch_size]
        
        # Получение эмбеддингов
        texts = [str(item[column]) for item in batch]
        vectors = await embedding_provider.get_embeddings_batch(texts)
        
        # Метаданные для каждого вектора
        metadata = [
            {column: str(item[column]), "id": item.get("id", i + j)}
            for j, item in enumerate(batch)
        ]
        
        # Добавление в индекс
        await faiss_provider.add(vectors, metadata)
        
        print(f"Обработано {min(i + batch_size, len(sample_data))}/{len(sample_data)} записей")

    # Сохранение индекса
    output_dir = os.path.join("data", "vectors", source)
    os.makedirs(output_dir, exist_ok=True)
    index_path = os.path.join(output_dir, "index.faiss")
    metadata_path = os.path.join(output_dir, "metadata.json")

    await faiss_provider.save(index_path)
    print(f"Индекс сохранён: {index_path}")
    print(f"Метаданные сохранены: {metadata_path}")
    print(f"Всего векторов в индексе: {faiss_provider.get_count()}")


async def _fetch_data_from_db(schema: str, table: str, column: str) -> List[Dict[str, Any]]:
    """
    Получение данных из БД.
    
    В РЕАЛЬНОЙ РЕАЛИЗАЦИИ здесь будет подключение к БД.
    Для примера возвращаем пустой список.
    """
    # Пример реализации:
    # executor = get_executor()
    # result = await executor.execute_action(
    #     action_name="sql_query.execute",
    #     parameters={
    #         "sql": f'SELECT id, "{column}" FROM "{schema}"."{table}"',
    #         "parameters": []
    #     },
    #     context=None
    # )
    # if result.status == ExecutionStatus.COMPLETED:
    #     return result.data.rows
    return []


def main():
    parser = argparse.ArgumentParser(
        description="Создание FAISS индексов из SQL данных для vector search"
    )
    parser.add_argument(
        "--source",
        required=True,
        help="Имя source для индекса (authors, genres, books)"
    )
    parser.add_argument(
        "--table",
        required=True,
        help="Имя таблицы в БД"
    )
    parser.add_argument(
        "--column",
        required=True,
        help="Имя колонки для векторизации"
    )
    parser.add_argument(
        "--schema",
        default="Lib",
        help="Схема БД (по умолчанию Lib)"
    )
    parser.add_argument(
        "--dimension",
        type=int,
        default=384,
        help="Размерность эмбеддинга (по умолчанию 384)"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Размер батча для обработки (по умолчанию 100)"
    )

    args = parser.parse_args()

    asyncio.run(create_faiss_index(
        source=args.source,
        table=args.table,
        column=args.column,
        schema=args.schema,
        dimension=args.dimension,
        batch_size=args.batch_size
    ))


if __name__ == "__main__":
    main()