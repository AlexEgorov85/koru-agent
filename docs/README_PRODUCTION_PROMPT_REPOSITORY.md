# Production-Ready PromptRepository - Архитектурное Решение

## Обзор

В рамках данного проекта был успешно доведен существующий PromptRepository до состояния production-ready компонента. Решение включает:

- Полный жизненный цикл промтов (draft → active → shadow → deprecated → archived)
- Строгую валидацию переменных по схеме
- Защиту от инъекций через проверку переменных
- Снапшоты выполнения для отладки и мониторинга
- Кэширование в памяти для высокой производительности
- Интеграцию с файловой системой и базой данных
- Совместимость с GreenPlum/PostgreSQL
- Обработку ошибок и fallback-механизмы
- Метрики использования и производительности

## Архитектурные компоненты

### 1. PromptVersion - модель данных

Обновленная модель включает:
- Идентификацию: id, semantic_version (MAJOR.MINOR.PATCH)
- Адресацию: domain, provider_type, capability_name, role
- Содержимое: content, variables_schema (с валидацией типов)
- Контракт вывода: expected_response_schema
- Жизненный цикл: status (draft/active/shadow/deprecated/archived), даты активации/деактивации
- Метрики: usage_metrics (количество использований, успехи, время генерации, ошибки)

### 2. PromptRepository - абстракция

Интерфейс репозитория с методами:
- `get_active_version()` - получить активную версию по адресу
- `get_version_by_id()` - получить версию по ID
- `save_version()` - сохранить новую версию
- `activate_version()` - активировать версию
- `archive_version()` - архивировать версию
- `update_usage_metrics()` - обновить метрики использования

### 3. DatabasePromptRepository - реализация

Реализация репозитория с использованием BaseDBProvider:
- Хранение в PostgreSQL/GreenPlum
- Поддержка всех методов интерфейса
- Совместимость с ограничениями GreenPlum
- Индексация для высокой производительности

### 4. CachedPromptRepository - кэширование

Кэширующая обертка поверх DatabasePromptRepository:
- In-memory кэш для быстрого доступа
- Инвалидация при изменениях
- Блокировки для многопоточного доступа
- Поддержка всех методов репозитория

### 5. PromptRenderer - рендеринг

Рендерер промтов с валидацией переменных:
- Проверка наличия обязательных переменных
- Проверка соответствия типов
- Подстановка значений в шаблон
- Создание снапшотов выполнения

## Поток выполнения

```
1. ИНИЦИАЛИЗАЦИЯ (при старте приложения):
   FS (Markdown-файлы) → PromptFileSyncService → DatabasePromptRepository
   - Сканируются .md файлы с frontmatter
   - Создаются PromptVersion объекты
   - Сохраняются в БД через DBProvider
   - Активируются подходящие версии

2. ВЫЗОВ АГЕНТА:
   Agent → Capability → PromptRenderer → CachedPromptRepository
   - Агент получает Capability с требуемыми промтами
   - PromptRenderer запрашивает актуальные версии из репозитория
   - Выполняется валидация переменных по схеме
   - Создается снапшот с параметрами

3. РЕНДЕРИНГ:
   PromptRenderer → Подстановка переменных → Отрендеренный промт
   - Проверка наличия обязательных переменных
   - Проверка типов переменных
   - Подстановка значений в шаблон
   - Создание снапшота выполнения

4. ВЫЗОВ LLM:
   Отрендеренный промт → LLM → Ответ
   - Отправка промта в LLM
   - Получение ответа
   - Обновление снапшота с результатом

5. ОБНОВЛЕНИЕ МЕТРИК:
   LLM Response → DatabaseSnapshotManager → DatabasePromptRepository
   - Обновление метрик использования
   - Регистрация времени выполнения
   - Обновление процента ошибок
```

## Формат промтов в файловой системе

Промты хранятся в формате Markdown с frontmatter:

```markdown
---
id: prompt_analysis_001
semantic_version: "1.0.0"
domain: "problem_solving"
provider_type: "openai"
capability_name: "code_analysis"
role: "system"
status: "active"
variables_schema:
  - name: "goal"
    type: "string"
    required: true
    description: "Цель анализа кода"
  - name: "file_content"
    type: "string"
    required: true
    description: "Содержимое файла для анализа"
  - name: "context"
    type: "string"
    required: false
    description: "Дополнительный контекст"
expected_response_schema:
  type: "object"
  properties:
    analysis:
      type: "string"
    suggestions:
      type: "array"
      items:
        type: "string"
---
Ты — эксперт по анализу кода. Твоя задача — проанализировать предоставленный код и дать рекомендации по улучшению.

Цель: {{goal}}
Контекст: {{context}}

Анализируй следующий код:
{{file_content}}

Верни результат в формате JSON.
```

## Использование в агентах и навыках

```python
from application.services.prompt_renderer import PromptRenderer

# Создаем рендерер с репозиторием
renderer = PromptRenderer(prompt_repository, snapshot_manager)

# Определяем capability с указанием версий промтов
capability = Capability(
    name="llm_decision",
    description="Принятие решений LLM",
    skill_name="decision_skill",
    prompt_versions={
        "openai:system": "llm_decision_prompt_v1"  # ID версии промта
    }
)

# Рендерим промт с валидацией переменных
rendered_prompts, snapshot, errors = await renderer.render_and_create_snapshot(
    capability=capability,
    provider_type=LLMProviderType.OPENAI,
    template_context={
        "goal": "Анализировать структуру проекта",
        "tools": "file_reader, file_lister",
        "last_steps_summary": "Инициализация контекста"
    },
    session_id="session_123"
)
```

## Контроль качества

- Все промты проходят валидацию переменных перед использованием
- Все вызовы промтов логируются в снапшоты
- Поддерживаются метрики использования и производительности
- Реализован полный жизненный цикл промтов

## Преимущества

1. **Централизованное управление:** Все промты в одном месте
2. **Версионность:** Возможность откатов и отслеживания изменений
3. **Метрики:** Отслеживание эффективности промтов
4. **Безопасность:** Защита от инъекций в шаблонах
5. **Аудит:** Полная история использования промтов
6. **Гибкость:** Поддержка разных провайдеров и ролей
7. **Валидация:** Строгая проверка переменных перед вызовом LLM
8. **Адаптивность:** Возможность тонкой настройки под разные задачи

## Файлы системы

- `domain/models/prompt/prompt_version.py` - модель данных версии промта
- `domain/abstractions/prompt_repository.py` - абстракция репозитория
- `infrastructure/repositories/prompt_repository.py` - реализация репозитория
- `application/services/prompt_renderer.py` - рендерер промтов
- `application/services/cached_prompt_repository.py` - кэширующая обертка
- `application/services/prompt_system_initializer.py` - инициализатор системы
- `prompts/*.md` - файлы промтов с frontmatter
- `infrastructure/database/prompt_tables.sql` - схема таблиц для БД
- `docs/prompt_repository_production_guide.md` - руководство по использованию
- `tests/test_production_prompt_repository.py` - тесты системы
- `demo/simple_concept_demo.py` - демонстрация работы системы

Система полностью готова к использованию в production-среде с поддержкой масштабируемости, безопасности и мониторинга.