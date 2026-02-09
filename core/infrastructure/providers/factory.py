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
from core.infrastructure.providers.llm.vllm_provider import VLLMProvider
from core.infrastructure.providers.llm.llama_cpp_provider import LlamaCppProvider
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
        - vllm: VLLMProvider
        - llama_cpp: LlamaCppProvider
        
        ПРИМЕР:
        config = {
            "type": "vllm",
            "model_name": "mistral-7b",
            "parameters": {
                "tensor_parallel_size": 1,
                "gpu_memory_utilization": 0.9
            }
        }
        provider = await factory.create_llm_provider_from_config(config, "primary_llm")
        """
        provider_type = provider_config.type_provider.lower()
        model_name = provider_config.model_name
        parameters = provider_config.parameters
        
        try:
            if provider_type == "vllm":
                provider = VLLMProvider(model_name = model_name, config = parameters)
            elif provider_type == "llama_cpp":
                provider = LlamaCppProvider(model_name = model_name, config = parameters)
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
            return None
    
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
            self.system_context.registry.register(resource_info)
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
        
        # 3. Регистрация обнаруженных навыков в реестре
        for skill_name, skill in skills.items():
            resource_info = ResourceInfo(
                name=skill_name,
                resource_type=ResourceType.SKILL,
                instance=skill
            )
            resource_info.is_default=False
            self.system_context.registry.register(resource_info)
            logger.info(f"Навык '{skill_name}' успешно зарегистрирован в реестре")
        
        logger.info(f"Успешно создано и зарегистрировано навыков: {len(skills)}")
        return skills

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