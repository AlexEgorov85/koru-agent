# Mock LLM Provider - Руководство по использованию

## Описание

MockLLMProvider позволяет создавать мок для LLM с заранее заготовленными ответами, которые агент может переиспользовать в тестах.

## Основные возможности

1. **Регистрация ответов** на конкретные вопросы/паттерны
2. **Поддержка regex** для гибкого matching
3. **Точное совпадение** промптов
4. **Строгий режим** - ошибка если ответ не найден
5. **Ответ по умолчанию** для всех незарегистрированных запросов
6. **История вызовов** для тестирования и отладки

## Быстрый старт

```python
from core.infrastructure.providers.llm.mock_provider import MockLLMProvider
from core.models.types.llm_types import LLMRequest
import asyncio

async def main():
    # Создаем mock LLM
    mock_llm = MockLLMProvider()
    await mock_llm.initialize()
    
    # Регистрируем ответы
    mock_llm.register_response("привет", "Привет! Как дела?")
    mock_llm.register_response("пока", "До свидания!")
    
    # Используем
    request = LLMRequest(prompt="привет, друг!")
    response = await mock_llm.generate(request)
    print(response.content)  # "Привет! Как дела?"
    
    await mock_llm.shutdown()

asyncio.run(main())
```

## Методы регистрации ответов

### 1. register_response() - Substring поиск (по умолчанию)

```python
mock_llm.register_response("статус", "Все системы в норме")

# Сработает на:
# - "проверить статус"
# - "какой статус системы?"
# - "статус пожалуйста"
```

### 2. register_exact_response() - Точное совпадение

```python
mock_llm.register_exact_response("ключ123", "Значение 123")

# Сработает ТОЛЬКО на:
# - "ключ123"
# Не сработает на:
# - "ключ123 дополнительный текст"
```

### 3. register_regex_response() - Regex паттерны

```python
mock_llm.register_regex_response(r"\d+", "Вы ввели число")
mock_llm.register_regex_response(r"что такое \w+", "Это вопрос о...")

# Сработает на:
# - "сколько будет 2 + 2"
# - "что такое питон"
```

### 4. register_responses_batch() - Массовая регистрация

```python
responses = {
    "доброе утро": "Доброе утро!",
    "спасибо": "Пожалуйста!",
    r"\d+": "Число найдено"
}
mock_llm.register_responses_batch(responses)
```

## Конфигурация

### Строгий режим

```python
from core.infrastructure.providers.llm.mock_provider import MockLLMConfig

config = MockLLMConfig(strict_mode=True)
mock_llm = MockLLMProvider(config=config)

# В строгом режиме будет ошибка если ответ не найден
mock_llm.register_response("вопрос", "ответ")

await mock_llm.generate(LLMRequest(prompt="вопрос"))  # OK
await mock_llm.generate(LLMRequest(prompt="другой"))  # MockProviderError!
```

### Ответ по умолчанию

```python
config = MockLLMConfig(
    default_response="Я не понимаю этот вопрос",
    strict_mode=False  # По умолчанию
)
mock_llm = MockLLMProvider(config=config)

# Все незарегистрированные запросы вернут default_response
```

## Проверка истории вызовов

```python
# Получить всю историю
history = mock_llm.get_call_history()
for call in history:
    print(f"Prompt: {call['prompt']}")
    print(f"Response: {call['response']}")
    print(f"Pattern: {call['matched_pattern']}")

# Последний вызов
last_call = mock_llm.get_last_call()

# Очистить историю
mock_llm.clear_history()

# Assert в тестах
mock_llm.assert_called_with("ожидаемый текст")
mock_llm.assert_call_count(3)
```

## Пример для тестирования агента

```python
import pytest
from core.infrastructure.providers.llm.mock_provider import MockLLMProvider
from core.models.types.llm_types import LLMRequest

@pytest.fixture
def mock_llm():
    llm = MockLLMProvider()
    asyncio.run(llm.initialize())
    
    # Предзагружаем ответы для агента
    llm.register_responses_batch({
        "проверить статус": "Статус: ОК",
        "перезагрузить": "Перезагрузка начата",
        "показать логи": "[INFO] Все чисто"
    })
    
    yield llm
    
    asyncio.run(llm.shutdown())

async def test_agent_workflow(mock_llm):
    # Агент использует mock_llm
    agent = MyAgent(llm=mock_llm)
    
    result = await agent.check_status()
    assert "ОК" in result
    
    # Проверяем что LLM был вызван правильно
    mock_llm.assert_called_with("проверить статус")
    assert mock_llm.call_count == 1
```

## Приоритет поиска ответов

1. **Точное совпадение** (register_exact_response)
2. **Regex паттерны** (register_regex_response)
3. **Substring поиск** (register_response)
4. **Ответ по умолчанию** (если strict_mode=False)
5. **Ошибка** (если strict_mode=True)

## Дополнительные методы

```python
# Получить количество зарегистрированных паттернов
health = await mock_llm.health_check()
print(health["registered_patterns"])

# Статистика вызовов
print(health["call_count"])
```

## Файл с примерами

Запустите примеры использования:
```bash
python test_mock_llm_example.py
```
