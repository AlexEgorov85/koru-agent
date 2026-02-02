"""
ToolFactory - фабрика для создания инструментов.
"""
from typing import Dict, Any, Type, List
from pathlib import Path
import importlib.util
import inspect

from domain.abstractions.tools.base_tool import BaseTool


class ToolFactory:
    """
    Фабрика для обнаружения и создания инструментов.
    
    АРХИТЕКТУРА:
    - Расположение: инфраструктурный слой (фабрика)
    - Ответственность: создание экземпляров инструментов на основе конфигурации
    - Принципы: соблюдение открытости/закрытости (O в SOLID)
    """
    
    def __init__(self):
        """Инициализация фабрики инструментов."""
        self._tool_registry: Dict[str, Type[BaseTool]] = {}
    
    def register_tool(self, tool_name: str, tool_class: Type[BaseTool]):
        """
        Регистрация инструмента в фабрике.
        
        Args:
            tool_name: Имя инструмента
            tool_class: Класс инструмента
        """
        self._tool_registry[tool_name] = tool_class
    
    def create_tool(self, tool_name: str, **kwargs) -> BaseTool:
        """
        Создание экземпляра инструмента.
        
        Args:
            tool_name: Имя инструмента
            **kwargs: Аргументы для инициализации инструмента
            
        Returns:
            BaseTool: Экземпляр инструмента
        """
        if tool_name not in self._tool_registry:
            raise ValueError(f"Неизвестный инструмент: {tool_name}")
        
        tool_class = self._tool_registry[tool_name]
        return tool_class(**kwargs)
    
    def discover_tools_in_directory(self, directory_path: str) -> List[str]:
        """
        Обнаружение инструментов в указанной директории.
        
        Args:
            directory_path: Путь к директории с инструментами
            
        Returns:
            List[str]: Список имен обнаруженных инструментов
        """
        discovered_tools = []
        directory = Path(directory_path)
        
        # Проходим по всем файлам в директории
        for file_path in directory.rglob("*.py"):
            if file_path.name.startswith("__"):
                continue  # Пропускаем специальные файлы
            
            try:
                # Загружаем модуль
                spec = importlib.util.spec_from_file_location(file_path.stem, file_path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                
                # Ищем классы, наследующие от BaseTool
                for name, obj in inspect.getmembers(module, inspect.isclass):
                    if (obj != BaseTool and  # Исключаем сам базовый класс
                        issubclass(obj, BaseTool) and
                        obj.__module__ == module.__name__):  # Убедимся, что класс определен в этом модуле
                        
                        # Регистрируем инструмент с именем в формате module.class
                        tool_name = f"{module.__name__}.{name}"
                        self.register_tool(tool_name, obj)
                        discovered_tools.append(tool_name)
                        
            except Exception as e:
                # Игнорируем ошибки при импорте файлов
                pass  # В продвинутой версии можно добавить логирование через шину событий
        
        return discovered_tools
    
    def discover_tools_by_config(self, config: Dict[str, Any]) -> Dict[str, BaseTool]:
        """
        Создание инструментов на основе конфигурации.
        
        Args:
            config: Конфигурация инструментов в формате {"tool_name": {"param": "value", ...}}
            
        Returns:
            Dict[str, BaseTool]: Словарь созданных инструментов
        """
        tools = {}
        
        for tool_name, tool_config in config.items():
            if isinstance(tool_config, dict):
                # Если конфигурация - словарь, используем его как параметры
                tool_instance = self.create_tool(tool_name, **tool_config)
            else:
                # Если конфигурация - не словарь, считаем его именем класса
                tool_instance = self.create_tool(tool_config)
            
            tools[tool_name] = tool_instance
        
        return tools
    
    def get_registered_tools(self) -> List[str]:
        """
        Получение списка зарегистрированных инструментов.
        
        Returns:
            List[str]: Список имен зарегистрированных инструментов
        """
        return list(self._tool_registry.keys())
    
    def tool_exists(self, tool_name: str) -> bool:
        """
        Проверка существования инструмента.
        
        Args:
            tool_name: Имя инструмента
            
        Returns:
            bool: True, если инструмент существует
        """
        return tool_name in self._tool_registry


# Глобальный экземпляр фабрики инструментов
tool_factory = ToolFactory()


def get_tool_factory() -> ToolFactory:
    """
    Функция для получения экземпляра фабрики инструментов.
    
    Returns:
        ToolFactory: Экземпляр фабрики инструментов
    """
    return tool_factory