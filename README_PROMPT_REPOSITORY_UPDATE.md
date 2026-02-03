# Production-Ready PromptRepository - Архитектурное обновление

## Обзор

В рамках этого проекта был успешно доведен существующий PromptRepository до состояния production-ready компонента. Решение включает:

- Полный жизненный цикл промтов (draft → active → shadow → deprecated → archived)
- Строгую валидацию переменных по схеме
- Защиту от инъекций через проверку переменных
- Снапшоты выполнения для отладки и мониторинга
- Кэширование в памяти для высокой производительности
- Интеграцию с файловой системой и базой данных
- Совместимость с GreenPlum/PostgreSQL

## Обновленные компоненты

### 1. Модель данных PromptVersion

Обновленная модель включает:
- Идентификацию: id, semantic_version (MAJOR.MINOR.PATCH)
- Адресацию: domain, provider_type, capability_name, role
- Содержимое: content, variables_schema (с валидацией типов)
- Контракт вывода: expected_response_schema
- Жизненный цикл: status (draft/active/shadow/deprecated/archived), даты активации/деактивации
- Метрики: usage_metrics (количество использований, успехи, время генерации, ошибки)

### 2. Репозитории

- **IPromptRepository**: Абстракция репозитория (инверсия зависимостей)
- **DatabasePromptRepository**: Реализация с использованием BaseDBProvider
- **CachedPromptRepository**: Кэширующая обертка поверх базы данных

### 3. Сервисы

- **PromptRenderer**: Рендеринг промтов с валидацией переменных
- **PromptSnapshotManager**: Управление снапшотами выполнения
- **PromptSystemInitializer**: Инициализация системы промтов

### 4. Формат хранения

Промты теперь хранятся в формате Markdown с frontmatter:

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
  - name: "code_snippet"
    type: "string"
    required: true
    description: "Сниппет кода для анализа"
  - name: "analysis_goal"
    type: "string"
    required: true
    description: "Цель анализа"
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
Ты — эксперт по анализу кода. Проанализируй: {{code_snippet}} с целью {{analysis_goal}}.
```

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
   LLM Response → SnapshotManager → PromptRepository
   - Обновление метрик использования
   - Регистрация времени выполнения
   - Обновление процента ошибок
```

## Тестирование

Созданы полные интеграционные тесты:
- `tests/integration/test_production_prompt_repository_complete.py` - полный workflow
- `tests/unit/application/test_prompt_renderer_updated.py` - тесты рендерера
- Демонстрационный скрипт: `demo/production_prompt_repository_demo.py`

## Ключевые особенности

1. **Жизненный цикл**: Полный контроль над статусами промтов
2. **Валидация**: Строгая проверка переменных до вызова LLM
3. **Безопасность**: Защита от инъекций через схему переменных
4. **Мониторинг**: Снапшоты выполнения и метрики
5. **Производительность**: Кэширование в памяти
6. **Совместимость**: Работа с GreenPlum/PostgreSQL
7. **Обратная совместимость**: Сохранена совместимость с существующим кодом

## Использование

### Инициализация системы

```python
from application.services.prompt_system_initializer import PromptSystemInitializer

initializer = PromptSystemInitializer(db_provider, fs_directory="./prompts")
prompt_repository = await initializer.initialize()
```

### Использование в агенте

```python
from application.services.prompt_renderer import PromptRenderer

renderer = PromptRenderer(prompt_repository, snapshot_manager)

capability = Capability(
    name="code_analysis",
    prompt_versions={
        "openai:system": "prod_workflow_version_001"
    }
)

rendered, errors = await renderer.render_for_request(
    capability=capability,
    provider_type=LLMProviderType.OPENAI,
    template_context={
        "task_description": "Реализовать функцию сортировки",
        "project_context": "Проект на Python"
    },
    session_id="session_123"
)
```

## Production Checklist

При деплое в продакшен проверьте:

- [x] Все методы PromptRepository реализованы и протестированы
- [x] Валидация переменных работает корректно
- [x] Жизненный цикл статусов работает (draft → active → deprecated → archived)
- [x] SnapshotManager корректно сохраняет и извлекает данные
- [x] Ошибки валидации переменных обрабатываются корректно
- [x] Метрики использования обновляются
- [x] Обратная совместимость сохранена
- [x] Нет утечки чувствительных данных в логах

Система полностью готова к использованию в production-среде.