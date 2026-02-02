# Инвентаризация данных для архитектурного рефакторинга

## Описание
Документ содержит результаты инвентаризации передачи данных между модулями системы. Цель - выявить места, где используются неявные контракты данных (например, `dict` вместо моделей), которые могут привести к ошибкам несоответствия типов.

## Найденные источники ошибок

### 1. Ошибка "sequence item 0: expected str instance, dict found"

**Место ошибки:** `models/code_unit.py`, строка 296, метод `get_signature()`

**Анализ:** Ошибка происходит в строке:
```python
bases_str = f"({', '.join(bases)})" if bases else ""
```
где `bases` - это список, содержащий не строки, а словари, а функция `join()` ожидает строки.

**Источник проблемного кода:**
```python
# В методе get_signature() класса CodeUnit
bases = self.metadata.get('bases', [])
base_names = []

for base in bases:
    # Обработка разных форматов базовых классов
    if isinstance(base, str):
        base_names.append(base)
    elif isinstance(base, dict):
        # Извлекаем имя из словаря (поддержка разных форматов)
        base_name = (
            base.get("name") or 
            base.get("value") or 
            base.get("full_name") or 
            str(base.get("node", ""))
        )
        if base_name and base_name != "None":
            base_names.append(base_name)
    elif hasattr(base, 'name'):
        base_names.append(str(getattr(base, 'name', base)))
    else:
        # Фолбэк: преобразуем в строку и очищаем от лишнего
        base_str = str(base).strip()
        if base_str and base_str != "None":
            base_names.append(base_str)

# Формирование строки базовых классов
bases_str = f"({', '.join(base_names)})" if base_names else ""
self._cached_signature = f"class {self.name}{bases_str}:"
```

### 2. Источники данных, возвращающие словари вместо строк

**Источник → Приёмник → Фактический тип → Использование**

1. **AST-парсер** → **CodeUnit.metadata.bases** → `list[dict]` → Используется в `get_signature()` для формирования подписи класса

2. **ProjectMapSkill** → **ProjectStructure.code_units** → `dict[str, CodeUnit]` → Используется в ProjectNavigatorSkill для навигации

3. **ProjectNavigatorSkill** → **NavigationResult** → `dict` (через `model_dump()`) → Возвращается в контекст сессии

4. **ProjectNavigatorSkill** → **SearchResult** → `dict` (через `model_dump()`) → Возвращается в контекст сессии

5. **ProjectMapSkill** → **ExecutionResult.result** → `ProjectStructure` → Сохраняется в контексте сессии

6. **CodeUnit.to_dict()** → **ExecutionResult.result** → `dict` → Передается в LLM и другие компоненты

## Проблемные участки кода

### ProjectNavigatorSkill
- В методе `_find_code_unit_in_file()` происходит поиск CodeUnit в файле
- В методе `_build_navigation_result()` происходит вызов `target_unit.get_signature()`, что может вызвать ошибку при наличии словарей в базовых классах
- В методе `_get_project_map()` извлекается ProjectMap из контекста как словарь, а затем преобразуется обратно в объект

### ProjectMapSkill
- В методе `_analyze_file()` возвращаются объекты CodeUnit, полученные из AST-сервиса
- В методе `_analyze_project()` происходит кэширование и возврат ProjectStructure
- В методе `_get_file_code_units()` возвращаются CodeUnit, возможно с неправильно обработанными метаданными

## Рекомендации для рефакторинга

1. **Обеспечить явную типизацию** в `CodeUnit.get_signature()` для обработки метаданных базовых классов
2. **Добавить валидацию** типов при создании CodeUnit из внешних источников (AST-сервисов)
3. **Создать модели Pydantic** для явного определения структуры метаданных, особенно для поля `bases`
4. **Обеспечить согласованность** формата данных между различными слоями (инструменты, сервисы, навыки, модели)
5. **Ввести слой адаптации** для преобразования данных от внешних источников (AST-парсеров) к внутреннему формату

## Вывод

Основная проблема заключается в том, что данные от внешних источников (AST-парсеров) поступают в формате `dict`, который затем используется в `CodeUnit.metadata.bases`. Метод `get_signature()` ожидает, что базовые классы будут представлены в виде строк, но получает словари, что приводит к ошибке времени выполнения.

Решение требует введения явных моделей для представления метаданных и обеспечения корректного преобразования данных на границах системы.