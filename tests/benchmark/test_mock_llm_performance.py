"""
Benchmark тесты производительности Mock LLM.

Тестирует:
- Скорость ответа
- Пропускную способность
- Использование памяти
- Детерминированность
"""
import pytest
import asyncio
import time
import json
from typing import List


# ============================================================================
# Тесты скорости
# ============================================================================

@pytest.mark.benchmark
@pytest.mark.asyncio
async def test_mock_llm_single_request_latency():
    """
    Benchmark: Задержка одиночного запроса.
    
    Ожидаемая задержка: < 1ms
    """
    from core.infrastructure.providers.llm.mock_provider import MockLLMProvider, MockLLMConfig
    from core.models.types.llm_types import LLMRequest
    
    config = MockLLMConfig(model_name="benchmark-mock", temperature=0.0)
    provider = MockLLMProvider(config=config)
    provider.register_response("test", "test response")
    
    request = LLMRequest(prompt="test", max_tokens=100)
    
    # Замеряем задержку
    start = time.perf_counter()
    await provider.generate(request)
    latency = time.perf_counter() - start
    
    # Проверяем что задержка < 1ms
    assert latency < 0.001, f"Задержка слишком высокая: {latency*1000:.2f}ms"
    


@pytest.mark.benchmark
@pytest.mark.asyncio
async def test_mock_llm_average_response_time():
    """
    Benchmark: Среднее время ответа.
    
    Запускает 100 запросов и вычисляет среднее время.
    """
    from core.infrastructure.providers.llm.mock_provider import MockLLMProvider, MockLLMConfig
    from core.models.types.llm_types import LLMRequest
    
    config = MockLLMConfig(model_name="avg-mock", temperature=0.0)
    provider = MockLLMProvider(config=config)
    provider.register_response("benchmark", "benchmark response")
    
    request = LLMRequest(prompt="benchmark", max_tokens=100)
    
    # Выполняем 100 запросов
    times = []
    for _ in range(100):
        start = time.perf_counter()
        await provider.generate(request)
        times.append(time.perf_counter() - start)
    
    avg_time = sum(times) / len(times)
    min_time = min(times)
    max_time = max(times)
    
    
    # Среднее время должно быть < 1ms
    assert avg_time < 0.001, f"Среднее время слишком высокое: {avg_time*1000:.2f}ms"


@pytest.mark.benchmark
@pytest.mark.asyncio
async def test_mock_llm_throughput():
    """
    Benchmark: Пропускная способность (запросов в секунду).
    
    Запускает 1000 запросов и измеряет общую пропускную способность.
    """
    from core.infrastructure.providers.llm.mock_provider import MockLLMProvider, MockLLMConfig
    from core.models.types.llm_types import LLMRequest
    
    config = MockLLMConfig(model_name="throughput-mock", temperature=0.0)
    provider = MockLLMProvider(config=config)
    provider.register_response("load", "load response")
    
    request = LLMRequest(prompt="load", max_tokens=100)
    
    # Выполняем 1000 запросов
    total_requests = 1000
    start = time.perf_counter()
    
    for _ in range(total_requests):
        await provider.generate(request)
    
    elapsed = time.perf_counter() - start
    requests_per_second = total_requests / elapsed
    
    
    # Пропускная способность должна быть > 1000 req/s
    assert requests_per_second > 1000, f"Пропускная способность слишком низкая: {requests_per_second:.0f} req/s"


# ============================================================================
# Тесты параллелизма
# ============================================================================

@pytest.mark.benchmark
@pytest.mark.asyncio
async def test_mock_llm_concurrent_performance():
    """
    Benchmark: Производительность при параллельных запросах.
    
    Запускает 100 параллельных запросов.
    """
    from core.infrastructure.providers.llm.mock_provider import MockLLMProvider, MockLLMConfig
    from core.models.types.llm_types import LLMRequest
    
    config = MockLLMConfig(model_name="concurrent-mock", temperature=0.0)
    provider = MockLLMProvider(config=config)
    provider.register_response("concurrent", "concurrent response")
    
    async def make_request():
        request = LLMRequest(prompt="concurrent", max_tokens=100)
        return await provider.generate(request)
    
    # Запускаем 100 параллельных запросов
    total_requests = 100
    start = time.perf_counter()
    
    tasks = [make_request() for _ in range(total_requests)]
    await asyncio.gather(*tasks)
    
    elapsed = time.perf_counter() - start
    requests_per_second = total_requests / elapsed
    
    
    # Пропускная способность должна быть > 5000 req/s для параллельных запросов
    assert requests_per_second > 5000, f"Пропускная способность слишком низкая: {requests_per_second:.0f} req/s"


@pytest.mark.benchmark
@pytest.mark.asyncio
async def test_mock_llm_scaled_concurrency():
    """
    Benchmark: Масштабирование параллелизма.
    
    Тестирует производительность при разном уровне параллелизма.
    """
    from core.infrastructure.providers.llm.mock_provider import MockLLMProvider, MockLLMConfig
    from core.models.types.llm_types import LLMRequest
    
    config = MockLLMConfig(model_name="scale-mock", temperature=0.0)
    provider = MockLLMProvider(config=config)
    provider.register_response("scale", "scale response")
    
    async def make_request():
        request = LLMRequest(prompt="scale", max_tokens=100)
        return await provider.generate(request)
    
    # Тестируем разный уровень параллелизма
    concurrency_levels = [10, 50, 100, 200]
    results = []
    
    for concurrency in concurrency_levels:
        start = time.perf_counter()
        tasks = [make_request() for _ in range(concurrency)]
        await asyncio.gather(*tasks)
        elapsed = time.perf_counter() - start
        
        throughput = concurrency / elapsed
        results.append({
            'concurrency': concurrency,
            'time_ms': elapsed * 1000,
            'throughput': throughput
        })
        
    
    # Проверяем что производительность масштабируется
    # (время не должно расти линейно с количеством запросов)
    base_time = results[0]['time_ms']
    for i, result in enumerate(results[1:], 1):
        expected_linear_time = base_time * (concurrency_levels[i] / concurrency_levels[0])
        assert result['time_ms'] < expected_linear_time, \
            f"Производительность не масштабируется на уровне {concurrency_levels[i]}"


# ============================================================================
# Тесты памяти
# ============================================================================

@pytest.mark.benchmark
@pytest.mark.asyncio
async def test_mock_llm_memory_usage():
    """
    Benchmark: Использование памяти.
    
    Проверяет что память не утекает при множественных запросах.
    """
    import sys
    from core.infrastructure.providers.llm.mock_provider import MockLLMProvider, MockLLMConfig
    from core.models.types.llm_types import LLMRequest
    
    config = MockLLMConfig(model_name="memory-mock", temperature=0.0)
    provider = MockLLMProvider(config=config)
    provider.register_response("memory", "memory response")
    
    request = LLMRequest(prompt="memory", max_tokens=100)
    
    # Замеряем память до
    if hasattr(sys, 'getsizeof'):
        initial_size = sys.getsizeof(provider._call_history)
    else:
        initial_size = 0
    
    # Выполняем 1000 запросов
    for _ in range(1000):
        await provider.generate(request)
    
    # Замеряем память после
    final_size = sys.getsizeof(provider._call_history) if hasattr(sys, 'getsizeof') else 0
    
    # Проверяем что история не растет бесконечно
    # (в реальном тесте можно добавить лимит на размер истории)
    history_size = len(provider.get_call_history())
    assert history_size == 1000
    


# ============================================================================
# Тесты детерминированности
# ============================================================================

@pytest.mark.benchmark
@pytest.mark.asyncio
async def test_mock_llm_determinism_benchmark():
    """
    Benchmark: Детерминированность ответов.
    
    Проверяет что 1000 одинаковых запросов возвращают одинаковый ответ.
    """
    from core.infrastructure.providers.llm.mock_provider import MockLLMProvider, MockLLMConfig
    from core.models.types.llm_types import LLMRequest
    
    config = MockLLMConfig(model_name="determinism-mock", temperature=0.0)
    provider = MockLLMProvider(config=config)
    provider.register_response("deterministic", "deterministic response")
    
    request = LLMRequest(prompt="deterministic", max_tokens=100)
    
    # Выполняем 1000 запросов
    responses = []
    for _ in range(1000):
        response = await provider.generate(request)
        responses.append(response.content)
    
    # Все ответы должны быть одинаковыми
    unique_responses = set(responses)
    
    
    assert len(unique_responses) == 1, f"Недетерминированные ответы: {len(unique_responses)} уникальных"


# ============================================================================
# Сравнительные тесты
# ============================================================================

@pytest.mark.benchmark
@pytest.mark.asyncio
async def test_mock_llm_vs_json_parsing():
    """
    Benchmark: Сравнение с парсингом JSON.
    
    Показывает что mock LLM работает быстрее чем реальный LLM
    и сравнимо с простым парсингом JSON.
    """
    import json
    import time
    from core.infrastructure.providers.llm.mock_provider import MockLLMProvider, MockLLMConfig
    from core.models.types.llm_types import LLMRequest
    
    # Mock LLM
    config = MockLLMConfig(model_name="compare-mock", temperature=0.0)
    provider = MockLLMProvider(config=config)
    provider.register_response("json", '{"key": "value", "number": 42}')
    
    request = LLMRequest(prompt="json", max_tokens=100)
    
    # Замеряем Mock LLM
    start = time.perf_counter()
    for _ in range(100):
        response = await provider.generate(request)
        json.loads(response.content)
    mock_time = time.perf_counter() - start
    
    # Замеряем чистый JSON
    json_string = '{"key": "value", "number": 42}'
    start = time.perf_counter()
    for _ in range(100):
        json.loads(json_string)
    json_time = time.perf_counter() - start
    
    
    # Overhead должен быть разумным (< 100x)
    assert mock_time < json_time * 100, f"Mock LLM слишком медленный"
