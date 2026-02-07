"""
SkillFactory - фабрика для создания навыков.
"""
from typing import Dict, Any, Type, List
from pathlib import Path
import importlib.util
import inspect

from domain.abstractions.base_skill import BaseSkill


class SkillFactory:
    """
    Фабрика для обнаружения и создания навыков.
    
    АРХИТЕКТУРА:
    - Расположение: инфраструктурный слой (фабрика)
    - Ответственность: создание экземпляров навыков на основе конфигурации
    - Принципы: соблюдение открытости/закрытости (O в SOLID)
    """
    
    def __init__(self):
        """Инициализация фабрики навыков."""
        self._skill_registry: Dict[str, Type[BaseSkill]] = {}
    
    def register_skill(self, skill_name: str, skill_class: Type[BaseSkill]):
        """
        Регистрация навыка в фабрике.
        
        Args:
            skill_name: Имя навыка
            skill_class: Класс навыка
        """
        self._skill_registry[skill_name] = skill_class
    
    def create_skill(self, skill_name: str, **kwargs) -> BaseSkill:
        """
        Создание экземпляра навыка.
        
        Args:
            skill_name: Имя навыка
            **kwargs: Аргументы для инициализации навыка
            
        Returns:
            BaseSkill: Экземпляр навыка
        """
        if skill_name not in self._skill_registry:
            raise ValueError(f"Неизвестный навык: {skill_name}")
        
        skill_class = self._skill_registry[skill_name]
        return skill_class(**kwargs)
    
    def discover_skills_in_directory(self, directory_path: str) -> List[str]:
        """
        Обнаружение навыков в указанной директории.
        
        Args:
            directory_path: Путь к директории с навыками
            
        Returns:
            List[str]: Список имен обнаруженных навыков
        """
        discovered_skills = []
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
                
                # Ищем классы, наследующие от BaseSkill
                for name, obj in inspect.getmembers(module, inspect.isclass):
                    if (obj != BaseSkill and  # Исключаем сам базовый класс
                        issubclass(obj, BaseSkill) and
                        obj.__module__ == module.__name__):  # Убедимся, что класс определен в этом модуле
                        
                        # Регистрируем навык с именем в формате module.class
                        skill_name = f"{module.__name__}.{name}"
                        self.register_skill(skill_name, obj)
                        discovered_skills.append(skill_name)
                        
            except Exception as e:
                # Игнорируем ошибки при импорте файлов
                pass  # В продвинутой версии можно добавить логирование через шину событий
        
        return discovered_skills
    
    def discover_skills_by_config(self, config: Dict[str, Any]) -> Dict[str, BaseSkill]:
        """
        Создание навыков на основе конфигурации.
        
        Args:
            config: Конфигурация навыков в формате {"skill_name": {"param": "value", ...}}
            
        Returns:
            Dict[str, BaseSkill]: Словарь созданных навыков
        """
        skills = {}
        
        for skill_name, skill_config in config.items():
            if isinstance(skill_config, dict):
                # Если конфигурация - словарь, используем его как параметры
                skill_instance = self.create_skill(skill_name, **skill_config)
            else:
                # Если конфигурация - не словарь, считаем его именем класса
                skill_instance = self.create_skill(skill_config)
            
            skills[skill_name] = skill_instance
        
        return skills
    
    def get_registered_skills(self) -> List[str]:
        """
        Получение списка зарегистрированных навыков.
        
        Returns:
            List[str]: Список имен зарегистрированных навыков
        """
        return list(self._skill_registry.keys())
    
    def skill_exists(self, skill_name: str) -> bool:
        """
        Проверка существования навыка.
        
        Args:
            skill_name: Имя навыка
            
        Returns:
            bool: True, если навык существует
        """
        return skill_name in self._skill_registry


# Глобальный экземпляр фабрики навыков
skill_factory = SkillFactory()


def get_skill_factory() -> SkillFactory:
    """
    Функция для получения экземпляра фабрики навыков.
    
    Returns:
        SkillFactory: Экземпляр фабрики навыков
    """
    return skill_factory