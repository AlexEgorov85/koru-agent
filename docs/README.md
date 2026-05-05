# 📚 Документация koru-agent

> **Версия проекта:** 5.46.3
> **Дата обновления:** 2026-05-05
> **Статус:** approved

---

## 🔍 О документации

Эта документация описывает архитектуру, компоненты и использование платформы автономных AI-агентов koru-agent.

---

## 📁 Структура документации

```
docs/
├── README.md                          # Этот файл
├── RULES.MD                           # Требования к разработке (полные)
├── AGENTS.md                          # Краткое руководство для coding agents
│
├── architecture/                      # Архитектурные документы
│   ├── README.md                      # Навигация по архитектуре
│   ├── ideal.md                       # Целевая архитектура
│   ├── checklist.md                   # Чек-лист зрелости
│   ├── lifecycle.md                   # Жизненный цикл компонентов
│   ├── AGENT_DOCUMENTATION.md         # Документация компонентов агента
│   └── KORU_AGENT_PRESENTATION.md    # Презентация проекта
│
├── adr/                               # Архитектурные решения (ADR)
│   ├── 0001-modular-architecture.md   # Модульная архитектура
│   └── template.md                    # Шаблон ADR
│
├── guides/                            # Практические руководства
│   ├── README.md                      # Обзор руководств
│   ├── skill_development.md           # 🆕 Разработка навыков (Skill)
│   ├── async_best_practices.md       # Async паттерны
│   ├── agent_resilience.md           # Устойчивость агента
│   └── vector_search.md               # Vector Search (кратко)
│
├── vector_search/                     # Vector Search документация
│   ├── README.md                      # Навигация по Vector Search
│   ├── UNIVERSAL_SPEC.md              # Спецификация
│   ├── VECTOR_LIFECYCLE.md            # Жизненный цикл
│   ├── CHUNKING_STRATEGY.md           # Chunking стратегия
│   ├── BOOKS_INTEGRATION.md           # Интеграция с книгами
│   ├── ADDING_NEW_VECTOR_DB.md        # Добавление новой БД
│   ├── VECTOR_FAISS_CONFIG.md         # Настройка FAISS индексов
│   └── VECTOR_SOURCE_CONFIG.md        # Настройка источников
│
├── logging/                           # Документация логирования
│   └── README.md                      # Система логирования
│
├── api/                               # API документация
│   └── vector_search_api.md           # Vector Search API
│
└── fixes/                             # Исправления и хотфиксы
    └── json_comma_fix.md               # Исправление JSON запятых
```

---

## 🚀 Быстрый старт

### 1. Установка

```bash
git clone <repository_url>
cd koru-agent
python -m venv venv
source venv/bin/activate  # Или venv\Scripts\activate на Windows
pip install -r requirements.txt
```

### 2. Конфигурация

Отредактируйте `core/config/defaults/dev.yaml` (или `prod.yaml`) под ваше окружение.

### 3. Запуск

```bash
python main.py "Какие книги написал Пушкин?"
```

### 4. Тесты

```bash
python -m pytest tests/ -v
```

---

## 📖 Для кого эта документация

### Разработчики

- [AGENTS.md](../AGENTS.md) — краткое руководство (README)
- [RULES.MD](./RULES.MD) — полные требования к разработке
- [guides/skill_development.md](./guides/skill_development.md) — 🆕 разработка навыков
- [architecture/lifecycle.md](./architecture/lifecycle.md) — жизненный цикл компонентов
- [guides/async_best_practices.md](./guides/async_best_practices.md) — async паттерны
- [logging/README.md](./logging/README.md) — система логирования

### Архитекторы

- [architecture/README.md](./architecture/README.md) — навигация по архитектуре
- [architecture/ideal.md](./architecture/ideal.md) — целевая архитектура
- [architecture/checklist.md](./architecture/checklist.md) — проверка зрелости
- [adr/](./adr/) — архитектурные решения

---

## 🔗 Дополнительные ресурсы

### Код

- [Исходный код](../core/)
- [Тесты](../tests/)
- [CHANGELOG](../CHANGELOG.md)

### Внешние ссылки

- [Python Documentation](https://docs.python.org/3/)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [Mermaid Diagrams](https://mermaid.js.org/)

---

## 🤝 Вклад в документацию

### Как помочь

1. Найдите опечатку или неточность
2. Откройте Issue на GitHub
3. Или создайте Pull Request с исправлениями

### Стиль документации

- Используйте чёткий и лаконичный язык
- Добавляйте примеры кода
- Обновляйте версию и дату при изменениях
- Проверяйте ссылки и диаграммы

---

*Документ обновлён: 2026-05-04*
