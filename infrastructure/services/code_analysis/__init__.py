"""
Сервисы анализа кода с поддержкой мультиязычности.
АРХИТЕКТУРНЫЕ ПРИНЦИПЫ:
- Чистые сервисы без зависимости от LLM
- Детерминированное поведение (без эвристик)
- Языко-независимые интерфейсы через абстрактные классы
- Расширяемость через адаптеры языков

ИСПОЛЬЗОВАНИЕ:
    # Получение сервисов из системного контекста
    ast_service = system_context.get_resource("ast_processing")
    nav_service = system_context.get_resource("code_navigation")
    
    # Анализ файла
    ast = await ast_service.parse_file("core/main.py", source_code)
    outline = await nav_service.get_file_outline("core/main.py", ast, source_bytes)
"""
from .language_registry import LanguageRegistry
# Убираем импорт несуществующего класса


__all__ = [
    'LanguageRegistry'
]
