# koru-agent — Модульная платформа автономных AI-агентов

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Version](https://img.shields.io/badge/version-5.36.4-orange.svg)]()
[![Coverage](https://img.shields.io/badge/coverage-≥98%25-brightgreen.svg)]()
[![Stability](https://img.shields.io/badge/stability-100%25%20stabilized-brightgreen.svg)]()

---

## 📋 О проекте

**koru-agent** — это модульная платформа для создания автономных AI-агентов с поддержкой reasoning-циклов (ReAct), планирования задач и интеграции с различными LLM-провайдерами.

### Ключевые возможности

- 🔄 **Reasoning-циклы (ReAct)** — агент планирует и выполняет задачи пошагово
- 🧠 **Мульти-LLM поддержка** — vLLM, LlamaCpp, OpenAI, Anthropic, Gemini
- 💾 **Работа с данными** — PostgreSQL, SQLite, векторные хранилища
- 🔍 **Векторный поиск** — семантический поиск по документам (FAISS)
- 📚 **Анализ книг** — LLM анализ героев, тем, классификация
- 📊 **Структурированный вывод** — типизированные ответы с валидацией
- 🎯 **Автоматическая оценка качества** — бенчмарки и сравнение версий
- 🚀 **Самооптимизация** — автоматическое улучшение промптов и контрактов
- 🛡️ **Стабилизация** — детекция зацикливания, гарантия вызова LLM, валидация decision

---

## 📊 Последние изменения (v5.36.0)

**Версия 5.36.0** (13 апреля 2026) — **Исправления final_answer и контрактов**

### Исправления final_answer
- ✅ Исправлены критические ошибки промпта и контрактов
- ✅ Исправлено имя переменной в user-промпте: `{observation}` → `{observations}`
- ✅ Добавлены новые переменные: `{steps_taken}`, `{format_type}`, `{include_steps}`, `{include_evidence}`
- ✅ Исправлено извлечение полей из LLM ответа: `answer` → `final_answer`, `confidence` → `confidence_score`
- ✅ Добавлено `additionalProperties: false` в output контракт

### Исправления исключений
- ✅ Убрано дублирование параметра `code` в иерархии исключений
- ✅ Исправлена передача metadata и component в InfrastructureError/VectorSearchError

📄 **Подробности:** См. [CHANGELOG.md](CHANGELOG.md#5360---2026-03-15)

---

## 🚀 Быстрый старт

### Установка

```bash
# Клонирование репозитория
git clone <repository_url>
cd koru-agent

# Установка зависимостей
pip install -r requirements.txt
```

### Первый запуск

```bash
# Простой вопрос
python main.py "Какие книги написал Пушкин?"

# Анализ данных
python main.py "Проанализируй рынок искусственного интеллекта"

# С отладкой
python main.py "Сравни подходы к ML" --profile=dev --debug
```

### Запуск тестов

```bash
# Все тесты
python -m pytest tests/ -v

# Быстрые тесты (без интеграционных)
python -m pytest tests/unit/ -v

# Интеграционные тесты с Mock LLM (быстро)
python -m pytest tests/integration/test_mock_llm_workflow.py -v

# Тестовые сценарии
python -m pytest tests/integration/test_scenarios/ -v

# Benchmark тесты производительности
python -m pytest tests/benchmark/test_mock_llm_performance.py -v

# С реальной LLM (для финальной валидации)
TEST_LLM_TYPE=real python -m pytest tests/integration/ -v
```

**Mock LLM тестирование:**
- 🚀 Скорость: тесты выполняются в 1000x быстрее (< 1ms на запрос)
- 💰 Экономия: $0 на тестирование
- ✅ Надёжность: 100% детерминированные результаты
- 📊 Полная история вызовов для отладки

---

## 🏗️ Архитектура

### Уровни системы

```
┌─────────────────────────────────────────────────────────────┐
│                    Agent Runtime                            │
│  (Reasoning-цикл: think → select → execute → write)        │
├─────────────────────────────────────────────────────────────┤
│                  Application Context                        │
│  (Изолированный на агента: сервисы, навыки, кэши)          │
├─────────────────────────────────────────────────────────────┤
│               Infrastructure Context                        │
│  (Общий: провайдеры, EventBus, метрики, логи)              │
└─────────────────────────────────────────────────────────────┘
```

### Контексты

**InfrastructureContext** — общий для всех агентов:
- ProviderFactory (LLM, DB)
- ResourceRegistry
- EventBus
- MetricsCollector
- LogCollector

**ApplicationContext** — изолированный на агента:
- ComponentRegistry (сервисы, навыки, инструменты)
- Isolated caches (промпты, контракты)
- ComponentConfig

---

## 📁 Структура проекта

```
Agent_v5/
├── core/                           # Ядро системы
│   ├── agent/                      # Runtime, Factory, Behaviors, Strategies
│   ├── application_context/        # ApplicationContext (изолированный на агента)
│   ├── components/                 # BaseComponent, ActionExecutor
│   ├── config/                     # Конфигурация (defaults/)
│   ├── infrastructure/             # Провайдеры, EventBus, logging, storage
│   ├── infrastructure_context/     # InfrastructureContext (общий)
│   ├── models/                     # Модели данных
│   ├── errors/                     # Исключения
│   ├── session_context/            # SessionContext (сессия)
│   └── security/                  # Безопасность
│
├── data/                           # Промпты, контракты
├── scripts/                        # CLI утилиты
├── tests/                          # Тесты
└── docs/                           # Документация
```

---

## 🧪 Тестирование

### Статистика

| Категория | Тестов | Моки | Описание |
|-----------|--------|------|----------|
| **Unit (модели)** | 63 | ❌ Нет | Чистая логика, сериализация |
| **Unit (хранилища)** | 34 | ❌ Нет | Реальная ФС (temp dirs) |
| **Unit (сервисы)** | 141 | ⚠️ LLM/DB | Изоляция внешних зависимостей |
| **Integration** | 21 | ❌ Нет | Реальные компоненты |
| **E2E** | 16 | ⚠️ Частично | Полные циклы |
| **CLI** | 30 | ⚠️ Сервисы | Тесты интерфейса |
| **Итого** | **398** | **31% без моков** | ✅ Все проходят |

### Запуск

```bash
# Все тесты
python -m pytest tests/ -v

# Только без моков
python -m pytest tests/unit/core_models/ tests/unit/storage/ -v

# Интеграционные
python -m pytest tests/integration/ tests/e2e/ -v

# С покрытием
python -m pytest tests/ --cov=core --cov-report=html
```

---

## ⚙️ Конфигурация

### Файлы

| Файл | Назначение |
|------|------------|
| `core/config/defaults/{profile}.yaml` | InfraConfig (провайдеры, пути) |
| `data/prompts/` | Auto-discovery промптов |
| `data/contracts/` | Auto-discovery контрактов |

### Пример

```yaml
profile: "dev"
log_level: "DEBUG"

llm_providers:
  primary_llm:
    enabled: true
    provider_type: "vllm"
    parameters:
      model_path: "models/mistral-7b-instruct.gguf"

agent:
  max_steps: 10
  timeout: 300
```

---

## 📊 Статистика проекта

| Показатель | Значение |
|------------|----------|
| **Тестов** | 545 тестов |
| **Поддержка LLM** | LlamaCpp, vLLM, OpenAI, OpenRouter, Anthropic |
| **Vector Search** | FAISS с chunking/embedding |
| **Профили** | dev, sandbox, prod |

---

## 🔧 Разработка

### Окружение

```bash
# Виртуальное окружение
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# Зависимости
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### Линтинг

```bash
flake8 core/
black core/ --check
```

### Вклад в проект

1. Fork репозитория
2. Feature branch (`git checkout -b feature/amazing-feature`)
3. Коммиты (`git commit -m 'Add amazing feature'`)
4. Push (`git push origin feature/amazing-feature`)
5. Pull Request

---

## 📚 Документация

### Основная документация

- **[CHANGELOG.md](CHANGELOG.md)** — История изменений
- **[AGENTS.md](AGENTS.md)** — Требования к разработке и архитектура
- **[docs/README.md](docs/README.md)** — Обзор документации

### Архитектура

- **[docs/architecture/README.md](docs/architecture/README.md)** — Архитектурные документы
- **[docs/architecture/ideal.md](docs/architecture/ideal.md)** — Целевая архитектура

### Vector Search

- **[docs/vector_search/README.md](docs/vector_search/README.md)** — навигация
- **[docs/api/vector_search_api.md](docs/api/vector_search_api.md)** — API документация

---

## 📄 Лицензия

MIT License — см. файл [LICENSE](LICENSE)

---

## 👥 Авторы

**koru-agent Team** — [GitHub](https://github.com/your-org)
