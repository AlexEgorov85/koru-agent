# Документация: Настройка FAISS индексов

> **Назначение:** Руководство по выбору и настройке типа FAISS индекса в `core/config/vector_config.py`.

---

## 1. Типы поддерживаемых индексов

### 1.1. `Flat` (IndexFlatIP) — РЕКОМЕНДУЕТСЯ ДЛЯ СТАРТА

```
Тип: IndexFlatIP (Inner Product)
Recall@10: 100% (идеально)
Скорость поиска (50k): ~5-15 мс на CPU
Построение: Мгновенно
Сложность: Нулевая
```

**Когда использоват:**
- ✅ Количество векторов < 100k
- ✅ Важна гарантия, что лучший результат не будет упущен
- ✅ Простота важнее максимальной скорости

**Конфигурация:**
```python
faiss: FAISSConfig = Field(default_factory=lambda: FAISSConfig(
    index_type="Flat",
    metric="IP",  # Inner Product = косинус при нормализации
))
```

---

### 1.2. `IVF` (IndexIVFFlat) — для больших данных

```
Тип: IndexIVFFlat (Inverted File)
Recall@10: ~95-99% (зависит от nlist/nprobe)
Скорость поиска (50k): ~2-5 мс на CPU
Построение: Требует обучения (train)
Сложность: Средняя (нужно подбирать nlist)
```

**Когда использоват:**
- ✅ Количество векторов > 100k
- ✅ Нужен баланс между скоростью и точностью
- ⚠️ Есть время на обучение индекса

**Конфигурация:**
```python
faiss: FAISSConfig = Field(default_factory=lambda: FAISSConfig(
    index_type="IVF",
    metric="IP",
    nlist=100,    # Количество кластеров (обычно sqrt(N) или 4*sqrt(N))
    nprobe=10,   # Сколько кластеров просматривать при поиске
))
```

**Правило для `nlist`:**
| Кол-во векторов | Рекомендованный `nlist` |
|------------------|---------------------------|
| 10k - 100k | 100 - 400 |
| 100k - 1M | 400 - 2000 |
| 1M+ | 2000+ |

---

### 1.3. `HNSW` (IndexHNSWFlat) — максимальная скорость

```
Тип: IndexHNSWFlat (Hierarchical Navigable Small World)
Recall@10: ~98-99.5% (зависит от efSearch)
Скорость поиска (50k): ~1-3 мс на CPU
Построение: Медленнее Flat, требует больше памяти
Сложность: Выше (нужно настраивать efConstruction/efSearch)
```

**Когда использоват:**
- ✅ Количество векторов > 500k
- ✅ Скорость критична (реал-тайм поиск)
- ✅ Есть достаточно RAM (HNSW потребляет ~1.5-2x больше памяти)

**Конфигурация:**
```python
faiss: FAISSConfig = Field(default_factory=lambda: FAISSConfig(
    index_type="HNSW",
    metric="IP",
    hnsw_ef_construction=40,  # Качество построения (больше = точнее, медленнее)
    hnsw_ef_search=16,         # Качество поиска (больше = точнее, медленнее)
))
```

**Параметры HNSW:**
| Параметр | Значение | Влияние |
|----------|----------|-----------|
| `hnsw_ef_construction` | 10-100 | Качество индекса при построении |
| `hnsw_ef_search` | 10-50 | Качество поиска (должно быть >= top_k) |

---

## 2. Обязательная нормализация

**ВАЖНО:** Для всех типов индексов с `metric="IP"` (Inner Product) нужно **ОБЯЗАТЕЛЬНО** нормализовать векторы через `faiss.normalize_L2()`.

Это делается автоматически в `FAISSProvider`:
```python
# При добавлении
vectors_array = np.ascontiguousarray(np.array(vectors, dtype=np.float32))
faiss.normalize_L2(vectors_array)  # ← ОБЯЗАТЕЛЬНО
self.index.add(vectors_array)

# При поиске
query_array = np.ascontiguousarray(np.array([query_vector], dtype=np.float32))
faiss.normalize_L2(query_array)  # ← ОБЯЗАТЕЛЬНО
scores, indices = self.index.search(query_array, top_k)
```

**Почему это важно:**
- `IP` (Inner Product) без нормализации = скалярное произведение (не косинус)
- С нормализацией `IP(vector1, vector2) = cos(θ)` — чистое косинусное сходство
- Без нормализации длинные векторы будут иметь незаслуженно высокий score

---

## 3. Выбор типа индекса — чек-лист

```
Вопросы:
1. У меня < 100k векторов?
   → ДА: Используйте Flat
   → НЕТ: Переходите к вопросу 2

2. Мне нужна максимальная скорость?
   → ДА: Используйте HNSW (не забудьте RAM)
   → НЕТ: Используйте IVF

3. Я готов к обучению индекса?
   → ДА: IVF
   → НЕТ: Оставайтесь на Flat
```

---

## 4. Примеры конфигурации

### 4.1. Для разработки и тестов (рекомендуется)

```python
# core/config/vector_config.py
class VectorSearchConfig(BaseModel):
    ...
    faiss: FAISSConfig = Field(default_factory=lambda: FAISSConfig(
        index_type="Flat",  # 100% точность, просто
        metric="IP",
    ))
```

### 4.2. Для продакшена (10k-100k векторов)

```python
faiss: FAISSConfig = Field(default_factory=lambda: FAISSConfig(
    index_type="Flat",  # Всё ещё актуально
    metric="IP",
))
# Или, если нужно быстрее:
faiss: FAISSConfig = Field(default_factory=lambda: FAISSConfig(
    index_type="IVF",
    metric="IP",
    nlist=100,
    nprobe=10,
))
```

### 4.3. Для больших данных (100k+ векторов)

```python
faiss: FAISSConfig = Field(default_factory=lambda: FAISSConfig(
    index_type="IVF",
    metric="IP",
    nlist=400,       # Для 100k векторов
    nprobe=20,       # Больше = точнее, но медленнее
))
# Или для максимальной скорости:
faiss: FAISSConfig = Field(default_factory=lambda: FAISSConfig(
    index_type="HNSW",
    metric="IP",
    hnsw_ef_construction=40,
    hnsw_ef_search=16,
))
```

---

## 5. Метрики производительности (ориентировочно)

Замеры на CPU (Intel i7), дименшн = 2048:

| Тип индекса | Кол-во векторов | Построение | Поиск (top_k=10) | RAM |
|--------------|-------------------|------------|-------------------|-----|
| Flat | 10k | < 0.1с | ~2 мс | ~80 МБ |
| Flat | 100k | < 0.5с | ~15 мс | ~800 МБ |
| IVF | 100k | ~2с | ~5 мс | ~800 МБ |
| HNSW | 100k | ~5с | ~2 мс | ~1.2 ГБ |

---

## 6. Переключение между типами индексов

⚠️ **ВНИМАНИЕ:** При смене `index_type` нужно **пересоздать индекс**!

```bash
# 1. Удалите старые индексы
rm -rf data/vector/*.faiss data/vector/*_metadata.json

# 2. Измените конфиг ( core/config/vector_config.py)
# 3. Переиндексируйте
python -m scripts.vector.indexer --all
```

---

## 7. Резюме

| Тип | Recall | Скорость | Память | Сложность | Когда использовать |
|-----|---------|----------|--------|-----------|-------------------|
| **Flat** | 100% | Средне | Низкая | Нулевая | **Старт, < 100k** |
| **IVF** | 95-99% | Быстро | Средне | Средняя | 100k - 1M |
| **HNSW** | 98-99.5% | Очень быстро | Высокая | Высокая | 1M+, реал-тайм |

**Золотое правило:** Начните с `Flat`. Если станет медленно — переходите на `IVF` или `HNSW`.
