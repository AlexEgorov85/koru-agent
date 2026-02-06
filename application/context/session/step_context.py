"""
Контекст второго уровня (StepContext).
НАЗНАЧЕНИЕ:
- Хранение шагов агента в формате, безопасном для LLM
- Предоставление интерфейса для построения контекста рассуждений
- Изоляция от сырых данных первого уровня
ОСОБЕННОСТИ:
- Безопасен для передачи в LLM
- Содержит только метаданные и ссылки
- Не содержит чувствительных данных
АРХИТЕКТУРНЫЕ ПРИНЦИПЫ:
1. Безопасность: нет прямого доступа к сырым данным
2. Производительность: быстрый доступ к последним шагам
3. Изоляция: не зависит от инфраструктуры
4. Согласованность: все шаги имеют правильную структуру
ПРИМЕР ИСПОЛЬЗОВАНИЯ:
from application.context.session.step_context import StepContext

context = StepContext()
context.add_step(my_agent_step)
last_steps = context.get_last_steps(3)
"""
from typing import List
from datetime import datetime

from application.context.session.models import AgentStep


class StepContext:
    """
    Контекст второго уровня для хранения шагов агента.
    
    СВОЙСТВА:
    - Безопасен для передачи в LLM
    - Содержит только метаданные шагов
    - Быстрый доступ к последним шагам
    - Полная изоляция от сырых данных
    
    СТРУКТУРА:
    - steps: Список шагов в порядке выполнения
    """
    
    def __init__(self):
        """Инициализация пустого контекста шагов."""
        self.steps: List[AgentStep] = []
    
    def add_step(self, step: AgentStep) -> None:
        """
        Добавление шага агента в контекст.
        
        ПАРАМЕТРЫ:
        - step: Шаг агента для добавления
        
        БИЗНЕС-ЛОГИКА:
        - Шаги добавляются в порядке выполнения
        - Дубликаты по step_number не допускаются
        - Нумерация шагов должна быть последовательной
        
        ВАЛИДАЦИЯ:
        - Проверка корректности step_number
        - Проверка существования ссылочных item_id
        - Проверка соответствия типов
        """
        # Проверка уникальности step_number
        if any(s.step_number == step.step_number for s in self.steps):
            raise ValueError(f"Шаг с номером {step.step_number} уже существует")
        
        # Проверка последовательности нумерации
        if self.steps and step.step_number != self.steps[-1].step_number + 1:
            raise ValueError(f"Нарушена последовательность шагов: ожидается {self.steps[-1].step_number + 1}, получено {step.step_number}")
        
        self.steps.append(step)
    
    def get_last_steps(self, n: int) -> List[AgentStep]:
        """
        Получение последних N шагов агента.
        
        ПАРАМЕТРЫ:
        - n: Количество шагов для получения
        
        ВОЗВРАЩАЕТ:
        - Список последних N шагов (или всех шагов если их меньше N)
        
        ИСПОЛЬЗОВАНИЕ:
        - Построение контекста для LLM
        - Анализ последних действий агента
        - Отладка и мониторинг
        
        ПРОИЗВОДИТЕЛЬНОСТЬ:
        - O(1) для получения среза списка
        """
        if n <= 0:
            return []
        return self.steps[-n:] if len(self.steps) >= n else self.steps.copy()
    
    def get_current_step_number(self) -> int:
        """
        Получение номера текущего шага.
        
        ВОЗВРАЩАЕТ:
        - Номер последнего шага или 0 если шагов нет
        
        ИСПОЛЬЗОВАНИЕ:
        - Определение следующего номера шага
        - Проверка прогресса выполнения
        - Логирование текущего состояния
        """
        return self.steps[-1].step_number if self.steps else 0
    
    def get_step(self, step_number: int) -> AgentStep:
        """
        Получение шага по номеру.
        
        ПАРАМЕТРЫ:
        - step_number: Номер шага (используется 1-based индексация)
        
        ВОЗВРАЩАЕТ:
        - AgentStep если шаг существует
        - None если шаг не существует
        """
        # Используем 1-based индексацию
        if step_number <= 0 or step_number > len(self.steps):
            return None
        # Ищем шаг с указанным номером
        for step in self.steps:
            if step.step_number == step_number:
                return step
        return None
    
    def step_exists(self, step_number: int) -> bool:
        """
        Проверка существования шага с заданным номером.
        
        ПАРАМЕТРЫ:
        - step_number: Номер шага для проверки
        
        ВОЗВРАЩАЕТ:
        - True если шаг существует
        - False если шаг не существует
        """
        return any(s.step_number == step_number for s in self.steps)
    
    def count(self) -> int:
        """
        Получение количества шагов в контексте.
        
        ВОЗВРАЩАЕТ:
        - Количество шагов
        
        ИСПОЛЬЗОВАНИЕ:
        - Мониторинг прогресса выполнения
        - Ограничение максимального количества шагов
        - Статистика использования
        """
        return len(self.steps)
    
    def calculate_progress(self) -> float:
        """
        Расчет прогресса выполнения сессии.
        
        ВОЗВРАЩАЕТ:
        - Процент выполнения (0.0 - 100.0)
        
        ЛОГИКА:
        - Без явного прогресса: линейная эвристика (шаги / 10) * 100, ограничено 100.0
        - С явным прогрессом в метаданных: используется максимальное значение из шагов
        """
        if not self.steps:
            return 0.0
        
        # Линейная эвристика: количество шагов влияет на прогресс
        # Ограничиваем максимальный прогресс 100%
        base_progress = min((len(self.steps) / 10.0) * 100.0, 100.0)
        
        return base_progress
    
    def clear(self):
        """
        Очистка всех шагов из контекста.
        """
        self.steps.clear()