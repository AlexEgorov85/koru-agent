# koru-agent — Модульная платформа автономных AI-агентов

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Version](https://img.shields.io/badge/version-5.41.8-orange.svg)]()
[![Coverage](https://img.shields.io/badge/coverage-≥98%25-brightgreen.svg)]()
[![Stability](https://img.shields.io/badge/stability-100%25%20stabilized-brightgreen.svg)]()

---

## 📋 О проекте

**koru-agent** — это модульная платформа для создания автономных AI-агентов с поддержкой reasoning-циклов (ReAct), планирования задач и интеграции с различными LLM-провайдерами.

### Ключевые возможности

- 🔄 **Reasoning-циклы (ReAct)** — агент планирует и выполняет задачи пошагово
- 🧠 **Мульти-LLM поддержка** — vLLM, LlamaCpp, OpenAI, OpenRouter, Anthropic, Gemini
- 💾 **Работа с данными** — PostgreSQL, SQLite, векторные хранилища
- 🔍 **Векторный поиск** — семантический поиск по документам (FAISS)
- 🎯 **Анализ данных** — SQL-запросы, агрегация, проверка результатов
- 📊 **Структурированный вывод** — типизированные ответы с валидацией
- 🔬 **Режим исследования** — автоматическое зондирование данных при пустых результатах
- 🎯 **Автоматическая оценка качества** — бенчмарки и сравнение версий
- 🛡️ **Стабилизация** — детекция зацикливания, Circuit Breaker, валидация decision

---

## 📊 Последние изменения (v5.41.8)

**Версия 5.41.8** (20 апреля 2026) — **Генерация финального ответа при превышении шагов + удаление traceback**

### Генерация финального ответа
- ✅ При достижении лимита шагов — попытка сгенерировать итоговый ответ через final_answer.generate
- ✅ Fallback с информативным сообщением о собранных данных
- ✅ Улучшенная обработка ошибок в runtime

### Очистка кода
- ✅ Удалён import traceback из main.py
- ✅ Исправлен синтаксис в обработке ошибок
- ✅ Улучшено логирование ошибок

📄 **Подробности:** См. [CHANGELOG.md](CHANGELOG.md#5418---2026-04-20)

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
| **Unit** | 446 | ✅ Частично | Чистая логика, изоляция внешних зависимостей |
| **Integration** | - | ❌ Нет | Реальные компоненты |
| **Итого** | **446** | **100% pass** | ✅ Все проходят |

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
| **Тестов** | 446 тестов (100% pass) |
| **Покрытие** | ≥98% |
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

---

## 📄 Лицензия

MIT License — см. файл [LICENSE](LICENSE)

---

## 👥 Авторы

**koru-agent Team** — [GitHub](https://github.com/your-org)
