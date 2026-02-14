# Обновленный анализ Блока 1: Разделение слоёв (Инфраструктура → Приложение → Сессия)

## 1.1 InfrastructureContext содержит ТОЛЬКО тяжёлые ресурсы

**Критерий успеха:** Провайдеры (LLM/DB), хранилища (без кэша), шина событий. Нет `PromptService`/`ContractService` с кэшами

**Обновленный анализ кода:**

После изменений, в файле `core/infrastructure/context/infrastructure_context.py` `InfrastructureContext` теперь содержит только тяжелые ресурсы:

```python
# Основные компоненты инфраструктуры
self.lifecycle_manager: Optional[LifecycleManager] = None
self.event_bus: Optional[EventBus] = None
self.resource_registry: Optional[ResourceRegistry] = None

# Фабрики провайдеров
self.llm_provider_factory: Optional[LLMProviderFactory] = None
self.db_provider_factory: Optional[DBProviderFactory] = None

# Инфраструктурные хранилища (только загрузка, без кэширования)
self.prompt_storage: Optional[PromptStorage] = None
self.contract_storage: Optional[ContractStorage] = None
```

**Изменения:**
- Удалено поле `_services` (сервисы с кэшами)
- Удалено поле `_tools` (инструменты)
- Удалено поле `capability_registry`
- Удалено поле `_providers` (дублирование реестра ресурсов)
- Удалены методы `register_service`, `get_service`, `register_tool`, `get_tool`
- Обновлен метод `get_resource`, чтобы не возвращать сервисы, инструменты и реестр возможностей
- Обновлен метод `get_provider` для использования `resource_registry`
- Обновлен метод `_cleanup_providers` для использования `resource_registry`

**Статус:** ✅ (Теперь InfrastructureContext содержит ТОЛЬКО тяжёлые ресурсы)

---

## 1.2 ApplicationContext создаёт изолированные экземпляры сервисов

**Критерий успеха:** `id(ctx1.prompt_service) != id(ctx2.prompt_service)` для двух контекстов

**Анализ кода:**

В файле `core/application/context/application_context.py` по-прежнему создается изолированные сервисы:

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

**Статус:** ✅ (ApplicationContext создает изолированные экземпляры сервисов)

---

## 1.3 Инструменты (`BaseTool`) stateless

**Критерий успеха:** Нет атрибутов `_cache`, `_state`, `_history` в инструментах

**Анализ кода:**

В файлах `core/application/tools/base_tool.py`, `core/application/tools/file_tool.py` и `core/application/tools/sql_tool.py` инструменты не имеют внутреннего состояния, кэша или истории.

**Статус:** ✅ (SQLTool, FileTool без состояния)

---

## 1.4 Навыки (`BaseSkill`) используют изолированные кэши

**Критерий успеха:** `id(skill1._cached_prompts) != id(skill2._cached_prompts)`

**Анализ кода:**

Каждый навык наследуется от `BaseComponent`, который обеспечивает изолированные кэши для каждого экземпляра.

**Статус:** ✅ (Навыки используют изолированные кэши)

---

## 1.5 Сессионный контекст (`SessionContext`) append-only

**Критерий успеха:** Невозможно изменить историю после добавления шага

**Анализ кода:**

Сессионный контекст реализует append-only семантику.

**Статус:** ✅ (Реализовано корректно)

---

## 1.6 Чёткие границы зависимостей

**Критерий успеха:** Прикладной слой → только чтение из инфраструктуры. Нет `infra.register_resource()` из `app_ctx`

**Анализ кода:**

Прикладной контекст получает ссылку на инфраструктурный контекст только для чтения и использует его только для получения ресурсов.

**Статус:** ✅ (Границы соблюдены)

---

## ИТОГИ

После выполнения изменений:
- ✅ **Пункт 1.1**: `InfrastructureContext` теперь содержит ТОЛЬКО тяжёлые ресурсы (провайдеры, хранилища), без сервисов с кэшами
- ✅ **Пункт 1.2**: `ApplicationContext` создает изолированные экземпляры сервисов с изолированными кэшами
- ✅ **Пункт 1.3**: Инструменты (`BaseTool`) остаются stateless
- ✅ **Пункт 1.4**: Навыки (`BaseSkill`) используют изолированные кэши
- ✅ **Пункт 1.5**: Сессионный контекст (`SessionContext`) остается append-only
- ✅ **Пункт 1.6**: Четкие границы зависимостей соблюдены

Архитектура теперь полностью соответствует принципам разделения слоев.