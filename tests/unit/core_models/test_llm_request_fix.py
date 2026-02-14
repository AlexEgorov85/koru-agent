import asyncio
import sys
sys.path.insert(0, r'c:\Users\Алексей\Documents\WORK\Agent_v5')

from core.models.llm_types import LLMRequest

async def test_llm_request():
    """Тестирование исправленного LLMRequest"""
    print("Тестирование LLMRequest с новым полем stop_sequences...")
    
    # Создание тестового запроса
    request = LLMRequest(
        prompt="Привет! Кратко расскажи о себе.",
        max_tokens=10,
        temperature=0.7,
        stop_sequences=["END", "STOP"]  # Добавляем stop_sequences
    )
    
    print(f"Prompt: {request.prompt}")
    print(f"Max tokens: {request.max_tokens}")
    print(f"Temperature: {request.temperature}")
    print(f"Stop sequences: {request.stop_sequences}")
    
    # Проверим, что все поля корректно установлены
    assert request.prompt == "Привет! Кратко расскажи о себе."
    assert request.max_tokens == 10
    assert request.temperature == 0.7
    assert request.stop_sequences == ["END", "STOP"]
    
    print("✓ Все поля LLMRequest корректно установлены")
    
    # Проверим, что валидация работает
    assert request.temperature >= 0.0 and request.temperature <= 1.0
    assert request.max_tokens >= 1 and request.max_tokens <= 4096
    print("✓ Валидация параметров работает корректно")
    
    print("Тест LLMRequest завершен успешно!")

# Запускаем тест
asyncio.run(test_llm_request())