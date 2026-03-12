"""
Базовый класс навыка (Skill) с поддержкой архитектуры портов и адаптеров.

ОСНОВНЫЕ ИЗМЕНЕНИЯ:
1. Наследование от BaseComponent для единого интерфейса инициализации
2. Полная инверсия зависимостей через порты
3. Устранение дублирования метода run()
4. Использование портов вместо прямых зависимостей
5. Четкое разделение ответственности
6. Кэширование промптов и контрактов при инициализации
7. Поддержка локальных конфигураций компонентов с разделением input/output контрактов
8. Возврат ExecutionResult для единого формата результатов
9. Наследование LifecycleMixin для управления состояниями (CREATED → INITIALIZING → READY → SHUTDOWN)
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, TYPE_CHECKING

from core.infrastructure.event_bus.unified_event_bus import EventType
from core.session_context.base_session_context import BaseSessionContext
from core.models.data.capability import Capability
from core.models.data.execution import ExecutionResult
from core.config.component_config import ComponentConfig
from core.components.base_component import BaseComponent

if TYPE_CHECKING:
    from core.application.context.application_context import ApplicationContext
    from core.application.agent.components.action_executor import ActionExecutor, ExecutionContext

class BaseSkill(BaseComponent):
    """
    Базовый класс для всех навыков агента с поддержкой архитектуры портов.

    Архитектурная роль:
    - Skill = "как думать и что делать"
    - Capability = "что именно можно сделать"
    - Порты = "как взаимодействовать с внешним миром"

    Один Skill может иметь несколько Capability.
    """
    #: Человекочитаемое имя навыка
    name: str = "base_skill"

    def __init__(
        self,
        name: str,
        application_context: 'ApplicationContext',
        component_config: ComponentConfig,
        executor: 'ActionExecutor'
    ):
        """
        Инициализация навыка с внедрением зависимостей.

        ПАРАМЕТРЫ:
        - name: имя навыка
        - application_context: контекст приложения (DEPRECATED, используется для совместимости)
        - component_config: конфигурация компонента с версиями ресурсов
        - executor: ActionExecutor для взаимодействия с другими компонентами
        """
        super().__init__(name, application_context, component_config=component_config, executor=executor)
    
    # --------------------------------------------------
    # Initialization API
    # --------------------------------------------------
    async def initialize(self) -> bool:
        """
        Инициализация с единовременной загрузкой ВСЕХ ресурсов из локальной конфигурации.
        После завершения метода компонент НЕ должен обращаться к внешним сервисам.
        
        ЖИЗНЕННЫЙ ЦИКЛ:
        - Вызывает super().initialize() который управляет состояниями
        - При успехе: READY
        - При ошибке: FAILED
        """
        # Вызов родительского метода инициализации (управляет состояниями)
        success = await super().initialize()

        if success:
            if hasattr(self.application_context, 'logger'):
                self.application_context.logger.info(
                    f"Навык '{self.name}' инициализирован с вариантом '{getattr(self.component_config, 'variant_key', 'default')}'. "
                    f"Загружено: промпты={len(self.prompts)}, "
                    f"input-контракты={len(self.input_contracts)}, "
                    f"output-контракты={len(self.output_contracts)}"
                )
            else:
                self._safe_log_sync("info",
                    f"Навык '{self.name}' инициализирован с вариантом '{getattr(self.component_config, 'variant_key', 'default')}'. "
                    f"Загружено: промпты={len(self.prompts)}, "
                    f"input-контракты={len(self.input_contracts)}, "
                    f"output-контракты={len(self.output_contracts)}"
                )

        return success

    # Метод _preload_contracts больше не нужен, так как предзагрузка
    # происходит автоматически в BaseComponent.initialize()
    # через ComponentConfig

    def is_preloaded(self) -> bool:
        """Проверка, были ли все ресурсы предзагружены"""
        return self._is_initialized

    # Методы initialize_with_config, _load_skill_prompts_from_system_config, _load_skill_contracts_from_system_config
    # и _load_contracts больше не используются, так как инициализация теперь происходит через BaseComponent
    # и компоненты используют ComponentConfig

    # Методы get_prompt, get_input_contract, get_output_contract и get_contract
    # наследуются из BaseComponent и обеспечивают доступ к изолированным кэшам
    # компонента, предварительно загруженным при инициализации через ComponentConfig

    def get_capability_names(self) -> list[str]:
        """Возвращает список capability, поддерживаемых навыком"""
        capabilities = self.get_capabilities()
        return [cap.name for cap in capabilities]

    def get_required_capabilities(self) -> List[Dict[str, Any]]:
        """
        Возвращает список необходимых capability с их ресурсами для загрузки.

        ВОЗВРАЩАЕТ:
        - List[Dict]: Список словарей с информацией о необходимых ресурсах для каждой capability
          Каждый словарь содержит:
          - 'name': имя capability
          - 'prompt_versions': словарь {capability_name: version} для промтов
          - 'input_contract_versions': словарь {capability_name: version} для входных контрактов
          - 'output_contract_versions': словарь {capability_name: version} для выходных контрактов
        """
        capabilities = self.get_capabilities()
        required_resources = []

        for cap in capabilities:
            # Для каждой capability определяем необходимые ресурсы
            required_resources.append({
                'name': cap.name,
                'prompt_versions': {cap.name: 'v1.0.0'},  # По умолчанию используем v1.0.0
                'input_contract_versions': {cap.name: 'v1.0.0'},
                'output_contract_versions': {cap.name: 'v1.0.0'}
            })

        return required_resources

    def _get_component_type(self) -> str:
        """Возвращает тип компонента для манифеста."""
        return "skill"
    
    async def _validate_loaded_resources(self) -> bool:
        """Расширенная валидация для навыков."""
        # Вызываем базовую валидацию
        if not await super()._validate_loaded_resources():
            return False

        # ← НОВОЕ: Валидация capability навыков
        if hasattr(self, 'capabilities'):
            for cap in self.capabilities:
                cap_name = f"{self.name}.{cap.name}"

                # Проверка наличия промпта для capability
                if cap_name not in self.prompts:
                    self.logger.warning(
                        f"{self.name}: Capability '{cap.name}' не имеет промпта"
                    )

                # Проверка наличия контрактов для capability
                if cap_name not in self.input_contracts:
                    self.logger.warning(
                        f"{self.name}: Capability '{cap.name}' не имеет input контракта"
                    )

                if cap_name not in self.output_contracts:
                    self.logger.warning(
                        f"{self.name}: Capability '{cap.name}' не имеет output контракта"
                    )

        return True
    
    def get_required_capabilities_from_manifest(self) -> List[str]:
        """Возвращает список required capabilities из манифеста."""
        if self.component_config and self.component_config.constraints:
            return self.component_config.constraints.get('required_capabilities', [])
        return []


    # --------------------------------------------------
    # Capability API
    # --------------------------------------------------
    @abstractmethod
    def get_capabilities(self) -> List[Capability]:
        """
        Возвращает список возможностей, которые предоставляет навык.
        
        Пример:
        PlanningSkill:
            - planning.create_plan
            - planning.update_plan
        
        ВАЖНО:
        - Метод должен быть реализован в дочерних классах
        - Возвращаемые capability должны быть валидными для системы
        - Имена capability должны быть уникальными в рамках системы
        """
        raise NotImplementedError
    
    def get_capability_by_name(self, capability_name: str) -> Capability:
        """
        Поиск capability по имени.

        ПАРАМЕТРЫ:
        - capability_name: Имя capability для поиска

        ВОЗВРАЩАЕТ:
        - Capability объект если найден

        ИСКЛЮЧЕНИЯ:
        - ValueError если capability не найдена

        ОСОБЕННОСТИ:
        - Регистронезависимый поиск
        - Быстрый поиск через итерацию списка
        """
        for cap in self.get_capabilities():
            if cap.name.lower() == capability_name.lower():
                return cap
        raise ValueError(f"Capability '{capability_name}' не найдена в skill '{self.name}'")
    
    # --------------------------------------------------
    # Execution API
    # --------------------------------------------------

    def _get_event_type_for_success(self) -> EventType:
        """Возвращает тип события для успешного выполнения навыка."""
        from core.infrastructure.event_bus.unified_event_bus import EventType
        return EventType.SKILL_EXECUTED

    async def execute(
        self,
        capability: Capability,
        parameters: Dict[str, Any],
        context: BaseSessionContext = None,
        execution_context: 'ExecutionContext' = None,
    ) -> ExecutionResult:
        """
        Выполнение конкретной capability навыка.

        ПАРАМЕТРЫ:
        - capability: выбранная возможность для выполнения
        - parameters: параметры от LLM или runtime
        - context: порт для работы с контекстом сессии (устаревший параметр)
        - execution_context: контекст выполнения (новый параметр)

        ВОЗВРАЩАЕТ:
        - Результат выполнения capability

        ИСПОЛЬЗОВАНИЕ:
        - Вызывается ActionExecutor через executor.execute_capability()
        - Результат будет сохранен в контексте как observation_item

        ПРИМЕР:
        result = await skill.execute(
            capability=create_plan_cap,
            parameters={"goal": "Найти информацию"},
            context=session_context
        )
        """
        # Адаптация старого интерфейса к новому
        if context is not None and execution_context is None:
            # Создаём ExecutionContext из BaseSessionContext
            from core.application.agent.components.action_executor import ExecutionContext
            execution_context = ExecutionContext(
                session_context=context,
                available_capabilities=self.get_capability_names()
            )
        
        # Используем универсальный шаблон выполнения из BaseComponent
        return await super().execute(capability, parameters, execution_context)

    async def _execute_impl(
        self,
        capability: Capability,
        parameters: Dict[str, Any],
        execution_context: 'ExecutionContext'
    ) -> Any:
        """
        Реализация бизнес-логики навыка (ASYNC).

        Переопределяется в наследниках для конкретной реализации.
        Возвращает Dict или Pydantic модель (выходной контракт).

        ПАРАМЕТРЫ:
        - capability: capability для выполнения
        - parameters: параметры выполнения (после валидации)
        - execution_context: контекст выполнения

        ВОЗВРАЩАЕТ:
        - Результат выполнения (Dict или Pydantic модель)

        ПРИМЕЧАНИЕ:
        - Этот метод вызывается из BaseComponent.execute()
        - Для вызова других компонентов используйте executor.execute_action()
        """
        # Базовая реализация возвращает пустой результат
        # Наследники должны переопределять этот метод
        return {}

    async def restart(self) -> bool:
        """
        Перезапуск навыка без полной перезагрузки системного контекста.
        Делегирует реализацию в BaseComponent.

        ВОЗВРАЩАЕТ:
        - bool: True если перезапуск прошел успешно, иначе False
        """
        return await super().restart()

    async def shutdown(self):
        """
        Очистка ресурсов навыка перед остановкой или перезапуском.
        Может быть переопределен в дочерних классах.
        """
        # По умолчанию ничего не делаем, но метод может быть переопределен
        pass