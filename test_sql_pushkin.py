#!/usr/bin/env python3
"""Проверка SQL запроса для поиска книг Пушкина"""
import psycopg2

conn = psycopg2.connect(
    host='localhost',
    port=5432,
    database='postgres',
    user='postgres',
    password='1'
)
cur = conn.cursor()

# Точная копия SQL из scripts_registry.py для get_books_by_author (исправленная)
sql = """
    SELECT
        b.id as book_id,
        b.title as book_title,
        b.isbn,
        b.publication_date,
        a.id as author_id,
        a.first_name,
        a.last_name,
        a.birth_date
    FROM "Lib".books b
    JOIN "Lib".authors a ON b.author_id = a.id
    WHERE a.last_name ILIKE %s
    ORDER BY b.title
    LIMIT %s
"""

print("=== Тест 1: Параметр 'Пушкин' (без %) ===")
cur.execute(sql, ('Пушкин', 50))
rows = cur.fetchall()
print(f"Найдено строк: {len(rows)}")
for r in rows[:5]:
    print(f"  {r[1]} ({r[4]})")

print("\n=== Тест 2: Параметр '%Пушкин%' (с %) ===")
cur.execute(sql, ('%Пушкин%', 50))
rows = cur.fetchall()
print(f"Найдено строк: {len(rows)}")
for r in rows[:5]:
    print(f"  {r[1]} ({r[4]})")

print("\n=== Тест 3: Проверка книг Пушкина ===")
cur.execute("""
    SELECT b.id, b.title, a.last_name, a.first_name 
    FROM "Lib".books b 
    JOIN "Lib".authors a ON b.author_id = a.id 
    WHERE a.id = 1
""")
rows = cur.fetchall()
print(f"Книг у Пушкина (ID=1): {len(rows)}")
for r in rows[:10]:
    print(f"  {r[1]}")

cur.close()
conn.close()
