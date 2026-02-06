"""
Тесты для SystemOrchestrator с обновленной архитектурой.
"""
import pytest
from application.orchestration.system_orchestrator import SystemOrchestrator
from application.context.system.system_context import SystemContext
from domain.abstractions.system.i_skill_registry import ISkillRegistry
from domain.abstractions.system.i_tool_registry import IToolRegistry
from domain.abstractions.system.i_config_manager import IConfigManager
from domain.abstractions.event_system import IEventPublisher
from application.gateways.execution.execution_gateway import ExecutionGateway
from domain.abstractions.gateways.i_execution_gateway import IExecutionGateway


def test_system_orchestrator_creates_execution_gateway_with_ports():
    """Тестируем, что SystemOrchestrator создает ExecutionGateway с портами"""
    orchestrator = SystemOrchestrator()
    
    # Проверяем, что созданы основные компоненты
    assert isinstance(orchestrator.system_context, SystemContext)
    assert hasattr(orchestrator, 'event_system')
    
    # Создаем сессию
    import asyncio
    session = asyncio.run(orchestrator.create_session("test_session"))
    
    # Проверяем, что ExecutionGateway был создан с правильными портами
    gateway = session.get_execution_gateway()
    assert isinstance(gateway, ExecutionGateway)
    
    # Проверяем, что у сессии есть доступ к портам
    assert session.get_skill_registry() is orchestrator.system_context.skill_registry
    assert session.get_tool_registry() is orchestrator.system_context.tool_registry
    assert session.get_config_manager() is orchestrator.system_context.config_manager
    assert session.get_event_bus() is orchestrator.event_system


def test_system_context_implements_interfaces():
    """Тестируем, что SystemContext реализует нужные интерфейсы"""
    system = SystemContext()
    
    assert isinstance(system.skill_registry, ISkillRegistry)
    assert isinstance(system.tool_registry, IToolRegistry)
    assert isinstance(system.config_manager, IConfigManager)


def test_system_orchestrator_provides_correct_dependencies():
    """Тестируем, что SystemOrchestrator предоставляет правильные зависимости"""
    orchestrator = SystemOrchestrator()
    
    # Проверяем, что системный контекст содержит реестры
    assert hasattr(orchestrator.system_context, 'skill_registry')
    assert hasattr(orchestrator.system_context, 'tool_registry')
    assert hasattr(orchestrator.system_context, 'config_manager')
    
    # Проверяем, что event_system реализует интерфейс
    assert isinstance(orchestrator.event_system, IEventPublisher)