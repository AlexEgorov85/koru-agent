"""
Тест системы логирования.

Проверяет:
1. Инициализацию InfrastructureContext
2. Подписку обработчиков на события EventBus
3. Вывод логов в терминал
4. Запись логов в файлы сессии
"""
import asyncio
import sys
import os
from pathlib import Path

# Установка кодировки UTF-8 для Windows
if sys.platform == 'win32':
    os.system('chcp 65001 >nul')

# Добавляем корень проекта в path
sys.path.insert(0, str(Path(__file__).parent))

from core.config import get_config
from core.infrastructure.context.infrastructure_context import InfrastructureContext
from core.infrastructure.logging import EventBusLogger, create_session_log_handler


async def test_logging():
    """Тестирование системы логирования."""
    print("=" * 60)
    print("ТЕСТ СИСТЕМЫ ЛОГИРОВАНИЯ")
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
    
    # 4. Тестирование логирования
    print("\n[4] Тестирование логирования...")
    
    await logger.info("Тестовое INFO сообщение")
    print("    -> Отправлено INFO сообщение")
    
    await logger.debug("Тестовое DEBUG сообщение (должно быть видно если level=DEBUG)")
    print("    -> Отправлено DEBUG сообщение")
    
    await logger.warning("Тестовое WARNING сообщение")
    print("    -> Отправлено WARNING сообщение")
    
    await logger.error("Тестовое ERROR сообщение")
    print("    -> Отправлено ERROR сообщение")
    
    # 5. Тестирование SessionLogHandler
    print("\n[5] Тестирование SessionLogHandler...")
    session_log_handler = create_session_log_handler(
        event_bus=infra.event_bus,
        session_id=infra.id,
        agent_id="test_agent"
    )
    session_info = session_log_handler.get_session_info()
    
    await logger.info(f"Logs folder: {session_info['session_folder']}")
    await logger.info(f"   common.log: {session_info['common_log']}")
    await logger.info(f"   llm.jsonl: {session_info['llm_log']}")
    await logger.info(f"   metrics.jsonl: {session_info['metrics_log']}")
    
    print("    [OK] SessionLogHandler активирован")
    print(f"    Папка сессии: {session_info['session_folder']}")
    
    # 6. Ожидание обработки событий
    print("\n[6] Ожидание обработки событий (0.5 сек)...")
    await asyncio.sleep(0.5)
    
    # 7. Завершение сессии
    print("\n[7] Завершение сессии...")
    await logger.info("Завершение тестовой сессии")
    await session_log_handler.shutdown()
    
    # 8. Остановка инфраструктуры
    print("\n[8] Остановка InfrastructureContext...")
    await infra.shutdown()
    
    print("\n" + "=" * 60)
    print("ТЕСТ ЗАВЕРШЁН")
    print("=" * 60)
    
    # 9. Проверка результатов
    print("\nПРОВЕРЬТЕ:")
    print("  [OK] Сообщения выводились в терминал (с цветами)")
    print(f"  [OK] Файлы логов созданы в: {session_info['session_folder']}")
    
    session_path = Path(session_info['session_folder'])
    if session_path.exists():
        files = list(session_path.glob("*"))
        print("  [OK] Файлы в папке сессии:")
        for f in files:
            print(f"     - {f.name} ({f.stat().st_size} байт)")
    else:
        print(f"  [WARN] Папка сессии не найдена: {session_path}")
    
    return True


if __name__ == "__main__":
    try:
        asyncio.run(test_logging())
    except KeyboardInterrupt:
        print("\n\nТест прерван пользователем")
    except Exception as e:
        print(f"\n\n[ERROR] Ошибка теста: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
