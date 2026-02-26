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
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List
from core.session_context.base_session_context import BaseSessionContext
from core.session_context.model import ContextItemType
from core.models.data.capability import Capability
from core.models.data.execution import ExecutionResult
from core.config.app_config import AppConfig
from core.config.component_config import ComponentConfig
from core.components.base_component import BaseComponent
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.application.context.application_context import ApplicationContext

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

    def __init__(self, name: str, application_context: 'ApplicationContext', app_config: Optional['AppConfig'] = None, component_config: Optional['ComponentConfig'] = None, executor=None, **kwargs):
        # Проверяем, какой тип конфигурации передан
        # Если передан component_config, используем его
        # Если нет, используем app_config для обратной совместимости
        config_to_use = component_config if component_config is not None else app_config
        # Вызов конструктора родительского класса
        super().__init__(name, application_context, component_config=config_to_use, executor=executor)
        self.config = kwargs
        self.executor = executor  # Сохраняем executor как атрибут
    
    # --------------------------------------------------
    # Initialization API
    # --------------------------------------------------
    async def initialize(self) -> bool:
        """
        Инициализация с единовременной загрузкой ВСЕХ ресурсов из локальной конфигурации.
        После завершения метода компонент НЕ должен обращаться к внешним сервисам.
        """
        # Вызов родительского метода инициализации
        success = await super().initialize()

        if success:
            self._is_initialized = True
            if hasattr(self.application_context, 'logger'):
                self.application_context.logger.info(
                    f"Навык '{self.name}' инициализирован с вариантом '{getattr(self.component_config, 'variant_key', 'default')}'. "
                    f"Загружено: промпты={len(self.prompts)}, "
                    f"input-контракты={len(self.input_contracts)}, "
                    f"output-контракты={len(self.output_contracts)}"
                )
            else:
                import logging
                logging.getLogger(__name__).info(
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
        
        Используется ExecutionGateway для маршрутизации запросов.
        
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

    def _get_event_type_for_success(self) -> 'EventType':
        """Возвращает тип события для успешного выполнения навыка."""
        from core.infrastructure.event_bus.event_bus import EventType
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
        - Вызывается ExecutionGateway после валидации параметров
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
    ) -> Dict[str, Any]:
        """
        Реализация бизнес-логики навыка.

        Переопределяется в наследниках для конкретной реализации.
        По умолчанию вызывает run() для обратной совместимости.

        ПАРАМЕТРЫ:
        - capability: capability для выполнения
        - parameters: параметры выполнения
        - execution_context: контекст выполнения

        ВОЗВРАЩАЕТ:
        - Результат выполнения в виде словаря
        """
        # Для обратной совместимости вызываем run()
        session_context = execution_context.session_context if execution_context else None
        return await self.run(parameters, session_context)

    def get_metadata(self):
        """
        Возвращает метаданные навыка.

        ВОЗВРАЩАЕТ:
        - Объект с метаданными навыка
        """
        # Возвращаем объект с базовыми метаданными
        class Metadata:
            def __init__(self, schema):
                self.input_schema = schema

        # Получаем схему параметров из первой capability или используем схему по умолчанию
        capabilities = self.get_capabilities()
        if capabilities:
            # В новой архитектуре схема параметров берется из контрактов
            try:
                schema = self.get_input_contract(capabilities[0].name)
            except (RuntimeError, KeyError):
                # Если контракт не загружен в кэш, используем пустую схему
                schema = {"type": "object", "properties": {}}
        else:
            schema = {"type": "object", "properties": {}}

        return Metadata(schema)

    async def run(
        self,
        action_payload: Dict[str, Any],
        session: BaseSessionContext
    ) -> Dict[str, Any]:
        """
        Метод для совместимости с предыдущими версиями.
        Выполняет действие с помощью execute метода.

        ПАРАМЕТРЫ:
        - action_payload: Параметры действия
        - session: Контекст сессии

        ВОЗВРАЩАЕТ:
        - Результат выполнения в виде словаря
        """
        # Создаем фиктивную capability для совместимости
        # В новой архитектуре все должно происходить через execute с конкретной capability
        # Этот метод предоставлен для обратной совместимости
        capabilities = self.get_capabilities()
        capability = capabilities[0] if capabilities else Capability(
            name=f"{self.name}.default",
            description="Default capability for backward compatibility",
            skill_name=self.name
        )

        result = await self.execute(
            capability=capability,
            parameters=action_payload,
            context=session
        )

        # Возвращаем content из ExecutionResult или сам результат
        if hasattr(result, 'content') and result.content:
            return result.content
        else:
            return {"result": "executed", "status": "success"}

    async def restart(self) -> bool:
        """
        Перезапуск навыка без полной перезагрузки системного контекста.

        ВОЗВРАЩАЕТ:
        - bool: True если перезапуск прошел успешно, иначе False
        """
        try:
            # Сначала выполним остановку текущего состояния
            await self.shutdown()

            # Затем заново инициализируем навык
            if hasattr(self, 'initialize') and callable(getattr(self, 'initialize')):
                return await self.initialize()
            else:
                # Если метод initialize не определен, просто возвращаем True
                return True
        except Exception as e:
            if hasattr(self.application_context, 'logger'):
                self.application_context.logger.error(f"Ошибка перезапуска навыка {self.name}: {str(e)}")
            else:
                import logging
                logging.getLogger(__name__).error(f"Ошибка перезапуска навыка {self.name}: {str(e)}")
            return False

    def restart_with_module_reload(self):
        """
        Перезапуск навыка с перезагрузкой модуля Python.
        ВНИМАНИЕ: Использовать с осторожностью!

        ВОЗВРАЩАЕТ:
        - Новый экземпляр навыка из перезагруженного модуля
        """
        from core.utils.module_reloader import safe_reload_component_with_module_reload
        if hasattr(self.application_context, 'logger'):
            self.application_context.logger.warning(f"Выполняется перезапуск с перезагрузкой модуля для навыка {self.name}")
        else:
            import logging
            logging.getLogger(__name__).warning(f"Выполняется перезапуск с перезагрузкой модуля для навыка {self.name}")
        return safe_reload_component_with_module_reload(self)

    async def shutdown(self):
        """
        Очистка ресурсов навыка перед остановкой или перезапуском.
        Может быть переопределен в дочерних классах.
        """
        # По умолчанию ничего не делаем, но метод может быть переопределен
        pass