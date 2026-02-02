"""Модель кодового элемента для тестов"""


class CodeUnit:
    """Представляет собой единицу кода (например, класс, функцию, модуль)"""
    
    def __init__(self, name: str, path: str, content: str, signatures: list = None):
        """
        Инициализирует кодовый элемент
        
        Args:
            name: Название элемента кода
            path: Путь к файлу с элементом
            content: Содержимое элемента кода
            signatures: Сигнатуры функций/методов в элементе
        """
        self.name = name
        self.path = path
        self.content = content
        self.signatures = signatures or []
    
    def __str__(self):
        """Строковое представление элемента кода"""
        return f"CodeUnit({self.name})"
    
    def __repr__(self):
        """Подробное строковое представление элемента кода"""
        return f"CodeUnit(name={self.name}, path={self.path})"
    
    def add_signature(self, signature: str):
        """
        Добавляет сигнатуру к элементу кода
        
        Args:
            signature: Новая сигнатура
        """
        self.signatures.append(signature)
    
    def get_signatures_count(self):
        """
        Возвращает количество сигнатур в элементе кода
        
        Returns:
            Число сигнатур
        """
        return len(self.signatures)