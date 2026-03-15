"""
Тест векторной БД (FAISS + Embedding)
С загрузкой модели онлайн если локальная не найдена
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from core.config import get_config
from core.infrastructure.context.infrastructure_context import InfrastructureContext


async def test_vector_search():
    """Тест векторного поиска"""
    print("=" * 60)
    print("ТЕСТ ВЕКТОРНОЙ БД (FAISS + Embedding)")
    print("=" * 60)
    
    # 1. Инициализация инфраструктуры
    print("\n[1/5] Инициализация инфраструктуры...")
    config = get_config(profile='dev', data_dir='data')
    infra = InfrastructureContext(config)
    await infra.initialize()
    print("✅ Инфраструктура инициализирована")
    
    # 2. Проверка FAISS провайдеров
    print("\n[2/5] Проверка FAISS провайдеров...")
    print(f"   FAISS провайдеры: {list(infra._faiss_providers.keys())}")
    
    for name, provider in infra._faiss_providers.items():
        count = await provider.count()
        print(f"   - {name}: {count} векторов")
    
    # 3. Проверка Embedding провайдера
    print("\n[3/5] Проверка Embedding провайдера...")
    
    # НЕ используем get_embedding_provider() — он не инициализирован
    # Создаём свой provider напрямую
    print("   📥 Загрузка модели all-MiniLM-L6-v2 (онлайн)...")
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer('all-MiniLM-L6-v2')
    print("   ✅ Модель загружена успешно!")
    
    # Создаём простой embedding provider
    class SimpleEmbeddingProvider:
        def __init__(self, model):
            self.model = model
        async def generate(self, texts):
            import numpy as np
            embeddings = self.model.encode(texts, convert_to_numpy=True)
            # Гарантируем что это list а не numpy array
            if isinstance(embeddings, np.ndarray):
                embeddings = embeddings.tolist()
            return embeddings
    
    embedding = SimpleEmbeddingProvider(model)
    print(f"   ✅ Embedding провайдер создан: {type(embedding).__name__}")
    
    # Тест генерации вектора
    print("\n[4/5] Генерация тестового вектора...")
    import time
    start = time.time()
    vector = await embedding.generate(["Капитанская дочка Пушкин"])
    elapsed = time.time() - start
    print(f"   ✅ Вектор сгенерирован за {elapsed:.2f}s")
    print(f"   - Длина вектора: {len(vector[0]) if vector else 0}")
    print(f"   - Первые 5 значений: {vector[0][:5] if vector else 'N/A'}")
    
    # 4. Тест поиска в FAISS
    print("\n[5/5] Тест поиска в FAISS...")
    faiss = infra._faiss_providers.get('books')
    if not faiss:
        print("   ❌ FAISS провайдер 'books' не найден!")
        return
    
    count = await faiss.count()
    print(f"   ✅ FAISS индекс: {count} векторов")
    
    if count == 0:
        print("   ❌ FAISS индекс пуст!")
        return
    
    # Поиск
    start = time.time()
    print(f"   🔍 Поиск по запросу 'Капитанская дочка'...")
    print(f"   - Тип вектора: {type(vector[0])}")
    print(f"   - Длина вектора: {len(vector[0])}")
    print(f"   - Тип FAISS: {type(faiss)}")
    
    # Конвертируем в numpy array для правильного выбора метода
    import numpy as np
    query_array = np.array(vector[0], dtype=np.float32)
    print(f"   - Тип query_array: {type(query_array)}")
    
    # Вызываем search с numpy array
    results = await faiss.search(query_array.tolist(), top_k=5)
    elapsed = time.time() - start
    print(f"   ✅ Поиск выполнен за {elapsed:.2f}s")
    print(f"   - Найдено результатов: {len(results)}")
    
    for i, result in enumerate(results[:3], 1):
        print(f"\n   Результат #{i}:")
        print(f"   - Score: {result.get('score', 0):.4f}")
        print(f"   - Book ID: {result.get('metadata', {}).get('book_id', 'N/A')}")
        print(f"   - Chapter: {result.get('metadata', {}).get('chapter', 'N/A')}")
        content = result.get('metadata', {}).get('content', '')
        if len(content) > 100:
            print(f"   - Content: {content[:100]}...")
        else:
            print(f"   - Content: {content}")
    
    # 5. Завершение
    print("\n" + "=" * 60)
    print("ТЕСТ ЗАВЕРШЁН УСПЕШНО!")
    print("=" * 60)
    
    await infra.shutdown()


if __name__ == "__main__":
    asyncio.run(test_vector_search())
