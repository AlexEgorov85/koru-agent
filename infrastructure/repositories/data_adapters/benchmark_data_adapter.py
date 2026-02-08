"""
Адаптер для преобразования данных бенчмарка
"""
from typing import Dict, Any
from datetime import datetime
import json
from domain.models.benchmark.benchmark_question import BenchmarkQuestion
from domain.models.benchmark.benchmark_result import BenchmarkResult
from domain.models.benchmark.solution_algorithm import SolutionAlgorithm
from domain.models.benchmark.solution_step import SolutionStep


class BenchmarkDataAdapter:
    """
    Адаптер для преобразования данных бенчмарка между доменной моделью и форматом хранения
    """
    
    def to_dict(self, question: BenchmarkQuestion) -> Dict[str, Any]:
        """
        Преобразовать вопрос бенчмарка в словарь
        """
        return {
            "question_id": question.question_id,
            "question_text": question.question_text,
            "expected_answer": question.expected_answer,
            "solution_algorithm": self._algorithm_to_dict(question.solution_algorithm),
            "category": question.category,
            "difficulty_level": question.difficulty_level,
            "metadata": question.metadata,
            "created_at": question.created_at.isoformat() if question.created_at else None
        }
    
    def from_dict(self, data: Dict[str, Any]) -> BenchmarkQuestion:
        """
        Создать вопрос бенчмарка из словаря
        """
        algorithm = self._algorithm_from_dict(data["solution_algorithm"])
        
        return BenchmarkQuestion(
            question_id=data["question_id"],
            question_text=data["question_text"],
            expected_answer=data["expected_answer"],
            solution_algorithm=algorithm,
            category=data["category"],
            difficulty_level=data["difficulty_level"],
            metadata=data.get("metadata"),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else None
        )
    
    def result_to_dict(self, result: BenchmarkResult) -> Dict[str, Any]:
        """
        Преобразовать результат бенчмарка в словарь
        """
        return {
            "benchmark_id": result.benchmark_id,
            "question_id": result.question_id,
            "agent_response": result.agent_response,
            "expected_answer": result.expected_answer,
            "similarity_score": result.similarity_score,
            "evaluation_metrics": result.evaluation_metrics,
            "timestamp": result.timestamp.isoformat() if result.timestamp else None,
            "deviation_points": result.deviation_points,
            "solution_path_accuracy": result.solution_path_accuracy,
            "step_by_step_evaluation": result.step_by_step_evaluation
        }
    
    def result_from_dict(self, data: Dict[str, Any]) -> BenchmarkResult:
        """
        Создать результат бенчмарка из словаря
        """
        return BenchmarkResult(
            benchmark_id=data["benchmark_id"],
            question_id=data["question_id"],
            agent_response=data["agent_response"],
            expected_answer=data["expected_answer"],
            similarity_score=data["similarity_score"],
            evaluation_metrics=data["evaluation_metrics"],
            timestamp=datetime.fromisoformat(data["timestamp"]) if data.get("timestamp") else None,
            deviation_points=data.get("deviation_points", []),
            solution_path_accuracy=data.get("solution_path_accuracy"),
            step_by_step_evaluation=data.get("step_by_step_evaluation", [])
        )
    
    def _algorithm_to_dict(self, algorithm: SolutionAlgorithm) -> Dict[str, Any]:
        """
        Преобразовать алгоритм решения в словарь
        """
        return {
            "steps": [self._step_to_dict(step) for step in algorithm.steps],
            "required_skills": algorithm.required_skills,
            "expected_tools": algorithm.expected_tools,
            "validation_criteria": algorithm.validation_criteria,
            "description": algorithm.description
        }
    
    def _algorithm_from_dict(self, data: Dict[str, Any]) -> SolutionAlgorithm:
        """
        Создать алгоритм решения из словаря
        """
        steps = [self._step_from_dict(step_data) for step_data in data["steps"]]
        
        return SolutionAlgorithm(
            steps=steps,
            required_skills=data["required_skills"],
            expected_tools=data["expected_tools"],
            validation_criteria=data["validation_criteria"],
            description=data.get("description", "")
        )
    
    def _step_to_dict(self, step: SolutionStep) -> Dict[str, Any]:
        """
        Преобразовать шаг решения в словарь
        """
        return {
            "step_number": step.step_number,
            "description": step.description,
            "expected_action": step.expected_action,
            "expected_observation": step.expected_observation,
            "required_capability": step.required_capability,
            "estimated_complexity": step.estimated_complexity,
            "step_type": step.step_type.value,
            "required_skills": step.required_skills,
            "expected_tools": step.expected_tools
        }
    
    def _step_from_dict(self, data: Dict[str, Any]) -> SolutionStep:
        """
        Создать шаг решения из словаря
        """
        from domain.models.benchmark.solution_step import StepType
        step_type = StepType(data["step_type"]) if data.get("step_type") else StepType.EXECUTION
        
        return SolutionStep(
            step_number=data["step_number"],
            description=data["description"],
            expected_action=data["expected_action"],
            expected_observation=data["expected_observation"],
            required_capability=data["required_capability"],
            estimated_complexity=data.get("estimated_complexity", 1),
            step_type=step_type,
            required_skills=data.get("required_skills", []),
            expected_tools=data.get("expected_tools", [])
        )