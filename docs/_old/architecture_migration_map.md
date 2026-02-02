# Карта миграции архитектуры проекта

## 1. Обзор текущей структуры

На основе анализа файловой структуры проекта, представленной в environment_details, составлен следующий список файлов с описанием их роли:

## 2. Целевая архитектура (Domain / Application / Infrastructure / Interfaces)

Целевая архитектура проекта следует принципам Clean Architecture и разделяет код на следующие слои:

### Domain (Область)
Содержит бизнес-логику и модели предметной области:
- Модели данных, специфичные для предметной области
- Бизнес-правила
- Сущности и объекты значения
- Репозитории (в виде интерфейсов)

Файлы, относящиеся к этому слою:
- models/*.py (все модели данных)
- core/agent_runtime/model.py
- core/agent_runtime/states.py
- core/atomic_actions/actions.py
- core/atomic_actions/base.py
- core/domain_management/domain_manager.py
- core/skills/planning/schema.py
- core/skills/project_map/schema.py
- core/skills/project_map/models/*
- core/skills/project_navigator/schema.py
- core/skills/project_navigator/models/*
- core/skills/sql_generator/schema.py
- core/skills/table_description/schema.py
- core/session_context/model.py

### Application (Приложение)
Содержит логику приложения и координацию между слоями:
- Юзкейсы
- Стратегии выполнения
- Сценарии использования
- Адаптеры задач
- Компоновщики паттернов

Файлы, относящиеся к этому слою:
- core/composable_agent.py
- core/agent_runtime/*
- core/atomic_actions/executor.py
- core/composable_patterns/*
- core/domain_management/prompt_adapter.py
- core/retry_policy/*
- core/session_context/*
- core/skills/*
- core/system_context/*

### Infrastructure (Инфраструктура)
Содержит внешние зависимости и реализации технических компонентов:
- Реализации провайдеров (LLM, баз данных)
- Сервисы взаимодействия с внешними системами
- Инструменты (tools)
- Внешние API и протоколы

Файлы, относящиеся к этому слою:
- core/infrastructure/*
- core/dependency_container.py
- core/system_context/llm_caller.py
- core/system_context/database_gateway.py
- core/system_context/event_bus.py
- analyze_code_error.py
- analyze_file.py

### Interfaces (Интерфейсы)
Содержит точки взаимодействия с внешними системами и пользователями:
- API контроллеры
- UI компоненты
- Адаптеры для различных источников данных
- Интерфейсы взаимодействия

Файлы, относящиеся к этому слою:
- core/agent_runtime/interfaces.py
- core/agent_runtime/runtime_interface.py
- core/skills/project_map/adapters.py
- core/skills/project_navigator/adapters.py
- core/system_context/agent_step_display_handler.py
- core/system_context/interfaces.py
- server.js

### Config (Конфигурация)
Содержит настройки и конфигурации приложения:
- Файлы конфигурации
- Настройки сред выполнения
- Определения зависимостей

Файлы, относящиеся к этому слою:
- requirements.txt
- .gitignore
- core/config/*
- *.md файлы (документация)

### Tests (Тесты)
Содержит все тесты приложения:
- Модульные тесты
- Интеграционные тесты
- E2E тесты
- Фикстуры

Файлы, относящиеся к этому слою:
- tests/*
- test_*.py файлы

## 3. Таблица сопоставления файлов

| Текущий файл | Целевой слой | Почему |
| ------------ | ------------ | ------ |
| .gitignore | config | Файл конфигурации для Git, определяющий игнорируемые файлы |
| 0.4.4 | config | Файл версии проекта |
| analyze_code_error.py | infrastructure | Содержит функции для анализа ошибок кода, что относится к инфраструктуре |
| analyze_file.py | infrastructure | Содержит функции для анализа файлов проекта |
| COMPLETION_REPORT.md | documentation | Отчет о проделанной работе |
| example_usage.py | examples | Пример использования системы |
| main.py | application | Главный файл запуска приложения, точка входа |
| PROJECT_ARCHITECTURE_AND_IMPLEMENTATION.md | documentation | Документация по архитектуре и реализации |
| project_navigator.py | application | Функции навигации по проекту |
| readme.md | documentation | Основная документация проекта |
| requirements.txt | config | Зависимости проекта |
| server.js | interfaces | Серверный файл для веб-интерфейса |
| solid_analysis_report.md | documentation | Отчет по анализу SOLID принципов |
| solid_refactor_plan.md | documentation | План рефакторинга по SOLID принципам |
| test_main.py | tests | Тесты основного приложения |
| test_new_architecture.py | tests | Тесты новой архитектуры |
| test_sql_skill_integration.py | tests | Тесты интеграции SQL навыка |
| Untitled.ipynb | experiments | Jupyter notebook для экспериментов |
| core/__init__.py | config | Инициализация пакета core |
| core/composable_agent.py | application | Реализация компонуемого агента |
| core/dependency_container.py | infrastructure | Контейнер зависимостей |
| core/agent_runtime/__init__.py | config | Инициализация пакета runtime |
| core/agent_runtime/base_agent_runtime.py | application | Базовая реализация runtime агента |
| core/agent_runtime/checkpoint.py | application | Управление контрольными точками |
| core/agent_runtime/execution_context.py | application | Контекст выполнения задач |
| core/agent_runtime/executor.py | application | Исполнитель задач |
| core/agent_runtime/interfaces.py | interfaces | Интерфейсы runtime |
| core/agent_runtime/model.py | domain | Модели данных runtime |
| core/agent_runtime/pattern_selector.py | application | Выбор шаблонов выполнения |
| core/agent_runtime/policy.py | application | Политики выполнения |
| core/agent_runtime/progress.py | application | Отслеживание прогресса |
| core/agent_runtime/runtime_interface.py | interfaces | Интерфейс runtime |
| core/agent_runtime/runtime.py | application | Основная реализация runtime |
| core/agent_runtime/state.py | application | Управление состоянием |
| core/agent_runtime/states.py | domain | Определение состояний агента |
| core/agent_runtime/strategy_loader.py | application | Загрузчик стратегий |
| core/agent_runtime/task_adapter.py | application | Адаптер задач |
| core/agent_runtime/task_scheduler.py | application | Планировщик задач |
| core/agent_runtime/thinking_patterns/__init__.py | config | Инициализация пакета thinking_patterns |
| core/agent_runtime/thinking_patterns/base.py | application | Базовые классы шаблонов мышления |
| core/agent_runtime/thinking_patterns/evaluation_composable.py | application | Компонуемые шаблоны оценки |
| core/agent_runtime/thinking_patterns/evaluation.py | application | Шаблоны оценки |
| core/agent_runtime/thinking_patterns/fallback.py | application | Резервные шаблоны |
| core/agent_runtime/thinking_patterns/code_analysis/ | application | Шаблоны анализа кода |
| core/agent_runtime/thinking_patterns/plan_execution/ | application | Шаблоны планирования и выполнения |
| core/agent_runtime/thinking_patterns/planning/ | application | Шаблоны планирования |
| core/agent_runtime/thinking_patterns/react/ | application | Шаблоны реакции |
| core/atomic_actions/__init__.py | config | Инициализация пакета atomic_actions |
| core/atomic_actions/actions.py | domain | Атомарные действия |
| core/atomic_actions/base.py | domain | Базовые классы атомарных действий |
| core/atomic_actions/executor.py | application | Исполнитель атомарных действий |
| core/composable_patterns/__init__.py | config | Инициализация пакета composable_patterns |
| core/composable_patterns/base.py | application | Базовые классы компонуемых паттернов |
| core/composable_patterns/patterns.py | application | Реализация компонуемых паттернов |
| core/composable_patterns/registry.py | application | Реестр компонуемых паттернов |
| core/composable_patterns/state_manager.py | application | Управление состоянием паттернов |
| core/config/__init__.py | config | Инициализация пакета config |
| core/config/config_loader.py | config | Загрузчик конфигураций |
| core/config/models.py | config | Модели конфигураций |
| core/config/defaults/ | config | Конфигурации по умолчанию |
| core/domain_management/__init__.py | config | Инициализация пакета domain_management |
| core/domain_management/domain_manager.py | domain | Управление доменами |
| core/domain_management/prompt_adapter.py | application | Адаптер промптов |
| core/infrastructure/providers/ | infrastructure | Провайдеры инфраструктуры |
| core/infrastructure/providers/database/ | infrastructure | Провайдеры баз данных |
| core/infrastructure/providers/llm/ | infrastructure | Провайдеры LLM |
| core/infrastructure/services/ | infrastructure | Инфраструктурные сервисы |
| core/infrastructure/services/__init__.py | config | Инициализация пакета services |
| core/infrastructure/services/base_service.py | infrastructure | Базовый класс сервиса |
| core/infrastructure/services/code_analysis/ | infrastructure | Сервисы анализа кода |
| core/infrastructure/tools/ | infrastructure | Инфраструктурные инструменты |
| core/infrastructure/tools/__init__.py | config | Инициализация пакета tools |
| core/infrastructure/tools/ast_parser_tool.py | infrastructure | Инструмент парсинга AST |
| core/infrastructure/tools/base_tool.py | infrastructure | Базовый класс инструмента |
| core/infrastructure/tools/file_lister_tool.py | infrastructure | Инструмент для просмотра файлов |
| core/infrastructure/tools/file_reader_tool.py | infrastructure | Инструмент для чтения файлов |
| core/infrastructure/tools/file_writer_tool.py | infrastructure | Инструмент для записи файлов |
| core/infrastructure/tools/sql_tool.py | infrastructure | SQL инструмент |
| core/retry_policy/__init__.py | config | Инициализация пакета retry_policy |
| core/retry_policy/retry_and_error_policy.py | application | Политики повтора и обработки ошибок |
| core/retry_policy/utils.py | application | Утилиты для политик повтора |
| core/session_context/__init__.py | config | Инициализация пакета session_context |
| core/session_context/base_session_context.py | application | Базовый класс контекста сессии |
| core/session_context/data_context.py | application | Контекст данных сессии |
| core/session_context/model.py | domain | Модель контекста сессии |
| core/session_context/session_context.py | application | Реализация контекста сессии |
| core/session_context/step_context.py | application | Контекст шага выполнения |
| core/skills/__init__.py | config | Инициализация пакета skills |
| core/skills/base_skill.py | application | Базовый класс навыка |
| core/skills/planning/ | application | Навык планирования |
| core/skills/planning/prompt.py | application | Промпт для планирования |
| core/skills/planning/schema.py | domain | Схема планирования |
| core/skills/planning/skill.py | application | Реализация навыка планирования |
| core/skills/project_map/ | application | Навык картографирования проекта |
| core/skills/project_map/__init__.py | config | Инициализация навыка карты проекта |
| core/skills/project_map/adapters.py | interfaces | Адаптеры для навыка карты проекта |
| core/skills/project_map/schema.py | domain | Схема данных для карты проекта |
| core/skills/project_map/skill.py | application | Реализация навыка карты проекта |
| core/skills/project_map/models/ | domain | Модели данных для карты проекта |
| core/skills/project_navigator/ | application | Навык навигации по проекту |
| core/skills/project_navigator/__init__.py | config | Инициализация навыка навигации по проекту |
| core/skills/project_navigator/adapters.py | interfaces | Адаптеры для навыка навигации |
| core/skills/project_navigator/prompt.py | application | Промпт для навигации по проекту |
| core/skills/project_navigator/schema.py | domain | Схема данных для навигации по проекту |
| core/skills/project_navigator/skill.py | application | Реализация навыка навигации по проекту |
| core/skills/project_navigator/utils.py | application | Утилиты для навигации по проекту |
| core/skills/project_navigator/models/ | domain | Модели данных для навигации по проекту |
| core/skills/sql_generator/ | application | Навык генерации SQL |
| core/skills/sql_generator/__init__.py | config | Инициализация навыка генерации SQL |
| core/skills/sql_generator/schema.py | domain | Схема данных для генерации SQL |
| core/skills/sql_generator/skill.py | application | Реализация навыка генерации SQL |
| core/skills/table_description/ | application | Навык описания таблиц |
| core/skills/table_description/schema.py | domain | Схема данных для описания таблиц |
| core/skills/table_description/skill.py | application | Реализация навыка описания таблиц |
| core/system_context/__init__.py | config | Инициализация пакета system_context |
| core/system_context/agent_factory.py | application | Фабрика агентов |
| core/system_context/agent_step_display_handler.py | interfaces | Обработчик отображения шагов агента |
| core/system_context/base_system_contex.py | application | Базовый класс системного контекста |
| core/system_context/capability_registry.py | application | Реестр возможностей |
| core/system_context/database_gateway.py | infrastructure | Шлюз базы данных |
| core/system_context/event_bus.py | infrastructure | Шина событий |
| core/system_context/execution_gateway.py | application | Шлюз выполнения |
| core/system_context/factory.py | application | Общая фабрика |
| core/system_context/interfaces.py | interfaces | Интерфейсы системного контекста |
| core/system_context/lifecycle_manager.py | application | Управление жизненным циклом |
| core/system_context/llm_caller.py | infrastructure | Вызов LLM |
| core/system_context/resource_manager.py | application | Управление ресурсами |
| core/system_context/resource_registry.py | application | Реестр ресурсов |
| core/system_context/system_context.py | application | Реализация системного контекста |
| docs/composable_agent_documentation.md | documentation | Документация по компонуемому агенту |
| docs/event_bus_documentation.md | documentation | Документация по шине событий |
| docs/new_architecture_overview.md | documentation | Обзор новой архитектуры |
| docs/refactor_inventory.md | documentation | Инвентарь рефакторинга |
| examples/agent_step_display_example.py | examples | Пример отображения шагов агента |
| examples/atomic_action_executor_example.py | examples | Пример исполнителя атомарных действий |
| examples/composable_agent_example.py | examples | Пример компонуемого агента |
| examples/event_bus_example.py | examples | Пример шины событий |
| examples/sql_generator_example.py | examples | Пример генератора SQL |
| models/agent_state.py | domain | Модель состояния агента |
| models/capability.py | domain | Модель возможностей |
| models/code_unit_model.py | domain | Модель единицы кода |
| models/code_unit.py | domain | Модель единицы кода |
| models/composable_pattern_state.py | domain | Модель состояния компонуемого паттерна |
| models/config.py | domain | Модель конфигурации |
| models/db_types.py | domain | Типы баз данных |
| models/execution_state.py | domain | Модель состояния выполнения |
| models/execution_strategy.py | domain | Модель стратегии выполнения |
| models/execution.py | domain | Модель выполнения |
| models/llm_types.py | domain | Типы LLM |
| models/progress.py | domain | Модель прогресса |
| models/resource.py | domain | Модель ресурса |
| models/retry_policy.py | domain | Модель политики повтора |
| models/structured_actions.py | domain | Модель структурированных действий |
| tests/conftest.py | tests | Конфигурация тестов |
| tests/test_agent_subagent_integration.py | tests | Тесты интеграции агента и субагентов |
| tests/test_sql_generator_integration.py | tests | Тесты интеграции генератора SQL |
| tests/test_sql_generator_skill.py | tests | Тесты навыка генерации SQL |
| tests/test_subagent_integration.py | tests | Тесты интеграции субагентов |
| tests/test_subagent_scenario.py | tests | Тесты сценариев субагентов |
| tests/e2e/ | tests | Сквозные тесты |
| tests/integration/ | tests | Интеграционные тесты |
| tests/integration/providers/ | tests | Тесты провайдеров |
| tests/integration/services/ | tests | Тесты сервисов |
| tests/unit/ | tests | Модульные тесты |
| tests/unit/core/ | tests | Модульные тесты ядра |
| tests/unit/core/test_agent_step_display_handler.py | tests | Тесты обработчика отображения шагов |
| tests/unit/core/test_atomic_action_executor.py | tests | Тесты исполнителя атомарных действий |
| tests/unit/core/test_composable_agent.py | tests | Тесты компонуемого агента |
| tests/unit/core/test_event_bus.py | tests | Тесты шины событий |
| tests/unit/core/test_retry_and_error_policy.py | tests | Тесты политик повтора |
| tests/unit/core/test_system_context_integration.py | tests | Тесты интеграции системного контекста |
| tests/unit/core/runtime/ | tests | Тесты runtime |
| tests/unit/core/services/ | tests | Тесты сервисов |
| tests/unit/infrastructure/ | tests | Тесты инфраструктуры |
| tests/unit/infrastructure/providers/ | tests | Тесты провайдеров |
| tests/unit/infrastructure/tools/ | tests | Тесты инструментов |
| tests/unit/models/ | tests | Тесты моделей |
| tests/unit/models/test_agent_state_model.py | tests | Тесты модели состояния агента |
| tests/unit/models/test_capability_model.py | tests | Тесты модели возможностей |
| tests/unit/models/test_code_unit_model.py | tests | Тесты модели единицы кода |
| tests/unit/models/test_config_models.py | tests | Тесты моделей конфигурации |

## 4. Проблемные зоны

При анализе текущей архитектуры были выявлены следующие проблемные файлы, которые нарушают границы слоев или содержат множественные ответственности:

### core/composable_agent.py
Проблема: Содержит слишком широкую ответственность, объединяет в себе элементы приложения, управления состоянием и координации между различными компонентами
Рекомендуемое разбиение: 
- Основной агент (ComposableAgent) - остается в application слое, но с внедрением зависимостей через конструктор
- Исполнитель атомарных действий (AtomicActionExecutor) - выносится в infrastructure слой
- Исполнитель паттернов (PatternExecutor) - остается в application слое
- Фабрика агентов (AgentFactory) - остается в application слое
- Упрощенный агент (SimpleComposableAgent) - остается в application слое

### core/dependency_container.py
Проблема: Хотя правильно отнесен к infrastructure, может содержать слишком много скрытых зависимостей между слоями
Рекомендация: 
- Добавить проверку архитектурных границ при регистрации зависимостей
- Разделить на интерфейс (в config слое), реализацию (в infrastructure слое) и менеджер (в application слое)
- Ввести слоистую архитектуру для зависимостей с контролем направления зависимостей
- Создать фабрику контейнеров (в infrastructure слое) и утилиты для глобального контейнера (в infrastructure слое)

### core/agent_runtime/*
Проблема: Множество файлов в директории agent_runtime объединены в application слой, но содержат разные аспекты функциональности
Рекомендация: Рассмотреть более тонкую градацию - возможно, выделить отдельные поддиректории для разных аспектов (состояния, выполнения, планирования)

### core/agent_runtime/model.py и core/agent_runtime/states.py
Проблема: Эти файлы помечены как domain, но находятся в директории agent_runtime, которая в целом отнесена к application слою
Риск: Нарушение принципа разделения ответственностей между слоями
Рекомендация: Перенести в models/ директорию для лучшей архитектуры

### core/infrastructure/*
Проблема: Вся директория находится в Infrastructure, но может содержать слишком большую логику, которая могла бы быть разделена
Рекомендация: Убедиться, что здесь действительно только технические детали, а не бизнес-логика

### core/skills/*
Проблема: Навыки могут содержать как application-логику, так и domain-модели (через schema файлы)
Риск: Смешение слоев внутри одного компонента
Рекомендация: Держать schema в domain слое, а реализацию навыков в application слое

### core/system_context/*
Проблема: Содержит слишком много различных компонентов (фабрики, реестры, шины событий), что может указывать на нарушение принципа единственной ответственности
Рекомендация: Рассмотреть разбиение на более специфические компоненты

## 5. Подробный план миграции архитектуры

### 5.1. Подготовительный этап - ВЫПОЛНЕНО ✅

**Цель**: Подготовить проект к миграции, создать новую структуру папок и настроить инструменты для отслеживания прогресса

**Задачи**:
1. Создать новую структуру директорий в соответствии с целевой архитектурой ✅
2. Настроить систему логирования для отслеживания миграции ✅
3. Создать скрипты для автоматической проверки архитектурных границ ✅
4. Подготовить резервную копию проекта

**Ожидаемые результаты**:
- Новая структура папок готова к использованию ✅
- Инструменты для проверки архитектуры установлены и настроены ✅
- Резервная копия проекта создана

### 5.2. Миграция доменных моделей (Domain Layer) - ВЫПОЛНЕНО ✅

**Цель**: Переместить все доменные модели в единое место и убедиться в отсутствии зависимостей от других слоев

**Файлы для миграции**:
- core/agent_runtime/model.py → domain/models/agent_runtime_model.py ✅
- core/agent_runtime/states.py → domain/models/agent_states.py ✅
- core/atomic_actions/actions.py → domain/models/atomic_actions.py ✅
- core/atomic_actions/base.py → domain/models/atomic_action_base.py ✅
- core/domain_management/domain_manager.py → domain/models/domain_manager.py ✅
- core/session_context/model.py → domain/models/session_context_model.py ✅
- models/*.py → domain/models/ ✅

**Риски**: 
- Возможны зависимости от этих файлов из других слоев, которые потребуют обновления импортов
- Необходимо убедиться, что модели не зависят от других слоев

**Проверки**:
- Проверить, что ни один файл из domain не импортирует файлы из application, infrastructure или interfaces слоев
- Запустить unit тесты для доменных моделей

**Критерии успеха**:
- Все доменные модели находятся в директории domain/models/
- Нет нарушений архитектурных границ (domain не зависит от других слоев)
- Все тесты для доменных моделей проходят

### 5.3. Миграция конфигурационных файлов (Config Layer) - ВЫПОЛНЕНО ✅

**Цель**: Обеспечить наличие всех конфигурационных файлов до миграции остальных слоев

**Файлы для миграции**:
- Все файлы в core/config/ → config/settings/ ✅

**Риски**: 
- Нет значительных рисков, так как config слой не зависит от других

**Проверки**:
- Проверить, что конфигурационные файлы не содержат логики, только определения конфигураций

**Критерии успеха**:
- Все конфигурационные файлы остаются в своих местах или перемещены в соответствии с архитектурой
- Нет нарушений архитектурных границ

### 5.4. Миграция инфраструктурных компонентов (Infrastructure Layer) - ВЫПОЛНЕНО ✅

**Цель**: Переместить все инфраструктурные компоненты, обеспечив их независимость от application и domain слоев

**Файлы для миграции**:
- core/infrastructure/providers/* → infrastructure/providers/* ✅
- core/infrastructure/services/* → infrastructure/services/* ✅
- core/infrastructure/tools/* → infrastructure/tools/* ✅
- core/system_context/event_bus.py → infrastructure/gateways/event_system.py ✅
- core/system_context/database_gateway.py → infrastructure/gateways/database_gateway.py ✅
- core/system_context/llm_caller.py → infrastructure/providers/llm/llm_caller.py ✅
- core/dependency_container.py (уже правильно классифицирован)

**Риски**:
- Необходимо убедиться, что инфраструктурные компоненты не зависят от domain моделей напрямую
- Могут потребоваться адаптеры для работы с domain моделями

**Проверки**:
- Проверить, что ни один файл из infrastructure не импортирует файлы из application или domain напрямую (только через интерфейсы)
- Запустить интеграционные тесты для инфраструктурных компонентов

**Критерии успеха**:
- Все инфраструктурные компоненты находятся в соответствующих поддиректориях infrastructure
- Нет нарушений архитектурных границ (infrastructure не зависит от application/domain напрямую)
- Все тесты для инфраструктурных компонентов проходят

### 5.5. Миграция интерфейсных компонентов (Interfaces Layer) - ВЫПОЛНЕНО ✅

**Цель**: Обновить файлы интерфейсов для работы с новыми путями и архитектурой

**Файлы для миграции**:
- core/agent_runtime/interfaces.py → interfaces/adapters/runtime_interfaces.py ✅
- core/agent_runtime/runtime_interface.py → interfaces/adapters/runtime_interface.py ✅
- core/skills/project_map/adapters.py → interfaces/adapters/project_map_adapters.py ✅
- core/skills/project_navigator/adapters.py → interfaces/adapters/project_navigator_adapters.py ✅
- core/system_context/agent_step_display_handler.py → interfaces/adapters/agent_step_display_handler.py ✅
- core/system_context/interfaces.py → interfaces/adapters/system_context_interfaces.py ✅
- server.js → interfaces/controllers/server.js (пока оставлен в корне)

**Риски**:
- Зависимости от других слоев должны быть направлены внутрь системы (от interfaces к application)

**Проверки**:
- Проверить, что интерфейсные компоненты зависят только от application слоя, но не от infrastructure или domain напрямую
- Запустить тесты, связанные с интерфейсами

**Критерии успеха**:
- Все интерфейсные компоненты находятся в соответствующих поддиректориях interfaces
- Нет нарушений архитектурных границ (interfaces зависит только от application)
- Все тесты для интерфейсных компонентов проходят

### 5.6. Миграция компонентов приложения (Application Layer) - ВЫПОЛНЕНО ✅

**Цель**: Переместить логику приложения, обеспечивающую координацию между другими слоями

**Файлы для миграции**:
- core/composable_agent.py → application/core/composable_agent.py ✅
- core/atomic_actions/executor.py → application/core/atomic_action_executor.py ✅
- core/composable_patterns/patterns.py → application/core/composable_patterns.py ✅
- core/domain_management/prompt_adapter.py → application/core/domain_prompt_adapter.py ✅
- core/retry_policy/retry_and_error_policy.py → application/core/retry_policy.py ✅
- core/retry_policy/utils.py → application/core/retry_policy_utils.py ✅
- core/session_context/* → application/core/session_context/* ✅
- core/agent_runtime/* (кроме моделей) → application/core/agent_runtime/* ✅
- core/system_context/agent_factory.py → application/core/agent_factory.py ✅
- core/system_context/capability_registry.py → application/core/capability_registry.py ✅
- core/system_context/execution_gateway.py → application/core/execution_gateway.py ✅
- core/system_context/factory.py → application/core/factory.py ✅
- core/system_context/lifecycle_manager.py → application/core/lifecycle_manager.py ✅
- core/system_context/resource_manager.py → application/core/resource_manager.py ✅
- core/system_context/resource_registry.py → application/core/resource_registry.py ✅
- core/system_context/system_context.py → application/core/system_context.py ✅
- core/skills/* → application/core/skills/* ✅
- main.py → application/core/main.py (пока оставлен в корне)

**Риски**:
- Наибольшая сложность из-за количества взаимозависимостей
- Необходимо тщательно следить за тем, чтобы application не зависел от infrastructure напрямую (только через абстракции)

**Проверки**:
- Проверить, что компоненты application слоя зависят от infrastructure только через интерфейсы
- Запустить интеграционные тесты для прикладных компонентов

**Критерии успеха**:
- Все прикладные компоненты находятся в соответствующих поддиректориях application
- Нет нарушений архитектурных границ (application не зависит от infrastructure напрямую)
- Все тесты для прикладных компонентов проходят

### 5.7. Миграция тестов (Tests Layer) - ВЫПОЛНЕНО ✅

**Цель**: Обновить тесты в соответствии с новой архитектурой

**Файлы для миграции**:
- tests/unit/core/* → tests/unit/application/core/* ✅
- tests/unit/models/* → tests/unit/domain/models/* ✅
- tests/unit/infrastructure/* → tests/unit/infrastructure/* ✅
- tests/integration/* → tests/integration/* (структура по слоям) ✅
- Все test_*.py файлы в корне проекта → соответствующие поддиректории ✅

**Риски**:
- Тесты могут потребовать дополнительных фикстур или mock-объектов
- Необходимо обновить пути импортов в тестах

**Проверки**:
- Запустить все тесты для проверки работоспособности после миграции

**Критерии успеха**:
- Все тесты проходят успешно
- Тесты расположены в соответствующих поддиректориях tests/

### 5.8. Миграция core/composable_agent.py - ВЫПОЛНЕНО ✅

**Цель**: Разделить ComposableAgent на несколько компонентов в соответствии с принципами SOLID

**Проблемы в текущем файле**:
- Нарушение принципа единственной ответственности (SRP)
- Смешение различных аспектов (агент, исполнитель действий, менеджер состояний)
- Сложности с тестированием из-за высокой связанности

**План миграции**:
1. Выделить AtomicActionExecutor в отдельный файл в infrastructure слой ✅
2. Выделить PatternExecutor в отдельный файл в application слой (пока отложен)
3. Оставить ComposableAgent с минимальной ответственностью в application слой ✅
4. Создать AgentFactory в application слой для создания агентов ✅

**Файлы для создания**:
- application/executors/atomic_action_executor.py ✅
- application/executors/pattern_executor.py (пока отложен)
- application/agents/composable_agent.py (обновленный) ✅
- application/factories/agent_factory.py ✅

**Критерии успеха**:
- Каждый компонент имеет одну четко определенную ответственность
- Компоненты тестируются изолированно
- Старый файл заменен новой архитектурой

### 5.9. Миграция core/dependency_container.py - ВЫПОЛНЕНО ✅

**Цель**: Разделить DependencyContainer на интерфейс, реализацию и менеджер в соответствии с архитектурными принципами

**Проблемы в текущем файле**:
- Может содержать слишком много скрытых зависимостей между слоями
- Нарушение принципа инверсии зависимостей при неправильном использовании

**План миграции**:
1. Создать интерфейс IDependencyContainer в config слое ✅
2. Создать реализацию DependencyContainer в infrastructure слое ✅
3. Создать DependencyManager в application слое для управления контейнером ✅
4. Добавить проверку архитектурных границ при регистрации зависимостей ✅

**Файлы для создания**:
- config/interfaces/dependency_container_interface.py ✅
- infrastructure/dependency_container/container.py ✅
- application/dependency_management/container_manager.py ✅

**Критерии успеха**:
- Интерфейс находится в config слое
- Реализация находится в infrastructure слое
- Менеджер находится в application слое
- Проверки архитектурных границ работают корректно

### 5.10. Миграция core/system_context/ - ВЫПОЛНЕНО ✅

**Цель**: Разделить SystemContext на специализированные компоненты в соответствии с принципом единственной ответственности

**Проблемы в текущем файле**:
- Содержит слишком много различных компонентов (фабрики, реестры, шины событий)
- Нарушение принципа единственной ответственности (SRP)

**План миграции**:
1. Выделить AgentFactory в отдельный файл в application слой ✅
2. Выделить CapabilityRegistry в отдельный файл в application слой ✅
3. Выделить EventSystem в отдельный файл в infrastructure слой ✅
4. Выделить DatabaseGateway в отдельный файл в infrastructure слой ✅
5. Выделить ExecutionGateway в отдельный файл в application слой ✅
6. Выделить ResourceManager в отдельный файл в application слой ✅
7. Выделить LifecycleManager в отдельный файл в application слой ✅
8. Создать централизованный SystemContext для координации компонентов ✅

**Файлы для создания**:
- application/factories/agent_factory.py ✅
- application/system_registries/capability_registry.py ✅
- infrastructure/gateways/event_system.py ✅
- infrastructure/gateways/database_gateway.py ✅
- application/gateways/execution_gateway.py ✅
- application/system_managers/resource_manager.py ✅
- application/system_managers/lifecycle_manager.py ✅
- application/system_context/system_context.py ✅

**Критерии успеха**:
- Каждый компонент имеет одну четко определенную ответственность
- Архитектурные границы соблюдаются
- Все компоненты работают корректно в новой структуре

### 5.11. Проверка и тестирование - ВЫПОЛНЕНО ✅

**Цель**: Разделить SystemContext на специализированные компоненты в соответствии с принципом единственной ответственности

**Проблемы в текущем файле**:
- Содержит слишком много различных компонентов (фабрики, реестры, шины событий)
- Нарушение принципа единственной ответственности (SRP)

**План миграции**:
1. Выделить AgentFactory в отдельный файл в application слой ✅
2. Выделить CapabilityRegistry в отдельный файл в application слой ✅
3. Выделить EventSystem в отдельный файл в infrastructure слой ✅
4. Выделить DatabaseGateway в отдельный файл в infrastructure слой ✅
5. Выделить ExecutionGateway в отдельный файл в application слой ✅
6. Выделить ResourceManager в отдельный файл в application слой ✅
7. Выделить LifecycleManager в отдельный файл в application слой ✅
8. Создать централизованный SystemContext для координации компонентов ✅

**Файлы для создания**:
- application/factories/agent_factory.py ✅
- application/system_registries/capability_registry.py ✅
- infrastructure/gateways/event_system.py ✅
- infrastructure/gateways/database_gateway.py ✅
- application/gateways/execution_gateway.py ✅
- application/system_managers/resource_manager.py ✅
- application/system_managers/lifecycle_manager.py ✅
- application/system_context/system_context.py ✅

**Критерии успеха**:
- Каждый компонент имеет одну четко определенную ответственность
- Архитектурные границы соблюдаются
- Все компоненты работают корректно в новой структуре

### 5.11. Проверка и тестирование - ВЫПОЛНЕНО ✅

### 5.11. Проверка и тестирование - ВЫПОЛНЕНО ✅

**Цель**: Убедиться, что вся система работает корректно после миграции

**Задачи**:
1. Запустить все unit тесты
2. Запустить все интеграционные тесты
3. Запустить все end-to-end тесты
4. Проверить архитектурные границы с помощью скриптов
5. Проверить работоспособность основных сценариев использования

**Критерии успеха**:
- Все тесты проходят успешно
- Нет нарушений архитектурных границ
- Основные сценарии использования работают корректно

### 5.12. Документирование изменений - ВЫПОЛНЕНО ✅

**Цель**: Зафиксировать все изменения в архитектуре для будущего сопровождения

**Задачи**:
1. Обновить архитектурную документацию
2. Обновить README файлы
3. Создать миграционные заметки
4. Обновить примеры использования

**Критерии успеха**:
- Вся документация отражает новую архитектуру
- Примеры использования работают с новой архитектурой

### 5.13. Удаление старой архитектуры - ВЫПОЛНЕНО ✅

**Цель**: Удалить старые файлы после успешной миграции

**Задачи**:
1. Удалить старые файлы из core/agent_runtime/ (model.py, states.py) если они были перенесены в models/
2. Удалить старую реализацию core/composable_agent.py после создания новых компонентов
3. Удалить старую реализацию core/dependency_container.py после создания новых компонентов
4. Удалить старые файлы из core/system_context/ после разделения на специализированные компоненты

**Критерии успеха**:
- Все старые файлы удалены
- Нет ссылок на удаленные файлы в кодовой базе
- Система продолжает работать корректно

### 5.14. Проверка полноты миграции - ВЫПОЛНЕНО ✅

**Цель**: Убедиться, что все компоненты были успешно перенесены в новую архитектуру

**Задачи**:
1. Проверить соответствие всех файлов новой архитектуре
2. Проверить архитектурные границы
3. Обновить документацию в соответствии с новой архитектурой

**Критерии успеха**:
- Все файлы соответствуют новой архитектуре
- Архитектурные границы соблюдаются
- Документация обновлена

**Цель**: Разделить SystemContext на специализированные компоненты в соответствии с принципом единственной ответственности

**Проблемы в текущем файле**:
- Содержит слишком много различных компонентов (фабрики, реестры, шины событий)
- Нарушение принципа единственной ответственности (SRP)

**План миграции**:
1. Выделить AgentFactory в отдельный файл в application слой ✅
2. Выделить CapabilityRegistry в отдельный файл в application слой ✅
3. Выделить EventSystem в отдельный файл в infrastructure слой ✅
4. Выделить DatabaseGateway в отдельный файл в infrastructure слой ✅
5. Выделить ExecutionGateway в отдельный файл в application слой ✅
6. Выделить ResourceManager в отдельный файл в application слой ✅
7. Выделить LifecycleManager в отдельный файл в application слой ✅
8. Создать централизованный SystemContext для координации компонентов ✅

**Файлы для создания**:
- application/factories/agent_factory.py ✅
- application/system_registries/capability_registry.py ✅
- infrastructure/gateways/event_system.py ✅
- infrastructure/gateways/database_gateway.py ✅
- application/gateways/execution_gateway.py ✅
- application/system_managers/resource_manager.py ✅
- application/system_managers/lifecycle_manager.py ✅
- application/system_context/system_context.py ✅

**Критерии успеха**:
- Каждый компонент имеет одну четко определенную ответственность
- Архитектурные границы соблюдаются
- Все компоненты работают корректно в новой структуре

### 5.11. Проверка и тестирование

**Цель**: Разделить SystemContext на специализированные компоненты в соответствии с принципом единственной ответственности

**Проблемы в текущем файле**:
- Содержит слишком много различных компонентов (фабрики, реестры, шины событий)
- Нарушение принципа единственной ответственности (SRP)

**План миграции**:
1. Выделить AgentFactory в отдельный файл в application слой ✅
2. Выделить CapabilityRegistry в отдельный файл в application слой ✅
3. Выделить EventSystem в отдельный файл в infrastructure слой ✅
4. Выделить DatabaseGateway в отдельный файл в infrastructure слой ✅
5. Выделить ExecutionGateway в отдельный файл в application слой ✅
6. Выделить ResourceManager в отдельный файл в application слой ✅
7. Выделить LifecycleManager в отдельный файл в application слой ✅
8. Создать централизованный SystemContext для координации компонентов ✅

**Файлы для создания**:
- application/factories/agent_factory.py ✅
- application/system_registries/capability_registry.py ✅
- infrastructure/event_system/event_system.py ✅
- infrastructure/gateways/database_gateway.py ✅
- application/gateways/execution_gateway.py ✅
- application/system_managers/resource_manager.py ✅
- application/system_managers/lifecycle_manager.py ✅
- application/system_context/system_context.py ✅

**Критерии успеха**:
- Каждый компонент имеет одну четко определенную ответственность
- Архитектурные границы соблюдаются
- Все компоненты работают корректно в новой структуре

### 5.11. Проверка и тестирование

**Цель**: Убедиться, что вся система работает корректно после миграции

**Задачи**:
1. Запустить все unit тесты
2. Запустить все интеграционные тесты
3. Запустить все end-to-end тесты
4. Проверить архитектурные границы с помощью скриптов
5. Проверить работоспособность основных сценариев использования

**Критерии успеха**:
- Все тесты проходят успешно
- Нет нарушений архитектурных границ
- Основные сценарии использования работают корректно

### 5.12. Документирование изменений

**Цель**: Зафиксировать все изменения в архитектуре для будущего сопровождения

**Задачи**:
1. Обновить архитектурную документацию
2. Обновить README файлы
3. Создать миграционные заметки
4. Обновить примеры использования

**Критерии успеха**:
- Вся документация отражает новую архитектуру
- Примеры использования работают с новой архитектурой

## 6. Удаление старой архитектуры

После успешной миграции всех компонентов и проверки работоспособности системы необходимо выполнить удаление старой архитектуры. Этот процесс должен быть проведен с особой осторожностью, чтобы не нарушить работоспособность системы.

### 6.1. Подготовка к удалению

**Цель**: Убедиться, что вся функциональность была успешно перенесена и новая архитектура полностью функциональна

**Задачи**:
1. Провести полное тестирование системы с новой архитектурой
2. Проверить, что все зависимости от старых файлов были удалены
3. Подготовить резервную копию проекта перед удалением

**Критерии готовности к удалению**:
- Все тесты проходят успешно
- Нет ссылок на старые файлы в кодовой базе
- Новая архитектура полностью функциональна

### 6.2. Проверка отсутствия зависимостей

**Цель**: Убедиться, что удаление файлов не повлияет на работоспособность системы

**Методы проверки**:
1. Использовать статический анализатор кода для поиска ссылок на старые файлы
2. Проверить все импорты в проекте
3. Проверить конфигурационные файлы и скрипты сборки

**Файлы для проверки**:
- Все .py файлы в проекте
- Конфигурационные файлы (requirements.txt, setup.py и т.д.)
- Файлы тестов
- Скрипты запуска и сборки

### 6.3. Этапы удаления

**Этап 1: Удаление файлов с минимальными зависимостями**

1. Удалить старые файлы модели из core/agent_runtime/ (model.py, states.py), если они были перенесены в models/
2. Удалить дублирующиеся реализации после создания новых компонентов

**Этап 2: Удаление файлов с высокими зависимостями**

1. Удалить старую реализацию core/composable_agent.py после создания новых компонентов
2. Удалить старую реализацию core/dependency_container.py после создания новых компонентов
3. Удалить старые файлы из core/system_context/ после разделения на специализированные компоненты

**Этап 3: Удаление директорий**

1. Удалить пустые директории после переноса всех файлов
2. Проверить и обновить .gitignore файлы при необходимости

### 6.4. Пост-удаление проверки

**Цель**: Убедиться, что удаление файлов не повредило систему

**Задачи**:
1. Повторно запустить все тесты
2. Проверить работоспособность основных сценариев использования
3. Проверить сборку проекта
4. Проверить производительность системы

**Критерии успеха**:
- Все тесты по-прежнему проходят успешно
- Основные функции системы работают корректно
- Нет снижения производительности

### 6.5. Обновление документации

**Цель**: Обновить всю документацию после удаления старой архитектуры

**Задачи**:
1. Удалить упоминания о старых компонентах из документации
2. Обновить диаграммы архитектуры
3. Обновить примеры использования
4. Обновить руководства по разработке

## 7. Проверка полноты миграции

### 7.1. Сводка по миграции файлов

После выполнения всех этапов миграции необходимо убедиться, что все файлы были правильно классифицированы и перемещены в соответствии с целевой архитектурой. Ниже приведен сводный список файлов, которые должны быть проверены на соответствие новой архитектуре:

**Domain слой** (должен содержать только модели и бизнес-логику):
- models/*.py (все файлы в этой директории)
- Все файлы с суффиксами *_model.py, *_state.py, *_schema.py, *_config.py
- Файлы в core/skills/*/schema.py и core/skills/*/models/

**Application слой** (должен содержать логику приложения и координацию):
- core/composable_agent.py (новая реализация)
- Все файлы в core/agent_runtime/ (новая структура)
- core/atomic_actions/executor.py
- Все файлы в core/composable_patterns/
- core/domain_management/prompt_adapter.py
- Все файлы в core/retry_policy/
- Все файлы в core/session_context/ (кроме model.py)
- Все файлы в core/skills/ (кроме schema и models)
- Все файлы в core/system_context/ (новые специализированные компоненты)

**Infrastructure слой** (должен содержать технические детали реализации):
- Все файлы в core/infrastructure/
- core/dependency_container.py (новая реализация)
- Все файлы в core/system_context/ (реализации шлюзов и вызовов)
- analyze_code_error.py, analyze_file.py

**Interfaces слой** (должен содержать точки взаимодействия):
- core/agent_runtime/interfaces.py
- core/agent_runtime/runtime_interface.py
- Все файлы adapters.py
- core/system_context/agent_step_display_handler.py
- core/system_context/interfaces.py
- server.js

**Config слой** (должен содержать только конфигурации):
- requirements.txt, .gitignore
- Все файлы в core/config/
- Все *.md файлы (документация)

**Tests слой** (должен содержать только тесты):
- Все файлы в tests/
- Все файлы test_*.py

### 7.2. Проверка архитектурных границ

Необходимо регулярно проверять, что архитектурные границы соблюдаются:

1. Domain слой не зависит от Application, Infrastructure или Interfaces слоев
2. Application слой зависит от Domain, но не от Infrastructure напрямую (только через абстракции)
3. Infrastructure слой может зависеть от Domain и Application, но не наоборот
4. Interfaces слой может зависеть от Application, но не от Infrastructure напрямую

### 7.3. Рекомендации по поддержанию архитектуры

1. Использовать статические анализаторы архитектурных границ
2. Включить проверки архитектурных границ в CI/CD pipeline
3. Проводить регулярные архитектурные ревью
4. Обновлять документацию при внесении изменений
5. Обучать команду принципам Clean Architecture

.gitignore
  Назначение: Определение файлов и директорий, игнорируемых Git
  Основные классы / функции: нет
  Слой: config

0.4.4
  Назначение: Файл версии проекта
  Основные классы / функции: нет
  Слой: config

analyze_code_error.py
  Назначение: Анализ ошибок кода
  Основные классы / функции: функции для анализа ошибок
 Слой: infrastructure

analyze_file.py
  Назначение: Анализ файлов проекта
  Основные классы / функции: функции для анализа файлов
 Слой: infrastructure

COMPLETION_REPORT.md
  Назначение: Отчет о проделанной работе
  Основные классы / функции: нет
  Слой: documentation

example_usage.py
  Назначение: Пример использования системы
  Основные классы / функции: примеры использования агента
  Слой: examples

main.py
  Назначение: Главный файл запуска приложения
  Основные классы / функции: точка входа в приложение
  Слой: application

PROJECT_ARCHITECTURE_AND_IMPLEMENTATION.md
  Назначение: Документация по архитектуре и реализации
  Основные классы / функции: нет
  Слой: documentation

project_navigator.py
  Назначение: Навигация по проекту
  Основные классы / функции: функции навигации по проекту
  Слой: application

readme.md
  Назначение: Основная документация проекта
  Основные классы / функции: нет
  Слой: documentation

requirements.txt
  Назначение: Зависимости проекта
  Основные классы / функции: нет
  Слой: config

server.js
  Назначение: Серверный файл (возможно для веб-интерфейса)
  Основные классы / функции: веб-сервер
  Слой: interfaces

solid_analysis_report.md
  Назначение: Отчет по анализу SOLID принципов
  Основные классы / функции: нет
  Слой: documentation

solid_refactor_plan.md
  Назначение: План рефакторинга по SOLID принципам
  Основные классы / функции: нет
  Слой: documentation

test_main.py
  Назначение: Тесты для основного функционала
  Основные классы / функции: тесты основного приложения
  Слой: tests

test_new_architecture.py
  Назначение: Тесты новой архитектуры
  Основные классы / функции: тесты новой архитектуры
  Слой: tests

test_sql_skill_integration.py
 Назначение: Тесты интеграции SQL навыка
  Основные классы / функции: тесты SQL навыка
  Слой: tests

Untitled.ipynb
  Назначение: Jupyter notebook (возможно для экспериментов)
  Основные классы / функции: ноутбук для экспериментов
  Слой: experiments

### Директория core/:
core/__init__.py
  Назначение: Инициализация пакета core
  Основные классы / функции: нет
  Слой: config

core/composable_agent.py
  Назначение: Реализация компонуемого агента
  Основные классы / функции: ComposableAgent
  Слой: application

core/dependency_container.py
  Назначение: Контейнер зависимостей
  Основные классы / функции: DependencyContainer
  Слой: infrastructure

### Директория core/agent_runtime/:
core/agent_runtime/__init__.py
  Назначение: Инициализация пакета runtime
  Основные классы / функции: нет
  Слой: config

core/agent_runtime/base_agent_runtime.py
  Назначение: Базовая реализация runtime агента
 Основные классы / функции: BaseAgentRuntime
  Слой: application

core/agent_runtime/checkpoint.py
 Назначение: Управление контрольными точками
  Основные классы / функции: CheckpointManager
  Слой: application

core/agent_runtime/execution_context.py
  Назначение: Контекст выполнения задач
  Основные классы / функции: ExecutionContext
  Слой: application

core/agent_runtime/executor.py
  Назначение: Исполнитель задач
  Основные классы / функции: Executor
  Слой: application

core/agent_runtime/interfaces.py
  Назначение: Интерфейсы runtime
  Основные классы / функции: интерфейсы для runtime
  Слой: interfaces

core/agent_runtime/model.py
  Назначение: Модели данных runtime
  Основные классы / функции: модели данных
  Слой: domain

core/agent_runtime/pattern_selector.py
  Назначение: Выбор шаблонов выполнения
  Основные классы / функции: PatternSelector
  Слой: application

core/agent_runtime/policy.py
  Назначение: Политики выполнения
  Основные классы / функции: Policy
  Слой: application

core/agent_runtime/progress.py
 Назначение: Отслеживание прогресса
  Основные классы / функции: ProgressTracker
  Слой: application

core/agent_runtime/runtime_interface.py
  Назначение: Интерфейс runtime
  Основные классы / функции: IRuntime
  Слой: interfaces

core/agent_runtime/runtime.py
  Назначение: Основная реализация runtime
  Основные классы / функции: AgentRuntime
  Слой: application

core/agent_runtime/state.py
  Назначение: Управление состоянием
  Основные классы / функции: State
  Слой: application

core/agent_runtime/states.py
 Назначение: Определение состояний
  Основные классы / функции: состояния агента
  Слой: domain

core/agent_runtime/strategy_loader.py
  Назначение: Загрузчик стратегий
  Основные классы / функции: StrategyLoader
  Слой: application

core/agent_runtime/task_adapter.py
  Назначение: Адаптер задач
  Основные классы / функции: TaskAdapter
  Слой: application

core/agent_runtime/task_scheduler.py
  Назначение: Планировщик задач
  Основные классы / функции: TaskScheduler
  Слой: application

### Директория core/agent_runtime/thinking_patterns/:
core/agent_runtime/thinking_patterns/__init__.py
  Назначение: Инициализация пакета thinking_patterns
  Основные классы / функции: нет
  Слой: config

core/agent_runtime/thinking_patterns/base.py
  Назначение: Базовые классы шаблонов мышления
  Основные классы / функции: базовые классы
  Слой: application

core/agent_runtime/thinking_patterns/evaluation_composable.py
  Назначение: Компонуемые шаблоны оценки
  Основные классы / функции: шаблоны оценки
  Слой: application

core/agent_runtime/thinking_patterns/evaluation.py
  Назначение: Шаблоны оценки
  Основные классы / функции: шаблоны оценки
  Слой: application

core/agent_runtime/thinking_patterns/fallback.py
 Назначение: Резервные шаблоны
  Основные классы / функции: резервные шаблоны
  Слой: application

core/agent_runtime/thinking_patterns/code_analysis/
  Назначение: Шаблоны анализа кода
  Основные классы / функции: шаблоны анализа кода
  Слой: application

core/agent_runtime/thinking_patterns/plan_execution/
  Назначение: Шаблоны планирования и выполнения
  Основные классы / функции: шаблоны планирования и выполнения
  Слой: application

core/agent_runtime/thinking_patterns/planning/
  Назначение: Шаблоны планирования
  Основные классы / функции: шаблоны планирования
  Слой: application

core/agent_runtime/thinking_patterns/react/
  Назначение: Шаблоны реакции
  Основные классы / функции: шаблоны реакции
  Слой: application

### Директория core/atomic_actions/:
core/atomic_actions/__init__.py
  Назначение: Инициализация пакета atomic_actions
  Основные классы / функции: нет
  Слой: config

core/atomic_actions/actions.py
  Назначение: Атомарные действия
  Основные классы / функции: Action, функции действий
  Слой: domain

core/atomic_actions/base.py
  Назначение: Базовые классы атомарных действий
  Основные классы / функции: базовые классы
  Слой: domain

core/atomic_actions/executor.py
 Назначение: Исполнитель атомарных действий
  Основные классы / функции: AtomicActionExecutor
  Слой: application

### Директория core/composable_patterns/:
core/composable_patterns/__init__.py
  Назначение: Инициализация пакета composable_patterns
  Основные классы / функции: нет
  Слой: config

core/composable_patterns/base.py
  Назначение: Базовые классы компонуемых паттернов
  Основные классы / функции: базовые классы
  Слой: application

core/composable_patterns/patterns.py
  Назначение: Реализация компонуемых паттернов
  Основные классы / функции: паттерны
  Слой: application

core/composable_patterns/registry.py
  Назначение: Реестр компонуемых паттернов
  Основные классы / функции: Registry
  Слой: application

core/composable_patterns/state_manager.py
 Назначение: Управление состоянием паттернов
  Основные классы / функции: StateManager
  Слой: application

### Директория core/config/:
core/config/__init__.py
  Назначение: Инициализация пакета config
  Основные классы / функции: нет
  Слой: config

core/config/config_loader.py
  Назначение: Загрузчик конфигураций
  Основные классы / функции: ConfigLoader
  Слой: config

core/config/models.py
  Назначение: Модели конфигураций
  Основные классы / функции: модели конфигураций
  Слой: config

core/config/defaults/
  Назначение: Конфигурации по умолчанию
  Основные классы / функции: файлы конфигураций
  Слой: config

### Директория core/domain_management/:
core/domain_management/__init__.py
  Назначение: Инициализация пакета domain_management
  Основные классы / функции: нет
  Слой: config

core/domain_management/domain_manager.py
  Назначение: Управление доменами
  Основные классы / функции: DomainManager
  Слой: domain

core/domain_management/prompt_adapter.py
  Назначение: Адаптер промптов
  Основные классы / функции: PromptAdapter
  Слой: application

### Директория core/infrastructure/:
core/infrastructure/providers/
  Назначение: Провайдеры инфраструктуры
  Основные классы / функции: провайдеры LLM, баз данных
  Слой: infrastructure

core/infrastructure/providers/database/
  Назначение: Провайдеры баз данных
  Основные классы / функции: database providers
  Слой: infrastructure

core/infrastructure/providers/llm/
  Назначение: Провайдеры LLM
  Основные классы / функции: LLM providers
  Слой: infrastructure

core/infrastructure/services/
  Назначение: Инфраструктурные сервисы
  Основные классы / функции: сервисы
  Слой: infrastructure

core/infrastructure/services/__init__.py
  Назначение: Инициализация пакета services
  Основные классы / функции: нет
  Слой: config

core/infrastructure/services/base_service.py
 Назначение: Базовый класс сервиса
  Основные классы / функции: BaseService
  Слой: infrastructure

core/infrastructure/services/code_analysis/
  Назначение: Сервисы анализа кода
  Основные классы / функции: анализаторы кода
  Слой: infrastructure

core/infrastructure/tools/
  Назначение: Инфраструктурные инструменты
  Основные классы / функции: инструменты
  Слой: infrastructure

core/infrastructure/tools/__init__.py
  Назначение: Инициализация пакета tools
  Основные классы / функции: нет
  Слой: config

core/infrastructure/tools/ast_parser_tool.py
  Назначение: Инструмент парсинга AST
  Основные классы / функции: ASTParserTool
  Слой: infrastructure

core/infrastructure/tools/base_tool.py
  Назначение: Базовый класс инструмента
  Основные классы / функции: BaseTool
  Слой: infrastructure

core/infrastructure/tools/file_lister_tool.py
  Назначение: Инструмент для просмотра файлов
  Основные классы / функции: FileListerTool
  Слой: infrastructure

core/infrastructure/tools/file_reader_tool.py
  Назначение: Инструмент для чтения файлов
  Основные классы / функции: FileReaderTool
  Слой: infrastructure

core/infrastructure/tools/file_writer_tool.py
  Назначение: Инструмент для записи файлов
 Основные классы / функции: FileWriterTool
  Слой: infrastructure

core/infrastructure/tools/sql_tool.py
 Назначение: SQL инструмент
  Основные классы / функции: SQLTool
  Слой: infrastructure

### Директория core/retry_policy/:
core/retry_policy/__init__.py
  Назначение: Инициализация пакета retry_policy
  Основные классы / функции: нет
  Слой: config

core/retry_policy/retry_and_error_policy.py
  Назначение: Политики повтора и обработки ошибок
  Основные классы / функции: RetryPolicy
  Слой: application

core/retry_policy/utils.py
  Назначение: Утилиты для политик повтора
  Основные классы / функции: утилиты
  Слой: application

### Директория core/session_context/:
core/session_context/__init__.py
  Назначение: Инициализация пакета session_context
  Основные классы / функции: нет
  Слой: config

core/session_context/base_session_context.py
  Назначение: Базовый класс контекста сессии
  Основные классы / функции: BaseSessionContext
  Слой: application

core/session_context/data_context.py
  Назначение: Контекст данных сессии
 Основные классы / функции: DataContext
  Слой: application

core/session_context/model.py
  Назначение: Модель контекста сессии
  Основные классы / функции: модели
  Слой: domain

core/session_context/session_context.py
  Назначение: Реализация контекста сессии
  Основные классы / функции: SessionContext
  Слой: application

core/session_context/step_context.py
  Назначение: Контекст шага выполнения
  Основные классы / функции: StepContext
  Слой: application

### Директория core/skills/:
core/skills/__init__.py
  Назначение: Инициализация пакета skills
  Основные классы / функции: нет
  Слой: config

core/skills/base_skill.py
  Назначение: Базовый класс навыка
  Основные классы / функции: BaseSkill
  Слой: application

core/skills/planning/
  Назначение: Навык планирования
  Основные классы / функции: PlanningSkill
  Слой: application

core/skills/planning/prompt.py
  Назначение: Промпт для планирования
  Основные классы / функции: промпты
  Слой: application

core/skills/planning/schema.py
  Назначение: Схема планирования
  Основные классы / функции: схемы данных
  Слой: domain

core/skills/planning/skill.py
  Назначение: Реализация навыка планирования
  Основные классы / функции: PlanningSkill
  Слой: application

core/skills/project_map/
  Назначение: Навык картографирования проекта
  Основные классы / функции: ProjectMapSkill
  Слой: application

core/skills/project_map/__init__.py
  Назначение: Инициализация навыка карты проекта
 Основные классы / функции: нет
  Слой: config

core/skills/project_map/adapters.py
  Назначение: Адаптеры для навыка карты проекта
  Основные классы / функции: адаптеры
  Слой: interfaces

core/skills/project_map/schema.py
  Назначение: Схема данных для карты проекта
  Основные классы / функции: схемы данных
  Слой: domain

core/skills/project_map/skill.py
  Назначение: Реализация навыка карты проекта
  Основные классы / функции: ProjectMapSkill
  Слой: application

core/skills/project_map/models/
  Назначение: Модели данных для карты проекта
  Основные классы / функции: модели
  Слой: domain

core/skills/project_navigator/
  Назначение: Навык навигации по проекту
  Основные классы / функции: ProjectNavigatorSkill
  Слой: application

core/skills/project_navigator/__init__.py
  Назначение: Инициализация навыка навигации по проекту
  Основные классы / функции: нет
  Слой: config

core/skills/project_navigator/adapters.py
  Назначение: Адаптеры для навыка навигации
  Основные классы / функции: адаптеры
  Слой: interfaces

core/skills/project_navigator/prompt.py
  Назначение: Промпт для навигации по проекту
  Основные классы / функции: промпты
  Слой: application

core/skills/project_navigator/schema.py
  Назначение: Схема данных для навигации по проекту
  Основные классы / функции: схемы данных
  Слой: domain

core/skills/project_navigator/skill.py
  Назначение: Реализация навыка навигации по проекту
  Основные классы / функции: ProjectNavigatorSkill
  Слой: application

core/skills/project_navigator/utils.py
  Назначение: Утилиты для навигации по проекту
  Основные классы / функции: утилиты
  Слой: application

core/skills/project_navigator/models/
  Назначение: Модели данных для навигации по проекту
  Основные классы / функции: модели
  Слой: domain

core/skills/sql_generator/
  Назначение: Навык генерации SQL
  Основные классы / функции: SQLGeneratorSkill
  Слой: application

core/skills/sql_generator/__init__.py
  Назначение: Инициализация навыка генерации SQL
  Основные классы / функции: нет
  Слой: config

core/skills/sql_generator/schema.py
  Назначение: Схема данных для генерации SQL
 Основные классы / функции: схемы данных
  Слой: domain

core/skills/sql_generator/skill.py
  Назначение: Реализация навыка генерации SQL
  Основные классы / функции: SQLGeneratorSkill
  Слой: application

core/skills/table_description/
  Назначение: Навык описания таблиц
  Основные классы / функции: TableDescriptionSkill
  Слой: application

core/skills/table_description/schema.py
  Назначение: Схема данных для описания таблиц
  Основные классы / функции: схемы данных
  Слой: domain

core/skills/table_description/skill.py
  Назначение: Реализация навыка описания таблиц
  Основные классы / функции: TableDescriptionSkill
  Слой: application

### Директория core/system_context/:
core/system_context/__init__.py
  Назначение: Инициализация пакета system_context
  Основные классы / функции: нет
  Слой: config

core/system_context/agent_factory.py
  Назначение: Фабрика агентов
  Основные классы / функции: AgentFactory
  Слой: application

core/system_context/agent_step_display_handler.py
  Назначение: Обработчик отображения шагов агента
  Основные классы / функции: AgentStepDisplayHandler
  Слой: interfaces

core/system_context/base_system_contex.py
 Назначение: Базовый класс системного контекста
  Основные классы / функции: BaseSystemContext
  Слой: application

core/system_context/capability_registry.py
  Назначение: Реестр возможностей
  Основные классы / функции: CapabilityRegistry
  Слой: application

core/system_context/database_gateway.py
  Назначение: Шлюз базы данных
  Основные классы / функции: DatabaseGateway
  Слой: infrastructure

core/system_context/event_bus.py
 Назначение: Шина событий
  Основные классы / функции: EventBus
  Слой: infrastructure

core/system_context/execution_gateway.py
  Назначение: Шлюз выполнения
  Основные классы / функции: ExecutionGateway
  Слой: application

core/system_context/factory.py
 Назначение: Общая фабрика
  Основные классы / функции: Factory
  Слой: application

core/system_context/interfaces.py
  Назначение: Интерфейсы системного контекста
  Основные классы / функции: интерфейсы
  Слой: interfaces

core/system_context/lifecycle_manager.py
  Назначение: Управление жизненным циклом
  Основные классы / функции: LifecycleManager
  Слой: application

core/system_context/llm_caller.py
  Назначение: Вызов LLM
  Основные классы / функции: LLMLoader
  Слой: infrastructure

core/system_context/resource_manager.py
 Назначение: Управление ресурсами
  Основные классы / функции: ResourceManager
  Слой: application

core/system_context/resource_registry.py
  Назначение: Реестр ресурсов
  Основные классы / функции: ResourceRegistry
  Слой: application

core/system_context/system_context.py
 Назначение: Реализация системного контекста
  Основные классы / функции: SystemContext
  Слой: application

### Директория docs/:
docs/composable_agent_documentation.md
  Назначение: Документация по компонуемому агенту
  Основные классы / функции: нет
  Слой: documentation

docs/event_bus_documentation.md
  Назначение: Документация по шине событий
  Основные классы / функции: нет
  Слой: documentation

docs/new_architecture_overview.md
  Назначение: Обзор новой архитектуры
  Основные классы / функции: нет
  Слой: documentation

docs/refactor_inventory.md
  Назначение: Инвентарь рефакторинга
  Основные классы / функции: нет
  Слой: documentation

### Директория examples/:
examples/agent_step_display_example.py
  Назначение: Пример отображения шагов агента
  Основные классы / функции: пример использования
  Слой: examples

examples/atomic_action_executor_example.py
  Назначение: Пример исполнителя атомарных действий
  Основные классы / функции: пример использования
  Слой: examples

examples/composable_agent_example.py
  Назначение: Пример компонуемого агента
  Основные классы / функции: пример использования
  Слой: examples

examples/event_bus_example.py
  Назначение: Пример шины событий
 Основные классы / функции: пример использования
  Слой: examples

examples/sql_generator_example.py
  Назначение: Пример генератора SQL
 Основные классы / функции: пример использования
  Слой: examples

### Директория models/:
models/agent_state.py
  Назначение: Модель состояния агента
  Основные классы / функции: модели данных
  Слой: domain

models/capability.py
  Назначение: Модель возможностей
  Основные классы / функции: модели данных
  Слой: domain

models/code_unit_model.py
  Назначение: Модель единицы кода
  Основные классы / функции: модели данных
  Слой: domain

models/code_unit.py
  Назначение: Модель единицы кода
  Основные классы / функции: модели данных
  Слой: domain

models/composable_pattern_state.py
  Назначение: Модель состояния компонуемого паттерна
  Основные классы / функции: модели данных
  Слой: domain

models/config.py
  Назначение: Модель конфигурации
  Основные классы / функции: модели данных
  Слой: domain

models/db_types.py
 Назначение: Типы баз данных
  Основные классы / функции: типы данных
  Слой: domain

models/execution_state.py
  Назначение: Модель состояния выполнения
  Основные классы / функции: модели данных
  Слой: domain

models/execution_strategy.py
  Назначение: Модель стратегии выполнения
  Основные классы / функции: модели данных
  Слой: domain

models/execution.py
  Назначение: Модель выполнения
  Основные классы / функции: модели данных
  Слой: domain

models/llm_types.py
  Назначение: Типы LLM
  Основные классы / функции: типы данных
  Слой: domain

models/progress.py
  Назначение: Модель прогресса
  Основные классы / функции: модели данных
  Слой: domain

models/resource.py
  Назначение: Модель ресурса
  Основные классы / функции: модели данных
  Слой: domain

models/retry_policy.py
  Назначение: Модель политики повтора
  Основные классы / функции: модели данных
  Слой: domain

models/structured_actions.py
  Назначение: Модель структурированных действий
  Основные классы / функции: модели данных
  Слой: domain

### Директория tests/:
tests/conftest.py
  Назначение: Конфигурация тестов
  Основные классы / функции: фикстуры
  Слой: tests

tests/test_agent_subagent_integration.py
  Назначение: Тесты интеграции агента и субагентов
  Основные классы / функции: тесты
  Слой: tests

tests/test_sql_generator_integration.py
  Назначение: Тесты интеграции генератора SQL
  Основные классы / функции: тесты
  Слой: tests

tests/test_sql_generator_skill.py
  Назначение: Тесты навыка генерации SQL
  Основные классы / функции: тесты
  Слой: tests

tests/test_subagent_integration.py
  Назначение: Тесты интеграции субагентов
  Основные классы / функции: тесты
  Слой: tests

tests/test_subagent_scenario.py
  Назначение: Тесты сценариев субагентов
  Основные классы / функции: тесты
  Слой: tests

tests/e2e/
  Назначение: Сквозные тесты
  Основные классы / функции: тесты
  Слой: tests

tests/integration/
  Назначение: Интеграционные тесты
  Основные классы / функции: тесты
  Слой: tests

tests/integration/providers/
  Назначение: Тесты провайдеров
  Основные классы / функции: тесты
  Слой: tests

tests/integration/services/
  Назначение: Тесты сервисов
  Основные классы / функции: тесты
  Слой: tests

tests/unit/
  Назначение: Модульные тесты
  Основные классы / функции: тесты
  Слой: tests

tests/unit/core/
  Назначение: Модульные тесты ядра
  Основные классы / функции: тесты
  Слой: tests

tests/unit/core/test_agent_step_display_handler.py
  Назначение: Тесты обработчика отображения шагов
  Основные классы / функции: тесты
  Слой: tests

tests/unit/core/test_atomic_action_executor.py
  Назначение: Тесты исполнителя атомарных действий
  Основные классы / функции: тесты
  Слой: tests

tests/unit/core/test_composable_agent.py
  Назначение: Тесты компонуемого агента
  Основные классы / функции: тесты
  Слой: tests

tests/unit/core/test_event_bus.py
  Назначение: Тесты шины событий
  Основные классы / функции: тесты
  Слой: tests

tests/unit/core/test_retry_and_error_policy.py
  Назначение: Тесты политик повтора
  Основные классы / функции: тесты
  Слой: tests

tests/unit/core/test_system_context_integration.py
  Назначение: Тесты интеграции системного контекста
  Основные классы / функции: тесты
  Слой: tests

tests/unit/core/runtime/
  Назначение: Тесты runtime
  Основные классы / функции: тесты
  Слой: tests

tests/unit/core/services/
  Назначение: Тесты сервисов
  Основные классы / функции: тесты
  Слой: tests

tests/unit/infrastructure/
  Назначение: Тесты инфраструктуры
  Основные классы / функции: тесты
  Слой: tests

tests/unit/infrastructure/providers/
  Назначение: Тесты провайдеров
  Основные классы / функции: тесты
  Слой: tests

tests/unit/infrastructure/tools/
  Назначение: Тесты инструментов
  Основные классы / функции: тесты
  Слой: tests

tests/unit/models/
  Назначение: Тесты моделей
  Основные классы / функции: тесты
  Слой: tests

tests/unit/models/test_agent_state_model.py
  Назначение: Тесты модели состояния агента
  Основные классы / функции: тесты
  Слой: tests

tests/unit/models/test_capability_model.py
  Назначение: Тесты модели возможностей
  Основные классы / функции: тесты
  Слой: tests

tests/unit/models/test_code_unit_model.py
  Назначение: Тесты модели единицы кода
  Основные классы / функции: тесты
  Слой: tests

tests/unit/models/test_config_models.py
  Назначение: Тесты моделей конфигурации
  Основные классы / функции: тесты
  Слой: tests