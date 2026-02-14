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
from models.capability import Capability
from models.execution import ExecutionResult
from core.config.app_config import AppConfig
from core.application.components.base import BaseComponent

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

    def __init__(self, name: str, application_context: 'ApplicationContext', app_config: Optional['AppConfig'] = None, **kwargs):
        # Вызов конструктора родительского класса
        super().__init__(name, application_context, app_config)
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
            if hasattr(self.application_context, 'logger'):
                self.application_context.logger.info(
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