"""
Фаза валидации: проверка инструмента и параметров перед выполнением.

АРХИТЕКТУРА:
- validate_action(): проверка существования инструмента + валидация параметров
- Возвращает подробную информацию об ошибках для LLM
- Использует Pydantic модели из component.input_contracts
"""

import logging
from typing import Any, Dict, List, Optional, Tuple


from core.models.data.capability import Capability
from core.models.data.execution import ExecutionResult
from core.models.enums.common_enums import ExecutionStatus


class ValidationPhase:
    """
    Фаза валидации действия перед выполнением.
    
    ОТВЕТСТВЕННОСТЬ:
    - Проверка существования инструмента (action_name в available_capabilities)
    - Валидация параметров через Pydantic (input_contracts)
    - Формирование подробного сообщения об ошибке для LLM
    """
    
    def __init__(
        self,
        log: logging.Logger,
        event_bus: Any,
        application_context: Any = None,
    ):
        self.log = log
        self.event_bus = event_bus
        self.application_context = application_context
    
    def validate_action(
        self,
        action_name: str,
        parameters: Dict[str, Any],
        available_capabilities: List[Capability],
    ) -> Tuple[bool, Optional[ExecutionResult]]:
        """
        Валидация действия: инструмент + параметры.
        
        ARGS:
            action_name: имя действия (например, "check_result.vector_search")
            parameters: параметры действия
            available_capabilities: список доступных capability
        
        RETURNS:
            Tuple[bool, Optional[ExecutionResult]]:
            - (True, None) если валидация прошла успешно
            - (False, ExecutionResult с ошибкой) если валидация не прошла
        """
        # 1. Проверка существования инструмента
        valid_names = [cap.name for cap in available_capabilities]
        
        if action_name not in valid_names:
            error_msg = self._build_unknown_tool_error(action_name, valid_names)
            self.log.warning(
                f"⚠️ {error_msg}",
                extra={"event_type": "WARNING"},
            )
            
            result = ExecutionResult(
                status=ExecutionStatus.FAILED,
                error=ValueError(error_msg),
                data={
                    "error_type": "unknown_tool",
                    "message": error_msg,
                    "valid_tools": valid_names[:10],
                }
            )
            return False, result
        
        # 2. Валидация параметров через Pydantic
        if self.application_context:
            validation_result = self._validate_parameters(
                action_name=action_name,
                parameters=parameters,
            )
            
            if not validation_result[0]:  # Ошибка валидации
                error_msg, details = validation_result[1], validation_result[2]
                self.log.warning(
                    f"⚠️ Ошибка валидации параметров для '{action_name}': {error_msg}",
                    extra={"event_type": "WARNING"},
                )
                
                result = ExecutionResult(
                    status=ExecutionStatus.FAILED,
                    error=ValueError(error_msg),
                    data={
                        "error_type": "invalid_parameters",
                        "message": error_msg,
                        "details": details,
                        "action_name": action_name,
                    }
                )
                return False, result
        
        return True, None
    
    def _build_unknown_tool_error(
        self,
        action_name: str,
        valid_names: List[str],
    ) -> str:
        """Формирует подробное сообщение о неизвестном инструменте."""
        # Извлекаем часть до точки для поиска похожих
        tool_prefix = action_name.split('.')[0] if '.' in action_name else action_name
        
        # Ищем похожие инструменты (по началу)
        similar = [name for name in valid_names if name.startswith(tool_prefix) or tool_prefix in name]
        
        error_parts = [
            f"Неизвестный инструмент: '{action_name}'",
            f"",
            f"Доступные инструменты (всего {len(valid_names)}):",
        ]
        
        # Группируем по типам (skill, tool, service, behavior)
        by_type = {}
        for name in valid_names:
            parts = name.split('.')
            if len(parts) >= 2:
                type_prefix = parts[0]
                if type_prefix not in by_type:
                    by_type[type_prefix] = []
                by_type[type_prefix].append(name)
        
        for type_name, names in sorted(by_type.items()):
            error_parts.append(f"  {type_name}: {', '.join(sorted(names))}")
        
        if similar:
            error_parts.append(f"")
            error_parts.append(f"Возможно, вы имели в виду один из этих:")
            for name in similar[:3]:
                error_parts.append(f"  - {name}")
        
        error_parts.append(f"")
        error_parts.append(f"ПОДСКАЗКА: используйте точное имя инструмента из списка выше.")
        
        return "\n".join(error_parts)
    
    def _validate_parameters(
        self,
        action_name: str,
        parameters: Dict[str, Any],
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Валидация параметров через Pydantic модель из input_contracts.
        
        RETURNS:
            Tuple[успех, сообщение_об_ошибке, детали_ошибки]
        """
        try:
            # Получаем компонент для действия
            if not self.application_context:
                return True, "OK", {}  # Нет контекста — пропускаем
            
            # Ищем компонент через application_context
            component = self._resolve_component(action_name)
            if not component:
                return True, "OK", {}  # Компонент не найден — пропускаем (ошибка будет позже)
            
            # Получаем Pydantic модель из input_contracts
            if not hasattr(component, 'input_contracts'):
                return True, "OK", {}
            
            input_contracts = component.input_contracts
            if action_name not in input_contracts:
                # Пробуем найти по имени без типа (например, check_result.vector_search -> vector_search)
                parts = action_name.split('.')
                if len(parts) >= 2:
                    simple_name = parts[1] if len(parts) >= 2 else action_name
                    # Ищем по partial match
                    for cap_name in input_contracts.keys():
                        if simple_name in cap_name:
                            action_name = cap_name
                            break
            
            if action_name in input_contracts:
                model_class = input_contracts[action_name]
                
                # Создаем экземпляр модели (это и есть валидация)
                try:
                    instance = model_class(**parameters)
                    return True, "OK", {"validated_data": str(instance)[:100]}
                except Exception as e:
                    # Извлекаем детали ошибки Pydantic
                    error_details = self._extract_pydantic_errors(e)
                    return False, f"Ошибка валидации параметров: {str(e)[:200]}", error_details
            
            return True, "OK", {}
            
        except Exception as e:
            return False, f"Ошибка валидации: {str(e)}", {"exception": str(e)}
    
    def _resolve_component(self, action_name: str):
        """Разрешение компонента по имени действия."""
        try:
            from core.application_context.application_context import ComponentType
            
            parts = action_name.split('.')
            if len(parts) >= 2:
                type_prefix = parts[0]
                component_name = parts[1].split('.')[0]
                
                type_map = {
                    "skill": ComponentType.SKILL,
                    "tool": ComponentType.TOOL,
                    "service": ComponentType.SERVICE,
                    "behavior": ComponentType.BEHAVIOR,
                }
                
                if type_prefix in type_map:
                    comp_type = type_map[type_prefix]
                    return self.application_context.components.get(comp_type, component_name)
            
            # Ищем во всех реестрах
            if hasattr(self.application_context, 'components'):
                for comp_type in [ComponentType.SKILL, ComponentType.TOOL, ComponentType.SERVICE, ComponentType.BEHAVIOR]:
                    for name, comp in self.application_context.components.all_of_type(comp_type):
                        if name in action_name or action_name in name:
                            return comp
            
            return None
        except Exception:
            return None
    
    def _extract_pydantic_errors(self, e: Exception) -> Dict[str, Any]:
        """Извлечение подробностей ошибки Pydantic."""
        details = {"exception_type": type(e).__name__}
        
        try:
            # Пробуем получить errors() если это Pydantic ValidationError
            if hasattr(e, 'errors'):
                errors = e.errors()
                details['pydantic_errors'] = errors
                
                # Формируем человекочитаемый список ошибок
                human_readable = []
                for error in errors:
                    field = '.'.join(str(loc) for loc in error.get('loc', []))
                    msg = error.get('msg', '')
                    human_readable.append(f"Поле '{field}': {msg}")
                
                details['human_readable'] = human_readable
        except:
            pass
        
        return details
