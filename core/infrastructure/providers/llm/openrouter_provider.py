import aiohttp
import json
import time
from typing import Dict, Any, Optional, List
from models.llm_types import LLMRequest, LLMResponse
from models.execution import ExecutionResult, ExecutionStatus
import logging

logger = logging.getLogger(__name__)

class OpenRouterProvider:
    """
    Провайдер для взаимодействия с OpenRouter API.
    Поддерживает различные модели, включая Qwen и другие.
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.api_key = config.get("api_key")
        self.base_url = config.get("base_url", "https://openrouter.ai/api/v1")
        self.model_name = config.get("model_name", "qwen/qwen-2-72b-instruct")
        self.temperature = config.get("temperature", 0.7)
        self.max_tokens = config.get("max_tokens", 2048)
        self.top_p = config.get("top_p", 1.0)
        self.frequency_penalty = config.get("frequency_penalty", 0.0)
        self.presence_penalty = config.get("presence_penalty", 0.0)
        self.timeout = config.get("timeout", 60)
        
        # Проверка наличия API ключа
        if not self.api_key:
            raise ValueError("API ключ для OpenRouter обязателен")
    
    async def generate(self, request: LLMRequest) -> LLMResponse:
        """
        Генерация ответа от модели через OpenRouter API.
        """
        start_time = time.time()
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": request.system_prompt or "You are a helpful assistant."},
                {"role": "user", "content": request.prompt}
            ],
            "temperature": request.temperature or self.temperature,
            "max_tokens": request.max_tokens or self.max_tokens,
            "top_p": request.top_p or self.top_p,
            "frequency_penalty": self.frequency_penalty,
            "presence_penalty": self.presence_penalty
        }
        
        # Добавляем дополнительные параметры из request
        if hasattr(request, 'extra_params') and request.extra_params:
            payload.update(request.extra_params)
        
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                async with session.post(
                    f"{self.base_url}/chat/completions", 
                    headers=headers, 
                    json=payload
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"OpenRouter API error {response.status}: {error_text}")
                        raise Exception(f"OpenRouter API error {response.status}: {error_text}")
                    
                    result = await response.json()
                    
                    content = result["choices"][0]["message"]["content"]
                    usage = result.get("usage", {})
                    generation_time = time.time() - start_time
                    
                    logger.info(f"OpenRouter request completed. Model: {self.model_name}, Tokens used: {usage.get('total_tokens', 'unknown')}, Time: {generation_time:.2f}s")
                    
                    return LLMResponse(
                        content=content,
                        usage=usage,
                        generation_time=generation_time
                    )
        
        except aiohttp.ClientError as e:
            logger.error(f"Network error during OpenRouter request: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during OpenRouter request: {str(e)}")
            raise
    
    async def generate_structured(
        self,
        user_prompt: str,
        output_schema: Dict[str, Any],
        system_prompt: str = None,
        temperature: float = None,
        max_tokens: int = None,
        **kwargs
    ) -> LLMResponse:
        """
        Генерация структурированного ответа в формате JSON.
        """
        start_time = time.time()
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # Создаем системный промпт, указывающий на формат JSON
        structured_system_prompt = (
            system_prompt or 
            "You are a helpful assistant that responds in JSON format. "
            "Always respond with valid JSON that matches the requested schema."
        )
        
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": structured_system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": temperature or self.temperature,
            "max_tokens": max_tokens or self.max_tokens,
            "top_p": self.top_p,
            "frequency_penalty": self.frequency_penalty,
            "presence_penalty": self.presence_penalty,
            "response_format": {"type": "json_object"}
        }
        
        # Добавляем любые дополнительные параметры
        payload.update(kwargs)
        
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                async with session.post(
                    f"{self.base_url}/chat/completions", 
                    headers=headers, 
                    json=payload
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"OpenRouter API error {response.status}: {error_text}")
                        raise Exception(f"OpenRouter API error {response.status}: {error_text}")
                    
                    result = await response.json()
                    
                    content = result["choices"][0]["message"]["content"]
                    usage = result.get("usage", {})
                    generation_time = time.time() - start_time
                    
                    logger.info(f"OpenRouter structured request completed. Model: {self.model_name}, Tokens used: {usage.get('total_tokens', 'unknown')}, Time: {generation_time:.2f}s")
                    
                    return LLMResponse(
                        content=content,
                        usage=usage,
                        generation_time=generation_time
                    )
        
        except aiohttp.ClientError as e:
            logger.error(f"Network error during OpenRouter structured request: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during OpenRouter structured request: {str(e)}")
            raise
    
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = None,
        max_tokens: int = None,
        **kwargs
    ) -> LLMResponse:
        """
        Прямой вызов чат-комплитиона с произвольными сообщениями.
        """
        start_time = time.time()
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": temperature or self.temperature,
            "max_tokens": max_tokens or self.max_tokens,
            "top_p": self.top_p,
            "frequency_penalty": self.frequency_penalty,
            "presence_penalty": self.presence_penalty
        }
        
        # Добавляем любые дополнительные параметры
        payload.update(kwargs)
        
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                async with session.post(
                    f"{self.base_url}/chat/completions", 
                    headers=headers, 
                    json=payload
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"OpenRouter API error {response.status}: {error_text}")
                        raise Exception(f"OpenRouter API error {response.status}: {error_text}")
                    
                    result = await response.json()
                    
                    content = result["choices"][0]["message"]["content"]
                    usage = result.get("usage", {})
                    generation_time = time.time() - start_time
                    
                    logger.info(f"OpenRouter chat completion completed. Model: {self.model_name}, Tokens used: {usage.get('total_tokens', 'unknown')}, Time: {generation_time:.2f}s")
                    
                    return LLMResponse(
                        content=content,
                        usage=usage,
                        generation_time=generation_time
                    )
        
        except aiohttp.ClientError as e:
            logger.error(f"Network error during OpenRouter chat completion: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during OpenRouter chat completion: {str(e)}")
            raise
    
    async def check_model_availability(self) -> bool:
        """
        Проверка доступности модели.
        """
        try:
            # Отправляем простой тестовый запрос
            test_request = LLMRequest(
                prompt="Say 'available' if you can respond.",
                system_prompt="You are a helpful assistant."
            )
            
            response = await self.generate(test_request)
            return "available" in response.content.lower()
        except Exception as e:
            logger.error(f"Model availability check failed: {str(e)}")
            return False
    
    def get_model_info(self) -> Dict[str, Any]:
        """
        Получение информации о текущей модели.
        """
        return {
            "model_name": self.model_name,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "supports_structured_output": True,
            "provider": "openrouter"
        }