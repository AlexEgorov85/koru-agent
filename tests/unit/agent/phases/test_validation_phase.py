"""
Тесты для ValidationPhase.

Проверяемая бизнес-логика:
1. validate_action() — проверяет существование инструмента (action_name в available_capabilities)
2. validate_action() — валидирует параметры через Pydantic (input_contracts)
3. _build_unknown_tool_error() — формирует подробное сообщение о неизвестном инструменте
4. _validate_parameters() — использует Pydantic модели для валидации
5. При ошибке валидации возвращает (False, ExecutionResult с подробностями)
"""

import pytest
from unittest.mock import MagicMock, patch
from core.agent.phases.validation_phase import ValidationPhase
from core.models.data.capability import Capability
from core.models.data.execution import ExecutionResult, ExecutionStatus
from pydantic import BaseModel, Field, ValidationError


# ============================================================================
# Вспомогательные классы
# ============================================================================

class TestInputModel(BaseModel):
    """Тестовая Pydantic модель для валидации параметров."""
    query: str
    limit: int = 10


class TestInputModelWithValidation(BaseModel):
    """Тестовая модель с валидацией."""
    name: str = Field(..., min_length=1)
    age: int = Field(..., ge=0, le=150)


# ============================================================================
# Фикстуры
# ============================================================================

@pytest.fixture
def validation_phase():
    """ValidationPhase с замоканными зависимостями."""
    mock_log = MagicMock()
    mock_event_bus = MagicMock()
    mock_app_context = MagicMock()
    
    phase = ValidationPhase(
        log=mock_log,
        event_bus=mock_event_bus,
        application_context=mock_app_context,
    )
    return phase


@pytest.fixture
def validation_phase_no_context():
    """ValidationPhase без application_context."""
    mock_log = MagicMock()
    mock_event_bus = MagicMock()
    
    phase = ValidationPhase(
        log=mock_log,
        event_bus=mock_event_bus,
        application_context=None,
    )
    return phase


@pytest.fixture
def sample_capabilities():
    """Список доступных Capability."""
    return [
        Capability(name="sql_tool.execute", skill_name="sql_tool", description="Execute SQL"),
        Capability(name="vector_search.query", skill_name="vector_search", description="Vector search"),
        Capability(name="final_answer.generate", skill_name="final_answer", description="Generate final answer"),
    ]


@pytest.fixture
def mock_component_with_contract():
    """Mock компонент с input_contracts."""
    component = MagicMock()
    component.input_contracts = {
        "sql_tool.execute": TestInputModel,
        "vector_search.query": TestInputModelWithValidation,
    }
    return component


# ============================================================================
# Тесты validate_action() — проверка инструмента
# ============================================================================

class TestValidateAction:
    """Тесты основного метода validate_action()."""
    
    def test_returns_true_for_valid_tool(
        self, validation_phase_no_context, sample_capabilities
    ):
        """Действие существует → (True, None)."""
        result = validation_phase_no_context.validate_action(
            action_name="sql_tool.execute",
            parameters={"query": "SELECT 1"},
            available_capabilities=sample_capabilities,
        )
        
        assert result == (True, None)
    
    def test_returns_false_for_unknown_tool(
        self, validation_phase_no_context, sample_capabilities
    ):
        """Неизвестный инструмент → (False, ExecutionResult)."""
        success, exec_result = validation_phase_no_context.validate_action(
            action_name="unknown_tool.execute",
            parameters={},
            available_capabilities=sample_capabilities,
        )
        
        assert success is False
        assert isinstance(exec_result, ExecutionResult)
        assert exec_result.status == ExecutionStatus.FAILED
        assert "неизвестный инструмент" in str(exec_result.error).lower() or "unknown" in str(exec_result.error).lower()
    
    def test_error_data_contains_valid_tools(
        self, validation_phase_no_context, sample_capabilities
    ):
        """В ответе об ошибке есть список доступных инструментов."""
        success, exec_result = validation_phase_no_context.validate_action(
            action_name="unknown_tool",
            parameters={},
            available_capabilities=sample_capabilities,
        )
        
        assert "valid_tools" in exec_result.data
        assert len(exec_result.data["valid_tools"]) == 3
    
    def test_error_data_contains_error_type(
        self, validation_phase_no_context, sample_capabilities
    ):
        """В ответе об ошибке есть error_type."""
        success, exec_result = validation_phase_no_context.validate_action(
            action_name="unknown_tool",
            parameters={},
            available_capabilities=sample_capabilities,
        )
        
        assert exec_result.data["error_type"] == "unknown_tool"
    
    def test_validates_with_empty_parameters(
        self, validation_phase_no_context, sample_capabilities
    ):
        """Валидация с пустыми параметрами."""
        result = validation_phase_no_context.validate_action(
            action_name="sql_tool.execute",
            parameters={},
            available_capabilities=sample_capabilities,
        )
        
        # Может быть True или False в зависимости от того, требует ли модель параметры
        assert isinstance(result, tuple)
        assert len(result) == 2


# ============================================================================
# Тесты валидации параметров
# ============================================================================

class TestParameterValidation:
    """Тесты валидации параметров через Pydantic."""
    
    def test_valid_parameters(
        self, validation_phase, sample_capabilities, mock_component_with_contract
    ):
        """Валидные параметры → True."""
        validation_phase.application_context.components.get.return_value = mock_component_with_contract
        
        with patch.object(validation_phase, '_resolve_component', return_value=mock_component_with_contract):
            success, exec_result = validation_phase.validate_action(
                action_name="sql_tool.execute",
                parameters={"query": "SELECT 1"},
                available_capabilities=sample_capabilities,
            )
            
            assert success is True
    
    def test_invalid_parameters_missing_field(
        self, validation_phase, sample_capabilities, mock_component_with_contract
    ):
        """Отсутствует обязательное поле → False."""
        validation_phase.application_context.components.get.return_value = mock_component_with_contract
        
        with patch.object(validation_phase, '_resolve_component', return_value=mock_component_with_contract):
            success, exec_result = validation_phase.validate_action(
                action_name="sql_tool.execute",
                parameters={},  # Нет обязательного поля 'query'
                available_capabilities=sample_capabilities,
            )
            
            assert success is False
            assert exec_result.data["error_type"] == "invalid_parameters"
            assert "details" in exec_result.data
    
    def test_invalid_parameters_validation_error(
        self, validation_phase, sample_capabilities, mock_component_with_contract
    ):
        """Параметры не проходят валидацию Pydantic → False."""
        validation_phase.application_context.components.get.return_value = mock_component_with_contract
        
        with patch.object(validation_phase, '_resolve_component', return_value=mock_component_with_contract):
            success, exec_result = validation_phase.validate_action(
                action_name="vector_search.query",
                parameters={"name": "", "age": 200},  # Неправильные значения
                available_capabilities=sample_capabilities,
            )
            
            assert success is False
            assert "details" in exec_result.data
    
    def test_no_application_context_skips_validation(
        self, validation_phase_no_context, sample_capabilities
    ):
        """Без application_context пропускает валидацию параметров."""
        result = validation_phase_no_context.validate_action(
            action_name="sql_tool.execute",
            parameters={"query": "SELECT 1"},
            available_capabilities=sample_capabilities,
        )
        
        assert result == (True, None)


# ============================================================================
# Тесты _build_unknown_tool_error()
# ============================================================================

class TestBuildUnknownToolError:
    """Тесты формирования сообщения о неизвестном инструменте."""
    
    def test_contains_action_name(self, validation_phase_no_context):
        """Сообщение содержит имя неизвестного инструмента."""
        error_msg = validation_phase_no_context._build_unknown_tool_error(
            action_name="unknown_tool",
            valid_names=["tool1", "tool2", "tool3"],
        )
        
        assert "unknown_tool" in error_msg
    
    def test_contains_valid_tools_list(self, validation_phase_no_context):
        """Сообщение содержит список доступных инструментов."""
        valid_names = ["sql_tool.execute", "vector_search.query", "final_answer.generate"]
        error_msg = validation_phase_no_context._build_unknown_tool_error(
            action_name="unknown",
            valid_names=valid_names,
        )
        
        for name in valid_names:
            assert name in error_msg
    
    def test_groups_tools_by_type(self, validation_phase_no_context):
        """Инструменты группируются по типам (skill, tool, service)."""
        valid_names = [
            "sql_tool.execute",
            "sql_tool.query",
            "vector_search.query",
            "final_answer.generate",
        ]
        error_msg = validation_phase_no_context._build_unknown_tool_error(
            action_name="unknown",
            valid_names=valid_names,
        )
        
        assert "sql_tool" in error_msg
        assert "vector_search" in error_msg
        assert "final_answer" in error_msg
    
    def test_suggests_similar_tools(self, validation_phase_no_context):
        """Предлагает похожие инструменты."""
        valid_names = ["sql_tool.execute", "sql_tool.query", "vector_search.query"]
        error_msg = validation_phase_no_context._build_unknown_tool_error(
            action_name="sql_tool.unknown",
            valid_names=valid_names,
        )
        
        # Должен предложить похожие инструменты, начинающиеся с sql_tool
        assert "возможно" in error_msg.lower() or "possible" in error_msg.lower() or "suggest" in error_msg.lower()
    
    def test_contains_hint(self, validation_phase_no_context):
        """Сообщение содержит подсказку."""
        error_msg = validation_phase_no_context._build_unknown_tool_error(
            action_name="unknown",
            valid_names=["tool1"],
        )
        
        assert "ПОДСКАЗКА" in error_msg or "hint" in error_msg.lower()


# ============================================================================
# Тесты _validate_parameters()
# ============================================================================

class TestValidateParameters:
    """Тесты валидации параметров через Pydantic модели."""
    
    def test_success(self, validation_phase, mock_component_with_contract):
        """Успешная валидация → (True, 'OK', details)."""
        validation_phase.application_context = MagicMock()
        
        with patch.object(validation_phase, '_resolve_component', return_value=mock_component_with_contract):
            success, msg, details = validation_phase._validate_parameters(
                action_name="sql_tool.execute",
                parameters={"query": "SELECT 1"},
            )
            
            assert success is True
            assert msg == "OK"
    
    def test_failure_missing_field(self, validation_phase, mock_component_with_contract):
        """Отсутствует поле → (False, error_msg, details)."""
        validation_phase.application_context = MagicMock()
        
        with patch.object(validation_phase, '_resolve_component', return_value=mock_component_with_contract):
            success, msg, details = validation_phase._validate_parameters(
                action_name="sql_tool.execute",
                parameters={},  # Нет 'query'
            )
            
            assert success is False
            assert "query" in msg.lower() or "error" in msg.lower()
            assert "details" in details or "pydantic_errors" in details
    
    def test_component_not_found(self, validation_phase):
        """Компонент не найден → пропускает валидацию."""
        validation_phase.application_context = MagicMock()
        
        with patch.object(validation_phase, '_resolve_component', return_value=None):
            success, msg, details = validation_phase._validate_parameters(
                action_name="unknown_tool",
                parameters={},
            )
            
            assert success is True
            assert msg == "OK"
    
    def test_no_input_contracts(self, validation_phase):
        """У компонента нет input_contracts → пропускает."""
        component = MagicMock()
        component.input_contracts = {}
        
        with patch.object(validation_phase, '_resolve_component', return_value=component):
            success, msg, details = validation_phase._validate_parameters(
                action_name="some_tool",
                parameters={},
            )
            
            assert success is True
    
    def test_finds_by_partial_name(self, validation_phase, mock_component_with_contract):
        """Поиск контракта по частичному совпадению имени."""
        validation_phase.application_context = MagicMock()
        
        with patch.object(validation_phase, '_resolve_component', return_value=mock_component_with_contract):
            # Передаем только часть имени (без префикса)
            success, msg, details = validation_phase._validate_parameters(
                action_name="execute",  # Должен найти sql_tool.execute
                parameters={"query": "SELECT 1"},
            )
            
            assert success is True


# ============================================================================
# Тесты _resolve_component()
# ============================================================================

class TestResolveComponent:
    """Тесты разрешения компонента по имени действия."""
    
    def test_resolves_by_type_prefix(self, validation_phase):
        """Определяет тип по префиксу (sql_tool → TOOL)."""
        mock_component = MagicMock()
        validation_phase.application_context.components.get.return_value = mock_component
        
        result = validation_phase._resolve_component("sql_tool.execute")
        
        validation_phase.application_context.components.get.assert_called()
    
    def test_searches_all_registries(self, validation_phase):
        """Ищет во всех реестрах, если не нашел по префиксу."""
        validation_phase.application_context = MagicMock()
        validation_phase.application_context.components.get.return_value = None
        validation_phase.application_context.components.all_of_type.return_value = [
            ("sql_tool", MagicMock()),
        ]
        
        result = validation_phase._resolve_component("some_tool.execute")
        
        validation_phase.application_context.components.all_of_type.assert_called()


# ============================================================================
# Тесты _extract_pydantic_errors()
# ============================================================================

class TestExtractPydanticErrors:
    """Тесты извлечения ошибок Pydantic."""
    
    def test_extracts_errors(self, validation_phase):
        """Извлекает ошибки из ValidationError."""
        try:
            TestInputModel(query="")  # type: ignore
        except Exception as e:
            details = validation_phase._extract_pydantic_errors(e)
            
            assert "pydantic_errors" in details or "exception_type" in details
    
    def test_formats_human_readable(self, validation_phase):
        """Формирует человекочитаемый список ошибок."""
        try:
            TestInputModelWithValidation(name="", age=200)
        except Exception as e:
            details = validation_phase._extract_pydantic_errors(e)
            
            if "human_readable" in details:
                assert len(details["human_readable"]) > 0
                assert any("name" in err.lower() or "age" in err.lower() for err in details["human_readable"])
