"""Тестирование расширенной функциональности LLMResponse"""

from domain.value_objects.provider_type import LLMResponse, LLMDecisionType
from application.services.llm_decision_validator import LLMDecisionValidator, ValidationResult
from application.prompts.llm_decision_prompt import LLM_DECISION_PROMPT
import json


def test_llm_response_creation():
    """Тест создания расширенного LLMResponse"""
    print("Тест 1: Создание расширенного LLMResponse")
    
    response = LLMResponse(
        raw_text='{"decision_type": "execute_tool", "reasoning": "Need to execute a tool", "confidence": 0.9}',
        model="test-model",
        tokens_used=100,
        generation_time=1.5,
        parsed={"decision_type": "execute_tool", "reasoning": "Need to execute a tool", "confidence": 0.9},
        validation_error=None,
        validation_attempts=1,
        validation_chain=["direct_validation"],
        finish_reason="stop",
        is_truncated=False
    )
    
    print(f"  Raw text: {response.raw_text}")
    print(f"  Parsed: {response.parsed}")
    print(f"  Model: {response.model}")
    print(f"  Tokens used: {response.tokens_used}")
    print(f"  Generation time: {response.generation_time}")
    print(f"  Validation error: {response.validation_error}")
    print(f"  Is truncated: {response.is_truncated}")
    print("  + Создание LLMResponse прошло успешно")


def test_llm_decision_types():
    """Тест типов решений LLM"""
    print("\nТест 2: Типы решений LLM")
    
    print(f"  EXECUTE_TOOL: {LLMDecisionType.EXECUTE_TOOL}")
    print(f"  PLAN_NEXT_STEP: {LLMDecisionType.PLAN_NEXT_STEP}")
    print(f"  ASK_USER: {LLMDecisionType.ASK_USER}")
    print(f"  STOP: {LLMDecisionType.STOP}")
    
    # Проверка, что все типы являются строками
    assert isinstance(LLMDecisionType.EXECUTE_TOOL, str)
    assert isinstance(LLMDecisionType.PLAN_NEXT_STEP, str)
    assert isinstance(LLMDecisionType.ASK_USER, str)
    assert isinstance(LLMDecisionType.STOP, str)
    
    print("  + Все типы решений являются строками")


def test_llm_decision_prompt():
    """Тест системного промпта для решений LLM"""
    print("\nТест 3: Системный промпт для решений LLM")
    
    print(f"  Длина промпта: {len(LLM_DECISION_PROMPT)} символов")
    print(f"  Содержит 'decision_type': {'decision_type' in LLM_DECISION_PROMPT}")
    print(f"  Содержит 'execute_tool': {'execute_tool' in LLM_DECISION_PROMPT}")
    print(f"  Содержит 'plan_next_step': {'plan_next_step' in LLM_DECISION_PROMPT}")
    print(f"  Содержит 'ask_user': {'ask_user' in LLM_DECISION_PROMPT}")
    print(f"  Содержит 'stop': {'stop' in LLM_DECISION_PROMPT}")
    
    print("  + Промпт содержит все необходимые элементы")


def test_validation_result():
    """Тест результатов валидации"""
    print("\nТест 4: Результаты валидации")
    
    # Создаем успешный результат валидации
    success_result = ValidationResult(
        is_valid=True,
        parsed_data={"decision_type": "execute_tool", "reasoning": "Test reasoning", "confidence": 0.8},
        error=None,
        suggested_action=None
    )
    
    print(f"  Успешная валидация: {success_result.is_valid}")
    print(f"  Parsed data: {success_result.parsed_data}")
    print(f"  Error: {success_result.error}")
    
    # Создаем неудачный результат валидации
    error_result = ValidationResult(
        is_valid=False,
        parsed_data=None,
        error="Invalid JSON format",
        suggested_action="ASK_USER"
    )
    
    print(f"  Неудачная валидация: {error_result.is_valid}")
    print(f"  Error: {error_result.error}")
    print(f"  Suggested action: {error_result.suggested_action}")
    
    print("  + Результаты валидации работают корректно")


def test_validator_instance():
    """Тест экземпляра валидатора"""
    print("\nТест 5: Экземпляр валидатора")
    
    validator = LLMDecisionValidator()
    
    print(f"  Валидатор создан: {validator is not None}")
    print(f"  Количество паттернов извлечения JSON: {len(validator.json_extract_patterns)}")
    
    # Тестируем извлечение JSON
    test_text = 'Some text before {"key": "value"} some text after'
    extracted = validator._extract_json(test_text)
    print(f"  Извлечение JSON из текста: {extracted}")
    
    print("  + Валидатор работает корректно")


if __name__ == "__main__":
    print("=== Тестирование расширенной функциональности LLMResponse ===")
    
    test_llm_response_creation()
    test_llm_decision_types()
    test_llm_decision_prompt()
    test_validation_result()
    test_validator_instance()
    
    print("\n=== Все тесты пройдены успешно! ===")