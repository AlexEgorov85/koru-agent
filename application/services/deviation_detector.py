"""
Компонент обнаружения отклонений
"""
from typing import List, Dict, Any
from domain.models.benchmark.solution_algorithm import SolutionAlgorithm
from domain.models.benchmark.solution_step import SolutionStep


class DeviationDetector:
    """
    Компонент обнаружения отклонений в пути решения агента
    """
    
    def __init__(self):
        pass
    
    def detect_deviation_points(
        self,
        actual_steps: List[Dict[str, Any]],
        expected_algorithm: SolutionAlgorithm
    ) -> List[Dict[str, Any]]:
        """
        Обнаружить точки отклонения между фактическим и ожидаемым путем решения
        """
        deviation_points = []
        
        for i, expected_step in enumerate(expected_algorithm.steps):
            if i < len(actual_steps):
                actual_step = actual_steps[i]
                deviation = self._analyze_step_deviation(actual_step, expected_step)
                
                if deviation["has_deviation"]:
                    deviation_points.append({
                        "step_number": i + 1,
                        "expected_step": expected_step,
                        "actual_step": actual_step,
                        "deviation_type": deviation["type"],
                        "deviation_severity": deviation["severity"],
                        "deviation_description": deviation["description"]
                    })
            else:
                # Агент не достиг ожидаемого шага
                deviation_points.append({
                    "step_number": i + 1,
                    "expected_step": expected_step,
                    "actual_step": None,
                    "deviation_type": "missing_step",
                    "deviation_severity": "high",
                    "deviation_description": f"Агент не выполнил ожидаемый шаг: {expected_step.description}"
                })
        
        # Проверяем, не сделал ли агент дополнительные шаги
        if len(actual_steps) > len(expected_algorithm.steps):
            for i in range(len(expected_algorithm.steps), len(actual_steps)):
                actual_step = actual_steps[i]
                deviation_points.append({
                    "step_number": i + 1,
                    "expected_step": None,
                    "actual_step": actual_step,
                    "deviation_type": "extra_step",
                    "deviation_severity": "medium",
                    "deviation_description": f"Агент выполнил дополнительный шаг: {str(actual_step)}"
                })
        
        return deviation_points
    
    def classify_deviation_type(self, deviation: Dict[str, Any]) -> str:
        """
        Классифицировать тип отклонения
        """
        deviation_type = deviation.get("deviation_type", "unknown")
        
        if deviation_type in ["missing_step", "extra_step"]:
            return "structural"
        elif deviation_type == "content_deviation":
            return "logical"
        elif deviation_type == "tool_mismatch":
            return "technical"
        else:
            return "other"
    
    def analyze_deviation_impact(
        self,
        deviation_points: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Проанализировать влияние отклонений на результат
        """
        total_deviations = len(deviation_points)
        structural_deviations = 0
        logical_deviations = 0
        technical_deviations = 0
        high_severity_count = 0
        
        for deviation in deviation_points:
            deviation_type = self.classify_deviation_type(deviation)
            severity = deviation.get("deviation_severity", "medium")
            
            if deviation_type == "structural":
                structural_deviations += 1
            elif deviation_type == "logical":
                logical_deviations += 1
            elif deviation_type == "technical":
                technical_deviations += 1
            
            if severity == "high":
                high_severity_count += 1
        
        # Рассчитываем общий риск отклонений
        risk_score = self._calculate_risk_score(
            total_deviations,
            high_severity_count,
            len(deviation_points)
        )
        
        return {
            "total_deviations": total_deviations,
            "structural_deviations": structural_deviations,
            "logical_deviations": logical_deviations,
            "technical_deviations": technical_deviations,
            "high_severity_deviations": high_severity_count,
            "risk_score": risk_score,
            "impact_assessment": self._assess_impact(risk_score)
        }
    
    def _analyze_step_deviation(
        self,
        actual_step: Dict[str, Any],
        expected_step: SolutionStep
    ) -> Dict[str, Any]:
        """
        Проанализировать отклонение для одного шага
        """
        has_deviation = False
        deviation_type = "none"
        severity = "low"
        description = ""
        
        # Сравниваем действие, которое ожидалось
        actual_action = actual_step.get("action", "") if isinstance(actual_step, dict) else str(actual_step)
        expected_action = expected_step.expected_action
        
        # Простое сравнение действий
        if expected_action.lower() not in actual_action.lower():
            has_deviation = True
            deviation_type = "content_deviation"
            severity = "medium"
            description = f"Ожидаемое действие '{expected_action}' не найдено в фактическом шаге '{actual_action}'"
        
        # Если шаг требовал определенный инструмент, проверяем его использование
        if expected_step.expected_tools:
            actual_tools = actual_step.get("used_tools", []) if isinstance(actual_step, dict) else []
            missing_tools = set(expected_step.expected_tools) - set(actual_tools)
            
            if missing_tools:
                has_deviation = True
                deviation_type = "tool_mismatch"
                severity = "high" if severity != "high" else "high"
                description += f" Не использованы ожидаемые инструменты: {list(missing_tools)}"
        
        # Если шаг требовал определенные навыки, проверяем их использование
        if expected_step.required_skills:
            actual_skills = actual_step.get("used_skills", []) if isinstance(actual_step, dict) else []
            missing_skills = set(expected_step.required_skills) - set(actual_skills)
            
            if missing_skills:
                has_deviation = True
                if deviation_type == "none":
                    deviation_type = "skill_mismatch"
                    severity = "medium"
                description += f" Не использованы ожидаемые навыки: {list(missing_skills)}"
        
        return {
            "has_deviation": has_deviation,
            "type": deviation_type,
            "severity": severity,
            "description": description.strip()
        }
    
    def _calculate_risk_score(
        self,
        total_deviations: int,
        high_severity_count: int,
        total_expected_steps: int
    ) -> float:
        """
        Рассчитать оценку риска на основе отклонений
        """
        if total_expected_steps == 0:
            return 0.0
        
        # Взвешиваем отклонения в зависимости от серьезности
        weighted_deviations = (high_severity_count * 3) + ((total_deviations - high_severity_count) * 1)
        max_possible_weight = total_expected_steps * 3  # Если все шаги с высоким риском
        
        risk_score = weighted_deviations / max_possible_weight
        return min(1.0, risk_score)  # Ограничиваем до 1.0
    
    def _assess_impact(self, risk_score: float) -> str:
        """
        Оценить влияние на основе оценки риска
        """
        if risk_score >= 0.7:
            return "high"
        elif risk_score >= 0.4:
            return "medium"
        elif risk_score > 0:
            return "low"
        else:
            return "none"