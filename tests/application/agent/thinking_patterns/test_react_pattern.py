"""
Тесты паттерна мышления ReAct - ТОЛЬКО логика паттерна
"""
import pytest
from unittest.mock import Mock, AsyncMock
from application.agent.thinking_patterns.react_pattern import ReActThinkingPattern, PlanningThinkingPattern, CodeAnalysisThinkingPattern, FallbackThinkingPattern
from domain.models.agent.agent_state import AgentState


class TestReActPattern:
    """Тесты паттерна мышления ReAct - ТОЛЬКО логика принятия решений"""
    
    @pytest.fixture
    def react_pattern(self):
        """Создает экземпляр паттерна ReAct"""
        return ReActThinkingPattern()
    
    def test_react_pattern_has_correct_name(self, react_pattern):
        """Тест: паттерн ReAct имеет правильное имя"""
        assert react_pattern.name == "react"
    
    @pytest.mark.asyncio
    async def test_react_pattern_adapt_to_task_returns_correct_format(self, react_pattern):
        """Тест: адаптация ReAct паттерна к задаче возвращает корректный формат"""
        task_description = "Анализировать код и предложить улучшения"
        
        result = await react_pattern.adapt_to_task(task_description)
        
        assert isinstance(result, dict)
        assert "domain" in result
        assert "confidence" in result
        assert "parameters" in result
        assert result["domain"] == "general"
        assert isinstance(result["confidence"], (int, float))
        assert result["confidence"] > 0.0
        assert isinstance(result["parameters"], dict)
    
    @pytest.mark.asyncio
    async def test_react_pattern_execute_returns_correct_format(self, react_pattern):
        """Тест: выполнение ReAct паттерна возвращает корректный формат"""
        state = AgentState()
        context = Mock()
        available_capabilities = ["analyze_code", "run_tests"]
        
        result = await react_pattern.execute(state, context, available_capabilities)
        
        assert isinstance(result, dict)
        assert "action" in result
        assert "thought" in result
        assert result["action"] in ["ACT", "THINK", "OBSERVE", "CONTINUE"]
    
    @pytest.mark.asyncio
    async def test_react_pattern_execute_considers_available_capabilities(self, react_pattern):
        """Тест: паттерн ReAct учитывает доступные возможности при выполнении"""
        state = AgentState()
        context = Mock()
        available_capabilities = ["special_capability", "another_one"]
        
        result = await react_pattern.execute(state, context, available_capabilities)
        
        # Результат должен быть корректным независимо от доступных возможностей
        assert isinstance(result, dict)
        assert "action" in result
        assert "thought" in result


class TestPlanningPattern:
    """Тесты паттерна мышления планирования - ТОЛЬКО логика планирования"""
    
    @pytest.fixture
    def planning_pattern(self):
        """Создает экземпляр паттерна планирования"""
        return PlanningThinkingPattern()
    
    def test_planning_pattern_has_correct_name(self, planning_pattern):
        """Тест: паттерн планирования имеет правильное имя"""
        assert planning_pattern.name == "planning"
    
    @pytest.mark.asyncio
    async def test_planning_pattern_adapt_to_task_returns_correct_format(self, planning_pattern):
        """Тест: адаптация паттерна планирования к задаче возвращает корректный формат"""
        task_description = "Создать план разработки проекта"
        
        result = await planning_pattern.adapt_to_task(task_description)
        
        assert isinstance(result, dict)
        assert "domain" in result
        assert "confidence" in result
        assert "parameters" in result
        assert result["domain"] == "planning"
        assert isinstance(result["confidence"], (int, float))
        assert result["confidence"] > 0.0
        assert isinstance(result["parameters"], dict)
    
    @pytest.mark.asyncio
    async def test_planning_pattern_execute_returns_plan_action(self, planning_pattern):
        """Тест: выполнение паттерна планирования возвращает действия планирования"""
        state = AgentState()
        context = Mock()
        available_capabilities = ["create_plan", "break_down_tasks"]
        
        result = await planning_pattern.execute(state, context, available_capabilities)
        
        assert isinstance(result, dict)
        assert "action" in result
        assert "thought" in result
        assert "plan" in result
        assert result["action"] == "THINK"


class TestCodeAnalysisPattern:
    """Тесты паттерна мышления анализа кода - ТОЛЬКО логика анализа кода"""
    
    @pytest.fixture
    def code_analysis_pattern(self):
        """Создает экземпляр паттерна анализа кода"""
        return CodeAnalysisThinkingPattern()
    
    def test_code_analysis_pattern_has_correct_name(self, code_analysis_pattern):
        """Тест: паттерн анализа кода имеет правильное имя"""
        assert code_analysis_pattern.name == "code_analysis"
    
    @pytest.mark.asyncio
    async def test_code_analysis_pattern_adapt_to_task_returns_correct_format(self, code_analysis_pattern):
        """Тест: адаптация паттерна анализа кода к задаче возвращает корректный формат"""
        task_description = "Проанализировать производительность кода"
        
        result = await code_analysis_pattern.adapt_to_task(task_description)
        
        assert isinstance(result, dict)
        assert "domain" in result
        assert "confidence" in result
        assert "parameters" in result
        assert result["domain"] == "code_analysis"
        assert isinstance(result["confidence"], (int, float))
        assert result["confidence"] > 0.0
        assert isinstance(result["parameters"], dict)
    
    @pytest.mark.asyncio
    async def test_code_analysis_pattern_execute_returns_analysis_action(self, code_analysis_pattern):
        """Тест: выполнение паттерна анализа кода возвращает действия анализа"""
        state = AgentState()
        context = Mock()
        available_capabilities = ["analyze_syntax", "check_performance"]
        
        result = await code_analysis_pattern.execute(state, context, available_capabilities)
        
        assert isinstance(result, dict)
        assert "action" in result
        assert "thought" in result
        assert "capability" in result
        assert result["action"] == "ANALYZE_CODE"


class TestFallbackPattern:
    """Тесты резервного паттерна мышления - ТОЛЬКО резервная логика"""
    
    @pytest.fixture
    def fallback_pattern(self):
        """Создает экземпляр резервного паттерна"""
        return FallbackThinkingPattern()
    
    def test_fallback_pattern_has_correct_name(self, fallback_pattern):
        """Тест: резервный паттерн имеет правильное имя"""
        assert fallback_pattern.name == "fallback"
    
    @pytest.mark.asyncio
    async def test_fallback_pattern_adapt_to_task_returns_correct_format(self, fallback_pattern):
        """Тест: адаптация резервного паттерна к задаче возвращает корректный формат"""
        task_description = "Критическая ошибка, требуется резервный режим"
        
        result = await fallback_pattern.adapt_to_task(task_description)
        
        assert isinstance(result, dict)
        assert "domain" in result
        assert "confidence" in result
        assert "parameters" in result
        assert result["domain"] == "general"
        assert isinstance(result["confidence"], (int, float))
        # Доверие к резервному паттерну обычно ниже
        assert 0.0 <= result["confidence"] <= 1.0
        assert isinstance(result["parameters"], dict)
    
    @pytest.mark.asyncio
    async def test_fallback_pattern_execute_returns_safe_action(self, fallback_pattern):
        """Тест: выполнение резервного паттерна возвращает безопасные действия"""
        state = AgentState()
        context = Mock()
        available_capabilities = ["safe_mode", "log_error"]
        
        result = await fallback_pattern.execute(state, context, available_capabilities)
        
        assert isinstance(result, dict)
        assert "action" in result
        assert "thought" in result
        assert result["action"] == "THINK"
        # Резервный паттерн должен предлагать безопасные действия
        assert "suggestion" in result
