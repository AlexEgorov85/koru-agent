# Миграция на ApplicationContext с изолированными кэшами

## Обзор изменений

В рамках миграции на новую архитектуру были обновлены компоненты системы для поддержки изолированных кэшей и разделения на InfrastructureContext и ApplicationContext.

## FileTool

### Архитектурные изменения

1. **Наследование от нового BaseTool**:
   - FileTool теперь наследуется от `core.application.tools.base_tool.BaseTool`
   - Использует архитектуру с изолированными кэшами
   - Все зависимости запрашиваются из инфраструктуры при выполнении

2. **Поддержка изолированных кэшей**:
   - Каждый экземпляр FileTool имеет свои изолированные кэши
   - Кэши предзагружаются через ComponentConfig
   - После инициализации компонент не обращается к внешним хранилищам

3. **Sandbox режим**:
   - Поддержка флага `side_effects_enabled` в ComponentConfig
   - Операции записи (write, delete и др.) блокируются при `side_effects_enabled=False`
   - Возвращаются объекты с флагом `dry_run=True` для безопасного выполнения

4. **Безопасность файловых операций**:
   - Проверка, что запрашиваемый путь находится внутри разрешенной директории
   - Использование `data_dir` из инфраструктурной конфигурации
   - Защита от выхода за пределы разрешенной директории

### Ключевые методы

- `execute(input_data: FileToolInput) -> FileToolOutput`: выполнение файловой операции
- `_is_write_operation(operation: str) -> bool`: проверка, является ли операция write-операцией
- Поддержка операций: read, write, delete, list

### Использование

```python
from core.application.tools.file_tool import FileToolInput

# Подготовка входных данных
input_data = FileToolInput(
    operation="read", 
    path="/path/to/file.txt"
)

# Выполнение инструмента
result = await file_tool.execute(input_data)

# Результат
if result.success:
    print(result.data["content"])
else:
    print(f"Ошибка: {result.error}")
```

## Тестирование

### Тесты изоляции

Созданы тесты для проверки изоляции FileTool между контекстами:

- `tests/application/test_filetool_isolation.py` - базовая проверка
- `tests/application/test_filetool_advanced_isolation.py` - расширенная проверка

### Проверки

- [x] Создание FileTool с изолированными кэшами
- [x] Работа sandbox режима
- [x] Безопасность операций с файловой системой
- [x] Изоляция между контекстами
- [x] Проверка write-операций в sandbox режиме

## Совместимость

- [x] Обратная совместимость с существующими интерфейсами
- [x] Поддержка ComponentConfig
- [x] Интеграция с ApplicationContext
- [x] Регистрация в инфраструктурном контексте