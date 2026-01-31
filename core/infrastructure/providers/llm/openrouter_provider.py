import asyncio
import aiohttp
import json
import time
from typing import Dict, Any, Optional, List
from models.llm_types import LLMRequest, LLMResponse, LLMHealthStatus
from core.infrastructure.providers.llm.base_llm import BaseLLMProvider
from core.retry_policy.retry_and_error_policy import RetryPolicy
import logging

logger = logging.getLogger(__name__)

class OpenRouterProvider(BaseLLMProvider):
    """
    Провайдер для взаимодействия с OpenRouter API.
    Поддерживает различные модели, включая Qwen и другие.
    """
    
    def __init__(self, model_name: str, config: Dict[str, Any], retry_policy: Optional[RetryPolicy] = None):
        super().__init__(model_name, config)
        self.api_key = config.get("api_key")
        self.base_url = config.get("base_url", "https://openrouter.ai/api/v1")
        self.model_name = model_name
        self.default_temperature = config.get("temperature", 0.7)
        self.default_max_tokens = config.get("max_tokens", 2048)
        self.default_top_p = config.get("top_p", 1.0)
        self.default_frequency_penalty = config.get("frequency_penalty", 0.0)
        self.default_presence_penalty = config.get("presence_penalty", 0.0)
        self.timeout = config.get("timeout", 60)
        self.retry_policy = retry_policy
        
        # Проверка наличия API ключа
        if not self.api_key:
            raise ValueError("API ключ для OpenRouter обязателен")
    
    async def initialize(self) -> bool:
        """
        Асинхронная инициализация провайдера.
        """
        try:
            # Проверка доступности API
            test_request = LLMRequest(
                prompt="Say 'initialized' if you can respond.",
                system_prompt="You are a helpful assistant."
            )
            
            response = await self.generate(test_request)
            self.is_initialized = True
            self.health_status = LLMHealthStatus.HEALTHY
            
            logger.info(f"OpenRouterProvider успешно инициализирован. Модель: {self.model_name}")
            return "initialized" in response.content.lower()
        except Exception as e:
            logger.error(f"Ошибка инициализации OpenRouterProvider: {str(e)}")
            self.health_status = LLMHealthStatus.UNHEALTHY
            return False
    
    async def shutdown(self) -> None:
        """
        Корректное завершение работы провайдера.
        """
        logger.info("Завершение работы OpenRouterProvider...")
        self.is_initialized = False
        self.health_status = LLMHealthStatus.UNKNOWN
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Проверка здоровья провайдера.
        """
        try:
            if not self.is_initialized:
                return {
                    "status": LLMHealthStatus.UNHEALTHY.value,
                    "error": "Provider not initialized",
                    "model": self.model_name
                }
            
            start_time = time.time()
            
            # Быстрый тестовый запрос
            test_request = LLMRequest(
                prompt="health check",
                system_prompt="You are a health check assistant",
                max_tokens=5,
                temperature=0.1
            )
            
            response = await self.generate(test_request)
            response_time = (time.time() - start_time) * 1000  # в миллисекундах
            
            return {
                "status": LLMHealthStatus.HEALTHY.value,
                "model": self.model_name,
                "response_time_ms": response_time,
                "is_initialized": self.is_initialized,
                "request_count": self.request_count,
                "error_count": self.error_count,
                "avg_response_time_ms": self.avg_response_time * 1000
            }
            
        except Exception as e:
            logger.error(f"Ошибка health check для OpenRouter: {str(e)}", exc_info=True)
            return {
                "status": LLMHealthStatus.UNHEALTHY.value,
                "error": str(e),
                "model": self.model_name,
                "is_initialized": self.is_initialized
            }
    
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
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "top_p": request.top_p,
            "frequency_penalty": request.frequency_penalty,
            "presence_penalty": request.presence_penalty
        }
        
        # Добавляем дополнительные параметры из request.metadata
        if request.metadata:
            # Если в metadata есть специальные параметры для OpenRouter
            if 'extra_params' in request.metadata:
                payload.update(request.metadata['extra_params'])
        
        attempt = 0
        max_retries = getattr(self, 'max_retries', 3)
        
        while attempt <= max_retries:
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
                            
                            if attempt < max_retries:
                                attempt += 1
                                if self.retry_policy:
                                    error_info = type('ErrorInfo', (), {
                                        'category': 'transient',
                                        'message': f"API error {response.status}: {error_text}",
                                        'raw_error': Exception(f"API error {response.status}")
                                    })
                                    retry_result = self.retry_policy.evaluate(error=error_info, attempt=attempt - 1)
                                    if retry_result.decision == "retry" and retry_result.delay_seconds > 0:
                                        await asyncio.sleep(retry_result.delay_seconds)
                                    continue
                                else:
                                    await asyncio.sleep(2 ** attempt)  # Экспоненциальная задержка
                                continue
                            else:
                                raise Exception(f"OpenRouter API error {response.status}: {error_text}")
                        
                        result = await response.json()
                        
                        content = result["choices"][0]["message"]["content"]
                        usage = result.get("usage", {})
                        generation_time = time.time() - start_time
                        
                        logger.info(f"OpenRouter request completed. Model: {self.model_name}, Tokens used: {usage.get('total_tokens', 'unknown')}, Time: {generation_time:.2f}s")
                        
                        # Обновление метрик
                        self._update_metrics(generation_time)
                        
                        return LLMResponse(
                            content=content,
                            model=self.model_name,
                            tokens_used=usage.get('total_tokens', 0),
                            generation_time=generation_time,
                            finish_reason=result["choices"][0].get("finish_reason", "stop"),
                            metadata={
                                "usage": usage,
                                "parameters": {
                                    "temperature": request.temperature,
                                    "max_tokens": request.max_tokens,
                                    "top_p": request.top_p
                                }
                            }
                        )
            
            except aiohttp.ClientError as e:
                logger.warning(f"Попытка {attempt + 1}/{max_retries + 1} не удалась: {str(e)}")
                
                if attempt < max_retries:
                    attempt += 1
                    if self.retry_policy:
                        error_info = type('ErrorInfo', (), {
                            'category': 'transient',
                            'message': str(e),
                            'raw_error': e
                        })
                        retry_result = self.retry_policy.evaluate(error=error_info, attempt=attempt - 1)
                        if retry_result.decision == "retry" and retry_result.delay_seconds > 0:
                            await asyncio.sleep(retry_result.delay_seconds)
                        continue
                    else:
                        await asyncio.sleep(2 ** attempt)  # Экспоненциальная задержка
                    continue
                else:
                    logger.error(f"Network error during OpenRouter request: {str(e)}")
                    self._update_metrics(time.time() - start_time, success=False)
                    raise
            except Exception as e:
                logger.warning(f"Попытка {attempt + 1}/{max_retries + 1} не удалась: {str(e)}")
                
                if attempt < max_retries:
                    attempt += 1
                    if self.retry_policy:
                        error_info = type('ErrorInfo', (), {
                            'category': 'transient',
                            'message': str(e),
                            'raw_error': e
                        })
                        retry_result = self.retry_policy.evaluate(error=error_info, attempt=attempt - 1)
                        if retry_result.decision == "retry" and retry_result.delay_seconds > 0:
                            await asyncio.sleep(retry_result.delay_seconds)
                        continue
                    else:
                        await asyncio.sleep(2 ** attempt)  # Экспоненциальная задержка
                    continue
                else:
                    logger.error(f"Unexpected error during OpenRouter request: {str(e)}")
                    self._update_metrics(time.time() - start_time, success=False)
                    raise
    
    async def generate_structured(self, request: LLMRequest, output_schema: Dict[str, Any]) -> LLMResponse:
        """
        Генерация структурированного ответа в формате JSON.
        """
        start_time = time.time()
        
        # Обновляем промпт, чтобы указать формат JSON
        structured_system_prompt = (
            request.system_prompt or 
            "You are a helpful assistant that responds in JSON format. "
            "Always respond with valid JSON that matches the requested schema."
        )
        
        # Создаем новый запрос с обновленным системным промптом и указанием формата
        structured_request = LLMRequest(
            prompt=request.prompt,
            system_prompt=structured_system_prompt,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            top_p=request.top_p,
            frequency_penalty=request.frequency_penalty,
            presence_penalty=request.presence_penalty,
            metadata={**(request.metadata or {}), "response_format": {"type": "json_object"}}
        )
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": structured_system_prompt},
                {"role": "user", "content": request.prompt}
            ],
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "top_p": request.top_p,
            "frequency_penalty": request.frequency_penalty,
            "presence_penalty": request.presence_penalty,
            "response_format": {"type": "json_object"}
        }
        
        # Добавляем любые дополнительные параметры из metadata
        if request.metadata:
            if 'extra_params' in request.metadata:
                payload.update(request.metadata['extra_params'])
        
        attempt = 0
        max_retries = getattr(self, 'max_retries', 3)
        
        while attempt <= max_retries:
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
                            
                            if attempt < max_retries:
                                attempt += 1
                                if self.retry_policy:
                                    error_info = type('ErrorInfo', (), {
                                        'category': 'transient',
                                        'message': f"API error {response.status}: {error_text}",
                                        'raw_error': Exception(f"API error {response.status}")
                                    })
                                    retry_result = self.retry_policy.evaluate(error=error_info, attempt=attempt - 1)
                                    if retry_result.decision == "retry" and retry_result.delay_seconds > 0:
                                        await asyncio.sleep(retry_result.delay_seconds)
                                    continue
                                else:
                                    await asyncio.sleep(2 ** attempt)  # Экспоненциальная задержка
                                continue
                            else:
                                raise Exception(f"OpenRouter API error {response.status}: {error_text}")
                        
                        result = await response.json()
                        
                        content = result["choices"][0]["message"]["content"]
                        usage = result.get("usage", {})
                        generation_time = time.time() - start_time
                        
                        logger.info(f"OpenRouter structured request completed. Model: {self.model_name}, Tokens used: {usage.get('total_tokens', 'unknown')}, Time: {generation_time:.2f}s")
                        
                        # Обновление метрик
                        self._update_metrics(generation_time)
                        
                        return LLMResponse(
                            content=content,
                            model=self.model_name,
                            tokens_used=usage.get('total_tokens', 0),
                            generation_time=generation_time,
                            finish_reason=result["choices"][0].get("finish_reason", "stop"),
                            metadata={
                                "usage": usage,
                                "parameters": {
                                    "temperature": request.temperature,
                                    "max_tokens": request.max_tokens,
                                    "top_p": request.top_p
                                },
                                "output_schema": output_schema
                            }
                        )
        
            except aiohttp.ClientError as e:
                logger.warning(f"Попытка {attempt + 1}/{max_retries + 1} структурированной генерации не удалась: {str(e)}")
                
                if attempt < max_retries:
                    attempt += 1
                    if self.retry_policy:
                        error_info = type('ErrorInfo', (), {
                            'category': 'transient',
                            'message': str(e),
                            'raw_error': e
                        })
                        retry_result = self.retry_policy.evaluate(error=error_info, attempt=attempt - 1)
                        if retry_result.decision == "retry" and retry_result.delay_seconds > 0:
                            await asyncio.sleep(retry_result.delay_seconds)
                        continue
                    else:
                        await asyncio.sleep(2 ** attempt)  # Экспоненциальная задержка
                    continue
                else:
                    logger.error(f"Network error during OpenRouter structured request: {str(e)}")
                    self._update_metrics(time.time() - start_time, success=False)
                    raise
            except Exception as e:
                logger.warning(f"Попытка {attempt + 1}/{max_retries + 1} структурированной генерации не удалась: {str(e)}")
                
                if attempt < max_retries:
                    attempt += 1
                    if self.retry_policy:
                        error_info = type('ErrorInfo', (), {
                            'category': 'transient',
                            'message': str(e),
                            'raw_error': e
                        })
                        retry_result = self.retry_policy.evaluate(error=error_info, attempt=attempt - 1)
                        if retry_result.decision == "retry" and retry_result.delay_seconds > 0:
                            await asyncio.sleep(retry_result.delay_seconds)
                        continue
                    else:
                        await asyncio.sleep(2 ** attempt)  # Экспоненциальная задержка
                    continue
                else:
                    logger.error(f"Unexpected error during OpenRouter structured request: {str(e)}")
                    self._update_metrics(time.time() - start_time, success=False)
                    raise
