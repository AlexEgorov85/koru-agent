"""
Упрощенный менеджер жизненного цикла ресурсов.
ОСОБЕННОСТИ:
- Явный порядок инициализации
- Нет циклических зависимостей
- Простая обработка ошибок
- Минимальная функциональность
"""
import asyncio
import logging
from typing import Dict, Any, List, Optional, Tuple

from core.system_context.resource_registry import ResourceRegistry, ResourceInfo, ResourceType

logger = logging.getLogger(__name__)

class LifecycleManager:
    """
    Упрощенный менеджер жизненного цикла ресурсов.

    ПОРЯДОК ИНИЦИАЛИЗАЦИИ:
    1. LLM провайдеры
    2. Инструменты
    3. Навыки
    4. Прочие ресурсы

    ФУНКЦИОНАЛЬНОСТЬ:
    - Инициализация всех ресурсов в правильном порядке
    - Корректное завершение работы
    - Проверка здоровья системы
    """

    def __init__(
        self,
        registry: ResourceRegistry
    ):
        """
        Инициализация менеджера жизненного цикла.

        ПАРАМЕТРЫ:
        - registry: Единый реестр ресурсов и возможностей
        """
        self.registry = registry
    
    async def initialize(self) -> bool:
        """
        Инициализация всех ресурсов в правильном порядке.
        
        ВОЗВРАЩАЕТ:
        - True если все ресурсы инициализированы успешно
        - False если есть ошибки инициализации
        
        ПОРЯДОК:
        1. LLM провайдеры
        2. Инструменты
        3. Навыки
        4. Прочие ресурсы
        
        ОБРАБОТКА ОШИБОК:
        - Логирование ошибок инициализации
        - Продолжение инициализации остальных ресурсов
        - Возврат False при наличии ошибок
        """
        logger.info("Начало инициализации системы...")
        success = True
        
        # 1. Инициализация LLM провайдеров
        llm_resources = self._get_resources_by_type(ResourceType.LLM_PROVIDER)
        for name, info in llm_resources.items():
            if not await self._initialize_resource(name, info):
                success = False
        
        # 2. Инициализация инструментов
        tool_resources = self._get_resources_by_type(ResourceType.TOOL)
        for name, info in tool_resources.items():
            if not await self._initialize_resource(name, info):
                success = False
        
        # 3. Инициализация навыков
        skill_resources = self._get_resources_by_type(ResourceType.SKILL)
        for name, info in skill_resources.items():
            if not await self._initialize_resource(name, info):
                success = False
        
        # 4. Инициализация прочих ресурсов
        all_resources = self.registry.all()
        other_resources = {}
        
        if isinstance(all_resources, list):
            for resource_info in all_resources:
                if (hasattr(resource_info, 'resource_type') and 
                    resource_info.resource_type not in [ResourceType.LLM_PROVIDER, ResourceType.TOOL, ResourceType.SKILL]):
                    other_resources[resource_info.name] = resource_info
        elif isinstance(all_resources, dict):
            other_resources = {name: info for name, info in all_resources.items() 
                            if info.resource_type not in [ResourceType.LLM_PROVIDER, ResourceType.TOOL, ResourceType.SKILL]}
        
        for name, info in other_resources.items():
            if not await self._initialize_resource(name, info):
                success = False
        
        if success:
            logger.info("Все ресурсы успешно инициализированы")
        else:
            logger.warning("Не все ресурсы были успешно инициализированы")
        
        return success
    
    async def shutdown(self) -> None:
        """
        Завершение работы всех ресурсов в обратном порядке.
        
        ПОРЯДОК:
        1. Прочие ресурсы
        2. Навыки
        3. Инструменты
        4. LLM провайдеры
        
        ОСОБЕННОСТИ:
        - Не генерирует исключения при ошибках завершения
        - Продолжает завершение остальных ресурсов даже при ошибках
        - Логирование процесса завершения
        """
        logger.info("Начало завершения работы системы...")
        
        # Получаем все ресурсы в обратном порядке инициализации
        all_resources = self.registry.all()
        all_resources.reverse()
        
        for info in all_resources:
            try:
                await self._shutdown_resource(info.name, info)
            except Exception as e:
                logger.warning(f"Ошибка завершения ресурса '{info.name}': {str(e)}")
        
        logger.info("Система корректно завершила работу")
    
    async def check_health(self) -> Dict[str, Any]:
        """
        Проверка здоровья системы.
        
        ВОЗВРАЩАЕТ:
        - Словарь с отчетом о состоянии системы:
            {
                "status": "healthy", "degraded" или "unhealthy",
                "timestamp": ISO timestamp,
                "resources": {
                    "resource_name": {
                        "type": "resource_type",
                        "health": "healthy", "degraded", "unhealthy" или "unknown",
                        "error_count": int
                    }
                }
            }
        
        ЛОГИКА:
        1. Проверка здоровья всех ресурсов
        2. Агрегация общего состояния системы
        3. Формирование отчета
        """
        from datetime import datetime
        
        health_report = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "resources": {}
        }
        
        for info in self.registry.all():
            resource_health = "unknown"
            
            if hasattr(info.instance, "health_check"):
                try:
                    health_info = await info.instance.health_check()
                    resource_health = health_info.get("status", "unknown")
                except Exception as e:
                    logger.error(f"Ошибка проверки здоровья ресурса {info.name}: {e}")
                    resource_health = "unhealthy"
            else:
                # Для ресурсов без метода health_check используем текущее состояние
                resource_health = info.health
            
            health_report["resources"][info.name] = {
                "type": info.resource_type.value,
                "health": resource_health,
                "error_count": info.error_count
            }
            
            # Обновление общего состояния системы
            if resource_health in ["unhealthy", "degraded"] and health_report["status"] == "healthy":
                health_report["status"] = resource_health
        
        return health_report
    
    def _get_resources_by_type(self, resource_type: ResourceType) -> Dict[str, ResourceInfo]:
        """
        Получение ресурсов заданного типа.
        
        ПАРАМЕТРЫ:
        - resource_type: Тип ресурсов для получения
        
        ВОЗВРАЩАЕТ:
        - Словарь {имя_ресурса: ResourceInfo} для ресурсов заданного типа
        """
        resources = {}
        all_resources = self.registry.all()
        
        # обработка как списка, так и словаря
        if isinstance(all_resources, dict):
            items = all_resources.items()
        elif isinstance(all_resources, list):
            items = [(res.name if hasattr(res, 'name') else str(i), res) 
                    for i, res in enumerate(all_resources)]
        else:
            items = []
            logger.warning(f"Неизвестный тип результата реестра: {type(all_resources)}")
        
        for name, info in items:
            if hasattr(info, 'resource_type') and info.resource_type == resource_type:
                resources[name] = info
            elif isinstance(info, dict) and info.get('resource_type') == resource_type:
                resources[name] = ResourceInfo(**info)
        
        return resources
        
    async def _initialize_resource(self, name: str, info: ResourceInfo) -> bool:
        """
        Инициализация отдельного ресурса.

        ПАРАМЕТРЫ:
        - name: Имя ресурса
        - info: Информация о ресурсе

        ВОЗВРАЩАЕТ:
        - True если ресурс успешно инициализирован
        - False если возникла ошибка инициализации

        ЛОГИКА:
        1. Вызов метода initialize() если он существует
        2. Обработка ошибок и обновление состояния здоровья
        3. Генерация события об успешной инициализации
        """
        try:
            instance = info.instance

            # Вызов метода initialize() если он существует
            if hasattr(instance, "initialize"):
                init_method = instance.initialize
                if asyncio.iscoroutinefunction(init_method):
                    await init_method()
                else:
                    init_method()

            # Регистрация capability для навыков - УДАЛЕНО: теперь делается через register_from_skill
            # УДАЛИТЬ: прямой вызов self.capabilities.register() больше не нужен
            # capability уже зарегистрированы через вызов registry.register_from_skill() 
            # при регистрации навыка

            info.health = "healthy"
            logger.info(f"Ресурс '{name}' успешно инициализирован")
            return True

        except Exception as e:
            logger.error(f"Ошибка инициализации ресурса '{name}': {str(e)}")
            info.health = "unhealthy"
            info.error_count += 1
            return False
    
    async def _shutdown_resource(self, name: str, info: ResourceInfo) -> None:
        """
        Завершение работы отдельного ресурса.
        
        ПАРАМЕТРЫ:
        - name: Имя ресурса
        - info: Информация о ресурсе
        
        ЛОГИКА:
        1. Вызов метода shutdown() если он существует
        2. Обработка ошибок
        3. Генерация события о завершении работы
        """
        instance = info.instance
        
        # Вызов метода shutdown() если он существует
        if hasattr(instance, "shutdown"):
            shutdown_method = instance.shutdown
            if asyncio.iscoroutinefunction(shutdown_method):
                await shutdown_method()
            else:
                shutdown_method()
        
        logger.debug(f"Ресурс '{name}' корректно завершил работу")