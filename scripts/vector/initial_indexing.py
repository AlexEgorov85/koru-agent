#!/usr/bin/env python3
"""
Скрипт первичной индексации книг и создания FAISS индексов.

Запуск:
    python scripts/vector/initial_indexing.py

Требования:
    - FAISS провайдер инициализирован
    - SQL база с книгами доступна (опционально)
    - Embedding модель загружена
"""

import asyncio
import sys
from pathlib import Path

# Добавим путь к корню проекта
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


async def main():
    """Первичная индексация всех книг и создание индексов."""
    from core.config import get_config
    from core.infrastructure.context.infrastructure_context import InfrastructureContext
    from core.infrastructure.providers.vector.faiss_provider import FAISSProvider
    from pathlib import Path

    print("="*60)
    print("ИНИЦИАЛИЗАЦИЯ ВЕКТОРНОЙ БД")
    print("="*60)

    try:
        # 1. Инициализация контекстов
        print("\n1. Инициализация контекстов...")
        config = get_config(profile='dev')
        infra = InfrastructureContext(config)
        await infra.initialize()
        print("OK Контексты инициализированы")

        # 2. Создание и сохранение пустых индексов для всех источников
        print("\n2. Создание FAISS индексов...")
        
        vs_config = config.vector_search
        storage_path = Path(vs_config.storage.base_path)
        storage_path.mkdir(parents=True, exist_ok=True)

        for source, index_file in vs_config.indexes.items():
            print(f"\n  {source}:")
            
            # Создаём FAISS провайдер
            provider = FAISSProvider(
                dimension=vs_config.embedding.dimension,
                config=vs_config.faiss
            )
            await provider.initialize()
            
            # Сохраняем пустой индекс
            index_path = storage_path / index_file
            await provider.save(str(index_path))
            
            count = await provider.count()
            print(f"     Создан: {index_path}")
            print(f"     Векторов: {count}")

        # 3. Статистика
        print("\n" + "="*60)
        print("СТАТИСТИКА")
        print("="*60)
        
        for source, index_file in vs_config.indexes.items():
            index_path = storage_path / index_file
            exists = "OK" if index_path.exists() else "X"
            print(f"  {exists} {source}: {index_file}")

        # 4. Завершение
        await infra.shutdown()

        print("\n" + "="*60)
        print("OK ИНДЕКСАЦИЯ ЗАВЕРШЕНА!")
        print("="*60)
        print("\nТеперь при запуске main.py Vector Search покажет:")
        print("  '4 загружено, 0 отсутствует, всего векторов: 0'")

        return 0

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
