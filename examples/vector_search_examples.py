"""
Примеры использования Vector Search.

VectorSearchTool — универсальный инструмент для семантического поиска.
Поддерживаемые источники (source): books, authors, audits, violations, ...

Запуск:
    python examples/vector_search_examples.py

ПРИМЕЧАНИЕ: Примеры устарели — VectorSearchTool теперь получает инфраструктуру
из ApplicationContext, а не через конструктор.
См. актуальное использование в core/components/skills/
"""

import asyncio
import sys
from pathlib import Path

# Добавляем корень проекта в path
sys.path.insert(0, str(Path(__file__).parent.parent))


async def example_1_basic_search():
    """Базовый поиск через VectorSearchTool (устаревший пример)."""
    print("\n" + "="*60)
    print("Пример 1: Базовый поиск")
    print("="*60)
    print("⚠️  Этот пример устарел. VectorSearchTool теперь получает")
    print("   инфраструктуру из ApplicationContext, а не через конструктор.")
    print("   См. core/components/skills/check_result/handlers/vector_search_handler.py")


async def example_2_audit_search():
    """Поиск по аудиторским проверкам (устаревший пример)."""
    print("\n" + "="*60)
    print("Пример 2: Поиск по аудиторским проверкам")
    print("="*60)
    print("⚠️  Этот пример устарел. См. актуальное использование в")
    print("   core/components/skills/check_result/handlers/vector_search_handler.py")


async def example_3_violation_search():
    """Поиск по отклонениям (устаревший пример)."""
    print("\n" + "="*60)
    print("Пример 3: Поиск по отклонениям")
    print("="*60)
    print("⚠️  Этот пример устарел. См. актуальное использование в")
    print("   core/components/skills/check_result/handlers/vector_search_handler.py")


async def main():
    """Запуск всех примеров."""
    print("\n" + "="*60)
    print("Vector Search примеры")
    print("="*60)
    print("\nВсе примеры устарели — VectorSearchTool теперь работает через")
    print("ApplicationContext и получает FAISS провайдеры динамически.")
    print("\nАктуальное использование:")
    print("  core/components/skills/check_result/handlers/vector_search_handler.py")
    print("  core/components/skills/book_library/handlers/semantic_search_handler.py")

    await example_1_basic_search()
    await example_2_audit_search()
    await example_3_violation_search()


if __name__ == "__main__":
    asyncio.run(main())
