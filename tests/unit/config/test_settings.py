"""
Юнит-тесты для Pydantic Settings конфигурации.

ЗАПУСК:
```bash
pytest tests/unit/config/test_settings.py -v
```
"""
import os
import pytest
from pathlib import Path
from core.config.settings import (
    AppConfig,
    DatabaseSettings,
    LLMSettings,
    AgentSettings,
    LoggingSettings,
    get_config,
)


class TestDatabaseSettings:
    """Тесты DatabaseSettings."""
    
    def test_default_values(self):
        """Тест: значения по умолчанию."""
        db = DatabaseSettings()
        
        assert db.host == "localhost"
        assert db.port == 5432
        assert db.database == "agent_db"
        assert db.username == "postgres"
        assert db.password == ""
        assert db.pool_size == 10
    
    def test_dsn_property(self):
        """Тест: DSN строка."""
        db = DatabaseSettings(
            host="db.example.com",
            port=5433,
            database="mydb",
            username="user",
            password="secret"
        )
        
        # DSN использует значения из полей
        assert "user:secret" in db.dsn
        assert "db.example.com:5433" in db.dsn
        assert "mydb" in db.dsn
    
    def test_invalid_port(self):
        """Тест: невалидный порт."""
        with pytest.raises(ValueError, match="Port must be between"):
            DatabaseSettings(port=80)
    
    def test_repr_hides_password(self):
        """Тест: repr скрывает пароль."""
        db = DatabaseSettings(password="secret")
        repr_str = repr(db)
        
        assert "secret" not in repr_str
        assert "DatabaseSettings" in repr_str


class TestLLMSettings:
    """Тесты LLMSettings."""
    
    def test_default_values(self):
        """Тест: значения по умолчанию."""
        llm = LLMSettings()
        
        assert llm.provider == "llama"
        assert llm.model == "mistral-7b-instruct"
        assert llm.temperature == 0.7
        assert llm.timeout_seconds == 120.0
    
    def test_is_local_property(self):
        """Тест: is_local для локальных провайдеров."""
        llama = LLMSettings(provider="llama")
        vllm = LLMSettings(provider="vllm")
        openai = LLMSettings(provider="openai")
        
        assert llama.is_local is True
        assert vllm.is_local is True
        assert openai.is_local is False
    
    def test_is_cloud_property(self):
        """Тест: is_cloud для облачных провайдеров."""
        openai = LLMSettings(provider="openai")
        anthropic = LLMSettings(provider="anthropic")
        llama = LLMSettings(provider="llama")
        
        assert openai.is_cloud is True
        assert anthropic.is_cloud is True
        assert llama.is_cloud is False
    
    def test_invalid_temperature_high(self):
        """Тест: температура выше 2."""
        from pydantic_core import ValidationError
        
        with pytest.raises(ValidationError, match="less_than_equal"):
            LLMSettings(temperature=3.0)
    
    def test_invalid_temperature_low(self):
        """Тест: температура ниже 0."""
        from pydantic_core import ValidationError
        
        with pytest.raises(ValidationError, match="greater_than_equal"):
            LLMSettings(temperature=-0.5)
    
    def test_valid_temperature_boundary(self):
        """Тест: граничные значения температуры."""
        llm_low = LLMSettings(temperature=0.0)
        llm_high = LLMSettings(temperature=2.0)
        
        assert llm_low.temperature == 0.0
        assert llm_high.temperature == 2.0


class TestAgentSettings:
    """Тесты AgentSettings."""
    
    def test_default_values(self):
        """Тест: значения по умолчанию."""
        agent = AgentSettings()
        
        assert agent.max_steps == 10
        assert agent.max_retries == 3
        assert agent.timeout_seconds == 300.0
        assert agent.enable_self_reflection is True
    
    def test_invalid_max_steps_low(self):
        """Тест: max_steps меньше 1."""
        with pytest.raises(ValueError, match="max_steps"):
            AgentSettings(max_steps=0)
    
    def test_invalid_max_steps_high(self):
        """Тест: max_steps больше 100."""
        with pytest.raises(ValueError, match="max_steps"):
            AgentSettings(max_steps=101)
    
    def test_valid_max_steps_boundary(self):
        """Тест: граничные значения max_steps."""
        agent_low = AgentSettings(max_steps=1)
        agent_high = AgentSettings(max_steps=100)
        
        assert agent_low.max_steps == 1
        assert agent_high.max_steps == 100


class TestLoggingSettings:
    """Тесты LoggingSettings."""
    
    def test_default_values(self):
        """Тест: значения по умолчанию."""
        logging = LoggingSettings()
        
        assert logging.level == "INFO"
        assert logging.format == "simple"
        assert logging.file_enabled is True
        assert logging.console_enabled is True
    
    def test_valid_log_levels(self):
        """Тест: допустимые уровни логирования."""
        for level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            log = LoggingSettings(level=level)
            assert log.level == level
    
    def test_invalid_log_level(self):
        """Тест: недопустимый уровень."""
        with pytest.raises(ValueError):
            LoggingSettings(level="TRACE")


class TestAppConfig:
    """Тесты AppConfig."""
    
    def test_default_values(self):
        """Тест: значения по умолчанию."""
        config = AppConfig()
        
        assert config.profile == "dev"
        assert config.config_id == "app_config"
        assert isinstance(config.database, DatabaseSettings)
        assert isinstance(config.llm, LLMSettings)
        assert isinstance(config.agent, AgentSettings)
        assert isinstance(config.logging, LoggingSettings)
    
    def test_nested_settings_access(self):
        """Тест: доступ к вложенным настройкам."""
        config = AppConfig()
        
        # Database
        assert config.database.host == "localhost"
        
        # LLM
        assert config.llm.provider == "llama"
        
        # Agent
        assert config.agent.max_steps == 10
        
        # Logging
        assert config.logging.level == "INFO"
    
    def test_profile_sync(self):
        """Тест: синхронизация профиля."""
        config = AppConfig(profile="prod")
        
        assert config.profile == "prod"
        assert config.agent.profile == "prod"
    
    def test_validate_all_success(self):
        """Тест: валидация без ошибок."""
        config = AppConfig(
            profile="dev",
            llm={"provider": "llama"}  # Локальный провайдер не требует api_key
        )
        
        errors = config.validate_all()
        
        # В dev режиме может быть warning о DEBUG логах
        assert len(errors) == 0 or any("DEBUG" in e for e in errors)
    
    def test_validate_cloud_llm_no_api_key(self):
        """Тест: облачный LLM без api_key."""
        config = AppConfig(
            profile="prod",
            llm={"provider": "openai", "api_key": None}
        )
        
        errors = config.validate_all()
        
        assert any("api_key" in e for e in errors)
    
    def test_validate_prod_debug_logging(self):
        """Тест: production с DEBUG логированием."""
        config = AppConfig(
            profile="prod",
            llm={"provider": "llama"},
            logging={"level": "DEBUG"}
        )
        
        errors = config.validate_all()
        
        assert any("DEBUG" in e for e in errors)
    
    def test_data_dir_creation(self):
        """Тест: создание директорий."""
        import tempfile
        
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "new_data_dir"
            
            config = AppConfig(data_dir=data_dir)
            
            assert data_dir.exists()
            assert data_dir.is_dir()
    
    def test_repr(self):
        """Тест: строковое представление."""
        config = AppConfig(profile="prod")
        repr_str = repr(config)
        
        assert "AppConfig" in repr_str
        assert "prod" in repr_str


class TestGetConfig:
    """Тесты factory функций."""
    
    def test_get_config_default(self):
        """Тест: получение конфигурации по умолчанию."""
        config = get_config()
        
        assert config.profile == "dev"
    
    def test_get_config_with_profile(self):
        """Тест: получение конфигурации с профилем."""
        config = get_config(profile="sandbox")
        
        assert config.profile == "sandbox"
        assert config.agent.profile == "sandbox"
    
    def test_get_database_config(self):
        """Тест: получение настроек БД."""
        from core.config.settings import get_database_config
        
        db = get_database_config()
        
        assert isinstance(db, DatabaseSettings)
        assert db.host == "localhost"
    
    def test_get_llm_config(self):
        """Тест: получение настроек LLM."""
        from core.config.settings import get_llm_config
        
        llm = get_llm_config()
        
        assert isinstance(llm, LLMSettings)
        assert llm.provider == "llama"
    
    def test_get_agent_config(self):
        """Тест: получение настроек агента."""
        from core.config.settings import get_agent_config
        
        agent = get_agent_config()
        
        assert isinstance(agent, AgentSettings)
        assert agent.max_steps == 10


class TestEnvironmentVariables:
    """Тесты переменных окружения."""
    
    def test_env_override_database(self, monkeypatch):
        """Тест: переопределение через env vars."""
        monkeypatch.setenv("AGENT_DB_HOST", "env-db.example.com")
        monkeypatch.setenv("AGENT_DB_PORT", "5433")
        
        db = DatabaseSettings()
        
        assert db.host == "env-db.example.com"
        assert db.port == 5433
    
    def test_env_override_llm(self, monkeypatch):
        """Тест: переопределение LLM через env vars."""
        monkeypatch.setenv("AGENT_LLM_PROVIDER", "openai")
        monkeypatch.setenv("AGENT_LLM_MODEL", "gpt-4")
        monkeypatch.setenv("AGENT_LLM_TEMPERATURE", "0.5")
        
        llm = LLMSettings()
        
        assert llm.provider == "openai"
        assert llm.model == "gpt-4"
        assert llm.temperature == 0.5
    
    def test_env_override_agent(self, monkeypatch):
        """Тест: переопределение агента через env vars."""
        monkeypatch.setenv("AGENT_MAX_STEPS", "20")
        monkeypatch.setenv("AGENT_MAX_RETRIES", "5")
        
        agent = AgentSettings()
        
        assert agent.max_steps == 20
        assert agent.max_retries == 5
    
    def test_env_override_logging(self, monkeypatch):
        """Тест: переопределение логирования через env vars."""
        monkeypatch.setenv("AGENT_LOG_LEVEL", "DEBUG")
        monkeypatch.setenv("AGENT_LOG_FORMAT", "json")
        
        logging = LoggingSettings()
        
        assert logging.level == "DEBUG"
        assert logging.format == "json"
