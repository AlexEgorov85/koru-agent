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

Справочник API всех компонентов системы koru-agent.

---

## 🛠️ Сервисы

### PromptService

**Модуль:** `core.application.services`

**Описание:** Управление промптами

**Методы:**
- `get_prompt(name: str) -> str` — получение промта

### ContractService

**Модуль:** `core.application.services`

**Описание:** Управление контрактами

**Методы:**
- `validate(data: Dict, schema: Dict) -> bool` — валидация данных

### SQLGenerationService

**Модуль:** `core.application.services.sql_generation`

**Описание:** Генерация SQL-запросов

**Методы:**
- `generate_query(natural_language: str, schema: Dict) -> SQLQueryResult`

### SQLQueryService

**Модуль:** `core.application.services.sql_query`

**Описание:** Выполнение SQL-запросов

**Методы:**
- `execute(query: str, params: Dict) -> List[Dict]`

### SQLValidatorService

**Модуль:** `core.application.services.sql_validator`

**Описание:** Валидация SQL

**Методы:**
- `validate(query: str, schema: Dict) -> ValidationResult`

---

## 🎯 Навыки

### PlanningSkill

**Модуль:** `core.application.skills.planning`

**Описание:** Создание планов

**Методы:**
- `create_plan(goal: str, context: Dict) -> Plan`

### BookLibrarySkill

**Модуль:** `core.application.skills.book_library`

**Описание:** Работа с библиотекой книг

**Методы:**
- `search_books(query: str) -> List[Book]`

### FinalAnswerSkill

**Модуль:** `core.application.skills.final_answer`

**Описание:** Формирование финального ответа

**Методы:**
- `generate(context: Dict) -> str`

### DataAnalysisSkill

**Модуль:** `core.application.skills.data_analysis`

**Описание:** Анализ данных

**Методы:**
- `analyze_step_data(step_context: Dict) -> AnalysisResult`

---

## 🔧 Инструменты

### FileTool

**Модуль:** `core.application.tools`

**Описание:** Файловые операции

**Методы:**
- `read_file(path: str) -> str`
- `write_file(path: str, content: str) -> None`

### SQLTool

**Модуль:** `core.application.tools`

**Описание:** SQL-запросы

**Методы:**
- `execute(query: str, params: Dict) -> List[Dict]`

---

## 🧠 Паттерны поведения

### ReActPattern

**Модуль:** `core.application.behaviors.react`

**Описание:** ReAct-цикл: think → act → observe

**Методы:**
- `think(context: Dict) -> Thought`
- `act(thought: Thought) -> Action`
- `observe(action: Action) -> Observation`

### PlanningPattern

**Модуль:** `core.application.behaviors.planning`

**Описание:** Планирование задач

**Методы:**
- `decompose(goal: str) -> List[SubGoal]`

### EvaluationPattern

**Модуль:** `core.application.behaviors.evaluation`

**Описание:** Оценка результатов

**Методы:**
- `evaluate(result: Dict, criteria: Dict) -> EvaluationResult`

### FallbackPattern

**Модуль:** `core.application.behaviors.fallback`

**Описание:** Резервное поведение

**Методы:**
- `execute(error: Exception) -> FallbackResult`

---

## 🔗 Ссылки

- [Руководство по компонентам](./COMPONENTS_GUIDE.md)
- [Исходный код](../core/)

---

*Документ автоматически сгенерирован. Не редактируйте вручную.*
