import pytest
import tempfile
from pathlib import Path
from datetime import datetime
from unittest.mock import patch, mock_open

from core.models.prompt import Prompt, PromptStatus, PromptMetadata
from core.models.prompt_serialization import PromptSerializer
from core.infrastructure.registry.prompt_registry import PromptRegistry, PromptRegistryEntry


class TestPromptModels:
    """Тесты для базовых моделей промптов"""
    
    def test_prompt_creation_valid(self):
        """Тест создания валидного промпта"""
        metadata = PromptMetadata(
            version="1.0.0",
            skill="test_skill",
            capability="test.capability",
            author="test@example.com"
        )
        
        prompt = Prompt(
            metadata=metadata,
            content="Тестовый промпт с переменной {{ variable }}"
        )
        
        assert prompt.metadata.version == "1.0.0"
        assert prompt.metadata.skill == "test_skill"
        assert prompt.metadata.capability == "test.capability"
        assert prompt.content == "Тестовый промпт с переменной {{ variable }}"
    
    def test_prompt_version_validation(self):
        """Тест валидации формата версии"""
        with pytest.raises(ValueError):
            PromptMetadata(
                version="invalid_version",
                skill="test_skill",
                capability="test.capability",
                author="test@example.com"
            )
        
        # Проверяем, что валидные форматы проходят
        valid_versions = ["1.0.0", "v1.0.0", "2.10.5", "v10.20.30"]
        for version in valid_versions:
            metadata = PromptMetadata(
                version=version,
                skill="test_skill",
                capability="test.capability",
                author="test@example.com"
            )
            assert metadata.version == version
    
    def test_prompt_content_variable_validation(self):
        """Тест валидации переменных в контенте"""
        # Проверяем, что объявленные переменные используются в контенте
        metadata = PromptMetadata(
            version="1.0.0",
            skill="test_skill",
            capability="test.capability",
            variables=["var1", "var2"],
            author="test@example.com"
        )
        
        # Правильное использование переменных
        prompt = Prompt(
            metadata=metadata,
            content="Тест {{ var1 }} и {{ var2 }}"
        )
        assert prompt.content == "Тест {{ var1 }} и {{ var2 }}"
        
        # Неправильное использование - переменная в контенте не объявлена
        with pytest.raises(ValueError):
            Prompt(
                metadata=metadata,
                content="Тест {{ var1 }} и {{ undeclared_var }}"
            )
        
        # Неправильное использование - объявлена переменная, но не используется
        with pytest.raises(ValueError):
            Prompt(
                metadata=metadata,
                content="Тест {{ var1 }} без var2"
            )


class TestPromptSerializer:
    """Тесты для сериализации промптов"""
    
    def setup_method(self):
        self.metadata = PromptMetadata(
            version="1.0.0",
            skill="test_skill",
            capability="test.capability",
            variables=["name", "age"],
            author="test@example.com"
        )
        
        self.prompt = Prompt(
            metadata=self.metadata,
            content="Привет, меня зовут {{ name }}, мне {{ age }} лет."
        )
    
    def test_to_yaml(self):
        """Тест сериализации в YAML"""
        yaml_str = PromptSerializer.to_yaml(self.prompt)
        
        assert "version: 1.0.0" in yaml_str
        assert "skill: test_skill" in yaml_str
        assert "capability: test.capability" in yaml_str
        assert "Привет, меня зовут {{ name }}, мне {{ age }} лет." in yaml_str
    
    def test_from_yaml_string(self):
        """Тест десериализации из YAML строки"""
        yaml_str = PromptSerializer.to_yaml(self.prompt)
        loaded_prompt = PromptSerializer.from_yaml(yaml_str)
        
        assert loaded_prompt.metadata.version == self.prompt.metadata.version
        assert loaded_prompt.metadata.skill == self.prompt.metadata.skill
        assert loaded_prompt.metadata.capability == self.prompt.metadata.capability
        assert loaded_prompt.content == self.prompt.content
    
    def test_from_yaml_file(self, tmp_path):
        """Тест десериализации из YAML файла"""
        # Создаем временный файл
        yaml_file = tmp_path / "test_prompt.yaml"
        yaml_file.write_text(PromptSerializer.to_yaml(self.prompt), encoding='utf-8')
        
        loaded_prompt = PromptSerializer.from_yaml(yaml_file)
        
        assert loaded_prompt.metadata.version == self.prompt.metadata.version
        assert loaded_prompt.metadata.skill == self.prompt.metadata.skill
        assert loaded_prompt.metadata.capability == self.prompt.metadata.capability
        assert loaded_prompt.content == self.prompt.content
    
    def test_validate_jinja2_template(self):
        """Тест валидации шаблона Jinja2"""
        # Валидный шаблон
        errors = PromptSerializer.validate_jinja2_template(
            "Привет, {{ name }}!", 
            ["name"]
        )
        assert errors == {'syntax_errors': [], 'undeclared_variables': [], 'unused_variables': []}
        
        # Невалидный синтаксис
        errors = PromptSerializer.validate_jinja2_template(
            "Привет, {{ name }!", 
            ["name"]
        )
        assert len(errors['syntax_errors']) > 0
        
        # Необъявленная переменная
        errors = PromptSerializer.validate_jinja2_template(
            "Привет, {{ name }} и {{ surname }}!", 
            ["name"]
        )
        assert "surname" in errors['undeclared_variables']
        
        # Неиспользуемая переменная
        errors = PromptSerializer.validate_jinja2_template(
            "Привет, {{ name }}!", 
            ["name", "surname"]
        )
        assert "surname" in errors['unused_variables']
    
    def test_extract_variables_from_content(self):
        """Тест извлечения переменных из контента"""
        content = "Привет, {{ name }}, тебе {{ age }} лет, живешь в {{ city }}"
        variables = PromptSerializer.extract_variables_from_content(content)
        
        assert "name" in variables
        assert "age" in variables
        assert "city" in variables
        assert len(variables) == 3


class TestPromptRegistry:
    """Тесты для реестра промптов"""
    
    def setup_method(self):
        # Создаем временный файл для реестра
        self.temp_dir = tempfile.mkdtemp()
        self.registry_path = Path(self.temp_dir) / "registry.yaml"
        
        # Создаем тестовые промпты
        self.metadata1 = PromptMetadata(
            version="1.0.0",
            skill="test_skill",
            capability="test.capability1",
            variables=["var1"],
            author="test@example.com"
        )
        
        self.prompt1 = Prompt(
            metadata=self.metadata1,
            content="Тест {{ var1 }}"
        )
        
        self.metadata2 = PromptMetadata(
            version="1.1.0",
            skill="test_skill",
            capability="test.capability2",
            variables=["var2"],
            status=PromptStatus.ARCHIVED,
            author="test@example.com"
        )
        
        self.prompt2 = Prompt(
            metadata=self.metadata2,
            content="Архив {{ var2 }}"
        )
    
    def test_registry_creation(self):
        """Тест создания реестра"""
        registry = PromptRegistry(self.registry_path)
        
        assert registry.registry_path == self.registry_path
        assert isinstance(registry.active_prompts, dict)
        assert isinstance(registry.archived_prompts, dict)
    
    def test_registry_add_active_prompt(self):
        """Тест добавления активного промпта в реестр"""
        registry = PromptRegistry(self.registry_path)
        
        # Создаем запись для активного промпта
        entry = PromptRegistryEntry(
            capability=self.prompt1.metadata.capability,
            version=self.prompt1.metadata.version,
            status=PromptStatus.ACTIVE,
            file_path="test/path.yaml"
        )
        
        registry.active_prompts[self.prompt1.metadata.capability] = entry
        
        # Проверяем, что промпт добавлен
        assert self.prompt1.metadata.capability in registry.active_prompts
        assert registry.active_prompts[self.prompt1.metadata.capability].version == self.prompt1.metadata.version
    
    def test_registry_add_archived_prompt(self):
        """Тест добавления архивного промпта в реестр"""
        registry = PromptRegistry(self.registry_path)
        
        # Создаем запись для архивного промпта
        key = (self.prompt2.metadata.capability, self.prompt2.metadata.version)
        entry = PromptRegistryEntry(
            capability=self.prompt2.metadata.capability,
            version=self.prompt2.metadata.version,
            status=PromptStatus.ARCHIVED,
            file_path="test/path.yaml"
        )
        
        registry.archived_prompts[key] = entry
        
        # Проверяем, что промпт добавлен
        assert key in registry.archived_prompts
        assert registry.archived_prompts[key].version == self.prompt2.metadata.version
    
    def test_compare_versions(self):
        """Тест сравнения версий"""
        assert PromptRegistry.compare_versions("1.0.0", "1.0.0") == 0
        assert PromptRegistry.compare_versions("1.0.1", "1.0.0") == 1
        assert PromptRegistry.compare_versions("1.0.0", "1.0.1") == -1
        assert PromptRegistry.compare_versions("2.0.0", "1.9.9") == 1
        assert PromptRegistry.compare_versions("v1.0.0", "1.0.0") == 0  # без учета 'v' префикса


class TestPromptServiceIntegration:
    """Интеграционные тесты для PromptService с новой объектной моделью"""
    
    def test_get_prompt_object(self):
        """Тест получения объекта промпта"""
        # Этот тест требует интеграции с PromptService, 
        # который мы протестируем отдельно в интеграционных тестах
        pass
    
    def test_create_and_promote_prompt(self):
        """Тест создания и продвижения промпта"""
        # Этот тест также требует интеграции с PromptService
        pass


if __name__ == "__main__":
    pytest.main([__file__])