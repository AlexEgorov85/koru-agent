"""
Тесты для контекста агента.

Цель:
- проверить корректность работы двухуровневого контекста
- покрыть основные сценарии agent runtime
- зафиксировать ожидаемое поведение через тесты

Тесты написаны с использованием pytest.
"""

import time
from datetime import timedelta

import pytest

from core.session_context.model import ContextItem, ContextItemMetadata
from core.session_context.model import ContextItemType
from core.session_context.session_context import SessionContext




# ----------------------------------------------------------
# Вспомогательные функции
# ----------------------------------------------------------

def create_context_item(session_id: str, item_type: ContextItemType, content: str, step_number: int | None = None):
    """
    Утилита для создания ContextItem.

    Используется в тестах для сокращения boilerplate-кода.
    """
    return ContextItem(
        session_id=session_id,
        item_type=item_type,
        content=content,
        metadata=ContextItemMetadata(step_number=step_number),
    )


# ----------------------------------------------------------
# DataContext tests
# ----------------------------------------------------------

def test_data_context_add_and_get_item():
    """
    Проверяем, что DataContext корректно:
    - добавляет элементы
    - возвращает их по item_id
    """
    ctx = SessionContext()

    item = create_context_item(ctx.session_id, ContextItemType.USER_QUERY, "test query")
    item_id = ctx.data_context.add_item(item)

    fetched = ctx.data_context.get_item(item_id)

    assert fetched is item
    assert fetched.content == "test query"


def test_data_context_is_append_only():
    """
    DataContext должен работать как append-only хранилище.
    """
    ctx = SessionContext()

    item1 = create_context_item(ctx.session_id, ContextItemType.USER_QUERY, "q1")
    item2 = create_context_item(ctx.session_id, ContextItemType.USER_QUERY, "q2")

    ctx.data_context.add_item(item1)
    ctx.data_context.add_item(item2)

    assert ctx.data_context.count() == 2


# ----------------------------------------------------------
# StepContext / AgentStep tests
# ----------------------------------------------------------

def test_register_single_step():
    """
    Проверка регистрации одного шага агента.
    """
    ctx = SessionContext()

    action = create_context_item(ctx.session_id, ContextItemType.ACTION, "action")
    action_id = ctx.data_context.add_item(action)

    obs = create_context_item(ctx.session_id, ContextItemType.TOOL_RESULT, "result")
    obs_id = ctx.data_context.add_item(obs)

    ctx.register_step(
        step_number=1,
        capability_name="planning.create_plan",
        skill_name="PlanningSkill",
        action_item_id=action_id,
        observation_item_ids=[obs_id],
        summary="Создан первичный план",
    )

    assert len(ctx.step_context.steps) == 1

    step = ctx.step_context.steps[0]
    assert step.step_number == 1
    assert step.capability_name == "planning.create_plan"
    assert step.observation_item_ids == [obs_id]


def test_multiple_steps_and_order():
    """
    Проверка корректного порядка шагов.
    """
    ctx = SessionContext()

    for i in range(3):
        action = create_context_item(ctx.session_id, ContextItemType.ACTION, f"action-{i}")
        action_id = ctx.data_context.add_item(action)

        obs = create_context_item(ctx.session_id, ContextItemType.TOOL_RESULT, f"result-{i}")
        obs_id = ctx.data_context.add_item(obs)

        ctx.register_step(
            step_number=i + 1,
            capability_name="generic.capability",
            skill_name="GenericSkill",
            action_item_id=action_id,
            observation_item_ids=[obs_id],
        )

    last_steps = ctx.step_context.get_last_steps(2)

    assert len(last_steps) == 2
    assert last_steps[0].step_number == 2
    assert last_steps[1].step_number == 3


# ----------------------------------------------------------
# Планирование
# ----------------------------------------------------------

def test_set_and_get_current_plan():
    """
    Проверяем:
    - установка текущего плана
    - получение плана по ссылке
    """
    ctx = SessionContext()

    plan = create_context_item(ctx.session_id, ContextItemType.EXECUTION_PLAN, "plan v1")
    plan_id = ctx.data_context.add_item(plan)

    ctx.set_current_plan(plan_id)

    fetched_plan = ctx.get_current_plan()

    assert fetched_plan is plan
    assert fetched_plan.content == "plan v1"


# ----------------------------------------------------------
# TTL / жизненный цикл
# ----------------------------------------------------------

def test_session_expiration():
    """
    Проверка истечения TTL сессии.
    """
    ctx = SessionContext()

    # Имитируем бездействие
    ctx.last_activity -= timedelta(minutes=120)

    assert ctx.is_expired(ttl_minutes=60) is True


def test_session_not_expired_when_active():
    """
    Проверяем, что активная сессия не считается истёкшей.
    """
    ctx = SessionContext()
    assert ctx.is_expired(ttl_minutes=60) is False
