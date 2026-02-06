# Обзор системы управления промтами

Система управления промтами - это ключевой компонент Composable AI Agent Framework, обеспечивающий гибкое управление, версионирование и валидацию промтов. Система позволяет эффективно работать с различными стратегиями взаимодействия с LLM, поддерживает различные домены и провайдеров, а также обеспечивает прозрачность и отслеживаемость использования промтов.

## Основные возможности

- **Версионирование промтов** - каждая версия промта хранится с уникальным идентификатором и семантической версией
- **Валидация переменных** - проверка соответствия входных данных схеме промта
- **Валидация ответов** - проверка выходных данных по заданной схеме
- **Поддержка ролей** - поддержка различных ролей (system, user, assistant, tool)
- **Метрики использования** - сбор статистики использования промтов
- **Поддержка доменов** - адаптация промтов к различным областям задач
- **Поддержка провайдеров** - работа с различными LLM провайдерами

## Модель данных промта

Центральным элементом системы является модель `PromptVersion`, определенная в `domain/models/prompt/prompt_version.py`:

```python
class PromptVersion(BaseModel):
    """
    Версия промта с полным жизненным циклом и контрактами
    """
    
    # === Идентификация ===
    id: str = Field(default_factory=lambda: f"prompt_{uuid4().hex[:12]}")
    semantic_version: str = Field(pattern=r"^\d+\.\d+\.\d+$")  # MAJOR.MINOR.PATCH
    
    # === Адресация ===
    domain: DomainType
    provider_type: LLMProviderType
    capability_name: str
    role: PromptRole
    
    # === Содержимое ===
    content: str = Field(description="Текст промта")
    max_size_bytes: int = Field(default=500_000, description="Максимальный размер промта в байтах (по умолчанию 500KB)")
    variables_schema: List[VariableSchema] = Field(
        default_factory=list,
        description="Схема переменных шаблона с валидацией"
    )
    
    # === Контракт вывода ===
    expected_response_schema: Optional[Dict[str, Any]] = Field(
        default=None,
        description="JSON Schema для валидации ответа"
    )
    
    # === Жизненный цикл ===
    status: PromptStatus = Field(default=PromptStatus.DRAFT, description="Статус жизненного цикла")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    activation_date: Optional[datetime] = Field(default=None, description="Дата активации")
    deprecation_date: Optional[datetime] = Field(default=None, description="Дата устаревания")
    archived_date: Optional[datetime] = Field(default=None, description="Дата архивации")
    
    # === История изменений ===
    parent_version_id: Optional[str] = Field(default=None, description="ID родительской версии")
    version_notes: str = Field(default="", description="Описание изменений в версии")
    
    # === Метрики ===
    usage_metrics: PromptUsageMetrics = Field(default_factory=PromptUsageMetrics)
```

## Статусы жизненного цикла

Промты проходят через различные статусы в своем жизненном цикле:

- **DRAFT** - Черновик, не готов к использованию
- **ACTIVE** - Активная версия, используется в системе
- **SHADOW** - Экспериментальная версия для A/B тестирования
- **DEPRECATED** - Устаревшая, но еще работает
- **ARCHIVED** - Архивированная, больше не используется

## Роли промтов

Система поддерживает различные роли промтов, соответствующие форматам провайдеров:

- **SYSTEM** - Системные промты, определяющие поведение агента
- **USER** - Промты, представляющие пользовательский ввод
- **ASSISTANT** - Промты, имитирующие ответы ассистента
- **TOOL** - Промты для вызова инструментов

## Структура хранения

Промты хранятся в структурированной файловой системе:

```
prompts/
├── {domain}/                    # Домен (например, code_analysis, data_processing)
│   └── {capability}/            # Капабилити (например, code_generation, data_query)
│       ├── {role}/              # Роль (system, user, assistant, tool)
│       │   ├── v1.0.0.md        # Версия промта
│       │   ├── v1.1.0.md        # Следующая версия
│       │   └── ...
│       └── _index.yaml          # Индекс капабилити (опционально)
```

Пример структуры:

```
prompts/
├── code_analysis/
│   └── code_review/
│       ├── system/
│       │   └── v1.0.0.md
│       ├── user/
│       │   └── v1.0.0.md
│       └── assistant/
│           └── v1.0.0.md
└── data_processing/
    └── data_transformation/
        ├── system/
        │   └── v1.0.md
        └── tool/
            └── v1.0.0.md
```

## Формат файла промта

Файлы промтов используют формат Markdown с YAML frontmatter:

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
expected_response:
  type: object
  properties:
    analysis:
      type: string
      description: "Анализ предоставленного кода"
    suggestions:
      type: array
      items:
        type: string
      description: "Предложения по улучшению кода"
---

# Инструкции для анализа кода

Ты являешься экспертом в области анализа кода. При анализе кода следуй следующим принципам:

1. Оцени качество кода по критериям: читаемость, эффективность, безопасность
2. Ищи потенциальные баги и уязвимости
3. Предлагай конкретные улучшения с обоснованием
4. Учитывай контекст задачи: {{task_description}}

Код для анализа:
```

## Загрузчик промтов

Система включает `PromptLoader` для загрузки промтов из файловой системы:

```python
class PromptLoader:
    """
    Загрузчик промтов из файловой системы.
    
    Поддерживает структуру:
    prompts/
    ├── {domain}/
    │   └── {capability}/
    │       ├── {role}/
    │       │   └── v{version}.md
    │       └── _index.yaml
    """
    
    def load_all_prompts(self) -> Tuple[List[PromptVersion], List[str]]:
        """
        Загружает все промты из файловой системы.
        Поддерживает структуру: prompts/{domain}/{capability}/{role}/v{version}.md
        
        Returns:
            Tuple[List[PromptVersion], List[str]]: Кортеж из списка загруженных промтов и списка ошибок
        """
        pass
```

## Валидация переменных

Система включает механизм валидации переменных по схеме:

```python
def validate_variables(self, variables: Dict[str, Any]) -> Dict[str, List[str]]:
    """Валидация переменных по схеме, возвращает ошибки"""
    errors = {}
    
    for schema_var in self.variables_schema:
        var_name = schema_var.name
        required = schema_var.required
        
        if required and var_name not in variables:
            errors[var_name] = [f"Обязательная переменная '{var_name}' отсутствует"]
            continue
            
        if var_name in variables:
            value = variables[var_name]
            
            # Проверка типа
            expected_type = schema_var.type
            actual_type = type(value).__name__
            
            if expected_type == "string" and not isinstance(value, str):
                errors.setdefault(var_name, []).append(f"Ожидается строка, получено {actual_type}")
            elif expected_type == "integer" and not isinstance(value, int):
                errors.setdefault(var_name, []).append(f"Ожидается целое число, получено {actual_type}")
            # ... другие проверки типов
```

## Снимки выполнения

Система поддерживает снимки выполнения промтов для аудита и отладки:

```python
class PromptExecutionSnapshot(BaseModel):
    """Снимок выполнения промта"""
    id: str = Field(default_factory=lambda: f"snapshot_{uuid4().hex[:12]}")
    prompt_id: str
    session_id: str
    rendered_prompt: str
    variables: Dict[str, Any]
    response: Optional[str] = None
    execution_time: float = 0.0
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    success: bool = True
    error_message: Optional[str] = None
    rejection_reason: Optional[str] = None  # Если валидатор отклонил
    provider_response_time: float = 0.0
```

## Интеграция с агентами

Промты интегрируются с агентами через систему репозиториев:

- Агенты запрашивают промты по адресу (домен:капабилити:провайдер:роль)
- Система выбирает подходящую версию промта на основе статуса и совместимости
- Переменные промта валидируются перед использованием
- Результаты выполнения могут быть валидированы по ожидаемой схеме

## Преимущества системы

- **Прозрачность**: Полная история изменений и версий промтов
- **Контролируемость**: Валидация входных и выходных данных
- **Масштабируемость**: Поддержка различных доменов и провайдеров
- **Надежность**: Встроенная система метрик и аудита
- **Гибкость**: Возможность A/B тестирования различных версий
- **Интеграция**: Легкая интеграция с различными LLM провайдерами