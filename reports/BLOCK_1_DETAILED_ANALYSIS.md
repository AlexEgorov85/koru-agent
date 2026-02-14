# Подробный анализ Блока 1: Разделение слоёв (Инфраструктура → Приложение → Сессия)

## 1.1 InfrastructureContext содержит ТОЛЬКО тяжёлые ресурсы

**Критерий успеха:** Провайдеры (LLM/DB), хранилища (без кэша), шина событий. Нет `PromptService`/`ContractService` с кэшами

**Анализ кода:**

В файле `core/infrastructure/context/infrastructure_context.py` можно увидеть, что `InfrastructureContext` действительно содержит тяжелые ресурсы:

```python
# Основные компоненты инфраструктуры
self.lifecycle_manager: Optional[LifecycleManager] = None
self.event_bus: Optional[EventBus] = None
self.resource_registry: Optional[ResourceRegistry] = None

# Фабрики провайдеров
self.llm_provider_factory: Optional[LLMProviderFactory] = None
self.db_provider_factory: Optional[DBProviderFactory] = None
# Общая фабрика для инструментов, навыков и сервисов
self.provider_factory: Optional['ProviderFactory'] = None

# Инфраструктурные хранилища (только загрузка, без кэширования)
self.prompt_storage: Optional[PromptStorage] = None
self.contract_storage: Optional[ContractStorage] = None
self.capability_registry: Optional[CapabilityRegistry] = None

# Общие ресурсы (провайдеры)
self._providers: Dict[str, Any] = {}
# Инструменты
self._tools: Dict[str, Any] = {}
# Сервисы
self._services: Dict[str, Any] = {}
```

Однако, в `InfrastructureContext` также регистрируются `PromptService` и `ContractService`:

```python
def register_service(self, name: str, service: Any):
    """Регистрация сервиса."""
    self._services[name] = service
    self.logger.info(f"Сервис '{name}' зарегистрирован")
```

Это нарушает критерий, так как `PromptService` и `ContractService` содержат кэши и должны быть в `ApplicationContext`, а не в `InfrastructureContext`.

**Статус:** ❌ (Сервисы с кэшами регистрируются в инфраструктуре)

---

## 1.2 ApplicationContext создаёт изолированные экземпляры сервисов

**Критерий успеха:** `id(ctx1.prompt_service) != id(ctx2.prompt_service)` для двух контекстов

**Анализ кода:**

В файле `core/application/context/application_context.py` можно увидеть, как создаются изолированные сервисы:

```python
async def _create_isolated_services(self):
    """Создание изолированных сервисов с изолированными кэшами."""
    # ...
    
    # Создание изолированного PromptService (новая архитектура)
    self._prompt_service = PromptService(
        application_context=self,  # ApplicationContext как прикладной контекст
        component_config=component_config
    )
    success = await self._prompt_service.initialize()
    if not success:
        self.logger.error("Ошибка инициализации PromptService")
        raise RuntimeError("Не удалось инициализировать PromptService")

    # Создание изолированного ContractService (новая архитектура)
    self._contract_service = ContractService(
        application_context=self,  # ApplicationContext как прикладной контекст
        component_config=component_config
    )
    success = await self._contract_service.initialize()
    if not success:
        self.logger.error("Ошибка инициализации ContractService")
        raise RuntimeError("Не удалось инициализировать ContractService")
```

В файлах `core/application/services/prompt_service_new.py` и `core/application/services/contract_service_new.py` можно увидеть, что каждый сервис имеет изолированный кэш:

```python
# В PromptService
self._cached_prompts: Dict[str, Dict[str, Any]] = {}  # ← Изолированный кэш!

# В ContractService  
self._cached_contracts: Dict[Tuple[str, str], Dict] = {}  # ← Изолированный кэш!
```

Каждый `ApplicationContext` создает свои собственные экземпляры `PromptService` и `ContractService`, что обеспечивает изоляцию.

**Статус:** ✅ (ApplicationContext создает изолированные экземпляры сервисов)

---

## 1.3 Инструменты (`BaseTool`) stateless

**Критерий успеха:** Нет атрибутов `_cache`, `_state`, `_history` в инструментах

**Анализ кода:**

В файле `core/application/tools/base_tool.py` определен базовый класс инструмента:

```python
class BaseTool(BaseComponent):
    """Базовый класс для инструментов с инверсией зависимостей."""

    def __init__(self, name: str, application_context: ApplicationContext, component_config: Optional[ComponentConfig] = None, **kwargs):
        # Вызов конструктора родительского класса
        super().__init__(name, application_context, component_config)
        self.config = kwargs
```

В файлах `core/application/tools/file_tool.py` и `core/application/tools/sql_tool.py` можно увидеть, что инструменты не имеют атрибутов `_cache`, `_state`, `_history`:

```python
# В FileTool
class FileTool(BaseTool):
    def __init__(self, name: str, application_context: ApplicationContext, component_config: Optional[ComponentConfig] = None, **kwargs):
        super().__init__(name, application_context, component_config, **kwargs)

# В SQLTool
class SQLTool(BaseTool):
    def __init__(self, name: str, application_context: ApplicationContext, component_config: Optional[ComponentConfig] = None, **kwargs):
        super().__init__(name, application_context, component_config, **kwargs)
```

Оба инструмента не имеют внутреннего состояния, кэша или истории.

**Статус:** ✅ (SQLTool, FileTool без состояния)

---

## 1.4 Навыки (`BaseSkill`) используют изолированные кэши

**Критерий успеха:** `id(skill1._cached_prompts) != id(skill2._cached_prompts)`

**Анализ кода:**

В файле `core/application/skills/base_skill.py` можно увидеть, что навыки наследуются от `BaseComponent`, который обеспечивает изолированные кэши:

```python
class BaseSkill(BaseComponent):
    # ...
    def __init__(self, name: str, application_context: 'ApplicationContext', app_config: Optional['AppConfig'] = None, **kwargs):
        # Вызов конструктора родительского класса
        super().__init__(name, application_context, app_config)
        self.config = kwargs
```

Класс `BaseComponent` (наследуемый от `BaseSkill`) обеспечивает изолированные кэши для каждого экземпляра навыка. Каждый навык получает свои собственные кэши при инициализации через `ComponentConfig`.

**Статус:** ✅ (Навыки используют изолированные кэши)

---

## 1.5 Сессионный контекст (`SessionContext`) append-only

**Критерий успеха:** Невозможно изменить историю после добавления шага

**Анализ кода:**

В файле `core/session_context/base_session_context.py` можно увидеть, что сессионный контекст реализует append-only семантику:

```python
class BaseSessionContext(ABC):
    """Абстрактный базовый класс для контекста сессии с append-only семантикой."""
    
    @abstractmethod
    async def add_item(self, item: ContextItem) -> str:
        """Добавляет элемент в контекст. Append-only операция."""
        pass
    
    @abstractmethod
    def get_items(self, item_type: Optional[ContextItemType] = None) -> List[ContextItem]:
        """Получает элементы из контекста (только для чтения)."""
        pass
```

Сессионный контекст позволяет только добавлять элементы, но не изменять или удалять уже добавленные, что обеспечивает append-only семантику.

**Статус:** ✅ (Реализовано корректно)

---

## 1.6 Чёткие границы зависимостей

**Критерий успеха:** Прикладной слой → только чтение из инфраструктуры. Нет `infra.register_resource()` из `app_ctx`

**Анализ кода:**

В файле `core/application/context/application_context.py` можно увидеть, что прикладной контекст получает ссылку на инфраструктурный контекст только для чтения:

```python
def __init__(
    self,
    infrastructure_context: InfrastructureContext,
    config: 'AppConfig',
    profile: Literal["prod", "sandbox"] = "prod"
):
    """
    ПАРАМЕТРЫ:
    - infrastructure_context: Инфраструктурный контекст (только для чтения!)
    """
    self.id = str(uuid.uuid4())
    self.infrastructure_context = infrastructure_context  # Только для чтения!
    # ...
```

Прикладной контекст использует инфраструктурный контекст только для получения ресурсов:

```python
def get_provider(self, name: str):
    """Получение провайдера через инфраструктурный контекст."""
    return self.infrastructure_context.get_provider(name)

def get_tool(self, name: str):
    """Получение инструмента через инфраструктурный контекст."""
    return self.infrastructure_context.get_tool(name)
```

Прикладной контекст не регистрирует ресурсы в инфраструктурном контексте, а только читает из него.

**Статус:** ✅ (Границы соблюдены)