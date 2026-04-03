"""
Тесты для ComponentDiscovery — динамическое обнаружение компонентов.
"""
import pytest
from core.agent.components.component_discovery import ComponentDiscovery


@pytest.fixture
def discovery():
    return ComponentDiscovery()


class TestComponentDiscovery:
    """Тесты сканирования всех типов компонентов."""

    def test_discovers_skills(self, discovery):
        result = discovery.scan()
        skills = result["skill"]
        assert "book_library" in skills
        assert "data_analysis" in skills
        assert "final_answer" in skills
        assert "meta_component_creator" in skills
        assert "planning" in skills
        assert len(skills) == 5

    def test_skill_classes_correct(self, discovery):
        result = discovery.scan()
        skills = result["skill"]
        assert skills["book_library"].class_name == "BookLibrarySkill"
        assert skills["data_analysis"].class_name == "DataAnalysisSkill"
        assert skills["final_answer"].class_name == "FinalAnswerSkill"
        assert skills["meta_component_creator"].class_name == "MetaComponentCreator"
        assert skills["planning"].class_name == "PlanningSkill"

    def test_discovers_tools(self, discovery):
        result = discovery.scan()
        tools = result["tool"]
        assert "file_tool" in tools
        assert "sql_tool" in tools
        assert "vector_books_tool" in tools
        assert len(tools) == 3

    def test_tool_classes_correct(self, discovery):
        result = discovery.scan()
        tools = result["tool"]
        assert tools["file_tool"].class_name == "FileTool"
        assert tools["sql_tool"].class_name == "SQLTool"
        assert tools["vector_books_tool"].class_name == "VectorBooksTool"

    def test_discovers_services(self, discovery):
        result = discovery.scan()
        services = result["service"]
        assert "prompt" in services
        assert "contract" in services
        assert "table_description" in services
        assert "sql_generation" in services
        assert "sql_query" in services
        assert "sql_validator" in services
        assert len(services) == 6

    def test_service_classes_correct(self, discovery):
        result = discovery.scan()
        services = result["service"]
        assert services["prompt"].class_name == "PromptService"
        assert services["contract"].class_name == "ContractService"
        assert services["sql_generation"].class_name == "SQLGenerationService"
        assert services["sql_query"].class_name == "SQLQueryService"
        assert services["sql_validator"].class_name == "SQLValidatorService"
        assert services["table_description"].class_name == "TableDescriptionService"

    def test_discovers_behaviors(self, discovery):
        result = discovery.scan()
        behaviors = result["behavior"]
        assert "evaluation" in behaviors
        assert "planning" in behaviors
        assert "react" in behaviors
        assert len(behaviors) == 3

    def test_behavior_classes_correct(self, discovery):
        result = discovery.scan()
        behaviors = result["behavior"]
        assert behaviors["evaluation"].class_name == "EvaluationPattern"
        assert behaviors["planning"].class_name == "PlanningPattern"
        assert behaviors["react"].class_name == "ReActPattern"


class TestNoBaseClasses:
    """Убедиться, что базовые классы НЕ обнаруживаются."""

    def test_no_base_skill(self, discovery):
        result = discovery.scan()
        for name, entry in result["skill"].items():
            assert entry.class_name != "BaseSkill"

    def test_no_base_tool(self, discovery):
        result = discovery.scan()
        for name, entry in result["tool"].items():
            assert entry.class_name != "BaseTool"

    def test_no_base_service(self, discovery):
        result = discovery.scan()
        for name, entry in result["service"].items():
            assert entry.class_name != "BaseService"

    def test_no_base_behavior(self, discovery):
        result = discovery.scan()
        for name, entry in result["behavior"].items():
            assert entry.class_name != "BaseBehaviorPattern"


class TestFindComponent:
    """Тесты поиска конкретного компонента."""

    def test_find_existing_skill(self, discovery):
        entry = discovery.find_component("skill", "book_library")
        assert entry is not None
        assert entry.name == "book_library"
        assert entry.class_name == "BookLibrarySkill"

    def test_find_existing_tool(self, discovery):
        entry = discovery.find_component("tool", "sql_tool")
        assert entry is not None
        assert entry.name == "sql_tool"
        assert entry.class_name == "SQLTool"

    def test_find_existing_service(self, discovery):
        entry = discovery.find_component("service", "prompt")
        assert entry is not None
        assert entry.name == "prompt"
        assert entry.class_name == "PromptService"

    def test_find_existing_behavior(self, discovery):
        entry = discovery.find_component("behavior", "react")
        assert entry is not None
        assert entry.name == "react"
        assert entry.class_name == "ReActPattern"

    def test_find_nonexistent(self, discovery):
        entry = discovery.find_component("skill", "nonexistent_skill")
        assert entry is None

    def test_find_wrong_type(self, discovery):
        entry = discovery.find_component("tool", "book_library")
        assert entry is None


class TestGetNames:
    """Тесты получения списков имён."""

    def test_get_skill_names(self, discovery):
        names = discovery.get_names("skill")
        assert len(names) == 5
        assert "planning" in names

    def test_get_all_names(self, discovery):
        all_names = discovery.get_all_names()
        assert len(all_names["skill"]) == 5
        assert len(all_names["tool"]) == 3
        assert len(all_names["service"]) == 6
        assert len(all_names["behavior"]) == 3


class TestCaching:
    """Тесты кэширования результатов."""

    def test_scan_caches_result(self, discovery):
        result1 = discovery.scan()
        result2 = discovery.scan()
        assert result1 is result2

    def test_force_rescan(self, discovery):
        result1 = discovery.scan()
        result2 = discovery.scan(force=True)
        assert result1 is not result2


class TestComponentEntry:
    """Тесты ComponentEntry."""

    def test_to_dict(self, discovery):
        entry = discovery.find_component("skill", "book_library")
        d = entry.to_dict()
        assert d["component_type"] == "skill"
        assert d["name"] == "book_library"
        assert d["class_name"] == "BookLibrarySkill"
        assert "module_name" in d
        assert "file_path" in d
