# {{TITLE}}

> **Версия:** {{VERSION}}  
> **Дата обновления:** {{DATE}}  
> **Статус:** {{STATUS: draft|review|approved}}  
> **Владелец:** {{OWNER}}

---

## 📋 Оглавление
- [Обзор](#-обзор)
- [Архитектура](#-архитектура)
- [Конфигурация](#-конфигурация)
- [Использование](#-использование)
- [API](#-api)
- [Примеры](#-примеры)
- [Устранение неполадок](#-устранение-неполадок)

---

## 🔍 Обзор

{{Краткое описание компонента/модуля}}

### Назначение
{{Для чего предназначен компонент}}

### Ключевые возможности
- ✅ {{Возможность 1}}
- ✅ {{Возможность 2}}
- ✅ {{Возможность 3}}

### Место в архитектуре
{{Описание места компонента в общей архитектуре системы}}

---

## 🏗️ Архитектура

### Диаграмма компонентов
```mermaid
graph TD
    A[{{Component A}}] --> B[{{Component B}}]
    B --> C[{{Component C}}]
```

### Зависимости
| Зависимость | Тип | Версия | Обязательная |
|-------------|-----|--------|--------------|
| {{dep_name}} | {{runtime/config}} | {{version}} | {{yes/no}} |

### Интерфейсы
```python
class {{ComponentName}}:
    async def {{method_name}}(self, params: Dict) -> Result:
        """{{Docstring}}"""
        pass
```

### Связанные компоненты
- {{Component 1}} — {{описание связи}}
- {{Component 2}} — {{описание связи}}

---

## ⚙️ Конфигурация

### Параметры в `registry.yaml`
```yaml
{{component_name}}:
  enabled: true
  dependencies: []
  parameters:
    {{param1}}: {{value1}}
    {{param2}}: {{value2}}
  prompt_versions:
    {{capability}}: v1.0.0
  input_contract_versions:
    {{capability}}: v1.0.0
  output_contract_versions:
    {{capability}}: v1.0.0
```

### Переменные окружения
| Переменная | Описание | Значение по умолчанию |
|------------|----------|----------------------|
| `{{VAR_NAME}}` | {{description}} | `{{default}}` |

### Профили
| Профиль | Конфигурация |
|---------|--------------|
| `dev` | {{описание}} |
| `prod` | {{описание}} |
| `test` | {{описание}} |

---

## 🚀 Использование

### Базовый пример
```python
from {{module}} import {{Component}}

component = {{Component}}(config)
result = await component.execute(params)
```

### Расширенный пример
```python
# {{Комментарий к примеру}}
{{Код примера}}
```

### Интеграция с другими компонентами
```python
# Пример интеграции с {{Component}}
{{Код интеграции}}
```

---

## 🔌 API Reference

### Класс `{{ComponentName}}`

#### Конструктор
```python
def __init__(
    self,
    config: ComponentConfig,
    application_context: ApplicationContext
) -> None:
```

| Параметр | Тип | Обязательный | Описание |
|----------|-----|--------------|----------|
| `config` | `ComponentConfig` | ✅ | Конфигурация компонента |
| `application_context` | `ApplicationContext` | ✅ | Контекст приложения |

### Методы

#### `{{method_name}}`
```python
async def {{method_name}}(
    self,
    param1: Type1,
    param2: Type2 = None
) -> ReturnType:
```

| Параметр | Тип | Обязательный | Описание |
|----------|-----|--------------|----------|
| `param1` | `Type1` | ✅ | {{description}} |
| `param2` | `Type2` | ❌ | {{description}} |

**Возвращает:** `ReturnType` — {{description}}

**Исключения:**
- `{{ExceptionName}}` — {{when_raised}}

#### `get_prompt(name: str) -> str`
Получение промта из кэша компонента.

#### `get_input_contract(name: str) -> Dict`
Получение схемы входного контракта.

#### `get_output_contract(name: str) -> Dict`
Получение схемы выходного контракта.

---

## 🐛 Устранение неполадок

| Симптом | Возможная причина | Решение |
|---------|------------------|---------|
| {{symptom}} | {{cause}} | {{solution}} |
| Компонент не инициализируется | Отсутствует зависимость | Проверьте `dependencies` в registry.yaml |
| Ошибка валидации контракта | Несоответствие версии | Убедитесь, что версия контракта существует в manifests/ |
| Пустой кэш промптов | Профиль prod для draft версии | Используйте sandbox профиль или активируйте версию |

### Логи для диагностики
```bash
# Включить отладочное логирование
export LOG_LEVEL=DEBUG
python main.py --debug
```

### Частые ошибки

#### Ошибка: `ComponentNotInitializedError`
**Причина:** Попытка использования компонента до инициализации  
**Решение:** Вызовите `await component.initialize()` перед использованием

#### Ошибка: `PromptNotFound`
**Причина:** Промпт не найден в кэше  
**Решение:** Проверьте `prompt_versions` в конфигурации компонента

---

## 📊 Метрики и мониторинг

{{Описание метрик, которые публикует компонент}}

| Метрика | Тип | Описание |
|---------|-----|----------|
| `{{metric_name}}` | counter/gauge | {{description}} |

---

## 🧪 Тестирование

### Юнит-тесты
```python
import pytest
from {{module}} import {{Component}}

@pytest.mark.asyncio
async def test_{{component_name}}():
    config = ComponentConfig(...)
    component = {{Component}}(config)
    await component.initialize()
    
    result = await component.execute({...})
    assert result is not None
```

### Интеграционные тесты
```bash
python -m pytest tests/{{component_path}}/ -v
```

---

## 🔗 Ссылки

### Внутренние
- [Документация смежного компонента](./related.md)
- [Исходный код](../../core/{{path}})
- [Тесты](../../tests/{{path}})
- [Манифест](../../data/manifests/{{path}}/manifest.yaml)

### Внешние
- [Архитектурный отчёт](../ARCHITECTURE_COMPLIANCE_REPORT.md)
- [CHANGELOG](../CHANGELOG.md)

---

*Документ автоматически сгенерирован. Не редактируйте вручную.*
