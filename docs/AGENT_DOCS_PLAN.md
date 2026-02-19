# 📋 План документации проекта koru-agent

> **Версия:** 1.0.0
> **Дата обновления:** 2026-02-17
> **Статус:** approved
> **Владелец:** @system

---

## 📁 Структура документации

```
docs/
├── README.md                          # Индекс документации
├── ARCHITECTURE_OVERVIEW.md           # Обзор архитектуры
├── COMPONENTS_GUIDE.md                # Руководство по компонентам
├── CONFIGURATION_MANUAL.md            # Руководство по конфигурации
├── DEPLOYMENT_GUIDE.md                # Руководство по развёртыванию
├── API_REFERENCE.md                   # Справочник API
├── TROUBLESHOOTING.md                 # Устранение неполадок
│
├── architecture/                      # Архитектурные документы
├── components/                        # Документация компонентов
└── guides/                            # Руководства
```

---

## 🎯 Цели документации

1. **Обучение**: Новые разработчики начинают работу за 1 день
2. **Справочник**: Быстрый поиск API и конфигурации
3. **Архитектура**: Понимание принципов и границ системы
4. **Операции**: Развёртывание, мониторинг, устранение неполадок

---

## 📝 Приоритеты

### Фаза 1: Критическая (неделя 1) ✅

- [x] `docs/README.md` — индекс и навигация
- [x] `docs/ARCHITECTURE_OVERVIEW.md` — обзор архитектуры
- [x] `docs/COMPONENTS_GUIDE.md` — руководство по компонентам
- [x] `docs/CONFIGURATION_MANUAL.md` — руководство по конфигурации
- [x] `docs/DEPLOYMENT_GUIDE.md` — руководство по развёртыванию
- [x] `docs/TROUBLESHOOTING.md` — устранение неполадок
- [x] `docs/API_REFERENCE.md` — справочник API

### Фаза 2: Детализация (неделя 2)

- [ ] `docs/architecture/layers.md` — слоёная архитектура
- [ ] `docs/architecture/data-flow.md` — поток данных
- [ ] `docs/components/infrastructure/context.md` — InfrastructureContext
- [ ] `docs/components/application/context.md` — ApplicationContext
- [ ] `docs/components/agent/runtime.md` — AgentRuntime

### Фаза 3: Руководства (неделя 3)

- [ ] `docs/guides/quick-start.md` — быстрый старт
- [ ] `docs/guides/development.md` — разработка
- [ ] `docs/guides/testing.md` — тестирование

---

## 🔧 Автоматизация

### Генерация

```bash
python scripts/generate_docs.py --output docs/
```

### Валидация

```bash
python scripts/validate_docs.py
```

---

## ✅ Чек-лист качества

- [x] Все основные документы созданы
- [ ] Документы-заглушки для будущих разделов
- [ ] Примеры кода протестированы
- [ ] API-сигнатуры синхронизированы с кодом
- [ ] Ссылки между документами работают

---

*Документ автоматически поддерживается в актуальном состоянии*
