"""
JSON Parser — утилитарные функции для работы с JSON ответами LLM.

ОТВЕТСТВЕННОСТЬ:
- Извлечение JSON из markdown-обёртки
- Используется провайдерами (llama_cpp, vllm) и компонентами

НЕ ОТВЕТСТВЕННОСТЬ:
- Валидация через Pydantic модели (это JsonParsingService)
- Создание Pydantic моделей из схемы (это JsonParsingService)

ИСПОЛЬЗУЕТСЯ:
- llama_cpp_provider._extract_json_from_response()
- vllm_provider._extract_json_from_response()
- data_analysis._parse_llm_response()
"""
import re


def extract_json_from_response(content: str) -> str:
    """
    Извлечение JSON из текста ответа (если есть обёртка).

    АЛГОРИТМ:
    1. Markdown блоки ```json ... ```
    2. Markdown блоки ``` ... ```
    3. Первая { и последняя } в тексте
    4. Первый [ и последний ] в тексте

    ПАРАМЕТРЫ:
    - content: Текст ответа LLM

    ВОЗВРАЩАЕТ:
    - JSON строка (или исходный текст если JSON не найден)
    """
    # Шаг 1: Ищем markdown блоки с json (приоритет)
    markdown_json_pattern = r'```json\s*(.*?)\s*```'
    matches = re.findall(markdown_json_pattern, content, re.DOTALL | re.IGNORECASE)
    for match in matches:
        json_content = match.strip()
        if json_content.startswith('{') or json_content.startswith('['):
            return json_content

    # Шаг 2: Ищем просто ``` без указания языка
    markdown_pattern = r'```\s*(.*?)\s*```'
    matches = re.findall(markdown_pattern, content, re.DOTALL)
    for match in matches:
        json_content = match.strip()
        if json_content.startswith('{') or json_content.startswith('['):
            return json_content

    # Шаг 3: Ищем первую { и последнюю } в тексте
    start = content.find('{')
    end = content.rfind('}') + 1

    if start != -1 and end > start:
        return content[start:end]

    # Шаг 4: Ищем массив [...]
    start = content.find('[')
    end = content.rfind(']') + 1

    if start != -1 and end > start:
        return content[start:end]

    # Ничего не нашли - возвращаем как есть
    return content
