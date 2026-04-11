"""
Фикстуры для интеграционных тестов.

ПРИНЦИПЫ:
- Минимум кода
- Реальная инфраструктура (InfrastructureContext, ApplicationContext)
- Никаких моков (кроме опциональных для LLM)
- Те же условия, что в production (main.py)
"""
import pytest
from pathlib import Path

from core.config import get_config
from core.infrastructure_context.infrastructure_context import InfrastructureContext
from core.application_context.application_context import ApplicationContext
from core.config.app_config import AppConfig
from core.session_context.session_context import SessionContext


# ============================================================================
# БАЗОВЫЕ ФИКСТУРЫ
# ============================================================================

@pytest.fixture(scope="session")
def config():
    """
    Та же конфигурация, что и в main.py (profile='dev').
    
    Кэшируется один раз на всю сессию тестов.
    """
    return get_config(profile='dev')


@pytest.fixture(scope="function")
async def infrastructure(config):
    """
    Реальный InfrastructureContext.
    
    Инициализируется для каждого теста, чтобы обеспечить изоляцию.
    """
    infra = InfrastructureContext(config)
    await infra.initialize()
    yield infra
    await infra.shutdown()


@pytest.fixture(scope="function")
async def app_context(infrastructure):
    """
    Реальный ApplicationContext с авто-обнаружением ресурсов.
    
    Использует тот же профиль и data_dir, что и infrastructure.
    """
    app_config = AppConfig.from_discovery(
        profile="dev",
        data_dir=infrastructure.config.data_dir
    )
    ctx = ApplicationContext(
        infrastructure_context=infrastructure,
        config=app_config,
        profile="dev"
    )
    await ctx.initialize()
    yield ctx
    await ctx.shutdown()


@pytest.fixture
def session_context():
    """
    Свежий контекст сессии.
    
    Используется для передачи в execute() навыков.
    """
    return SessionContext()


# ============================================================================
# ФИКСТУРЫ ДЛЯ ТЕСТОВ С БД
# ============================================================================

@pytest.fixture
async def db_transaction(infrastructure):
    """
    Транзакция с откатом для тестов, которые могут писать в БД.
    
    Используется для навыков с side_effects_enabled=True.
    BEGIN → тест → ROLLBACK
    """
    db = infrastructure.get_provider("default_db")
    if db is None:
        pytest.skip("БД провайдер не доступен")
    
    await db.execute("BEGIN")
    try:
        yield
    finally:
        await db.execute("ROLLBACK")


# ============================================================================
# ФИКСТУРЫ ДЛЯ ПОЛУЧЕНИЯ КОМПОНЕНТОВ
# ============================================================================

@pytest.fixture
def book_library_skill(app_context):
    """
    Получение навыка book_library из ApplicationContext.
    """
    from core.models.enums.common_enums import ComponentType
    
    skill = app_context.components.get(ComponentType.TOOL, "book_library")
    if skill is None:
        pytest.skip("Навык book_library не найден в реестре")
    
    return skill


@pytest.fixture
def get_capability(book_library_skill):
    """
    Factory для получения capability по имени.
    """
    def _get(capability_name: str):
        caps = book_library_skill.get_capabilities()
        for cap in caps:
            if cap.name == capability_name:
                return cap
        pytest.skip(f"Capability {capability_name} не найдена")
    
    return _get
