"""
Фабрика для создания провайдеров из конфигурации.
ОСОБЕННОСТИ:
- Централизованное создание провайдеров
- Поддержка разных типов провайдеров (LLM, DB, Tools)
- Соответствие архитектуре портов и адаптеров
- Отсутствие циклических зависимостей
"""
import importlib
import inspect
import logging
import os
from pathlib import Path
import pkgutil
from typing import Dict, Any, Optional, Type
from core.infrastructure.providers.llm.base_llm import BaseLLMProvider
from core.infrastructure.providers.llm.llama_cpp_provider import LlamaCppProvider
from core.infrastructure.providers.llm.mock_provider import MockLLMProvider
from core.infrastructure.providers.database.base_db import BaseDBProvider, DBConnectionConfig
from core.infrastructure.providers.database.postgres_provider import PostgreSQLProvider
from core.infrastructure.tools.base_tool import BaseTool
from core.system_context.base_system_contex import BaseSystemContext
from core.system_context.resource_registry import ResourceInfo
from models.resource import ResourceType


logger = logging.getLogger(__name__)

class ProviderFactory:
    """
    Фабрика для создания провайдеров из конфигурации.
    
    ФУНКЦИОНАЛЬНОСТЬ:
    - Создание LLM провайдеров из конфигурации
    - Создание DB провайдеров из конфигурации  
    - Создание инструментов из конфигурации
    - Инициализация созданных провайдеров
    """
    
    def __init__(self, system_context: BaseSystemContext):
        """
        Инициализация фабрики провайдеров.
        
        ПАРАМЕТРЫ:
        - system_context: Системный контекст для доступа к ресурсам
        """
        self.system_context = system_context
        self.tools_dir = Path("core/infrastructure/tools")
    
    async def create_llm_provider_from_config(
        self,
        provider_config: Dict[str, Any],
        provider_name: str
    ) -> Optional[BaseLLMProvider]:
        """
        Создание LLM провайдера из конфигурации.

        ПАРАМЕТРЫ:
        - provider_config: Конфигурация провайдера
        - provider_name: Имя провайдера

        ВОЗВРАЩАЕТ:
        - BaseLLMProvider: Созданный и инициализированный провайдер
        - None если тип провайдера не поддерживается

        ПОДДЕРЖИВАЕМЫЕ ТИПЫ:
        - llama_cpp: LlamaCppProvider
        - mock: MockLLMProvider (для тестирования)

        ПРИМЕР:
        config = {
            "type": "llama_cpp",
            "model_name": "mistral-7b",
            "parameters": {
                "model_path": "./models/mistral-7b.gguf",
                "n_ctx": 2048,
                "temperature": 0.7
            }
        }
        provider = await factory.create_llm_provider_from_config(config, "primary_llm")
        """
        # Проверяем, является ли provider_config словарем или объектом Pydantic
        if hasattr(provider_config, 'type_provider'):
            # Это объект Pydantic
            provider_type = getattr(provider_config, 'type_provider', 'llama_cpp').lower()
            model_name = getattr(provider_config, 'model_name', 'default_model')
            parameters = getattr(provider_config, 'parameters', {})
        else:
            # Это словарь
            provider_type = provider_config.get("type", provider_config.get("type_provider", "llama_cpp")).lower()
            model_name = provider_config.get("model_name", "default_model")
            parameters = provider_config.get("parameters", {})

        try:
            if provider_type == "llama_cpp":
                # Подготовим словарь параметров для LlamaCppProvider
                config_params = {
                    "model_path": parameters.get("model_path"),
                    "n_ctx": parameters.get("n_ctx", 2048),
                    "n_gpu_layers": parameters.get("n_gpu_layers", 0),
                    "n_batch": parameters.get("n_batch", 512),
                    "temperature": parameters.get("temperature", 0.7),
                    "max_tokens": parameters.get("max_tokens", 512),
                    "top_p": parameters.get("top_p", 0.95),
                    "verbose": parameters.get("verbose", False),
                    "f16_kv": True,
                    "embedding": False,
                    "stop": parameters.get("stop", ["\n", "###"]),
                    "echo": False
                }
                provider = LlamaCppProvider(config=config_params, model_name=model_name)
            elif provider_type == "mock":
                # Используем mock-провайдер для тестирования
                from core.infrastructure.providers.llm.mock_provider import MockLLMConfig
                config = MockLLMConfig(
                    model_name=model_name,
                    temperature=parameters.get("temperature", 0.7),
                    max_tokens=parameters.get("max_tokens", 512),
                    verbose=parameters.get("verbose", False)
                )
                provider = MockLLMProvider(config=config)
            else:
                logger.error(f"Неподдерживаемый тип LLM провайдера: {provider_type}")
                return None

            # Инициализация провайдера
            success = await provider.initialize()
            if not success:
                logger.error(f"Не удалось инициализировать LLM провайдер {provider_name}")
                return None

            logger.info(f"LLM провайдер '{provider_name}' ({provider_type}) успешно создан и инициализирован")
            return provider

        except Exception as e:
            logger.error(f"Ошибка создания LLM провайдера '{provider_name}': {str(e)}", exc_info=True)
            # Храним ошибку и возвращаем ее, чтобы система могла правильно обработать недоступность провайдера
            raise
    
    async def create_db_provider_from_config(
        self,
        provider_config: Dict[str, Any],
        provider_name: str
    ) -> Optional[BaseDBProvider]:
        """
        Создание DB провайдера из конфигурации.
        
        ПАРАМЕТРЫ:
        - provider_config: Конфигурация провайдера
        - provider_name: Имя провайдера
        
        ВОЗВРАЩАЕТ:
        - BaseDBProvider: Созданный и инициализированный провайдер
        - None если тип провайдера не поддерживается
        
        ПОДДЕРЖИВАЕМЫЕ ТИПЫ:
        - postgres: PostgreSQLProvider
        
        ПРИМЕР:
        config = {
            "type": "postgres",
            "parameters": {
                "host": "localhost",
                "port": 5432,
                "database": "agent_db",
                "username": "user",
                "password": "pass"
            }
        }
        provider = await factory.create_db_provider_from_config(config, "main_db")
        """
        provider_type = provider_config.type_provider.lower()
        parameters = provider_config.parameters
        
        try:
            if provider_type == "postgres":
                # Создание конфигурации подключения
                db_config = DBConnectionConfig(**parameters)
                provider = PostgreSQLProvider(db_config)
            else:
                logger.error(f"Неподдерживаемый тип DB провайдера: {provider_type}")
                return None
            
            # Инициализация провайдера
            success = await provider.initialize()
            if not success:
                logger.error(f"Не удалось инициализировать DB провайдер {provider_name}")
                return None
            
            logger.info(f"DB провайдер '{provider_name}' ({provider_type}) успешно создан и инициализирован")
            return provider
            
        except Exception as e:
            logger.error(f"Ошибка создания DB провайдера '{provider_name}': {str(e)}", exc_info=True)
            return None
        
    async def discover_and_create_all_tools(self):
        """Единый метод для автоматического обнаружения ВСЕХ инструментов
        и применения конфигурации при наличии.
        
        ВОЗВРАЩАЕТ:
        - Словарь {имя_инструмента: инструмент} для всех успешно созданных инструментов
        """
        tools = {}
        
        # 1. Автоматическое обнаружение инструментов из директории
        discovered_tools = await self._discover_tools_from_directory()
        
        # 2. Применение конфигурации к обнаруженным инструментам
        for tool_name, tool_class in discovered_tools.items():
            # Получаем конфигурацию из общей конфигурации системы
            tool_config = self._get_tool_config(tool_name)
            
            # Пропускаем отключенные инструменты
            if not tool_config.get("enabled", True):
                logger.info(f"Инструмент '{tool_name}' отключен в конфигурации")
                continue
            
            # Создаем инструмент с применением конфигурации
            tool = await self._create_tool_instance(tool_class, tool_name, tool_config)
            if tool:
                tools[tool_name] = tool
        
        # 3. Регистрация обнаруженных инструментов в реестре
        for tool_name, tool in tools.items():
            resource_info = ResourceInfo(
                name=tool_name,
                resource_type=ResourceType.TOOL,
                instance=tool
            )
            resource_info.is_default=False
            self.system_context.registry.register_resource(resource_info)
            logger.info(f"Инструмент '{tool_name}' успешно зарегистрирован в реестре")
        
        logger.info(f"Успешно создано и зарегистрировано инструментов: {len(tools)}")
    
    async def _discover_tools_from_directory(self) -> Dict[str, Type[BaseTool]]:
        """Обнаружение всех классов инструментов в директории.
        
        ВОЗВРАЩАЕТ:
        - Словарь {имя_инструмента: класс_инструмента} для всех найденных инструментов
        """
        tool_classes = {}
        
        if not self.tools_dir.exists():
            logger.warning(f"Директория инструментов не найдена: {self.tools_dir}")
            return tool_classes
        
        logger.info(f"Сканирование директории инструментов: {self.tools_dir}")
        
        # Получаем путь к модулю в формате Python
        tools_package_path = str(self.tools_dir).replace("/", ".").replace("\\", ".")
        
        try:
            # Импортируем пакет инструментов
            tools_package = importlib.import_module(tools_package_path)
            
            # Сканируем все модули в пакете
            for _, module_name, _ in pkgutil.iter_modules(tools_package.__path__):
                full_module_name = f"{tools_package_path}.{module_name}"
                
                try:
                    # Динамически импортируем модуль
                    module = importlib.import_module(full_module_name)
                    
                    # Ищем все классы в модуле, наследуемые от BaseTool
                    for name, obj in inspect.getmembers(module, inspect.isclass):
                        # Проверяем, что класс определен в этом модуле (а не импортирован)
                        if obj.__module__ != full_module_name:
                            continue
                        
                        # Проверяем наследование от BaseTool
                        if issubclass(obj, BaseTool) and obj != BaseTool:
                            # Генерируем имя инструмента из имени класса
                            # tool_name = self._normalize_tool_name(name)
                            tool_classes[name] = obj
                            logger.debug(f"Найден класс инструмента '{name}'")
                
                except Exception as e:
                    logger.error(f"Ошибка при загрузке модуля '{full_module_name}': {str(e)}")
        
        except Exception as e:
            logger.error(f"Ошибка при импорте пакета инструментов '{tools_package_path}': {str(e)}")
        
        logger.info(f"Найдено классов инструментов: {len(tool_classes)}")
        return tool_classes
    
    def _get_tool_config(self, tool_name: str) -> Dict[str, Any]:
        """Получение конфигурации для инструмента из общей конфигурации.
        
        ПАРАМЕТРЫ:
        - tool_name: Имя инструмента
        
        ВОЗВРАЩАЕТ:
        - Словарь с конфигурацией инструмента или конфигурацию по умолчанию
        """
        # Получаем конфигурацию инструментов из системы
        tools_config = getattr(self.system_context.config, 'tools', {})
        
        if tool_name in tools_config:
            config = tools_config[tool_name]
            if hasattr(config, "dict"):
                return config.dict()
            elif hasattr(config, "__dict__"):
                return config.__dict__
            elif isinstance(config, dict):
                return config
        
        # Конфигурация по умолчанию
        return {
            "enabled": True,
            "parameters": {}
        }
    
    async def _create_tool_instance(
        self, 
        tool_class: Type[BaseTool], 
        tool_name: str, 
        config: Dict[str, Any]
    ) -> Optional[BaseTool]:
        """Создание экземпляра инструмента с применением конфигурации.
        
        ПАРАМЕТРЫ:
        - tool_class: Класс инструмента
        - tool_name: Имя инструмента
        - config: Конфигурация инструмента
        
        ВОЗВРАЩАЕТ:
        - Экземпляр инструмента или None при ошибке
        """
        try:
            logger.debug(f"Создание инструмента '{tool_name}' из класса {tool_class.__name__}")
            
            # Подготовка параметров для конструктора
            init_params = {
                "name": tool_name,
                "system_context": self.system_context,
                **config.get("parameters", {})
            }
            
            # Создание экземпляра
            tool = tool_class(**init_params)
            
            # Инициализация инструмента
            if hasattr(tool, "initialize") and callable(tool.initialize):
                await tool.initialize()
            
            logger.info(f"Инструмент '{tool_name}' успешно создан")
            return tool
            
        except Exception as e:
            logger.error(f"Ошибка создания инструмента '{tool_name}': {str(e)}", exc_info=True)
            return None

    async def discover_and_create_all_skills(self) -> Dict[str, Any]:
        """Автоматическое обнаружение и создание ВСЕХ навыков из директории."""
        skills = {}
        
        # 1. Автоматическое обнаружение навыков из директории
        discovered_skills = await self._discover_skills_from_directory()
        
        # 2. Применение конфигурации к обнаруженным навыкам
        for skill_name, skill_class in discovered_skills.items():
            # Получаем конфигурацию из общей конфигурации системы
            skill_config = self._get_skill_config(skill_name)
            
            # Пропускаем отключенные навыки
            if not skill_config.get("enabled", True):
                logger.info(f"Навык '{skill_name}' отключен в конфигурации")
                continue
            
            # Создаем навык с применением конфигурации
            skill = await self._create_skill_instance(skill_class, skill_name, skill_config)
            if skill:
                skills[skill_name] = skill
        
        # 3. Регистрация обнаруженных навыков в реестре (вместе с их возможностями)
        for skill_name, skill in skills.items():
            self.system_context.registry.register_from_skill(skill)
            logger.info(f"Навык '{skill_name}' успешно зарегистрирован в реестре вместе с его возможностями")
        
        logger.info(f"Успешно создано и зарегистрировано навыков: {len(skills)}")
        return skills

    async def discover_and_create_all_services(self):
        """Единый метод для автоматического обнаружения ВСЕХ инфраструктурных сервисов
        и применения конфигурации при наличии.

        ВОЗВРАЩАЕТ:
        - Словарь {имя_сервиса: сервис} для всех успешно созданных сервисов
        """
        services = {}

        # 1. Автоматическое обнаружение сервисов из директории
        discovered_services = await self._discover_services_from_directory()

        # 2. Применение конфигурации к обнаруженным сервисам
        for service_name, service_class in discovered_services.items():
            # Получаем конфигурацию из общей конфигурации системы
            service_config = self._get_service_config(service_name)

            # Пропускаем отключенные сервисы
            if not service_config.get("enabled", True):
                logger.info(f"Сервис '{service_name}' отключен в конфигурации")
                continue

            # Создаем сервис с применением конфигурации
            service = await self._create_service_instance(service_class, service_name, service_config)
            if service:
                services[service_name] = service

        # 3. Регистрация обнаруженных сервисов в реестре
        for service_name, service in services.items():
            resource_info = ResourceInfo(
                name=service_name,
                resource_type=ResourceType.SERVICE,
                instance=service
            )
            self.system_context.registry.register_resource(resource_info)
            logger.info(f"Сервис '{service_name}' успешно зарегистрирован в реестре")

        logger.info(f"Успешно создано и зарегистрировано сервисов: {len(services)}")

    async def _discover_services_from_directory(self):
        """Обнаружение всех классов сервисов в директории сервисов."""
        from pathlib import Path
        import importlib
        import pkgutil
        import inspect

        service_classes = {}

        services_dir = Path("core/infrastructure/service")

        if not services_dir.exists():
            logger.warning(f"Директория сервисов не найдена: {services_dir}")
            return service_classes

        logger.info(f"Сканирование директории сервисов: {services_dir}")

        # Получаем путь к модулю в формате Python
        services_package_path = str(services_dir).replace("/", ".").replace("\\", ".")

        try:
            # Импортируем пакет сервисов
            services_package = importlib.import_module(services_package_path)

            # Сканируем все модули в пакете
            for _, module_name, _ in pkgutil.iter_modules(services_package.__path__):
                if module_name in ['base_service']:  # Пропускаем базовые классы
                    continue
                    
                full_module_name = f"{services_package_path}.{module_name}"

                try:
                    # Динамически импортируем модуль
                    module = importlib.import_module(full_module_name)

                    # Ищем все классы в модуле, наследуемые от BaseService
                    for name, obj in inspect.getmembers(module, inspect.isclass):
                        # Проверяем, что класс определен в этом модуле (а не импортирован)
                        if obj.__module__ != full_module_name:
                            continue

                        # Проверяем наследование от BaseService
                        try:
                            from core.infrastructure.service.base_service import BaseService
                            if issubclass(obj, BaseService) and obj != BaseService:
                                # Исключаем PromptService из автоматической регистрации, 
                                # так как он регистрируется вручную как системный сервис
                                if name != "PromptService":
                                    # Генерируем имя сервиса из имени класса
                                    service_classes[name] = obj
                                    logger.debug(f"Найден класс сервиса '{name}' в модуле {module_name}")
                                else:
                                    logger.debug(f"Пропущен класс сервиса '{name}' (регистрируется вручную)")
                        except:
                            # Если не удается проверить наследование, пропускаем
                            continue

                except Exception as e:
                    logger.error(f"Ошибка при загрузке модуля '{full_module_name}': {str(e)}")

        except Exception as e:
            logger.error(f"Ошибка при импорте пакета сервисов '{services_package_path}': {str(e)}")

        logger.info(f"Найдено классов сервисов: {len(service_classes)}")
        return service_classes

    def _get_service_config(self, service_name: str) -> Dict[str, Any]:
        """Получение конфигурации для сервиса из общей конфигурации."""
        # Получаем конфигурацию сервисов из системы
        services_config = getattr(self.system_context.config, 'services', {})

        if service_name in services_config:
            config = services_config[service_name]
            if hasattr(config, "dict"):
                return config.dict()
            elif hasattr(config, "__dict__"):
                return config.__dict__
            elif isinstance(config, dict):
                return config

        # Конфигурация по умолчанию
        return {
            "enabled": True,
            "parameters": {}
        }

    async def _create_service_instance(
        self,
        service_class,
        service_name: str,
        config: Dict[str, Any]
    ):
        """Создание экземпляра сервиса с применением конфигурации."""
        try:
            logger.debug(f"Создание сервиса '{service_name}' из класса {service_class.__name__}")

            # Подготовка параметров для конструктора
            init_params = {
                "system_context": self.system_context,
                "name": service_name,
                **config.get("parameters", {})
            }

            # Создание экземпляра
            service = service_class(**init_params)

            # Инициализация сервиса
            if hasattr(service, "initialize") and callable(getattr(service, "initialize")):
                success = await service.initialize()
                if not success:
                    logger.warning(f"Сервис '{service_name}' не прошел инициализацию")
                    return None

            logger.info(f"Сервис '{service_name}' успешно создан")
            return service

        except Exception as e:
            logger.error(f"Ошибка создания сервиса '{service_name}': {str(e)}", exc_info=True)
            return None

    async def _discover_skills_from_directory(self) -> Dict[str, Type[Any]]:
        """Обнаружение всех классов навыков в директории навыков."""
        skill_classes = {}
        
        skills_dir = Path("core/skills")
        
        if not skills_dir.exists():
            logger.warning(f"Директория навыков не найдена: {skills_dir}")
            return skill_classes
        
        logger.info(f"Сканирование директории навыков: {skills_dir}")
        
        # Получаем путь к модулю в формате Python
        skills_package_path = str(skills_dir).replace("/", ".").replace("\\", ".")
        
        try:
            # Импортируем пакет навыков
            skills_package = importlib.import_module(skills_package_path)
            
            # Сканируем все поддиректории и модули
            for root, dirs, files in os.walk(skills_dir):
                for dir_name in dirs:
                    if dir_name.startswith("__") or dir_name in ["base", "templates"]:
                        continue
                    
                    skill_subdir = Path(root) / dir_name
                    skill_package_path = str(skill_subdir).replace("/", ".").replace("\\", ".")
                    
                    try:
                        # Импортируем подпакет навыка
                        skill_package = importlib.import_module(skill_package_path)
                        
                        # Сканируем все модули в подпакете
                        for _, module_name, _ in pkgutil.iter_modules(skill_package.__path__):
                            if module_name.startswith("__"):
                                continue
                            
                            full_module_name = f"{skill_package_path}.{module_name}"
                            
                            try:
                                # Динамически импортируем модуль
                                module = importlib.import_module(full_module_name)
                                
                                # Ищем все классы в модуле, наследуемые от BaseSkill
                                for name, obj in inspect.getmembers(module, inspect.isclass):
                                    # Проверяем, что класс определен в этом модуле
                                    if obj.__module__ != full_module_name:
                                        continue
                                    
                                    # Проверяем наследование от BaseSkill
                                    if hasattr(obj, '__bases__') and any('BaseSkill' in str(base) for base in obj.__bases__):
                                        skill_classes[name] = obj
                                        logger.debug(f"Найден класс навыка '{name}'")
                            
                            except Exception as e:
                                logger.error(f"Ошибка при загрузке модуля '{full_module_name}': {str(e)}")
                    
                    except Exception as e:
                        logger.error(f"Ошибка при импорте пакета навыков '{skill_package_path}': {str(e)}")
            
        except Exception as e:
            logger.error(f"Ошибка при импорте пакета навыков '{skills_package_path}': {str(e)}")
        
        logger.info(f"Найдено классов навыков: {len(skill_classes)}")
        return skill_classes

    def _get_skill_config(self, skill_name: str) -> Dict[str, Any]:
        """Получение конфигурации для навыка из общей конфигурации."""
        # Получаем конфигурацию навыков из системы
        skills_config = getattr(self.system_context.config, 'skills', {})
        
        if skill_name in skills_config:
            config = skills_config[skill_name]
            if hasattr(config, "dict"):
                return config.dict()
            elif hasattr(config, "__dict__"):
                return config.__dict__
            elif isinstance(config, dict):
                return config
        
        # Конфигурация по умолчанию
        return {
            "enabled": True,
            "parameters": {}
        }

    async def _create_skill_instance(
        self,
        skill_class: Type[Any],
        skill_name: str,
        config: Dict[str, Any]
    ) -> Optional[Any]:
        """Создание экземпляра навыка с применением конфигурации."""
        try:
            logger.debug(f"Создание навыка '{skill_name}' из класса {skill_class.__name__}")

            # Подготовка параметров для конструктора
            init_params = {
                "name": skill_name,
                "system_context": self.system_context,
                **config.get("parameters", {})
            }

            # Создание экземпляра
            skill = skill_class(**init_params)

            # Инициализация навыка
            if hasattr(skill, "initialize") and callable(skill.initialize):
                await skill.initialize()

            logger.info(f"Навык '{skill_name}' успешно создан")
            return skill

        except Exception as e:
            logger.error(f"Ошибка создания навыка '{skill_name}': {str(e)}", exc_info=True)
            return None

    @staticmethod
    def create_llm_provider(provider_type: str, model_name: str, config: Optional[Dict[str, Any]] = None):
        """
        Создание LLM провайдера по типу.

        ПАРАМЕТРЫ:
        - provider_type: Тип провайдера ('llama_cpp')
        - model_name: Название модели
        - config: Дополнительная конфигурация

        ВОЗВРАЩАЕТ:
        - BaseLLMProvider: Созданный провайдер
        """
        config = config or {}
        
        if provider_type == "llama_cpp":
            return LlamaCppProvider(model_name=model_name, config=config)
        else:
            raise ValueError(f"Unsupported LLM provider type: {provider_type}")

    @staticmethod
    def create_db_provider(provider_type: str, config: DBConnectionConfig):
        """
        Создание DB провайдера по типу.

        ПАРАМЕТРЫ:
        - provider_type: Тип провайдера ('postgres')
        - config: Конфигурация подключения

        ВОЗВРАЩАЕТ:
        - BaseDBProvider: Созданный провайдер
        """
        if provider_type == "postgres":
            return PostgreSQLProvider(config=config)
        else:
            raise ValueError(f"Unsupported DB provider type: {provider_type}")

    @staticmethod
    async def initialize_provider(provider):
        """
        Инициализация провайдера.

        ПАРАМЕТРЫ:
        - provider: Провайдер для инициализации

        ВОЗВРАЩАЕТ:
        - bool: Успех инициализации
        """
        try:
            success = await provider.initialize()
            return success
        except Exception as e:
            logger.error(f"Ошибка инициализации провайдера: {str(e)}")
            return False

    @staticmethod
    async def create_and_initialize_llm(provider_type: str, model_name: str, config: Dict[str, Any]):
        """
        Создание и инициализация LLM провайдера.

        ПАРАМЕТРЫ:
        - provider_type: Тип провайдера
        - model_name: Название модели
        - config: Конфигурация

        ВОЗВРАЩАЕТ:
        - BaseLLMProvider: Инициализированный провайдер

        ВЫЗЫВАЕТ:
        - RuntimeError если инициализация не удалась
        """
        provider = ProviderFactory.create_llm_provider(provider_type, model_name, config)
        success = await ProviderFactory.initialize_provider(provider)
        
        if not success:
            raise RuntimeError(f"Не удалось инициализировать LLM провайдер типа {provider_type}")
        
        return provider

    @staticmethod
    async def create_and_initialize_db(provider_type: str, config: DBConnectionConfig):
        """
        Создание и инициализация DB провайдера.

        ПАРАМЕТРЫ:
        - provider_type: Тип провайдера
        - config: Конфигурация подключения

        ВОЗВРАЩАЕТ:
        - BaseDBProvider: Инициализированный провайдер

        ВЫЗЫВАЕТ:
        - RuntimeError если инициализация не удалась
        """
        provider = ProviderFactory.create_db_provider(provider_type, config)
        success = await ProviderFactory.initialize_provider(provider)
        
        if not success:
            raise RuntimeError(f"Не удалось инициализировать DB провайдер типа {provider_type}")
        
        return provider