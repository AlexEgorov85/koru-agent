"""
Валидатор схемы для ReAct стратегии в новой архитектуре

АРХИТЕКТУРА:
- Типизированные объекты вместо dict
- Dataclass для структур данных
"""
import logging
import re
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from core.models.data.capability import Capability


@dataclass
class ParameterSchema:
    """
    Схема параметра capability.
    
    ATTRIBUTES:
    - name: Имя параметра
    - type: Ожидаемый тип (string, integer, number, boolean)
    - required: Обязательность параметра
    - description: Описание параметра
    - default: Значение по умолчанию
    """
    name: str
    type: str = "string"
    required: bool = False
    description: str = ""
    default: Any = None


@dataclass
class CapabilitySchema:
    """
    Типизированная схема capability.
    
    ATTRIBUTES:
    - capability_name: Имя capability
    - input_parameters: Параметры входных данных
    - output_schema: Схема выходных данных
    - description: Описание capability
    """
    capability_name: str
    input_parameters: List[ParameterSchema] = field(default_factory=list)
    output_schema: Optional[Dict[str, Any]] = None
    description: str = ""
    
    def get_required_params(self) -> List[str]:
        """Получить список обязательных параметров."""
        return [p.name for p in self.input_parameters if p.required]
    
    def to_dict(self) -> Dict[str, Any]:
        """Конвертация в dict для обратной совместимости."""
        return {
            param.name: {
                'type': param.type,
                'required': param.required,
                'description': param.description,
                'default': param.default
            }
            for param in self.input_parameters
        }


@dataclass
class ValidationResult:
    """
    Результат валидации параметров.
    
    ATTRIBUTES:
    - success: Успешность валидации
    - validated_params: Валидированные параметры
    - errors: Список ошибок
    - warnings: Список предупреждений
    """
    success: bool
    validated_params: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    def add_error(self, error: str):
        """Добавить ошибку."""
        self.errors.append(error)
        self.success = False
    
    def add_warning(self, warning: str):
        """Добавить предупреждение."""
        self.warnings.append(warning)


class SchemaValidator:
    """Валидатор параметров capability для ReAct стратегии"""

    def __init__(self):
        # Кэш схем: {capability_name: CapabilitySchema}
        self._schemas_cache: Dict[str, CapabilitySchema] = {}

    def register_capability_schema(self, capability_name: str, input_schema: Dict[str, Any]):
        """
        Регистрирует схему для capability.

        ARGS:
        - capability_name: имя capability
        - input_schema: схема входных параметров из контракта (dict для обратной совместимости)
        """
        # Конвертируем dict в CapabilitySchema
        schema = self._dict_to_capability_schema(capability_name, input_schema)
        self._schemas_cache[capability_name] = schema
        return True
    
    def _dict_to_capability_schema(self, capability_name: str, input_dict: Dict[str, Any]) -> CapabilitySchema:
        """Конвертация dict схемы в CapabilitySchema."""
        parameters = []
        for param_name, param_info in input_dict.items():
            if isinstance(param_info, dict):
                parameters.append(ParameterSchema(
                    name=param_name,
                    type=param_info.get('type', 'string'),
                    required=param_info.get('required', False),
                    description=param_info.get('description', ''),
                    default=param_info.get('default')
                ))
            else:
                # Упрощённый формат: просто тип
                parameters.append(ParameterSchema(
                    name=param_name,
                    type=param_info if isinstance(param_info, str) else 'string'
                ))
        
        return CapabilitySchema(
            capability_name=capability_name,
            input_parameters=parameters
        )

    def get_capability_schema(self, capability_name: str) -> Optional[CapabilitySchema]:
        """
        Получает схему для capability.

        ARGS:
        - capability_name: имя capability

        RETURNS:
        - CapabilitySchema или None
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
        logger = logging.getLogger(__name__)

        if not capability or not raw_params:
            return None

        # Получаем схему из кэша по имени capability
        schema = self.get_capability_schema(capability.name)

        # Если схема не найдена в кэше, пробуем получить из meta capability
        params_schema_dict = None
        if schema:
            params_schema_dict = schema.to_dict()
        elif capability.meta.get('contract_schema'):
            params_schema_dict = capability.meta.get('contract_schema', {})
            logger.debug(f"Схема не найдена в кэше, используем из meta: {params_schema_dict}")
        
        # Если схема всё ещё пуста, создаём минимальную схему с "input"
        if not params_schema_dict:
            params_schema_dict = {
                "input": {"type": "string", "required": True}
            }
            logger.debug(f"Используем дефолтную схему: {params_schema_dict}")

        # СПЕЦИАЛЬНАЯ ЛОГИКА для book_library.execute_script
        if capability.name == "book_library.execute_script":
            validated_params = self._try_fix_book_library_params(raw_params, params_schema_dict)
            if validated_params:
                logger.info(f"✅ Параметры для book_library.execute_script исправлены: {validated_params}")
                return validated_params

        # Валидация через схему
        result = self._validate_with_schema(params_schema_dict, raw_params, logger)
        
        if result.success:
            return result.validated_params
        else:
            for warning in result.warnings:
                logger.warning(warning)
            for error in result.errors:
                logger.error(error)
            return None
    
    def _validate_with_schema(
        self,
        schema_dict: Dict[str, Any],
        raw_params: Dict[str, Any],
        logger: logging.Logger
    ) -> ValidationResult:
        """Валидация параметров через схему."""
        result = ValidationResult(success=True)
        validated_params = {}

        for param_name, param_info in schema_dict.items():
            if param_name in raw_params:
                param_value = raw_params[param_name]
                
                # Простая валидация типов
                expected_type = param_info.get('type') if isinstance(param_info, dict) else param_info
                if expected_type:
                    converted_value = self._convert_type(param_name, param_value, expected_type, logger, result)
                    if converted_value is not None:
                        validated_params[param_name] = converted_value
                else:
                    validated_params[param_name] = param_value
                    
            elif isinstance(param_info, dict) and param_info.get('required', False):
                result.add_error(f"Обязательный параметр {param_name} отсутствует")

        result.validated_params = validated_params
        return result
    
    def _convert_type(
        self,
        param_name: str,
        value: Any,
        expected_type: str,
        logger: logging.Logger,
        result: ValidationResult
    ) -> Optional[Any]:
        """Преобразование значения к ожидаемому типу."""
        try:
            if expected_type == 'string' and not isinstance(value, str):
                return str(value)
            elif expected_type == 'integer' and not isinstance(value, int):
                return int(value)
            elif expected_type == 'number' and not isinstance(value, (int, float)):
                return float(value)
            elif expected_type == 'boolean' and not isinstance(value, bool):
                return bool(value)
            return value
        except Exception as e:
            result.add_warning(f"Не удалось преобразовать параметр {param_name} к {expected_type}: {e}")
            return None

    def _try_fix_book_library_params(
        self,
        raw_params: Dict[str, Any],
        params_schema: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Пытается исправить параметры для book_library.execute_script.
        """
        logger = logging.getLogger(__name__)

        # Если уже есть script_name, ничего не делаем
        if 'script_name' in raw_params:
            return None

        # Если есть только input, пытаемся извлечь информацию
        input_text = raw_params.get('input', '')
        if not input_text:
            return None

        logger.info(f"_try_fix_book_library_params: Пытаемся исправить параметры для input='{input_text}'")

        # Паттерны для извлечения авторов
        author = self._extract_author_from_text(input_text, logger)
        
        # Если автор найден, создаём правильные параметры
        if author and len(author) > 2:
            return {
                "script_name": "get_books_by_author",
                "parameters": {
                    "author": author,
                    "max_rows": 20
                }
            }

        # Если автора нет, пробуем определить тип запроса
        input_lower = input_text.lower()
        if "все книги" in input_lower or "полный список" in input_lower:
            return {
                "script_name": "get_all_books",
                "parameters": {
                    "max_rows": 50
                }
            }

        logger.warning(f"❌ Не удалось определить параметры для input='{input_text}'")
        return None
    
    def _extract_author_from_text(self, text: str, logger: logging.Logger) -> Optional[str]:
        """Извлечение имени автора из текста."""
        author_patterns = [
            r'(?:написал|написали|автор|авторы)\s+([А-Я][а-яё]+(?:-[А-Я][а-яё]+)?\s+[А-Я][а-яё]+)',
            r'(?:книги|произведения|творения)\s+([А-Я][а-яё]+(?:-[А-Я][а-яё]+)?[а-яё]+)',
            r'([А-Я][а-яё]+(?:-[А-Я][а-яё]+)?(?:ов|ев|ин|ский|ц[а-яё]+)?\s+[А-Я][а-яё]+(?:-[А-Я][а-яё]+)?)',
        ]

        for i, pattern in enumerate(author_patterns):
            match = re.search(pattern, text)
            if match:
                author = match.group(1).strip()
                author = re.sub(r'(?:ова|ева|ина|ская|цкого|ого|ему|ым|ою|е)$', '', author)
                logger.info(f"Найден автор по паттерну #{i}: {author}")
                return author
        
        return None
