# Production-Ready PromptRepository - Полное архитектурное решение

## Обзор

В рамках данного проекта был успешно доведен существующий PromptRepository до состояния production-ready компонента. Решение включает полный жизненный цикл промтов, контракты переменных, снапшоты выполнения и защиту от деградации поведения.

## Основные компоненты

### 1. Модель данных PromptVersion

Обновленная модель включает:

- **Идентификация**: id, semantic_version (MAJOR.MINOR.PATCH)
- **Адресация**: domain, provider_type, capability_name, role
- **Содержимое**: content, variables_schema (с валидацией типов)
- **Контракт вывода**: expected_response_schema
- **Жизненный цикл**: status (draft/active/shadow/deprecated/archived), даты активации/деактивации
- **Метрики**: usage_metrics (количество использований, успехи, время генерации, ошибки)

### 2. Статусы жизненного цикла

- **DRAFT**: Черновик, не готов к использованию
- **ACTIVE**: Активная версия, используется в системе
- **SHADOW**: Экспериментальная версия для A/B тестирования
- **DEPRECATED**: Устаревшая, но еще работает
- **ARCHIVED**: Архивированная, больше не используется

### 3. Контракты переменных

Каждый промт теперь имеет строго определенную схему переменных:

```python
class VariableSchema(BaseModel):
    name: str
    type: str  # "string", "integer", "boolean", "array", "object"
    required: bool = True
    description: str = ""
    default_value: Optional[Any] = None
    validation_pattern: Optional[str] = None  # regex для валидации строки
```

## Архитектурные слои

### Domain Layer
- `PromptVersion`: Модель данных
- `IPromptRepository`: Абстракция репозитория
- `ISnapshotManager`: Абстракция менеджера снапшотов

### Infrastructure Layer
- `DatabasePromptRepository`: Реализация репозитория с использованием DBProvider
- `DatabaseSnapshotManager`: Реализация менеджера снапшотов
- `PromptFileSyncService`: Синхронизация файлов и БД

### Application Layer
- `PromptRenderer`: Рендеринг промтов с валидацией переменных
- `CachedPromptRepository`: Кэширование в памяти
- `PromptSystemInitializer`: Инициализация системы промтов

## Ключевые особенности

### 1. Валидация переменных
- Проверка наличия обязательных переменных
- Проверка соответствия типов (строка, число, булево, массив, объект)
- Проверка соответствия регулярным выражениям для строк
- Защита от инъекций (подстановка только тех переменных, которые определены в схеме)

### 2. Snapshot'ы выполнения
Каждый вызов промта создает снапшот с информацией:
- ID промта и сессии
- Отрендеренный промт
- Переменные подстановки
- Время выполнения
- Статус успеха/ошибки
- Причины отклонения (если есть)

### 3. Кэширование
- `CachedPromptRepository` обеспечивает кэширование в памяти
- Индексация по адресам (domain:provider:capability:role)
- Инвалидация кэша при изменениях
- Блокировки для многопоточного доступа

### 4. Хранение данных
- **Source of Truth**: Файловая система (Git) - для версионности и аудита
- **Runtime Storage**: PostgreSQL/GreenPlum - для высокой доступности
- **In-Memory Cache**: Локальный кэш - для быстрого доступа

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

## Тестирование

Созданы полные тесты, проверяющие:
- Жизненный цикл промтов
- Валидацию переменных
- Рендеринг с проверкой
- Переходы статусов
- Работу снапшотов

## Использование

### Инициализация системы
```python
from application.services.prompt_system_initializer import PromptSystemInitializer
from infrastructure.gateways.database_providers.postgresql_provider import PostgreSQLProvider

# Создаем DBProvider
db_config = {
    "host": "localhost",
    "port": 5432,
    "database": "prompts_db",
    "username": "user",
    "password": "password"
}
db_provider = PostgreSQLProvider("postgresql://...", db_config)
await db_provider.initialize()

# Инициализируем систему промтов
initializer = PromptSystemInitializer(db_provider)
prompt_repository = await initializer.initialize()
```

### Использование в агенте
```python
from application.services.prompt_renderer import PromptRenderer

# Создаем рендерер с репозиторием и менеджером снапшотов
renderer = PromptRenderer(prompt_repository, snapshot_manager)

# Рендерим промт для запроса
rendered_prompts, snapshot, errors = await renderer.render_and_create_snapshot(
    capability=capability,
    provider_type=LLMProviderType.OPENAI,
    template_context=context,
    session_id=session_id
)
```

## Production Checklist

### Что проверять перед релизом:
- [x] Все методы PromptRepository реализованы и протестированы
- [x] Валидация переменных работает корректно
- [x] Жизненный цикл статусов работает (draft → active → deprecated → archived)
- [x] SnapshotManager корректно сохраняет и извлекает данные
- [x] Ошибки валидации переменных обрабатываются корректно
- [x] Метрики использования обновляются
- [x] Обратная совместимость сохранена
- [x] Нет утечки чувствительных данных в логах

### Фатальные ошибки:
- [x] Невозможно получить активную версию промта
- [x] Ошибка валидации обязательных переменных
- [x] Нарушение контракта переменных
- [x] Ошибка сохранения снапшота выполнения

### Контроль деградации:
- [x] Мониторинг процента ошибок (должен быть < 5%)
- [x] Мониторинг времени генерации (должно быть в пределах SLA)
- [x] Мониторинг процента отклонений валидатором
- [x] Сравнение производительности между версиями промтов

## Заключение

Проект успешно реализовал production-ready PromptRepository, который:

1. Обеспечивает полный жизненный цикл промтов
2. Внедряет строгую валидацию переменных
3. Обеспечивает полную видимость выполнения через снапшоты
4. Защищает от деградации поведения
5. Поддерживает масштабируемую архитектуру с разделением ответственности
6. Совместим с GreenPlum/PostgreSQL
7. Обеспечивает надежное хранение и версионность

Система готова к использованию в продакшене и может масштабироваться в соответствии с требованиями.