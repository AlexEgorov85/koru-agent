"""Валидатор решений LLM"""
from typing import Dict, Any, Optional, List
from pydantic import BaseModel
import json
import re
import asyncio


class ValidationResult:
    """Результат валидации"""
    def __init__(self, is_valid: bool, parsed_data: Optional[Dict[str, Any]] = None, 
                 error: Optional[str] = None, suggested_action: Optional[str] = None):
        self.is_valid = is_valid
        self.parsed_data = parsed_data
        self.error = error
        self.suggested_action = suggested_action


class LLMDecisionValidator:
    """Валидатор решений LLM с многоуровневым подходом"""
    
    def __init__(self):
        self.json_extract_patterns = [
            r'\{.*\}',  # Любой JSON объект
            r'\[.*\]', # Любой JSON массив
            r'```(?:json)?\s*(\{.*?\})\s*```',  # JSON в блоке кода
            r'```(?:json)?\s*(\[.*?\])\s*```',  # Массив в блоке кода
        ]
    
    async def validate(self, raw_text: str, schema: Dict[str, Any], 
                       is_truncated: bool = False, max_retries: int = 2) -> ValidationResult:
        """
        Валидация решения от LLM с многоуровневым подходом
        
        Args:
            raw_text: Сырой текст от LLM
            schema: JSON Schema для валидации
            is_truncated: Флаг обрезанного ответа
            max_retries: Максимальное количество попыток исправления
            
        Returns:
            ValidationResult: Результат валидации
        """
        if not raw_text or not raw_text.strip():
            return ValidationResult(
                is_valid=False, 
                error="Пустой ответ от LLM",
                suggested_action="ASK_USER"
            )
        
        # Если ответ обрезан, сначала пробуем восстановить JSON
        if is_truncated:
            recovery_result = await self._validate_truncated_response(raw_text, schema, max_retries)
            if recovery_result:
                return recovery_result
        
        # Этап 1: Прямая валидация
        result = self._try_direct_validation(raw_text, schema)
        if result.is_valid:
            return result
        
        # Этап 2: Извлечение JSON из текста
        extracted_json = self._extract_json(raw_text)
        if extracted_json:
            result = self._try_direct_validation(extracted_json, schema)
            if result.is_valid:
                return result
        
        # Этап 3: Очистка и исправление JSON
        cleaned_json = self._clean_json(raw_text)
        if cleaned_json and cleaned_json != raw_text:
            result = self._try_direct_validation(cleaned_json, schema)
            if result.is_valid:
                return result
        
        # Этап 4: Повторная генерация через LLM (с ограничением попыток)
        if max_retries > 0:
            fixed_response = await self._fix_with_llm(raw_text, schema)
            if fixed_response:
                return await self.validate(fixed_response, schema, False, max_retries - 1)
        
        # Финальный fallback
        return ValidationResult(
            is_valid=False,
            error=f"Не удалось валидировать ответ после {max_retries + 1} попыток. "
                  f"Оригинальный ответ: {raw_text[:200]}...",
            suggested_action="ASK_USER"
        )
    
    def _try_direct_validation(self, text: str, schema: Dict[str, Any]) -> ValidationResult:
        """Попытка прямой валидации JSON"""
        try:
            # Пытаемся распарсить JSON
            parsed = json.loads(text)
            
            # Проверяем соответствие схеме
            self._validate_against_schema(parsed, schema)
            
            return ValidationResult(is_valid=True, parsed_data=parsed)
        except json.JSONDecodeError as e:
            return ValidationResult(is_valid=False, error=f"JSONDecodeError: {str(e)}")
        except Exception as e:
            return ValidationResult(is_valid=False, error=f"SchemaValidationError: {str(e)}")
    
    def _validate_against_schema(self, data: Dict[str, Any], schema: Dict[str, Any]):
        """Валидация данных против JSON Schema"""
        try:
            from jsonschema import validate, ValidationError
            validate(instance=data, schema=schema)
        except ImportError:
            # Если jsonschema не установлен, пропускаем валидацию
            pass
        except Exception as e:
            raise e
    
    def _extract_json(self, text: str) -> Optional[str]:
        """Извлечение JSON из текста с помощью регулярных выражений"""
        for pattern in self.json_extract_patterns:
            matches = re.findall(pattern, text, re.DOTALL)
            for match in matches:
                # Если паттерн захватил содержимое внутри блока кода, берем его
                potential_json = match if isinstance(match, str) else text
                try:
                    # Пробуем распарсить
                    json.loads(potential_json)
                    return potential_json
                except json.JSONDecodeError:
                    # Пробуем парсить захваченную группу, если она есть
                    if isinstance(match, str):
                        try:
                            json.loads(match)
                            return match
                        except json.JSONDecodeError:
                            continue
        return None
    
    def _clean_json(self, text: str) -> Optional[str]:
        """Очистка JSON от лишних символов"""
        # Убираем лишние пробелы и переносы строк
        cleaned = text.strip()
        
        # Если текст начинается с ``` и заканчивается ```, извлекаем содержимое
        if cleaned.startswith('```'):
            end_marker = cleaned.find('```', 3)
            if end_marker != -1:
                cleaned = cleaned[3:end_marker].strip()
                # Убираем указание языка (json)
                if cleaned.lower().startswith('json'):
                    cleaned = cleaned[4:].strip()
        
        # Пробуем завершить обрезанный JSON
        completed_json = self._attempt_json_recovery(cleaned)
        if completed_json:
            return completed_json
        
        return cleaned if cleaned != text.strip() else None
    
    def _is_truncated_json(self, text: str) -> bool:
        """Проверяет, является ли текст обрезанным JSON-объектом"""
        text = text.rstrip()
        
        # Проверяем, заканчивается ли текст на потенциально незавершённый JSON
        if text.endswith(('{', '[', ':', ',', '"')):
            return True
        
        # Подсчитываем количество открывающих и закрывающих скобок
        open_braces = text.count('{')
        close_braces = text.count('}')
        open_brackets = text.count('[')
        close_brackets = text.count(']')
        
        return (open_braces > close_braces) or (open_brackets > close_brackets)
    
    def _attempt_json_recovery(self, text: str) -> Optional[str]:
        """Пытается восстановить обрезанный JSON"""
        if not self._is_truncated_json(text):
            return None
        
        # Пробуем завершить JSON, добавляя закрывающие скобки
        recovered_text = text.rstrip()
        
        # Подсчитываем недостающие закрывающие скобки
        open_braces = recovered_text.count('{')
        close_braces = recovered_text.count('}')
        open_brackets = recovered_text.count('[')
        close_brackets = recovered_text.count(']')
        
        # Добавляем недостающие закрывающие скобки
        while close_braces < open_braces:
            recovered_text += '}'
            close_braces += 1
        
        while close_brackets < open_brackets:
            recovered_text += ']'
            close_brackets += 1
        
        # Проверяем, можно ли распарсить восстановленный JSON
        try:
            json.loads(recovered_text)
            return recovered_text
        except json.JSONDecodeError:
            # Если восстановление не удалось, возвращаем None
            return None
    
    async def _fix_with_llm(self, raw_text: str, schema: Dict[str, Any], llm_provider=None) -> Optional[str]:
        """Использование LLM для исправления структуры"""
        # В реальной реализации это будет использовать LLM для исправления
        # Пока возвращаем None, так как функциональность требует интеграции с LLM
        return None
    
    async def _validate_truncated_response(self, raw_text: str, schema: Dict[str, Any], 
                                         max_retries: int) -> Optional[ValidationResult]:
        """Валидация обрезанного ответа от LLM"""
        # Попытка 1: Восстановление JSON
        recovered = self._attempt_json_recovery(raw_text)
        if recovered:
            result = self._try_direct_validation(recovered, schema)
            if result.is_valid:
                return result
        
        # Возвращаем результат с ошибкой и предложением действий
        return ValidationResult(
            is_valid=False,
            error=f"Ответ LLM был обрезан и не может быть корректно валидирован. "
                  f"Исходный обрезанный текст: {raw_text[-200:]}...",
            suggested_action="ASK_USER"  # Предложить пользователю уточнить
        )


# Глобальный экземпляр валидатора
llm_validator = LLMDecisionValidator()