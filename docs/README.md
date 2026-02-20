# 📚 Документация koru-agent

> **Версия:** 5.4.0
> **Дата обновления:** 2026-02-20
> **Статус:** approved

---

## 🔍 О документации

Эта документация описывает архитектуру, компоненты и использование платформы автономных AI-агентов koru-agent.

### Быстрые ссылки

| Документ | Описание |
|----------|----------|
| [🏗️ Обзор архитектуры](./ARCHITECTURE_OVERVIEW.md) | Общее описание архитектуры системы |
| [🧩 Руководство по компонентам](./COMPONENTS_GUIDE.md) | Создание и использование компонентов |
| [⚙️ Руководство по конфигурации](./CONFIGURATION_MANUAL.md) | Настройка и конфигурирование |
| [🚀 Руководство по развёртыванию](./DEPLOYMENT_GUIDE.md) | Установка и развёртывание |
| [🐛 Устранение неполадок](./TROUBLESHOOTING.md) | Диагностика и решение проблем |
| [📖 CHANGELOG](../CHANGELOG.md) | История изменений |

---

## 📁 Структура документации

### Основные документы

```
docs/
├── README.md                          # Этот файл
├── ARCHITECTURE_OVERVIEW.md           # Обзор архитектуры
├── COMPONENTS_GUIDE.md                # Руководство по компонентам
├── CONFIGURATION_MANUAL.md            # Руководство по конфигурации
├── DEPLOYMENT_GUIDE.md                # Руководство по развёртыванию
├── API_REFERENCE.md                   # Справочник API
├── TROUBLESHOOTING.md                 # Устранение неполадок
│
├── architecture/                      # Архитектурные документы
│   ├── README.md                      # Обзор
│   ├── checklist.md                   # Чек-лист архитектуры
│   └── ideal.md                       # Идеальная архитектура
│
├── components/                        # Документация компонентов
│   ├── README.md                      # Обзор компонентов
│   ├── infrastructure/
│   │   └── context.md                 # InfrastructureContext
│   └── application/
│       └── context.md                 # ApplicationContext
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
├── plans/                             # Планы разработки
│   └── BENCHMARK_LEARNING_PLAN.md     # Benchmark + Learning
│
└── adr/                               # Архитектурные решения
    ├── 0001-modular-architecture.md   # Модульная архитектура
    └── 0002-contract-validation.md    # Валидация контрактов
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

```bash
cp .env.example .env
# Отредактируйте .env под ваше окружение
```

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

- [Руководство по компонентам](./COMPONENTS_GUIDE.md) — создание новых компонентов
- [Руководство по разработке](./guides/development.md) — лучшие практики
- [API Reference](./API_REFERENCE.md) — справочник API

### DevOps инженеры

- [Руководство по развёртыванию](./DEPLOYMENT_GUIDE.md) — установка и настройка
- [Мониторинг](./DEPLOYMENT_GUIDE.md#мониторинг) — метрики и логи
- [Устранение неполадок](./TROUBLESHOOTING.md) — диагностика проблем

### Архитекторы

- [Обзор архитектуры](./ARCHITECTURE_OVERVIEW.md) — общее описание
- [Слои системы](./architecture/layers.md) — детальная архитектура
- [Модель безопасности](./architecture/security-model.md) — безопасность

---

## 🔗 Дополнительные ресурсы

### Код

- [Исходный код](https://github.com/your-org/koru-agent)
- [Примеры](../examples/)
- [Тесты](../tests/)

### Отчёты

- [Архитектурный отчёт](../ARCHITECTURE_COMPLIANCE_REPORT_*.md)
- [План документации](./AGENT_DOCS_PLAN.md)

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

## 📊 Статус документации

| Раздел | Статус | Последнее обновление |
|--------|--------|---------------------|
| Обзор архитектуры | ✅ Готово | 2026-02-17 |
| Руководство по компонентам | ✅ Готово | 2026-02-17 |
| Руководство по конфигурации | ✅ Готово | 2026-02-17 |
| Руководство по развёртыванию | ✅ Готово | 2026-02-17 |
| Устранение неполадок | ✅ Готово | 2026-02-17 |
| API Reference | 🚧 В работе | — |
| Архитектурные документы | 🚧 В работе | — |
| Документация компонентов | 🚧 В работе | — |
| Руководства | 🚧 В работе | — |

**Легенда**: ✅ Готово | 🚧 В работе | 📋 Запланировано

---

*Документ автоматически поддерживается в актуальном состоянии*
