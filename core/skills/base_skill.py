"""
Базовый класс навыка (Skill) с поддержкой архитектуры портов и адаптеров.

ОСНОВНЫЕ ИЗМЕНЕНИЯ:
1. Полная инверсия зависимостей через порты
2. Устранение дублирования метода run()
3. Использование портов вместо прямых зависимостей
4. Четкое разделение ответственности
5. Кэширование промптов и контрактов при инициализации
6. Поддержка локальных конфигураций компонентов с разделением input/output контрактов
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

class BaseSkill(ABC):
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
        self.name = name
        self.system_context = system_context
        self.prompt_service = system_context.get_resource("prompt_service")  # Получение сервиса
        self.contract_service = system_context.get_resource("contract_service")
        self.component_config = component_config
        self.config = kwargs

        # === КРИТИЧЕСКИ ВАЖНО: изолированные кэши инициализируются ПУСТЫМИ ===
        # Попытка использования до initialize() вызовет ошибку
        self._cached_prompts: Dict[str, str] = {}          # {capability_name: prompt_text}
        self._cached_input_contracts: Dict[str, Dict] = {}  # {capability_name: contract_schema}
        self._cached_output_contracts: Dict[str, Dict] = {} # {capability_name: contract_schema}
        self._agent_config: Optional[AgentConfig] = None
    
    # --------------------------------------------------
    # Initialization API
    # --------------------------------------------------
    async def initialize(self, agent_config: Optional[AgentConfig] = None) -> bool:
        """
        Инициализация с единовременной загрузкой ВСЕХ ресурсов из локальной конфигурации.
        После завершения метода компонент НЕ должен обращаться к внешним сервисам.
        """
        # === ШАГ 1: Загрузка из локальной конфигурации (приоритет) ===
        if self.component_config:
            # Загрузка промптов
            for cap_name, version in self.component_config.prompt_versions.items():
                prompt = await self.prompt_service.get_prompt(
                    capability_name=cap_name,
                    version=version,
                    allow_inactive=False
                )
                self._cached_prompts[cap_name] = prompt
            
            # Загрузка ВХОДЯЩИХ контрактов
            for cap_name, version in self.component_config.input_contract_versions.items():
                contract = await self.contract_service.get_contract(
                    capability_name=cap_name,
                    version=version,
                    direction="input"  # ← ЯВНО указываем направление
                )
                self._cached_input_contracts[cap_name] = contract
            
            # Загрузка ИСХОДЯЩИХ контрактов
            for cap_name, version in self.component_config.output_contract_versions.items():
                contract = await self.contract_service.get_contract(
                    capability_name=cap_name,
                    version=version,
                    direction="output"  # ← ЯВНО указываем направление
                )
                self._cached_output_contracts[cap_name] = contract
            
            self.system_context.logger.info(
                f"Навык '{self.name}' инициализирован с вариантом '{self.component_config.variant_key}'. "
                f"Загружено: промпты={len(self._cached_prompts)}, "
                f"input-контракты={len(self._cached_input_contracts)}, "
                f"output-контракты={len(self._cached_output_contracts)}"
            )
            return True
        
        # === ШАГ 2: Обратная совместимость — загрузка из глобального agent_config ===
        elif agent_config:
            # 1. Сохраняем конфигурацию для внутреннего использования
            self._agent_config = agent_config or AgentConfig.auto_resolve(self.system_context)

            # 2. Загружаем ВСЕ промпты для capability навыка согласно конфигурации
            # Это ЕДИНСТВЕННОЕ обращение к хранилищу промптов за жизненный цикл навыка
            for capability_name in self.get_capability_names():
                try:
                    # Загрузка ТОЧНО указанной версии из конфигурации
                    version = self._agent_config.prompt_versions.get(capability_name)

                    prompt = await self.prompt_service.get_prompt(
                        capability_name=capability_name,
                        version=version,
                        allow_inactive=self._agent_config.allow_inactive_resources
                    )

                    # Кэшируем промпт — больше обращений к хранилищу не будет
                    self._cached_prompts[capability_name] = prompt

                    self.system_context.logger.debug(
                        f"Навык '{self.name}': загружен промпт {capability_name} v{version or 'active'}"
                    )

                except Exception as e:
                    self.system_context.logger.error(
                        f"Ошибка загрузки промпта {capability_name} для навыка '{self.name}': {e}"
                    )
                    return False

            # 3. Загрузка контрактов (аналогично)
            await self._load_contracts()

            self.system_context.logger.info(
                f"Навык '{self.name}' инициализирован. Загружено промптов: {len(self._cached_prompts)}"
            )
            return True
        
        else:
            raise ValueError(
                f"Навык '{self.name}' не может быть инициализирован: "
                f"отсутствует и локальная конфигурация (component_config), "
                f"и глобальная (agent_config)"
            )

    async def initialize_with_config(self, system_resources_config: Any) -> bool:
        """
        Инициализация навыка с ОДНОКРАТНОЙ загрузкой промптов и контрактов из конфигурации системных ресурсов.
        Используется при инициализации системного контекста.
        """
        # 1. Сохраняем конфигурацию системных ресурсов для внутреннего использования
        self._system_resources_config = system_resources_config
        
        # 2. Загружаем промпты, специфичные для навыка, из конфигурации системных ресурсов
        await self._load_skill_prompts_from_system_config()
        
        # 3. Загрузка контрактов из конфигурации системных ресурсов
        await self._load_skill_contracts_from_system_config()
        
        self.system_context.logger.info(
            f"Навык '{self.name}' инициализирован с кэшированием системных ресурсов. Загружено промптов: {len(self._cached_prompts)}"
        )
        return True

    async def _load_skill_prompts_from_system_config(self):
        """Загрузка промптов для навыка из конфигурации системных ресурсов"""
        if hasattr(self._system_resources_config, 'resource_prompt_versions'):
            # Загрузка промптов для конкретных capability навыка
            for capability_name in self.get_capability_names():
                version = self._system_resources_config.resource_prompt_versions.get(capability_name)
                
                if version:
                    prompt = await self.prompt_service.get_prompt(
                        capability_name=capability_name,
                        version=version,
                        allow_inactive=self._system_resources_config.allow_inactive_resources
                    )
                    self._cached_prompts[capability_name] = prompt

    async def _load_skill_contracts_from_system_config(self):
        """Загрузка контрактов для навыка из конфигурации системных ресурсов"""
        if not self.contract_service:
            return
        
        # Логика загрузки контрактов для навыка из конфигурации системных ресурсов
        # Пример для навыка планирования:
        if self.name == "planning":
            contract_name = "planning.create_plan.output"
            version = self._system_resources_config.resource_contract_versions.get(contract_name)
            
            if version:
                contract = await self.contract_service.get_contract(
                    contract_name=contract_name,
                    version=version,
                    allow_inactive=self._system_resources_config.allow_inactive_resources
                )
                self._cached_contracts[contract_name] = contract

    async def _load_contracts(self):
        """Загрузка контрактов согласно конфигурации (аналогично промптам)"""
        if not self.contract_service:
            return
        
        # Логика загрузки контрактов для навыка (зависит от конкретного навыка)
        # Пример для навыка планирования:
        if self.name == "planning":
            contract_name = "planning.create_plan.output"
            version = self._agent_config.contract_versions.get(contract_name)
            
            if version:
                contract = await self.contract_service.get_contract(
                    contract_name=contract_name,
                    version=version,
                    allow_inactive=self._agent_config.allow_inactive_resources
                )
                self._cached_contracts[contract_name] = contract

    def get_prompt(self, capability_name: str) -> str:
        """Получение промпта ТОЛЬКО из изолированного кэша"""
        if capability_name not in self._cached_prompts:
            raise RuntimeError(
                f"Промпт для capability '{capability_name}' не загружен в навык '{self.name}'. "
                f"Возможно, не указана версия в component_config.prompt_versions."
            )
        return self._cached_prompts[capability_name]

    def get_input_contract(self, capability_name: str) -> Dict:
        """Получение входящего контракта ТОЛЬКО из кэша"""
        if capability_name not in self._cached_input_contracts:
            raise RuntimeError(
                f"Входящий контракт для capability '{capability_name}' не загружен в навык '{self.name}'. "
                f"Возможно, не указана версия в component_config.input_contract_versions."
            )
        return self._cached_input_contracts[capability_name]

    def get_output_contract(self, capability_name: str) -> Dict:
        """Получение исходящего контракта ТОЛЬКО из кэша"""
        if capability_name not in self._cached_output_contracts:
            raise RuntimeError(
                f"Исходящий контракт для capability '{capability_name}' не загружен в навык '{self.name}'. "
                f"Возможно, не указана версия в component_config.output_contract_versions."
            )
        return self._cached_output_contracts[capability_name]

    def get_contract(self, contract_name: str) -> Any:
        """Получение контракта из кэша (для обратной совместимости)"""
        # Проверяем сначала в старом кэше для обратной совместимости
        if contract_name in self._cached_contracts:
            return self._cached_contracts[contract_name]
        
        # Если не найден, пробуем найти в новых кэшах
        # Разделяем имя контракта на capability_name и направление
        parts = contract_name.split('.')
        if len(parts) >= 3:
            direction = parts[-1]  # последняя часть - направление
            capability_name = '.'.join(parts[:-1])  # всё остальное - имя capability
            
            if direction == "input":
                return self.get_input_contract(capability_name)
            elif direction == "output":
                return self.get_output_contract(capability_name)
        
        # Если не найден ни в одном кэше
        raise RuntimeError(
            f"Контракт '{contract_name}' не загружен в навыке '{self.name}'."
        )

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
            parameters_schema={"type": "object", "properties": {}},
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
            logger.error(f"Ошибка перезапуска навыка {self.name}: {str(e)}")
            return False

    def restart_with_module_reload(self):
        """
        Перезапуск навыка с перезагрузкой модуля Python.
        ВНИМАНИЕ: Использовать с осторожностью!
        
        ВОЗВРАЩАЕТ:
        - Новый экземпляр навыка из перезагруженного модуля
        """
        from core.infrastructure.utils.module_reloader import safe_reload_component_with_module_reload
        logger.warning(f"Выполняется перезапуск с перезагрузкой модуля для навыка {self.name}")
        return safe_reload_component_with_module_reload(self)

    async def shutdown(self):
        """
        Очистка ресурсов навыка перед остановкой или перезапуском.
        Может быть переопределен в дочерних классах.
        """
        # По умолчанию ничего не делаем, но метод может быть переопределен
        pass