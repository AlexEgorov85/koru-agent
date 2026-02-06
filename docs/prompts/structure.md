# Структура хранения промтов

Система хранения промтов Koru AI Agent Framework организована в иерархическую структуру, обеспечивающую удобное управление, версионирование и доступ к промтам различных доменов и ролей. В этом разделе описаны принципы организации и формат хранения промтов.

## Общая структура

Промты хранятся в директории `prompts/` в следующей иерархии:

```
prompts/
├── {domain}/                    # Домен (например, code_analysis, data_processing)
│   └── {capability}/            # Капабилити (например, code_generation, data_query)
│       ├── {role}/              # Роль (system, user, assistant, tool)
│       │   ├── v{version}.md    # Файл версии промта
│       │   └── ...
│       └── _index.yaml          # Индекс капабилити (опционально)
└── ...
```

Где:
- `{domain}` - тип домена (например, `code_analysis`, `data_processing`, `content_generation`)
- `{capability}` - функциональная возможность (например, `security_analysis`, `code_review`, `data_transformation`)
- `{role}` - роль в диалоге (например, `system`, `user`, `assistant`, `tool`)
- `{version}` - семантическая версия в формате `MAJOR.MINOR.PATCH` (например, `1.0.0`)

## Пример структуры

```
prompts/
├── code_analysis/
│   ├── security_analysis/
│   │   ├── system/
│   │   │   ├── v1.0.0.md
│   │   │   ├── v1.1.0.md
│   │   │   └── v2.0.0.md
│   │   ├── user/
│   │   │   ├── v1.0.0.md
│   │   │   └── v1.1.0.md
│   │   └── assistant/
│   │       ├── v1.0.0.md
│   │       └── v1.1.0.md
│   └── code_review/
│       ├── system/
│       │   ├── v1.0.0.md
│       │   └── v1.1.0.md
│       └── user/
│           ├── v1.0.0.md
│           └── v1.1.0.md
├── data_processing/
│   ├── data_transformation/
│   │   ├── system/
│   │   │   └── v1.0.0.md
│   │   └── tool/
│   │       └── v1.0.0.md
│   └── data_validation/
│       ├── system/
│       │   └── v1.0.0.md
│       └── user/
│           └── v1.0.0.md
└── content_generation/
    └── report_generation/
        ├── system/
        │   └── v1.0.0.md
        └── assistant/
            └── v1.0.0.md
```

## Формат файла промта

Каждый файл промта использует формат Markdown с YAML frontmatter:

```markdown
---
provider: openai
role: system
status: active
variables:
  - name: task_description
    type: string
    required: true
    description: "Описание задачи для анализа"
  - name: code_snippet
    type: string
    required: false
    description: "Фрагмент кода для анализа"
  - name: language
    type: string
    required: false
    default_value: "python"
    description: "Язык программирования кода"
expected_response:
  type: object
  properties:
    analysis:
      type: string
      description: "Анализ предоставленного кода"
    vulnerabilities:
      type: array
      items:
        type: object
        properties:
          type:
            type: string
            description: "Тип уязвимости"
          severity:
            type: string
            description: "Уровень серьезности"
          description:
            type: string
            description: "Описание уязвимости"
          recommendation:
            type: string
            description: "Рекомендации по устранению"
---

# Инструкции для анализа безопасности кода

Ты являешься экспертом в области безопасности кода. При анализе кода на безопасность следуй следующим принципам:

1. Идентифицируй потенциальные уязвимости в коде
2. Оцени уровень риска каждой уязвимости
3. Предложи конкретные рекомендации по устранению
4. Объясни, почему каждая уязвимость представляет риск

## Контекст задачи

Задача: {{task_description}}

## Код для анализа

```
{{code_snippet}}
```

## Инструкции по анализу

Пожалуйста, проанализируй предоставленный код наличие следующих типов уязвимостей:
- SQL-инъекции
- XSS (Cross-Site Scripting)
- CSRF (Cross-Site Request Forgery)
- Уязвимости в обработке ввода
- Небезопасное хранение данных
- Проблемы с аутентификацией и авторизацией

Ответь в формате JSON с полями: analysis, vulnerabilities.
```

## Структура YAML frontmatter

### Обязательные поля

- `provider`: Тип LLM-провайдера (`openai`, `anthropic`, `huggingface`, `custom`)
- `role`: Роль промта (`system`, `user`, `assistant`, `tool`)
- `status`: Статус промта (`draft`, `active`, `shadow`, `deprecated`, `archived`)

### Опциональные поля

- `variables`: Список переменных, используемых в промте
- `expected_response`: Ожидаемая структура ответа
- `version_notes`: Примечания к версии
- `activation_date`: Дата активации версии
- `deprecation_date`: Дата устаревания версии
- `author`: Автор версии промта
- `reviewed_by`: Кто провел ревью
- `tags`: Теги для категоризации

### Структура переменных

Каждая переменная в списке `variables` должна содержать:

```yaml
- name: имя_переменной
  type: тип_данных  # string, integer, boolean, array, object
  required: true/false
  description: "Описание переменной"
  default_value: значение_по_умолчанию  # опционально
  validation_pattern: "регулярное_выражение"  # для строковых значений
```

### Структура expected_response

Определяет ожидаемую структуру ответа в формате JSON Schema:

```yaml
expected_response:
  type: object
  properties:
    field_name:
      type: string
      description: "Описание поля"
  required:
    - field_name
```

## Роли промтов

Система поддерживает следующие роли:

### 1. System (system)
- Используется для задания контекста и инструкций для LLM
- Обычно содержит основные правила поведения и инструкции
- Пример: инструкции для анализа кода, правила безопасности

### 2. User (user)
- Используется для предоставления пользовательского ввода
- Содержит конкретные запросы или данные для обработки
- Пример: фрагменты кода для анализа, вопросы

### 3. Assistant (assistant)
- Используется для эмуляции ответов ассистента
- Полезен для few-shot обучения и примеров
- Пример: образцы правильных ответов

### 4. Tool (tool)
- Используется для взаимодействия с инструментами
- Содержит инструкции для вызова инструментов
- Пример: формат вызова SQL-запроса, формат вызова API

## Версионирование

Система использует семантическое версионирование (SemVer):

- `MAJOR.MINOR.PATCH` (например, `1.2.3`)
- `MAJOR` - значительные изменения, нарушающие обратную совместимость
- `MINOR` - добавление новой функциональности с сохранением совместимости
- `PATCH` - исправление ошибок без изменения функциональности

### Стратегии версионирования

1. **Контроль изменений**: Каждое изменение в логике промта требует новой версии
2. **Обратная совместимость**: PATCH-версии не должны менять ожидаемую структуру ответа
3. **Тестирование**: Каждая новая версия должна быть протестирована перед активацией
4. **Миграция**: Старые версии могут быть помечены как deprecated, но остаются доступными

## Индексные файлы

Для крупных капабилити можно создавать индексные файлы `_index.yaml`:

```yaml
# prompts/code_analysis/security_analysis/_index.yaml
capability:
  name: security_analysis
  description: "Анализ кода на наличие уязвимостей безопасности"
  domain: code_analysis
  version: 1.0.0
  
versions:
 - version: 1.0.0
    status: active
    created: "2023-01-15"
    author: "author_name"
    changes: "Initial version"
  - version: 1.1.0
    status: deprecated
    created: "2023-02-20"
    author: "author_name"
    changes: "Added support for Python 3.9 features"
    
dependencies:
  - capability: code_parsing
    version: ">=1.0.0"
  
tags:
  - security
  - code-analysis
  - vulnerability
```

## Лучшие практики

### 1. Именование доменов
- Используйте понятные имена: `code_analysis`, `data_processing`, `content_generation`
- Избегайте аббревиатур, если они не общеприняты
- Используйте snake_case для именования

### 2. Именование капабилити
- Называйте по функциональности: `security_analysis`, `code_review`, `data_transformation`
- Будьте конкретны в названиях
- Используйте глаголы в прошедшем времени для описания действия

### 3. Организация версий
- Начинайте с версии `1.0.0` для стабильных промтов
- Используйте `0.x.y` для экспериментальных промтов
- Поддерживайте четкую историю изменений

### 4. Документирование
- Всегда указывайте `description` для переменных
- Используйте `version_notes` для описания изменений
- Добавляйте `tags` для лучшей категоризации

## Валидация структуры

Система включает валидацию структуры промтов:

- Проверка формата имен файлов (`vX.Y.Z.md`)
- Проверка обязательных полей в YAML frontmatter
- Валидация структуры переменных
- Проверка корректности путей к файлам

## Интеграция с системой

Система хранения промтов интегрирована с:

- **Загрузчиком промтов**: `PromptLoader` автоматически сканирует структуру
- **Системой валидации**: Проверяет переменные и ожидаемые ответы
- **Системой версионирования**: Управляет активными и устаревшими версиями
- **Системой кэширования**: Оптимизирует доступ к часто используемым промтам