#!/usr/bin/env python3
"""
Тестирование разрешения классов компонентов
"""

import asyncio
import sys
import os

# Добавляем путь к проекту
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.application_context.application_context import ApplicationContext
from core.config.app_config import AppConfig
from core.models.data.contract import ComponentType


def test_component_resolution(fake_infra_context):
    """Тестируем разрешение классов компонентов"""

    # Создаем минимальную конфигурацию
    app_config = AppConfig(config_id="test")

    app_context = ApplicationContext(
        infrastructure_context=fake_infra_context,
        config=app_config,
        profile="prod"
    )

    # Тестируем разрешение различных компонентов
    test_components = [
        ("prompt_service", ComponentType.SERVICE),
        ("contract_service", ComponentType.SERVICE),
        ("table_description_service", ComponentType.SERVICE),
        ("sql_generation_service", ComponentType.SERVICE),
        ("sql_query_service", ComponentType.SERVICE),
        ("sql_validator_service", ComponentType.SERVICE),
    ]

    for name, comp_type in test_components:
        try:
            cls = app_context._resolve_component_class(comp_type, name)
        except Exception as e:


def test_minimal_config(fake_infra_context):
    """Тестирование с минимальной конфигурацией"""

    fake_infra = fake_infra_context

    # Создаем минимальную конфигурацию
    app_config = AppConfig(config_id="minimal_test")

    app_context = ApplicationContext(
        infrastructure_context=fake_infra,
        config=app_config,
        profile="prod"
    )

