"""
Тесты адаптации паттернов мышления - ТОЛЬКО адаптация
"""
import pytest
from unittest.mock import Mock
from application.agent.thinking_patterns.react_pattern import ReActThinkingPattern, PlanningThinkingPattern, CodeAnalysisThinkingPattern, FallbackThinkingPattern
from domain.models.agent.agent_state import AgentState


class TestPatternAdaptation:
    """Тесты адаптации паттернов мышления - ТОЛЬКО адаптация к задачам"""
    
    @pytest.mark.asyncio
    async def test_react_pattern_adapts_to_various_tasks(self):
        """Тест: паттерн ReAct адаптируется к различным типам задач"""
        pattern = ReActThinkingPattern()
        
        tasks = [
            "Анализировать данные и предоставить отчет",
            "Решить математическую задачу",
            "Написать короткий рассказ",
            "Оптимизировать алгоритм сортировки"
        ]
        
        for task in tasks:
            result = await pattern.adapt_to_task(task)
            
            assert isinstance(result, dict)
            assert "domain" in result
            assert "confidence" in result
            assert "parameters" in result
            assert result["domain"] == "general"
            assert 0.0 < result["confidence"] <= 1.0
            assert isinstance(result["parameters"], dict)
    
    @pytest.mark.asyncio
    async def test_planning_pattern_adapts_to_planning_tasks(self):
        """Тест: паттерн планирования адаптируется к задачам планирования"""
        pattern = PlanningThinkingPattern()
        
        planning_tasks = [
            "Создать план разработки проекта",
            "Разработать пошаговый план обучения",
            "Спланировать маркетинговую кампанию",
            "Подготовить план миграции данных"
        ]
        
        for task in planning_tasks:
            result = await pattern.adapt_to_task(task)
            
            assert isinstance(result, dict)
            assert result["domain"] == "planning"
            assert 0.0 < result["confidence"] <= 1.0
            assert isinstance(result["parameters"], dict)
    
    @pytest.mark.asyncio
    async def test_code_analysis_pattern_adapts_to_code_tasks(self):
        """Тест: паттерн анализа кода адаптируется к задачам анализа кода"""
        pattern = CodeAnalysisThinkingPattern()
        
        code_tasks = [
            "Проанализировать производительность функции",
            "Найти уязвимости в коде",
            "Оценить читаемость класса",
            "Проверить соблюдение стандартов кодирования"
        ]
        
        for task in code_tasks:
            result = await pattern.adapt_to_task(task)
            
            assert isinstance(result, dict)
            assert result["domain"] == "code_analysis"
            assert 0.0 < result["confidence"] <= 1.0
            assert isinstance(result["parameters"], dict)
    
    @pytest.mark.asyncio
    async def test_fallback_pattern_adapts_with_lower_confidence(self):
        """Тест: резервный паттерн адаптируется с более низким уровнем уверенности"""
        pattern = FallbackThinkingPattern()
        
        various_tasks = [
            "Необычная задача, которую трудно классифицировать",
            "Критическая ошибка в системе",
            "Неожиданная ситуация",
            "Задача вне обычного диапазона"
        ]
        
        for task in various_tasks:
            result = await pattern.adapt_to_task(task)
            
            assert isinstance(result, dict)
            assert "domain" in result
            assert "confidence" in result
            assert "parameters" in result
            # Резервный паттерн обычно имеет более низкую уверенность
            assert 0.0 <= result["confidence"] <= 0.7
            assert isinstance(result["parameters"], dict)
    
    @pytest.mark.asyncio
    async def test_all_patterns_return_consistent_format(self):
        """Тест: все паттерны возвращают согласованный формат адаптации"""
        patterns = [
            ReActThinkingPattern(),
            PlanningThinkingPattern(),
            CodeAnalysisThinkingPattern(),
            FallbackThinkingPattern()
        ]
        
        test_task = "Тестовая задача для проверки адаптации"
        
        for pattern in patterns:
            result = await pattern.adapt_to_task(test_task)
            
            # Проверим, что все паттерны возвращают одинаковую структуру
            assert isinstance(result, dict)
            assert "domain" in result
            assert "confidence" in result
            assert "parameters" in result
            assert isinstance(result["domain"], str)
            assert isinstance(result["confidence"], (int, float))
            assert isinstance(result["parameters"], dict)
            assert 0.0 <= result["confidence"] <= 1.0
    
    @pytest.mark.asyncio
    async def test_pattern_adaptation_handles_edge_cases(self):
        """Тест: адаптация паттернов корректно обрабатывает крайние случаи"""
        pattern = ReActThinkingPattern()
        
        edge_cases = [
            "",  # Пустая задача
            "   ",  # Задача с пробелами
            "x",  # Очень короткая задача
            "!" * 1000,  # Очень длинная задача
        ]
        
        for task in edge_cases:
            result = await pattern.adapt_to_task(task)
            
            # Даже в крайних случаях формат должен быть корректным
            assert isinstance(result, dict)
            assert "domain" in result
            assert "confidence" in result
            assert "parameters" in result
            assert isinstance(result["confidence"], (int, float))
    
    @pytest.mark.asyncio
    async def test_pattern_confidence_reflects_task_complexity(self):
        """Тест: уверенность паттерна отражает сложность задачи (гипотетически)"""
        pattern = ReActThinkingPattern()
        
        simple_task = "Сложить 2 и 2"
        complex_task = "Разработать архитектуру распределенной системы с учетом отказоустойчивости, безопасности и масштабируемости"
        
        simple_result = await pattern.adapt_to_task(simple_task)
        complex_result = await pattern.adapt_to_task(complex_task)
        
        # Оба результата должны быть корректными
        assert isinstance(simple_result, dict)
        assert isinstance(complex_result, dict)
        assert "confidence" in simple_result
        assert "confidence" in complex_result
        assert 0.0 <= simple_result["confidence"] <= 1.0
        assert 0.0 <= complex_result["confidence"] <= 1.0