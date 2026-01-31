from datetime import datetime
import json
import logging
import re
from typing import Any, Dict

logger = logging.getLogger(__name__)

def validate_reasoning_result(result: Any) -> Dict[str, Any]:
    """Валидация и нормализация результата рассуждения от LLM.
    
    ОСОБЕННОСТИ:
    - Обработка различных форматов ответа (строка JSON, словарь, объект)
    - Восстановление при частичной валидации
    - Безопасное извлечение значений с fallback
    - Унификация структуры для дальнейшего использования
    
    ВОЗВРАЩАЕТ:
    - Словарь с унифицированной структурой рассуждения
    """
    logger.debug(f"Валидация результата рассуждения, тип: {type(result)}")
    
    # Шаг 1: Преобразование результата в словарь
    reasoning_data = _normalize_reasoning_result(result)
    
    # Шаг 2: Проверка обязательных полей
    validated_result = {
        "analysis": _validate_analysis_section(reasoning_data.get("analysis", {})),
        "recommended_action": _validate_action_section(reasoning_data.get("recommended_action", {})),
        "needs_rollback": _validate_rollback_flag(reasoning_data.get("needs_rollback", False))
    }
    
    # Шаг 3: Валидация типов и значений
    _validate_types_and_values(validated_result)
    
    # Шаг 4: Добавление метаданных для отладки
    validated_result["_validation_metadata"] = {
        "original_keys": list(reasoning_data.keys()) if isinstance(reasoning_data, dict) else [],
        "validation_timestamp": datetime.now().isoformat(),
        "confidence": _calculate_confidence(reasoning_data, validated_result)
    }
    
    logger.debug(f"Результат рассуждения успешно валидирован. Уверенность: {validated_result['_validation_metadata']['confidence']:.2f}")
    return validated_result

def _normalize_reasoning_result(result: Any) -> Dict[str, Any]:
    """Нормализация результата в стандартный словарь."""
    try:
        # Если результат - строка JSON
        if isinstance(result, str):
            try:
                return json.loads(result)
            except json.JSONDecodeError:
                logger.warning("Результат рассуждения не является валидным JSON, пытаемся извлечь данные")
                # Попытка извлечь JSON из текста
                json_match = re.search(r'\{.*\}', result, re.DOTALL)
                if json_match:
                    try:
                        return json.loads(json_match.group())
                    except json.JSONDecodeError:
                        pass
        
        # Если результат - объект Pydantic или подобный
        if hasattr(result, 'model_dump'):
            return result.model_dump()
        if hasattr(result, 'dict'):
            return result.dict()
        
        # Если результат уже словарь
        if isinstance(result, dict):
            return result
        
        # Любые другие случаи
        logger.warning(f"Неожиданный тип результата рассуждения: {type(result)}. Создаем минимально валидную структуру.")
        return {
            "analysis": {
                "current_situation": "Неизвестная ситуация",
                "progress_assessment": "Невозможно оценить",
                "confidence": 0.3,
                "errors_detected": True,
                "consecutive_errors": 1,
                "has_plan": False,
                "plan_status": "unknown",
                "execution_time": 0,
                "no_progress_steps": 0
            },
            "recommended_action": {
                "action_type": "execute_capability",
                "capability_name": "generic.execute",
                "parameters": {"input": "Продолжить выполнение задачи"},
                "reasoning": "fallback из-за некорректного формата результата"
            },
            "needs_rollback": False
        }
    except Exception as e:
        logger.error(f"Ошибка при нормализации результата рассуждения: {str(e)}")
        # Возврат безопасного fallback
        return {
            "analysis": {
                "current_situation": "Ошибка при обработке результата",
                "progress_assessment": "Невозможно определить",
                "confidence": 0.1,
                "errors_detected": True,
                "consecutive_errors": 1,
                "has_plan": False,
                "plan_status": "unknown"
            },
            "recommended_action": {
                "action_type": "execute_capability",
                "capability_name": "generic.execute",
                "parameters": {"input": "Продолжить выполнение задачи"},
                "reasoning": f"fallback после ошибки нормализации: {str(e)}"
            },
            "needs_rollback": False
        }

def _validate_analysis_section(analysis_data: Any) -> Dict[str, Any]:
    """Валидация секции анализа."""
    if not isinstance(analysis_data, dict):
        logger.warning("Секция анализа не является словарем, создаю fallback")
        return {
            "current_situation": "Неизвестная ситуация",
            "progress_assessment": "Невозможно оценить",
            "confidence": 0.3,
            "errors_detected": True,
            "consecutive_errors": 1,
            "has_plan": False,
            "plan_status": "unknown",
            "execution_time": 0,
            "no_progress_steps": 0
        }
    
    # Обязательные поля с безопасными значениями по умолчанию
    validated = {
        "current_situation": _get_safe_string(analysis_data.get("current_situation", "Неизвестная ситуация"), max_length=500),
        "progress_assessment": _get_safe_string(analysis_data.get("progress_assessment", "Невозможно оценить"), max_length=300),
        "confidence": _get_safe_float(analysis_data.get("confidence", 0.3), min_val=0.0, max_val=1.0),
        "errors_detected": bool(analysis_data.get("errors_detected", False)),
        "consecutive_errors": int(analysis_data.get("consecutive_errors", 0)),
        "has_plan": bool(analysis_data.get("has_plan", False)),
        "plan_status": _get_safe_string(analysis_data.get("plan_status", "unknown"), max_length=50).lower(),
        "execution_time": max(0, int(analysis_data.get("execution_time", 0))),
        "no_progress_steps": max(0, int(analysis_data.get("no_progress_steps", 0)))
    }
    
    # Опциональные поля
    if "context_summary" in analysis_data:
        validated["context_summary"] = _get_safe_string(analysis_data["context_summary"], max_length=1000)
    if "risk_assessment" in analysis_data:
        validated["risk_assessment"] = _get_safe_string(analysis_data["risk_assessment"], max_length=300)
    
    return validated

def _validate_action_section(action_data: Any) -> Dict[str, Any]:
    """Валидация секции рекомендуемого действия."""
    if not isinstance(action_data, dict):
        logger.warning("Секция действия не является словарем, создаю fallback")
        return {
            "action_type": "execute_capability",
            "capability_name": "generic.execute",
            "parameters": {"input": "Продолжить выполнение задачи"},
            "reasoning": "fallback из-за некорректного формата секции действия"
        }
    
    # Определение типа действия с валидацией
    action_type = _get_safe_string(action_data.get("action_type", "execute_capability"), max_length=50).lower()
    valid_action_types = ["execute_capability", "create_plan", "update_plan", "use_plan", "stop", "rollback"]
    if action_type not in valid_action_types:
        logger.warning(f"Некорректный тип действия '{action_type}', использую fallback")
        action_type = "execute_capability"
    
    # Базовая структура действия
    validated = {
        "action_type": action_type,
        "reasoning": _get_safe_string(action_data.get("reasoning", f"Выбрано действие: {action_type}"), max_length=500)
    }
    
    # Специфические поля для разных типов действий
    if action_type == "execute_capability":
        capability_name = _get_safe_string(action_data.get("capability_name", "generic.execute"), max_length=100)
        validated["capability_name"] = capability_name.lower()
        validated["parameters"] = _validate_parameters(action_data.get("parameters", {}))
    
    elif action_type in ["create_plan", "update_plan", "use_plan"]:
        validated["plan_strategy"] = _get_safe_string(action_data.get("plan_strategy", "iterative"), max_length=50)
        if "plan_id" in action_data:
            validated["plan_id"] = _get_safe_string(action_data["plan_id"], max_length=100)
    
    elif action_type == "rollback":
        validated["rollback_steps"] = max(1, min(10, int(action_data.get("rollback_steps", 1))))
    
    return validated

def _validate_rollback_flag(rollback_flag: Any) -> bool:
    """Валидация флага необходимости отката."""
    if isinstance(rollback_flag, bool):
        return rollback_flag
    if isinstance(rollback_flag, str):
        return rollback_flag.lower() in ["true", "yes", "1", "need_rollback", "required"]
    if isinstance(rollback_flag, (int, float)):
        return bool(rollback_flag)
    logger.warning(f"Некорректное значение для needs_rollback: {rollback_flag}, использую False")
    return False

def _validate_parameters(params: Any) -> Dict[str, Any]:
    """Валидация параметров capability."""
    if not isinstance(params, dict):
        logger.warning("Параметры не являются словарем, возвращаю пустой словарь")
        return {}
    
    validated = {}
    for key, value in params.items():
        safe_key = _get_safe_string(str(key), max_length=50)
        # Ограничиваем сложность значений
        if isinstance(value, (str, int, float, bool)):
            validated[safe_key] = value
        elif isinstance(value, (list, dict)):
            # Ограничиваем размер сложных структур
            validated[safe_key] = json.loads(json.dumps(value)[:500] + "...") if json.dumps(value) else {}
        else:
            validated[safe_key] = str(value)[:200]
    
    return validated

def _validate_types_and_values(result: Dict[str, Any]):
    """Финальная валидация типов и значений в результате."""
    # Проверка диапазонов числовых значений
    confidence = result["analysis"]["confidence"]
    if not (0.0 <= confidence <= 1.0):
        logger.warning(f"Некорректное значение confidence: {confidence}, исправляю на 0.5")
        result["analysis"]["confidence"] = 0.5
    
    # Коррекция статуса плана
    plan_status = result["analysis"]["plan_status"]
    valid_statuses = ["none", "active", "in_progress", "completed", "failed", "unknown"]
    if plan_status not in valid_statuses:
        logger.warning(f"Некорректный статус плана: {plan_status}, исправляю на 'unknown'")
        result["analysis"]["plan_status"] = "unknown"
    
    # Проверка consistency: если нужны откат, должен быть план
    if result["needs_rollback"] and not result["analysis"]["has_plan"]:
        logger.warning("Указано needs_rollback=True, но has_plan=False. Корректирую.")
        result["analysis"]["has_plan"] = True

def _get_safe_string(value: Any, max_length: int = 200) -> str:
    """Получение безопасной строки с ограничением длины."""
    try:
        text = str(value).strip()
        return text[:max_length] if len(text) > max_length else text
    except Exception as e:
        logger.warning(f"Ошибка при преобразовании в строку: {str(e)}")
        return ""

def _get_safe_float(value: Any, min_val: float = 0.0, max_val: float = 1.0) -> float:
    """Получение безопасного числа с плавающей точкой в заданном диапазоне."""
    try:
        num = float(value)
        return max(min_val, min(max_val, num))
    except (TypeError, ValueError, Exception) as e:
        logger.warning(f"Ошибка при преобразовании в float: {str(e)}, возвращаю {min_val}")
        return min_val

def _calculate_confidence(original_data: Dict[str, Any], validated_data: Dict[str, Any]) -> float:
    """Расчет уверенности в валидированном результате."""
    base_confidence = validated_data["analysis"]["confidence"]
    penalty = 0.0
    
    # Штраф за использование fallback значений
    if "_validation_metadata" in validated_data:
        if "original_keys" in validated_data["_validation_metadata"]:
            original_keys = validated_data["_validation_metadata"]["original_keys"]
            required_keys = ["analysis", "recommended_action", "needs_rollback"]
            missing_keys = [key for key in required_keys if key not in original_keys]
            penalty += len(missing_keys) * 0.1
    
    # Штраф за некорректные типы
    if original_data != validated_data:
        penalty += 0.15
    
    # Штраф за ошибки в анализе
    if validated_data["analysis"].get("errors_detected", False):
        penalty += 0.2
    
    final_confidence = max(0.1, min(1.0, base_confidence - penalty))
    return final_confidence