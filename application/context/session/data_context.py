"""
Контекст первого уровня (DataContext).
НАЗНАЧЕНИЕ:
- Хранение всех сырых данных сессии
- Append-only модель данных
- Быстрый доступ к элементам по ID
ОСОБЕННОСТИ:
- Никогда не передается напрямую в LLM
- Содержит все данные включая чувствительные
- Полностью изолирован от инфраструктуры
АРХИТЕКТУРНЫЕ ПРИНЦИПЫ:
1. Append-only: данные только добавляются, не изменяются
2. Идемпотентность: повторное добавление одинаковых данных безопасно
3. Быстрый доступ: O(1) для получения элементов по ID
4. Изоляция: не зависит от внешних систем
"""
from typing import Dict, List
import random
import string
from datetime import datetime

from application.context.session.models import ContextItem, ContextItemType


class DataContext:
    """
    Контекст первого уровня для хранения сырых данных.
    
    СВОЙСТВА:
    - Append-only: данные только добавляются
    - Быстрый доступ по ID
    - Полная изоляция от инфраструктуры
    - Поддержка различных типов контента
    
    СТРУКТУРА:
    - items: Словарь {item_id: ContextItem}
    - item_counter: Счетчик для генерации ID
    """
    
    def __init__(self):
        """Инициализация пустого контекста."""
        self.items: Dict[str, ContextItem] = {}
        self.item_counter = 0
    
    def add_item(self, item: ContextItem) -> str:
        """
        Добавление элемента в контекст.
        
        ПАРАМЕТРЫ:
        - item: Элемент контекста для добавления
        
        ВОЗВРАЩАЕТ:
        - item_id: Уникальный идентификатор элемента
        
        БИЗНЕС-ЛОГИКА:
        - Если item_id уже существует, элемент перезаписывается
        - Если item_id не указан, генерируется автоматически
        - Генерируем ID в формате 'ctx_{counter:06d}_{random8}'
        """
        if not item.item_id or item.item_id == "":
            self.item_counter += 1
            # Генерируем случайную строку из 8 символов
            random_part = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
            item_id = f"ctx_{self.item_counter:06d}_{random_part}"
            
            # Обновляем item с новым ID, создав новый экземпляр
            item = item.model_copy(update={"item_id": item_id, "updated_at": datetime.now()})
        else:
            item_id = item.item_id
        
        self.items[item_id] = item
        return item_id
    
    def get_item(self, item_id: str) -> ContextItem:
        """
        Получение элемента по идентификатору.
        
        ПАРАМЕТРЫ:
        - item_id: Уникальный идентификатор элемента
        
        ВОЗВРАЩАЕТ:
        - ContextItem: Запрошенный элемент или None если не найден
        
        ПРОИЗВОДИТЕЛЬНОСТЬ:
        - O(1) благодаря использованию словаря
        """
        return self.items.get(item_id)
    
    def item_exists(self, item_id: str) -> bool:
        """
        Проверка существования элемента в контексте.
        
        ПАРАМЕТРЫ:
        - item_id: Уникальный идентификатор элемента
        
        ВОЗВРАЩАЕТ:
        - True если элемент существует
        - False если элемент не существует
        """
        return item_id in self.items
    
    def count(self) -> int:
        """
        Получение количества элементов в контексте.
        
        ВОЗВРАЩАЕТ:
        - Количество элементов
        
        ИСПОЛЬЗОВАНИЕ:
        - Мониторинг размера контекста
        - Ограничение ресурсов
        - Статистика использования
        """
        return len(self.items)
    
    def get_all_items(self) -> List[ContextItem]:
        """
        Получение всех элементов контекста.
        
        ВОЗВРАЩАЕТ:
        - Список всех элементов, отсортированных по времени создания (от старых к новым)
        
        ЗАМЕЧАНИЕ:
        - Возвращается копия списка для безопасности
        - Порядок элементов по времени создания
        """
        # Сортируем элементы по времени создания (от старых к новым)
        sorted_items = sorted(self.items.values(), key=lambda x: x.created_at)
        return sorted_items
    
    def get_last_items(self, count: int) -> List[ContextItem]:
        """
        Получение последних N элементов контекста.
        
        ПАРАМЕТРЫ:
        - count: Количество элементов для получения
        
        ВОЗВРАЩАЕТ:
        - Список последних элементов в порядке добавления (новые в конце)
        """
        if count <= 0:
            return []
        
        # Сортируем элементы по времени создания (от старых к новым)
        sorted_items = sorted(self.items.values(), key=lambda x: x.created_at)
        
        # Возвращаем последние count элементов
        return sorted_items[-count:] if len(sorted_items) >= count else sorted_items
    
    def get_items_by_type(self, item_type: ContextItemType) -> List[ContextItem]:
        """
        Получение элементов по типу.
        
        ПАРАМЕТРЫ:
        - item_type: Тип элементов для фильтрации
        
        ВОЗВРАЩАЕТ:
        - Список элементов указанного типа, отсортированных по времени создания
        """
        filtered_items = [item for item in self.items.values() if item.item_type == item_type]
        # Сортируем по времени создания (от старых к новым)
        filtered_items.sort(key=lambda x: x.created_at)
        return filtered_items
    
    def get_items_by_step(self, step_number: int) -> List[ContextItem]:
        """
        Получение элементов по номеру шага.
        
        ПАРАМЕТРЫ:
        - step_number: Номер шага для фильтрации
        
        ВОЗВРАЩАЕТ:
        - Список элементов с указанным номером шага, отсортированных по времени создания
        """
        filtered_items = [
            item for item in self.items.values() 
            if item.metadata and item.metadata.step_number == step_number
        ]
        # Сортируем по времени создания (от старых к новым)
        filtered_items.sort(key=lambda x: x.created_at)
        return filtered_items
    
    def update_item(self, item_id: str, **kwargs) -> bool:
        """
        Обновление элемента по ID.
        
        ПАРАМЕТРЫ:
        - item_id: ID элемента для обновления
        - **kwargs: Поля для обновления
        
        ВОЗВРАЩАЕТ:
        - True если элемент успешно обновлен
        - False если элемент не найден
        """
        if item_id not in self.items:
            return False
        
        # Получаем существующий элемент
        existing_item = self.items[item_id]
        
        # Подготовливаем обновленные данные
        update_data = {k: v for k, v in kwargs.items() if v is not None}
        update_data['updated_at'] = datetime.now()
        
        # Создаем новый экземпляр с обновленными данными
        updated_item = existing_item.model_copy(update=update_data)
        
        # Сохраняем обновленный элемент
        self.items[item_id] = updated_item
        
        return True
    
    def clear(self):
        """
        Очистка всех элементов из контекста и сброс счетчика.
        """
        self.items.clear()
        self.item_counter = 0