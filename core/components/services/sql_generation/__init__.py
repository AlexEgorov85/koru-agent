"""
SQL Generation Service - генерация и коррекция SQL запросов.

КОМПОНЕНТЫ:
- SQLGenerationService: основной сервис генерации SQL
- SQLErrorAnalyzer: анализ ошибок выполнения SQL
- SQLCorrectionEngine: коррекция SQL запросов на основе ошибок
"""
from .service import SQLGenerationService
from .error_analyzer import SQLErrorAnalyzer, ExecutionError
from .correction import SQLCorrectionEngine

__all__ = [
    "SQLGenerationService",
    "SQLErrorAnalyzer",
    "ExecutionError",
    "SQLCorrectionEngine",
]
