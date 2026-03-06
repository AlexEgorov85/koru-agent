"""
Адаптеры для LLMPort.

АДАПТЕРЫ = Реализации портов для конкретных LLM-провайдеров.
Использует существующие провайдеры через адаптер.
"""
from typing import Dict, Any, List, Optional
import json

from core.infrastructure.interfaces.ports import LLMPort


class LlamaCppAdapter(LLMPort):
    """
    Адаптер LlamaCpp для LLMPort.
    
    ОБЁРТКА вокруг LlamaCppProvider для работы через порт.
    
    USAGE:
    ```python
    from core.infrastructure.providers.llm.llama_cpp_provider import LlamaCppProvider, LlamaCppConfig
    
    config = LlamaCppConfig(model_path="models/mistral.gguf")
    provider = LlamaCppProvider(config)
    await provider.initialize()
    
    adapter = LlamaCppAdapter(provider)
    
    # Использование через порт
    response = await adapter.generate(
        messages=[{"role": "user", "content": "Hello!"}],
        temperature=0.7
    )
    ```
    """
    
    def __init__(self, provider):
        """
        ARGS:
        - provider: Экземпляр LlamaCppProvider
        """
        self._provider = provider
    
    async def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stop_sequences: Optional[List[str]] = None
    ) -> str:
        """
        Сгенерировать текстовый ответ.
        
        ARGS:
        - messages: Список сообщений в формате [{"role": "user", "content": "..."}]
        - temperature: Температура генерации (0.0-1.0)
        - max_tokens: Максимальное количество токенов
        - stop_sequences: Последовательности для остановки генерации
        
        RETURNS:
        - Сгенерированный текст
        """
        if not self._provider.is_initialized:
            await self._provider.initialize()
        
        # Форматируем сообщения в промт для LlamaCpp
        prompt = self._format_messages_to_prompt(messages)
        
        # Используем внутренний метод провайдера для генерации
        response = await self._provider._generate_impl(
            prompt=prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            stop_sequences=stop_sequences
        )
        
        # Извлекаем текст из ответа
        if hasattr(response, 'content'):
            return response.content
        elif isinstance(response, dict):
            return response.get('content', '')
        else:
            return str(response)
    
    async def generate_structured(
        self,
        messages: List[Dict[str, str]],
        response_schema: Dict[str, Any],
        temperature: float = 0.7
    ) -> Dict[str, Any]:
        """
        Сгенерировать структурированный ответ (JSON).
        
        ARGS:
        - messages: Список сообщений
        - response_schema: JSON Schema ожидаемого ответа
        - temperature: Температура генерации
        
        RETURNS:
        - Словарь с полями согласно схеме
        """
        if not self._provider.is_initialized:
            await self._provider.initialize()
        
        # Добавляем инструкцию для JSON вывода
        schema_json = json.dumps(response_schema, ensure_ascii=False)
        system_message = {
            "role": "system",
            "content": f"Ответь ТОЛЬКО валидным JSON согласно этой схеме:\n{schema_json}"
        }
        
        # Объединяем сообщения
        all_messages = [system_message] + messages
        
        # Форматируем в промт
        prompt = self._format_messages_to_prompt(all_messages)
        
        # Генерируем ответ
        response = await self._provider._generate_impl(
            prompt=prompt,
            temperature=temperature,
            max_tokens=1000  # Увеличиваем для JSON
        )
        
        # Извлекаем и парсим JSON
        content = response.content if hasattr(response, 'content') else str(response)
        
        # Пытаемся найти JSON в ответе
        json_content = self._extract_json_from_response(content)
        
        return json.loads(json_content)
    
    async def count_tokens(self, messages: List[Dict[str, str]]) -> int:
        """
        Подсчитать количество токенов в сообщениях.
        
        ARGS:
        - messages: Список сообщений
        
        RETURNS:
        - Количество токенов
        """
        if not self._provider.is_initialized:
            await self._provider.initialize()
        
        prompt = self._format_messages_to_prompt(messages)
        
        # LlamaCpp имеет метод для токенизации
        if hasattr(self._provider.llm, 'tokenize'):
            tokens = self._provider.llm.tokenize(prompt.encode())
            return len(tokens)
        
        # Fallback: приблизительный подсчёт
        return len(prompt.split()) // 4
    
    def _format_messages_to_prompt(self, messages: List[Dict[str, str]]) -> str:
        """
        Форматировать сообщения в промт для LlamaCpp.
        
        Использует ChatML формат или формат конкретной модели.
        """
        prompt_parts = []
        
        for msg in messages:
            role = msg.get('role', 'user')
            content = msg.get('content', '')
            
            if role == 'system':
                prompt_parts.append(f"<|system|>\n{content}</s>")
            elif role == 'user':
                prompt_parts.append(f"<|user|>\n{content}</s>")
            elif role == 'assistant':
                prompt_parts.append(f"<|assistant|>\n{content}</s>")
            else:
                prompt_parts.append(content)
        
        # Добавляем префикс для ответа ассистента
        prompt_parts.append("<|assistant|>")
        
        return "\n".join(prompt_parts)
    
    def _extract_json_from_response(self, content: str) -> str:
        """
        Извлечь JSON из ответа LLM.
        
        LLM часто добавляют текст до/после JSON.
        """
        # Пытаемся найти JSON по скобкам
        start = content.find('{')
        end = content.rfind('}') + 1
        
        if start != -1 and end > start:
            return content[start:end]
        
        # Если не найдено, возвращаем как есть (возможно, это чистый JSON)
        return content.strip()


class MockLLMAdapter(LLMPort):
    """
    Mock-адаптер для LLMPort.
    
    ДЛЯ ТЕСТИРОВАНИЯ без реальной LLM.
    
    USAGE:
    ```python
    adapter = MockLLMAdapter(predefined_responses=["Test response"])
    response = await adapter.generate([...])
    assert response == "Test response"
    ```
    """
    
    def __init__(
        self,
        predefined_responses: Optional[List[str]] = None,
        delay_seconds: float = 0.0
    ):
        """
        ARGS:
        - predefined_responses: Список ответов для циклического возврата
        - delay_seconds: Имитация задержки ответа
        """
        import asyncio
        
        self._asyncio = asyncio
        self._responses = predefined_responses or ["Mock LLM response"]
        self._delay = delay_seconds
        self._call_count = 0
        self._messages_history: List[List[Dict[str, str]]] = []
    
    async def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stop_sequences: Optional[List[str]] = None
    ) -> str:
        if self._delay > 0:
            await self._asyncio.sleep(self._delay)
        
        self._call_count += 1
        self._messages_history.append(messages)
        
        return self._responses[(self._call_count - 1) % len(self._responses)]
    
    async def generate_structured(
        self,
        messages: List[Dict[str, str]],
        response_schema: Dict[str, Any],
        temperature: float = 0.7
    ) -> Dict[str, Any]:
        if self._delay > 0:
            await self._asyncio.sleep(self._delay)
        
        self._call_count += 1
        self._messages_history.append(messages)
        
        # Возвращаем mock-ответ по схеме
        return self._mock_structured_response(response_schema)
    
    async def count_tokens(self, messages: List[Dict[str, str]]) -> int:
        total = 0
        for msg in messages:
            total += len(msg.get("content", "").split())
        return total
    
    def _mock_structured_response(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        """Сгенерировать mock-ответ по схеме."""
        result = {}
        
        if "properties" in schema:
            for field_name, field_schema in schema["properties"].items():
                field_type = field_schema.get("type", "string")
                
                if field_type == "string":
                    result[field_name] = "Mock value"
                elif field_type == "integer":
                    result[field_name] = 0
                elif field_type == "boolean":
                    result[field_name] = False
                elif field_type == "array":
                    result[field_name] = []
                elif field_type == "object":
                    result[field_name] = {}
        
        return result
    
    @property
    def call_count(self) -> int:
        """Количество вызовов для assert."""
        return self._call_count
    
    @property
    def messages_history(self) -> List[List[Dict[str, str]]]:
        """История всех сообщений для assert."""
        return self._messages_history
