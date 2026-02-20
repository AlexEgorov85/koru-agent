#!/usr/bin/env python3
"""
Скрипт первичной индексации книг.

Запуск:
    python scripts/vector/initial_indexing.py

Требования:
    - FAISS провайдер инициализирован
    - SQL база с книгами доступна
    - Embedding модель загружена
"""

import asyncio
import sys
from pathlib import Path

# Добавим путь к корню проекта
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


async def main():
    """Первичная индексация всех книг."""
    from core.config.models import SystemConfig
    from core.infrastructure.context.infrastructure_context import InfrastructureContext
    from core.application.services.document_indexing_service import DocumentIndexingService
    from pathlib import Path
    
    print("="*60)
    print("ИНИЦИАЛИЗАЦИЯ ВЕКТОРНОЙ БД")
    print("="*60)
    
    try:
        # 1. Инициализация контекстов
        print("\n1️⃣ Инициализация контекстов...")
        config = SystemConfig(data_dir='data')
        infra = InfrastructureContext(config)
        await infra.initialize()
        print("✅ Контексты инициализированы")
        
        # 2. Создание сервиса индексации
        print("\n2️⃣ Создание сервиса индексации...")
        service = DocumentIndexingService(
            sql_provider=infra.get_sql_provider('books_db'),
            faiss_provider=infra.get_faiss_provider('books'),
            embedding_provider=infra.get_embedding_provider(),
            chunking_strategy=infra.get_chunking_strategy()
        )
        print("✅ Сервис создан")
        
        # 3. Индексация всех книг
        print("\n3️⃣ Индексация книг...")
        results = await service.index_all_books()
        
        # 4. Отчёт
        print("\n" + "="*60)
        print("РЕЗУЛЬТАТЫ ИНДЕКСАЦИИ")
        print("="*60)
        
        success = sum(1 for r in results if 'error' not in r)
        failed = len(results) - success
        
        print(f"\n✅ Успешно: {success}")
        print(f"❌ Ошибок: {failed}")
        
        if failed > 0:
            print("\nОшибки:")
            for r in results:
                if 'error' in r:
                    print(f"  - Книга {r.get('book_id', '?')}: {r['error']}")
        
        # 5. Сохранение индексов
        print("\n💾 Сохранение индексов...")
        for source, provider in infra._faiss_providers.items():
            index_path = Path(config.vector_search.storage.base_path) / f"{source}_index.faiss"
            index_path.parent.mkdir(parents=True, exist_ok=True)
            await provider.save(str(index_path))
            print(f"  ✅ {source}: {index_path}")
        
        # 6. Статистика
        print("\n" + "="*60)
        print("СТАТИСТИКА")
        print("="*60)
        
        for source, provider in infra._faiss_providers.items():
            count = await provider.count()
            print(f"  {source}: {count} векторов")
        
        # 7. Завершение
        await infra.shutdown()
        
        print("\n" + "="*60)
        print("✅ ИНДЕКСАЦИЯ ЗАВЕРШЕНА!")
        print("="*60)
        
        return 0
    
    except Exception as e:
        print(f"\n❌ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
