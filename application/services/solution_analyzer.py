"""
Сервис анализа решения агента
"""
from typing import List, Dict, Any
from domain.models.benchmark.solution_algorithm import SolutionAlgorithm
from domain.models.benchmark.benchmark_result import BenchmarkResult
from application.services.deviation_detector import DeviationDetector


class SolutionAnalyzerService:
    """
    Сервис анализа решения агента
    """
    
    def __init__(self):
        self.deviation_detector = DeviationDetector()
    
    async def compare_solution_paths(
        self,
        agent_steps: List[Dict[str, Any]],
        expected_algorithm: SolutionAlgorithm
    ) -> Dict[str, Any]:
        """
        Сравнить пути решения: эталонный алгоритм vs. фактический путь агента
        """
        # Обнаруживаем точки отклонения
        deviation_points = self.deviation_detector.detect_deviation_points(
            agent_steps,
            expected_algorithm
        )
        
        # Анализируем влияние отклонений
        impact_analysis = self.deviation_detector.analyze_deviation_impact(
            deviation_points
        )
        
        # Рассчитываем точность пути решения
        path_accuracy = self._calculate_path_accuracy(
            agent_steps,
            expected_algorithm
        )
        
        return {
            "path_accuracy": path_accuracy,
            "deviation_points": deviation_points,
            "impact_analysis": impact_analysis,
            "total_expected_steps": len(expected_algorithm.steps),
            "total_actual_steps": len(agent_steps),
            "completed_steps": len([step for step in agent_steps if self._is_step_completed(step)]),
            "efficiency_ratio": self._calculate_efficiency_ratio(agent_steps, expected_algorithm)
        }
    
    async def identify_deviation_points(
        self,
        agent_steps: List[Dict[str, Any]],
        expected_algorithm: SolutionAlgorithm
    ) -> List[Dict[str, Any]]:
        """
        Идентифицировать точки отклонения
        """
        return self.deviation_detector.detect_deviation_points(
            agent_steps,
            expected_algorithm
        )
    
    async def calculate_path_accuracy(
        self,
        agent_steps: List[Dict[str, Any]],
        expected_algorithm: SolutionAlgorithm
    ) -> float:
        """
        Рассчитать точность пути решения
        """
        return self._calculate_path_accuracy(agent_steps, expected_algorithm)
    
    def _calculate_path_accuracy(
        self,
        agent_steps: List[Dict[str, Any]],
        expected_algorithm: SolutionAlgorithm
    ) -> float:
        """
        Рассчитать точность пути решения
        """
        if not expected_algorithm.steps:
            return 1.0 if not agent_steps else 0.0
        
        # Сравниваем каждый шаг
        matched_steps = 0
        total_expected = len(expected_algorithm.steps)
        
        for i, expected_step in enumerate(expected_algorithm.steps):
            if i < len(agent_steps):
                actual_step = agent_steps[i]
                if self._is_step_matching(actual_step, expected_step):
                    matched_steps += 1
        
        # Также учитываем дополнительные шаги агента
        extra_steps = max(0, len(agent_steps) - total_expected)
        
        # Рассчитываем точность: (совпавшие шаги - дополнительные шаги) / ожидаемые шаги
        # Но не допускаем отрицательный результат
        accuracy = max(0.0, (matched_steps - extra_steps) / total_expected if total_expected > 0 else 0.0)
        return min(1.0, accuracy)  # Ограничиваем сверху 1.0
    
    def _is_step_matching(
        self,
        actual_step: Dict[str, Any],
        expected_step,
    ) -> bool:
        """
        Проверить, соответствует ли фактический шаг ожидаемому
        """
        # Проверяем соответствие действия
        actual_action = actual_step.get("action", "") if isinstance(actual_step, dict) else str(actual_step)
        expected_action = expected_step.expected_action
        
        # Проверяем частичное совпадение действия
        if expected_action.lower() in actual_action.lower():
            return True
        
        # Проверяем соответствие инструментов, если они указаны
        if expected_step.expected_tools:
            actual_tools = actual_step.get("used_tools", []) if isinstance(actual_step, dict) else []
            if not set(expected_step.expected_tools).issubset(set(actual_tools)):
                return False
        
        # Проверяем соответствие навыков, если они указаны
        if expected_step.required_skills:
            actual_skills = actual_step.get("used_skills", []) if isinstance(actual_step, dict) else []
            if not set(expected_step.required_skills).issubset(set(actual_skills)):
                return False
        
        return True
    
    def _is_step_completed(self, step: Dict[str, Any]) -> bool:
        """
        Проверить, завершен ли шаг
        """
        if isinstance(step, dict):
            return step.get("status", "").lower() == "completed" or step.get("completed", False)
        return True
    
    def _calculate_efficiency_ratio(
        self,
        agent_steps: List[Dict[str, Any]],
        expected_algorithm: SolutionAlgorithm
    ) -> float:
        """
        Рассчитать коэффициент эффективности (отношение фактических шагов к ожидаемым)
        """
        expected_count = len(expected_algorithm.steps)
        actual_count = len(agent_steps)
        
        if expected_count == 0:
            return 0.0 if actual_count == 0 else float('inf')  # Агент сделал шаги, когда ничего не ожидалось
        
        ratio = actual_count / expected_count
        # Возвращаем обратную величину, если больше шагов, чем ожидалось (меньше эффективность)
        return 1.0 / ratio if ratio >= 1.0 else ratio