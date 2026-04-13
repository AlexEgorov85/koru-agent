# ✂️ Chunking: Разбиение на чанки

**Версия:** 3.0.0
**Дата:** 2026-04-12
**Статус:** ✅ Утверждено

---

## 📋 Обзор

Chunking — рекурсивное разбиение текста на чанки с учётом естественных границ
(заголовки, абзацы, предложения) и опциональным перекрытием между соседними чанками.

**Текущая реализация:**
- `TextChunkingStrategy` — единственная стратегия (рекурсивный split по разделителям)
- `ChunkingFactory` — фабрика для создания стратегий
- `ChunkingService` — единая точка входа

**Архитектура позволяет** легко добавить новые стратегии (`SemanticChunkingStrategy`,
`HybridChunkingStrategy` и т.д.) без изменения API.

---

## 🏗️ Архитектура

```
┌────────────────────────────────────────────────────────────────┐
│                      ChunkingService                           │
│                   (единая точка входа)                         │
│                                                                │
│  from_config(config) → ChunkingService                         │
│  from_dict(dict)     → ChunkingService                         │
│  split(text)         → List[VectorChunk]                       │
└──────────────────────────┬─────────────────────────────────────┘
                           │ делегирует
                           ▼
┌────────────────────────────────────────────────────────────────┐
│                      ChunkingFactory                           │
│                   (создание стратегий)                         │
│                                                                │
│  create("text", config) → TextChunkingStrategy                 │
│  register(name, cls)    → расширяет реестр                     │
└──────────────────────────┬─────────────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────────────┐
│                  TextChunkingStrategy                          │
│              (рекурсивный split по разделителям)               │
│                                                                │
│  1. Заголовки (\n## , \n### )                                  │
│  2. Абзацы (\n\n)                                              │
│  3. Строки (\n)                                                │
│  4. Предложения (. ! ?)                                        │
│  5. Точка с запятой (;)                                        │
│  6. Слова (пробелы)                                            │
│  7. Fallback: жёсткий split по chunk_size                      │
│  8. Overlap: хвост предыдущего → начало следующего             │
└────────────────────────────────────────────────────────────────┘
```

---

## 🎯 Алгоритм: рекурсивный split

### Как работает

```
Вход: "## Глава 1\n\nПервый абзац. Второй абзац. " + 2000 символов...

Уровень 0: separator = "\n## " (заголовки)
   → ["## Глава 1\n\nПервый абзац...", "## Глава 2\n\n..."]

Уровень 1: separator = "\n\n" (абзацы)
   → ["## Глава 1\n\n", "Первый абзац. Второй абзац.", "Третий..."]

Уровень 4: separator = ". " (предложения)
   → ["Первый абзац.", "Второй абзац."]

Уровень 6: separator = " " (слова) — fallback
   → ["очень", "длинное", "предложение..."]

Жёсткий split (если разделители кончились):
   → режем по chunk_size, стараясь не ломать слова
```

### Ключевое свойство

Алгоритм **НЕ режет** предложения/слова посередине, пока есть разделитель
выше по приоритету. Жёсткий split — только крайний fallback.

---

## 🔧 Параметры

| Параметр | По умолчанию | Описание | Рекомендации |
|----------|-------------|----------|-------------|
| `chunk_size` | 500 | Макс. размер чанка (символы) | 500 — книги, 200 — статьи |
| `chunk_overlap` | 50 | Перекрытие между чанками | 10% от chunk_size |
| `min_chunk_size` | 100 | Мин. размер (меньше — отбрасывается) | 100–150 |
| `separators` | (см. ниже) | Разделители по приоритету | Обычно не менять |

### Разделители по умолчанию

```python
DEFAULT_SEPARATORS = [
    "\n## ",      # Заголовки H2
    "\n### ",     # Заголовки H3
    "\n#### ",    # Заголовки H4
    "\n\n",       # Абзацы
    "\n",         # Строки
    ". ",         # Предложения (точка)
    "! ",         # Восклицания
    "? ",         # Вопросы
    "; ",         # Точка с запятой
    "。 ",        # Японские/китайские предложения
    " ",          # Слова
    "—",          # Тире
    "-",          # Дефис
]
```

---

## 🔄 Перекрытие (Overlap)

### Зачем нужно

```
БЕЗ ПЕРЕКРЫТИЯ:
  Chunk 0: "...он сказал что пойдёт..."
  Chunk 1: "...завтра утром в магазин..."
  Проблема: потерян контекст!

С ПЕРЕКРЫТИЕМ (50 символов):
  Chunk 0: "...он сказал что пойдёт..."
  Chunk 1: "...пойдёт завтра утром в магазин..."
            ↑ overlap — хвост Chunk 0
  Преимущество: поиск найдёт оба чанка
```

### Как работает

```python
# Без overlap
pieces = ["Первый.", "Второй."]
# → ["Первый.", "Второй."]

# С overlap=7
pieces = ["Первый.", "Второй."]
# → ["Первый.", "рвый. Второй."]
#     ↑ хвост предыдущего
```

### Метаданные чанка

Каждый `VectorChunk` содержит:

```python
{
    "chunk_size": 485,           # Длина чанка в символах
    "has_overlap": True,         # Есть ли overlap (False для первого)
    "overlap_chars": 50,         # Размер overlap в символах
}
```

---

## ⚙️ Использование

### Через ChunkingService (рекомендуется)

```python
from core.infrastructure.providers.vector.chunking_service import ChunkingService
from core.config.vector_config import ChunkingConfig

# Из конфигурации
config = ChunkingConfig(
    strategy="text",
    chunk_size=500,
    chunk_overlap=50,
    min_chunk_size=100,
)
service = ChunkingService.from_config(config)

# Разбиение
chunks = await service.split(
    content=chapter_text,
    document_id="book_1",
    metadata={"title": "Евгений Онегин"},
)

for chunk in chunks:
    print(f"Chunk {chunk.index}: {len(chunk.content)} символов")
```

### Через ChunkingFactory напрямую

```python
from core.infrastructure.providers.vector.chunking_factory import ChunkingFactory

strategy = ChunkingFactory.create(
    strategy_type="text",
    chunk_size=300,
    chunk_overlap=30,
)
chunks = await strategy.split(text, document_id="doc_1")
```

### В indexer.py

Indexer автоматически использует `ChunkingService`:

```python
# scripts/vector/indexer.py
from core.infrastructure.providers.vector.chunking_service import ChunkingService

chunking = ChunkingService.from_config(vs_config.chunking)
chunks = await chunking.split(
    content=chapter_text,
    document_id=f"book_{book_id}",
    metadata={"book_title": title, "chapter_number": chapter_num},
)
```

---

## 🏭 Добавление новой стратегии

ChunkingFactory поддерживает регистрацию:

```python
from core.infrastructure.providers.vector.chunking_factory import ChunkingFactory
from core.infrastructure.providers.vector.chunking_strategy import IChunkingStrategy

class SemanticChunkingStrategy(IChunkingStrategy):
    """Разбиение по смыслу (через embedding similarity)."""

    async def split(self, content, document_id, metadata=None):
        # ... реализация ...
        pass

    def get_config(self) -> dict:
        return {"type": "semantic"}

# Регистрация
ChunkingFactory.register("semantic", SemanticChunkingStrategy)

# Использование
strategy = ChunkingFactory.create(strategy_type="semantic", config=...)
```

---

## 📊 Примеры

### Пример 1: Маленький текст (< chunk_size)

**Вход:**
```
Глава 1

Мой дядя самых честных правил...
(150 символов)
```

**Выход:** 1 чанк (текст целиком, >= min_chunk_size)

### Пример 2: Текст с абзацами

**Вход:**
```
## Глава 1

Первый абзац. Короткий.

Второй абзац. Тоже короткий.
```

**chunk_size=100, chunk_overlap=10**

**Выход:**
```
Chunk 0: "## Глава 1\n\nПервый абзац. Короткий.\n\n"
Chunk 1: "Короткий.\n\nВторой абзац. Тоже короткий."
         ↑ overlap (хвост Chunk 0)
```

### Пример 3: Большой текст (fallback до слов)

**Вход:** 2000 символов без единого `\n`

**Выход:** Чанки разбиваются по предложениям (`. `), а если
предложение длинное — по словам (` `), и только если слово
длиннее chunk_size — жёсткий split по символам.

---

## 🧪 Тесты

```bash
# Запустить все тесты chunking
python -m pytest tests/unit/infrastructure/vector/test_chunking_strategy.py -v

# Конкретный тест
python -m pytest tests/unit/infrastructure/vector/test_chunking_strategy.py::TestTextChunkingStrategy::test_overlap_added -v
```

**Покрытие (28 тестов):**
- `TestTextChunkingStrategy` — 18 тестов (пустой текст, overlap, разделители, валидация, hard split)
- `TestChunkingFactory` — 6 тестов (создание, config, kwargs, регистрация)
- `TestChunkingService` — 4 тесты (from_config, from_dict, split, get_config)

---

## 📁 Файлы

| Файл | Назначение |
|------|-----------|
| `core/infrastructure/providers/vector/chunking_strategy.py` | `IChunkingStrategy` — интерфейс |
| `core/infrastructure/providers/vector/text_chunking_strategy.py` | `TextChunkingStrategy` — реализация |
| `core/infrastructure/providers/vector/chunking_factory.py` | `ChunkingFactory` — фабрика |
| `core/infrastructure/providers/vector/chunking_service.py` | `ChunkingService` — entry point |
| `core/config/vector_config.py` | `ChunkingConfig` — конфигурация |
| `scripts/vector/indexer.py` | Использование ChunkingService |
| `tests/unit/infrastructure/vector/test_chunking_strategy.py` | Тесты |

---

*Обновлено: 2026-04-12*
*Версия: 3.0.0 (рекурсивный split + ChunkingFactory + ChunkingService)*
*Статус: ✅ Утверждено*
