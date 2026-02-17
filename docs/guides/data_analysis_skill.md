# DataAnalysisSkill — Анализ данных по шагу

## Обзор

`DataAnalysisSkill` — навык для анализа сырых данных, связанных с конкретным шагом выполнения агента, и генерации ответов на пользовательские вопросы.

## Возможности

✅ **Поддержка источников данных:**
- Файлы (CSV, JSON, TXT) через `FileTool`
- Базы данных (через `SQLTool`)
- Память (данные из `SessionContext`)

✅ **Обработка больших данных:**
- Автоматический чанкинг при превышении лимита токенов
- 4 стратегии агрегации: `summary`, `statistical`, `extractive`, `generative`
- Конфигурируемый размер чанка и лимит количества

✅ **Качественный анализ:**
- Валидация входных/выходных данных через контракты
- Оценка уверенности в ответе (0.0–1.0)
- Предоставление доказательств с источниками

✅ **Архитектурная интеграция:**
- Изолированные кэши промптов/контрактов через `ComponentConfig`
- Доступ к инструментам через `ApplicationContext`
- Поддержка профилей `prod`/`sandbox`

## Использование

### Базовый вызов

```python
# Получение навыка из контекста
skill = app_context.components.get(ComponentType.SKILL, "data_analysis")

parameters = {
    "step_id": "step_abc123",
    "question": "Какие ключевые выводы можно сделать из данных?",
    "data_source": {
        "type": "file",
        "path": "/data/step_abc123/results.csv"
    }
}

capability = skill.get_capabilities()[0]
result = await skill.execute(
    capability=capability,
    parameters=parameters,
    execution_context=execution_context
)

print(result.result["answer"])
print(f"Уверенность: {result.result['confidence']:.2%}")
```

### Анализ больших данных

```python
parameters = {
    "step_id": "step_large",
    "question": "Опиши основные тренды в данных",
    "data_source": {
        "type": "database",
        "path": "analytics.events",
        "query": "SELECT * FROM events WHERE step_id = 'step_large'"
    },
    "analysis_config": {
        "chunk_size": 1500,
        "max_chunks": 30,
        "aggregation_method": "summary",
        "max_response_tokens": 2500
    }
}
```

### Стратегии агрегации

| Метод | Описание | Когда использовать |
|-------|----------|------------------|
| `summary` | Краткое содержание каждого чанка | Общий обзор, извлечение идей |
| `statistical` | Вычисление метрик и паттернов | Числовые данные, аналитика |
| `extractive` | Поиск прямых цитат | Фактологические вопросы |
| `generative` | Синтез на основе контекста | Сложные вопросы с интерпретацией |

## Параметры

### Обязательные

| Параметр | Тип | Описание |
|----------|-----|----------|
| `step_id` | string | ID шага для анализа |
| `question` | string | Вопрос пользователя |
| `data_source` | object | Источник данных |

### data_source

| Поле | Тип | Описание |
|------|-----|----------|
| `type` | string | Тип источника: `file`, `database`, `memory` |
| `path` | string | Путь к файлу или имя таблицы |
| `query` | string | SQL-запрос для фильтрации (опционально) |
| `content` | string | Сырые данные (для `type: memory`) |

### analysis_config (опционально)

| Поле | Тип | По умолчанию | Описание |
|------|-----|-------------|----------|
| `chunk_size` | integer | 2000 | Токенов на чанк |
| `max_chunks` | integer | 50 | Максимум чанков |
| `aggregation_method` | string | summary | Стратегия агрегации |
| `max_response_tokens` | integer | 2000 | Максимум токенов в ответе |
| `max_rows` | integer | 10000 | Максимум строк из БД |

## Формат ответа

```json
{
  "answer": "Прямой и конкретный ответ на вопрос",
  "confidence": 0.95,
  "evidence": [
    {
      "source": "чанк_3, строки 15-20",
      "excerpt": "Цитата или краткое описание",
      "relevance_score": 0.9
    }
  ],
  "metadata": {
    "chunks_processed": 3,
    "total_tokens": 1500,
    "processing_time_ms": 1200,
    "data_size_mb": 2.5
  }
}
```

## Обработка ошибок

| Ситуация | Поведение |
|----------|-----------|
| Недостаточно данных | Ответ с `confidence < 0.5` |
| Ошибка загрузки данных | `ExecutionStatus.FAILED` с описанием |
| Невалидный ответ от LLM | Fallback-парсинг, снижение `confidence` |
| Превышение лимита чанков | Обработка первых `max_chunks` |

## Best Practices

1. **Конкретные вопросы** — чем точнее вопрос, тем качественнее ответ
2. **Фильтры в SQL** — уменьшайте объём данных до загрузки
3. **Настройка `chunk_size`** — меньше для точности, больше для контекста
4. **Проверка `confidence`** — значения < 0.7 требуют верификации
5. **Использование `evidence`** — сохраняйте источники для аудита

## Архитектура

```
DataAnalysisSkill
├── BaseSkill
│   └── BaseComponent (изолированные кэши)
├── Промпты: data_analysis.analyze_step_data
├── Контракты:
│   ├── input: data_analysis.analyze_step_data.input.v1.0.0
│   └── output: data_analysis.analyze_step_data.output.v1.0.0
└── Зависимости:
    ├── file_tool
    ├── sql_tool
    └── LLM Provider (через ApplicationContext)
```

## Тестирование

```bash
# Запуск unit-тестов
pytest tests/application/skills/test_data_analysis_skill.py -v

# Запуск с покрытием
pytest tests/application/skills/test_data_analysis_skill.py --cov=core.application.skills.data_analysis
```

## Примеры использования

### Пример 1: Анализ CSV файла

```python
parameters = {
    "step_id": "step_sales_analysis",
    "question": "Какой продукт имеет наибольшие продажи?",
    "data_source": {
        "type": "file",
        "path": "/data/sales/q1_2026.csv"
    },
    "analysis_config": {
        "aggregation_method": "statistical"
    }
}
```

### Пример 2: Анализ данных из БД

```python
parameters = {
    "step_id": "step_user_behavior",
    "question": "Какие действия пользователи выполняют чаще всего?",
    "data_source": {
        "type": "database",
        "path": "analytics.user_actions",
        "query": """
            SELECT action_type, COUNT(*) as count 
            FROM user_actions 
            WHERE session_id = 'abc123'
            GROUP BY action_type
            ORDER BY count DESC
        """
    }
}
```

### Пример 3: Анализ данных из памяти

```python
# Данные уже загружены в контекст
session_data = await load_data_to_context(...)

parameters = {
    "step_id": "step_memory_analysis",
    "question": "Суммарное значение всех транзакций?",
    "data_source": {
        "type": "memory",
        "content": session_data
    },
    "analysis_config": {
        "aggregation_method": "statistical"
    }
}
```

## Метрики качества

| Метрика | Значение |
|---------|----------|
| Целевой success_rate | 0.95 |
| Среднее время выполнения | 1500 мс |
| Порог error_rate | 0.05 |
| Максимальный размер данных | 100 MB |
| Таймаут выполнения | 300 секунд |

## Changelog

### v1.0.0 (2026-02-17)
- Initial release
- Поддержка анализа данных с чанкингом
- 4 стратегии агрегации: summary/statistical/extractive/generative
- Интеграция с FileTool и SQLTool
- Валидация через контракты
