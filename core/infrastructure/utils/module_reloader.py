"""
Модуль для перезапуска компонентов с перезагрузкой модулей Python.
ВНИМАНИЕ: Использовать с осторожностью, так как перезагрузка модулей может привести к непредсказуемому поведению.
"""
import importlib
import logging
import sys
from typing import Type, Any

logger = logging.getLogger(__name__)


class ModuleReloader:
    """
    Класс для перезапуска компонентов с перезагрузкой модулей Python.
    
    ВАЖНО: Перезагрузка модулей во время работы приложения может привести к:
    - Потере состояния объектов
    - Нарушению ссылочной целостности
    - Непредсказуемому поведению других компонентов
    - Утечке памяти
    
    ИСПОЛЬЗОВАТЬ ТОЛЬКО В ОСОБЫХ СЛУЧАЯХ И С ОСТОРОЖНОСТЬЮ!
    """
    
    @staticmethod
    def reload_module_for_component(component_instance: Any) -> Any:
        """
        Перезагружает модуль, в котором определен класс компонента, и создает новый экземпляр.
        
        ПАРАМЕТРЫ:
        - component_instance: текущий экземпляр компонента
        
        ВОЗВРАЩАЕТ:
        - Новый экземпляр компонента из перезагруженного модуля
        """
        try:
            # Получаем класс компонента
            component_class = component_instance.__class__
            
            # Получаем имя модуля
            module_name = component_class.__module__
            
            logger.warning(f"Попытка перезагрузки модуля {module_name} для компонента {component_class.__name__}")
            
            # Получаем модуль
            module = sys.modules.get(module_name)
            if not module:
                raise ValueError(f"Модуль {module_name} не найден в sys.modules")
            
            # Перезагружаем модуль
            importlib.reload(module)
            
            # Находим класс в перезагруженном модуле
            reloaded_class = getattr(module, component_class.__name__)
            
            # Создаем новый экземпляр класса
            # Для этого нам нужно получить аргументы, которые были использованы при создании оригинального экземпляра
            # Это может быть сложно, если конструктор принимает много параметров
            # В простом случае мы можем попытаться использовать атрибуты экземпляра для воссоздания
            
            # Попробуем создать новый экземпляр с теми же параметрами, что и оригинальный
            # Это работает только если у компонента есть атрибуты, которые можно использовать для воссоздания
            constructor_args = ModuleReloader._get_constructor_args(component_instance)
            
            new_instance = reloaded_class(**constructor_args)
            
            logger.info(f"Модуль {module_name} успешно перезагружен, создан новый экземпляр {reloaded_class.__name__}")
            
            return new_instance
            
        except Exception as e:
            logger.error(f"Ошибка перезагрузки модуля для компонента {component_instance.__class__.__name__}: {str(e)}")
            raise
    
    @staticmethod
    def _get_constructor_args(instance: Any) -> dict:
        """
        Пытается получить аргументы, которые были использованы при создании экземпляра.
        Это упрощенная реализация, которая может не работать для всех случаев.
        """
        args = {}
        
        # Попробуем получить часто используемые атрибуты
        if hasattr(instance, 'system_context'):
            args['system_context'] = instance.system_context
        if hasattr(instance, 'name'):
            args['name'] = instance.name
            
        # Добавим другие атрибуты, которые могут быть важны для конструктора
        # Это сильно зависит от конкретного класса
        
        return args


def safe_reload_component_with_module_reload(component_instance: Any) -> Any:
    """
    Безопасная перезагрузка компонента с перезагрузкой модуля.
    Возвращает новый экземпляр или оригинальный в случае ошибки.
    """
    try:
        return ModuleReloader.reload_module_for_component(component_instance)
    except Exception as e:
        logger.error(f"Безопасная перезагрузка модуля не удалась, возвращаем оригинальный экземпляр: {str(e)}")
        return component_instance