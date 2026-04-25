"""
Сервис промптов с изолированным кэшем.
"""
from typing import Dict, Optional, Any
from core.components.services.service import Service
from core.config.component_config import ComponentConfig
from core.models.errors.version_not_found import VersionNotFoundError


class PromptService(Service):
    """
    Сервис промптов с ИЗОЛИРОВАННЫМ кэшем.
    Создаётся НОВЫЙ экземпляр для каждого ApplicationContext.
    """

    @property
    def description(self) -> str:
        return "Сервис промптов с изолированным кэшем"
    
    def __init__(
        self,
        name: str = "prompt_service",
        application_context: 'ApplicationContext' = None,
        component_config: ComponentConfig = None,
        executor = None
    ):
        # Call the parent constructor with proper parameters
        super().__init__(
            name=name,
            component_config=component_config,
            executor=executor,
            application_context=application_context
        )
        # Кэш: {capability: {version: prompt_obj}} - структура для совместимости с BaseComponent
        self.prompts: Dict[str, Dict[str, Any]] = {}  # ← Изолированный кэш!
    
    async def initialize(self) -> bool:
        """Инициализация PromptService с использованием предзагруженных ресурсов из ComponentConfig."""
        try:
            # Используем предзагруженные промпты из ComponentConfig
            # Они уже были загружены в ComponentConfig через DataRepository
            for capability, version in self.component_config.prompt_versions.items():
                # Получаем промпт из resolved_prompts в ComponentConfig (предзагруженные ресурсы)
                if capability in self.component_config.resolved_prompts:
                    prompt_text = self.component_config.resolved_prompts[capability]
                    # Создаем объект промпта для совместимости
                    from core.models.data.prompt import Prompt, PromptStatus, ComponentType
                    prompt_obj = Prompt(
                        capability=capability,
                        version=version,
                        status=PromptStatus.ACTIVE,
                        component_type=ComponentType.SERVICE,
                        content=prompt_text,
                        variables=[],
                        metadata={}
                    )

                    if capability not in self.prompts:
                        self.prompts[capability] = {}
                    self.prompts[capability][version] = prompt_obj
                else:
                    self._log_warning(f"Промпт {capability}@{version} не найден в предзагруженных ресурсах")

            self._initialized = True
            self._log_info(
                f"PromptService инициализирован: загружено {len(self.prompts)} промптов"
            )
            return True
        except Exception as e:
            self._log_error(f"Ошибка инициализации PromptService: {e}")
            return False

    def get_prompt(self, capability_name: str, version: Optional[str] = None) -> str:
        """Возвращает промпт из ИЗОЛИРОВАННОГО кэша."""
        if not self._initialized:
            raise RuntimeError(
                f"Сервис '{self.name}' не инициализирован. "
                f"Вызовите .initialize() перед использованием."
            )

        if capability_name not in self.prompts:
            raise KeyError(
                f"Промпт для capability '{capability_name}' не найден в кэше. "
                f"Доступные: {list(self.prompts.keys())}"
            )

        # Если версия не указана, берем первую доступную
        if version is None:
            # Берем первую доступную версию
            available_versions = list(self.prompts[capability_name].keys())
            if not available_versions:
                raise KeyError(
                    f"Нет доступных версий промпта для capability '{capability_name}'"
                )
            version = available_versions[0]

        if version not in self.prompts[capability_name]:
            raise KeyError(
                f"Версия '{version}' промпта для capability '{capability_name}' не найдена в кэше. "
                f"Доступные версии: {list(self.prompts[capability_name].keys())}"
            )

        # Получаем элемент из кэша
        cached_item = self.prompts[capability_name][version]
        # Если элемент - это объект Prompt, возвращаем его content
        if hasattr(cached_item, 'content'):
            return cached_item.content
        # Если элемент - это строка, возвращаем его напрямую
        else:
            return cached_item

    def get_all_prompts(self) -> Dict[str, Dict[str, Any]]:
        """Возвращает копию кэша промптов (для отладки)."""
        if not self._initialized:
            raise RuntimeError(
                f"Сервис '{self.name}' не инициализирован. "
                f"Вызовите .initialize() перед использованием."
            )
        return self.prompts.copy()

    async def preload_prompts(self, component_config) -> bool:
        """
        Предзагрузка всех промптов, указанных в конфигурации компонента.
        Совместимость с BaseComponent.
        """
        if not hasattr(component_config, 'prompt_versions'):
            self._log_info("Нет конфигурации промптов для предзагрузки")
            return True

        success = True
        # Используем внедрённый prompt_storage из BaseComponent
        storage = self.prompt_storage

        if storage is None:
            self._log_error("prompt_storage не внедрён")
            return False

        for capability_name, version in component_config.prompt_versions.items():
            try:
                # Загружаем промпт и помещаем его в кэш
                prompt_obj = await storage.load(capability_name, version)

                # Помещаем в кэш для быстрого доступа
                if capability_name not in self.prompts:
                    self.prompts[capability_name] = {}

                self.prompts[capability_name][version] = prompt_obj

                self._log_debug(f"Предзагружен промпт {capability_name} версии {version}")

            except Exception as e:
                self._log_error(f"Ошибка предзагрузки промпта {capability_name} версии {version}: {e}")
                success = False

        return success

    async def get_prompt_object(self, capability: str, version: Optional[str] = None) -> Any:
        """
        Возвращает объект промпта (не строку!).
        """
        # Если версия не указана, берем первую доступную
        if version is None:
            if capability not in self.prompts or not self.prompts[capability]:
                raise KeyError(f"Нет доступных версий промпта для capability '{capability}'")
            version = list(self.prompts[capability].keys())[0]

        if capability not in self.prompts or version not in self.prompts[capability]:
            # Загружаем из хранилища, если нет в кэше
            # Используем внедрённый prompt_storage из BaseComponent
            storage = self.prompt_storage
            
            if storage is None:
                raise RuntimeError("prompt_storage не внедрён")
            
            prompt_obj = await storage.load(capability, version)

            # Сохраняем в кэш
            if capability not in self.prompts:
                self.prompts[capability] = {}
            self.prompts[capability][version] = prompt_obj

            return prompt_obj

        return self.prompts[capability][version]

    def get_prompt_from_cache(self, capability_name: str, version: Optional[str] = None) -> Optional[str]:
        """
        Получение промпта ТОЛЬКО из кэша (без обращения к файловой системе).
        Совместимость с BaseComponent.
        """
        if capability_name in self.prompts:
            if version:
                if version in self.prompts[capability_name]:
                    cached_item = self.prompts[capability_name][version]
                    # Если элемент - это объект Prompt, возвращаем его content
                    if hasattr(cached_item, 'content'):
                        return cached_item.content
                    # Если элемент - это строка, возвращаем его напрямую
                    else:
                        return cached_item
            else:
                # Если нет версии, возвращаем первую доступную
                if self.prompts[capability_name]:
                    # Возвращаем контент первой доступной версии
                    first_version = list(self.prompts[capability_name].keys())[0]  # берем первую доступную
                    cached_item = self.prompts[capability_name][first_version]
                    # Если элемент - это объект Prompt, возвращаем его content
                    if hasattr(cached_item, 'content'):
                        return cached_item.content
                    # Если элемент - это строка, возвращаем его напрямую
                    else:
                        return cached_item

        return None

    def _execute_impl(
        self,
        capability: 'Capability',
        parameters: Dict[str, Any],
        execution_context: 'ExecutionContext'
    ) -> Dict[str, Any]:
        """
        Реализация бизнес-логики сервиса промптов (СИНХРОННАЯ).

        ВАЖНО: Валидация входа/выхода и метрики выполняются в BaseComponent.execute()
        Здесь только бизнес-логика.
        
        АРХИТЕКТУРА: Используем get_input_contract() для валидации структуры входных данных.
        """
        # Получаем входной контракт для валидации структуры параметров
        input_schema = self.get_input_contract("prompt_service.get_prompt")
        if input_schema:
            # Валидация структуры входных данных через контракт
            validated_input = input_schema.model_validate(parameters)
        
        # Получение промпта по capability
        prompt_content = self.get_prompt(capability.name)
        result = {"prompt": prompt_content, "capability": capability.name}
        
        # Валидация выхода через контракт (если доступен)
        output_schema = self.get_output_contract("prompt_service.get_prompt")
        if output_schema:
            return output_schema.model_validate(result).model_dump()
        
        return result