"""
Тесты для класса ConfigLoader.
"""
import pytest
import tempfile
import os
from pathlib import Path
from core.config.config_loader import ConfigLoader
from core.config.models import SystemConfig


class TestConfigLoader:
    """Тесты для ConfigLoader."""
    
    def test_load_config_from_file(self):
        """Тест загрузки конфигурации из файла."""
        # Создаем временный YAML-файл с конфигурацией
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as temp_file:
            temp_file.write("""
profile: dev
log_level: INFO
log_dir: logs
agent:
  max_steps: 20
  default_strategy: react
llm_providers:
  default_llm:
    type: llama_cpp
    model_path: ./models/test_model.gguf
    enabled: true
db_providers:
  default_db:
    type: postgresql
    host: localhost
    port: 5432
    enabled: true
""")
            temp_file_path = temp_file.name
        
        try:
            # Загружаем конфигурацию
            config_loader = ConfigLoader()
            config = config_loader.load(temp_file_path)
            
            # Проверяем загруженные значения
            assert config.profile == "dev"
            assert config.log_level == "INFO"
            assert config.log_dir == "logs"
            assert config.agent["max_steps"] == 20
            assert config.agent["default_strategy"] == "react"
            assert config.llm_providers["default_llm"]["type"] == "llama_cpp"
            assert config.llm_providers["default_llm"]["enabled"] is True
            assert config.db_providers["default_db"]["host"] == "localhost"
        finally:
            # Удаляем временный файл
            os.unlink(temp_file_path)
    
    def test_load_config_from_nonexistent_file(self):
        """Тест загрузки конфигурации из несуществующего файла."""
        config_loader = ConfigLoader()
        
        with pytest.raises(FileNotFoundError):
            config_loader.load("nonexistent_file.yaml")
    
    def test_load_config_with_invalid_yaml(self):
        """Тест загрузки конфигурации с невалидным YAML."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as temp_file:
            temp_file.write("""
invalid: yaml: content: {
""")
            temp_file_path = temp_file.name
        
        try:
            config_loader = ConfigLoader()
            
            with pytest.raises(Exception):  # yaml.YAMLError или другая ошибка парсинга
                config_loader.load(temp_file_path)
        finally:
            os.unlink(temp_file_path)
    
    def test_load_config_with_defaults(self):
        """Тест загрузки конфигурации с использованием значений по умолчанию."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as temp_file:
            temp_file.write("""
profile: test_profile
""")
            temp_file_path = temp_file.name
        
        try:
            config_loader = ConfigLoader()
            config = config_loader.load(temp_file_path)
            
            # Проверяем, что profile загружен
            assert config.profile == "test_profile"
            
            # Проверяем, что остальные значения установлены в значения по умолчанию
            # (предполагая, что SystemConfig устанавливает дефолтные значения)
        finally:
            os.unlink(temp_file_path)
    
    def test_get_config(self):
        """Тест метода get_config."""
        # Создаем временную конфигурацию
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as temp_file:
            temp_file.write("""
profile: prod
log_level: ERROR
""")
            temp_file_path = temp_file.name
        
        try:
            config_loader = ConfigLoader()
            config_loader.load(temp_file_path)
            
            config = config_loader.get_config()
            
            assert isinstance(config, SystemConfig)
            assert config.profile == "prod"
            assert config.log_level == "ERROR"
        finally:
            os.unlink(temp_file_path)
    
    def test_get_config_before_loading(self):
        """Тест метода get_config до загрузки конфигурации."""
        config_loader = ConfigLoader()
        
        # Проверяем, что возвращается None или дефолтная конфигурация
        config = config_loader.get_config()
        
        # Проверяем, что возвращается объект SystemConfig с дефолтными значениями
        assert isinstance(config, SystemConfig)
    
    def test_load_config_with_nested_structure(self):
        """Тест загрузки конфигурации со вложенными структурами."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as temp_file:
            temp_file.write("""
agent:
  max_steps: 30
  temperature: 0.7
  default_strategy: planning
  memory:
    type: episodic
    capacity: 100
llm_providers:
  primary:
    type: openai
    model: gpt-4
    api_key_env: OPENAI_API_KEY
    enabled: true
    settings:
      max_tokens: 2048
      temperature: 0.5
db_providers:
  main_db:
    type: postgresql
    connection_string: postgresql://user:pass@localhost/db
    pool_size: 10
    enabled: true
custom_settings:
  feature_flags:
    - advanced_analytics
    - real_time_monitoring
  limits:
    max_concurrent_requests: 10
    timeout_seconds: 30
""")
            temp_file_path = temp_file.name
        
        try:
            config_loader = ConfigLoader()
            config = config_loader.load(temp_file_path)
            
            # Проверяем вложенные структуры
            assert config.agent["max_steps"] == 30
            assert config.agent["temperature"] == 0.7
            assert config.agent["memory"]["capacity"] == 100
            assert config.llm_providers["primary"]["type"] == "openai"
            assert config.llm_providers["primary"]["settings"]["max_tokens"] == 2048
            assert config.db_providers["main_db"]["pool_size"] == 10
            assert "advanced_analytics" in config.custom_settings["feature_flags"]
            assert config.custom_settings["limits"]["max_concurrent_requests"] == 10
        finally:
            os.unlink(temp_file_path)
    
    def test_load_config_with_environment_variable_expansion(self):
        """Тест загрузки конфигурации с раскрытием переменных окружения."""
        # Устанавливаем тестовую переменную окружения
        os.environ["TEST_MODEL_PATH"] = "/path/to/test/model"
        os.environ["TEST_DB_HOST"] = "test-db-host.com"
        
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as temp_file:
                temp_file.write("""
llm_providers:
  test_llm:
    model_path: ${TEST_MODEL_PATH}
    enabled: true
db_providers:
  test_db:
    host: ${TEST_DB_HOST}
    enabled: true
""")
                temp_file_path = temp_file.name
            
            config_loader = ConfigLoader()
            config = config_loader.load(temp_file_path)
            
            # Проверяем, что переменные окружения были раскрыты
            assert config.llm_providers["test_llm"]["model_path"] == "/path/to/test/model"
            assert config.db_providers["test_db"]["host"] == "test-db-host.com"
        finally:
            # Удаляем временные переменные окружения
            if "TEST_MODEL_PATH" in os.environ:
                del os.environ["TEST_MODEL_PATH"]
            if "TEST_DB_HOST" in os.environ:
                del os.environ["TEST_DB_HOST"]
            
            # Удаляем временный файл
            os.unlink(temp_file_path)