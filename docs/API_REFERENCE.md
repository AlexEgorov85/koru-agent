# 🔌 API Reference

> **Версия:** 5.1.0  
> **Дата обновления:** 2026-02-17  
> **Статус:** draft  
> **Владелец:** @system

---

## 📋 Оглавление

- [Сервисы](#сервисы)
- [Навыки](#навыки)
- [Инструменты](#инструменты)
- [Паттерны поведения](#паттерны-поведения)

---

## 🔍 Обзор

Этот документ содержит справочник API всех компонентов системы Agent_v5.

---

## 🛠️ Сервисы

### `SQLGenerationServiceOutput`

**Модуль:** `core.application.services.sql_generation.service`

**Описание:** Результат генерации с метаданными для анализа ошибок

**Методы:**

#### `execute`

```python
async def execute(self, input_data: ServiceInput) -> SQLGenerationServiceOutput:
```

#### `restart`

```python
async def restart(self) -> bool:
```

#### `shutdown`

```python
async def shutdown(self) -> None:
```

### `SQLQueryServiceInput`

**Модуль:** `core.application.services.sql_query.service`

**Описание:** Входные данные для SQLQueryService

**Методы:**

#### `execute`

```python
async def execute(self, input_data: SQLQueryServiceInput) -> SQLQueryServiceOutput:
```

#### `restart`

```python
async def restart(self) -> bool:
```

#### `shutdown`

```python
async def shutdown(self) -> None:
```

### `SQLValidatorServiceInput`

**Модуль:** `core.application.services.sql_validator.service`

**Описание:** Входные данные для SQLValidatorService

**Методы:**

#### `execute`

```python
async def execute(self, input_data: SQLValidatorServiceInput) -> SQLValidatorServiceOutput:
```

#### `validate_query`

```python
async def validate_query(self, sql_query: str, parameters: Dict[str, Any] = None) -> ValidatedSQL:
```

#### `restart`

```python
async def restart(self) -> bool:
```

#### `shutdown`

```python
async def shutdown(self) -> None:
```


---

## 🎯 Навыки

### `Booklibraryskill`

**Модуль:** `core.application.skills.book_library.skill`

**Описание:** Навык работы с библиотекой книг.

**Методы:**

#### `initialize`

```python
async def initialize(self) -> bool:
```

### `Dataanalysisskill`

**Модуль:** `core.application.skills.data_analysis.skill`

**Описание:** Навык анализа сырых данных по шагу.

**Методы:**

#### `initialize`

```python
async def initialize(self) -> bool:
```

### `Finalanswerskill`

**Модуль:** `core.application.skills.final_answer.skill`

**Описание:** Навык для генерации финального ответа агента.

**Методы:**

#### `initialize`

```python
async def initialize(self) -> bool:
```

### `Planningskill`

**Модуль:** `core.application.skills.planning.skill`

**Описание:** НАВЫК ПЛАНИРОВАНИЯ С ПОЛНОЙ ИЗОЛЯЦИЕЙ

**Методы:**

#### `shutdown`

```python
async def shutdown(self) -> None:
```


---

## 🔧 Инструменты

### `Toolinput`

**Модуль:** `core.application.tools.base_tool`

**Описание:** Абстрактный класс для входных данных инструмента.

### `Filetoolinput`

**Модуль:** `core.application.tools.file_tool`

**Описание:** Файловый инструмент - операции с файловой системой с поддержкой изолированных кэшей и sandbox режима.

### `Sqltoolinput`

**Модуль:** `core.application.tools.sql_tool`

**Описание:** Инструмент для выполнения SQL-запросов с поддержкой изолированных кэшей и sandbox режима.


---

## 🧠 Паттерны поведения

### `Evaluationpattern`

**Модуль:** `core.application.behaviors.evaluation.pattern`

**Описание:** Паттерн оценки достижения цели.

### `Fallbackpattern`

**Модуль:** `core.application.behaviors.fallback.pattern`

**Описание:** Паттерн интеллектуального восстановления.

### `Planningpattern`

**Модуль:** `core.application.behaviors.planning.pattern`

**Описание:** Паттерн иерархического планирования: создание плана → выполнение шагов → коррекция

### `Reactpattern`

**Модуль:** `core.application.behaviors.react.pattern`

**Описание:** ReActPattern - реактивная стратегия без логики планирования.

