"""
Провайдер для vLLM (Very Large Language Model).
Использует локальный инференс через vLLM движок.

vLLM — высокопроизводительный движок для инференса и обслуживания LLM.
Обеспечивает эффективное использование памяти и высокую пропускную способность.
"""
import time
import json
import re
from typing import Dict, Any, Optional, List

from core.infrastructure.providers.llm.base_llm import BaseLLMProvider
from core.infrastructure.interfaces.llm import LLMInterface
from core.models.types.llm_types import (
    LLMRequest,
    LLMResponse,
    LLMHealthStatus,
    StructuredOutputConfig,
    RawLLMResponse
)
from pydantic import BaseModel, Field


class VLLMConfig(BaseModel):
    """Конфигурация для vLLM провайдера."""
    model_name: str = Field(
        default="meta-llama/Llama-2-7b-chat-hf",
        description="Имя модели на HuggingFace или локальный путь"
    )
    model_path: Optional[str] = Field(
        default=None,
        description="Локальный путь к модели (если отличается от model_name)"
    )
    tensor_parallel_size: int = Field(
        default=1,
        description="Количество GPU для tensor parallelism"
    )
    gpu_memory_utilization: float = Field(
        default=0.9,
        ge=0.1,
        le=1.0,
        description="Доля GPU памяти для KV cache"
    )
    max_num_seqs: int = Field(
        default=256,
        description="Максимальное количество параллельных последовательностей"
    )
    max_model_len: Optional[int] = Field(
        default=None,
        description="Максимальная длина контекста"
    )
    enforce_eager: bool = Field(
        default=True,
        description="Использовать eager execution (без CUDA graphs)"
    )
    temperature: float = Field(default=0.7, description="Температура генерации")
    max_tokens: int = Field(default=4096, description="Максимальное количество токенов")
    dtype: str = Field(
        default="auto",
        description="Тип данных: auto, float16, bfloat16, float8"
    )
    trust_remote_code: bool = Field(
        default=True,
        description="Доверять remote code при загрузке модели"
    )


class VLLMProvider(BaseLLMProvider, LLMInterface):
    """
    Провайдер для vLLM с локальным инференсом.

    Поддерживает:
    - Все модели, поддерживаемые vLLM
    - Structured output через JSON schema
    - Parallel generation
    - Tool calling (function calling)
    
    ОСОБЕННОСТИ:
    - Использует vLLM LLM class для offline inference
    - Эффективное использование памяти PagedAttention
    - Загружает модель в GPU напрямую
    """

    def __init__(self, config, model_name: str = None):
        if isinstance(config, dict):
            config_obj = VLLMConfig(**config)
        else:
            config_obj = config

        model_name = model_name or config_obj.model_name
        super().__init__(model_name=model_name, config=config_obj.model_dump())

        self.config_obj = config_obj
        self.llm = None
        self._tokenizer = None

    def _resolve_model_path(self, model_path: str) -> str:
        """Разрешение пути к модели."""
        from pathlib import Path

        path = Path(model_path)
        if path.is_absolute():
            return model_path

        project_root = Path(__file__).parent.parent.parent.parent.parent
        resolved = project_root / model_path

        if resolved.exists():
            return str(resolved)

        return model_path

    async def initialize(self) -> bool:
        """Инициализация vLLM движка и загрузка модели."""
        try:
            model_path = self.config_obj.model_path or self.config_obj.model_name
            model_path = self._resolve_model_path(model_path)

            from vllm import LLM
            self.llm = LLM(
                model=model_path,
                tensor_parallel_size=self.config_obj.tensor_parallel_size,
                gpu_memory_utilization=self.config_obj.gpu_memory_utilization,
                max_num_seqs=self.config_obj.max_num_seqs,
                max_model_len=self.config_obj.max_model_len,
                enforce_eager=self.config_obj.enforce_eager,
                dtype=self.config_obj.dtype,
                trust_remote_code=self.config_obj.trust_remote_code,
            )

            self.is_initialized = True
            self.health_status = LLMHealthStatus.HEALTHY
            self.last_health_check = time.time()

            return True

        except ImportError as e:
            self.health_status = LLMHealthStatus.UNHEALTHY
            return False
        except Exception as e:
            self.health_status = LLMHealthStatus.UNHEALTHY
            return False

    async def shutdown(self) -> None:
        """Завершение работы vLLM провайдера."""
        self.llm = None
        self.is_initialized = False

    async def health_check(self) -> Dict[str, Any]:
        """Проверка здоровья vLLM провайдера."""
        try:
            if not self.is_initialized or not self.llm:
                return {
                    "status": LLMHealthStatus.UNHEALTHY.value,
                    "error": "Not initialized",
                    "model": self.model_name,
                    "is_initialized": self.is_initialized
                }

            start_time = time.time()

            from vllm import SamplingParams
            result = await self.llm.generate(
                "ОК",
                SamplingParams(temperature=0.1, max_tokens=5)
            )

            response_time = time.time() - start_time

            return {
                "status": LLMHealthStatus.HEALTHY.value,
                "model": self.model_name,
                "is_initialized": self.is_initialized,
                "response_time": response_time,
                "request_count": self.request_count,
                "error_count": self.error_count
            }

        except Exception as e:
            return {
                "status": LLMHealthStatus.UNHEALTHY.value,
                "error": str(e),
                "model": self.model_name,
                "is_initialized": self.is_initialized
            }

    def _extract_json_from_response(self, content: str) -> str:
        """Извлечь JSON из ответа LLM."""
        json_block_pattern = r'```json\s*\n?(.*?)\n?```'
        matches = re.findall(json_block_pattern, content, re.DOTALL)
        if matches:
            return matches[-1].strip()

        code_block_pattern = r'```\s*\n?(.*?)\n?```'
        matches = re.findall(code_block_pattern, content, re.DOTALL)
        if matches:
            for block in reversed(matches):
                block = block.strip()
                if block.startswith('{') and block.endswith('}'):
                    try:
                        json.loads(block)
                        return block
                    except json.JSONDecodeError:
                        continue

        start = content.find('{')
        end = content.rfind('}') + 1

        if start != -1 and end > start:
            candidate = content[start:end]
            try:
                json.loads(candidate)
                return candidate
            except json.JSONDecodeError:
                pos = start + 1
                while pos < len(content):
                    next_start = content.find('{', pos)
                    if next_start == -1:
                        break
                    next_end = content.rfind('}', pos) + 1
                    if next_end <= next_start:
                        break
                    candidate = content[next_start:next_end]
                    try:
                        json.loads(candidate)
                        return candidate
                    except json.JSONDecodeError:
                        pos = next_start + 1
                return candidate

        return content.strip()

    def _format_messages_to_prompt(self, messages: List[Dict[str, str]]) -> str:
        """Форматировать сообщения в промпт для vLLM."""
        from transformers import AutoTokenizer

        if self._tokenizer is None:
            model_path = self.config_obj.model_path or self.config_obj.model_name
            model_path = self._resolve_model_path(model_path)
            try:
                self._tokenizer = AutoTokenizer.from_pretrained(
                    model_path, 
                    trust_remote_code=self.config_obj.trust_remote_code
                )
            except Exception:
                return self._simple_format_messages(messages)

        try:
            texts = self._tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True
            )
            return texts
        except Exception:
            return self._simple_format_messages(messages)

    def _simple_format_messages(self, messages: List[Dict[str, str]]) -> str:
        """Простое форматирование сообщений."""
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

        prompt_parts.append("<|assistant|>")
        return "\n".join(prompt_parts)

    async def _generate_impl(self, request: LLMRequest) -> LLMResponse:
        """Генерация текста через vLLM."""
        if not self.is_initialized or not self.llm:
            await self.initialize()

        start_time = time.time()

        if hasattr(request, 'structured_output') and request.structured_output:
            max_tokens = min(request.max_tokens, 4000)
        else:
            max_tokens = request.max_tokens

        from vllm import SamplingParams
        from vllm.sampling_params import StructuredOutputsParams

        prompt = request.prompt
        system_prompt = request.system_prompt or ""

        if request.messages:
            messages = list(request.messages)
            if system_prompt:
                messages.insert(0, {"role": "system", "content": system_prompt})
            prompt = self._format_messages_to_prompt(messages)

        structured_outputs = None
        if hasattr(request, 'structured_output') and request.structured_output:
            schema_def = request.structured_output.schema_def
            structured_outputs = StructuredOutputsParams(
                json={
                    "name": "response",
                    "schema": schema_def
                }
            )

        sampling_params = SamplingParams(
            temperature=request.temperature,
            max_tokens=max_tokens,
            top_p=request.top_p,
            frequency_penalty=request.frequency_penalty,
            presence_penalty=request.presence_penalty,
            stop=request.stop_sequences or None,
            structured_outputs=structured_outputs
        )

        try:
            response = await self.llm.generate(prompt, sampling_params)

            choices = response.outputs
            usage = response.usage

            if choices:
                generated_text = choices[0].text
                finish_reason = choices[0].finish_reason or "stop"
            else:
                generated_text = ''
                finish_reason = 'error'

            tokens_used = usage.total_tokens if usage else 0
            generation_time = time.time() - start_time

            if hasattr(request, 'structured_output') and request.structured_output:
                if not generated_text or not generated_text.strip():
                    return LLMResponse(
                        parsed_content=None,
                        raw_response=RawLLMResponse(
                            content="",
                            model=self.model_name,
                            tokens_used=tokens_used,
                            generation_time=generation_time,
                            finish_reason="stop",
                            metadata={
                                "error": "empty_response",
                                "warning": "vLLM вернул пустой ответ для structured output запроса"
                            }
                        ),
                        model=self.model_name,
                        tokens_used=tokens_used,
                        generation_time=generation_time,
                        parsing_attempts=1,
                        validation_errors=[{
                            "error": "empty_response",
                            "message": "LLM вернул пустой ответ — невозможно распарсить JSON"
                        }]
                    )

                json_content = self._extract_json_from_response(generated_text)

                try:
                    parsed_json = json.loads(json_content)

                    return LLMResponse(
                        parsed_content=None,
                        raw_response=RawLLMResponse(
                            content=json_content,
                            model=self.model_name,
                            tokens_used=tokens_used,
                            generation_time=generation_time,
                            finish_reason=finish_reason,
                            metadata={"parsed_json": parsed_json}
                        ),
                        model=self.model_name,
                        tokens_used=tokens_used,
                        generation_time=generation_time,
                        parsing_attempts=1,
                        validation_errors=[]
                    )
                except (json.JSONDecodeError, Exception) as err:
                    return LLMResponse(
                        parsed_content=None,
                        raw_response=RawLLMResponse(
                            content=generated_text,
                            model=self.model_name,
                            tokens_used=tokens_used,
                            generation_time=generation_time,
                            finish_reason="stop",
                            metadata={"parse_error": str(err)}
                        ),
                        model=self.model_name,
                        tokens_used=tokens_used,
                        generation_time=generation_time,
                        parsing_attempts=1,
                        validation_errors=[{
                            "error": "json_parse_error" if isinstance(err, json.JSONDecodeError) else "exception",
                            "message": str(err)
                        }]
                    )

            self._update_metrics(generation_time)

            return LLMResponse(
                content=generated_text,
                model=self.model_name,
                tokens_used=tokens_used,
                generation_time=generation_time,
                finish_reason=finish_reason
            )

        except Exception as e:
            self._update_metrics(time.time() - start_time, success=False)
            return LLMResponse(
                content="",
                model=self.model_name,
                tokens_used=0,
                generation_time=time.time() - start_time,
                finish_reason="error",
                metadata={"error": str(e)}
            )

    async def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stop_sequences: Optional[List[str]] = None
    ) -> str:
        """Генерация текста (для совместимости с LLMInterface)."""
        if not self.is_initialized:
            await self.initialize()

        request = LLMRequest(
            prompt="",
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens or self.config_obj.max_tokens,
            stop_sequences=stop_sequences
        )

        response = await self._generate_impl(request)
        return response.content

    async def generate_structured(
        self,
        messages: List[Dict[str, str]],
        response_schema: Dict[str, Any],
        temperature: float = 0.7
    ) -> Dict[str, Any]:
        """Генерация структурированного ответа (для совместимости с LLMInterface)."""
        if not self.is_initialized:
            await self.initialize()

        schema_instruction = {
            "role": "system",
            "content": (
                "Ответь ТОЛЬКО валидным JSON согласно предоставленной схеме.\n"
                "НЕ добавляй пояснений, вступлений или markdown-обёрток.\n"
                "НЕ используй triple backticks (```)."
            )
        }

        has_system = any(msg.get("role") == "system" for msg in messages)

        if has_system:
            all_messages = list(messages) + [schema_instruction]
        else:
            all_messages = [schema_instruction] + list(messages)

        request = LLMRequest(
            prompt="",
            messages=all_messages,
            structured_output=StructuredOutputConfig(
                output_model="dynamic",
                schema_def=response_schema
            ),
            temperature=temperature,
            max_tokens=4096
        )

        response = await self._generate_impl(request)

        if response.raw_response and response.raw_response.metadata and "parsed_json" in response.raw_response.metadata:
            return response.raw_response.metadata["parsed_json"]

        json_content = self._extract_json_from_response(response.content)
        return json.loads(json_content)

    async def count_tokens(self, messages: List[Dict[str, str]]) -> int:
        """Подсчёт токенов."""
        prompt = self._format_messages_to_prompt(messages)

        if self._tokenizer:
            tokens = self._tokenizer(prompt)
            return len(tokens.input_ids)

        return len(prompt.split()) // 4
