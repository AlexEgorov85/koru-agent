# 📊 Валидация бенчмарков — Руководство

## 🎯 Обзор

Система валидации бенчмарков предназначена для автоматической оценки качества ответов агента.

**Компоненты:**
- `benchmark_validator.py` — модуль валидации
- `run_agent_benchmark.py` — запуск бенчмарка с валидацией
- `run_real_agent_benchmark.py` — запуск реального агента с валидацией

---

## 📁 Структура валидатора

```
core/benchmarks/
├── __init__.py                # Экспорт классов
└── benchmark_validator.py     # Модуль валидации
    ├── SQLValidator           # Валидация SQL запросов
    ├── AnswerValidator        # Валидация финальных ответов
    └── BenchmarkValidator     # Фасад для комплексной валидации
```

**Компоненты:**
- `core/benchmarks/` — модуль бенчмарков (код)
- `data/benchmarks/` — файлы бенчмарков (данные JSON)
- `scripts/cli/run_agent_benchmark.py` — запуск бенчмарка
- `scripts/cli/run_real_agent_benchmark.py` — запуск реального агента

---

## ✅ Правила валидации SQL

| Правило | Описание | Пример |
|---------|----------|--------|
| `must_be_valid_sql` | Базовая проверка валидности SQL | `SELECT...FROM` ✅ |
| `must_have_tables` | Наличие требуемых таблиц | `['books', 'authors']` |
| `must_have_where` | Наличие WHERE clause | `WHERE author_id = 1` ✅ |
| `must_have_join` | Наличие JOIN | `JOIN authors ON...` ✅ |
| `must_have_count` | Наличие COUNT() | `COUNT(*)` ✅ |
| `must_have_year_filter` | Фильтр по году | `WHERE year > 1850` ✅ |
| `must_have_group_by` | Наличие GROUP BY | `GROUP BY author_id` ✅ |
| `must_have_order_by` | Наличие ORDER BY | `ORDER BY title` ✅ |
| `must_return_correct_columns` | Проверка колонок в SELECT | `['title', 'isbn']` |
| `must_have_multiple_authors` | Поддержка нескольких авторов | `IN (id1, id2)` ✅ |

### Пример валидации SQL

```python
from core.benchmarks import BenchmarkValidator

validator = BenchmarkValidator()

sql = """
    SELECT b.title, a.name
    FROM books b
    JOIN authors a ON b.author_id = a.id
    WHERE a.last_name = 'Гоголь'
"""

rules = {
    'must_have_tables': ['books', 'authors'],
    'must_have_where': True,
    'must_have_join': True,
    'must_be_valid_sql': True
}

result = validator.validate_sql_generation(sql, rules)

print(result)
# {
#     'passed': True,
#     'errors': [],
#     'checks': {
#         'sql_valid': True,
#         'has_tables': True,
#         'has_where': True,
#         'has_join': True,
#         'tables_found': ['books', 'authors']
#     }
# }
```

---

## ✅ Правила валидации Final Answer

| Правило | Описание | Пример |
|---------|----------|--------|
| `must_contain_keywords` | Наличие ключевых слов | `['Мёртвые души', 'Ревизор']` |
| `must_be_in_russian` | Ответ на русском языке | Кириллица ≥50% ✅ |
| `must_not_hallucinate` | Отсутствие выдумок | Сверка с БД |
| `min_length` | Минимальная длина | `20` символов |
| `must_mention_author` | Упоминание автора | `"Гоголь"` в ответе ✅ |
| `must_indicate_no_results` | Указание на отсутствие результатов | "ничего не найдено" ✅ |
| `must_be_polite` | Вежливость ответа | "к сожалению" ✅ |
| `must_contain_number` | Наличие числа | `"33 книги"` ✅ |

### Пример валидации ответа

```python
from core.benchmarks import BenchmarkValidator

validator = BenchmarkValidator()

answer = "Николай Гоголь написал: Мёртвые души, Ревизор, Тарас Бульба"

rules = {
    'must_contain_keywords': ['Мёртвые души', 'Ревизор', 'Тарас Бульба'],
    'must_be_in_russian': True,
    'must_mention_author': True,
    'min_length': 20
}

context = {
    'metadata': {'author': 'Николай Гоголь'}
}

result = validator.validate_final_answer(answer, rules, context)

print(result)
# {
#     'passed': True,
#     'errors': [],
#     'checks': {
#         'has_keywords': True,
#         'is_russian': True,
#         'cyrillic_ratio': 1.0,
#         'mentions_author': True,
#         'length': 67
#     }
# }
```

---

## 🔄 Комплексная валидация теста

```python
from core.benchmarks import BenchmarkValidator

validator = BenchmarkValidator()

# Тестовый кейс из бенчмарка
test_case = {
    'id': 'sql_gogol',
    'validation': {
        'must_have_tables': ['books', 'authors'],
        'must_have_where': True,
        'must_have_join': True,
        'must_contain_keywords': ['Мёртвые души', 'Ревизор'],
        'must_be_in_russian': True
    },
    'expected_output': {
        'books': [
            {'title': 'Мёртвые души'},
            {'title': 'Ревизор'}
        ]
    }
}

# Ответ агента
agent_response = {
    'sql': """
        SELECT b.title FROM books b
        JOIN authors a ON b.author_id = a.id
        WHERE a.last_name = 'Гоголь'
    """,
    'final_answer': 'Гоголь написал: Мёртвые души, Ревизор'
}

# Комплексная валидация
result = validator.validate_test_result(test_case, agent_response)

print(result)
# {
#     'test_id': 'sql_gogol',
#     'sql_validation': {...},
#     'answer_validation': {...},
#     'overall_passed': True,
#     'errors': []
# }
```

---

## 📊 Интерпретация результатов

### Успешная валидация

```json
{
  "passed": true,
  "errors": [],
  "checks": {
    "sql_valid": true,
    "has_where": true,
    "has_join": true
  }
}
```

### Проваленная валидация

```json
{
  "passed": false,
  "errors": [
    "Нет keywords: ['Ревизор']",
    "Отсутствует JOIN"
  ],
  "checks": {
    "sql_valid": true,
    "has_where": true,
    "has_join": false,
    "has_keywords": false
  }
}
```

---

## 🧪 Запуск тестов валидатора

```bash
# Запустить все тесты
py -m pytest tests/test_cli/test_benchmark_validator.py -v

# Запустить тесты SQL валидатора
py -m pytest tests/test_cli/test_benchmark_validator.py::TestSQLValidator -v

# Запустить тесты Answer валидатора
py -m pytest tests/test_cli/test_benchmark_validator.py::TestAnswerValidator -v

# Запустить интеграционные тесты
py -m pytest tests/test_cli/test_benchmark_validator.py::TestIntegration -v
```

---

## 🚀 Запуск бенчмарка с валидацией

```bash
# Запустить полный бенчмарк
py -m scripts.cli.run_real_agent_benchmark

# Запустить только SQL тесты
py -m scripts.cli.run_real_agent_benchmark --level sql

# Запустить только Final Answer тесты
py -m scripts.cli.run_real_agent_benchmark --level answer

# Запустить первые 5 тестов
py -m scripts.cli.run_real_agent_benchmark --limit 5

# Запустить один конкретный вопрос
py -m scripts.cli.run_real_agent_benchmark -g "Какие книги написал Пушкин?"
```

---

## 📈 Результаты валидации в отчёте

После запуска бенчмарка результаты сохраняются в JSON:

```json
{
  "run_at": "2026-03-25T16:26:51",
  "test_results": [
    {
      "test_id": "sql_гоголь_515",
      "input": "Какие книги написал Николай Гоголь?",
      "success": true,
      "final_answer": "Николай Гоголь написал...",
      "validation": {
        "passed": true,
        "errors": [],
        "checks": {
          "has_keywords": true,
          "is_russian": true,
          "mentions_author": true,
          "length": 95
        }
      }
    }
  ],
  "metrics": {
    "total": 15,
    "successful": 14,
    "failed": 1,
    "success_rate": 93.3
  }
}
```

---

## ⚠️ Ограничения

### Текущие ограничения валидатора

| Компонент | Ограничение | Статус |
|-----------|-------------|--------|
| SQL парсинг | Регулярные выражения (не полноценный парсер) | ⚠️ Работает |
| Галлюцинации | Упрощённая проверка (нет полной сверки с БД) | ⚠️ Частично |
| Вежливость | Простой поиск слов-маркеров | ✅ Работает |
| Язык | Проверка по кириллице (не точная) | ✅ Работает |

### Планы по улучшению

1. **SQL парсинг** — использовать `sqlparse` для точного разбора
2. **Галлюцинации** — полная сверка с результатами из БД
3. **Семантика** — проверка смыслового сходства (embeddings)
4. **Контекст** — учёт контекста диалога при валидации

---

## 📝 Добавление новых правил валидации

### Шаг 1: Добавить правило в бенчмарк

```json
{
  "id": "new_test",
  "validation": {
    "must_have_new_rule": true,
    ...
  }
}
```

### Шаг 2: Реализовать проверку в валидаторе

```python
# В AnswerValidator.validate()
if validation_rules.get('must_have_new_rule', False):
    result = self._check_new_rule(answer, context)
    checks['has_new_rule'] = result
    if not result:
        errors.append('Описание ошибки')
```

### Шаг 3: Добавить тесты

```python
def test_new_rule(self):
    answer = "..."
    rules = {'must_have_new_rule': True}
    result = self.validator.validate(answer, rules)
    assert result['passed'] is True
```

---

## 🎯 Чеклист валидации

Перед запуском бенчмарка проверьте:

- [ ] Все тесты имеют правила валидации (`validation` секция)
- [ ] Правила соответствуют типу теста (SQL/Answer)
- [ ] Ожидаемые результаты указаны (`expected_output`)
- [ ] Тесты покрывают все сценарии использования

После запуска бенчмарка:

- [ ] Success Rate ≥ 75%
- [ ] Нет критических ошибок валидации
- [ ] Все ошибки задокументированы
- [ ] Результаты сохранены в JSON

---

## 🔧 Отладка валидации

### Включить подробный вывод

```python
# В run_real_agent_benchmark.py
validation_result = validator.validate_final_answer(...)

# Подробный вывод
if not validation_result['passed']:
    print(f"❌ Ошибки: {validation_result['errors']}")
    print(f"✅ Чек: {validation_result['checks']}")
```

### Проверка отдельного правила

```python
validator = BenchmarkValidator()

# Проверка одного правила
result = validator.validate_final_answer(
    answer="Тестовый ответ",
    validation_rules={'must_be_in_russian': True}
)

print(result['checks'])  # Детали проверки
```

---

## 📚 Примеры использования

### Пример 1: Валидация простого запроса

```python
validator = BenchmarkValidator()

test = {
    'validation': {
        'must_contain_keywords': ['книга', 'автор'],
        'must_be_in_russian': True
    }
}

response = {'final_answer': 'Это книга автора Пушкина'}

result = validator.validate_test_result(test, response)
assert result['overall_passed'] is True
```

### Пример 2: Валидация сложного SQL

```python
validator = BenchmarkValidator()

sql = """
    SELECT a.name, COUNT(b.id) as book_count
    FROM authors a
    JOIN books b ON a.id = b.author_id
    WHERE b.publication_date > '1850-01-01'
    GROUP BY a.name
    ORDER BY book_count DESC
"""

rules = {
    'must_have_tables': ['authors', 'books'],
    'must_have_join': True,
    'must_have_where': True,
    'must_have_group_by': True,
    'must_have_order_by': True,
    'must_have_count': True
}

result = validator.validate_sql_generation(sql, rules)
assert result['passed'] is True
```

### Пример 3: Валидация edge case

```python
validator = BenchmarkValidator()

test = {
    'validation': {
        'must_indicate_no_results': True,
        'must_be_polite': True
    }
}

response = {
    'final_answer': 'К сожалению, ничего не найдено по вашему запросу'
}

result = validator.validate_test_result(test, response)
assert result['overall_passed'] is True
```

---

## 📞 Поддержка

Вопросы и предложения направляйте в документацию проекта или создайте issue в репозитории.
