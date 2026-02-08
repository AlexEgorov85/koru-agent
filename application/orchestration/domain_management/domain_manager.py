"""
Менеджер доменов для адаптации агента к различным областям задач.
"""
from typing import Dict, List, Optional


class DomainManager:
    """
    Менеджер доменов для адаптации агента к различным областям задач.
    
    ОТВЕТСТВЕННОСТЬ:
    - Определение домена задачи по описанию
    - Адаптация агента к домену
    - Управление паттернами для различных доменов
    """
    
    def __init__(self):
        # Определяем ключевые слова для каждого домена
        self.domain_keywords = {
            'code_analysis': [
                'код', 'анализ', 'файл', 'структура', 'зависимость', 'импорт',
                'класс', 'функция', 'метод', 'переменная', 'модуль', 'пакет',
                'рефакторинг', 'баг', 'ошибка', 'дебаг', 'дебаг', 'отладка'
            ],
            'sql_generation': [
                'sql', 'запрос', 'база данных', 'таблица', 'select', 'insert',
                'join', 'update', 'delete', 'where', 'from', 'create', 'schema'
            ],
            'testing': [
                'тест', 'покрытие', 'валидация', 'юнит-тест', 'тестирование',
                'unittest', 'pytest', 'assert', 'проверка', 'валидация'
            ],
            'documentation': [
                'документация', 'док', 'описание', 'комментарий', 'документирование',
                'docstring', 'readme', 'specification', 'спецификация'
            ],
            'research': [
                'исследование', 'поиск', 'найти', 'информация', 'источник',
                'данные', 'анализ', 'статистика', 'исследовательский'
            ]
        }
    
    def adapt_to_task(self, task_description: str) -> str:
        """
        Адаптация к домену на основе описания задачи.
        
        ПАРАМЕТРЫ:
        - task_description: Описание задачи
        
        ВОЗВРАЩАЕТ:
        - Название домена
        """
        task_lower = task_description.lower().strip()
        detected_domain = 'general'
        
        # Проверяем каждый домен на наличие ключевых слов
        for domain, keywords in self.domain_keywords.items():
            if any(keyword in task_lower for keyword in keywords):
                detected_domain = domain
                break
        
        return detected_domain
    
    def get_domain_pattern(self, domain: str) -> str:
        """
        Получение рекомендуемого паттерна для домена.
        
        ПАРАМЕТРЫ:
        - domain: Название домена
        
        ВОЗВРАЩАЕТ:
        - Название рекомендуемого паттерна
        """
        domain_patterns = {
            'code_analysis': 'code_analysis',
            'sql_generation': 'sql_generation',
            'testing': 'testing',
            'documentation': 'documentation',
            'research': 'research'
        }
        
        return domain_patterns.get(domain, 'general')
    
    def set_current_domain(self, domain: str):
        """
        Установка текущего домена.
        
        ПАРАМЕТРЫ:
        - domain: Название домена
        """
        # В этой реализации просто проверяем, что домен поддерживается
        if domain not in self.domain_keywords:
            raise ValueError(f"Unsupported domain: {domain}")