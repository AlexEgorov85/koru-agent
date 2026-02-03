"""Тестирование расширенной функциональности LLMResponse"""

from infrastructure.gateways.llm_providers.base_provider import LLMResponse, LLMDecisionType
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
    
