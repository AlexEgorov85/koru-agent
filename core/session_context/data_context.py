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

from core.session_context.model import ContextItem

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
    - item_counter: Счетчик для генерации ID (для тестов)
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
        - Append-only семантика гарантируется на уровне приложения
        """
        if not item.item_id:
            self.item_counter += 1
            item.item_id = f"auto_{self.item_counter}"
        
        self.items[item.item_id] = item
        return item.item_id
    
    def get_item(self, item_id: str, raise_on_missing: bool = True) -> ContextItem:
        """
        Получение элемента по идентификатору.

        ПАРАМЕТРЫ:
        - item_id: Уникальный идентификатор элемента
        - raise_on_missing: Если True, выбрасывает KeyError при отсутствии элемента;
                           если False, возвращает None

        ВОЗВРАЩАЕТ:
        - ContextItem: Запрошенный элемент или None если элемент не найден и raise_on_missing=False

        ВЫБРАСЫВАЕТ:
        - KeyError если элемент не найден и raise_on_missing=True

        ПРОИЗВОДИТЕЛЬНОСТЬ:
        - O(1) благодаря использованию словаря
        """
        if item_id not in self.items:
            if raise_on_missing:
                raise KeyError(f"Элемент контекста не найден: {item_id}")
            else:
                return None
        return self.items[item_id]
    
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
        - Список всех элементов
        
        ЗАМЕЧАНИЕ:
        - Возвращается копия списка для безопасности
        - Порядок элементов не гарантируется
        """
        return list(self.items.values())
    
    def get_last_item_id(self) -> str:
        """Возвращает ID последнего добавленного элемента"""
        if not self.items:
            return None
        return list(self.items.keys())[-1]