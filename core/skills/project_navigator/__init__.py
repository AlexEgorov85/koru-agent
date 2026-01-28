"""
ProjectNavigatorSkill — навык для структурной навигации по кодовой базе.
ОСОБЕННОСТИ:
- Фокус на навигации (не семантическом анализе)
- Интеграция с ProjectMap из контекста сессии
- Использование существующих сервисов (ASTProcessingService)
- Минимальная сложность и зависимостей
"""
from .skill import ProjectNavigatorSkill

__all__ = ['ProjectNavigatorSkill']