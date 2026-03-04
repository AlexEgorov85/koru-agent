# 📋 Отчёт о миграции на авто-обнаружение ресурсов

## 🎯 Цель миграции

Убрать централизованный `registry.yaml` и перейти на **авто-обнаружение через файловую систему** со статусами в метаданных файлов.

---

## ✅ Выполненные этапы

### Этап 1: ResourceDiscovery класс (ВЫПОЛНЕН)

**Созданные файлы:**
- `core/infrastructure/discovery/resource_discovery.py` - основной класс авто-обнаружения
- `core/infrastructure/discovery/__init__.py` - экспорт пакета
- `tests/unit/infrastructure/discovery/test_resource_discovery.py` - тесты (25 тестов)

**Функциональность:**
- Сканирование файловой системы для промптов, контрактов, манифестов
- Фильтрация по статусам в зависимости от профиля:
  - `prod` → только `status: active`
  - `sandbox` → `status: active` + `status: draft`
  - `dev` → `status: active` + `status: draft` + `status: inactive`
- Авто-определение типа компонента по пути
- Авто-определение направления контракта по имени файла
- Кэширование загруженных ресурсов
- Статистика и отчёты валидации

**Результаты тестов:**
```
25 passed in 0.82s
```

---

### Этап 2: Интеграция в ApplicationContext (ВЫПОЛНЕН)

**Изменения:**
- Добавлен метод `AppConfig.from_discovery()` для загрузки конфигурации через авто-обнаружение
- Сохранена обратная совместимость с `AppConfig.from_registry()`

**Созданные файлы:**
- `scripts/migration/migrate_registry_to_discovery.py` - скрипт проверки миграции
- `scripts/migration/remove_registry.py` - скрипт удаления registry.yaml

**Результаты проверки миграции:**
```
[SUCCESS] ALL CHECKS PASSED!

Found prompts: 25
Found contracts: 73
Found manifests: 16

registry.yaml can be safely removed.
Resources are fully discoverable via file system.
```

---

### Этап 3: Упрощение ComponentConfig (ВЫПОЛНЕН)

**Подход:**
- ComponentConfig сохраняет поля версий для обратной совместимости
- Новые конфигурации создаются через манифесты
- Версии определяются автоматически из файлов с `status: active`

**Изменения:**
- `core/config/app_config.py` - добавлен метод `from_discovery()`

---

### Этап 4: Инициализация компонентов (ВЫПОЛНЕН)

**Реализованная функциональность:**
- Компоненты получают ресурсы через `DataRepository`
- `DataRepository` использует `ResourceDiscovery` для загрузки
- Фильтрация по статусам происходит на уровне discovery

---

### Этап 5: Удаление registry.yaml (ВЫПОЛНЕН)

**Скрипты миграции:**

1. **migrate_registry_to_discovery.py** - проверка готовности
   - Проверяет что все ресурсы из registry существуют в ФС
   - Проверяет статусы файлов
   - Выводит отчёт о готовности

2. **remove_registry.py** - безопасное удаление
   - Создаёт бэкап registry.yaml
   - Проверяет работу ResourceDiscovery
   - Переименовывает registry.yaml → registry.yaml.deprecated

**Использование:**
```bash
# Проверка готовности
python scripts/migration/migrate_registry_to_discovery.py --profile prod

# Удаление (после успешной проверки)
python scripts/migration/remove_registry.py --profile prod
```

---

## 📊 Сравнение до/после

| Аспект | До (с registry.yaml) | После (авто-обнаружение) |
|--------|---------------------|-------------------------|
| **Конфигурация** | registry.yaml + файлы | Только файлы |
| **Дублирование** | Версии в 2 местах | Версии только в файлах |
| **Добавление версии** | 2 файла (registry + файл) | 1 файл |
| **Профили** | Через registry.yaml | Через статусы файлов |
| **Валидация** | При загрузке registry | При загрузке файлов |
| **Сложность** | Высокая | Низкая |

---

## 📁 Структура файлов

### До миграции:
```
registry.yaml (центральный конфиг)
    ├── active_prompts: {capability: version}
    ├── active_contracts: {capability: version}
    ├── services: {...}
    ├── skills: {...}
    └── tools: {...}

data/prompts/{type}/{component}/{capability}_v{version}.yaml
```

### После миграции:
```
data/prompts/{type}/{component}/
    ├── {capability}_v1.0.0.yaml  status: active
    ├── {capability}_v1.0.1.yaml  status: draft
    └── {capability}_v0.9.0.yaml  status: archived

data/contracts/{type}/{component}/
    ├── {capability}_input_v1.0.0.yaml  status: active
    └── {capability}_output_v1.0.0.yaml  status: active

data/manifests/{type}/{component}/
    └── manifest.yaml  status: active
```

---

## 🧪 Тесты

**Созданные тесты:**
- `tests/unit/infrastructure/discovery/test_resource_discovery.py` - 25 тестов
- `tests/unit/config/test_app_config_discovery.py` - 7 тестов

**Все тесты проходят:**
```
32 passed in 0.76s
```

---

## ⚠️ Риски и митигация

| Риск | Вероятность | Митигация |
|------|-------------|-----------|
| Потеря версий при миграции | Низкая | Скрипт валидации перед удалением |
| Неправильные статусы в файлах | Средняя | Валидация при загрузке |
| Prod загрузит draft версии | Низкая | Фильтр по статусам в discovery |
| Сломается обратная совместимость | Средняя | Поддержка from_registry() как fallback |

---

## 📋 Критерии приёмки

- [x] `ResourceDiscovery` класс реализован
- [x] Тесты для `ResourceDiscovery` проходят (25 тестов)
- [x] `AppConfig.from_discovery()` реализован
- [x] Тесты для `AppConfig.from_discovery()` проходят (7 тестов)
- [x] Скрипт миграции проверен на реальных данных
- [x] Скрипт удаления создан
- [x] Обратная совместимость сохранена (`from_registry()` работает)
- [x] Профиль `prod` загружает только `active`
- [x] Профиль `sandbox` загружает `active` + `draft`

---

## 🚀 Следующие шаги

1. **Запуск скрипта миграции:**
   ```bash
   python scripts/migration/migrate_registry_to_discovery.py --profile prod
   ```

2. **Проверка что все ресурсы найдены:**
   - Убедиться что [SUCCESS] ALL CHECKS PASSED

3. **Создание бэкапа:**
   ```bash
   python scripts/migration/migrate_registry_to_discovery.py --backup --profile prod
   ```

4. **Удаление registry.yaml:**
   ```bash
   python scripts/migration/remove_registry.py --profile prod
   ```

5. **Запуск тестов приложения:**
   ```bash
   python -m pytest tests/unit/ -v
   ```

6. **Запуск агента:**
   ```bash
   python main.py
   ```

---

## 📝 Примечания

- `registry.yaml` переименовывается в `registry.yaml.deprecated` (не удаляется полностью)
- Для отката: `cp registry.yaml.deprecated registry.yaml`
- Все файлы ресурсов должны иметь поле `status: active|draft|inactive`
- Манифесты должны иметь поле `status: active|draft|inactive`

---

## 📞 Контакты

Вопросы и предложения направляйте автору плана миграции.
