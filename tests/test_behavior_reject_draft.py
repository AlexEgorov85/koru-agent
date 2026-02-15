import pytest
import tempfile
import os
from unittest.mock import Mock, patch, AsyncMock

from core.application.storage.behavior.behavior_storage import BehaviorStorage


@pytest.mark.asyncio
async def test_production_rejects_draft_patterns():
    """Тест отклонения draft версий паттернов в продакшн окружении"""
    
    # Создаем временный каталог для тестирования
    with tempfile.TemporaryDirectory() as temp_dir:
        # Создаем подкаталоги для паттернов
        behaviors_dir = os.path.join(temp_dir, "behaviors", "react")
        os.makedirs(behaviors_dir, exist_ok=True)
        
        # Создаем файл draft версии
        draft_yaml_content = """version: "1.0.0-draft"
pattern_id: "react.v1.0.0-draft"
name: "ReAct Draft"
description: "Draft version of ReAct pattern"
supported_skills: ["book_library", "sql_query"]
required_capabilities: ["generic.execute"]
context_requirements:
  min_steps: 0
  max_steps: 10
status: "draft"  # Это черновик
quality_metrics:
  success_rate: 0.93
  avg_decision_time_ms: 450
created_at: "2026-02-15T10:00:00Z"
"""
        
        draft_file_path = os.path.join(behaviors_dir, "v1.0.0-draft.yaml")
        with open(draft_file_path, 'w', encoding='utf-8') as f:
            f.write(draft_yaml_content)
        
        # Создаем файл active версии
        active_yaml_content = """version: "1.0.0"
pattern_id: "react.v1.0.0"
name: "ReAct"
description: "Active version of ReAct pattern"
supported_skills: ["book_library", "sql_query"]
required_capabilities: ["generic.execute"]
context_requirements:
  min_steps: 0
  max_steps: 10
status: "active"  # Это активная версия
quality_metrics:
  success_rate: 0.93
  avg_decision_time_ms: 450
created_at: "2026-02-15T10:00:00Z"
"""
        
        active_file_path = os.path.join(behaviors_dir, "v1.0.0.yaml")
        with open(active_file_path, 'w', encoding='utf-8') as f:
            f.write(active_yaml_content)
        
        # Создаем mock сервисов
        mock_prompt_service = Mock()
        
        # Создаем BehaviorStorage с временным каталогом
        storage = BehaviorStorage(data_dir=temp_dir, prompt_service=mock_prompt_service)
        
        # Проверяем, что активная версия загружается успешно
        try:
            active_pattern = await storage.load_pattern("react.v1.0.0")
            assert active_pattern is not None
            assert "react.v1.0.0" in str(active_pattern.pattern_id)
        except Exception as e:
            pytest.fail(f"Активная версия не должна быть отклонена: {e}")
        
        # Проверяем, что draft версия отклоняется
        with pytest.raises(ValueError, match=r".*not active \(status: draft\)"):
            await storage.load_pattern("react.v1.0.0-draft")


@pytest.mark.asyncio
async def test_behavior_storage_status_validation():
    """Тест валидации статуса паттернов в BehaviorStorage"""
    
    # Создаем временный каталог для тестирования
    with tempfile.TemporaryDirectory() as temp_dir:
        # Создаем подкаталоги для паттернов
        behaviors_dir = os.path.join(temp_dir, "behaviors", "planning")
        os.makedirs(behaviors_dir, exist_ok=True)
        
        # Создаем файл с разными статусами
        statuses = ["active", "draft", "deprecated", "archived"]
        
        for status in statuses:
            yaml_content = f"""version: "1.0.0-{status}"
pattern_id: "planning.v1.0.0-{status}"
name: "Planning {status.title()}"
description: "{status.title()} version of Planning pattern"
supported_skills: ["planning"]
required_capabilities: ["planning.create_plan"]
context_requirements:
  min_steps: 0
  max_steps: 50
status: "{status}"
quality_metrics:
  success_rate: 0.85
  avg_decision_time_ms: 650
created_at: "2026-02-15T10:00:00Z"
"""
            
            file_path = os.path.join(behaviors_dir, f"v1.0.0-{status}.yaml")
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(yaml_content)
        
        # Создаем mock сервисов
        mock_prompt_service = Mock()
        
        # Создаем BehaviorStorage с временным каталогом
        storage = BehaviorStorage(data_dir=temp_dir, prompt_service=mock_prompt_service)
        
        # Проверяем, что только active версии загружаются
        # (в реальной системе могут быть и другие разрешенные статусы, кроме active)
        
        # Active должна загружаться
        try:
            active_pattern = await storage.load_pattern("planning.v1.0.0-active")
            assert active_pattern is not None
        except Exception as e:
            pytest.fail(f"Active версия должна загружаться: {e}")
        
        # Draft, deprecated и archived должны отклоняться в продакшене
        for status in ["draft", "deprecated", "archived"]:
            with pytest.raises(ValueError, match=r".*not active \(status:.*"):
                await storage.load_pattern(f"planning.v1.0.0-{status}")


@pytest.mark.asyncio
async def test_list_patterns_by_status():
    """Тест списка паттернов по статусу"""
    
    # Создаем временный каталог для тестирования
    with tempfile.TemporaryDirectory() as temp_dir:
        # Создаем подкаталоги для паттернов
        behaviors_dir = os.path.join(temp_dir, "behaviors", "evaluation")
        os.makedirs(behaviors_dir, exist_ok=True)
        
        # Создаем файлы с разными статусами
        for i, status in enumerate(["active", "draft", "active"]):
            yaml_content = f"""version: "1.0.{i}"
pattern_id: "evaluation.v1.0.{i}"
name: "Evaluation Version 1.0.{i}"
description: "Version 1.0.{i} of Evaluation pattern"
supported_skills: ["evaluation"]
required_capabilities: ["evaluation.assess_goal"]
context_requirements:
  min_steps: 0
  max_steps: 5
status: "{status}"
quality_metrics:
  success_rate: 0.95
  avg_decision_time_ms: 300
created_at: "2026-02-15T10:00:00Z"
"""
            
            file_path = os.path.join(behaviors_dir, f"v1.0.{i}.yaml")
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(yaml_content)
        
        # Создаем mock сервисов
        mock_prompt_service = Mock()
        
        # Создаем BehaviorStorage с временным каталогом
        storage = BehaviorStorage(data_dir=temp_dir, prompt_service=mock_prompt_service)
        
        # Получаем список паттернов для типа evaluation
        available_patterns = storage.list_patterns_by_type("evaluation")
        
        # Должны быть только active паттерны (2 штуки: v1.0.0 и v1.0.2)
        assert len(available_patterns) == 2
        assert "evaluation.v1.0.0" in available_patterns
        assert "evaluation.v1.0.2" in available_patterns
        # v1.0.1 не должен быть в списке, так как статус draft
        assert "evaluation.v1.0.1" not in available_patterns