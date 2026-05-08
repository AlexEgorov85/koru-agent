# koru-agent — Модульная платформа автономных AI-агентов

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Version](https://img.shields.io/badge/version-5.46.7-orange.svg)]()
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

## 📊 Последние изменения (v5.46.7)

**Версия 5.46.7** (8 мая 2026) — **Структурированный вывод в MapReduce, исправление контрактов**

### Исправлено в 5.46.7:
- ✅ Структурированный вывод (`llm.generate_structured`) для `_analyze_chunk` в MapReduceStrategy
- ✅ Валидация наличия выходного контракта перед LLM-вызовом в MapReduce
- ✅ Обработка Pydantic-моделей и dict в `result.data` для MapReduce
- ✅ `execution_error` возвращает `""` вместо `None` для соответствия контракту
- ✅ 5 новых unit-тестов для structured output

### Исправлено в 5.46.6:
- ✅ Runtime ACT block fix
- ✅ Pydantic contract validation fixes

### Исправлено в 5.46.4:
- ✅ Исправлена валидация входных/выходных данных в `component.py` (корректная работа с `pydantic_schema`)
- ✅ Сохранение полных данных в ContextItem (убрано обрезание в `_prepare_observation_content`)
- ✅ Перевод текстов наблюдений и логов на русский язык
- ✅ Исправление регистра и опечаток в `ParamValidator` (fuzzy matching)
- ✅ Исправление таймаутов в `final_answer/skill.py` (безопасная работа с конфигом)
- ✅ Обработка `next_action` перед остановкой в `ReActPattern`

📄 **Подробности:** См. [CHANGELOG.md](CHANGELOG.md#5467---2026-05-08)

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

Система строится на трёх независимых жизненных циклах:

| Слой | Конфигурация | Источник | Жизненный цикл | Ответственность |
|------|--------------|----------|----------------|-----------------|
| **Инфраструктурный** | `InfraConfig` | `core/config/defaults/{profile}.yaml` | 1 раз на приложение | Тяжёлые ресурсы (модели, пулы), пути к данным |
| **Прикладной** | `AppConfig` | Auto-discovery из `data/prompts/`, `data/contracts/` | 1 раз на агента | Версионируемое поведение (промпты, контракты), профиль |
| **Сессионный** | `AgentConfig` | Параметры запроса | 1 раз на запрос | Контекст выполнения (goal, correlation_id, max_steps) |

### Контексты

**InfrastructureContext** — общий для всех агентов:
- LLMProvider, DBProvider (общие провайдеры)
- PromptStorage, ContractStorage (хранилища)
- LoggingSession (логирование)

**ApplicationContext** — изолированный на агента:
- PromptService, ContractService (изолированные кэши)
- ComponentRegistry (навыки, инструменты, сервисы)
- ActionExecutor (единая точка взаимодействия)

**SessionContext** — изолированный на сессию:
- AgentRuntime (reasoning-цикл)
- Шаги, наблюдения, планы

---

## 📁 Структура проекта

```
Agent_v5/
├── core/
│   ├── components/                 # Базовые компоненты (BaseComponent, Skill, Tool)
│   │   ├── skills/                # Навыки (Skills)
│   │   ├── tools/                 # Инструменты (Tools)
│   │   └── services/              # Сервисы (Services)
│   ├── agent/                      # Agent Runtime, Factory, Phases, Behaviors
│   ├── config/                     # Конфигурация (InfraConfig, AppConfig)
│   │   └── defaults/              # Инфраструктурные профили (dev.yaml, prod.yaml)
│   ├── infrastructure/             # Провайдеры (LLM, DB), EventBus, logging, storage
│   ├── models/                     # Модели данных (Capability, ExecutionResult)
│   ├── session_context/            # SessionContext (сессия агента)
│   ├── application_context/        # ApplicationContext (изолированный на агента)
│   ├── infrastructure_context/     # InfrastructureContext (общий)
│   ├── errors/                     # Исключения и ErrorHandler
│   └── security/                  # Безопасность
│
├── data/                           # Единый источник истины для ресурсов
│   ├── prompts/                    # Промпты (auto-discovery)
│   │   └── {type}/{component}/
│   └── contracts/                 # Контракты (auto-discovery)
│       └── {type}/{component}/
│
├── scripts/                        # CLI утилиты, валидация, обслуживание
├── tests/                          # Тесты (unit/, integration/, benchmark/)
└── docs/                           # Документация
    ├── RULES.MD                    # Требования к разработке
    ├── guides/                     # Практические руководства
    │   └── skill_development.md    # Руководство по разработке навыков
    └── architecture/               # Архитектурные документы
```

---

## 🧪 Тестирование

### Статистика

| Категория | Тестов | Моки | Описание |
|-----------|--------|------|----------|
| **Unit** | 446+ | ✅ Mock LLM | Чистая логика, изоляция внешних зависимостей |
| **Integration** | 50+ | ✅ Mock LLM | Быстрые интеграционные тесты (1000x быстрее реальных) |
| **Benchmark** | 10+ | ✅ Mock LLM | Тесты производительности |
| **Итого** | **500+** | **100% pass** | ✅ Все проходят |

### Mock LLM тестирование

- 🚀 Скорость: тесты выполняются в 1000x быстрее (< 1ms на запрос)
- 💰 Экономия: $0 на тестирование
- ✅ Надёжность: 100% детерминированные результаты
- 📊 Полная история вызовов для отладки

### Запуск

```bash
# Все тесты
python -m pytest tests/ -v

# Unit тесты
python -m pytest tests/unit/ -v

# Integration тесты с Mock LLM (быстро)
python -m pytest tests/integration/ -v

# Benchmark тесты
python -m pytest tests/benchmark/ -v

# С покрытием
python -m pytest tests/ --cov=core --cov-report=html

# С реальной LLM (для финальной валидации)
TEST_LLM_TYPE=real python -m pytest tests/integration/ -v
```

---

## ⚙️ Конфигурация

### Трёхслойная иерархия (без дублирования)

| Слой | Файл / Источник | Что содержит |
|------|------------------|---------------|
| **Infrastructure** | `core/config/defaults/{profile}.yaml` | Тяжёлые ресурсы: `llm_providers`, `db_providers`, `data_dir` |
| **Application** | Auto-discovery: `data/prompts/`, `data/contracts/` | Поведение: версии промптов/контрактов, `profile` |
| **Session** | Код при запуске агента | Параметры запроса: `goal`, `max_steps`, `correlation_id` |

> ⚠️ **Критическое правило:** Никакого дублирования! `llm_providers` только в InfraConfig, `goal`/`max_steps` только в AgentConfig.

### Пример InfraConfig (`core/config/defaults/dev.yaml`)

```yaml
profile: "dev"
log_level: "DEBUG"
data_dir: data/dev

llm_providers:
  default_llm:
    enabled: true
    provider_type: "llama_cpp"
    parameters:
      model_path: "models/qwen3-4b-instruct-f16.gguf"
      n_ctx: 2048

db_providers:
  default_db:
    enabled: true
    provider_type: "postgres"
    parameters:
      host: "localhost"
      port: 5432
```

### Пример AgentConfig (в коде)

```python
from core.config.agent_config import AgentConfig

agent_config = AgentConfig(
    goal="Какие книги написал Пушкин?",
    max_steps=10,
    correlation_id="req_123"
)
```

---

## 📊 Статистика проекта

| Показатель | Значение |
|------------|----------|
| **Версия** | 5.46.7 |
| **Тестов** | 446+ тестов (100% pass) |
| **Покрытие** | ≥98% |
| **Поддержка LLM** | LlamaCpp, vLLM, OpenAI, OpenRouter, Anthropic, Gemini |
| **Vector Search** | FAISS с chunking/embedding |
| **Профили** | dev, sandbox, prod |
| **Архитектура** | 3-слойная (Infra → App → Session) |

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
```

### Быстрый старт

```bash
# Простой вопрос
python main.py "Какие книги написал Пушкин?"

# Анализ данных
python main.py "Проанализируй рынок искусственного интеллекта"

# С отладкой
python main.py "Сравни подходы к ML" --profile=dev --debug
```

### Линтинг и валидация

```bash
# Линтеры
flake8 core/
black core/ --check

# Архитектурные проверки
python scripts/validation/check_skill_architecture.py
python scripts/validation/check_yaml_syntax.py
python scripts/maintenance/check_consistency.py
```

### Вклад в проект

1. Fork репозитория
2. Feature branch (`git checkout -b feature/amazing-feature`)
3. Коммиты (согласно чеклисту в `docs/RULES.MD`)
4. Push (`git push origin feature/amazing-feature`)
5. Pull Request

---

## 📚 Документация
### Основная документация

- **[CHANGELOG.md](CHANGELOG.md)** — История изменений
- **[AGENTS.md](AGENTS.md)** — Краткое руководство (README для coding agents)
- **[docs/RULES.MD](docs/RULES.MD)** — Полные требования к разработке
- **[docs/README.md](docs/README.md)** — Обзор документации
- **[docs/guides/skill_development.md](docs/guides/skill_development.md)** — 🆕 Руководство по разработке навыков

### Практические руководства

- **[docs/guides/skill_development.md](docs/guides/skill_development.md)** — 🆕 Руководство по разработке навыков (Skill)
- **[docs/guides/README.md](docs/guides/README.md)** — Все руководства

### Архитектура

- **[docs/architecture/README.md](docs/architecture/README.md)** — Навигация по архитектуре
- **[docs/architecture/ideal.md](docs/architecture/ideal.md)** — Целевая архитектура
- **[docs/architecture/checklist.md](docs/architecture/checklist.md)** — Чек-лист зрелости
- **[docs/architecture/lifecycle.md](docs/architecture/lifecycle.md)** — Жизненный цикл компонентов

---

## 📄 Лицензия

MIT License — см. файл [LICENSE](LICENSE)

---

### Дополнительно

- **[docs/logging/README.md](docs/logging/README.md)** — Система логирования
- **[docs/api/vector_search_api.md](docs/api/vector_search_api.md)** — Vector Search API
- **[docs/fixes/json_comma_fix.md](docs/fixes/json_comma_fix.md)** — Исправление ошибок

---

## 👥 Авторы

**Egorov A.V.** — [GitHub](https://github.com/AlexEgorov85)
