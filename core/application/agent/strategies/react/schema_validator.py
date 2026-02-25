"""
Валидатор схемы для ReAct стратегии в новой архитектуре
"""
from typing import Dict, Any, Optional
from core.models.data.capability import Capability


class SchemaValidator:
    """Валидатор параметров capability для ReAct стратегии"""
    
    def __init__(self):
        pass
    
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
        if not capability or not raw_params:
            return None

        validated_params = {}

        # Получаем схему параметров из capability
        params_schema = getattr(capability, 'parameters_schema', None) or {}

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
                            continue
                    elif expected_type == 'integer' and not isinstance(param_value, int):
                        try:
                            param_value = int(param_value)
                        except:
                            continue
                    elif expected_type == 'number' and not isinstance(param_value, (int, float)):
                        try:
                            param_value = float(param_value)
                        except:
                            continue
                    elif expected_type == 'boolean' and not isinstance(param_value, bool):
                        try:
                            param_value = bool(param_value)
                        except:
                            continue
                
                validated_params[param_name] = param_value
            elif param_info.get('required', False):
                # Если параметр обязательный, но отсутствует, возвращаем None
                return None
        
        return validated_params