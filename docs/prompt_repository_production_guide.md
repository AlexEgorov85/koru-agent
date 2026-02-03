# Production-Ready PromptRepository - Архитектурное решение

## 1. Обзор

В данном документе представлено архитектурное решение для доведения существующего PromptRepository до состояния production-ready компонента. Решение включает:

- Полный жизненный цикл промтов (draft → active → shadow → deprecated → archived)
- Контракты переменных с валидацией
- Snapshot'ы исполнения для отслеживания производительности
- Защиту от деградации поведения
- Интеграцию с файловой системой и базой данных

## 2. Архитектурные компоненты

### 2.1 Модель данных PromptVersion

Обновленная модель `PromptVersion` включает:

- **Идентификация**: id, semantic_version (MAJOR.MINOR.PATCH)
- **Адресация**: domain, provider_type, capability_name, role
- **Содержимое**: content, variables_schema (с валидацией типов)
- **Контракт вывода**: expected_response_schema
- **Жизненный цикл**: status (draft/active/shadow/deprecated/archived), даты активации/деактивации
- **Метрики**: usage_metrics (количество использований, успехи, время генерации, ошибки)

### 2.2 Статусы жизненного цикла

- **DRAFT**: Черновик, не готов к использованию
- **ACTIVE**: Активная версия, используется в системе
- **SHADOW**: Экспериментальная версия для A/B тестирования
- **DEPRECATED**: Устаревшая, но еще работает
- **ARCHIVED**: Архивированная, больше не используется

### 2.3 Контракты переменных

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

## 3. Слои архитектуры

### 3.1 Domain Layer
- `PromptVersion`: Модель данных
- `IPromptRepository`: Абстракция репозитория
- `ISnapshotManager`: Абстракция менеджера снапшотов

### 3.2 Infrastructure Layer
- `DatabasePromptRepository`: Реализация репозитория с использованием DBProvider
- `DatabaseSnapshotManager`: Реализация менеджера снапшотов
- `PromptFileSyncService`: Синхронизация файлов и БД

### 3.3 Application Layer
- `PromptRenderer`: Рендеринг промтов с валидацией переменных
- `CachedPromptRepository`: Кэширование в памяти
- `PromptSystemInitializer`: Инициализация системы промтов

## 4. Поток выполнения

### 4.1 Полный поток от FS → Repository → Renderer → LLM

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

### 4.2 Формат промтов в файловой системе

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

## 5. Валидация переменных

Система проверяет:
- Наличие обязательных переменных
- Соответствие типов (строка, число, булево, массив, объект)
- Соответствие регулярным выражениям для строк
- Защита от инъекций (подстановка только тех переменных, которые определены в схеме)

## 6. Snapshot'ы выполнения

Каждый вызов промта создает снапшот с информацией:
- ID промта и сессии
- Отрендеренный промт
- Переменные подстановки
- Время выполнения
- Статус успеха/ошибки
- Причины отклонения (если есть)

## 7. Кэширование

- `CachedPromptRepository` обеспечивает кэширование в памяти
- Индексация по адресам (domain:provider:capability:role)
- Инвалидация кэша при изменениях
- Блокировки для многопоточного доступа

## 8. Хранение данных

- **Source of Truth**: Файловая система (Git) - для версионности и аудита
- **Runtime Storage**: PostgreSQL/GreenPlum - для высокой доступности
- **In-Memory Cache**: Локальный кэш - для быстрого доступа

## 9. Production Checklist

### 9.1 Что проверять перед релизом:

- [ ] Все методы PromptRepository реализованы и протестированы
- [ ] Валидация переменных работает корректно
- [ ] Жизненный цикл статусов работает (draft → active → deprecated → archived)
- [ ] SnapshotManager корректно сохраняет и извлекает данные
- [ ] Ошибки валидации переменных обрабатываются корректно
- [ ] Метрики использования обновляются
- [ ] Обратная совместимость сохранена
- [ ] Нет утечки чувствительных данных в логах

### 9.2 Фатальные ошибки:

- [ ] Невозможно получить активную версию промта
- [ ] Ошибка валидации обязательных переменных
- [ ] Нарушение контракта переменных
- [ ] Ошибка сохранения снапшота выполнения

### 9.3 Допустимые ошибки:

- [ ] Ошибки при получении теневой (shadow) версии (не фатально)
- [ ] Ошибки при сохранении метрик (не должно влиять на основной поток)
- [ ] Ошибки при сохранении снапшотов (не должно влиять на основной поток)

### 9.4 Контроль деградации:

- [ ] Мониторинг процента ошибок (должен быть < 5%)
- [ ] Мониторинг времени генерации (должно быть в пределах SLA)
- [ ] Мониторинг процента отклонений валидатором
- [ ] Сравнение производительности между версиями промтов

## 10. Использование

### 10.1 Инициализация системы

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

### 10.2 Использование в агенте

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

Это архитектурное решение позволяет довести PromptRepository до production-ready состояния, сохранив существующую архитектуру и расширив её необходимыми компонентами для надёжной работы в продакшене.