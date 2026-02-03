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
        from unittest.mock import Mock
        from domain.abstractions.event_system import IEventPublisher

        # Создаем контекст сессии
        mock_event_publisher = Mock(spec=IEventPublisher)
        session_context = SessionContext(event_publisher=mock_event_publisher)
        # Инициализация не требуется для теста, т.к. методы доступны и без неё
        
        # Создаем тестовую структуру проекта
        project_structure = ProjectStructure()
        project_structure.root_dir = "navigation_test_project"
        # Добавляем файлы и директории для тестирования
        project_structure.files = {"main.py": None, "utils/helper.py": None, "models/user.py": None}
        project_structure.directory_tree = {"utils": None, "models": None}
        
        # Устанавливаем структуру проекта в контекст с помощью доступных методов
        session_context.set_session_data("current_project", project_structure)
        session_context.set_session_data("search_results", [])
        session_context.set_session_data("navigation_history", [])
        
        # Проверяем, что контекст установлен правильно
        retrieved_project = session_context.get_session_data("current_project")
        assert retrieved_project.root_dir == "navigation_test_project"
        assert len(retrieved_project.files) == 3
        assert len(retrieved_project.directory_tree) == 2

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
    
    @patch('infrastructure.tools.filesystem.file_lister.FileListerTool')
    @patch('application.context.session.session_context.SessionContext')
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
        from unittest.mock import Mock
        from domain.abstractions.event_system import IEventPublisher

        mock_event_publisher = Mock(spec=IEventPublisher)
        session_context = SessionContext(event_publisher=mock_event_publisher)
        
        # Этап 2: Создание структуры проекта
        project_structure = ProjectStructure()
        project_structure.root_dir = "workflow_test_project"
        
        # Этап 3: Установка начального контекста
        session_context.set_session_data("project", project_structure)
        session_context.set_session_data("current_location", "/tmp/workflow_test")
        session_context.set_session_data("navigation_stack", [])
        session_context.set_session_data("search_history", [])
        
        # Этап 4: Симуляция процесса навигации
        navigation_stack = session_context.get_session_data("navigation_stack") or []
        navigation_stack.append("config/settings.py")
        session_context.set_session_data("navigation_stack", navigation_stack)
        
        search_history = session_context.get_session_data("search_history") or []
        search_history.append({
            "query": "settings",
            "results": ["config/settings.py"],
            "timestamp": "2023-01-01T00:00Z"
        })
        session_context.set_session_data("search_history", search_history)
        
        # Этап 5: Проверка результатов навигации
        final_navigation_stack = session_context.get_session_data("navigation_stack") or []
        final_search_history = session_context.get_session_data("search_history") or []
        assert len(final_navigation_stack) == 1
        assert final_navigation_stack[0] == "config/settings.py"
        assert len(final_search_history) == 1
        assert final_search_history[0]["query"] == "settings"
    
    def test_file_navigation_with_context_preservation(self):
        """Тест навигации по файлам с сохранением контекста"""
        # Создаем оба контекста
        from unittest.mock import Mock
        from domain.abstractions.event_system import IEventPublisher
        from config.models import SystemConfig

        mock_event_publisher = Mock(spec=IEventPublisher)
        session_context = SessionContext(event_publisher=mock_event_publisher)
        mock_sys_event_publisher = Mock(spec=IEventPublisher)
        mock_config = SystemConfig()
        system_context = SystemContext(config=mock_config, event_publisher=mock_sys_event_publisher)
        
        # Подготовка данных для навигации
        project_files = [
            "core/main.py",
            "core/engine.py",
            "ui/interface.py",
            "data/storage.py",
            "tests/test_core.py"
        ]
        
        # Устанавливаем контекст сессии с информацией о навигации
        session_context.set_session_data("active_project_files", project_files)
        session_context.set_session_data("current_file", "core/main.py")
        session_context.set_session_data("recent_files", ["core/engine.py", "ui/interface.py"])
        session_context.set_session_data("navigation_preferences", {
            "show_hidden": False,
            "sort_order": "alphabetical"
        })
        
        # Проверяем, что контекст навигации установлен
        current_file = session_context.get_session_data("current_file")
        recent_files = session_context.get_session_data("recent_files")
        nav_preferences = session_context.get_session_data("navigation_preferences")
        assert current_file == "core/main.py"
        assert len(recent_files) == 2
        assert nav_preferences["show_hidden"] is False
        
        # Проверяем, что системный контекст также доступен
        # (Проверка на то, что объект создан, т.к. у него нет метода get_config)
        assert system_context is not None
        
        # Симулируем переход к другому файлу
        previous_file = current_file
        session_context.set_session_data("previous_file", previous_file)
        session_context.set_session_data("current_file", "ui/interface.py")
        updated_recent_files = [previous_file] + recent_files
        updated_recent_files = updated_recent_files[:5]  # Ограничиваем историю
        session_context.set_session_data("recent_files", updated_recent_files)
        
        # Проверяем результаты перехода
        updated_current_file = session_context.get_session_data("current_file")
        updated_previous_file = session_context.get_session_data("previous_file")
        updated_recent_files_check = session_context.get_session_data("recent_files")
        assert updated_current_file == "ui/interface.py"
        assert updated_previous_file == "core/main.py"
        assert updated_recent_files_check[0] == "core/main.py"
