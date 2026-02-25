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
        logger = logging.getLogger(__name__)
        
        if not capability or not raw_params:
            return None

        # Получаем схему из кэша по имени capability
        params_schema = self.get_capability_schema(capability.name)
        
        logger.info(f"validate_parameters: capability={capability.name}, raw_params={raw_params}, params_schema={params_schema}")
        
        # Если схема не найдена в кэше, пробуем получить из meta capability
        if not params_schema:
            # Пытаемся получить из meta (если там есть contract_schema)
            params_schema = capability.meta.get('contract_schema', {})
            logger.debug(f"Схема не найдена в кэше, пробуем из meta: {params_schema}")
        
        # Если схема всё ещё пуста, создаём минимальную схему с "input"
        if not params_schema:
            # Дефолтная схема: требуется поле "input" типа string
            params_schema = {
                "input": {"type": "string", "required": True}
            }
            logger.debug(f"Используем дефолтную схему: {params_schema}")

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
                            logger.warning(f"Не удалось преобразовать параметр {param_name} к строке")
                            continue
                    elif expected_type == 'integer' and not isinstance(param_value, int):
                        try:
                            param_value = int(param_value)
                        except:
                            logger.warning(f"Не удалось преобразовать параметр {param_name} к integer")
                            continue
                    elif expected_type == 'number' and not isinstance(param_value, (int, float)):
                        try:
                            param_value = float(param_value)
                        except:
                            logger.warning(f"Не удалось преобразовать параметр {param_name} к number")
                            continue
                    elif expected_type == 'boolean' and not isinstance(param_value, bool):
                        try:
                            param_value = bool(param_value)
                        except:
                            logger.warning(f"Не удалось преобразовать параметр {param_name} к boolean")
                            continue

                validated_params[param_name] = param_value
                logger.debug(f"Валидирован параметр {param_name}={param_value}")
            elif param_info.get('required', False):
                # Если параметр обязательный, но отсутствует, возвращаем None
                logger.warning(f"Обязательный параметр {param_name} отсутствует")
                return None

        logger.info(f"validate_parameters: result={validated_params}")
        return validated_params