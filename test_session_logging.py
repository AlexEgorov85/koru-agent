"""
Тест: проверка что SessionLogHandler записывает LLM события при запуске через asyncio.run()
(имитация веб-сценария)
"""
import asyncio
import json
from pathlib import Path

async def test_session_llm_logging():
    from core.config import get_config
    from core.infrastructure_context.infrastructure_context import InfrastructureContext
    from core.infrastructure.event_bus.unified_event_bus import EventType

    config = get_config(profile='prod', data_dir='data')
    infra = InfrastructureContext(config)
    await infra.initialize()
    
    print(f"EventBus: {type(infra.event_bus).__name__}")
    print(f"SessionHandler: {infra.session_handler}")
    print(f"All subscribers count: {len(infra.event_bus._all_subscribers)}")
    
    # Подсчитаем подписчиков на LLM события
    llm_prompt_subs = [s for s in infra.event_bus._all_subscribers 
                       if hasattr(s, 'handler') and 'on_event' in str(s.handler)]
    print(f"All subscribers with 'on_event': {len(llm_prompt_subs)}")
    
    # Проверим _subscribers по типам событий
    llm_prompt_type = EventType.LLM_PROMPT_GENERATED.value
    llm_response_type = EventType.LLM_RESPONSE_RECEIVED.value
    
    print(f"Subscribers for {llm_prompt_type}: {len(infra.event_bus._subscribers.get(llm_prompt_type, []))}")
    print(f"Subscribers for {llm_response_type}: {len(infra.event_bus._subscribers.get(llm_response_type, []))}")
    
    # Публикуем тестовое LLM событие
    print("\nПубликация тестового LLM события...")
    await infra.event_bus.publish(
        EventType.LLM_PROMPT_GENERATED,
        data={
            "call_id": "test_call_1",
            "session_id": "test_session_1",
            "agent_id": "agent_001",
            "system_prompt": "test system",
            "user_prompt": "test user",
            "prompt_length": 100,
        },
        source="test",
        session_id="test_session_1",
        agent_id="agent_001"
    )
    
    # Ждём немного
    await asyncio.sleep(0.5)
    
    # Проверяем файл логов
    session_log = infra.session_handler.session_log_path
    if session_log.exists():
        with open(session_log, 'r', encoding='utf-8') as f:
            events = [json.loads(line) for line in f if line.strip()]
        print(f"\nЗаписано событий в {session_log}: {len(events)}")
        for e in events[-5:]:
            print(f"  - {e.get('event_type', 'unknown')}")
    else:
        print(f"\nФайл логов не найден: {session_log}")
    
    await infra.shutdown()

if __name__ == "__main__":
    asyncio.run(test_session_llm_logging())
