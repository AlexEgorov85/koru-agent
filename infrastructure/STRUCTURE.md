# Структура инфраструктурного слоя

## Принцип организации
Инфраструктура разделена по типу компонентов без избыточной вложенности:

1. **`tools/`** — Инструменты (реализации ITool)
   - file_tools/ — файловые инструменты
     - file_reader_tool.py — чтение файлов
     - file_lister_tool.py — список файлов
     - file_writer_tool.py — запись файлов
     - safe_file_reader_tool.py — безопасное чтение файлов
   - code_analysis_tools/ — инструменты анализа кода
     - ast_parser_tool.py — парсер AST
   - database_tools/ — инструменты работы с базами данных
     - sql_tool.py — SQL инструмент
   - code_analysis/ — анализ кода
   - filesystem/ — файловая система

2. **`skills/`** — Навыки (реализации ISkill) и связанные файлы
   - planning_skill.py — основной файл навыка планирования
   - planning_models.py — модели для планирования
   - planning_prompt_templates.py — шаблоны промтов для планирования
   - project_navigator_skill.py — основной файл навыка навигации по проекту
   - project_navigator_models.py — модели для навигации
   - project_navigator_adapters.py — адаптеры для навигации
   - project_map_skill.py — основной файл навыка создания карты проекта
   - project_map_models.py — модели для создания карты
   - project_map_adapters.py — адаптеры для создания карты
   → Все файлы связанного навыка находятся в одном месте (без вложенных папок)

3. **`gateways/`** — Шлюзы к внешним системам (сгруппированы по типу)
   - llm/ — интеграция с LLM
     - llm_execution_gateway.py — шлюз выполнения для LLM
     - execution/ — выполнение
     - base_provider.py, llama_cpp_provider.py, provider_factory.py — провайдеры LLM
   - db/ — интеграция с базами данных
     - base_provider.py, postgresql_provider.py — провайдеры БД
   - filesystem/ — безопасная работа с ФС
   - event/ — система событий
     - event_bus_adapter.py, event_system.py, event_publisher_adapter.py — компоненты событийной системы
   - api/ — внешние API

4. **`repositories/`** — Хранилища данных
   - prompt_repository.py — версионность промтов
   - benchmark_repository_impl.py — результаты бенчмарков
   - in_memory_prompt_repository.py — in-memory репозиторий промтов
   - data_adapters/ — адаптеры данных
     - benchmark_data_adapter.py — адаптер данных бенчмарков
     - code_unit_adapter.py — адаптер единиц кода
     - project_structure_adapter.py — адаптер структуры проекта

5. **`config/`** — Конфигурация
   - config_manager.py — управление конфигурацией

6. **`contexts/`** — Инфраструктурные реализации контекстов (реализации интерфейсов из domain/)
   - system/ — инфраструктурные реализации системного контекста
     - enhanced_system_context.py — расширенная реализация системного контекста
     - skill_registry.py — реализация реестра навыков
     - tool_registry.py — реализация реестра инструментов
     - system_context.py — основная реализация системного контекста
   → Интерфейсы находятся в domain/abstractions/system/ (чистая архитектура)

7. **`factories/`** — Фабрики создания компонентов
   - agent_factory.py, skill_factory.py, tool_factory.py — фабрики основных компонентов
   - execution_gateway_factory.py, pattern_executor_factory.py — фабрики шлюзов и исполнителей
   - pattern_executor.py — исполнитель паттернов (перемещен из adapters)

8. **`services/`** — Сервисы
   - code_analysis/ — анализ кода
   - prompt_renderer/ — рендеринг промтов
   - prompt_services/ — сервисы для работы с промтами
     - prompt_sync_service.py — синхронизация промтов
   - utility_services/ — утилитарные сервисы
     - text_similarity_service.py — сервис оценки схожести текстов
   - system_services/ — системные сервисы
     - system_initialization_service.py — инициализация системы

9. **`testing/` — Тестовые компоненты
   - db/ — тестовые провайдеры БД
   - llm/ — тестовые провайдеры LLM

10. **`to_refactor/`** — Компоненты требующие ручной обработки
    - prompt_loader.py — требуется инкапсуляция в репозитории

11. **`database/`** — SQL-скрипты
    - prompt_tables.sql — таблицы промтов

## Изменения в этой версии
- Устранена избыточная вложенность навыков (было: `adapters/skills/planning/skill.py` → стало: `skills/planning_skill.py`)
- Вспомогательные файлы навыков также перемещены в папку skills для лучшей организации
- Шлюзы сгруппированы по типу внешней системы для упрощения навигации
- Загрузчики промтов помечены для инкапсуляции внутри репозиториев
- Сервисы организованы в логические подгруппы
- Удалены пустые промежуточные папки (`adapters/`, `adapters/skills/`, и т.д.)
- Адаптеры данных перемещены в `repositories/data_adapters/`
- Файловые инструменты сгруппированы в `tools/file_tools/`
- Тестовые провайдеры сгруппированы в `testing/`
- Системные компоненты сгруппированы в `contexts/system/`