"""
Реализация хранилища стратегий.

АРХИТЕКТУРНЫЕ ГАРАНТИИ:
- Полная реализация интерфейса IStrategyStorage
- Асинхронные операции для масштабируемости
- Локальное хранение данных стратегий
- Обработка ошибок и логирование
"""
import json
import os
from typing import Dict, Any, Optional, List
from pathlib import Path
import asyncio
import logging

from core.components.strategy.i_strategy_storage import IStrategyStorage


class StrategyStorage(IStrategyStorage):
    """
    Реализация хранилища стратегий с локальным файловым хранилищем.
    
    Attributes:
        storage_path: Путь к директории хранения стратегий
        strategies: Кэш загруженных стратегий
    """
    
    def __init__(self, storage_path: Optional[str] = None):
        """
        Инициализирует хранилище стратегий.
        
        Args:
            storage_path: Путь к директории хранения стратегий (по умолчанию './strategies')
        """
        self.storage_path = Path(storage_path or "./strategies")
        self.strategies: Dict[str, Dict[str, Any]] = {}
        
        # Создаем директорию если она не существует
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        # Настройка логгера
        self.logger = logging.getLogger(__name__)
    
    async def save_strategy(self, strategy_id: str, strategy_data: Dict[str, Any]) -> bool:
        """
        Сохраняет стратегию в файловое хранилище.
        
        Args:
            strategy_id: Уникальный идентификатор стратегии
            strategy_data: Данные стратегии в формате словаря
            
        Returns:
            bool: True если сохранение прошло успешно, иначе False
        """
        try:
            # Формируем путь к файлу стратегии
            file_path = self.storage_path / f"{strategy_id}.json"
            
            # Записываем данные стратегии в файл
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(strategy_data, f, ensure_ascii=False, indent=2)
            
            # Обновляем кэш
            self.strategies[strategy_id] = strategy_data
            
            self.logger.info(f"Стратегия '{strategy_id}' успешно сохранена")
            return True
            
        except Exception as e:
            self.logger.error(f"Ошибка при сохранении стратегии '{strategy_id}': {e}")
            return False
    
    async def load_strategy(self, strategy_id: str) -> Optional[Dict[str, Any]]:
        """
        Загружает стратегию из файлового хранилища по ID.
        
        Args:
            strategy_id: Уникальный идентификатор стратегии
            
        Returns:
            Optional[Dict[str, Any]]: Данные стратегии или None если не найдена
        """
        try:
            # Проверяем кэш первым
            if strategy_id in self.strategies:
                return self.strategies[strategy_id]
            
            # Формируем путь к файлу стратегии
            file_path = self.storage_path / f"{strategy_id}.json"
            
            # Проверяем существование файла
            if not file_path.exists():
                self.logger.warning(f"Файл стратегии '{file_path}' не найден")
                return None
            
            # Читаем данные стратегии из файла
            with open(file_path, 'r', encoding='utf-8') as f:
                strategy_data = json.load(f)
            
            # Кэшируем данные
            self.strategies[strategy_id] = strategy_data
            
            self.logger.info(f"Стратегия '{strategy_id}' успешно загружена")
            return strategy_data
            
        except Exception as e:
            self.logger.error(f"Ошибка при загрузке стратегии '{strategy_id}': {e}")
            return None
    
    async def delete_strategy(self, strategy_id: str) -> bool:
        """
        Удаляет стратегию из файлового хранилища по ID.
        
        Args:
            strategy_id: Уникальный идентификатор стратегии
            
        Returns:
            bool: True если удаление прошло успешно, иначе False
        """
        try:
            # Формируем путь к файлу стратегии
            file_path = self.storage_path / f"{strategy_id}.json"
            
            # Проверяем существование файла
            if not file_path.exists():
                self.logger.warning(f"Файл стратегии '{file_path}' не найден для удаления")
                return False
            
            # Удаляем файл
            file_path.unlink()
            
            # Удаляем из кэша
            if strategy_id in self.strategies:
                del self.strategies[strategy_id]
            
            self.logger.info(f"Стратегия '{strategy_id}' успешно удалена")
            return True
            
        except Exception as e:
            self.logger.error(f"Ошибка при удалении стратегии '{strategy_id}': {e}")
            return False
    
    async def list_strategies(self) -> List[str]:
        """
        Возвращает список идентификаторов всех доступных стратегий.
        
        Returns:
            List[str]: Список ID стратегий
        """
        try:
            # Получаем все JSON файлы в директории
            strategy_files = list(self.storage_path.glob("*.json"))
            
            # Извлекаем имена стратегий из имен файлов
            strategy_ids = [f.stem for f in strategy_files]
            
            self.logger.info(f"Найдено {len(strategy_ids)} стратегий")
            return strategy_ids
            
        except Exception as e:
            self.logger.error(f"Ошибка при получении списка стратегий: {e}")
            return []
    
    async def update_strategy(self, strategy_id: str, strategy_data: Dict[str, Any]) -> bool:
        """
        Обновляет существующую стратегию в хранилище.
        
        Args:
            strategy_id: Уникальный идентификатор стратегии
            strategy_data: Новые данные стратегии
            
        Returns:
            bool: True если обновление прошло успешно, иначе False
        """
        # Для этой реализации обновление идентично сохранению
        return await self.save_strategy(strategy_id, strategy_data)