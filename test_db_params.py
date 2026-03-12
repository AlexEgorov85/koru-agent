#!/usr/bin/env python3
"""Прямой тест передачи параметров в БД"""
import psycopg2

conn = psycopg2.connect(
    host='localhost',
    port=5432,
    database='postgres',
    user='postgres',
    password='1'
)
cur = conn.cursor()

# SQL из scripts_registry.py (с %s)
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

print("=== Тест 1: params=('%Пушкин%', 50) ===")
cur.execute(sql, ('%Пушкин%', 50))
rows = cur.fetchall()
print(f"Найдено строк: {len(rows)}")
for r in rows[:5]:
    print(f"  {r[1]} ({r[6]})")

print("\n=== Тест 2: params=('Пушкин', 50) ===")
cur.execute(sql, ('Пушкин', 50))
rows = cur.fetchall()
print(f"Найдено строк: {len(rows)}")
for r in rows[:5]:
    print(f"  {r[1]} ({r[6]})")

print("\n=== Тест 3: params=({}, 50) - пустой dict ===")
try:
    cur.execute(sql, ({}, 50))
    rows = cur.fetchall()
    print(f"Найдено строк: {len(rows)}")
except Exception as e:
    print(f"Ошибка: {e}")

print("\n=== Тест 4: params=(None, 50) ===")
try:
    cur.execute(sql, (None, 50))
    rows = cur.fetchall()
    print(f"Найдено строк: {len(rows)}")
except Exception as e:
    print(f"Ошибка: {e}")

cur.close()
conn.close()

print("\n=== Вывод ===")
print("psycopg2 требует кортеж параметров, НЕ dict!")
print("sql_params должен быть кортежем или списком, а не {'1': 'value'}")
