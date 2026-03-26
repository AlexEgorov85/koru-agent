"""
StrategySelector — минимальный селектор паттернов на основе контекста.

АРХИТЕКТУРА:
- Выбирает лучший паттерн на основе контекста и истории ошибок
- Учитывает сложность задачи
- Переключается на react_pattern при проблемах
- Минимальная реализация без ML

ОТВЕТСТВЕННОСТЬ:
- Оценка доступных паттернов
- Выбор лучшего паттерна для текущей ситуации
- Учёт истории ошибок из FailureMemory
"""
from typing import List, Optional, Dict, Any
from core.agent.components.failure_memory import FailureMemory
from core.models.enums.common_enums import ErrorType


class StrategySelector:
    """
    Минимальный селектор паттернов на основе контекста.
    
    ПРИНЦИПЫ:
    - Простая эвристика без ML
    - Учитывает сложность задачи
    - Учитывает историю ошибок
    - Fallback на react_pattern
    
    ПРИМЕР ИСПОЛЬЗОВАНИЯ:
    selector = StrategySelector()
    best_pattern = selector.select_best_pattern(
        available_patterns=["react_pattern", "planning_pattern"],
        context={"complexity": "high"},
        failure_memory=failure_memory
    )
    """
    
    # Базовые scores для паттернов
    BASE_SCORES: Dict[str, float] = {
        "react_pattern": 0.5,           # Универсальный
        "planning_pattern": 0.6,        # Для сложных задач
        "evaluation_pattern": 0.4       # Для оценки качества
    }
    
    # Пороги для переключения
    FAILURE_THRESHOLD = 2  # 2 ошибки → switch pattern
    CONSECUTIVE_LOGIC_THRESHOLD = 3  # 3 последовательные LOGIC ошибки → switch
    
    def select_best_pattern(
        self,
        available_patterns: List[str],
        context: Optional[Dict[str, Any]] = None,
        failure_memory: Optional[FailureMemory] = None,
        current_pattern: Optional[str] = None
    ) -> str:
        """
        Выбрать лучший паттерн на основе контекста и истории ошибок.
        
        ПАРАМЕТРЫ:
        - available_patterns: список доступных паттернов
        - context: контекст задачи (complexity, goal_type, etc.)
        - failure_memory: история ошибок для учёта проблем
        - current_pattern: текущий паттерн (для избежания частых переключений)
        
        ВОЗВРАЩАЕТ:
        - str: имя лучшего паттерна
        
        АЛГОРИТМ:
        1. Исключаем паттерны с ошибками (failure_memory)
        2. Оцениваем паттерны по контексту
        3. Выбираем лучший score
        4. Fallback на react_pattern
        """
        if not available_patterns:
            return "react_pattern"  # Fallback
        
        # 1. Исключаем паттерны с ошибками
        failed_patterns = set()
        if failure_memory:
            for pattern in available_patterns:
                if failure_memory.should_switch_pattern(pattern):
                    failed_patterns.add(pattern)
        
        candidates = [p for p in available_patterns if p not in failed_patterns]
        if not candidates:
            candidates = available_patterns  # Все паттерны проблемные → берём все
        
        # 2. Оценка паттернов на основе контекста
        scores = {}
        for pattern in candidates:
            score = self.BASE_SCORES.get(pattern, 0.5)
            
            # Контекстные бонусы
            if context:
                # Сложные задачи → planning_pattern
                if context.get("complexity") == "high":
                    if pattern == "planning_pattern":
                        score += 0.2
                    elif pattern == "react_pattern":
                        score -= 0.1
                
                # Простые задачи → react_pattern
                elif context.get("complexity") == "low":
                    if pattern == "react_pattern":
                        score += 0.2
                    elif pattern == "planning_pattern":
                        score -= 0.1
                
                # Оценка качества → evaluation_pattern
                if context.get("needs_evaluation"):
                    if pattern == "evaluation_pattern":
                        score += 0.3
            
            # Штраф за частые переключения
            if current_pattern and pattern != current_pattern:
                score -= 0.05  # Небольшой штраф за переключение
            
            scores[pattern] = score
        
        # 3. Выбор лучшего паттерна
        best_pattern = max(scores, key=scores.get)
        
        # 4. Обновление scores (reinforcement learning lite)
        self._update_score(best_pattern, success=True)
        
        return best_pattern
    
    def recommend_switch(
        self,
        current_pattern: str,
        failure_memory: FailureMemory,
        context: Optional[Dict[str, Any]] = None
    ) -> tuple[bool, str]:
        """
        Рекомендовать переключение паттерна.
        
        ПАРАМЕТРЫ:
        - current_pattern: текущий паттерн
        - failure_memory: история ошибок
        - context: контекст задачи
        
        ВОЗВРАЩАЕТ:
        - tuple[bool, str]: (нужно_переключить, рекомендация)
        """
        if not failure_memory.should_switch_pattern(current_pattern):
            return False, ""
        
        # Получаем рекомендацию из failure memory
        recommendation = failure_memory.get_recommendation(current_pattern)
        
        # Определяем целевой паттерн
        if recommendation == "switch_pattern":
            # LOGIC ошибки → react_pattern
            target_pattern = "react_pattern"
        elif recommendation == "retry_with_backoff":
            # TRANSIENT ошибки → остаёмся на текущем
            return False, ""
        else:
            target_pattern = "react_pattern"  # Fallback
        
        return True, target_pattern
    
    def _update_score(self, pattern: str, success: bool):
        """
        Обновить score паттерна на основе результата.
        
        ПАРАМЕТРЫ:
        - pattern: имя паттерна
        - success: успешность выполнения
        """
        if pattern not in self.BASE_SCORES:
            self.BASE_SCORES[pattern] = 0.5
        
        if success:
            # Успех → немного увеличиваем score
            self.BASE_SCORES[pattern] = min(1.0, self.BASE_SCORES[pattern] + 0.05)
        else:
            # Неудача → немного уменьшаем score
            self.BASE_SCORES[pattern] = max(0.0, self.BASE_SCORES[pattern] - 0.1)
    
    def get_pattern_scores(self) -> Dict[str, float]:
        """
        Получить текущие scores паттернов.
        
        ВОЗВРАЩАЕТ:
        - Dict[str, float]: scores паттернов
        """
        return self.BASE_SCORES.copy()
