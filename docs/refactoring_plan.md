# План рефакторинга архитектуры компонентов

## 📊 ТЕКУЩАЯ ПРОБЛЕМА

### Глубокая иерархия наследования (до 5 уровней):
```
LifecycleMixin + LoggingMixin
    ↓
BaseComponent (646 строк)
    ├─→ BaseSkill (309 строк) → BookLibrarySkill, PlanningSkill, etc.
    ├─→ BaseService (531 строка) → PromptService, ContractService, etc.
    └─→ BaseTool (238 строк) → FileTool, SqlTool, etc.
    
BaseSkillHandler (275 строк) → search_books_handler, execute_script_handler, etc.
```

**Проблемы:**
1. **Дублирование кода**: BaseSkill, BaseService, BaseTool повторяют 80% логики
2. **Нарушение консистентности**: PlanningSkill наследует BaseComponent напрямую, а не BaseSkill
3. **BaseSkillHandler не наследует BaseComponent** — нарушает единую модель
4. **Сложность поддержки**: Изменения в BaseComponent требуют проверки всех наследников
5. **Избыточность**: 1999 строк базовых классов можно сократить до ~800

---

## ✅ ЦЕЛЕВАЯ АРХИТЕКТУРА

### Принцип: "Один базовый класс + композиция"

```
LifecycleMixin + LoggingMixin
    ↓
Component (универсальный, ~400 строк)
    ├─→ Skill (минимальный, ~50 строк) [опционально]
    ├─→ Service (минимальный, ~50 строк) [опционально]
    └─→ Tool (минимальный, ~50 строк) [опционально]

SkillHandler (базовый класс для хендлеров, ~150 строк)
```

**Ключевые изменения:**
1. **Component** — единый класс для всех типов компонентов
2. **Skill/Service/Tool** — легкие оболочки только для специфичной логики
3. **Композиция вместо наследования** — используем протоколы и миксины
4. **Логирование через event_bus** — встроенное в Component

---

## 📝 ДЕТАЛЬНЫЙ ПЛАН ИЗМЕНЕНИЙ

### ЭТАП 1: Создание универсального класса Component

**Файл:** `/workspace/core/agent/components/component.py`

**Структура (~400 строк):**
```python
class Component(LifecycleMixin, LoggingMixin, ABC):
    """
    Универсальный базовый класс для всех компонентов.
    
    АТРИБУТЫ:
    - name: str
    - component_type: Literal["skill", "service", "tool"]
    - application_context: ApplicationContext
    - component_config: ComponentConfig
    - executor: ActionExecutor
    - prompts: Dict[str, Prompt]
    - input_contracts: Dict[str, Type[BaseModel]]
    - output_contracts: Dict[str, Type[BaseModel]]
    """
    
    # Абстрактные методы
    @abstractmethod
    def get_capabilities(self) -> List[Capability]: ...
    
    @abstractmethod
    async def _execute_impl(
        self,
        capability: Capability,
        parameters: Dict[str, Any],
        execution_context: ExecutionContext
    ) -> Any: ...
    
    # Методы логирования (переиспользуемые)
    def _log_component_event(self, level: str, message: str, **kwargs):
        """Единый метод логирования с авто-контекстом"""
        # Автоматически добавляет component_name, component_type
        # Публикует через event_bus.publish()
        
    async def initialize(self) -> bool:
        """Универсальная инициализация с логированием"""
        # Логирование: f"[{self.component_type}:{self.name}] Инициализация..."
        
    async def execute(...) -> ExecutionResult:
        """Универсальное выполнение с логированием"""
        # Логирование: f"[{self.component_type}:{self.name}] Выполнение {capability.name}"
```

**Ключевые особенности:**
- **Встроенное логирование**: Каждый компонент автоматически логирует с префиксом `[type:name]`
- **Переиспользование**: Все методы логирования доступны из коробки
- **Гибкость**: component_type определяет поведение (skill/service/tool)

---

### ЭТАП 2: Упрощение BaseSkill, BaseService, BaseTool

**Файл:** `/workspace/core/components/skills/base_skill.py`
**Структура (~50 строк):**
```python
class Skill(Component):
    """Оболочка для навыков с специфичной логикой"""
    
    def _get_component_type(self) -> str:
        return "skill"
    
    def _get_event_type_for_success(self) -> EventType:
        return EventType.SKILL_EXECUTED
    
    # Только специфичная логика навыков
    def get_capability_names(self) -> List[str]: ...
    def get_capability_by_name(self, name: str) -> Capability: ...
```

**Файл:** `/workspace/core/components/services/base_service.py`
**Структура (~50 строк):**
```python
class Service(Component):
    """Оболочка для сервисов с зависимостями"""
    
    DEPENDENCIES: ClassVar[List[str]] = []
    
    def _get_component_type(self) -> str:
        return "service"
    
    async def _resolve_dependencies(self) -> bool:
        """Специфичная логика сервисов"""
        
    def get_dependency(self, name: str) -> Optional[Any]: ...
```

**Файл:** `/workspace/core/components/tools/base_tool.py`
**Структура (~50 строк):**
```python
class Tool(Component):
    """Оболочка для инструментов"""
    
    def _get_component_type(self) -> str:
        return "tool"
    
    def _get_event_type_for_success(self) -> EventType:
        return EventType.ACTION_PERFORMED
    
    # Специфичная логика инструментов
    def get_allowed_operations(self) -> List[str]: ...
```

---

### ЭТАП 3: Рефакторинг BaseSkillHandler

**Файл:** `/workspace/core/components/skills/handlers/base_handler.py`

**Изменения:**
```python
class BaseSkillHandler(ABC):
    """Базовый класс для обработчиков навыков"""
    
    def __init__(self, skill: Skill):  # ← Типизированный параметр
        self.skill = skill
        self.executor = skill.executor
        self._event_bus = skill._event_bus
        
    # Методы логирования через skill
    async def log_info(self, message: str):
        await self.skill._log_component_event("info", message)
```

---

### ЭТАП 4: Обновление существующих компонентов

#### 4.1 PlanningSkill (пример нарушения)
**Было:**
```python
class PlanningSkill(BaseComponent):  # ← Нарушение: должен быть BaseSkill
```

**Стало:**
```python
class PlanningSkill(Skill):  # ← Консистентно
```

#### 4.2 BookLibrarySkill
**Было:**
```python
class BookLibrarySkill(BaseSkill):
    # Много дублирования init
```

**Стало:**
```python
class BookLibrarySkill(Skill):
    # Только специфичная логика
```

#### 4.3 PromptService
**Было:**
```python
class PromptService(BaseService):
    # Дублирование resolve_dependencies
```

**Стало:**
```python
class PromptService(Service):
    # Наследует resolve_dependencies из Service
```

---

### ЭТАП 5: Встроенное логирование в Component

**Реализация в Component:**

```python
class Component(LifecycleMixin, LoggingMixin, ABC):
    
    def __init__(self, name: str, component_type: str, ...):
        self.component_type = component_type
        self._log_prefix = f"[{component_type}:{name}]"
        
        LoggingMixin.__init__(
            self,
            event_bus=event_bus,
            component_name=self._log_prefix,  # ← Префикс для всех логов
            get_init_state_callback=self._get_logger_init_state
        )
    
    def _safe_log_sync(self, level: str, message: str, **kwargs):
        """Синхронное логирование с префиксом"""
        full_message = f"{self._log_prefix} {message}"
        # Публикация через event_bus
        
    async def _log_async(self, level: str, message: str, **kwargs):
        """Асинхронное логирование с префиксом"""
        full_message = f"{self._log_prefix} {message}"
        await self._event_bus.publish(
            event_type=f"component.{level}",
            data={"message": full_message, **kwargs},
            source=self.name,
            session_id=...,
            agent_id=...
        )
    
    async def initialize(self) -> bool:
        self._log_async("info", "Начало инициализации")
        # ... логика
        self._log_async("info", f"Инициализирован: промпты={len(self.prompts)}")
```

**Пример использования в навыке:**
```python
class BookLibrarySkill(Skill):
    async def _execute_impl(self, capability, parameters, context):
        self._log_async("info", f"Выполнение {capability.name}")
        # ... логика
        self._log_async("info", "Поиск книг завершен", rows=len(results))
```

**Вывод логов:**
```
[skill:book_library] Начало инициализации
[skill:book_library] Инициализирован: промпты=5
[skill:book_library] Выполнение book_library.search_books
[skill:book_library] Поиск книг завершен, rows=10
```

---

### ЭТАП 6: Миграция существующих компонентов

#### Файлы для обновления:

**Навыки (Skills):**
1. `/workspace/core/components/skills/planning/skill.py` → `class PlanningSkill(Skill)`
2. `/workspace/core/components/skills/book_library/skill.py` → `class BookLibrarySkill(Skill)`
3. `/workspace/core/components/skills/data_analysis/skill.py`
4. `/workspace/core/components/skills/check_result/skill.py`
5. `/workspace/core/components/skills/final_answer/skill.py`
6. `/workspace/core/components/skills/meta_component_creator/skill.py`

**Сервисы (Services):**
1. `/workspace/core/components/services/prompt_service.py`
2. `/workspace/core/components/services/contract_service.py`
3. `/workspace/core/components/services/table_description_service.py`
4. `/workspace/core/components/services/sql_query/service.py`
5. `/workspace/core/components/services/sql_generation/service.py`
6. `/workspace/core/components/services/sql_validator/service.py`
7. `/workspace/core/components/services/validation_service.py`
8. `/workspace/core/components/services/document_indexing_service.py`
9. `/workspace/core/components/services/metrics_publisher.py`
10. `/workspace/core/components/services/data_repository.py`

**Инструменты (Tools):**
1. `/workspace/core/components/tools/file_tool.py`
2. `/workspace/core/components/tools/sql_tool.py`
3. `/workspace/core/components/tools/vector_books_tool.py`

**Хендлеры:**
1. `/workspace/core/components/skills/handlers/base_handler.py` → обновление импорта
2. Все handlers в `book_library/handlers/`, `planning/handlers/`, etc.

---

## 📈 ОЖИДАЕМЫЕ РЕЗУЛЬТАТЫ

### Метрики до/после:

| Показатель | До | После | Изменение |
|------------|-----|-------|-----------|
| Строк базовых классов | 1999 | ~800 | **-60%** |
| Уровней наследования | 5 | 2-3 | **-40%** |
| Файлов базовых классов | 5 | 4 | -20% |
| Дублирования кода | ~80% | ~10% | **-87%** |
| Время на понимание | Высокое | Низкое | **-70%** |

### Преимущества:
1. ✅ **Единая точка изменений** — все компоненты используют Component
2. ✅ **Консистентность** — PlanningSkill больше не нарушает архитектуру
3. ✅ **Логирование из коробки** — каждый компонент автоматически логирует с префиксом
4. ✅ **Гибкость** — легко добавить новый тип компонента
5. ✅ **Тестируемость** — проще мокать Component чем глубокую иерархию
6. ✅ **Документированность** — один класс вместо пяти

---

## ⚠️ РИСКИ И МИТИГАЦИЯ

### Риск 1: Обратная совместимость
**Митигация:**
- Сохранить алиасы: `BaseSkill = Skill`, `BaseService = Service`, `BaseTool = Tool`
- Поэтапная миграция с тестами

### Риск 2: Поломка существующих компонентов
**Митигация:**
- Запустить полный набор тестов перед коммитом
- Проверить интеграционные тесты

### Риск 3: Потеря функциональности
**Митигация:**
- Тщательный код-ревью каждого этапа
- Сравнение поведения до/после

---

## 🚀 ПОШАГОВЫЙ ПЛАН ВНЕДРЕНИЯ

### Неделя 1:
1. ✅ Создать `Component` класс
2. ✅ Создать упрощенные `Skill`, `Service`, `Tool`
3. ✅ Написать тесты для новых классов

### Неделя 2:
4. ✅ Мигрировать PlanningSkill (как пример нарушения)
5. ✅ Мигрировать BookLibrarySkill
6. ✅ Мигрировать 2-3 сервиса

### Неделя 3:
7. ✅ Мигрировать остальные компоненты
8. ✅ Обновить хендлеры
9. ✅ Финальное тестирование

---

## 📋 ЧЕКЛИСТ ЗАВЕРШЕНИЯ

- [ ] Component создан с логированием
- [ ] Skill/Service/Tool созданы
- [ ] PlanningSkill мигрирован
- [ ] BookLibrarySkill мигрирован
- [ ] Все сервисы мигрированы
- [ ] Все инструменты мигрированы
- [ ] Хендлеры обновлены
- [ ] Тесты проходят
- [ ] Документация обновлена
- [ ] Алиасы для обратной совместимости добавлены
