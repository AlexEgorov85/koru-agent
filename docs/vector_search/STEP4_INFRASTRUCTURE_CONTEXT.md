# 🔄 Шаг 4: Интеграция в InfrastructureContext

**Статус:** ⏳ Требует реализации

---

## 📋 Задача

Добавить инициализацию Vector Search провайдеров в `InfrastructureContext`.

---

## 📁 Файл для обновления

**Файл:** `core/infrastructure/context/infrastructure_context.py`

---

## 🔧 Код для добавления

### 1. Добавить атрибуты в `__init__`

```python
# core/infrastructure/context/infrastructure_context.py

class InfrastructureContext:
    def __init__(self, config: SystemConfig):
        # ... существующий код ...
        
        # Vector Search провайдеры
        self._faiss_providers: Dict[str, FAISSProvider] = {}
        self._embedding_provider: Optional[EmbeddingProvider] = None
        self._chunking_strategy: Optional[ChunkingStrategy] = None
```

---

### 2. Добавить метод инициализации

```python
# core/infrastructure/context/infrastructure_context.py

class InfrastructureContext:
    async def initialize(self):
        """Инициализация контекста."""
        
        # ... существующий код ...
        
        # Инициализация Vector Search
        if self.config.vector_search and self.config.vector_search.enabled:
            await self._init_vector_search()
    
    async def _init_vector_search(self):
        """Инициализация векторного поиска."""
        from core.infrastructure.providers.vector.faiss_provider import FAISSProvider
        from core.infrastructure.providers.embedding.sentence_transformers_provider import SentenceTransformersProvider
        from core.infrastructure.providers.vector.text_chunking_strategy import TextChunkingStrategy
        from pathlib import Path
        
        vs_config = self.config.vector_search
        
        # Инициализация FAISS провайдеров для каждого источника
        for source, index_file in vs_config.indexes.items():
            provider = FAISSProvider(
                dimension=vs_config.embedding.dimension,
                config=vs_config.faiss
            )
            await provider.initialize()
            
            # Загрузка индекса если существует
            index_path = Path(vs_config.storage.base_path) / index_file
            if index_path.exists():
                try:
                    await provider.load(str(index_path))
                    print(f"✅ Загружен индекс {source}: {index_path}")
                except Exception as e:
                    print(f"⚠️ Не удалось загрузить индекс {source}: {e}")
            
            self._faiss_providers[source] = provider
        
        # Инициализация Embedding провайдера
        self._embedding_provider = SentenceTransformersProvider(vs_config.embedding)
        await self._embedding_provider.initialize()
        print(f"✅ Инициализирован Embedding: {vs_config.embedding.model_name}")
        
        # Инициализация Chunking стратегии
        self._chunking_strategy = TextChunkingStrategy(
            chunk_size=vs_config.chunking.chunk_size,
            chunk_overlap=vs_config.chunking.chunk_overlap,
            min_chunk_size=vs_config.chunking.min_chunk_size
        )
        print(f"✅ Инициализирован Chunking: {vs_config.chunking.chunk_size} символов")
```

---

### 3. Добавить методы доступа

```python
# core/infrastructure/context/infrastructure_context.py

class InfrastructureContext:
    def get_faiss_provider(self, source: str) -> Optional[FAISSProvider]:
        """Получение FAISS провайдера по источнику."""
        return self._faiss_providers.get(source)
    
    def get_embedding_provider(self) -> Optional[EmbeddingProvider]:
        """Получение Embedding провайдера."""
        return self._embedding_provider
    
    def get_chunking_strategy(self) -> Optional[ChunkingStrategy]:
        """Получение Chunking стратегии."""
        return self._chunking_strategy
```

---

### 4. Добавить метод shutdown

```python
# core/infrastructure/context/infrastructure_context.py

class InfrastructureContext:
    async def shutdown(self):
        """Завершение работы контекста."""
        
        # ... существующий код ...
        
        # Завершение Vector Search провайдеров
        for source, provider in self._faiss_providers.items():
            # Сохранение индексов
            if self.config.vector_search:
                index_path = Path(self.config.vector_search.storage.base_path) / f"{source}_index.faiss"
                try:
                    await provider.save(str(index_path))
                    print(f"💾 Сохранён индекс {source}: {index_path}")
                except Exception as e:
                    print(f"⚠️ Не удалось сохранить индекс {source}: {e}")
            
            await provider.shutdown()
        
        if self._embedding_provider:
            await self._embedding_provider.shutdown()
```

---

## ⚠️ Важные замечания

1. **Импорты:** Убедитесь что все импорты добавлены в начало файла
2. **Типизация:** Добавьте типы в аннотации
3. **Обработка ошибок:** Добавьте try/except где нужно
4. **Логирование:** Используйте logger вместо print в продакшене

---

## ✅ Чек-лист

- [ ] Добавлены атрибуты в `__init__`
- [ ] Добавлен метод `_init_vector_search`
- [ ] Вызов из `initialize()`
- [ ] Добавлены методы доступа (get_faiss_provider, get_embedding_provider, get_chunking_strategy)
- [ ] Обновлён метод `shutdown`
- [ ] Тесты проходят

---

## 🚀 Следующий шаг

После реализации запустить тесты:

```bash
python -m pytest tests/unit/infrastructure/ -v
```

---

*Инструкция создана: 2026-02-20*
