"""
Стресс-тесты для инфраструктуры.

Тестирует:
- Параллельные запросы к одному провайдеру
- Нагрузку на EventBus
- Поведение при высокой нагрузке
"""
import asyncio
import pytest
import time
from unittest.mock import AsyncMock, patch

from core.config.models import SystemConfig, LLMProviderConfig, DBProviderConfig
from core.infrastructure.context.infrastructure_context import InfrastructureContext
from core.infrastructure.event_bus.event_bus import Event, EventType


@pytest.mark.stress
@pytest.mark.asyncio
async def test_parallel_requests_to_single_provider():
    """
    Стресс-тест: 50 параллельных запросов к одному провайдеру
    """
    config = SystemConfig(
        llm_providers={
            "stress_test_llm": LLMProviderConfig(
                type_provider="llama_cpp",
                model_name="stress-test-model",
                enabled=True,
                parameters={
                    "model_path": "models/stress-test-model.gguf",
                    "n_ctx": 512,
                    "n_threads": 1,
                    "verbose": False
                }
            )
        }
    )
    
    infra = InfrastructureContext(config)
    
    with patch('core.infrastructure.providers.llm.factory.LLMProviderFactory.create_provider') as mock_factory:
        mock_provider = AsyncMock()
        mock_provider.initialize = AsyncMock()
        mock_provider.shutdown = AsyncMock()
        
        # Мокаем generate с небольшой задержкой для симуляции реальной работы
        async def delayed_generate(prompt, max_tokens=1, **kwargs):
            await asyncio.sleep(0.001)  # очень короткая задержка
            return type('Response', (), {
                'text': f'Response to: {prompt}',
                'tokens_used': min(max_tokens, 10),
                'generation_time': 0.001
            })()
        
        mock_provider.generate = delayed_generate
        mock_factory.return_value = mock_provider
        
        try:
            await infra.initialize()
            
            llm = infra.get_provider("stress_test_llm")
            
            # Создаем 50 параллельных запросов
            tasks = []
            for i in range(50):
                task = llm.generate(prompt=f"Test prompt {i}", max_tokens=1)
                tasks.append(task)
            
            start_time = time.time()
            results = await asyncio.gather(*tasks)
            end_time = time.time()
            
            duration = end_time - start_time
            
            # Проверяем, что все запросы завершились успешно
            assert len(results) == 50
            for i, result in enumerate(results):
                assert result.text.startswith(f'Response to: Test prompt {i}')
            
            # Проверяем, что выполнение не заняло слишком много времени
            # (параллельные запросы должны выполняться быстрее, чем последовательно)
            assert duration < 0.1  # 100ms для 50 запросов с задержкой 1ms каждый
            
        finally:
            await infra.shutdown()


@pytest.mark.stress
@pytest.mark.asyncio
async def test_event_bus_under_high_load():
    """
    Стресс-тест: высокая нагрузка на EventBus
    """
    bus = EventBus()
    
    # Создаем обработчики для подсчета событий
    event_counts = {"processed": 0}
    processing_lock = asyncio.Lock()
    
    async def event_counter(event: Event):
        async with processing_lock:
            event_counts["processed"] += 1
    
    # Подписываемся на событие
    bus.subscribe(EventType.METRIC_COLLECTED, event_counter)
    
    # Публикуем 100 событий параллельно
    tasks = []
    for i in range(100):
        task = bus.publish(
            EventType.METRIC_COLLECTED,
            data={"metric": f"value_{i}", "timestamp": time.time()}
        )
        tasks.append(task)
    
    start_time = time.time()
    await asyncio.gather(*tasks)
    end_time = time.time()
    
    duration = end_time - start_time
    
    # Ждем немного, чтобы обработчики успели выполниться
    await asyncio.sleep(0.01)
    
    # Проверяем, что все события были обработаны
    assert event_counts["processed"] == 100
    assert duration < 1.0  # Обработка 100 событий не должна занимать больше секунды


@pytest.mark.stress
@pytest.mark.asyncio
async def test_multiple_contexts_creation_destruction():
    """
    Стресс-тест: многократное создание и уничтожение контекстов
    """
    config = SystemConfig(
        llm_providers={
            "temp_llm": LLMProviderConfig(
                type_provider="llama_cpp",
                model_name="temp-model",
                enabled=True,
                parameters={
                    "model_path": "models/temp-model.gguf",
                    "n_ctx": 512,
                    "n_threads": 1,
                    "verbose": False
                }
            )
        }
    )
    
    contexts = []
    
    with patch('core.infrastructure.providers.llm.factory.LLMProviderFactory.create_provider') as mock_factory:
        mock_provider = AsyncMock()
        mock_provider.initialize = AsyncMock()
        mock_provider.shutdown = AsyncMock()
        mock_factory.return_value = mock_provider
        
        # Создаем и уничтожаем 10 контекстов
        for i in range(10):
            ctx = InfrastructureContext(config)
            await ctx.initialize()
            
            # Проверяем, что контекст работает
            provider = ctx.get_provider("temp_llm")
            assert provider is not None
            
            contexts.append(ctx)
        
        # Теперь завершаем все контексты
        shutdown_tasks = []
        for ctx in contexts:
            shutdown_tasks.append(ctx.shutdown())
        
        await asyncio.gather(*shutdown_tasks)
        
        # Проверяем, что все контексты завершены
        for ctx in contexts:
            assert not ctx._initialized


@pytest.mark.stress
@pytest.mark.asyncio
async def test_concurrent_database_connections():
    """
    Стресс-тест: параллельные подключения к БД
    """
    config = SystemConfig(
        db_providers={
            "concurrent_db": DBProviderConfig(
                type_provider="sqlite",
                enabled=True,
                parameters={
                    "database_url": "sqlite:///:memory:",
                    "pool_size": 10
                }
            )
        }
    )
    
    infra = InfrastructureContext(config)
    
    with patch('core.infrastructure.providers.database.factory.DBProviderFactory.create_provider') as mock_factory:
        mock_provider = AsyncMock()
        mock_provider.initialize = AsyncMock()
        
        # Мокаем выполнение запроса с небольшой задержкой
        async def delayed_query(query):
            await asyncio.sleep(0.001)  # очень короткая задержка
            return type('Result', (), {
                'rowcount': 1,
                'rows': [{'query_num': hash(query) % 1000}]  # уникальный номер запроса
            })()
        
        mock_provider.execute_query = delayed_query
        mock_provider.shutdown = AsyncMock()
        mock_factory.return_value = mock_provider
        
        try:
            await infra.initialize()
            
            db = infra.get_provider("concurrent_db")
            
            # Выполняем 30 параллельных запросов
            queries = [f"SELECT {i} FROM dual" for i in range(30)]
            tasks = [db.execute_query(q) for q in queries]
            
            start_time = time.time()
            results = await asyncio.gather(*tasks)
            end_time = time.time()
            
            duration = end_time - start_time
            
            # Проверяем, что все запросы выполнились
            assert len(results) == 30
            for result in results:
                assert result.rowcount == 1
                assert 'query_num' in result.rows[0]
            
            # Проверяем, что выполнение не заняло слишком много времени
            assert duration < 0.1  # 100ms для 30 запросов с задержкой 1ms каждый
            
        finally:
            await infra.shutdown()


@pytest.mark.stress
@pytest.mark.asyncio
async def test_resource_leak_under_load():
    """
    Стресс-тест: проверка на утечки ресурсов при высокой нагрузке
    """
    config = SystemConfig(
        llm_providers={
            "leak_test_llm": LLMProviderConfig(
                type_provider="llama_cpp",
                model_name="leak-test-model",
                enabled=True,
                parameters={
                    "model_path": "models/leak-test-model.gguf",
                    "n_ctx": 512,
                    "n_threads": 1,
                    "verbose": False
                }
            )
        }
    )
    
    # Запоминаем начальное состояние
    initial_objects_count = len(asyncio.all_tasks()) if hasattr(asyncio, 'all_tasks') else 0
    
    infra = InfrastructureContext(config)
    
    with patch('core.infrastructure.providers.llm.factory.LLMProviderFactory.create_provider') as mock_factory:
        mock_provider = AsyncMock()
        mock_provider.initialize = AsyncMock()
        mock_provider.shutdown = AsyncMock()
        
        async def generate_response(prompt, **kwargs):
            await asyncio.sleep(0.0005)  # очень короткая задержка
            return type('Response', (), {
                'text': 'ok',
                'tokens_used': 1,
                'generation_time': 0.0005
            })()
        
        mock_provider.generate = generate_response
        mock_factory.return_value = mock_provider
        
        try:
            await infra.initialize()
            
            llm = infra.get_provider("leak_test_llm")
            
            # Выполняем 20 запросов
            tasks = [llm.generate(prompt=f"req_{i}") for i in range(20)]
            await asyncio.gather(*tasks)
            
        finally:
            await infra.shutdown()
    
    # Проверяем, что после завершения работы нет лишних объектов
    # (в реальной ситуации можно проверить использование памяти и количество задач)


@pytest.mark.stress
@pytest.mark.asyncio
async def test_event_bus_many_subscribers():
    """
    Стресс-тест: EventBus с множеством подписчиков
    """
    bus = EventBus()
    
    # Создаем 50 подписчиков
    counters = [0] * 50
    
    async def create_handler(index):
        async def handler(event: Event):
            counters[index] += 1
        return handler
    
    handlers = []
    for i in range(50):
        handler = await create_handler(i)
        handlers.append(handler)
        bus.subscribe(EventType.RETRY_ATTEMPT, handler)
    
    # Публикуем 10 событий
    tasks = []
    for i in range(10):
        task = bus.publish(EventType.RETRY_ATTEMPT, data={"attempt": i})
        tasks.append(task)
    
    await asyncio.gather(*tasks)
    
    # Ждем немного для обработки
    await asyncio.sleep(0.01)
    
    # Проверяем, что каждое событие получили все подписчики
    for counter in counters:
        assert counter == 10  # каждый подписчик должен получить 10 событий
    
    # Всего должно быть обработано 50 * 10 = 500 событий
    total_processed = sum(counters)
    assert total_processed == 500


@pytest.mark.stress
@pytest.mark.asyncio
async def test_long_running_stress_test():
    """
    Стресс-тест: продолжительная нагрузка
    """
    config = SystemConfig(
        llm_providers={
            "long_stress_llm": LLMProviderConfig(
                type_provider="llama_cpp",
                model_name="long-stress-model",
                enabled=True,
                parameters={
                    "model_path": "models/long-stress-model.gguf",
                    "n_ctx": 512,
                    "n_threads": 1,
                    "verbose": False
                }
            )
        },
        db_providers={
            "long_stress_db": DBProviderConfig(
                type_provider="sqlite",
                enabled=True,
                parameters={
                    "database_url": "sqlite:///:memory:"
                }
            )
        }
    )
    
    infra = InfrastructureContext(config)
    
    with patch('core.infrastructure.providers.llm.factory.LLMProviderFactory.create_provider') as mock_llm_factory, \
         patch('core.infrastructure.providers.database.factory.DBProviderFactory.create_provider') as mock_db_factory:
        
        mock_llm = AsyncMock()
        mock_llm.initialize = AsyncMock()
        mock_llm.shutdown = AsyncMock()
        
        async def llm_generate(prompt, **kwargs):
            await asyncio.sleep(0.001)
            return type('Response', (), {
                'text': f'LLM response to {prompt}',
                'tokens_used': 5,
                'generation_time': 0.001
            })()
        
        mock_llm.generate = llm_generate
        mock_llm_factory.return_value = mock_llm
        
        mock_db = AsyncMock()
        mock_db.initialize = AsyncMock()
        mock_db.shutdown = AsyncMock()
        
        async def db_query(query):
            await asyncio.sleep(0.001)
            return type('Result', (), {
                'rowcount': 1,
                'rows': [{'result': 'db_ok'}]
            })()
        
        mock_db.execute_query = db_query
        mock_db_factory.return_value = mock_db
        
        try:
            await infra.initialize()
            
            llm = infra.get_provider("long_stress_llm")
            db = infra.get_provider("long_stress_db")
            
            # Выполняем череду запросов в течение короткого периода
            tasks = []
            for i in range(25):
                # Чередуем LLM и DB запросы
                if i % 2 == 0:
                    task = llm.generate(prompt=f"LLM req {i}")
                else:
                    task = db.execute_query(f"SELECT {i}")
                tasks.append(task)
            
            start_time = time.time()
            results = await asyncio.gather(*tasks)
            end_time = time.time()
            
            duration = end_time - start_time
            
            # Проверяем результаты
            assert len(results) == 25
            for i, result in enumerate(results):
                if i % 2 == 0:  # LLM результаты
                    assert hasattr(result, 'text')
                    assert 'LLM response to LLM req' in result.text
                else:  # DB результаты
                    assert hasattr(result, 'rowcount')
                    assert result.rowcount == 1
            
            # Проверяем, что выполнение было относительно быстрым
            assert duration < 0.1  # 100ms для 25 запросов с задержкой 1ms каждый
            
        finally:
            await infra.shutdown()