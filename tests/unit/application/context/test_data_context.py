"""
Тесты для DataContext - компонента управления контекстом данных.

Принципы тестирования:
1. Тесты описывают поведение, а не реализацию
2. Минимизация моков - разрешены только TestLLMProvider и InMemoryDBProvider
3. Запрещено мокировать тестируемые компоненты (DataContext, StepContext, SessionContext)
4. Тесты служат спецификацией поведения системы
"""

import pytest
from datetime import datetime
from typing import Any, Dict, List, Optional

from application.context.session.session_context import ContextItem, ContextItemType, ContextItemMetadata, DataContext
from pydantic import BaseModel, ValidationError


def test_add_item_generates_unique_id():
    """
    При добавлении элемента генерируется уникальный ID в формате 'ctx_{counter}_{random}'
    """
    data_context = DataContext()
    
    # Добавляем элемент без ID
    item = ContextItem(
        item_id="",
        session_id="session_1",
        item_type=ContextItemType.USER_QUERY,
        content="test query"
    )
    
    generated_id = data_context.add_item(item)
    
    # Проверяем, что ID был сгенерирован
    assert generated_id.startswith("ctx_")
    assert len(generated_id) > 4  # Должен быть длиннее префикса
    
    # Проверяем, что ID теперь связан с элементом
    retrieved_item = data_context.get_item(generated_id)
    assert retrieved_item.item_id == generated_id


def test_get_item_returns_exact_match_or_none():
    """
    get_item возвращает элемент по точному совпадению ID или None если не найден
    """
    data_context = DataContext()
    
    # Добавляем элемент
    item = ContextItem(
        item_id="",
        session_id="session_1",
        item_type=ContextItemType.USER_QUERY,
        content="test query"
    )
    item_id = data_context.add_item(item)
    
    # Проверяем, что элемент находится по ID
    retrieved_item = data_context.get_item(item_id)
    assert retrieved_item.item_id == item_id
    assert retrieved_item.content == "test query"
    
    # Проверяем, что несуществующий ID возвращает None
    non_existent_item = data_context.get_item("non_existent_id")
    assert non_existent_item is None


def test_update_item_modifies_content_and_timestamp():
    """
    update_item изменяет содержимое и обновляет updated_at, возвращает False для несуществующего ID
    """
    data_context = DataContext()
    
    # Добавляем элемент
    item = ContextItem(
        item_id="",
        session_id="session_1",
        item_type=ContextItemType.USER_QUERY,
        content="original query"
    )
    item_id = data_context.add_item(item)
    
    original_updated_at = data_context.get_item(item_id).updated_at
    
    # Обновляем элемент
    success = data_context.update_item(item_id, content="updated query")
    
    # Проверяем, что обновление прошло успешно
    assert success is True
    
    # Проверяем, что содержимое изменилось
    updated_item = data_context.get_item(item_id)
    assert updated_item.content == "updated query"
    
    # Проверяем, что updated_at обновилось
    assert updated_item.updated_at > original_updated_at
    
    # Проверяем, что обновление несуществующего элемента возвращает False
    nonexistent_update = data_context.update_item("nonexistent", content="some content")
    assert nonexistent_update is False


def test_get_all_items_returns_sorted_by_creation_time():
    """
    get_all_items возвращает элементы, отсортированные по времени создания (от старых к новым)
    """
    data_context = DataContext()
    
    # Добавляем элементы в определенном порядке
    item1 = ContextItem(
        item_id="",
        session_id="session_1",
        item_type=ContextItemType.USER_QUERY,
        content="first query"
    )
    id1 = data_context.add_item(item1)
    
    item2 = ContextItem(
        item_id="",
        session_id="session_1",
        item_type=ContextItemType.ACTION,
        content="second action"
    )
    id2 = data_context.add_item(item2)
    
    item3 = ContextItem(
        item_id="",
        session_id="session_1",
        item_type=ContextItemType.OBSERVATION,
        content="third observation"
    )
    id3 = data_context.add_item(item3)
    
    # Получаем все элементы
    all_items = data_context.get_all_items()
    
    # Проверяем, что элементы возвращаются в порядке создания (от старых к новым)
    assert len(all_items) == 3
    assert all_items[0].item_id == id1
    assert all_items[1].item_id == id2
    assert all_items[2].item_id == id3


def test_get_last_items_returns_latest_elements():
    """
    get_last_items(n) возвращает последние N элементов (новейшие)
    """
    data_context = DataContext()
    
    # Добавляем несколько элементов
    ids = []
    for i in range(5):
        item = ContextItem(
            item_id="",
            session_id="session_1",
            item_type=ContextItemType.USER_QUERY,
            content=f"query {i}"
        )
        ids.append(data_context.add_item(item))
    
    # Получаем последние 3 элемента
    last_items = data_context.get_last_items(3)
    
    # Проверяем, что возвращается 3 элемента
    assert len(last_items) == 3
    
    # Проверяем, что это последние добавленные элементы (новейшие)
    assert last_items[0].item_id == ids[2]  # четвертый элемент (индекс 3)
    assert last_items[1].item_id == ids[3]  # пятый элемент (индекс 4)
    assert last_items[2].item_id == ids[4]  # шестой элемент (индекс 5)


def test_get_items_by_type_filters_by_type():
    """
    get_items_by_type фильтрует элементы по типу и сортирует по времени
    """
    data_context = DataContext()
    
    # Добавляем элементы разных типов
    item1 = ContextItem(
        item_id="",
        session_id="session_1",
        item_type=ContextItemType.USER_QUERY,
        content="query 1"
    )
    query_id1 = data_context.add_item(item1)
    
    item2 = ContextItem(
        item_id="",
        session_id="session_1",
        item_type=ContextItemType.ACTION,
        content="action 1"
    )
    action_id = data_context.add_item(item2)
    
    item3 = ContextItem(
        item_id="",
        session_id="session_1",
        item_type=ContextItemType.USER_QUERY,
        content="query 2"
    )
    query_id2 = data_context.add_item(item3)
    
    # Получаем элементы типа USER_QUERY
    query_items = data_context.get_items_by_type(ContextItemType.USER_QUERY)
    
    # Проверяем, что возвращаются только элементы типа USER_QUERY
    assert len(query_items) == 2
    for item in query_items:
        assert item.item_type == ContextItemType.USER_QUERY
    
    # Проверяем, что элементы отсортированы по времени создания
    assert query_items[0].item_id == query_id1
    assert query_items[1].item_id == query_id2


def test_get_items_by_step_filters_by_step_number():
    """
    get_items_by_step фильтрует элементы по metadata.step_number
    """
    data_context = DataContext()
    
    # Добавляем элементы с разными номерами шагов
    item1 = ContextItem(
        item_id="",
        session_id="session_1",
        item_type=ContextItemType.USER_QUERY,
        content="query 1",
        metadata=ContextItemMetadata(step_number=1)
    )
    step1_id1 = data_context.add_item(item1)
    
    item2 = ContextItem(
        item_id="",
        session_id="session_1",
        item_type=ContextItemType.ACTION,
        content="action 1",
        metadata=ContextItemMetadata(step_number=2)
    )
    step2_id = data_context.add_item(item2)
    
    item3 = ContextItem(
        item_id="",
        session_id="session_1",
        item_type=ContextItemType.USER_QUERY,
        content="query 2",
        metadata=ContextItemMetadata(step_number=1)
    )
    step1_id2 = data_context.add_item(item3)
    
    # Получаем элементы с номером шага 1
    step1_items = data_context.get_items_by_step(1)
    
    # Проверяем, что возвращаются только элементы с шагом 1
    assert len(step1_items) == 2
    for item in step1_items:
        assert item.metadata.step_number == 1
    
    # Проверяем, что элементы отсортированы по времени создания
    assert step1_items[0].item_id == step1_id1
    assert step1_items[1].item_id == step1_id2


def test_clear_removes_all_items_and_resets_counter():
    """
    clear полностью удаляет все элементы и сбрасывает счётчик ID
    """
    data_context = DataContext()
    
    # Добавляем несколько элементов
    for i in range(3):
        item = ContextItem(
            item_id="",
            session_id="session_1",
            item_type=ContextItemType.USER_QUERY,
            content=f"query {i}"
        )
        data_context.add_item(item)
    
    # Проверяем, что элементы есть
    assert data_context.count() == 3
    
    # Очищаем контекст
    data_context.clear()
    
    # Проверяем, что элементов больше нет
    assert data_context.count() == 0
    assert len(data_context.get_all_items()) == 0
    
    # Проверяем, что счетчик сброшен (новый элемент получит ID с начала)
    item = ContextItem(
        item_id="",
        session_id="session_1",
        item_type=ContextItemType.USER_QUERY,
        content="new query"
    )
    new_id = data_context.add_item(item)
    # Проверяем, что ID начинается с начала (номер 1 в новой серии)
    assert new_id.startswith("ctx_000001_")


def test_item_exists_returns_boolean():
    """
    item_exists возвращает True если элемент существует, False если нет
    """
    data_context = DataContext()
    
    # Добавляем элемент
    item = ContextItem(
        item_id="",
        session_id="session_1",
        item_type=ContextItemType.USER_QUERY,
        content="test query"
    )
    item_id = data_context.add_item(item)
    
    # Проверяем, что существующий элемент возвращает True
    assert data_context.item_exists(item_id) is True
    
    # Проверяем, что несуществующий элемент возвращает False
    assert data_context.item_exists("nonexistent_id") is False


def test_count_returns_correct_number():
    """
    count возвращает правильное количество элементов
    """
    data_context = DataContext()
    
    # Проверяем начальный счет
    assert data_context.count() == 0
    
    # Добавляем элементы
    for i in range(5):
        item = ContextItem(
            item_id="",
            session_id="session_1",
            item_type=ContextItemType.USER_QUERY,
            content=f"query {i}"
        )
        data_context.add_item(item)
    
    # Проверяем счет после добавления
    assert data_context.count() == 5
    
    # Очищаем и проверяем снова
    data_context.clear()
    assert data_context.count() == 0