"""
Версия проекта Agent v5.

Исползуются семантическое версионирование (SemVer):
- MAJOR (первая цифра): кардинальные изменения архитектуры
- MINOR (вторая цифра): новые возможности, рефакторинг фаз, добавление компонентов
- PATCH (третья цифра): исправления ошибок, обновление промптов
"""

# Основная версия
__version__ = "5.44.0"

# Компоненты версии
VERSION_MAJOR = 5
VERSION_MINOR = 44
VERSION_PATCH = 0

# Метаданные
VERSION_CODENAME = "GigaChat Support + Final Answer Fix"
VERSION_RELEASE_DATE = "2026-04-27"

# Полная строка версии
VERSION_STRING = f"{VERSION_MAJOR}.{VERSION_MINOR}.{VERSION_PATCH} ({VERSION_CODENAME})"


def get_version() -> str:
    """Получить строку версии."""
    return __version__


def get_version_info() -> dict:
    """Получить полную информацию о версии."""
    return {
        "version": __version__,
        "major": VERSION_MAJOR,
        "minor": VERSION_MINOR,
        "patch": VERSION_PATCH,
        "codename": VERSION_CODENAME,
        "release_date": VERSION_RELEASE_DATE,
    }
