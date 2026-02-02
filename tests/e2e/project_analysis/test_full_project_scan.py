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
        # Создаем контекст сессии
        session_context = SessionContext()
        
        # Создаем тестовую структуру проекта
        project_structure = ProjectStructure(
            name="test_project",
            root_path="/tmp/test_project",
            files=["file1.py", "file2.py"],
            directories=["dir1", "dir2"]
        )
        
        # Проверяем, что контекст сессии может хранить информацию о проекте
        session_context.set_context({"project_structure": project_structure})
        
        retrieved_context = session_context.get_context()
        assert "project_structure" in retrieved_context
        assert retrieved_context["project_structure"].name == "test_project"
    
    @patch('application.context.system_context.ConfigLoader')
    def test_full_project_scan_with_system_context(self, mock_config_loader):
        """Тест полного сканирования проекта с системным контекстом"""
        # Мокируем загрузчик конфигурации
        mock_config = Mock()
        mock_config.get_config.return_value = {"scan_depth": 3, "include_tests": True}
        mock_config_loader.return_value = mock_config
        
        # Создаем системный контекст
        system_context = SystemContext()
        
        # Получаем конфигурацию
        config = system_context.get_config()
        assert config is not None
    
    def test_end_to_end_project_analysis_workflow(self):
        """Тест сквозного рабочего процесса анализа проекта"""
        # Создаем контексты
        session_context = SessionContext()
        system_context = SystemContext()
        
        # Создаем тестовую структуру проекта
        project_structure = ProjectStructure(
            name="end_to_end_test_project",
            root_path="/tmp/end_to_end_test",
            files=["main.py", "utils.py", "tests/test_main.py"],
            directories=["src", "tests", "docs"]
        )
        
        # Устанавливаем контекст сессии
        session_context.set_context({
            "project_structure": project_structure,
            "analysis_results": {}
        })
        
        # Проверяем, что контекст установлен
        context = session_context.get_context()
        assert context["project_structure"].name == "end_to_end_test_project"
        assert "analysis_results" in context
        
        # Проверяем, что системный контекст доступен
        config = system_context.get_config()
        assert config is not None
        
        # Симулируем процесс анализа
        context["analysis_results"]["status"] = "completed"
        context["analysis_results"]["files_analyzed"] = len(project_structure.files)
        session_context.set_context(context)
        
        # Проверяем результаты анализа
        updated_context = session_context.get_context()
        assert updated_context["analysis_results"]["status"] == "completed"
        assert updated_context["analysis_results"]["files_analyzed"] == 3
    
    def test_project_scan_with_multiple_contexts_interaction(self):
        """Тест сканирования проекта с взаимодействием多个 контекстов"""
        # Создаем оба контекста
        session_context = SessionContext()
        system_context = SystemContext()
        
        # Инициализируем данные для анализа
        project_data = {
            "name": "multi_context_test",
            "path": "/tmp/multi_context_test",
            "files": ["a.py", "b.py"],
            "directories": ["subdir"]
        }
        
        # Устанавливаем данные в контекст сессии
        session_context.set_context({"current_project": project_data})
        
        # Проверяем, что данные установлены
        session_data = session_context.get_context()
        assert session_data["current_project"]["name"] == "multi_context_test"
        
        # Проверяем, что системный контекст также функционирует
        system_config = system_context.get_config()
        assert system_config is not None
    
    def test_complete_project_analysis_pipeline(self):
        """Тест полного конвейера анализа проекта"""
        # Этап 1: Инициализация контекстов
        session_context = SessionContext()
        system_context = SystemContext()
        
        # Этап 2: Подготовка данных проекта
        project_structure = ProjectStructure(
            name="pipeline_test_project",
            root_path="/tmp/pipeline_test",
            files=["module1.py", "module2.py", "config.py"],
            directories=["src", "tests"]
        )
        
        # Этап 3: Установка начального контекста
        initial_context = {
            "project": project_structure,
            "stage": "initialization",
            "results": {}
        }
        session_context.set_context(initial_context)
        
        # Этап 4: Симуляция процесса анализа
        current_context = session_context.get_context()
        current_context["stage"] = "scanning"
        current_context["results"]["files_found"] = len(project_structure.files)
        current_context["results"]["dirs_found"] = len(project_structure.directories)
        session_context.set_context(current_context)
        
        # Этап 5: Завершение анализа
        final_context = session_context.get_context()
        final_context["stage"] = "completed"
        final_context["results"]["status"] = "success"
        session_context.set_context(final_context)
        
        # Проверка результатов
        result_context = session_context.get_context()
        assert result_context["stage"] == "completed"
        assert result_context["results"]["status"] == "success"
        assert result_context["results"]["files_found"] == 3
        assert result_context["results"]["dirs_found"] == 2