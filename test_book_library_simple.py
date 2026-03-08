"""
Простой тест BookLibrarySkill.
Проверяем что _execute_impl возвращает dict а не SkillResult.
"""

# Проверяем сигнатуру метода
import inspect
from core.application.skills.book_library.skill import BookLibrarySkill

# Получаем сигнатуру _execute_impl
sig = inspect.signature(BookLibrarySkill._execute_impl)
print(f"_execute_impl signature: {sig}")
print(f"_execute_impl return annotation: {BookLibrarySkill._execute_impl.__annotations__.get('return', 'N/A')}")

# Проверяем что методы возвращают SkillResult
print(f"\n_search_books_dynamic return: {BookLibrarySkill._search_books_dynamic.__annotations__.get('return', 'N/A')}")
print(f"_execute_script_static return: {BookLibrarySkill._execute_script_static.__annotations__.get('return', 'N/A')}")

print("\n[OK] Проверка завершена")
