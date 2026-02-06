"""
Реализация репозитория бенчмарков
"""
import json
import os
from datetime import datetime
from typing import List, Optional
from pathlib import Path

from domain.abstractions.benchmark_repository import IBenchmarkRepository
from domain.models.benchmark.benchmark_question import BenchmarkQuestion
from domain.models.benchmark.benchmark_result import BenchmarkResult
from infrastructure.adapters.data.benchmark_data_adapter import BenchmarkDataAdapter


class BenchmarkRepositoryImpl(IBenchmarkRepository):
    """
    Реализация репозитория бенчмарков с хранением в файловой системе
    """
    
    def __init__(self, base_path: str = "benchmarks"):
        self.base_path = Path(base_path)
        self.questions_path = self.base_path / "questions"
        self.results_path = self.base_path / "results"
        
        # Создаем необходимые директории
        self.questions_path.mkdir(parents=True, exist_ok=True)
        self.results_path.mkdir(parents=True, exist_ok=True)
        
        self.adapter = BenchmarkDataAdapter()
    
    async def save_benchmark_question(self, question: BenchmarkQuestion) -> bool:
        """
        Сохранить вопрос бенчмарка
        """
        try:
            # Создаем директорию для категории, если она не существует
            category_path = self.questions_path / question.category
            category_path.mkdir(exist_ok=True)
            
            # Преобразуем объект в словарь для сохранения
            question_dict = self.adapter.to_dict(question)
            
            # Сохраняем в JSON файл
            file_path = category_path / f"{question.question_id}.json"
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(question_dict, f, ensure_ascii=False, indent=2)
            
            return True
        except Exception as e:
            print(f"Ошибка при сохранении вопроса бенчмарка: {e}")
            return False
    
    async def get_benchmark_question(self, question_id: str) -> Optional[BenchmarkQuestion]:
        """
        Получить вопрос бенчмарка по ID
        """
        try:
            # Ищем файл по всем категориям
            for category_dir in self.questions_path.iterdir():
                if category_dir.is_dir():
                    file_path = category_dir / f"{question_id}.json"
                    if file_path.exists():
                        with open(file_path, 'r', encoding='utf-8') as f:
                            question_dict = json.load(f)
                        
                        return self.adapter.from_dict(question_dict)
            
            return None
        except Exception as e:
            print(f"Ошибка при загрузке вопроса бенчмарка: {e}")
            return None
    
    async def get_all_questions_by_category(self, category: str) -> List[BenchmarkQuestion]:
        """
        Получить все вопросы по категории
        """
        try:
            category_path = self.questions_path / category
            if not category_path.exists():
                return []
            
            questions = []
            for file_path in category_path.glob("*.json"):
                with open(file_path, 'r', encoding='utf-8') as f:
                    question_dict = json.load(f)
                
                question = self.adapter.from_dict(question_dict)
                questions.append(question)
            
            return questions
        except Exception as e:
            print(f"Ошибка при загрузке вопросов бенчмарка: {e}")
            return []
    
    async def get_all_questions(self) -> List[BenchmarkQuestion]:
        """
        Получить все вопросы
        """
        try:
            questions = []
            for category_dir in self.questions_path.iterdir():
                if category_dir.is_dir():
                    for file_path in category_dir.glob("*.json"):
                        with open(file_path, 'r', encoding='utf-8') as f:
                            question_dict = json.load(f)
                        
                        question = self.adapter.from_dict(question_dict)
                        questions.append(question)
            
            return questions
        except Exception as e:
            print(f"Ошибка при загрузке всех вопросов бенчмарка: {e}")
            return []
    
    async def save_benchmark_result(self, result: BenchmarkResult) -> bool:
        """
        Сохранить результат бенчмарка
        """
        try:
            # Создаем директорию для сессии, если она не существует
            session_path = self.results_path / result.benchmark_id
            session_path.mkdir(exist_ok=True)
            
            # Преобразуем объект в словарь для сохранения
            result_dict = self.adapter.result_to_dict(result)
            
            # Сохраняем в JSON файл
            file_path = session_path / f"{result.question_id}_result.json"
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(result_dict, f, ensure_ascii=False, indent=2)
            
            return True
        except Exception as e:
            print(f"Ошибка при сохранении результата бенчмарка: {e}")
            return False
    
    async def get_results_by_session(self, session_id: str) -> List[BenchmarkResult]:
        """
        Получить результаты по ID сессии
        """
        try:
            session_path = self.results_path / session_id
            if not session_path.exists():
                return []
            
            results = []
            for file_path in session_path.glob("*_result.json"):
                with open(file_path, 'r', encoding='utf-8') as f:
                    result_dict = json.load(f)
                
                result = self.adapter.result_from_dict(result_dict)
                results.append(result)
            
            return results
        except Exception as e:
            print(f"Ошибка при загрузке результатов бенчмарка: {e}")
            return []
    
    async def get_results_by_question(self, question_id: str) -> List[BenchmarkResult]:
        """
        Получить результаты по ID вопроса
        """
        try:
            results = []
            for session_dir in self.results_path.iterdir():
                if session_dir.is_dir():
                    file_path = session_dir / f"{question_id}_result.json"
                    if file_path.exists():
                        with open(file_path, 'r', encoding='utf-8') as f:
                            result_dict = json.load(f)
                        
                        result = self.adapter.result_from_dict(result_dict)
                        results.append(result)
            
            return results
        except Exception as e:
            print(f"Ошибка при загрузке результатов по вопросу: {e}")
            return []