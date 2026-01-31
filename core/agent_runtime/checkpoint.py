"""Система чекпоинтов для сохранения состояния агента."""
import pickle
import json
import hashlib
from datetime import datetime
from typing import Any, Dict, Optional
from pathlib import Path


class CheckpointManager:
    """
    CheckpointManager - менеджер чекпоинтов для сохранения и восстановления состояния.
    
    НАЗНАЧЕНИЕ:
    - Обеспечивает сохранение состояния агента в файлы
    - Позволяет восстанавливать состояние агента из файлов
    - Обеспечивает управление сохраненными чекпоинтами
    
    ВОЗМОЖНОСТИ:
    - Сохранение произвольных объектов в чекпоинты
    - Автоматическая генерация имен чекпоинтов
    - Создание метаданных для каждого чекпоинта
    - Список и удаление существующих чекпоинтов
    - Загрузка объектов из чекпоинтов
    
    ПРИМЕРЫ РАБОТЫ:
    # Создание менеджера чекпоинтов
    manager = CheckpointManager("./my_checkpoints")
    
    # Сохранение чекпоинта
    checkpoint_name = manager.save_checkpoint(my_object, "my_checkpoint")
    
    # Загрузка чекпоинта
    restored_object = manager.load_checkpoint("my_checkpoint")
    
    # Получение списка чекпоинтов
    checkpoints = manager.list_checkpoints()
    
    # Удаление чекпоинта
    manager.delete_checkpoint("my_checkpoint")
    """
    
    def __init__(self, checkpoint_dir: str = "./checkpoints"):
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(exist_ok=True)
    
    def save_checkpoint(self, obj: Any, name: str = None) -> str:
        """Сохранить чекпоинт объекта.
        
        Args:
            obj: Объект для сохранения
            name: Имя чекпоинта (если не указано, генерируется автоматически)
            
        Returns:
            str: Имя созданного чекпоинта
        """
        if name is None:
            # Генерируем имя на основе хэша объекта и времени
            obj_hash = hashlib.md5(pickle.dumps(obj)).hexdigest()[:8]
            name = f"checkpoint_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{obj_hash}"
        
        # Сохраняем в формате pickle для полного сохранения состояния
        checkpoint_path = self.checkpoint_dir / f"{name}.pkl"
        
        with open(checkpoint_path, 'wb') as f:
            pickle.dump(obj, f)
        
        # Также создаем метаданные
        metadata = {
            "name": name,
            "timestamp": datetime.now().isoformat(),
            "size": checkpoint_path.stat().st_size
        }
        
        metadata_path = self.checkpoint_dir / f"{name}_metadata.json"
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        
        return name
    
    def load_checkpoint(self, name: str) -> Any:
        """Загрузить чекпоинт по имени.
        
        Args:
            name: Имя чекпоинта
            
        Returns:
            Any: Восстановленный объект
        """
        checkpoint_path = self.checkpoint_dir / f"{name}.pkl"
        
        if not checkpoint_path.exists():
            raise FileNotFoundError(f"Checkpoint {name} не найден")
        
        with open(checkpoint_path, 'rb') as f:
            obj = pickle.load(f)
        
        return obj
    
    def list_checkpoints(self) -> Dict[str, Dict[str, Any]]:
        """Получить список всех чекпоинтов.
        
        Returns:
            Dict: Словарь с информацией о чекпоинтах
        """
        checkpoints = {}
        
        for meta_file in self.checkpoint_dir.glob("*_metadata.json"):
            with open(meta_file, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
                checkpoints[metadata['name']] = metadata
        
        return checkpoints
    
    def delete_checkpoint(self, name: str):
        """Удалить чекпоинт.
        
        Args:
            name: Имя чекпоинта для удаления
        """
        checkpoint_path = self.checkpoint_dir / f"{name}.pkl"
        metadata_path = self.checkpoint_dir / f"{name}_metadata.json"
        
        if checkpoint_path.exists():
            checkpoint_path.unlink()
        
        if metadata_path.exists():
            metadata_path.unlink()


# Убираем SerializableMixin из этого файла, так как он создает проблемы с сериализацией
# и не используется в текущей реализации
# class SerializableMixin:
#     """Примесь для добавления функциональности сериализации к классу."""
#     
#     def serialize(self) -> bytes:
#         """Сериализовать объект в байты."""
#         return pickle.dumps(self)
#     
#     @classmethod
#     def deserialize(cls, data: bytes) -> 'SerializableMixin':
#         """Десериализовать объект из байт."""
#         obj = pickle.loads(data)
#         # Проверяем, что десериализованный объект является экземпляром нужного класса
#         if not isinstance(obj, cls):
#             raise TypeError(f"Deserialized object is not of type {cls.__name__}")
#         return obj
