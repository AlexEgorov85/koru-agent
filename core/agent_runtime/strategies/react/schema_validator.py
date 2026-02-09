"""
Валидатор параметров с использованием Pydantic.
ОСОБЕННОСТИ:
- Полная валидация через Pydantic
- Автоматическая коррекция типов данных
- Интеграция с LLMPort для исправления невалидных параметров
- Кэширование схем для производительности
"""
from datetime import datetime
import json
import logging
from typing import Dict, Any, Optional, Type
import uuid
from pydantic import create_model, Field, BaseModel, ValidationError
from core.system_context.base_system_contex import BaseSystemContext
logger = logging.getLogger(__name__)

class SchemaValidator:
    """
    Валидатор параметров для capability с использованием Pydantic.
    """
    
    def __init__(self):
        """Инициализация валидатора."""
        self._capability_schemas: Dict[str, Type[BaseModel]] = {}
        self._fallback_values = {
            "string": "",
            "integer": 0,
            "number": 0.0,
            "boolean": False,
            "array": [],
            "object": {}
        }
    
    def validate_parameters(
        self,
        capability: Any,
        raw_params: Dict[str, Any],
        context: str,
        system_context: BaseSystemContext = None
    ) -> Dict[str, Any]:
        """
        Валидирует и при необходимости корректирует параметры.
        ПРОЦЕДУРА:
        1. Получение схемы валидации для capability
        2. Валидация через Pydantic
        3. При ошибках - автоматическое исправление
        4. При сложных ошибках - корректировка через LLM
        """

        """ДОБАВИТЬ: Детальное логирование для отладки"""
        logger.debug(f"Валидация параметров для capability '{capability.name}'")
        logger.debug(f"Исходные параметры: {json.dumps(raw_params, indent=2, ensure_ascii=False)}")

        capability_name = capability.name
        schema_definition = getattr(capability, 'parameters_schema', None)
        
        if not schema_definition:
            logger.debug(f"Схема отсутствует для capability '{capability_name}', пропускаем валидацию")
            return raw_params.copy() if raw_params else {}
        
        # Получение схемы валидации
        validation_model = self.get_capability_model(capability_name, schema_definition)
        
        if not validation_model:
            logger.warning(f"Не удалось создать модель валидации для '{capability_name}'")
            return raw_params.copy() if raw_params else {}
        
        try:
            # Прямая валидация
            return self._direct_validation(validation_model, raw_params)
            
        except ValidationError as e:
            logger.warning(f"Ошибка валидации параметров для '{capability_name}': {str(e)}")
            # Автоматическое исправление
            corrected_params = self._auto_correct_parameters(validation_model, raw_params, e)
            
            try:
                # Повторная валидация исправленных параметров
                return self._direct_validation(validation_model, corrected_params)
                
            except ValidationError as e2:
                logger.warning(f"Автоматическое исправление не удалось для '{capability_name}'")
                
                # Корректировка через LLM при наличии system_context
                if system_context:
                    corrected_params = self._llm_correct_parameters(
                        system_context=system_context,
                        capability_name=capability_name,
                        capability_schema=schema_definition,
                        invalid_params=raw_params,
                        validation_errors=e2.errors(),
                        context=context
                    )
                    
                    if corrected_params:
                        try:
                            return self._direct_validation(validation_model, corrected_params)
                        except ValidationError:
                            logger.error(f"Даже LLM-корректировка не помогла для '{capability_name}'")
                
                # Fallback - возвращаем исходные параметры
                return raw_params.copy() if raw_params else {}
    
    def get_capability_model(self, capability_name: str, schema_definition: Dict[str, Any]) -> Optional[Type[BaseModel]]:
        """
        Создает или возвращает существующую Pydantic модель для capability.
        """
        if not schema_definition or not isinstance(schema_definition, dict):
            logger.warning(f"Пустая или некорректная схема для capability '{capability_name}'")
            return None
        
        if capability_name in self._capability_schemas:
            return self._capability_schemas[capability_name]
        
        try:
            properties = schema_definition.get("properties", {})
            required_fields = schema_definition.get("required", [])
            
            # Создание полей для модели
            fields = {}
            for field_name, field_info in properties.items():
                field_type = self._get_python_type(field_info)
                default_value = self._get_default_value(field_info, field_name, required_fields)
                description = field_info.get("description", "")
                fields[field_name] = (field_type, Field(default=default_value, description=description))
            
            # Создание модели
            model_name = f"{capability_name.replace('.', '_')}_Params"
            validation_model = create_model(model_name, **fields)
            self._capability_schemas[capability_name] = validation_model
            
            return validation_model
            
        except Exception as e:
            logger.error(f"Ошибка создания модели валидации для '{capability_name}': {str(e)}")
            return None
    
    def _get_python_type(self, field_info: Dict[str, Any]) -> type:
        """Определяет Python тип из JSON схемы."""
        field_type = field_info.get("type", "string")
        format_spec = field_info.get("format", "")
        
        # Поддержка специальных форматов
        if format_spec == "date":
            return datetime.date
        elif format_spec == "datetime":
            return datetime.datetime
        elif format_spec == "uuid":
            return uuid.UUID


        if field_type in ["string", "str"]:
            return str
        elif field_type in ["integer", "int"]:
            return int
        elif field_type in ["number", "float"]:
            return float
        elif field_type in ["boolean", "bool"]:
            return bool
        elif field_type in ["array", "list"]:
            return list
        elif field_type in ["object", "dict"]:
            return dict
        else:
            return str
    
    def _get_default_value(self, field_info: Dict[str, Any], field_name: str, required_fields: list) -> Any:
        """Определяет значение по умолчанию для поля."""
        if field_name in required_fields:
            return ...
        
        # Попытка получить значение по умолчанию из схемы
        default = field_info.get("default")
        if default is not None:
            return default
        
        # Значение по умолчанию в зависимости от типа
        field_type = field_info.get("type", "string")
        return self._fallback_values.get(field_type, None)
    
    def _direct_validation(
        self,
        validation_model: Type[BaseModel],
        raw_params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Выполняет прямую валидацию параметров через Pydantic."""
        validated_obj = validation_model(**raw_params)
        return validated_obj.model_dump()


    def _auto_correct_parameters(
        self,
        validation_model: Type[BaseModel],
        raw_params: Dict[str, Any],
        validation_error: ValidationError
    ) -> Dict[str, Any]:
        """
        Автоматически исправляет типы данных в параметрах для соответствия схеме.
        УЛУЧШЕНИЯ:
        1. Обработка пустых значений для числовых типов
        2. Поддержка Optional типов
        3. Более гибкая логика преобразований
        4. Детальное логирование для отладки
        """
        corrected = raw_params.copy()
        errors = validation_error.errors()
        
        for error in errors:
            # Извлечение информации об ошибке
            field_path = error.get("loc", [])
            if not field_path:
                continue
                
            field_name = str(field_path[-1])  # Гарантируем строковое представление
            if field_name not in corrected:
                continue
                
            # Получение информации о поле из модели
            field = validation_model.model_fields.get(field_name)
            if not field:
                continue
                
            expected_type = field.annotation
            required = field_name in validation_model.model_fields_set
            
            # Текущее значение для исправления
            actual_value = corrected[field_name]
            original_value = actual_value  # Для логирования
            
            try:
                # ======================================================
                # СПЕЦИАЛЬНАЯ ОБРАБОТКА ПУСТЫХ ЗНАЧЕНИЙ
                # ======================================================
                is_empty_value = (
                    actual_value is None or 
                    (isinstance(actual_value, str) and actual_value.strip() == "")
                )
                
                if is_empty_value:
                    # Для Optional полей используем None
                    if self._is_optional_type(expected_type):
                        corrected[field_name] = None
                        logger.debug(f"Пустое значение для Optional поля '{field_name}' -> None")
                    # Для обязательных полей используем значение по умолчанию
                    elif not required and field.default is not ...:
                        corrected[field_name] = field.default
                        logger.debug(f"Пустое значение для необязательного поля '{field_name}' -> значение по умолчанию")
                    # Для обязательных полей без значения по умолчанию - оставляем как есть (валидация провалится)
                    else:
                        logger.warning(f"Обнаружено пустое значение для обязательного поля '{field_name}', исправление невозможно")
                    continue
                
                # ======================================================
                # ОБРАБОТКА ЧИСЛОВЫХ ТИПОВ
                # ======================================================
                if self._is_int_type(expected_type):
                    if isinstance(actual_value, str):
                        # Удаляем пробелы и проверяем на пустоту
                        stripped = actual_value.strip()
                        if stripped == "":
                            # Для Optional[int] устанавливаем None
                            if self._is_optional_type(expected_type):
                                corrected[field_name] = None
                                logger.debug(f"Пустая строка для поля '{field_name}' -> None (Optional[int])")
                            else:
                                # Используем 0 как fallback для обязательных полей
                                corrected[field_name] = 0
                                logger.warning(f"Пустая строка для обязательного поля '{field_name}' -> 0 (fallback)")
                        elif stripped.isdigit():
                            corrected[field_name] = int(stripped)
                        else:
                            # Попытка извлечь число из строки
                            import re
                            number_match = re.search(r'-?\d+', stripped)
                            if number_match:
                                corrected[field_name] = int(number_match.group())
                                logger.debug(f"Извлечено число из строки для '{field_name}': {number_match.group()}")
                            else:
                                # Для Optional[int] устанавливаем None
                                if self._is_optional_type(expected_type):
                                    corrected[field_name] = None
                                    logger.debug(f"Невозможно преобразовать строку в число для '{field_name}' -> None (Optional[int])")
                                else:
                                    # Используем 0 как fallback
                                    corrected[field_name] = 0
                                    logger.warning(f"Невозможно преобразовать строку '{actual_value}' в число для поля '{field_name}' -> 0 (fallback)")
                    elif isinstance(actual_value, float):
                        corrected[field_name] = int(actual_value)
                    elif isinstance(actual_value, bool):
                        corrected[field_name] = 1 if actual_value else 0
                
                elif self._is_float_type(expected_type):
                    if isinstance(actual_value, str):
                        stripped = actual_value.strip()
                        if stripped == "":
                            if self._is_optional_type(expected_type):
                                corrected[field_name] = None
                            else:
                                corrected[field_name] = 0.0
                        else:
                            try:
                                # Заменяем запятую на точку для дробных чисел
                                cleaned = stripped.replace(',', '.')
                                corrected[field_name] = float(cleaned)
                            except (ValueError, TypeError):
                                if self._is_optional_type(expected_type):
                                    corrected[field_name] = None
                                else:
                                    corrected[field_name] = 0.0
                
                # ======================================================
                # ОБРАБОТКА БУЛЕВЫХ ЗНАЧЕНИЙ
                # ======================================================
                elif self._is_bool_type(expected_type):
                    if isinstance(actual_value, str):
                        normalized = actual_value.strip().lower()
                        bool_map = {
                            "true": True, "1": True, "да": True, "yes": True, "y": True, "on": True, "вкл": True,
                            "false": False, "0": False, "нет": False, "no": False, "n": False, "off": False, "выкл": False
                        }
                        corrected[field_name] = bool_map.get(normalized, bool(normalized))
                    elif isinstance(actual_value, (int, float)):
                        corrected[field_name] = bool(actual_value)
                
                # ======================================================
                # ОБРАБОТКА СПИСКОВ И СЛОВАРЕЙ
                # ======================================================
                elif self._is_list_type(expected_type):
                    if isinstance(actual_value, str):
                        try:
                            # Попытка парсинга JSON
                            import json
                            parsed = json.loads(actual_value)
                            if isinstance(parsed, list):
                                corrected[field_name] = parsed
                            else:
                                # Если не список, создаем список из одного элемента
                                corrected[field_name] = [parsed]
                        except json.JSONDecodeError:
                            # Разделение по запятым как fallback
                            corrected[field_name] = [item.strip() for item in actual_value.split(',') if item.strip()]
                
                elif self._is_dict_type(expected_type):
                    if isinstance(actual_value, str):
                        try:
                            import json
                            parsed = json.loads(actual_value)
                            if isinstance(parsed, dict):
                                corrected[field_name] = parsed
                        except json.JSONDecodeError:
                            pass  # Оставляем исходное значение
                
                # ======================================================
                # ЛОГИРОВАНИЕ ИЗМЕНЕНИЙ
                # ======================================================
                if corrected[field_name] != original_value:
                    logger.debug(
                        f"Автоматическое исправление параметра '{field_name}': "
                        f"'{original_value}' ({type(original_value).__name__}) -> "
                        f"'{corrected[field_name]}' ({type(corrected[field_name]).__name__})"
                    )
                    
            except (ValueError, TypeError) as e:
                logger.debug(f"Не удалось автоматически исправить параметр {field_name}: {str(e)}")
                # Для Optional типов пытаемся установить None
                if self._is_optional_type(expected_type):
                    corrected[field_name] = None
                    logger.debug(f"Установлено None для Optional поля '{field_name}' после ошибки преобразования")
        
        return corrected

    def _is_optional_type(self, field_type: type) -> bool:
        """Проверяет, является ли тип Optional или Union с None."""
        from typing import Optional, Union, get_origin, get_args
        
        # Проверка для Optional[type]
        if get_origin(field_type) is Union:
            args = get_args(field_type)
            return type(None) in args
        
        # Проверка для typing.Optional
        return field_type == Optional or field_type == type(None)

    def _is_int_type(self, field_type: type) -> bool:
        """Проверяет, является ли тип целочисленным."""
        from typing import get_origin
        
        origin = get_origin(field_type) or field_type
        return origin in (int, Optional[int]) or str(origin).endswith("int")

    def _is_float_type(self, field_type: type) -> bool:
        """Проверяет, является ли тип числом с плавающей точкой."""
        from typing import get_origin
        
        origin = get_origin(field_type) or field_type
        return origin in (float, Optional[float]) or str(origin).endswith("float")

    def _is_bool_type(self, field_type: type) -> bool:
        """Проверяет, является ли тип булевым."""
        from typing import get_origin
        
        origin = get_origin(field_type) or field_type
        return origin in (bool, Optional[bool]) or str(origin).endswith("bool")

    def _is_list_type(self, field_type: type) -> bool:
        """Проверяет, является ли тип списком."""
        from typing import List, get_origin
        
        origin = get_origin(field_type) or field_type
        return origin in (list, List, Optional[list], Optional[List])

    def _is_dict_type(self, field_type: type) -> bool:
        """Проверяет, является ли тип словарем."""
        from typing import Dict, get_origin
        
        origin = get_origin(field_type) or field_type
        return origin in (dict, Dict, Optional[dict], Optional[Dict])



    def _llm_correct_parameters(
        self,
        system_context: BaseSystemContext,
        capability_name: str,
        capability_schema: Dict[str, Any],
        invalid_params: Dict[str, Any],
        validation_errors: list,
        context: str
    ) -> Optional[Dict[str, Any]]:
        """
        Корректирует параметры через LLM при ошибках валидации.
        """
        try:
            # Формирование промпта для корректировки
            from .prompts import PARAMETER_CORRECTION_PROMPT
            
            # Форматирование ошибок валидации
            errors_list = []
            for i, error in enumerate(validation_errors, 1):
                field = " -> ".join(str(loc) for loc in error.get('loc', []))
                msg = error.get('msg', 'Неизвестная ошибка')
                errors_list.append(f"{i}. Поле '{field}': {msg}")
            
            errors_str = "\n".join(errors_list) if errors_list else "Нет конкретных ошибок"
            
            prompt = PARAMETER_CORRECTION_PROMPT.format(
                context=context,
                goal=system_context.session.get_goal() if hasattr(system_context, 'session') else "Неизвестная цель",
                capability_name=capability_name,
                invalid_params_json=json.dumps(invalid_params, indent=2, ensure_ascii=False),
                errors_list=errors_str,
                schema_json=json.dumps(capability_schema, indent=2, ensure_ascii=False)
            )
            
            # Генерация исправленных параметров
            response = system_context.call_llm_with_params(
                user_prompt=prompt,
                system_prompt="Ты — эксперт по валидации данных и параметров навыков. Исправь параметры для соответствия схеме.",
                output_schema=capability_schema,
                temperature=0.3,
                max_tokens=800,
                output_format="json"
            )
            
            # Обработка результата
            corrected_params = response.content if hasattr(response, 'content') else response
            if not isinstance(corrected_params, dict):
                logger.error("LLM вернул некорректный формат для исправленных параметров")
                return None
            
            logger.info(f"Параметры успешно исправлены для capability '{capability_name}'")
            return corrected_params
            
        except Exception as e:
            logger.error(f"Ошибка корректировки параметров через LLM для '{capability_name}': {str(e)}")
            return None