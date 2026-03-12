#!/usr/bin/env python3
"""Проверка авторов в базе данных"""
import psycopg2

conn = psycopg2.connect(
    host='localhost',
    port=5432,
    database='postgres',
    user='postgres',
    password='1'
)
cur = conn.cursor()

print("=== Авторы в базе ===")
cur.execute('SELECT DISTINCT last_name, first_name FROM "Lib".authors ORDER BY last_name LIMIT 30')
for r in cur.fetchall():
    print(f"  {r[0]} {r[1]}")

print("\n=== Поиск Пушкина ===")
cur.execute("SELECT id, last_name, first_name FROM \"Lib\".authors WHERE last_name ILIKE '%пуш%' OR last_name ILIKE '%push%'")
for r in cur.fetchall():
    print(f"  ID={r[0]}, Фамилия={r[1]}, Имя={r[2]}")

cur.close()
conn.close()
