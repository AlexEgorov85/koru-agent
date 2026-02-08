"""
Сервис для оценки схожести текстов
"""
import math
from collections import Counter
from typing import List
import re
from domain.abstractions.benchmark_evaluator import IBenchmarkEvaluator
from domain.models.benchmark.benchmark_question import BenchmarkQuestion
from domain.models.benchmark.benchmark_result import BenchmarkResult


class TextSimilarityService(IBenchmarkEvaluator):
    """
    Сервис для оценки схожести текстов и оценки ответов агента
    """
    
    async def evaluate_response(
        self, 
        agent_response: str, 
        expected_answer: str,
        question: BenchmarkQuestion
    ) -> BenchmarkResult:
        """
        Оценить ответ агента
        """
        similarity_score = await self.calculate_similarity(agent_response, expected_answer)
        
        # Создаем базовый результат
        result = BenchmarkResult(
            benchmark_id="",  # Будет установлено при сохранении
            question_id=question.question_id,
            agent_response=agent_response,
            expected_answer=expected_answer,
            similarity_score=similarity_score,
            evaluation_metrics={
                "cosine_similarity": similarity_score,
                "length_ratio": len(agent_response) / len(expected_answer) if expected_answer else 0,
                "word_overlap": await self._calculate_word_overlap(agent_response, expected_answer)
            }
        )
        
        return result
    
    async def calculate_similarity(
        self, 
        response1: str, 
        response2: str
    ) -> float:
        """
        Рассчитать схожесть двух ответов с использованием косинусного сходства
        """
        # Приводим тексты к нижнему регистру и удаляем знаки препинания
        clean_response1 = self._preprocess_text(response1)
        clean_response2 = self._preprocess_text(response2)
        
        # Создаем векторы слов
        vector1 = self._text_to_vector(clean_response1)
        vector2 = self._text_to_vector(clean_response2)
        
        # Рассчитываем косинусное сходство
        cosine_sim = self._cosine_similarity(vector1, vector2)
        
        return max(0.0, min(1.0, cosine_sim))  # Ограничиваем значение от 0 до 1
    
    async def analyze_solution_path(
        self,
        actual_steps: List,
        expected_algorithm: List
    ) -> dict:
        """
        Анализировать путь решения
        """
        if not expected_algorithm or not actual_steps:
            return {
                "path_accuracy": 0.0,
                "deviation_points": [],
                "step_comparison": []
            }
        
        # Сравниваем шаги решения
        comparison_results = []
        deviation_points = []
        
        for i, expected_step in enumerate(expected_algorithm):
            if i < len(actual_steps):
                actual_step = actual_steps[i]
                step_match = await self._compare_steps(actual_step, expected_step)
                comparison_results.append(step_match)
                
                if not step_match["matches"]:
                    deviation_points.append({
                        "step_number": i + 1,
                        "expected": expected_step,
                        "actual": actual_step,
                        "deviation_type": step_match["deviation_type"],
                        "severity": step_match["severity"]
                    })
            else:
                # Агент не выполнил ожидаемый шаг
                deviation_points.append({
                    "step_number": i + 1,
                    "expected": expected_step,
                    "actual": None,
                    "deviation_type": "missing_step",
                    "severity": "high"
                })
        
        # Рассчитываем точность пути решения
        total_steps = max(len(expected_algorithm), len(actual_steps))
        matched_steps = sum(1 for comp in comparison_results if comp["matches"])
        path_accuracy = matched_steps / total_steps if total_steps > 0 else 0.0
        
        return {
            "path_accuracy": path_accuracy,
            "deviation_points": deviation_points,
            "step_comparison": comparison_results,
            "total_expected_steps": len(expected_algorithm),
            "total_actual_steps": len(actual_steps),
            "completed_steps": matched_steps
        }
    
    def _preprocess_text(self, text: str) -> str:
        """
        Предобработка текста: приведение к нижнему регистру, удаление знаков препинания
        """
        # Приводим к нижнему регистру
        text = text.lower()
        # Удаляем знаки препинания, оставляя только слова и пробелы
        text = re.sub(r'[^\w\s]', ' ', text)
        # Заменяем множественные пробелы одним пробелом
        text = re.sub(r'\s+', ' ', text).strip()
        return text
    
    def _text_to_vector(self, text: str) -> Counter:
        """
        Преобразовать текст вектор (Counter слов)
        """
        words = text.split()
        return Counter(words)
    
    def _cosine_similarity(self, vector1: Counter, vector2: Counter) -> float:
        """
        Рассчитать косинусное сходство между двумя векторами
        """
        # Получаем пересечение всех слов
        intersection = set(vector1.keys()) & set(vector2.keys())
        
        # Рассчитываем скалярное произведение
        dot_product = sum(vector1[word] * vector2[word] for word in intersection)
        
        # Рассчитываем нормы векторов
        magnitude1 = math.sqrt(sum(count ** 2 for count in vector1.values()))
        magnitude2 = math.sqrt(sum(count ** 2 for count in vector2.values()))
        
        # Рассчитываем косинусное сходство
        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0
        
        return dot_product / (magnitude1 * magnitude2)
    
    async def _calculate_word_overlap(self, response1: str, response2: str) -> float:
        """
        Рассчитать перекрытие слов между двумя текстами
        """
        set1 = set(self._preprocess_text(response1).split())
        set2 = set(self._preprocess_text(response2).split())
        
        if not set1 and not set2:
            return 1.0  # Оба пустые - идеальное совпадение
        if not set1 or not set2:
            return 0.0  # Одно из них пустое - нет совпадений
        
        intersection = set1.intersection(set2)
        union = set1.union(set2)
        
        return len(intersection) / len(union)
    
    async def _compare_steps(self, actual_step: any, expected_step: any) -> dict:
        """
        Сравнить фактический и ожидаемый шаги
        """
        # Временная реализация - в будущем можно улучшить логику сравнения
        matches = False
        deviation_type = "unknown"
        severity = "medium"
        
        # Простое сравнение на основе описания шага (в реальной реализации будет сложнее)
        if hasattr(expected_step, 'description') and hasattr(actual_step, 'description'):
            similarity = await self.calculate_similarity(
                getattr(actual_step, 'description', ''),
                getattr(expected_step, 'description', '')
            )
            matches = similarity >= 0.7  # Порог схожести
            deviation_type = "content_deviation" if not matches else "matches"
            severity = "low" if similarity >= 0.9 else "medium" if similarity >= 0.7 else "high"
        else:
            # Если шаги не имеют описания, сравниваем как строки
            actual_str = str(actual_step)
            expected_str = str(expected_step)
            similarity = await self.calculate_similarity(actual_str, expected_str)
            matches = similarity >= 0.7
            deviation_type = "content_deviation" if not matches else "matches"
            severity = "low" if similarity >= 0.9 else "medium" if similarity >= 0.7 else "high"
        
        return {
            "matches": matches,
            "deviation_type": deviation_type,
            "severity": severity,
            "similarity": await self.calculate_similarity(str(actual_step), str(expected_step))
        }