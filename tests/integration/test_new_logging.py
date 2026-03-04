"""
Тест новой системы логирования.

Запускает тестовые события и проверяет, что они записываются в терминал и файлы.
"""
import asyncio
import logging
from pathlib import Path

from core.infrastructure.event_bus.unified_event_bus import UnifiedEventBus
from core.infrastructure.logging import (
    EventBusLogger,
    setup_logging,
    shutdown_logging,
    LoggingConfig,
    TerminalOutputConfig,
    FileOutputConfig,
    LogLevel,
    LogFormat,
)


async def test_logging():
    """Тестирование системы логирования."""
    print("=" * 60)
    print("ТЕСТ НОВОЙ СИСТЕМЫ ЛОГИРОВАНИЯ")
    print("=" * 60)
    
    # Создание EventBus
    event_bus = UnifiedEventBus()
    print("[OK] EventBus создан")
    
    # Настройка конфигурации
    log_config = LoggingConfig(
        terminal=TerminalOutputConfig(
            enabled=True,
            level=LogLevel.DEBUG,  # Включаем DEBUG для теста
            format=LogFormat.COLORED,
            show_debug=True,
            show_source=True,
            show_session_info=True,
        ),
        file=FileOutputConfig(
            enabled=True,
            level=LogLevel.DEBUG,
            format=LogFormat.JSONL,
            base_dir=Path("logs/test_sessions"),
            organize_by_session=True,
            organize_by_date=True,
            max_file_size_mb=100,
            backup_count=10,
        )
    )
    
    # Настройка обработчиков
    terminal_handler, file_handler = setup_logging(event_bus, log_config)
    print("[OK] Обработчики настроены (терминал + файлы)")
    
    # Создание логгера
    logger = EventBusLogger(
        event_bus,
        session_id="test_session_001",
        agent_id="test_agent",
        component="TestLogger"
    )
    print("[OK] EventBusLogger создан")
    
    # Тестовые сообщения
    print("\n" + "=" * 60)
    print("ОТПРАВКА ТЕСТОВЫХ СООБЩЕНИЙ")
    print("=" * 60 + "\n")
    
    await logger.info("INFO: Тестовое сообщение")
    await logger.debug("DEBUG: Отладочная информация")
    await logger.warning("WARNING: Предупреждение")
    await logger.error("ERROR: Ошибка")
    
    # Тест с исключением
    try:
        raise ValueError("Тестовая ошибка")
    except Exception as e:
        await logger.exception("EXCEPTION: Произошло исключение", exc=e)
    
    # Тест LLM событий
    await logger.log_llm_prompt(
        component="TestLLM",
        phase="generation",
        system_prompt="Тестовый системный промпт",
        user_prompt="Тестовый пользовательский промпт"
    )
    
    await logger.log_llm_response(
        component="TestLLM",
        phase="generation",
        response="Тестовый ответ LLM",
        tokens=150,
        latency_ms=234.5
    )
    
    # Тест сессий
    await logger.start_session(goal="Тестовая цель сессии")
    await logger.end_session(success=True, result="Успешно завершено")
    
    # Ожидание записи в файлы
    await asyncio.sleep(0.5)
    
    # Закрытие
    shutdown_logging(file_handler)
    print("\n[OK] Обработчики закрыты")
    
    # Проверка файлов
    test_logs_dir = Path("logs/test_sessions")
    if test_logs_dir.exists():
        print(f"\n[OK] Директория логов создана: {test_logs_dir}")

        # Список файлов
        files = list(test_logs_dir.rglob("*.log"))
        if files:
            print(f"[OK] Файлов создано: {len(files)}")
            for f in files:
                size = f.stat().st_size
                print(f"  - {f.relative_to(test_logs_dir)} ({size} байт)")
        else:
            print("[WARN] Файлы не созданы!")
    else:
        print("[WARN] Директория логов не создана!")
    
    print("\n" + "=" * 60)
    print("ТЕСТ ЗАВЕРШЕН")
    print("=" * 60)


if __name__ == "__main__":
    # Настройка базового logging для отладки
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )
    
    asyncio.run(test_logging())
