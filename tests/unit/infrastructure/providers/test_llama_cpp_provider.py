"""
Реальные интеграционные тесты для LlamaCppProvider.
Тестируют работу с реальным Llama.cpp движком и реальными моделями.
ВАЖНО: Эти тесты требуют наличия файла модели и могут выполняться долго.
Для запуска: pytest -v tests/providers/test_llama_cpp_provider_real.py
"""

import pytest
import os
import time
import json


from core.config.config_loader import get_config
from core.infrastructure.providers.llm.base_llm import LLMResponse
from core.infrastructure.providers.llm.llama_cpp_provider import LlamaCppProvider
from models.llm_types import LLMHealthStatus, LLMRequest

# ==========================================================
# Конфигурация для реальных тестов
# ==========================================================

# Путь к модели по умолчанию для тестов
DEFAULT_MODEL_PATH = "./test_models/tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf"
TEST_MODELS_DIR = "./test_models"

# Проверяем, существует ли тестовая модель
def check_test_model_exists():
    """Проверяет наличие тестовой модели и скачивает её при необходимости."""
    if not os.path.exists(TEST_MODELS_DIR):
        os.makedirs(TEST_MODELS_DIR)
    
    if not os.path.exists(DEFAULT_MODEL_PATH):
        pytest.skip(f"Тестовая модель не найдена по пути: {DEFAULT_MODEL_PATH}. Скачайте тестовую модель для запуска этих тестов.")
    return True

# Пропускаем тесты если нет модели
check_test_model_exists()

@pytest.fixture(scope="module")
def real_llama_config():
    """Конфигурация для реального Llama.cpp провайдера."""
    return {
        "model_path": DEFAULT_MODEL_PATH,
        "n_ctx": 512,
        "n_gpu_layers": 0,  # 0 для CPU-only тестов
        "n_batch": 128,
        "verbose": False,
        "f16_kv": True,
        "temperature": 0.7,
        "max_tokens": 100
    }

@pytest.fixture(scope="module")
def system_context():
    """Системный контекст для тестов."""
    return get_config()

# ==========================================================
# Реальные тесты
# ==========================================================

@pytest.mark.integration
@pytest.mark.slow
class TestLlamaCppProviderReal:
    """Реальные интеграционные тесты для LlamaCppProvider."""
    
    @pytest.fixture(autouse=True)
    async def setup_provider(self, real_llama_config):
        """Инициализация провайдера перед каждым тестом."""
        self.provider = LlamaCppProvider("tinyllama-test", real_llama_config)
        try:
            success = await self.provider.initialize()
            assert success, "Не удалось инициализировать Llama.cpp провайдер"
            yield
        finally:
            await self.provider.shutdown()
    
    @pytest.mark.asyncio
    async def test_real_initialization(self):
        """Тест реальной инициализации Llama.cpp провайдера."""
        assert self.provider.is_initialized
        assert self.provider.health_status == LLMHealthStatus.HEALTHY
        assert hasattr(self.provider, 'engine') and self.provider.engine is not None
        
        # Проверяем базовую информацию о модели
        model_info = self.provider.get_model_info()
        assert model_info["model_name"] == "tinyllama-test"
        assert model_info["provider_type"] == "LlamaCppProvider"
        assert model_info["is_initialized"] is True
        assert model_info["health_status"] == LLMHealthStatus.HEALTHY.value
    
    @pytest.mark.asyncio
    async def test_base_text_generation(self):
        """Тест базовой генерации текста с реальной моделью."""
        request = LLMRequest(
            prompt="Привет! Как дела?",
            max_tokens=20,
            temperature=0.3,
            system_prompt="Ты — дружелюбный ассистент."
        )
        
        response = await self.provider.generate(request)
        
        # Проверки результатов
        assert isinstance(response, LLMResponse)
        assert isinstance(response.content, str)
        assert len(response.content) > 0
        assert response.model == "tinyllama-test"
        assert response.tokens_used > 0
        assert response.generation_time > 0
        assert response.finish_reason in ["stop", "length"]
        
        # Проверка метаданных
        assert "prompt_tokens" in response.metadata
        assert "completion_tokens" in response.metadata
        assert "total_tokens" in response.metadata
        assert response.metadata["prompt_tokens"] > 0
        assert response.metadata["completion_tokens"] > 0
        
        print(f"\nБазовый тест генерации:")
        print(f"Промпт: {request.prompt}")
        print(f"Ответ: {response.content}")
        print(f"Токенов: {response.tokens_used}, Время: {response.generation_time:.2f}с")
    
    @pytest.mark.asyncio
    async def test_structured_generation(self):
        """Тест генерации структурированных данных с реальной моделью."""
        schema = {
            "type": "object",
            "properties": {
                "answer": {"type": "string"},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                "follow_up_questions": {"type": "array", "items": {"type": "string"}}
            },
            "required": ["answer", "confidence"]
        }
        
        result = await self.provider.generate_structured(
            prompt="Какие преимущества у искусственного интеллекта?",
            output_schema=schema,
            system_prompt="Ты — эксперт по ИИ. Верни ответ в формате JSON."
        )
        
        # Проверки результатов
        assert isinstance(result, dict)
        assert "answer" in result
        assert "confidence" in result
        assert isinstance(result["answer"], str)
        assert isinstance(result["confidence"], float)
        assert 0.0 <= result["confidence"] <= 1.0
        
        # Опциональные поля
        if "follow_up_questions" in result:
            assert isinstance(result["follow_up_questions"], list)
            assert all(isinstance(q, str) for q in result["follow_up_questions"])
        
        print(f"\nТест структурированной генерации:")
        print(f"Результат: {json.dumps(result, indent=2, ensure_ascii=False)}")
        
        # Проверка валидации схемы
        from jsonschema import validate
        validate(instance=result, schema=schema)
    
    @pytest.mark.asyncio
    async def test_conversation_flow(self):
        """Тест разговорного потока с сохранением контекста."""
        # Шаг 1: Первый вопрос
        request1 = LLMRequest(
            prompt="Как тебя зовут?",
            max_tokens=30,
            temperature=0.3,
            system_prompt="Ты — помощник по имени Лунтик."
        )
        response1 = await self.provider.generate(request1)
        assert isinstance(response1.content, str)
        assert len(response1.content) > 0
        
        print(f"\nШаг 1 - Вопрос о имени:")
        print(f"Ответ: {response1.content}")
        
        # Шаг 2: Следующий вопрос с контекстом
        request2 = LLMRequest(
            prompt="А сколько тебе лет?",
            max_tokens=30,
            temperature=0.3,
            system_prompt="Ты — помощник по имени Лунтик."
        )
        response2 = await self.provider.generate(request2)
        assert isinstance(response2.content, str)
        assert len(response2.content) > 0
        
        print(f"Шаг 2 - Вопрос о возрасте:")
        print(f"Ответ: {response2.content}")
        
        # Шаг 3: Запрос с сохранением контекста разговора
        conversation_context = f"""
        Предыдущий разговор:
        Пользователь: Как тебя зовут?
        Ассистент: {response1.content}
        Пользователь: А сколько тебе лет?
        Ассистент: {response2.content}
        """
        
        request3 = LLMRequest(
            prompt="Какие у тебя хобби?",
            max_tokens=40,
            temperature=0.3,
            system_prompt=f"Ты — помощник по имени Лунтик. {conversation_context}"
        )
        response3 = await self.provider.generate(request3)
        assert isinstance(response3.content, str)
        assert len(response3.content) > 0
        
        print(f"Шаг 3 - Вопрос о хобби:")
        print(f"Ответ: {response3.content}")
    
    @pytest.mark.asyncio
    async def test_error_handling_and_recovery(self):
        """Тест обработки ошибок и восстановления после сбоев."""
        # Тест 1: Слишком длинный контекст
        long_prompt = "x" * 10000  # Очень длинный промпт
        request = LLMRequest(
            prompt=long_prompt,
            max_tokens=10,
            temperature=0.3
        )
        
        try:
            response = await self.provider.generate(request)
            # Должен вернуть ответ, даже если он обрезан
            assert isinstance(response.content, str)
            assert len(response.content) > 0
        except Exception as e:
            print(f"Ожидаемая ошибка при обработке длинного контекста: {str(e)}")
        
        # Проверка, что провайдер все еще работает
        health = await self.provider.health_check()
        assert health["status"] == LLMHealthStatus.HEALTHY.value
        
        # Тест 2: Некорректные параметры
        try:
            bad_request = LLMRequest(
                prompt="Тест",
                max_tokens=-1,  # Некорректное значение
                temperature=2.0  # Некорректное значение
            )
            await self.provider.generate(bad_request)
            pytest.fail("Ожидалась ошибка при некорректных параметрах")
        except ValueError:
            # Ожидаемая ошибка валидации
            pass
        except Exception as e:
            print(f"Обработана ошибка параметров: {str(e)}")
        
        # Проверка восстановления
        test_request = LLMRequest(
            prompt="Все в порядке?",
            max_tokens=20,
            temperature=0.3
        )
        recovery_response = await self.provider.generate(test_request)
        assert isinstance(recovery_response.content, str)
        assert len(recovery_response.content) > 0
        
        print(f"\nТест восстановления после ошибок успешен")
        print(f"Восстановленный ответ: {recovery_response.content}")
    
    @pytest.mark.asyncio
    async def test_performance_metrics(self):
        """Тест производительности и метрик."""
        test_prompts = [
            "Кратко опиши машинное обучение.",
            "Какие бывают типы нейронных сетей?",
            "Что такое большая языковая модель?"
        ]
        
        results = []
        total_time = 0
        total_tokens = 0
        
        for i, prompt in enumerate(test_prompts):
            print(f"\nТест производительности - запрос #{i+1}")
            print(f"Промпт: {prompt}")
            
            request = LLMRequest(
                prompt=prompt,
                max_tokens=50,
                temperature=0.3,
                system_prompt="Ты — эксперт по ИИ. Отвечай кратко и по делу."
            )
            
            start_time = time.time()
            response = await self.provider.generate(request)
            elapsed_time = time.time() - start_time
            
            # Сбор метрик
            tokens_per_second = response.tokens_used / elapsed_time if elapsed_time > 0 else 0
            
            results.append({
                "prompt": prompt,
                "response": response.content,
                "tokens": response.tokens_used,
                "time": elapsed_time,
                "tokens_per_second": tokens_per_second
            })
            
            total_time += elapsed_time
            total_tokens += response.tokens_used
            
            print(f"Ответ: {response.content[:100]}...")
            print(f"Токенов: {response.tokens_used}, Время: {elapsed_time:.2f}с, Скорость: {tokens_per_second:.1f} ток/с")
        
        # Итоговые метрики
        avg_time = total_time / len(test_prompts) if test_prompts else 0
        avg_tokens_per_second = total_tokens / total_time if total_time > 0 else 0
        
        print(f"\n=== ИТОГОВЫЕ МЕТРИКИ ===")
        print(f"Среднее время ответа: {avg_time:.2f}с")
        print(f"Средняя скорость: {avg_tokens_per_second:.1f} ток/с")
        print(f"Общее количество токенов: {total_tokens}")
        print(f"Общее время: {total_time:.2f}с")
        
        # Проверки производительности
        assert avg_tokens_per_second > 5, "Слишком низкая производительность"
        assert avg_time < 10.0, "Слишком долгий ответ"
        
        # Проверка метрик провайдера
        provider_info = self.provider.get_model_info()
        assert provider_info["request_count"] >= len(test_prompts)
        assert provider_info["error_count"] == 0
        assert provider_info["avg_response_time"] > 0
    
    @pytest.mark.asyncio
    async def test_context_window_handling(self):
        """Тест обработки длинного контекста и окна контекста."""
        # Создаем длинный контекст
        context_parts = []
        for i in range(20):  # Генерируем длинный контекст
            context_parts.append(f"Часть {i+1}: Это тестовая часть контекста для проверки обработки длинных последовательностей.")
        
        long_context = "\n".join(context_parts)
        assert len(long_context) > 1000, "Контекст недостаточно длинный для теста"
        
        request = LLMRequest(
            prompt="Обобщи основную мысль этого текста.",
            system_prompt=f"Контекст для анализа:\n{long_context}",
            max_tokens=100,
            temperature=0.3
        )
        
        response = await self.provider.generate(request)
        
        # Проверки
        assert isinstance(response.content, str)
        assert len(response.content) > 0
        assert "обобщение" in response.content.lower() or "основная" in response.content.lower()
        
        print(f"\nТест длинного контекста:")
        print(f"Длина контекста: {len(long_context)} символов")
        print(f"Ответ: {response.content}")
        
        # Проверка использования токенов
        assert response.tokens_used > 0
        assert response.metadata["prompt_tokens"] > 100  # Должно быть много токенов в промпте
    
    @pytest.mark.asyncio
    async def test_multilingual_support(self):
        """Тест поддержки нескольких языков."""
        test_cases = [
            {
                "prompt": "What are the benefits of renewable energy?",
                "system_prompt": "You are an environmental expert. Answer in English.",
                "language": "english"
            },
            {
                "prompt": "Каковы преимущества возобновляемых источников энергии?",
                "system_prompt": "Вы — эксперт по экологии. Отвечайте на русском языке.",
                "language": "russian"
            },
            {
                "prompt": "Quels sont les avantages des énergies renouvelables?",
                "system_prompt": "Vous êtes un expert en environnement. Répondez en français.",
                "language": "french"
            }
        ]
        
        results = {}
        
        for test_case in test_cases:
            request = LLMRequest(
                prompt=test_case["prompt"],
                system_prompt=test_case["system_prompt"],
                max_tokens=50,
                temperature=0.3
            )
            
            response = await self.provider.generate(request)
            results[test_case["language"]] = response.content
            
            print(f"\nТест {test_case['language']}:")
            print(f"Промпт: {test_case['prompt']}")
            print(f"Ответ: {response.content}")
            
            # Базовые проверки
            assert isinstance(response.content, str)
            assert len(response.content) > 10
            
            # Языковые проверки
            if test_case["language"] == "english":
                assert any(word in response.content.lower() for word in ["benefit", "renewable", "energy"])
            elif test_case["language"] == "russian":
                assert any(word in response.content.lower() for word in ["преимущество", "возобновляемый", "энергия"])
            elif test_case["language"] == "french":
                assert any(word in response.content.lower() for word in ["avantage", "renouvelable", "énergie"])
        
        print(f"\n=== МУЛЬТИЛИНГВАЛЬНЫЙ ТЕСТ УСПЕШЕН ===")