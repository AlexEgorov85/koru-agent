"""
Валидатор схемы для ReAct стратегии в новой архитектуре
"""
from typing import Dict, Any, Optional
from core.models.data.capability import Capability


class SchemaValidator:
    """Валидатор параметров capability для ReAct стратегии"""

    def __init__(self):
        # Кэш схем: {capability_name: {"input": schema_dict}}
        self._schemas_cache: Dict[str, Dict[str, Any]] = {}

    def register_capability_schema(self, capability_name: str, input_schema: Dict[str, Any]):
        """
        Регистрирует схему для capability.

        ARGS:
        - capability_name: имя capability
        - input_schema: схема входных параметров из контракта
        """
        self._schemas_cache[capability_name] = input_schema
        return True

    def get_capability_schema(self, capability_name: str) -> Optional[Dict[str, Any]]:
        """
        Получает схему для capability.

        ARGS:
        - capability_name: имя capability

        RETURNS:
        - Схема параметров или None
        """
        return self._schemas_cache.get(capability_name)

    def validate_parameters(
        self,
        capability: Capability,
        raw_params: Dict[str, Any],
        context: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Валидирует параметры для данной capability.

        ARGS:
        - capability: объект capability для валидации
        - raw_params: необработанные параметры
        - context: дополнительный контекст для валидации

        RETURNS:
        - Валидированные параметры или None, если валидация не удалась
        """
        import logging
        import re
        logger = logging.getLogger(__name__)

        if not capability or not raw_params:
            return None

        # Получаем схему из кэша по имени capability
        params_schema = self.get_capability_schema(capability.name)

        # logger.info(f"validate_parameters: capability={capability.name}, raw_params={raw_params}, params_schema={params_schema}")

        # Если схема не найдена в кэше, пробуем получить из meta capability
        if not params_schema:
            # Пытаемся получить из meta (если там есть contract_schema)
            params_schema = capability.meta.get('contract_schema', {})
            self.event_bus_logger.debug(f"Схема не найдена в кэше, пробуем из meta: {params_schema}")

        # Если схема всё ещё пуста, создаём минимальную схему с "input"
        if not params_schema:
            # Дефолтная схема: требуется поле "input" типа string
            params_schema = {
                "input": {"type": "string", "required": True}
            }
            self.event_bus_logger.debug(f"Используем дефолтную схему: {params_schema}")

        # СПЕЦИАЛЬНАЯ ЛОГИКА для book_library.execute_script
        # Если LLM передал только {"input": "..."}, пытаемся извлечь автора и создать правильные параметры
        if capability.name == "book_library.execute_script":
            validated_params = self._try_fix_book_library_params(raw_params, params_schema)
            if validated_params:
                self.event_bus_logger.info(f"✅ Параметры для book_library.execute_script исправлены: {validated_params}")
                return validated_params

        validated_params = {}

        # Проходим по каждому параметру и валидируем его
        for param_name, param_info in params_schema.items():
            if param_name in raw_params:
                # Простая валидация типов
                param_value = raw_params[param_name]

                # Проверяем тип, если он указан в схеме
                expected_type = param_info.get('type')
                if expected_type:
                    if expected_type == 'string' and not isinstance(param_value, str):
                        # Попробуем преобразовать к строке
                        try:
                            param_value = str(param_value)
                        except:
                            # Если не удается преобразовать, пропускаем этот параметр
                            self.event_bus_logger.warning(f"Не удалось преобразовать параметр {param_name} к строке")
                            continue
                    elif expected_type == 'integer' and not isinstance(param_value, int):
                        try:
                            param_value = int(param_value)
                        except:
                            self.event_bus_logger.warning(f"Не удалось преобразовать параметр {param_name} к integer")
                            continue
                    elif expected_type == 'number' and not isinstance(param_value, (int, float)):
                        try:
                            param_value = float(param_value)
                        except:
                            self.event_bus_logger.warning(f"Не удалось преобразовать параметр {param_name} к number")
                            continue
                    elif expected_type == 'boolean' and not isinstance(param_value, bool):
                        try:
                            param_value = bool(param_value)
                        except:
                            self.event_bus_logger.warning(f"Не удалось преобразовать параметр {param_name} к boolean")
                            continue

                validated_params[param_name] = param_value
                # logger.debug(f"Валидирован параметр {param_name}={param_value}")
            elif param_info.get('required', False):
                # Если параметр обязательный, но отсутствует, возвращаем None
                self.event_bus_logger.warning(f"Обязательный параметр {param_name} отсутствует")
                return None

        # logger.info(f"validate_parameters: result={validated_params}")
        return validated_params

    def _try_fix_book_library_params(
        self,
        raw_params: Dict[str, Any],
        params_schema: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Пытается исправить параметры для book_library.execute_script.
        
        Если LLM передал только {"input": "Какие книги написал Александр Пушкин?"},
        извлекаем имя автора и создаём правильные параметры.
        
        RETURNS:
        - Исправленные параметры или None
        """
        import logging
        import re
        logger = logging.getLogger(__name__)

        # Если уже есть script_name, ничего не делаем
        if 'script_name' in raw_params:
            self.event_bus_logger.debug("script_name уже присутствует, пропускаем исправление")
            return None

        # Если есть только input, пытаемся извлечь информацию
        input_text = raw_params.get('input', '')
        if not input_text:
            self.event_bus_logger.debug("input текст пустой")
            return None

        self.event_bus_logger.info(f"_try_fix_book_library_params: Пытаемся исправить параметры для input='{input_text}'")

        # Паттерны для извлечения авторов (русские имена)
        author_patterns = [
            # "книги написал Александр Пушкин"
            r'(?:написал|написали|автор|авторы)\s+([А-Я][а-яё]+(?:-[А-Я][а-яё]+)?\s+[А-Я][а-яё]+)',
            # "книги Александра Пушкина" (родительный падеж)
            r'(?:книги|произведения|творения)\s+([А-Я][а-яё]+(?:-[А-Я][а-яё]+)?[а-яё]+)',
            # "Пушкин" или "Лев Толстой" (просто имя)
            r'([А-Я][а-яё]+(?:-[А-Я][а-яё]+)?(?:ов|ев|ин|ский|ц[а-яё]+)?\s+[А-Я][а-яё]+(?:-[А-Я][а-яё]+)?)',
        ]

        # Пробуем найти имя автора
        author = None
        for i, pattern in enumerate(author_patterns):
            match = re.search(pattern, input_text)
            if match:
                author = match.group(1).strip()
                # Очищаем от лишних окончаний
                author = re.sub(r'(?:ова|ева|ина|ская|цкого|ого|ему|ым|ою|е)$', '', author)
                self.event_bus_logger.info(f"Найден автор по паттерну #{i} '{pattern}': {author}")
                break

        # Если автор найден, создаём правильные параметры
        if author and len(author) > 2:
            result = {
                "script_name": "get_books_by_author",
                "parameters": {
                    "author": author,
                    "max_rows": 20
                }
            }
            self.event_bus_logger.info(f"✅ Созданы исправленные параметры: {result}")
            return result

        # Если автора нет, пробуем определить тип запроса
        input_lower = input_text.lower()
        if "все книги" in input_lower or "полный список" in input_lower:
            result = {
                "script_name": "get_all_books",
                "parameters": {
                    "max_rows": 50
                }
            }
            self.event_bus_logger.info(f"✅ Определён запрос 'все книги': {result}")
            return result

        # Для других запросов - используем fallback на dynamic search
        self.event_bus_logger.warning(f"❌ Не удалось определить параметры для input='{input_text}'")
        return None