"""
Пример использования MockLLMProvider для тестирования.

Этот файл демонстрирует как создавать и использовать мок для LLM
с заранее заготовленными ответами.
"""
import asyncio
from core.infrastructure.providers.llm.mock_provider import MockLLMProvider, MockLLMConfig
from core.models.types.llm_types import LLMRequest


async def test_basic_usage():
    """Базовое использование MockLLMProvider."""
    print("=" * 60)
    print("Тест 1: Базовое использование")
    print("=" * 60)
    
    # Создаем mock LLM
    mock_llm = MockLLMProvider()
    await mock_llm.initialize()
    
    # Регистрируем ответы на конкретные вопросы
    mock_llm.register_response("привет", "Привет! Как я могу помочь вам сегодня?")
    mock_llm.register_response("как дела", "Отлично! Спасибо что спросили.")
    mock_llm.register_response("пока", "До свидания! Хорошего дня!")
    
    # Тестируем
    request = LLMRequest(prompt="привет, как ты?")
    response = await mock_llm.generate(request)
    print(f"Запрос: {request.prompt}")
    print(f"Ответ: {response.content}")
    assert "Привет!" in response.content
    
    # Проверяем историю вызовов
    history = mock_llm.get_call_history()
    print(f"Всего вызовов: {len(history)}")
    print(f"Последний вызов: {history[-1]['prompt']}")
    
    await mock_llm.shutdown()
    print("✓ Тест пройден\n")


async def test_regex_patterns():
    """Использование regex паттернов."""
    print("=" * 60)
    print("Тест 2: Regex паттерны")
    print("=" * 60)
    
    mock_llm = MockLLMProvider()
    await mock_llm.initialize()
    
    # Регистрируем regex паттерны
    mock_llm.register_regex_response(r"\d+", "Вы ввели число: {}")
    mock_llm.register_regex_response(r"что такое \w+", "Это интересный вопрос о {}")
    
    # Тестируем с числами
    request = LLMRequest(prompt="Сколько будет 2 + 2? Ответ: 4")
    response = await mock_llm.generate(request)
    print(f"Запрос: {request.prompt}")
    print(f"Ответ: {response.content}")
    
    await mock_llm.shutdown()
    print("✓ Тест пройден\n")


async def test_exact_matching():
    """Точное совпадение промптов."""
    print("=" * 60)
    print("Тест 3: Точное совпадение")
    print("=" * 60)
    
    mock_llm = MockLLMProvider()
    await mock_llm.initialize()
    
    # Регистрируем точные совпадения
    mock_llm.register_exact_response("ключ1", "Значение 1")
    mock_llm.register_exact_response("ключ2", "Значение 2")
    
    # Точное совпадение
    request = LLMRequest(prompt="ключ1")
    response = await mock_llm.generate(request)
    print(f"Запрос: '{request.prompt}'")
    print(f"Ответ: {response.content}")
    assert response.content == "Значение 1"
    
    # Неполное совпадение не сработает для exact
    request = LLMRequest(prompt="ключ1 дополнительный текст")
    response = await mock_llm.generate(request)
    print(f"Запрос: '{request.prompt}'")
    print(f"Ответ (default): {response.content}")
    
    await mock_llm.shutdown()
    print("✓ Тест пройден\n")


async def test_batch_registration():
    """Массовая регистрация ответов."""
    print("=" * 60)
    print("Тест 4: Массовая регистрация")
    print("=" * 60)
    
    mock_llm = MockLLMProvider()
    await mock_llm.initialize()
    
    # Массовая регистрация
    responses = {
        "доброе утро": "Доброе утро! Желаю продуктивного дня!",
        "добрый вечер": "Добрый вечер! Как прошел ваш день?",
        "спасибо": "Пожалуйста! Всегда рад помочь.",
        "помоги": "Конечно! Что именно вас интересует?"
    }
    mock_llm.register_responses_batch(responses)
    
    # Тестируем
    request = LLMRequest(prompt="доброе утро!")
    response = await mock_llm.generate(request)
    print(f"Запрос: {request.prompt}")
    print(f"Ответ: {response.content}")
    
    await mock_llm.shutdown()
    print("✓ Тест пройден\n")


async def test_strict_mode():
    """Строгий режим - ошибка если ответ не найден."""
    print("=" * 60)
    print("Тест 5: Строгий режим")
    print("=" * 60)
    
    config = MockLLMConfig(strict_mode=True, default_response="Не должно использоваться")
    mock_llm = MockLLMProvider(config=config)
    await mock_llm.initialize()
    
    mock_llm.register_response("известный вопрос", "Известный ответ")
    
    # Этот запрос сработает
    request = LLMRequest(prompt="известный вопрос")
    response = await mock_llm.generate(request)
    print(f"Запрос: {request.prompt}")
    print(f"Ответ: {response.content}")
    
    # Этот запрос вызовет ошибку
    try:
        request = LLMRequest(prompt="неизвестный вопрос")
        response = await mock_llm.generate(request)
        print("ERROR: Должна была быть ошибка!")
    except Exception as e:
        print(f"✓ Ошибка как ожидалось: {type(e).__name__}")
    
    await mock_llm.shutdown()
    print("✓ Тест пройден\n")


async def test_default_response():
    """Ответ по умолчанию для всех незаregistered запросов."""
    print("=" * 60)
    print("Тест 6: Ответ по умолчанию")
    print("=" * 60)
    
    config = MockLLMConfig(
        default_response="Я не понимаю этот вопрос, но это тестовый ответ.",
        strict_mode=False
    )
    mock_llm = MockLLMProvider(config=config)
    await mock_llm.initialize()
    
    mock_llm.register_response("специальный", "Специальный ответ")
    
    # Специальный ответ
    request = LLMRequest(prompt="специальный вопрос")
    response = await mock_llm.generate(request)
    print(f"Запрос: {request.prompt}")
    print(f"Ответ: {response.content}")
    
    # Ответ по умолчанию
    request = LLMRequest(prompt="случайный вопрос")
    response = await mock_llm.generate(request)
    print(f"Запрос: {request.prompt}")
    print(f"Ответ (default): {response.content}")
    assert "Я не понимаю" in response.content
    
    await mock_llm.shutdown()
    print("✓ Тест пройден\n")


async def test_agent_reuse():
    """Пример переиспользования ответов агентом."""
    print("=" * 60)
    print("Тест 7: Переиспользование ответов агентом")
    print("=" * 60)
    
    # Создаем mock LLM
    mock_llm = MockLLMProvider()
    await mock_llm.initialize()
    
    # Предзагружаем ответы которые будет использовать агент
    agent_responses = {
        "проверить статус": "Статус системы: ОК. Все сервисы работают нормально.",
        "перезагрузить": "Команда на перезагрузку отправлена. Ожидайте подтверждения.",
        "показать логи": "Последние логи:\n[INFO] Система запущена\n[INFO] Все проверки пройдены",
        r"анализ.*ошибк": "Анализ показал: ошибок не обнаружено."
    }
    mock_llm.register_responses_batch(agent_responses)
    
    # Симуляция работы агента
    async def agent_step(question: str) -> str:
        """Шаг агента который использует LLM."""
        request = LLMRequest(prompt=question)
        response = await mock_llm.generate(request)
        return response.content
    
    # Агент выполняет несколько шагов
    questions = [
        "проверить статус системы",
        "нужно перезагрузить сервер",
        "покажи логи за последний час",
        "проведи анализ ошибок"
    ]
    
    for question in questions:
        answer = await agent_step(question)
        print(f"Агент спросил: {question}")
        print(f"LLM ответил: {answer[:60]}...")
        print("-" * 40)
    
    # Проверяем что все вызовы были залогированы
    history = mock_llm.get_call_history()
    print(f"\nВсего шагов агента: {len(history)}")
    print("История вызовов доступна для анализа и тестов")
    
    await mock_llm.shutdown()
    print("✓ Тест пройден\n")


async def main():
    """Запуск всех тестов."""
    print("\n" + "=" * 60)
    print("MOCK LLM PROVIDER - ПРИМЕРЫ ИСПОЛЬЗОВАНИЯ")
    print("=" * 60 + "\n")
    
    await test_basic_usage()
    await test_regex_patterns()
    await test_exact_matching()
    await test_batch_registration()
    await test_strict_mode()
    await test_default_response()
    await test_agent_reuse()
    
    print("=" * 60)
    print("ВСЕ ТЕСТЫ ПРОЙДЕНЫ ✓")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
