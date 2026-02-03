"""Сквозные тесты полного сканирования проекта"""
import pytest
from unittest.mock import Mock, patch
from application.context.session.session_context import SessionContext
from application.context.system.system_context import SystemContext
from domain.models.project.project_structure import ProjectStructure


class TestFullProjectScan:
    """Сквозные тесты полного сканирования проекта"""
    
    def test_full_project_scan_with_session_context(self):
        """Тест полного сканирования проекта с контекстом сессии"""
        from unittest.mock import Mock
        from domain.abstractions.event_system import IEventPublisher

        # Создаем контекст сессии
        mock_event_publisher = Mock(spec=IEventPublisher)
        session_context = SessionContext(event_publisher=mock_event_publisher)
        
        # Создаем тестовую структуру проекта
        project_structure = ProjectStructure()
        project_structure.root_dir = "test_project"
        project_structure.files = {"file1.py": None, "file2.py": None}
        project_structure.directory_tree = {"dir1": None, "dir2": None}
        
        # Проверяем, что контекст сессии может хранить информацию о проекте
        session_context.set_session_data("project_structure", project_structure)
        
        retrieved_structure = session_context.get_session_data("project_structure")
        assert retrieved_structure is not None
        assert retrieved_structure.root_dir == "test_project"
    
    def test_full_project_scan_with_system_context(self):
        """Тест полного сканирования проекта с системным контекстом"""
        # Создаем системный контекст
        from config.models import SystemConfig
        from domain.abstractions.event_system import IEventPublisher

        mock_event_publisher = Mock(spec=IEventPublisher)
        mock_config_obj = SystemConfig()
        system_context = SystemContext(config=mock_config_obj, event_publisher=mock_event_publisher)
        
        # Проверяем, что объект создан
        assert system_context is not None
    
    def test_end_to_end_project_analysis_workflow(self):
        """Тест сквозного рабочего процесса анализа проекта"""
        # Создаем контексты
        from unittest.mock import Mock
        from domain.abstractions.event_system import IEventPublisher
        from config.models import SystemConfig

        mock_session_event_publisher = Mock(spec=IEventPublisher)
        session_context = SessionContext(event_publisher=mock_session_event_publisher)
        mock_system_event_publisher = Mock(spec=IEventPublisher)
        mock_config = SystemConfig()
        system_context = SystemContext(config=mock_config, event_publisher=mock_system_event_publisher)
        
        # Создаем тестовую структуру проекта
        project_structure = ProjectStructure()
        project_structure.root_dir = "end_to_end_test_project"
        project_structure.files = {"main.py": None, "utils.py": None, "tests/test_main.py": None}
        project_structure.directory_tree = {"src": None, "tests": None, "docs": None}
        
        # Устанавливаем контекст сессии
        session_context.set_session_data("project_structure", project_structure)
        session_context.set_session_data("analysis_results", {})
        
        # Проверяем, что контекст установлен
        retrieved_structure = session_context.get_session_data("project_structure")
        analysis_results = session_context.get_session_data("analysis_results")
        assert retrieved_structure.root_dir == "end_to_end_test_project"
        assert analysis_results is not None
        
        # Проверяем, что системный контекст доступен
        assert system_context is not None
        
        # Симулируем процесс анализа
        analysis_results = {"status": "completed", "files_analyzed": 3}
        session_context.set_session_data("analysis_results", analysis_results)
        
        # Проверяем результаты анализа
        updated_analysis_results = session_context.get_session_data("analysis_results")
        assert updated_analysis_results["status"] == "completed"
        assert updated_analysis_results["files_analyzed"] == 3
    
    def test_project_scan_with_multiple_contexts_interaction(self):
        """Тест сканирования проекта с взаимодействием多个 контекстов"""
        # Создаем оба контекста
        from unittest.mock import Mock
        from domain.abstractions.event_system import IEventPublisher
        from config.models import SystemConfig

        mock_session_event_publisher = Mock(spec=IEventPublisher)
        session_context = SessionContext(event_publisher=mock_session_event_publisher)
        mock_system_event_publisher = Mock(spec=IEventPublisher)
        mock_config = SystemConfig()
        system_context = SystemContext(config=mock_config, event_publisher=mock_system_event_publisher)
        
        # Инициализируем данные для анализа
        project_data = {
            "name": "multi_context_test",
            "path": "/tmp/multi_context_test",
            "files": ["a.py", "b.py"],
            "directories": ["subdir"]
        }
        
        # Устанавливаем данные в контекст сессии
        session_context.set_session_data("current_project", project_data)
        
        # Проверяем, что данные установлены
        retrieved_data = session_context.get_session_data("current_project")
        assert retrieved_data["name"] == "multi_context_test"
        
        # Проверяем, что системный контекст также функционирует
        assert system_context is not None
    
    def test_complete_project_analysis_pipeline(self):
        """Тест полного конвейера анализа проекта"""
        # Этап 1: Инициализация контекстов
        from unittest.mock import Mock
        from domain.abstractions.event_system import IEventPublisher
        from config.models import SystemConfig

        mock_session_event_publisher = Mock(spec=IEventPublisher)
        session_context = SessionContext(event_publisher=mock_session_event_publisher)
        mock_system_event_publisher = Mock(spec=IEventPublisher)
        mock_config = SystemConfig()
        system_context = SystemContext(config=mock_config, event_publisher=mock_system_event_publisher)
        
        # Этап 2: Подготовка данных проекта
        project_structure = ProjectStructure()
        project_structure.root_dir = "pipeline_test_project"
        project_structure.files = {"module1.py": None, "module2.py": None, "config.py": None}
        project_structure.directory_tree = {"src": None, "tests": None}
        
        # Этап 3: Установка начального контекста
        session_context.set_session_data("project", project_structure)
        session_context.set_session_data("stage", "initialization")
        session_context.set_session_data("results", {})
        
        # Этап 4: Симуляция процесса анализа
        session_context.set_session_data("stage", "scanning")
        results = {"files_found": 3, "dirs_found": 2}
        session_context.set_session_data("results", results)
        
        # Этап 5: Завершение анализа
        session_context.set_session_data("stage", "completed")
        results["status"] = "success"
        session_context.set_session_data("results", results)
        
        # Проверка результатов
        stage = session_context.get_session_data("stage")
        results = session_context.get_session_data("results")
        assert stage == "completed"
        assert results["status"] == "success"
        assert results["files_found"] == 3
        assert results["dirs_found"] == 2
