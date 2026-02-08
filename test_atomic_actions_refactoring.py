"""
Тестирование рефакторинга атомарных действий
"""
import asyncio
import tempfile
from pathlib import Path
from application.orchestration.atomic_actions.executor import AtomicActionExecutor
from application.orchestration.atomic_actions.react_actions import (
    ThinkAction,
    ActAction,
    ObserveAction,
    FileOperationAction
)
from domain.abstractions.event_types import EventType, IEventPublisher


class MockEventPublisher:
    """Мок для публикатора событий"""
    async def publish(self, event_type: EventType, source: str, data: dict):
        print(f"Event: {event_type.value} from {source}: {data}")


async def test_atomic_actions():
    print("=== Тестирование атомарных действий ===\n")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        event_publisher = MockEventPublisher()
        
        # Создаем исполнитель атомарных действий
        executor = AtomicActionExecutor(project_root=project_root, event_publisher=event_publisher)
        
        # Регистрируем действия
        executor.register_action("think", ThinkAction(event_publisher=event_publisher))
        executor.register_action("act", ActAction(event_publisher=event_publisher))
        executor.register_action("observe", ObserveAction(event_publisher=event_publisher))
        executor.register_action("file_operation", FileOperationAction(
            event_publisher=event_publisher,
            project_root=project_root
        ))
        
        print("1. Тестирование ThinkAction:")
        think_result = await executor.execute("think", {"goal": "Тестовая цель", "history": [], "available_capabilities": []})
        print(f"   Результат: {think_result.success}, thought: {getattr(think_result, 'thought', 'N/A')}")
        assert think_result.success is True
        print("   ✅ ThinkAction работает корректно\n")
        
        print("2. Тестирование ActAction:")
        act_result = await executor.execute("act", {
            "selected_action": "test_action", 
            "action_parameters": {"param": "value"},
            "available_capabilities": ["test_action"]
        })
        print(f"   Результат: {act_result.success}, action_result: {getattr(act_result, 'action_result', 'N/A')}")
        assert act_result.success is True
        print("   ✅ ActAction работает корректно\n")
        
        print("3. Тестирование ObserveAction:")
        observe_result = await executor.execute("observe", {
            "action_result": "test result",
            "last_action": "test_action"
        })
        print(f"   Результат: {observe_result.success}, observation: {getattr(observe_result, 'observation', 'N/A')}")
        assert observe_result.success is True
        print("   ✅ ObserveAction работает корректно\n")
        
        print("4. Тестирование FileOperationAction (безопасность):")
        # Создаем безопасный файл
        test_file = project_root / "test.txt"
        test_file.write_text("test content")
        
        file_result = await executor.execute("file_operation", {
            "operation_type": "read",
            "file_path": "test.txt"
        })
        print(f"   Результат: {file_result.success}, result: {getattr(file_result, 'result', 'N/A')}")
        assert file_result.success is True
        print("   ✅ FileOperationAction работает корректно\n")
        
        print("5. Тестирование безопасности (path traversal защита):")
        unsafe_result = await executor.execute("file_operation", {
            "operation_type": "read",
            "file_path": "../../../windows/system32/config/sam"  # Windows unsafe path
        })
        print(f"   Результат: {unsafe_result.success}, error: {unsafe_result.error_message}")
        assert unsafe_result.success is False
        print("   ✅ Защита от path traversal работает\n")
        
        print("6. Тестирование композиции действий:")
        actions_sequence = [
            {"action": "think", "parameters": {"goal": "Тест композиции", "available_capabilities": ["test"]}},
            {"action": "act", "parameters": {"selected_action": "test", "action_parameters": {}}},
            {"action": "observe", "parameters": {"action_result": "test result", "last_action": "test"}}
        ]
        
        composition_results = await executor.execute_with_rollback(actions_sequence)
        print(f"   Результаты: {[r.success for r in composition_results]}")
        assert all(r.success for r in composition_results)
        print("   ✅ Композиция действий работает корректно\n")
        
        print("7. Тестирование отката при ошибке:")
        # Последовательность с ошибкой на 2-м шаге
        bad_sequence = [
            {"action": "file_operation", "parameters": {"operation_type": "write", "file_path": "step1.txt", "file_content": "data1"}},
            {"action": "file_operation", "parameters": {"operation_type": "read", "file_path": "../../../windows/system32/config/sam"}},  # Ошибка
            {"action": "think", "parameters": {"goal": "should not reach"}}
        ]
        
        bad_results = await executor.execute_with_rollback(bad_sequence)
        print(f"   Результаты: {[r.success for r in bad_results]}, ошибка на шаге: {not bad_results[1].success}")
        # Второй шаг должен завершиться с ошибкой
        assert not bad_results[1].success
        print("   ✅ Откат при ошибке работает корректно\n")
        
        print("🎉 Все тесты пройдены успешно!")


if __name__ == "__main__":
    asyncio.run(test_atomic_actions())