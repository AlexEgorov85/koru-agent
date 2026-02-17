# 📋 План документации проекта Agent_v5

> **Версия:** 1.0.0  
> **Дата обновления:** 2026-02-17  
> **Статус:** approved  
> **Владелец:** @system

---

## 📁 Структура документации

```
docs/
├── README.md                           # Индекс документации
├── ARCHITECTURE_OVERVIEW.md            # Обзор архитектуры
├── COMPONENTS_GUIDE.md                 # Руководство по компонентам
├── CONFIGURATION_MANUAL.md             # Руководство по конфигурации
├── DEPLOYMENT_GUIDE.md                 # Руководство по развёртыванию
├── API_REFERENCE.md                    # Справочник API
├── TROUBLESHOOTING.md                  # Устранение неполадок
├── CHANGELOG.md                        # История изменений (существующий)
│
├── architecture/
│   ├── layers.md                       # Слои системы
│   ├── data-flow.md                    # Поток данных
│   ├── security-model.md               # Модель безопасности
│   └── scalability.md                  # Масштабируемость
│
├── components/
│   ├── infrastructure/
│   │   ├── context.md                  # InfrastructureContext
│   │   ├── providers.md                # Провайдеры (LLM, Database)
│   │   └── storage.md                  # Хранилища
│   ├── application/
│   │   ├── context.md                  # ApplicationContext
│   │   ├── services.md                 # Сервисы
│   │   └── tools.md                    # Инструменты
│   └── agent/
│       ├── runtime.md                  # AgentRuntime
│       ├── behaviors.md                # Паттерны поведения
│       └── skills.md                   # Навыки
│
└── guides/
    ├── quick-start.md                  # Быстрый старт
    ├── development.md                  # Разработка
    ├── testing.md                      # Тестирование
    └── migration.md                    # Миграция (существующий)
```

---

## 🎯 Цели документации

1. **Обучение**: Новые разработчики могут начать работу за 1 день
2. **Справочник**: Быстрый поиск API и конфигурации
3. **Архитектура**: Понимание принципов и границ системы
4. **Операции**: Развёртывание, мониторинг, устранение неполадок

---

## 📝 Приоритеты генерации

### Фаза 1: Критическая документация (неделя 1)
- [ ] `docs/README.md` — индекс и навигация
- [ ] `docs/ARCHITECTURE_OVERVIEW.md` — обзор архитектуры
- [ ] `docs/guides/quick-start.md` — быстрый старт
- [ ] `docs/architecture/layers.md` — слоёная архитектура

### Фаза 2: Компоненты (неделя 2)
- [ ] `docs/components/infrastructure/context.md`
- [ ] `docs/components/application/context.md`
- [ ] `docs/components/agent/runtime.md`
- [ ] `docs/components/agent/behaviors.md`

### Фаза 3: Руководства (неделя 3)
- [ ] `docs/CONFIGURATION_MANUAL.md`
- [ ] `docs/guides/development.md`
- [ ] `docs/guides/testing.md`
- [ ] `docs/TROUBLESHOOTING.md`

### Фаза 4: Справочники (неделя 4)
- [ ] `docs/API_REFERENCE.md`
- [ ] `docs/components/infrastructure/providers.md`
- [ ] `docs/components/application/services.md`
- [ ] `docs/architecture/data-flow.md`

---

## 🔧 Автоматизация

### Скрипт генерации
```bash
python scripts/generate_docs.py --output docs/
```

### Валидация
```bash
python scripts/validate_docs.py
```

### Pre-commit хук
```yaml
# .pre-commit-config.yaml
- repo: local
  hooks:
    - id: check-docs-sync
      name: Проверка синхронизации документации
      entry: python scripts/validate_docs.py
      language: python
      files: ^core/.*\.py$
```

---

## 📊 Источники данных для генерации

### Анализ кода
- `core/**/*.py` — извлечение API сигнатур
- `core/config/**/*.yaml` — параметры конфигурации
- `data/manifests/**/manifest.yaml` — описания компонентов

### Существующая документация
- `ARCHITECTURE_COMPLIANCE_REPORT_*.md` — отчёты о соответствии
- `docs/resource_management.md` — управление ресурсами
- `CHANGELOG.md` — история изменений

### Тесты
- `tests/**/*.py` — примеры использования

---

## ✅ Чек-лист качества документации

- [ ] Все компоненты имеют `.md` файлы в `docs/components/`
- [ ] Диаграммы Mermaid валидны и отображаются
- [ ] Ссылки между документами работают
- [ ] Примеры кода протестированы и актуальны
- [ ] API-сигнатуры синхронизированы с кодом
- [ ] Добавлены метки версий и дат обновления
- [ ] Документация проходит линтинг (markdownlint)
- [ ] Интегрирована в CI/CD для авто-обновления

---

## 🔄 Процесс обновления

1. **При изменении кода**: Автоматическая проверка актуальности документации
2. **Еженедельно**: Генерация отчёта о расхождениях
3. **Перед релизом**: Полная регенерация документации

---

*Документ автоматически поддерживается в актуальном состоянии*
