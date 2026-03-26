import asyncio
import sys
sys.path.insert(0, r'c:\Users\Алексей\Documents\WORK\Agent_v5')

from core.models.types.llm_types import LLMRequest

async def test_llm_request_stop_sequences():
    """Тестирование LLMRequest с полем stop_sequences"""
    
    # Создаем LLMRequest с полем stop_sequences
    request = LLMRequest(
        prompt="Привет! Кратко расскажи о себе.",
        max_tokens=10,
        temperature=0.7,
        stop_sequences=["END", "STOP", "CONCLUSION"]
    )
    
    
    # Проверяем, что поле stop_sequences корректно установлено
    assert request.stop_sequences == ["END", "STOP", "CONCLUSION"], f"Ожидалось ['END', 'STOP', 'CONCLUSION'], получено {request.stop_sequences}"
    
    # Проверяем, что можно создать LLMRequest без stop_sequences (должно быть None по умолчанию)
    request_default = LLMRequest(
        prompt="Привет! Кратко расскажи о себе.",
        max_tokens=10,
        temperature=0.7
    )
    
    assert request_default.stop_sequences is None, f"Ожидалось None, получено {request_default.stop_sequences}"
    

# Запускаем тест
asyncio.run(test_llm_request_stop_sequences())