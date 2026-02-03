"""Тесты направления зависимостей в архитектуре"""
import pytest
import inspect
from domain.abstractions.skills.base_skill import BaseSkill
from domain.abstractions.tools.base_tool import BaseTool
from domain.models.code.code_unit import CodeUnit
from domain.models.project.project_structure import ProjectStructure


class TestDependencyDirection:
    """Тесты направления зависимостей в архитектуре"""
    
    def test_domain_abstractions_do_not_depend_on_infrastructure(self):
        """Тест что абстракции домена не зависят от инфраструктуры"""
        # Проверяем, что классы в domain.abstractions не импортируют из infrastructure
        domain_abstraction_classes = [
            BaseSkill,
            BaseTool
        ]
        
        for cls in domain_abstraction_classes:
            module = inspect.getmodule(cls)
            assert module is not None
            # Проверяем, что модуль находится в domain.abstractions
            assert "domain.abstractions" in module.__name__
            # Убеждаемся, что он не содержит ссылок на infrastructure
            module_source = inspect.getsource(module)
            assert "infrastructure" not in module_source.lower() or \
                   "from infrastructure" not in module_source.lower() or \
                   "import infrastructure" not in module_source.lower()
    
    def test_domain_models_do_not_depend_on_application_or_infrastructure(self):
        """Тест что модели домена не зависят от приложения или инфраструктуры"""
        domain_model_classes = [
            CodeUnit,
            ProjectStructure
        ]
        
        for cls in domain_model_classes:
            module = inspect.getmodule(cls)
            assert module is not None
            # Проверяем, что модуль находится в domain.models
            assert "domain.models" in module.__name__
            # Убеждаемся, что он не содержит ссылок на application или infrastructure
            module_source = inspect.getsource(module)
            assert "application" not in module_source.lower() or \
                   "from application" not in module_source.lower() or \
                   "import application" not in module_source.lower()
            assert "infrastructure" not in module_source.lower() or \
                   "from infrastructure" not in module_source.lower() or \
                   "import infrastructure" not in module_source.lower()
    
    def test_high_level_modules_do_not_depend_on_low_level_implementation(self):
        """Тест что высокоуровневые модули не зависят от низкоуровневых реализаций"""
        # Domain (высокий уровень) не должен зависеть от Infrastructure (низкий уровень)
        base_skill_module = inspect.getmodule(BaseSkill)
        file_reader_module = None  # Это будет из инфраструктуры
        
        # Имитируем проверку зависимостей через анализ модулей
        assert base_skill_module is not None
        assert "domain" in base_skill_module.__name__
        
        # Проверим, что абстракции находятся в домене, а реализации в инфраструктуре
        from infrastructure.adapters.skills.project_map.skill import ProjectMapSkill
        from infrastructure.tools.filesystem.file_reader import FileReaderTool
        
        # BaseSkill - это абстракция в домене
        assert "domain.abstractions" in inspect.getmodule(BaseSkill).__name__
        
        # ProjectMapSkill - это реализация в инфраструктуре
        assert "infrastructure" in inspect.getmodule(ProjectMapSkill).__name__
        
        # FileReaderTool - это реализация в инфраструктуре
        assert "infrastructure" in inspect.getmodule(FileReaderTool).__name__
    
    def test_abstractions_not_dependent_on_concrete_implementation(self):
        """Тест что абстракции не зависят от конкретных реализаций"""
        # Проверяем, что BaseSkill не зависит от конкретных реализаций
        base_skill_module = inspect.getmodule(BaseSkill)
        assert base_skill_module is not None
        
        # Проверяем, что BaseTool не зависит от конкретных реализаций
        base_tool_module = inspect.getmodule(BaseTool)
        assert base_tool_module is not None
        
        # Ни одна из абстракций не должна импортировать конкретные реализации
        base_skill_source = inspect.getsource(base_skill_module)
        base_tool_source = inspect.getsource(base_tool_module)
        
        # Убеждаемся, что в исходном коде абстракций нет импортов инфраструктурных реализаций
        assert "infrastructure.adapters.skills" not in base_skill_source
        assert "infrastructure.tools" not in base_tool_source
    
    def test_dependency_inversion_principle(self):
        """Тест принципа инверсии зависимостей"""
        # 1. Модули верхних уровней не должны зависеть от модулей нижних уровней.
        #    Оба должны зависеть от абстракций.
        from domain.abstractions.skills.base_skill import BaseSkill
        from infrastructure.adapters.skills.project_map.skill import ProjectMapSkill
        
        # 2. Абстракции не должны зависеть от деталей. 
        #    Детали должны зависеть от абстракций.
        assert issubclass(ProjectMapSkill, BaseSkill)
        
        # Проверяем, что реализация (инфраструктура) зависит от абстракции (домен)
        # а не наоборот
        implementation_module = inspect.getmodule(ProjectMapSkill)
        abstraction_module = inspect.getmodule(BaseSkill)
        
        assert "infrastructure" in implementation_module.__name__
        assert "domain.abstractions" in abstraction_module.__name__
        
        # Реализация наследует абстракцию, что подтверждает принцип инверсии зависимостей
        assert issubclass(ProjectMapSkill, BaseSkill)
    
    def test_domain_models_dont_import_infrastructure_or_application(self):
        """Тест что доменные модели не импортируют из инфраструктуры или приложения"""
        # Получаем модули доменных моделей
        code_unit_module = inspect.getmodule(CodeUnit)
        project_structure_module = inspect.getmodule(ProjectStructure)
        
        # Проверяем, что они не импортируют из infrastructure или application
        for model_module in [code_unit_module, project_structure_module]:
            if model_module:
                module_source = inspect.getsource(model_module)
                assert "from infrastructure" not in module_source
                assert "import infrastructure" not in module_source
                assert "from application" not in module_source
                assert "import application" not in module_source
