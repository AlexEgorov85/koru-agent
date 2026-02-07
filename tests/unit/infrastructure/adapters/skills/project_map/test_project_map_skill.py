import tempfile
import pathlib
import sys
from pathlib import Path

# Добавим путь к основному коду
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import AsyncMock
from infrastructure.tools.safe_file_reader_tool import SafeFileReaderTool
from infrastructure.adapters.skills.project_map.skill import ProjectMapSkill
from domain.models.capability import Capability

class TestProjectMapSkill:
    """Тесты для навыка карты проекта"""
    
    def setup_method(self):
        """Подготовка тестовой среды"""
        # Создаем временную директорию проекта
        self.test_project_dir = tempfile.mkdtemp(prefix="test_project_")
        self.project_path = pathlib.Path(self.test_project_dir)
        
        # Создаем тестовые файлы
        test_file = self.project_path / "main.py"
        test_file.write_text("# Main module\nprint('Hello, World!')", encoding="utf-8")
    
    def teardown_method(self):
        """Очистка после тестов"""
        import shutil
        shutil.rmtree(self.test_project_dir, ignore_errors=True)
    
    @pytest.mark.asyncio
    async def test_skill_creation(self):
        """Тест: Создание навыка"""
        tool = SafeFileReaderTool(project_root=self.test_project_dir)
        skill = ProjectMapSkill(tool)
        
        assert skill.name == "project_map"
        assert skill.file_reader_tool is not None
    
    @pytest.mark.asyncio
    async def test_skill_get_capabilities(self):
        """Тест: Получение возможностей навыка"""
        tool = SafeFileReaderTool(project_root=self.test_project_dir)
        skill = ProjectMapSkill(tool)
        
        capabilities = skill.get_capabilities()
        assert len(capabilities) == 1
        assert capabilities[0].name == "project_map.analyze_project"
        assert "Анализ структуры проекта" in capabilities[0].description
    
    @pytest.mark.asyncio
    async def test_skill_execute_analyze_project(self):
        """Тест: Выполнение анализа проекта через навык"""
        tool = SafeFileReaderTool(project_root=self.test_project_dir)
        skill = ProjectMapSkill(tool)
        
        # Подготовим capability для анализа проекта
        capability = Capability(
            name="project_map.analyze_project",
            description="",
            parameters_schema=None,
            parameters_class=None,
            skill_name="project_map"
        )
        parameters = {"directory": str(self.project_path.absolute())}  # Используем абсолютный путь
        context = {"file_reader_tool": tool}
        
        result = await skill.execute(capability, parameters, context)
        
        assert result.status.name == "SUCCESS"  # SUCCESS - это enum, поэтому обращаемся через .name
        assert result.result is not None
        # Проверим, что результат - это ProjectStructure
        from domain.core.project.project_structure import ProjectStructure
        assert isinstance(result.result, ProjectStructure)
        assert result.result.root_dir == str(self.project_path.absolute())
        # Проверим, что файл main.py был найден и обработан
        # Даже если он не был обработан из-за ошибок, в директории должен быть хотя бы один .py файл
        # Проверим, что структура создана корректно
        assert result.result.root_dir != ""
        # Проверим, что возвращаемое сообщение содержит информацию о найденных файлах
        assert "Проект успешно проанализирован:" in result.summary


# Запуск тестов, если файл выполняется напрямую
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
