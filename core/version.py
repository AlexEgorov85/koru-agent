"""
Версия проекта Agent v5.

Исползуются семантическое версионирование (SemVer):
- MAJOR (первая цифра): кардинальные изменения архитектуры
- MINOR (вторая цифра): новые возможности, рефакторинг фаз, добавление компонентов
- PATCH (третья цифра): исправления ошибок, обновление промптов
"""

# Основная версия
__version__ = "5.46.2"

# Компоненты версии
VERSION_MAJOR = 5
VERSION_MINOR = 46
VERSION_PATCH = 2

# Метаданные
VERSION_CODENAME = "License Fix + Test Updates"
VERSION_RELEASE_DATE = "2026-05-04"

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
