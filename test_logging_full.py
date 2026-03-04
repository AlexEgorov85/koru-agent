"""
Полноценный тест системы логирования.

Проверяет запись ВСЕХ файлов:
- common.log (логи INFO/DEBUG/WARNING/ERROR)
- llm.jsonl (LLM вызовы)
- metrics.jsonl (метрики)
"""
import asyncio
import sys
import os
from pathlib import Path

# Установка кодировки UTF-8 для Windows
if sys.platform == 'win32':
    os.system('chcp 65001 >nul')

sys.path.insert(0, str(Path(__file__).parent))

from core.config import get_config
from core.infrastructure.context.infrastructure_context import InfrastructureContext
from core.infrastructure.logging import EventBusLogger, create_session_log_handler
from core.infrastructure.event_bus.unified_event_bus import EventType


async def test_full_logging():
    """Полноценное тестирование системы логирования."""
    print("=" * 60)
    print("ПОЛНОЦЕННЫЙ ТЕСТ СИСТЕМЫ ЛОГИРОВАНИЯ")
    print("=" * 60)
    
    # 1. Загрузка конфигурации
    print("\n[1] Загрузка конфигурации...")
    config = get_config(profile='dev')
    print("    [OK] Конфигурация загружена")
    
    # 2. Инициализация InfrastructureContext
    print("\n[2] Инициализация InfrastructureContext...")
    infra = InfrastructureContext(config)
    success = await infra.initialize()
    
    if not success:
        print("    [ERROR] Ошибка инициализации InfrastructureContext")
        return False
    
    print("    [OK] InfrastructureContext инициализирован")
    print(f"    Session ID: {infra.id}")
    
    # 3. Создание логгера
    print("\n[3] Создание EventBusLogger...")
    logger = EventBusLogger(
        infra.event_bus,
        session_id=infra.id,
        agent_id="test_agent",
        component="TestComponent"
    )
    print("    [OK] Логгер создан")
    
    # 4. Тестирование common.log (логи)
    print("\n[4] Тестирование common.log (INFO/WARNING/ERROR)...")
    await logger.info("Тестовое INFO сообщение")
    await logger.warning("Тестовое WARNING сообщение")
    await logger.error("Тестовое ERROR сообщение")
    print("    [OK] Отправлены логи")
    
    # 5. Тестирование llm.jsonl (LLM вызовы)
    print("\n[5] Тестирование llm.jsonl (LLM вызовы)...")
    
    # Публикуем событие начала LLM вызова
    await infra.event_bus.publish(
        event_type=EventType.LLM_CALL_STARTED,
        data={
            "message": "LLM call started",
            "component": "TestLLMProvider",
            "model": "test-model",
            "session_id": infra.id,
            "agent_id": "test_agent"
        },
        source="TestLLMProvider"
    )
    print("    -> Отправлено LLM_CALL_STARTED")
    
    # Публикуем событие генерации промпта
    await infra.event_bus.publish(
        event_type=EventType.LLM_PROMPT_GENERATED,
        data={
            "message": "LLM prompt generated",
            "component": "TestLLMProvider",
            "system_prompt": "You are a helpful assistant",
            "user_prompt": "Hello, how are you?",
            "prompt_length": 50,
            "session_id": infra.id,
            "agent_id": "test_agent"
        },
        source="TestLLMProvider"
    )
    print("    -> Отправлено LLM_PROMPT_GENERATED")
    
    # Публикуем событие получения ответа
    await infra.event_bus.publish(
        event_type=EventType.LLM_RESPONSE_RECEIVED,
        data={
            "message": "LLM response received",
            "component": "TestLLMProvider",
            "response": "I'm fine, thank you!",
            "tokens": 10,
            "latency_ms": 150.5,
            "session_id": infra.id,
            "agent_id": "test_agent"
        },
        source="TestLLMProvider"
    )
    print("    -> Отправлено LLM_RESPONSE_RECEIVED")
    
    # Публикуем событие завершения LLM вызова
    await infra.event_bus.publish(
        event_type=EventType.LLM_CALL_COMPLETED,
        data={
            "message": "LLM call completed",
            "component": "TestLLMProvider",
            "success": True,
            "session_id": infra.id,
            "agent_id": "test_agent"
        },
        source="TestLLMProvider"
    )
    print("    -> Отправлено LLM_CALL_COMPLETED")
    
    # 6. Тестирование metrics.jsonl (метрики)
    print("\n[6] Тестирование metrics.jsonl (метрики)...")
    
    await infra.event_bus.publish(
        event_type=EventType.METRIC_COLLECTED,
        data={
            "message": "Metric collected",
            "metric_name": "test_metric",
            "metric_value": 42.5,
            "metric_type": "counter",
            "component": "TestComponent",
            "session_id": infra.id,
            "agent_id": "test_agent"
        },
        source="TestMetricsCollector"
    )
    print("    -> Отправлено METRIC_COLLECTED")
    
    await infra.event_bus.publish(
        event_type=EventType.METRIC_COLLECTED,
        data={
            "message": "Metric collected",
            "metric_name": "execution_time",
            "metric_value": 1.234,
            "metric_type": "gauge",
            "unit": "seconds",
            "component": "TestComponent",
            "session_id": infra.id,
            "agent_id": "test_agent"
        },
        source="TestMetricsCollector"
    )
    print("    -> Отправлено ещё одно METRIC_COLLECTED")
    
    # 7. Создание SessionLogHandler
    print("\n[7] Создание SessionLogHandler...")
    session_log_handler = create_session_log_handler(
        event_bus=infra.event_bus,
        session_id=infra.id,
        agent_id="test_agent"
    )
    session_info = session_log_handler.get_session_info()
    
    await logger.info(f"Logs folder: {session_info['session_folder']}")
    print("    [OK] SessionLogHandler активирован")
    print(f"    Папка сессии: {session_info['session_folder']}")
    
    # 8. Ожидание обработки событий
    print("\n[8] Ожидание обработки событий (1 сек)...")
    await asyncio.sleep(1.0)
    
    # 9. Завершение сессии
    print("\n[9] Завершение сессии...")
    await logger.info("Завершение тестовой сессии")
    await session_log_handler.shutdown()
    
    # 10. Остановка инфраструктуры
    print("\n[10] Остановка InfrastructureContext...")
    await infra.shutdown()
    
    print("\n" + "=" * 60)
    print("ТЕСТ ЗАВЕРШЁН")
    print("=" * 60)
    
    # 11. Проверка результатов
    print("\nПРОВЕРКА РЕЗУЛЬТАТОВ:")
    print(f"  Папка сессии: {session_info['session_folder']}")
    
    session_path = Path(session_info['session_folder'])
    if session_path.exists():
        files = list(session_path.glob("*.log")) + list(session_path.glob("*.jsonl"))
        print(f"\n  Файлы в папке сессии:")
        for f in sorted(files):
            print(f"    - {f.name} ({f.stat().st_size} байт)")
        
        # Проверка каждого файла
        print("\n  Содержимое файлов:")
        
        # common.log
        common_log = session_path / "common.log"
        if common_log.exists():
            lines = common_log.read_text(encoding='utf-8').strip().split('\n')
            print(f"\n    [common.log] - {len(lines)} записей:")
            for line in lines[-3:]:  # Последние 3
                import json
                try:
                    data = json.loads(line)
                    print(f"      - {data.get('event_type')}: {data.get('message', '')[:50]}")
                except:
                    print(f"      - {line[:60]}...")
        else:
            print("    [common.log] - НЕ СОЗДАН")
        
        # llm.jsonl
        llm_log = session_path / "llm.jsonl"
        if llm_log.exists():
            lines = llm_log.read_text(encoding='utf-8').strip().split('\n')
            print(f"\n    [llm.jsonl] - {len(lines)} записей:")
            for line in lines[-3:]:  # Последние 3
                import json
                try:
                    data = json.loads(line)
                    print(f"      - {data.get('event_type')}: {data.get('message', '')[:50]}")
                except:
                    print(f"      - {line[:60]}...")
        else:
            print("    [llm.jsonl] - НЕ СОЗДАН")
        
        # metrics.jsonl
        metrics_log = session_path / "metrics.jsonl"
        if metrics_log.exists():
            lines = metrics_log.read_text(encoding='utf-8').strip().split('\n')
            print(f"\n    [metrics.jsonl] - {len(lines)} записей:")
            for line in lines[-2:]:  # Последние 2
                import json
                try:
                    data = json.loads(line)
                    print(f"      - {data.get('metric_name')}: {data.get('metric_value')}")
                except:
                    print(f"      - {line[:60]}...")
        else:
            print("    [metrics.jsonl] - НЕ СОЗДАН")
    else:
        print(f"  [ERROR] Папка сессии не найдена: {session_path}")
    
    return True


if __name__ == "__main__":
    try:
        asyncio.run(test_full_logging())
    except KeyboardInterrupt:
        print("\n\nТест прерван пользователем")
    except Exception as e:
        print(f"\n\n[ERROR] Ошибка теста: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
