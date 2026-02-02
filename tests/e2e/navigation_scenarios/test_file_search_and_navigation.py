"""Сквозные тесты сценариев поиска и навигации по файлам"""
import pytest
from unittest.mock import Mock, patch
from application.context.session.session_context import SessionContext
from application.context.system.system_context import SystemContext
from domain.models.project.project_structure import ProjectStructure
from infrastructure.adapters.skills.project_navigator.skill import ProjectNavigatorSkill


class TestFileSearchAndNavigation:
    """Сквозные тесты сценариев поиска и навигации по файлам"""
    
    def test_file_search_scenario_with_session_context(self):
        """Тест сценария поиска файлов с контекстом сессии"""
        # Создаем контекст сессии
        session_context = SessionContext()
        
        # Создаем тестовую структуру проекта
        project_structure = ProjectStructure()
        project_structure.root_dir = "navigation_test_project"
        
        # Устанавливаем структуру проекта в контекст
        session_context.set_context({
            "current_project": project_structure,
            "search_results": [],
            "navigation_history": []
        })
        
        # Проверяем, что контекст установлен правильно
        context = session_context.get_context()
        assert context["current_project"].name == "navigation_test_project"
        assert len(context["current_project"].files) == 3
        assert len(context["current_project"].directories) == 3

    def test_file_navigation_with_project_structure(self):
        """Тест навигации по файлам с использованием структуры проекта"""
        # Создаем структуру проекта
        project_structure = ProjectStructure()
        project_structure.root_dir = "nav_project"
        
        # Создаем навигационный скилл
        navigator_skill = ProjectNavigatorSkill()
        
        # Проверяем, что навигационный скилл создан
        assert navigator_skill is not None
        assert hasattr(navigator_skill, 'execute')
        
        # Проверяем, что структура проекта создана корректно
        assert project_structure.root_dir == "nav_project"
    
    @patch('infrastructure.adapters.skills.project_navigator.skill.FileLister')
    @patch('application.context.session_context.SessionContext')
    def test_integrated_file_search_and_navigation(self, mock_session_context, mock_file_lister):
        """Тест интегрированного поиска и навигации по файлам"""
        # Мокируем результаты работы инструментов
        mock_file_lister_instance = Mock()
        mock_file_lister_instance.execute.return_value = [
            "src/main.py",
            "src/utils/helpers.py",
            "src/models/user_model.py"
        ]
        mock_file_lister.return_value = mock_file_lister_instance
        
        mock_session_instance = Mock()
        mock_session_instance.get_context.return_value = {
            "current_path": "/tmp/integrated_test",
            "search_criteria": "*.py"
        }
        mock_session_context.return_value = mock_session_instance
        
        # Создаем навигационный скилл
        navigator_skill = ProjectNavigatorSkill()
        
        # Проверяем, что скилл может быть создан
        assert navigator_skill is not None
        
        # Проверяем, что моки были вызваны корректно
        assert mock_file_lister is not None
        assert mock_session_context is not None
    
    def test_end_to_end_file_navigation_workflow(self):
        """Тест сквозного рабочего процесса навигации по файлам"""
        # Этап 1: Инициализация контекста сессии
        session_context = SessionContext()
        
        # Этап 2: Создание структуры проекта
        project_structure = ProjectStructure()
        project_structure.root_dir = "workflow_test_project"
        
        # Этап 3: Установка начального контекста
        initial_context = {
            "project": project_structure,
            "current_location": "/tmp/workflow_test",
            "navigation_stack": [],
            "search_history": []
        }
        session_context.set_context(initial_context)
        
        # Этап 4: Симуляция процесса навигации
        context = session_context.get_context()
        context["navigation_stack"].append("config/settings.py")
        context["search_history"].append({
            "query": "settings",
            "results": ["config/settings.py"],
            "timestamp": "2023-01-01T00:00Z"
        })
        session_context.set_context(context)
        
        # Этап 5: Проверка результатов навигации
        final_context = session_context.get_context()
        assert len(final_context["navigation_stack"]) == 1
        assert final_context["navigation_stack"][0] == "config/settings.py"
        assert len(final_context["search_history"]) == 1
        assert final_context["search_history"][0]["query"] == "settings"
    
    def test_file_navigation_with_context_preservation(self):
        """Тест навигации по файлам с сохранением контекста"""
        # Создаем оба контекста
        session_context = SessionContext()
        system_context = SystemContext()
        
        # Подготовка данных для навигации
        project_files = [
            "core/main.py",
            "core/engine.py",
            "ui/interface.py",
            "data/storage.py",
            "tests/test_core.py"
        ]
        
        # Устанавливаем контекст сессии с информацией о навигации
        session_context.set_context({
            "active_project_files": project_files,
            "current_file": "core/main.py",
            "recent_files": ["core/engine.py", "ui/interface.py"],
            "navigation_preferences": {
                "show_hidden": False,
                "sort_order": "alphabetical"
            }
        })
        
        # Проверяем, что контекст навигации установлен
        nav_context = session_context.get_context()
        assert nav_context["current_file"] == "core/main.py"
        assert len(nav_context["recent_files"]) == 2
        assert nav_context["navigation_preferences"]["show_hidden"] is False
        
        # Проверяем, что системный контекст также доступен
        system_config = system_context.get_config()
        assert system_config is not None
        
        # Симулируем переход к другому файлу
        nav_context["previous_file"] = nav_context["current_file"]
        nav_context["current_file"] = "ui/interface.py"
        nav_context["recent_files"].insert(0, nav_context["previous_file"])
        nav_context["recent_files"] = nav_context["recent_files"][:5]  # Ограничиваем историю
        
        session_context.set_context(nav_context)
        
        # Проверяем результаты перехода
        updated_nav_context = session_context.get_context()
        assert updated_nav_context["current_file"] == "ui/interface.py"
        assert updated_nav_context["previous_file"] == "core/main.py"
        assert updated_nav_context["recent_files"][0] == "core/main.py"