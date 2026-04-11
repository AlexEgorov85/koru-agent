# 📚 Документация koru-agent

> **Версия:** 5.35.0
> **Дата обновления:** 2026-03-15
> **Статус:** approved

---

## 🔍 О документации

Эта документация описывает архитектуру, компоненты и использование платформы автономных AI-агентов koru-agent.

---

## 📁 Структура документации

```
docs/
├── README.md                          # Этот файл
├── RULES.MD                           # Требования к разработке
│
├── architecture/                      # Архитектурные документы
│   ├── ideal.md                       # Целевая архитектура
│   ├── checklist.md                   # Чек-лист зрелости
│   └── lifecycle.md                   # Жизненный цикл компонентов
│
├── adr/                               # Архитектурные решения
│   ├── 0001-modular-architecture.md   # Модульная архитектура
│   ├── 0002-contract-validation.md    # Валидация контрактов
│   └── template.md                    # Шаблон ADR
│
├── guides/                            # Руководства
│   ├── README.md                      # Обзор руководств
│   ├── book_library.md                # Book Library
│   └── vector_search.md               # Vector Search
│
├── vector_search/                     # Vector Search документация
│   ├── README.md                      # Навигация
│   ├── UNIVERSAL_SPEC.md              # Спецификация
│   ├── VECTOR_LIFECYCLE.md            # Жизненный цикл
│   ├── CHUNKING_STRATEGY.md           # Chunking стратегия
│   └── BOOKS_INTEGRATION.md           # Интеграция с книгами
│
├── logging/                           # Документация логирования
│   ├── README.md                      # Обзор системы логирования
│   └── ARCHITECTURE.md                # Архитектура логирования
│
└── api/                               # API документация
    └── vector_search_api.md           # Vector Search API
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
python main.py "Проанализируй рынок искусственного интеллекта"
```

### 4. Тесты

```bash
python -m pytest tests/ -v
```

---

## 📖 Для кого эта документация

### Разработчики

- [RULES.MD](./RULES.MD) — требования к разработке
- [architecture/lifecycle.md](./architecture/lifecycle.md) — жизненный цикл компонентов
- [guides/async_best_practices.md](./guides/async_best_practices.md) — async паттерны
- [logging/README.md](./logging/README.md) — система логирования

### Архитекторы

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

*Документ обновлён: 2026-03-15*
