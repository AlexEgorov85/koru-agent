# рџ“љ РРЅС‚РµРіСЂР°С†РёСЏ СЃ Р±Р°Р·РѕР№ РєРЅРёРі (SQL + Vector)

**Р’РµСЂСЃРёСЏ:** 1.0.0  
**Р”Р°С‚Р°:** 2026-02-19  
**РЎС‚Р°С‚СѓСЃ:** вњ… РЈС‚РІРµСЂР¶РґРµРЅРѕ

---

## рџ“‹ РћР±Р·РѕСЂ

Р­С‚РѕС‚ РґРѕРєСѓРјРµРЅС‚ РѕРїРёСЃС‹РІР°РµС‚ РёРЅС‚РµРіСЂР°С†РёСЋ СЃСѓС‰РµСЃС‚РІСѓСЋС‰РµР№ SQL Р±Р°Р·С‹ РґР°РЅРЅС‹С… СЃ Р°РІС‚РѕСЂР°РјРё, РєРЅРёРіР°РјРё Рё С‚РµРєСЃС‚Р°РјРё СЃ СЃРёСЃС‚РµРјРѕР№ РІРµРєС‚РѕСЂРЅРѕРіРѕ РїРѕРёСЃРєР°.

---

## рџЋЇ РђСЂС…РёС‚РµРєС‚СѓСЂРЅРѕРµ СЂРµС€РµРЅРёРµ

### ADR-011: Р“РёР±СЂРёРґРЅС‹Р№ РїРѕРёСЃРє (Vector + SQL)

| РџР°СЂР°РјРµС‚СЂ | Р РµС€РµРЅРёРµ |
|----------|---------|
| **РЎРµРјР°РЅС‚РёС‡РµСЃРєРёР№ РїРѕРёСЃРє** | Vector DB (FAISS) |
| **РџРѕР»РЅС‹Р№ С‚РµРєСЃС‚ РєРЅРёРіРё** | SQL DB (PostgreSQL) |
| **РЎРІСЏР·СЊ РјРµР¶РґСѓ Р‘Р”** | book_id, author_id РІ РјРµС‚Р°РґР°РЅРЅС‹С… |
| **РЎРёРЅС…СЂРѕРЅРёР·Р°С†РёСЏ** | Event-driven (РїСЂРё РґРѕР±Р°РІР»РµРЅРёРё РєРЅРёРіРё) |

**РћР±РѕСЃРЅРѕРІР°РЅРёРµ:**
1. вњ… Р’РµРєС‚РѕСЂРЅС‹Р№ РїРѕРёСЃРє РґР»СЏ СЃРµРјР°РЅС‚РёС‡РµСЃРєРѕРіРѕ РїРѕРёСЃРєР° РїРѕ С‚РµРєСЃС‚Р°Рј
2. вњ… SQL РґР»СЏ РїРѕР»СѓС‡РµРЅРёСЏ РїРѕР»РЅРѕРіРѕ С‚РµРєСЃС‚Р° РєРЅРёРіРё
3. вњ… РЎСЃС‹Р»РєРё С‡РµСЂРµР· book_id/author_id
4. вњ… РќРµ РґСѓР±Р»РёСЂСѓРµРј РїРѕР»РЅС‹Р№ С‚РµРєСЃС‚ РІ РІРµРєС‚РѕСЂРЅРѕР№ Р‘Р”

---

## рџ“Љ РЎС‚СЂСѓРєС‚СѓСЂР° РґР°РЅРЅС‹С…

### SQL Р‘Р°Р·Р° (СЃСѓС‰РµСЃС‚РІСѓСЋС‰Р°СЏ)

```sql
-- РђРІС‚РѕСЂС‹
CREATE TABLE authors (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    birth_date DATE,
    nationality TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- РљРЅРёРіРё
CREATE TABLE books (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    author_id INTEGER REFERENCES authors(id),
    year INTEGER,
    genre TEXT,
    language TEXT DEFAULT 'ru',
    publisher TEXT,
    isbn TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    indexed_at TIMESTAMP  -- РљРѕРіРґР° РґРѕР±Р°РІР»РµРЅР° РІ РІРµРєС‚РѕСЂРЅС‹Р№ РёРЅРґРµРєСЃ
);

-- РўРµРєСЃС‚С‹ РєРЅРёРі (РїРѕ РіР»Р°РІР°Рј)
CREATE TABLE book_texts (
    id INTEGER PRIMARY KEY,
    book_id INTEGER REFERENCES books(id),
    chapter INTEGER NOT NULL,
    title TEXT,  -- РќР°Р·РІР°РЅРёРµ РіР»Р°РІС‹
    content TEXT NOT NULL,
    word_count INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(book_id, chapter)
);

-- РРЅРґРµРєСЃС‹ РґР»СЏ РїСЂРѕРёР·РІРѕРґРёС‚РµР»СЊРЅРѕСЃС‚Рё
CREATE INDEX idx_books_author ON books(author_id);
CREATE INDEX idx_book_texts_book ON book_texts(book_id);
CREATE INDEX idx_books_year ON books(year);
CREATE INDEX idx_books_genre ON books(genre);
```

---

### Vector Р‘Р°Р·Р° (РЅРѕРІР°СЏ)

```
data/vector/
в”њв”Ђв”Ђ books_index.faiss          в†ђ РРЅРґРµРєСЃ С‡Р°РЅРєРѕРІ С‚РµРєСЃС‚РѕРІ РєРЅРёРі
в”њв”Ђв”Ђ books_metadata.json        в†ђ РњРµС‚Р°РґР°РЅРЅС‹Рµ С‡Р°РЅРєРѕРІ (СЃСЃС‹Р»РєРё РЅР° SQL)
в””в”Ђв”Ђ config.json
```

---

## рџ”— РЎС‚СЂСѓРєС‚СѓСЂР° РјРµС‚Р°РґР°РЅРЅС‹С… С‡Р°РЅРєР°

### РџРѕР»РЅР°СЏ СЃС…РµРјР°

```json
{
  "chunk_id": "book_chunk_0001_0000",
  "document_id": "book_0001",
  "source": "books",
  "content": "С‚РµРєСЃС‚ С‡Р°РЅРєР° (500 СЃРёРјРІРѕР»РѕРІ)...",
  "vector_id": 0,
  
  "book_metadata": {
    "book_id": 1,
    "book_title": "Р’РѕР№РЅР° Рё РјРёСЂ",
    "author_id": 1,
    "author_name": "Р›РµРІ РўРѕР»СЃС‚РѕР№",
    "year": 1869,
    "genre": "roman",
    "language": "ru",
    "publisher": "РђР·Р±СѓРєР°",
    "isbn": "978-5-389-12345-6"
  },
  
  "chunk_metadata": {
    "chapter": 1,
    "chapter_title": "Р“Р»Р°РІР° 1",
    "chunk_index": 0,
    "total_chunks": 150,
    "chunk_size": 500,
    "chunk_overlap": 50,
    "word_count": 85
  },
  
  "sql_reference": {
    "enabled": true,
    "database": "books_db",
    "table": "book_texts",
    "text_column": "content",
    "join_columns": {
      "book_id": 1,
      "chapter": 1
    },
    "full_text_query": "SELECT content FROM book_texts WHERE book_id = ? ORDER BY chapter"
  },
  
  "indexed_at": "2026-02-19T10:00:00Z",
  "content_hash": "sha256:abc123..."
}
```

### РњРёРЅРёРјР°Р»СЊРЅР°СЏ СЃС…РµРјР° (РґР»СЏ СЌРєРѕРЅРѕРјРёРё РјРµСЃС‚Р°)

```json
{
  "chunk_id": "book_chunk_0001_0000",
  "document_id": "book_0001",
  "source": "books",
  "content": "С‚РµРєСЃС‚ С‡Р°РЅРєР°...",
  "vector_id": 0,
  "book_id": 1,
  "author_id": 1,
  "chapter": 1,
  "chunk_index": 0
}
```

**РџСЂРёРјРµС‡Р°РЅРёРµ:** РџРѕР»РЅС‹Рµ РјРµС‚Р°РґР°РЅРЅС‹Рµ РєРЅРёРі С…СЂР°РЅСЏС‚СЃСЏ РІ SQL, РІ РІРµРєС‚РѕСЂРЅРѕР№ Р‘Р” С‚РѕР»СЊРєРѕ СЃСЃС‹Р»РєРё.

---

## рџ”Ќ РЎС†РµРЅР°СЂРёРё РёСЃРїРѕР»СЊР·РѕРІР°РЅРёСЏ

### РЎС†РµРЅР°СЂРёР№ 1: РЎРµРјР°РЅС‚РёС‡РµСЃРєРёР№ РїРѕРёСЃРє РїРѕ С‚РµРєСЃС‚Р°Рј РєРЅРёРі

**Р—Р°РїСЂРѕСЃ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ:**
```
"РЅР°Р№РґРё РєРЅРёРіРё Рѕ Р»СЋР±РІРё Рё РІРѕР№РЅРµ"
```

**Р’С‹РїРѕР»РЅРµРЅРёРµ:**
```python
# 1. Р’РµРєС‚РѕСЂРЅС‹Р№ РїРѕРёСЃРє
results = await agent.use_tool(
    "vector_books_tool",
    query="Р»СЋР±РѕРІСЊ РІРѕР№РЅР° СЂРѕРјР°РЅ",
    top_k=10
)

# 2. Р РµР·СѓР»СЊС‚Р°С‚С‹
[
  {
    "chunk_id": "book_chunk_0001_0025",
    "score": 0.92,
    "content": "С‚РµРєСЃС‚ С‡Р°РЅРєР° СЃ РѕРїРёСЃР°РЅРёРµРј СЃС†РµРЅС‹...",
    "book_id": 1,
    "book_title": "Р’РѕР№РЅР° Рё РјРёСЂ",
    "author_name": "Р›РµРІ РўРѕР»СЃС‚РѕР№",
    "chapter": 5,
    "chunk_index": 25
  },
  {
    "chunk_id": "book_chunk_0002_0010",
    "score": 0.87,
    "content": "С‚РµРєСЃС‚ С‡Р°РЅРєР°...",
    "book_id": 2,
    "book_title": "РђРЅРЅР° РљР°СЂРµРЅРёРЅР°",
    "author_name": "Р›РµРІ РўРѕР»СЃС‚РѕР№",
    "chapter": 3,
    "chunk_index": 10
  }
]
```

---

### РЎС†РµРЅР°СЂРёР№ 2: РџРѕР»СѓС‡РµРЅРёРµ РїРѕР»РЅРѕРіРѕ С‚РµРєСЃС‚Р° РєРЅРёРіРё

**Р—Р°РїСЂРѕСЃ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ:**
```
"РґР°Р№ РїРѕР»РЅС‹Р№ С‚РµРєСЃС‚ РєРЅРёРіРё Р’РѕР№РЅР° Рё РјРёСЂ"
```

**Р’С‹РїРѕР»РЅРµРЅРёРµ:**
```python
# 1. SQL Р·Р°РїСЂРѕСЃ (С‡РµСЂРµР· sql_tool)
result = await agent.use_tool(
    "sql_tool",
    query="""
        SELECT bt.content, bt.chapter, bt.title as chapter_title
        FROM book_texts bt
        JOIN books b ON bt.book_id = b.id
        WHERE b.id = 1
        ORDER BY bt.chapter
    """
)

# 2. Р РµР·СѓР»СЊС‚Р°С‚С‹
{
  "book_id": 1,
  "book_title": "Р’РѕР№РЅР° Рё РјРёСЂ",
  "author_name": "Р›РµРІ РўРѕР»СЃС‚РѕР№",
  "chapters": [
    {
      "chapter": 1,
      "chapter_title": "Р“Р»Р°РІР° 1",
      "content": "РїРѕР»РЅС‹Р№ С‚РµРєСЃС‚ РіР»Р°РІС‹ 1..."
    },
    {
      "chapter": 2,
      "chapter_title": "Р“Р»Р°РІР° 2",
      "content": "РїРѕР»РЅС‹Р№ С‚РµРєСЃС‚ РіР»Р°РІС‹ 2..."
    }
  ]
}
```

---

### РЎС†РµРЅР°СЂРёР№ 3: Р“РёР±СЂРёРґРЅС‹Р№ РїРѕРёСЃРє (РІРµРєС‚РѕСЂ + SQL С„РёР»СЊС‚СЂ)

**Р—Р°РїСЂРѕСЃ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ:**
```
"РЅР°Р№РґРё Сѓ РўРѕР»СЃС‚РѕРіРѕ РїСЂРѕ Р»СЋР±РѕРІСЊ"
```

**Р’С‹РїРѕР»РЅРµРЅРёРµ:**
```python
# Р’Р°СЂРёР°РЅС‚ 1: Р’РµРєС‚РѕСЂРЅС‹Р№ РїРѕРёСЃРє СЃ С„РёР»СЊС‚СЂРѕРј РїРѕ author_id
results = await agent.use_tool(
    "vector_books_tool",
    query="Р»СЋР±РѕРІСЊ",
    top_k=10,
    filters={"author_id": [1]}  # в†ђ Р¤РёР»СЊС‚СЂ РїРѕ Р°РІС‚РѕСЂСѓ
)

# Р’Р°СЂРёР°РЅС‚ 2: SQL в†’ Р’РµРєС‚РѕСЂРЅС‹Р№ РїРѕСЃС‚-С„РёР»СЊС‚СЂ
# 1. SQL: РїРѕР»СѓС‡Р°РµРј book_id РґР»СЏ Р°РІС‚РѕСЂР°
books = await sql_db.fetch(
    "SELECT id FROM books WHERE author_id = ?",
    (1,)
)
book_ids = [b["id"] for b in books]

# 2. Vector: РїРѕРёСЃРє РїРѕ РєРЅРёРіР°Рј Р°РІС‚РѕСЂР°
results = await agent.use_tool(
    "vector_books_tool",
    query="Р»СЋР±РѕРІСЊ",
    top_k=10,
    filters={"book_id": book_ids}
)
```

---

### РЎС†РµРЅР°СЂРёР№ 4: РџРѕРёСЃРє СЃ РїРµСЂРµС…РѕРґРѕРј Рє РїРѕР»РЅРѕРјСѓ С‚РµРєСЃС‚Сѓ

**Р—Р°РїСЂРѕСЃ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ:**
```
"РЅР°Р№РґРё СЃС†РµРЅСѓ Р±Р°Р»Р° РІ Р’РѕР№РЅРµ Рё РјРёСЂ Рё РїРѕРєР°Р¶Рё РїРѕР»РЅС‹Р№ С‚РµРєСЃС‚"
```

**Р’С‹РїРѕР»РЅРµРЅРёРµ:**
```python
# 1. Р’РµРєС‚РѕСЂРЅС‹Р№ РїРѕРёСЃРє СЃС†РµРЅС‹
chunk_results = await agent.use_tool(
    "vector_books_tool",
    query="Р±Р°Р» РќР°С‚Р°С€Р° Р РѕСЃС‚РѕРІР°",
    top_k=3
)

# 2. РџРѕР»СѓС‡Р°РµРј book_id РёР· СЂРµР·СѓР»СЊС‚Р°С‚РѕРІ
book_id = chunk_results[0]["book_id"]  # 1

# 3. SQL: РїРѕР»СѓС‡Р°РµРј РїРѕР»РЅС‹Р№ С‚РµРєСЃС‚ РєРЅРёРіРё
full_text = await agent.use_tool(
    "sql_tool",
    query="""
        SELECT content, chapter
        FROM book_texts
        WHERE book_id = ?
        ORDER BY chapter
    """,
    parameters=(book_id,)
)

# 4. Р’РѕР·РІСЂР°С‰Р°РµРј С‡Р°РЅРє + РїРѕР»РЅС‹Р№ С‚РµРєСЃС‚
{
  "chunk_results": chunk_results,
  "full_book_text": full_text
}
```

---

## рџ› пёЏ VectorBooksTool

### РњР°РЅРёС„РµСЃС‚

```yaml
# data/manifests/tools/vector_books_tool/manifest.yaml

name: "vector_books_tool"
version: "1.0.0"
description: "РЎРµРјР°РЅС‚РёС‡РµСЃРєРёР№ РїРѕРёСЃРє РїРѕ С‚РµРєСЃС‚Р°Рј РєРЅРёРі СЃ РёРЅС‚РµРіСЂР°С†РёРµР№ SQL"

capabilities:
  - name: "search"
    description: "РџРѕРёСЃРє РїРѕ С‚РµРєСЃС‚Р°Рј РєРЅРёРі (РІРµРєС‚РѕСЂРЅС‹Р№)"
    input_contract: "vector_books.search_input_v1.0.0"
    output_contract: "vector_books.search_output_v1.0.0"
  
  - name: "get_book_text"
    description: "РџРѕР»СѓС‡РµРЅРёРµ РїРѕР»РЅРѕРіРѕ С‚РµРєСЃС‚Р° РєРЅРёРіРё (SQL)"
    input_contract: "vector_books.get_book_text_input_v1.0.0"
    output_contract: "vector_books.get_book_text_output_v1.0.0"
  
  - name: "get_chapter_text"
    description: "РџРѕР»СѓС‡РµРЅРёРµ С‚РµРєСЃС‚Р° РіР»Р°РІС‹ (SQL)"
    input_contract: "vector_books.get_chapter_text_input_v1.0.0"
    output_contract: "vector_books.get_chapter_text_output_v1.0.0"

dependencies:
  infrastructure:
    - "faiss_provider_books"
    - "sql_provider"
  services:
    - "book_indexing_service"

config:
  default_top_k: 10
  max_top_k: 50
  chunk_size: 500
  chunk_overlap: 50
```

---

### РџСЂРѕРјРїС‚ РґР»СЏ РЅР°РІС‹РєР°

```
РўС‹ вЂ” РёРЅСЃС‚СЂСѓРјРµРЅС‚ СЃРµРјР°РЅС‚РёС‡РµСЃРєРѕРіРѕ РїРѕРёСЃРєР° РїРѕ С‚РµРєСЃС‚Р°Рј РєРЅРёРі.

РСЃРїРѕР»СЊР·СѓР№ СЌС‚РѕС‚ РЅР°РІС‹Рє РґР»СЏ:
- РџРѕРёСЃРєР° СЃС†РµРЅ, С†РёС‚Р°С‚, РѕРїРёСЃР°РЅРёР№ РІ С‚РµРєСЃС‚Р°С… РєРЅРёРі
- РџРѕРёСЃРєР° РїРѕ СЃРјС‹СЃР»Сѓ (РЅРµ С‚РѕС‡РЅРѕРµ СЃРѕРІРїР°РґРµРЅРёРµ СЃР»РѕРІ)
- РџРѕРёСЃРєР° СЃ С„РёР»СЊС‚СЂР°РјРё РїРѕ Р°РІС‚РѕСЂСѓ, Р¶Р°РЅСЂСѓ, РіРѕРґСѓ

РџР°СЂР°РјРµС‚СЂС‹:
- query: С‚РµРєСЃС‚ Р·Р°РїСЂРѕСЃР° (РѕР±СЏР·Р°С‚РµР»СЊРЅРѕ)
- top_k: РєРѕР»РёС‡РµСЃС‚РІРѕ СЂРµР·СѓР»СЊС‚Р°С‚РѕРІ (РїРѕ СѓРјРѕР»С‡Р°РЅРёСЋ 10)
- filters: РѕРїС†РёРѕРЅР°Р»СЊРЅС‹Рµ С„РёР»СЊС‚СЂС‹
  - author_id: С„РёР»СЊС‚СЂ РїРѕ Р°РІС‚РѕСЂСѓ
  - book_id: С„РёР»СЊС‚СЂ РїРѕ РєРЅРёРіРµ
  - genre: С„РёР»СЊС‚СЂ РїРѕ Р¶Р°РЅСЂСѓ
  - year_from, year_to: С„РёР»СЊС‚СЂ РїРѕ РіРѕРґСѓ

Р”Р»СЏ РїРѕР»СѓС‡РµРЅРёСЏ РїРѕР»РЅРѕРіРѕ С‚РµРєСЃС‚Р° РєРЅРёРіРё РёСЃРїРѕР»СЊР·СѓР№ capability "get_book_text".
Р”Р»СЏ РїРѕР»СѓС‡РµРЅРёСЏ С‚РµРєСЃС‚Р° РіР»Р°РІС‹ РёСЃРїРѕР»СЊР·СѓР№ capability "get_chapter_text".

РџСЂРёРјРµСЂС‹:
- search(query="Р»СЋР±РѕРІСЊ РІРѕР№РЅР°", top_k=10)
- search(query="Р±Р°Р»", filters={"author_id": [1]})
- get_book_text(book_id=1)
- get_chapter_text(book_id=1, chapter=5)
```

---

## рџ”„ РЎРёРЅС…СЂРѕРЅРёР·Р°С†РёСЏ SQL в†” Vector

### Р”РѕР±Р°РІР»РµРЅРёРµ РєРЅРёРіРё РІ РІРµРєС‚РѕСЂРЅС‹Р№ РёРЅРґРµРєСЃ

```python
# core/application/services/book_indexing_service.py

class BookIndexingService:
    """РЎРµСЂРІРёСЃ РёРЅРґРµРєСЃР°С†РёРё РєРЅРёРі РІ РІРµРєС‚РѕСЂРЅРѕРј РёРЅРґРµРєСЃРµ."""
    
    def __init__(
        self,
        sql_provider: SQLProvider,
        faiss_provider: FAISSProvider,
        embedding_provider: EmbeddingProvider,
        chunking_service: ChunkingService
    ):
        self.sql = sql_provider
        self.faiss = faiss_provider
        self.embedding = embedding_provider
        self.chunking = chunking_service
    
    async def index_book(self, book_id: int) -> IndexResult:
        """Р”РѕР±Р°РІР»РµРЅРёРµ РєРЅРёРіРё РІ РІРµРєС‚РѕСЂРЅС‹Р№ РёРЅРґРµРєСЃ."""
        
        # 1. РџРѕР»СѓС‡Р°РµРј РґР°РЅРЅС‹Рµ РєРЅРёРіРё РёР· SQL
        book_data = await self.sql.fetch("""
            SELECT 
                b.id as book_id,
                b.title,
                b.author_id,
                b.year,
                b.genre,
                b.language,
                a.name as author_name,
                a.nationality
            FROM books b
            JOIN authors a ON b.author_id = a.id
            WHERE b.id = ?
        """, (book_id,))
        
        if not book_data:
            raise ValueError(f"Book {book_id} not found")
        
        book = book_data[0]
        
        # 2. РџРѕР»СѓС‡Р°РµРј С‚РµРєСЃС‚С‹ РіР»Р°РІ
        chapter_texts = await self.sql.fetch("""
            SELECT chapter, title as chapter_title, content
            FROM book_texts
            WHERE book_id = ?
            ORDER BY chapter
        """, (book_id,))
        
        # 3. Р Р°Р·Р±РёРІР°РµРј РЅР° С‡Р°РЅРєРё
        all_chunks = []
        for chapter in chapter_texts:
            chapter_chunks = await self.chunking.split(
                content=chapter["content"],
                chapter=chapter["chapter"],
                chapter_title=chapter["chapter_title"]
            )
            all_chunks.extend(chapter_chunks)
        
        # 4. Р“РµРЅРµСЂРёСЂСѓРµРј СЌРјР±РµРґРґРёРЅРіРё
        vectors = await self.embedding.generate(
            [chunk.content for chunk in all_chunks]
        )
        
        # 5. Р¤РѕСЂРјРёСЂСѓРµРј РјРµС‚Р°РґР°РЅРЅС‹Рµ
        metadata = []
        for i, (chunk, vector) in enumerate(zip(all_chunks, vectors)):
            metadata.append({
                "chunk_id": f"book_chunk_{book_id:04d}_{i:04d}",
                "document_id": f"book_{book_id:04d}",
                "source": "books",
                "content": chunk.content,
                "book_id": book["book_id"],
                "book_title": book["title"],
                "author_id": book["author_id"],
                "author_name": book["author_name"],
                "year": book["year"],
                "genre": book["genre"],
                "language": book["language"],
                "chapter": chunk.chapter,
                "chapter_title": chunk.chapter_title,
                "chunk_index": i,
                "total_chunks": len(all_chunks),
                "sql_reference": {
                    "enabled": True,
                    "table": "book_texts",
                    "text_column": "content",
                    "join_columns": {
                        "book_id": book_id,
                        "chapter": chunk.chapter
                    }
                }
            })
        
        # 6. Р”РѕР±Р°РІР»СЏРµРј РІ FAISS
        await self.faiss.add(vectors, metadata)
        
        # 7. РћР±РЅРѕРІР»СЏРµРј РјРµС‚РєСѓ РёРЅРґРµРєСЃР°С†РёРё РІ SQL
        await self.sql.execute("""
            UPDATE books SET indexed_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (book_id,))
        
        return IndexResult(
            book_id=book_id,
            chunks_indexed=len(all_chunks),
            vectors_added=len(vectors)
        )
    
    async def reindex_book(self, book_id: int) -> IndexResult:
        """РџРµСЂРµРёРЅРґРµРєСЃР°С†РёСЏ РєРЅРёРіРё (СѓРґР°Р»РµРЅРёРµ + РґРѕР±Р°РІР»РµРЅРёРµ)."""
        
        # 1. РЈРґР°Р»СЏРµРј СЃС‚Р°СЂС‹Рµ С‡Р°РЅРєРё
        await self.faiss.delete_by_filter({"book_id": book_id})
        
        # 2. Р”РѕР±Р°РІР»СЏРµРј Р·Р°РЅРѕРІРѕ
        return await self.index_book(book_id)
    
    async def index_all_books(self) -> List[IndexResult]:
        """РРЅРґРµРєСЃР°С†РёСЏ РІСЃРµС… РєРЅРёРі."""
        
        # РџРѕР»СѓС‡Р°РµРј РІСЃРµ РєРЅРёРіРё
        books = await self.sql.fetch("SELECT id FROM books")
        
        results = []
        for book in books:
            try:
                result = await self.index_book(book["id"])
                results.append(result)
            except Exception as e:
                logger.error(f"Failed to index book {book['id']}: {e}")
        
        return results
```

---

### Event-driven СЃРёРЅС…СЂРѕРЅРёР·Р°С†РёСЏ

```python
# core/infrastructure/event_bus/vector_event_handler.py

class VectorBookEventHandler:
    """РћР±СЂР°Р±РѕС‚С‡РёРє СЃРѕР±С‹С‚РёР№ РґР»СЏ СЃРёРЅС…СЂРѕРЅРёР·Р°С†РёРё РєРЅРёРі."""
    
    def __init__(self, indexing_service: BookIndexingService):
        self.indexing_service = indexing_service
    
    @subscribe_to_event("BookCreated")
    async def on_book_created(self, event: BookCreatedEvent):
        """РќРѕРІР°СЏ РєРЅРёРіР° СЃРѕР·РґР°РЅР° в†’ РґРѕР±Р°РІРёС‚СЊ РІ РІРµРєС‚РѕСЂРЅС‹Р№ РёРЅРґРµРєСЃ."""
        await self.indexing_service.index_book(event.book_id)
    
    @subscribe_to_event("BookUpdated")
    async def on_book_updated(self, event: BookUpdatedEvent):
        """РљРЅРёРіР° РѕР±РЅРѕРІР»РµРЅР° в†’ РїРµСЂРµРёРЅРґРµРєСЃРёСЂРѕРІР°С‚СЊ."""
        if event.text_changed:
            await self.indexing_service.reindex_book(event.book_id)
    
    @subscribe_to_event("BookDeleted")
    async def on_book_deleted(self, event: BookDeletedEvent):
        """РљРЅРёРіР° СѓРґР°Р»РµРЅР° в†’ СѓРґР°Р»РёС‚СЊ РёР· РІРµРєС‚РѕСЂРЅРѕРіРѕ РёРЅРґРµРєСЃР°."""
        await self.faiss_provider_books.delete_by_filter(
            {"book_id": event.book_id}
        )
```

---

## рџ“Љ РњРµС‚СЂРёРєРё

### РњРµС‚СЂРёРєРё РёРЅРґРµРєСЃР°С†РёРё

```python
{
    "books_indexing": {
        "total_books": 150,
        "indexed_books": 145,
        "pending_books": 5,
        "total_chunks": 7500,
        "total_vectors": 7500,
        "index_size_mb": 75,
        "last_indexing": "2026-02-19T10:00:00Z"
    }
}
```

### РњРµС‚СЂРёРєРё РїРѕРёСЃРєР°

```python
{
    "vector_books_tool": {
        "search_count_24h": 200,
        "avg_search_latency_ms": 55,
        "p95_latency_ms": 90,
        "avg_results_count": 8.5,
        "get_book_text_count_24h": 50
    }
}
```

---

## рџ“Ѓ РћР±РЅРѕРІР»С‘РЅРЅР°СЏ СЃС‚СЂСѓРєС‚СѓСЂР° С„Р°Р№Р»РѕРІ

```
data/vector/
в”њв”Ђв”Ђ knowledge_index.faiss
в”њв”Ђв”Ђ knowledge_metadata.json
в”њв”Ђв”Ђ history_index.faiss
в”њв”Ђв”Ђ history_metadata.json
в”њв”Ђв”Ђ docs_index.faiss
в”њв”Ђв”Ђ docs_metadata.json
в”њв”Ђв”Ђ books_index.faiss          в†ђ РќРѕРІС‹Р№
в”њв”Ђв”Ђ books_metadata.json        в†ђ РќРѕРІС‹Р№
в””в”Ђв”Ђ config.json

data/manifests/tools/
в”њв”Ђв”Ђ vector_knowledge_tool/
в”њв”Ђв”Ђ vector_history_tool/
в”њв”Ђв”Ђ vector_docs_tool/
в””в”Ђв”Ђ vector_books_tool/         в†ђ РќРѕРІС‹Р№
    в””в”Ђв”Ђ manifest.yaml

core/application/services/
в”њв”Ђв”Ђ vector_search_service.py
в”њв”Ђв”Ђ book_indexing_service.py   в†ђ РќРѕРІС‹Р№
в””в”Ђв”Ђ ...

core/application/tools/
в”њв”Ђв”Ђ vector_knowledge_tool.py
в”њв”Ђв”Ђ vector_history_tool.py
в”њв”Ђв”Ђ vector_docs_tool.py
в””в”Ђв”Ђ vector_books_tool.py       в†ђ РќРѕРІС‹Р№
```

---

## рџЋЇ РљСЂРёС‚РµСЂРёРё РїСЂРёС‘РјРєРё

### Р¤СѓРЅРєС†РёРѕРЅР°Р»СЊРЅС‹Рµ:
```
вњ… РЎРµРјР°РЅС‚РёС‡РµСЃРєРёР№ РїРѕРёСЃРє РїРѕ С‚РµРєСЃС‚Р°Рј РєРЅРёРі СЂР°Р±РѕС‚Р°РµС‚
вњ… РџРѕР»СѓС‡РµРЅРёРµ РїРѕР»РЅРѕРіРѕ С‚РµРєСЃС‚Р° РєРЅРёРіРё С‡РµСЂРµР· SQL СЂР°Р±РѕС‚Р°РµС‚
вњ… Р“РёР±СЂРёРґРЅС‹Р№ РїРѕРёСЃРє (РІРµРєС‚РѕСЂ + SQL С„РёР»СЊС‚СЂ) СЂР°Р±РѕС‚Р°РµС‚
вњ… РЎРёРЅС…СЂРѕРЅРёР·Р°С†РёСЏ SQL в†” Vector СЂР°Р±РѕС‚Р°РµС‚
вњ… Event-driven РѕР±РЅРѕРІР»РµРЅРёСЏ СЂР°Р±РѕС‚Р°СЋС‚
```

### РќРµС„СѓРЅРєС†РёРѕРЅР°Р»СЊРЅС‹Рµ:
```
вњ… Р’СЂРµРјСЏ РїРѕРёСЃРєР° p95 < 1000ms
вњ… РРЅРґРµРєСЃР°С†РёСЏ РєРЅРёРіРё (100 РіР»Р°РІ) < 60 СЃРµРє
вњ… РњРµС‚Р°РґР°РЅРЅС‹Рµ С‡Р°РЅРєР° < 1KB
```

---

*Р”РѕРєСѓРјРµРЅС‚ СЃРѕР·РґР°РЅ: 2026-02-19*
*Р’РµСЂСЃРёСЏ: 1.0.1*
*РЎС‚Р°С‚СѓСЃ: вњ… РЈС‚РІРµСЂР¶РґРµРЅРѕ*

---

## рџ“ќ РСЃС‚РѕСЂРёСЏ РёР·РјРµРЅРµРЅРёР№

| Р”Р°С‚Р° | Р’РµСЂСЃРёСЏ | РР·РјРµРЅРµРЅРёРµ |
|------|--------|-----------|
| 2026-02-19 | 1.0.0 | Initial document |
| 2026-02-19 | 1.0.1 | РЈРїСЂРѕС‰РµРЅРѕ: VectorBooksTool СЃРѕРґРµСЂР¶РёС‚ РІСЃСЋ Р»РѕРіРёРєСѓ (Р±РµР· BookAnalysisTool) |
