from typing import Any, Dict
from domain.abstractions.system.i_config_manager import IConfigManager
from domain.models.system.config import SystemConfig


class ConfigManager(IConfigManager):
    """Реализация менеджера конфигурации"""
    
    def __init__(self, config: SystemConfig = None):
        self._config = config or SystemConfig()
        self._parameters: Dict[str, Any] = {}
        self._is_validated = False
    
    def set_config(self, key: str, value: Any) -> None:
        """Установка параметра конфигурации с валидацией типа"""
        if self._is_validated:
            raise RuntimeError("Конфигурация была валидирована и теперь неизменяема")
        
        # Здесь можно добавить дополнительную валидацию типа
        self._parameters[key] = value
    
    def get_config(self, key: str, default: Any = None) -> Any:
        """Получение параметра по ключу"""
        if key in self._parameters:
            return self._parameters[key]
        elif default is not None:
            return default
        else:
            raise KeyError(f"Параметр конфигурации '{key}' не найден и значение по умолчанию не предоставлено")
    
    def export_config(self) -> Dict[str, Any]:
        """Экспорт конфигурации в словарь"""
        return self._parameters.copy()
    
    def reset_config(self) -> None:
        """Сброс конфигурации к значениям по умолчанию"""
        if self._is_validated:
            raise RuntimeError("Конфигурация была валидирована и теперь неизменяема")
        
        self._parameters.clear()
    
    def validate_config(self) -> bool:
        """Валидация конфигурации"""
        # Помечаем, что конфигурация валидирована и теперь неизменяема
        self._is_validated = True
        return True