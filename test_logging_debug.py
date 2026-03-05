#!/usr/bin/env python3
"""
Тест системы логирования.

Проверяет:
1. Инициализацию InfrastructureContext
2. Подписку обработчиков (TerminalLogHandler, FileLogHandler)
3. Публикацию событий LOG_*
4. Публикацию событий LLM_*
5. Вывод в терминал
6. Запись в файлы
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from core.config import get_config
from core.infrastructure.context.infrastructure_context import InfrastructureContext
from core.infrastructure.logging import EventBusLogger


async def test_logging():
    print("=" * 70)
    print("ТЕСТ СИСТЕМЫ ЛОГИРОВАНИЯ")
    print("=" * 70)
    
    # 1. Инициализация
    print("\n[1/5] Инициализация InfrastructureContext...")
    config = get_config(profile='dev')
    infra = InfrastructureContext(config)
    await infra.initialize()
    print("   [OK] InfrastructureContext инициализирован")
    print(f"   Session ID: {infra.id}")
    print(f"   Terminal handler: {infra.terminal_handler is not None}")
    print(f"   File handler: {infra.file_handler is not None}")
    
    # 2. Создание логгера
    print("\n[2/5] Создание EventBusLogger...")
    logger = EventBusLogger(
        infra.event_bus,
        session_id="test_session",
        agent_id="test_agent",
        component="TestComponent"
    )
    print("   [OK] EventBusLogger создан")
    
    # 3. Публикация событий LOG_*
    print("\n[3/5] Публикация тестовых событий LOG_*...")
    await logger.info("Тест INFO сообщение")
    await logger.debug("Тест DEBUG сообщение")
    await logger.warning("Тест WARNING сообщение")
    await logger.error("Тест ERROR сообщение")
    print("   [OK] События LOG_* опубликованы")
    
    # 4. Публикация событий LLM_*
    print("\n[4/5] Публикация тестовых событий LLM_*...")
    from core.infrastructure.event_bus.unified_event_bus import EventType
    
    await infra.event_bus.publish(
        event_type=EventType.LLM_CALL_STARTED,
        data={
            "message": "Начало LLM вызова",
            "level": "INFO",
            "session_id": "test_session",
            "agent_id": "test_agent",
            "component": "test_llm",
            "provider": "MockLLM",
            "model": "test-model",
            "prompt_length": 100,
            "max_tokens": 512,
            "temperature": 0.7
        },
        source="test_llm_provider",
        session_id="test_session",
        agent_id="test_agent"
    )
    
    await infra.event_bus.publish(
        event_type=EventType.LLM_CALL_COMPLETED,
        data={
            "message": "LLM вызов завершён",
            "level": "INFO",
            "session_id": "test_session",
            "agent_id": "test_agent",
            "component": "test_llm",
            "provider": "MockLLM",
            "model": "test-model",
            "success": True,
            "elapsed_time": 1.23,
            "result_length": 256
        },
        source="test_llm_provider",
        session_id="test_session",
        agent_id="test_agent"
    )
    
    await infra.event_bus.publish(
        event_type=EventType.LLM_PROMPT_GENERATED,
        data={
            "message": "LLM Prompt: test_component/test_phase",
            "level": "INFO",
            "session_id": "test_session",
            "agent_id": "test_agent",
            "component": "test_component",
            "phase": "test_phase",
            "system_prompt": "Test system prompt",
            "user_prompt": "Test user prompt",
            "prompt_length": 50
        },
        source="test_logger",
        session_id="test_session",
        agent_id="test_agent"
    )
    
    await infra.event_bus.publish(
        event_type=EventType.LLM_RESPONSE_RECEIVED,
        data={
            "message": "LLM Response: test_component/test_phase",
            "level": "INFO",
            "session_id": "test_session",
            "agent_id": "test_agent",
            "component": "test_component",
            "phase": "test_phase",
            "response": "Test response text",
            "tokens": 100,
            "latency_ms": 500
        },
        source="test_logger",
        session_id="test_session",
        agent_id="test_agent"
    )
    
    print("   [OK] События LLM_* опубликованы")
    
    # 5. Ожидание обработки
    print("\n[5/5] Ожидание обработки событий (3 сек)...")
    await asyncio.sleep(3)
    
    # 6. Проверка файлов
    print("\n[6/5] Проверка файлов логов...")
    logs_dir = Path('data/logs')
    if logs_dir.exists():
        files = list(logs_dir.rglob('*.log'))
        print(f"   Найдено файлов: {len(files)}")
        for f in files[:5]:
            print(f"   - {f}")
    else:
        print("   [INFO] Директория data/logs/ не найдена (это нормально если file handler отключён)")
    
    # 7. Завершение
    await infra.shutdown()
    
    print("\n" + "=" * 70)
    print("ТЕСТ ЗАВЕРШЁН")
    print("=" * 70)
    print("\nЕсли вы видите сообщения выше с цветами и иконками - логирование работает!")
    print("Проверьте вывод терминала и файлы в data/logs/ (если включён file handler).")


if __name__ == '__main__':
    # Устанавливаем кодировку UTF-8 для Windows
    if sys.platform == 'win32':
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    
    asyncio.run(test_logging())
