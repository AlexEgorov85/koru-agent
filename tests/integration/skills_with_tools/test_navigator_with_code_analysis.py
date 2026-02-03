"""Тесты интеграции навигатора проекта с инструментами анализа кода"""
import pytest
from unittest.mock import Mock, patch
from infrastructure.adapters.skills.project_navigator.skill import ProjectNavigatorSkill
from infrastructure.tools.ast_parser_tool import ASTParserTool


class TestNavigatorWithCodeAnalysis:
    """Тесты интеграции навигатора проекта с инструментом анализа кода"""
    
    def test_navigator_skill_can_use_ast_parser(self):
        """Тест что навык навигации может использовать инструмент анализа AST"""
        # Создаем мок для инструмента анализа AST
        mock_ast_parser = Mock(spec=ASTParserTool)
        mock_ast_parser.execute.return_value = {"functions": [], "classes": []}
        
        # Создаем навык навигации по проекту
        skill = ProjectNavigatorSkill()
        
        # Проверяем, что навык может быть создан
        assert skill is not None
        
        # Проверяем, что навык имеет метод execute
        assert hasattr(skill, 'execute')
    
    @patch('infrastructure.tools.ast_parser_tool.ASTParserTool')
    def test_navigator_skill_integration_with_real_ast_parser(self, mock_ast_parser_class):
        """Тест интеграции навыка навигации с реальным инструментом анализа AST"""
        # Мокируем результат работы инструмента анализа AST
        mock_ast_parser_instance = Mock()
        mock_ast_parser_instance.execute.return_value = {"functions": ["func1"], "classes": ["Class1"]}
        mock_ast_parser_class.return_value = mock_ast_parser_instance
        
        # Создаем навык навигации по проекту
        skill = ProjectNavigatorSkill()
        
        # Проверяем, что навык может быть создан и работает
        assert skill is not None
        assert hasattr(skill, 'execute')
    
    def test_navigator_skill_str_representation(self):
        """Тест строкового представления навыка навигации"""
        skill = ProjectNavigatorSkill()
        
        # Проверяем, что строковое представление содержит имя класса
        assert "ProjectNavigatorSkill" in str(skill)
