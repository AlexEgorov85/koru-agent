"""
Тесты для моделей конфигурации (Config, LLMProviderConfig, DBProviderConfig).
"""
import pytest
from models.config import Config, LLMProviderConfig, DBProviderConfig, ConfigType


class TestConfigModel:
    """Тесты для модели Config."""
    
    def test_config_creation(self):
        """Тест создания Config."""
        config = Config(
            profile="dev",
            log_level="INFO",
            log_dir="logs",
            agent={"max_steps": 10, "default_strategy": "react"},
            llm_providers={"default": {"type": "llama_cpp", "model_path": "./models/test.gguf"}},
            db_providers={"default": {"type": "postgresql", "host": "localhost"}}
        )
        
        assert config.profile == "dev"
        assert config.log_level == "INFO"
        assert config.log_dir == "logs"
        assert config.agent == {"max_steps": 10, "default_strategy": "react"}
        assert config.llm_providers == {"default": {"type": "llama_cpp", "model_path": "./models/test.gguf"}}
        assert config.db_providers == {"default": {"type": "postgresql", "host": "localhost"}}
    
    def test_config_with_optional_fields(self):
        """Тест создания Config с опциональными полями."""
        config = Config(
            profile="production",
            log_level="ERROR",
            custom_settings={"feature_flags": ["advanced_analytics"], "limits": {"max_concurrent": 100}},
            metadata={"version": "1.0", "deployment": "aws"}
        )
        
        assert config.custom_settings == {"feature_flags": ["advanced_analytics"], "limits": {"max_concurrent": 100}}
        assert config.metadata == {"version": "1.0", "deployment": "aws"}
    
    def test_config_default_values(self):
        """Тест значений по умолчанию для Config."""
        config = Config()
        
        assert config.profile == "dev"           # значение по умолчанию
        assert config.log_level == "INFO"       # значение по умолчанию
        assert config.log_dir == "logs"         # значение по умолчанию
        assert config.agent == {"max_steps": 10, "default_strategy": "react"}  # значение по умолчанию
        assert config.llm_providers == {}       # значение по умолчанию
        assert config.db_providers == {}        # значение по умолчанию
        assert config.custom_settings == {}     # значение по умолчанию
        assert config.metadata == {}            # значение по умолчанию
    
    def test_config_equality(self):
        """Тест равенства Config."""
        config1 = Config(
            profile="test_profile",
            log_level="DEBUG"
        )
        
        config2 = Config(
            profile="test_profile",
            log_level="DEBUG"
        )
        
        config3 = Config(
            profile="different_profile",  # другое значение
            log_level="DEBUG"
        )
        
        assert config1 == config2  # одинаковые по значению
        assert config1 != config3  # разные profile
        assert config2 != config3  # разные profile
    
    def test_config_serialization(self):
        """Тест сериализации Config."""
        config = Config(
            profile="serialize_profile",
            log_level="WARNING",
            log_dir="/var/logs/app",
            agent={"max_steps": 20, "default_strategy": "planning", "temperature": 0.7},
            custom_settings={"feature_flags": ["flag1", "flag2"]},
            metadata={"env": "staging", "region": "us-east-1"}
        )
        
        data = config.model_dump()
        
        assert data["profile"] == "serialize_profile"
        assert data["log_level"] == "WARNING"
        assert data["log_dir"] == "/var/logs/app"
        assert data["agent"] == {"max_steps": 20, "default_strategy": "planning", "temperature": 0.7}
        assert data["custom_settings"] == {"feature_flags": ["flag1", "flag2"]}
        assert data["metadata"] == {"env": "staging", "region": "us-east-1"}
    
    def test_config_from_dict(self):
        """Тест создания Config из словаря."""
        data = {
            "profile": "dict_profile",
            "log_level": "ERROR",
            "log_dir": "/tmp/logs",
            "agent": {"max_steps": 30, "default_strategy": "evaluation"},
            "custom_settings": {"limits": {"max_retries": 5}},
            "metadata": {"source": "api", "timestamp": "2023-01-01T00:00:00Z"}
        }
        
        config = Config.model_validate(data)
        
        assert config.profile == "dict_profile"
        assert config.log_level == "ERROR"
        assert config.log_dir == "/tmp/logs"
        assert config.agent == {"max_steps": 30, "default_strategy": "evaluation"}
        assert config.custom_settings == {"limits": {"max_retries": 5}}
        assert config.metadata == {"source": "api", "timestamp": "2023-01-01T00:00:00Z"}


class TestLLMProviderConfigModel:
    """Тесты для модели LLMProviderConfig."""
    
    def test_llm_provider_config_creation(self):
        """Тест создания LLMProviderConfig."""
        config = LLMProviderConfig(
            type="llama_cpp",
            model_path="./models/test_model.gguf",
            enabled=True,
            parameters={"n_ctx": 2048, "temperature": 0.7}
        )
        
        assert config.type == "llama_cpp"
        assert config.model_path == "./models/test_model.gguf"
        assert config.enabled is True
        assert config.parameters == {"n_ctx": 2048, "temperature": 0.7}
    
    def test_llm_provider_config_with_optional_fields(self):
        """Тест создания LLMProviderConfig с опциональными полями."""
        config = LLMProviderConfig(
            type="openrouter",
            model_path="gpt-4",
            enabled=True,
            parameters={"max_tokens": 2048, "top_p": 0.9},
            api_key_env="OPENROUTER_API_KEY",
            base_url="https://openrouter.ai/api/v1",
            metadata={"provider_specific": "value"}
        )
        
        assert config.api_key_env == "OPENROUTER_API_KEY"
        assert config.base_url == "https://openrouter.ai/api/v1"
        assert config.metadata == {"provider_specific": "value"}
    
    def test_llm_provider_config_default_values(self):
        """Тест значений по умолчанию для LLMProviderConfig."""
        config = LLMProviderConfig(
            type="llama_cpp",
            model_path="./models/default_model.gguf"
        )
        
        assert config.enabled is True      # значение по умолчанию
        assert config.parameters == {}     # значение по умолчанию
        assert config.api_key_env is None  # значение по умолчанию
        assert config.base_url is None     # значение по умолчанию
        assert config.metadata == {}       # значение по умолчанию
    
    def test_llm_provider_config_equality(self):
        """Тест равенства LLMProviderConfig."""
        config1 = LLMProviderConfig(
            type="test_type",
            model_path="test_path",
            enabled=True
        )
        
        config2 = LLMProviderConfig(
            type="test_type",
            model_path="test_path",
            enabled=True
        )
        
        config3 = LLMProviderConfig(
            type="different_type",  # другой тип
            model_path="test_path",
            enabled=True
        )
        
        assert config1 == config2  # одинаковые по значению
        assert config1 != config3  # разные type
        assert config2 != config3  # разные type
    
    def test_llm_provider_config_serialization(self):
        """Тест сериализации LLMProviderConfig."""
        config = LLMProviderConfig(
            type="openai",
            model_path="gpt-4-turbo",
            enabled=False,
            parameters={"temperature": 0.5, "max_tokens": 4096},
            api_key_env="OPENAI_API_KEY",
            metadata={"cost_per_token": 0.00001}
        )
        
        data = config.model_dump()
        
        assert data["type"] == "openai"
        assert data["model_path"] == "gpt-4-turbo"
        assert data["enabled"] is False
        assert data["parameters"] == {"temperature": 0.5, "max_tokens": 4096}
        assert data["api_key_env"] == "OPENAI_API_KEY"
        assert data["metadata"] == {"cost_per_token": 1e-05}
    
    def test_llm_provider_config_from_dict(self):
        """Тест создания LLMProviderConfig из словаря."""
        data = {
            "type": "anthropic",
            "model_path": "claude-3-opus",
            "enabled": True,
            "parameters": {"temperature": 0.3, "top_k": 5},
            "api_key_env": "ANTHROPIC_API_KEY",
            "base_url": "https://api.anthropic.com",
            "metadata": {"supports_vision": True}
        }
        
        config = LLMProviderConfig.model_validate(data)
        
        assert config.type == "anthropic"
        assert config.model_path == "claude-3-opus"
        assert config.enabled is True
        assert config.parameters == {"temperature": 0.3, "top_k": 5}
        assert config.api_key_env == "ANTHROPIC_API_KEY"
        assert config.base_url == "https://api.anthropic.com"
        assert config.metadata == {"supports_vision": True}


class TestDBProviderConfigModel:
    """Тесты для модели DBProviderConfig."""
    
    def test_db_provider_config_creation(self):
        """Тест создания DBProviderConfig."""
        config = DBProviderConfig(
            type="postgresql",
            host="localhost",
            port=5432,
            username="test_user",
            password="test_pass",
            database="test_db",
            enabled=True,
            parameters={"pool_size": 10, "timeout": 30}
        )
        
        assert config.type == "postgresql"
        assert config.host == "localhost"
        assert config.port == 5432
        assert config.username == "test_user"
        assert config.password == "test_pass"
        assert config.database == "test_db"
        assert config.enabled is True
        assert config.parameters == {"pool_size": 10, "timeout": 30}
    
    def test_db_provider_config_with_optional_fields(self):
        """Тест создания DBProviderConfig с опциональными полями."""
        config = DBProviderConfig(
            type="mysql",
            host="mysql.example.com",
            port=3306,
            username="mysql_user",
            password="mysql_pass",
            database="mysql_db",
            enabled=True,
            parameters={"charset": "utf8mb4", "collation": "utf8mb4_unicode_ci"},
            connection_string="mysql://user:pass@host:port/db",
            ssl_enabled=True,
            metadata={"ssl_cert_path": "/path/to/cert.pem"}
        )
        
        assert config.connection_string == "mysql://user:pass@host:port/db"
        assert config.ssl_enabled is True
        assert config.metadata == {"ssl_cert_path": "/path/to/cert.pem"}
    
    def test_db_provider_config_default_values(self):
        """Тест значений по умолчанию для DBProviderConfig."""
        config = DBProviderConfig(
            type="sqlite",
            database="local.db"
        )
        
        assert config.host == "localhost"     # значение по умолчанию
        assert config.port == 5432           # значение по умолчанию
        assert config.username == "postgres"  # значение по умолчанию
        assert config.password == ""          # значение по умолчанию
        assert config.enabled is True         # значение по умолчанию
        assert config.parameters == {}        # значение по умолчанию
        assert config.connection_string is None  # значение по умолчанию
        assert config.ssl_enabled is False     # значение по умолчанию
        assert config.metadata == {}          # значение по умолчанию
    
    def test_db_provider_config_equality(self):
        """Тест равенства DBProviderConfig."""
        config1 = DBProviderConfig(
            type="test_type",
            host="test_host",
            database="test_db"
        )
        
        config2 = DBProviderConfig(
            type="test_type",
            host="test_host",
            database="test_db"
        )
        
        config3 = DBProviderConfig(
            type="different_type",  # другой тип
            host="test_host",
            database="test_db"
        )
        
        assert config1 == config2  # одинаковые по значению
        assert config1 != config3  # разные type
        assert config2 != config3  # разные type
    
    def test_db_provider_config_serialization(self):
        """Тест сериализации DBProviderConfig."""
        config = DBProviderConfig(
            type="postgres",
            host="prod-db.example.com",
            port=5433,
            username="prod_user",
            database="prod_db",
            enabled=False,
            parameters={"pool_size": 20, "statement_timeout": 60},
            ssl_enabled=True,
            metadata={"backup_frequency": "daily", "region": "eu-west-1"}
        )
        
        data = config.model_dump()
        
        assert data["type"] == "postgres"
        assert data["host"] == "prod-db.example.com"
        assert data["port"] == 5433
        assert data["username"] == "prod_user"
        assert data["database"] == "prod_db"
        assert data["enabled"] is False
        assert data["parameters"] == {"pool_size": 20, "statement_timeout": 60}
        assert data["ssl_enabled"] is True
        assert data["metadata"] == {"backup_frequency": "daily", "region": "eu-west-1"}
    
    def test_db_provider_config_from_dict(self):
        """Тест создания DBProviderConfig из словаря."""
        data = {
            "type": "redis",
            "host": "redis.example.com",
            "port": 6379,
            "database": "cache_db",
            "enabled": True,
            "parameters": {"max_connections": 100, "socket_timeout": 5},
            "ssl_enabled": False,
            "metadata": {"cluster_mode": True, "replication_enabled": True}
        }
        
        config = DBProviderConfig.model_validate(data)
        
        assert config.type == "redis"
        assert config.host == "redis.example.com"
        assert config.port == 6379
        assert config.database == "cache_db"
        assert config.enabled is True
        assert config.parameters == {"max_connections": 100, "socket_timeout": 5}
        assert config.ssl_enabled is False
        assert config.metadata == {"cluster_mode": True, "replication_enabled": True}


def test_config_type_enum_values():
    """Тест значений ConfigType enum."""
    assert ConfigType.SYSTEM.value == "system"
    assert ConfigType.LLM_PROVIDER.value == "llm_provider"
    assert ConfigType.DB_PROVIDER.value == "db_provider"
    assert ConfigType.TOOL.value == "tool"
    assert ConfigType.SKILL.value == "skill"
    
    # Проверяем все значения
    all_types = [config_type.value for config_type in ConfigType]
    expected_types = ["system", "llm_provider", "db_provider", "tool", "skill"]
    assert set(all_types) == set(expected_types)