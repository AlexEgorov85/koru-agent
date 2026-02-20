"""
AnalysisCache — кэш результатов LLM анализа.

Используется для:
- Кэширования результатов анализа героев
- Кэширования анализа тем
- Кэширования классификации

TTL: 7 дней по умолчанию
"""

import json
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, Any


class AnalysisCache:
    """
    Кэш результатов анализа.
    
    Пример использования:
        cache = AnalysisCache("data/cache/book_analysis")
        await cache.set("character:book_1", result, ttl_hours=168)
        cached = await cache.get("character:book_1")
    """
    
    def __init__(self, storage_path: str = "data/cache/book_analysis"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
    
    async def get(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """
        Получение из кэша.
        
        Args:
            cache_key: Ключ кэша (например, "character_book_1")
        
        Returns:
            Данные из кэша или None
        """
        
        # Заменяем недопустимые символы для Windows
        safe_key = cache_key.replace(":", "_").replace("/", "_")
        file_path = self.storage_path / f"{safe_key}.json"
        
        if not file_path.exists():
            return None
        
        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
            
            # Проверка срока действия
            expires_at = datetime.fromisoformat(data["expires_at"])
            if expires_at < datetime.utcnow():
                # Просрочен — удаляем
                file_path.unlink(missing_ok=True)
                return None
            
            return data["value"]
        
        except (json.JSONDecodeError, KeyError, ValueError):
            # Повреждённый файл — удаляем
            file_path.unlink(missing_ok=True)
            return None
    
    async def set(
        self,
        cache_key: str,
        value: Dict[str, Any],
        ttl_hours: int = 168
    ):
        """
        Сохранение в кэш.
        
        Args:
            cache_key: Ключ кэша
            value: Данные для сохранения
            ttl_hours: Время жизни в часах (по умолчанию 168 = 7 дней)
        """
        
        # Заменяем недопустимые символы для Windows
        safe_key = cache_key.replace(":", "_").replace("/", "_")
        file_path = self.storage_path / f"{safe_key}.json"
        
        data = {
            "value": value,
            "cached_at": datetime.utcnow().isoformat(),
            "expires_at": (
                datetime.utcnow() + timedelta(hours=ttl_hours)
            ).isoformat()
        }
        
        # Атомарная запись (через temp файл)
        temp_path = file_path.with_suffix(".tmp")
        temp_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        temp_path.rename(file_path)
    
    async def delete(self, cache_key: str) -> bool:
        """
        Удаление из кэша.
        
        Args:
            cache_key: Ключ кэша
        
        Returns:
            True если удалено, False если не существовало
        """
        
        # Заменяем недопустимые символы для Windows
        safe_key = cache_key.replace(":", "_").replace("/", "_")
        file_path = self.storage_path / f"{safe_key}.json"
        
        if file_path.exists():
            file_path.unlink()
            return True
        
        return False
    
    async def invalidate_by_prefix(self, prefix: str) -> int:
        """
        Инвалидация по префиксу.
        
        Args:
            prefix: Префикс ключей (например, "character_")
        
        Returns:
            Количество удалённых записей
        """
        
        # Заменяем недопустимые символы для Windows
        safe_prefix = prefix.replace(":", "_").replace("/", "_")
        
        deleted = 0
        
        for file_path in self.storage_path.glob(f"{safe_prefix}*.json"):
            file_path.unlink()
            deleted += 1
        
        return deleted
    
    async def clear(self) -> int:
        """
        Очистка всего кэша.
        
        Returns:
            Количество удалённых записей
        """
        
        deleted = 0
        
        for file_path in self.storage_path.glob("*.json"):
            file_path.unlink()
            deleted += 1
        
        return deleted
    
    async def get_stats(self) -> Dict[str, Any]:
        """
        Статистика кэша.
        
        Returns:
            {"total_keys": int, "total_size_mb": float}
        """
        
        files = list(self.storage_path.glob("*.json"))
        
        total_size = sum(f.stat().st_size for f in files)
        
        return {
            "total_keys": len(files),
            "total_size_mb": total_size / (1024 * 1024)
        }
