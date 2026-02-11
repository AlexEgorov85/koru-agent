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
from typing import Dict, Any, List, Optional
from core.session_context.base_session_context import BaseSessionContext
from core.session_context.model import ContextItemType
from core.system_context.base_system_contex import BaseSystemContext
from models.capability import Capability
from models.execution import ExecutionResult
from core.config.agent_config import AgentConfig
from core.config.component_config import ComponentConfig
from core.components.base_component import BaseComponent

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
    #: Список стратегий, поддерживаемых навыком
    supported_strategies: List[str] = ["react"]  # По умолчанию только для ReAct

    def supports_strategy(self, strategy_name: str) -> bool:
        """
        Проверяет, поддерживает ли навык указанную стратегию.

        ПАРАМЕТРЫ:
        - strategy_name: имя стратегии для проверки

        ВОЗВРАЩАЕТ:
        - bool: True если стратегия поддерживается, иначе False
        """
        return strategy_name.lower() in [s.lower() for s in self.supported_strategies]

    def __init__(self, name: str, system_context: BaseSystemContext, component_config: Optional[ComponentConfig] = None, **kwargs):
        # Вызов конструктора родительского класса
        super().__init__(name, system_context, component_config)
        self.config = kwargs
    
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
            if hasattr(self.system_context, 'logger'):
                self.system_context.logger.info(
                    f"Навык '{self.name}' инициализирован с вариантом '{getattr(self.component_config, 'variant_key', 'default')}'. "
                    f"Загружено: промпты={len(self._cached_prompts)}, "
                    f"input-контракты={len(self._cached_input_contracts)}, "
                    f"output-контракты={len(self._cached_output_contracts)}"
                )
            else:
                import logging
                logging.getLogger(__name__).info(
                    f"Навык '{self.name}' инициализирован с вариантом '{getattr(self.component_config, 'variant_key', 'default')}'. "
                    f"Загружено: промпты={len(self._cached_prompts)}, "
                    f"input-контракты={len(self._cached_input_contracts)}, "
                    f"output-контракты={len(self._cached_output_contracts)}"
                )
        
        return success

    async def _preload_contracts(self, agent_config: AgentConfig):
        """Предзагрузка контрактов согласно конфигурации (аналогично промптам)"""
        if not self.contract_service:
            return

        for capability_name in self.get_capability_names():
            try:
                # Загрузка ТОЧНО указанной версии из конфигурации
                version = agent_config.contract_versions.get(capability_name)

                # Загрузка INPUT контракта из кэша
                input_contract = self.contract_service.get_contract_schema_from_cache(
                    capability_name=capability_name,
                    version=version,
                    direction="input"
                )
                
                if input_contract is None:
                    # Если в кэше нет, пробуем получить напрямую (для обратной совместимости)
                    input_contract = await self.contract_service.get_contract_schema(
                        capability_name=capability_name,
                        version=version,
                        direction="input"
                    )

                # Загрузка OUTPUT контракта из кэша
                output_contract = self.contract_service.get_contract_schema_from_cache(
                    capability_name=capability_name,
                    version=version,
                    direction="output"
                )
                
                if output_contract is None:
                    # Если в кэше нет, пробуем получить напрямую (для обратной совместимости)
                    output_contract = await self.contract_service.get_contract_schema(
                        capability_name=capability_name,
                        version=version,
                        direction="output"
                    )

                # Кэшируем контракты — больше обращений к хранилищу не будет
                self._cached_input_contracts[capability_name] = input_contract
                self._cached_output_contracts[capability_name] = output_contract

                if hasattr(self.system_context, 'logger'):
                    self.system_context.logger.debug(
                        f"Навык '{self.name}': загружен input контракт {capability_name} v{version or 'active'}"
                    )
                    self.system_context.logger.debug(
                        f"Навык '{self.name}': загружен output контракт {capability_name} v{version or 'active'}"
                    )
                else:
                    import logging
                    logging.getLogger(__name__).debug(
                        f"Навык '{self.name}': загружен input контракт {capability_name} v{version or 'active'}"
                    )
                    logging.getLogger(__name__).debug(
                        f"Навык '{self.name}': загружен output контракт {capability_name} v{version or 'active'}"
                    )

            except Exception as e:
                if hasattr(self.system_context, 'logger'):
                    self.system_context.logger.error(
                        f"Ошибка загрузки контрактов {capability_name} для навыка '{self.name}': {e}"
                    )
                else:
                    import logging
                    logging.getLogger(__name__).error(
                        f"Ошибка загрузки контрактов {capability_name} для навыка '{self.name}': {e}"
                    )
                raise

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
            schema = self.get_input_contract(capabilities[0].name)
        else:
            schema = {"type": "object", "properties": {}}

        return Metadata(schema)

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
    @abstractmethod
    async def execute(
        self,
        capability: Capability,
        parameters: Dict[str, Any],
        context: BaseSessionContext,
    ) -> ExecutionResult:
        """
        Выполнение конкретной capability навыка.

        ПАРАМЕТРЫ:
        - capability: выбранная возможность для выполнения
        - parameters: параметры от LLM или runtime
        - context: порт для работы с контекстом сессии

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
        # По умолчанию делегируем выполнение методу run для обратной совместимости
        result = await self.run(parameters, context)
        return ExecutionResult(
            status=ExecutionStatus.SUCCESS,
            result=result,
            observation_item_id=None,
            summary=f"Capability {capability.name} executed successfully",
            error=None
        )

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
            schema = capabilities[0].parameters_schema
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
            if hasattr(self.system_context, 'logger'):
                self.system_context.logger.error(f"Ошибка перезапуска навыка {self.name}: {str(e)}")
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
        from core.infrastructure.utils.module_reloader import safe_reload_component_with_module_reload
        if hasattr(self.system_context, 'logger'):
            self.system_context.logger.warning(f"Выполняется перезапуск с перезагрузкой модуля для навыка {self.name}")
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