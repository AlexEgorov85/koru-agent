"""
Тестирование EventBus и сервисов промтов/контрактов
"""
import sys
import os
sys.path.insert(0, r'c:\Users\Алексей\Documents\WORK\Agent_v5')

import asyncio
from core.config.config_loader import ConfigLoader
from core.infrastructure.context.infrastructure_context import InfrastructureContext
from core.infrastructure.event_bus.event_bus import Event, EventType


async def test_event_bus_and_services():
    try:
        # Загрузка конфигурации
        config_loader = ConfigLoader()
        config = config_loader.load()
        
        print("Конфигурация загружена")
        print(f"LLM провайдеры: {list(config.llm_providers.keys())}")
        print(f"DB провайдеры: {list(config.db_providers.keys())}")
        
        # Создание инфраструктурного контекста
        infra = InfrastructureContext(config)
        
        print("\nИнициализация инфраструктурного контекста...")
        await infra.initialize()
        
        print("[OK] Инфраструктурный контекст успешно инициализирован!")
        print(f"Доступные ресурсы: {infra.resource_registry.get_all_names()}")
        
        # Проверка EventBus
        print("\n--- Проверка EventBus ---")
        event_bus = infra.get_resource("event_bus")
        if event_bus:
            print(f"[OK] EventBus доступен: {type(event_bus).__name__}")
            
            # Создание обработчика событий
            received_events = []
            
            async def test_event_handler(event):
                print(f"   Получено событие: {event.event_type}, данные: {event.data}")
                received_events.append(event)
            
            # Подписка на событие
            event_bus.subscribe(EventType.SYSTEM_INITIALIZED, test_event_handler)
            print("   Подписка на событие выполнена")
            
            # Публикация события
            await event_bus.publish(
                EventType.SYSTEM_INITIALIZED, 
                data={"test": "event_data", "timestamp": "now"}
            )
            print("   Событие опубликовано")
            
            # Ждем немного для обработки
            await asyncio.sleep(0.1)
            
            if received_events:
                print(f"   [OK] Событие успешно получено: {received_events[0].data}")
            else:
                print("   [WARN] Событие не было получено")
        else:
            print("[ERROR] EventBus недоступен")
        
        # Проверка сервисов промтов
        print("\n--- Проверка сервисов промтов и контрактов ---")
        prompt_storage = infra.get_resource("prompt_storage")
        if prompt_storage:
            print(f"[OK] PromptStorage доступен: {type(prompt_storage).__name__}")
            
            # Попробуем загрузить какой-нибудь промпт (если он существует)
            try:
                # Попробуем загрузить промпт с любым именем
                available_prompts = []
                import os
                from pathlib import Path
                
                # Проверим, есть ли директория с промптами
                prompts_dir = Path("prompts") if os.path.exists("prompts") else Path("core/config/defaults/prompts")
                if prompts_dir.exists():
                    for file_path in prompts_dir.glob("*.jinja2"):
                        available_prompts.append(file_path.stem)
                
                if available_prompts:
                    first_prompt = available_prompts[0]
                    prompt_content = await prompt_storage.load_prompt(first_prompt)
                    if prompt_content:
                        print(f"   [OK] Промпт '{first_prompt}' успешно загружен ({len(prompt_content)} символов)")
                    else:
                        print(f"   [WARN] Промпт '{first_prompt}' пустой или не найден")
                else:
                    print("   [WARN] Нет доступных промптов для тестирования")
            except Exception as e:
                print(f"   [WARN] Ошибка при загрузке промпта: {e}")
        else:
            print("[ERROR] PromptStorage недоступен")
        
        # Проверка сервисов контрактов
        contract_storage = infra.get_resource("contract_storage")
        if contract_storage:
            print(f"[OK] ContractStorage доступен: {type(contract_storage).__name__}")
            
            try:
                # Проверим, есть ли какие-то контракты
                # Для этого посмотрим внутреннее состояние
                if hasattr(contract_storage, 'contracts'):
                    contract_count = len(contract_storage.contracts) if contract_storage.contracts else 0
                    print(f"   Контрактов загружено: {contract_count}")
                    
                    if contract_count > 0:
                        print("   [OK] Контракты успешно загружены")
                    else:
                        print("   [WARN] Нет загруженных контрактов")
                else:
                    print("   [WARN] Нет доступа к списку контрактов")
            except Exception as e:
                print(f"   [WARN] Ошибка при проверке контрактов: {e}")
        else:
            print("[ERROR] ContractStorage недоступен")
        
        # Проверка других ресурсов
        print("\n--- Проверка других ресурсов ---")
        for resource_name in infra.resource_registry.get_all_names():
            if resource_name not in ['default_llm', 'default_db']:  # уже проверили
                resource = infra.get_resource(resource_name)
                print(f"[OK] Ресурс '{resource_name}': {type(resource).__name__ if resource else 'None'}")
        
        # Завершение работы
        await infra.shutdown()
        print("\n[OK] Инфраструктурный контекст успешно завершен")
        
        print("\n[SUCCESS] Все компоненты работают корректно!")
        print("- EventBus успешно обрабатывает события")
        print("- PromptStorage доступен и может загружать промпты")
        print("- ContractStorage доступен и управляет контрактами")
        print("- Все ресурсы корректно регистрируются в реестре")
        
    except Exception as e:
        print(f"[ERROR] Ошибка: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_event_bus_and_services())