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

        УНИВЕРСАЛЬНЫЙ ПОДХОД:
        - Используем схему из контракта capability
        - Проверяем наличие обязательных параметров
        - Возвращаем все параметры как есть (плоская структура)

        ARGS:
        - capability: объект capability для валидации
        - raw_params: необработанные параметры
        - context: дополнительный контекст для валидации

        RETURNS:
        - Валидированные параметры или None, если валидация не удалась
        """
        logger = logging.getLogger(__name__)

        # [PARAM_DEBUG] 1. Входные параметры
        print(f"[PARAM_DEBUG] validate_parameters: capability={capability.name}", flush=True)
        print(f"[PARAM_DEBUG] raw_params={raw_params}", flush=True)

        if not capability or not raw_params:
            print(f"[PARAM_DEBUG] capability или raw_params пустые", flush=True)
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

        # Если схема всё ещё пуста — пропускаем валидацию и возвращаем как есть
        if not params_schema_dict:
            logger.debug(f"Схема не найдена для {capability.name}, возвращаем параметры как есть")
            return raw_params

        # УНИВЕРСАЛЬНАЯ ВАЛИДАЦИЯ:
        # 1. Проверяем обязательные параметры
        # 2. Возвращаем все параметры (включая опциональные)
        validated_params = {}
        has_error = False

        for param_name, param_info in params_schema_dict.items():
            if param_name in raw_params:
                param_value = raw_params[param_name]
                
                # Простая валидация типов
                expected_type = param_info.get('type') if isinstance(param_info, dict) else param_info
                if expected_type:
                    converted_value = self._convert_type(param_name, param_value, expected_type, logger, None)
                    if converted_value is not None:
                        validated_params[param_name] = converted_value
                    elif isinstance(param_info, dict) and param_info.get('required', False):
                        logger.error(f"Обязательный параметр {param_name} имеет неверный тип")
                        has_error = True
                    else:
                        validated_params[param_name] = param_value
                else:
                    validated_params[param_name] = param_value
                    
            elif isinstance(param_info, dict) and param_info.get('required', False):
                logger.error(f"Обязательный параметр {param_name} отсутствует")
                has_error = True

        print(f"[PARAM_DEBUG] validated_params={validated_params}", flush=True)

        if has_error:
            return None
            
        logger.info(f"✅ Параметры валидированы для {capability.name}: {validated_params}")
        return validated_params
    
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
            if result:
                result.add_warning(f"Не удалось преобразовать параметр {param_name} к {expected_type}: {e}")
            return None
