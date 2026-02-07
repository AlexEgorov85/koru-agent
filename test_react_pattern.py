"""
Тестовый скрипт для проверки работы компонуемого ReAct паттерна.
"""
import asyncio
from unittest.mock import Mock, AsyncMock
from application.agent.composable_patterns.patterns import ReActPattern
from application.agent.adapters.composable_to_classic import ComposablePatternAdapter
from domain.models.agent.agent_state import AgentState


async def test_composable_react_pattern():
    """Тест работы компонуемого ReAct паттерна"""
    print("=== Тестирование компонуемого ReAct паттерна ===")
    
    # Создаем моки для зависимостей
    mock_llm_provider = Mock()
    mock_llm_provider.generate_response = AsyncMock(return_value='{"action": "TEST_ACTION", "thought": "Testing ReAct pattern", "parameters": {"test": "value"}}')
    
    mock_prompt_renderer = Mock()
    mock_prompt_renderer.render = Mock(return_value="Тестовый промт для ReAct")
    
    # Создаем компонуемый паттерн
    composable_pattern = ReActPattern(
        llm_provider=mock_llm_provider,
        prompt_renderer=mock_prompt_renderer,
        max_iterations=3
    )
    
    # Подготовим контекст задачи
    class Context:
        goal = "Тестовая задача для ReAct паттерна"
    
    state = AgentState()
    context = Context()
    capabilities = ["test_capability", "analyze", "generate"]
    
    composable_context = {
        "state": state,
        "context": context,
        "available_capabilities": capabilities,
        "step": state.step
    }
    
    print(f"Цель задачи: {context.goal}")
    print(f"Доступные возможности: {capabilities}")
    
    # Выполняем несколько итераций
    for i in range(3):
        print(f"\n--- Итерация {i+1} ---")
        result = composable_pattern.execute(composable_context)
        
        print(f"Действие: {result.get('action', 'N/A')}")
        print(f"Рассуждение: {result.get('thought', 'N/A')}")
        print(f"Параметры: {result.get('parameters', {})}")
        
        # Имитируем обработку наблюдения
        if result.get('action') == 'TEST_ACTION':
            observation = {"result": "Успешно выполнено тестовое действие", "success": True}
            obs_result = composable_pattern.process_observation(observation)
            if obs_result:
                print(f"Обработка наблюдения: {obs_result.get('thought', 'N/A')}")
    
    # Проверим состояние
    current_state = composable_pattern.get_state()
    if current_state:
        print(f"\n--- Состояние паттерна ---")
        print(f"Цель: {current_state.goal}")
        print(f"Количество шагов: {len(current_state.steps)}")
        print(f"Завершено: {current_state.is_completed}")
        
        print("\n--- Последние шаги ---")
        for step in current_state.steps[-3:]:  # Последние 3 шага
            print(f"[{step.action_type.value}] {step.content[:100]}...")
    
    print("\n=== Тестирование компонуемого паттерна завершено ===")


async def test_react_pattern_via_adapter():
    """Тест работы ReAct паттерна через адаптер"""
    print("\n=== Тестирование ReAct паттерна через адаптер ===")
    
    # Создаем моки для зависимостей
    mock_llm_provider = Mock()
    mock_llm_provider.generate_response = AsyncMock(return_value='{"action": "ADAPTER_TEST", "thought": "Testing adapter", "parameters": {"adapter": "value"}}')
    
    mock_prompt_renderer = Mock()
    mock_prompt_renderer.render = Mock(return_value="Тестовый промт для адаптера")
    
    # Создаем компонуемый паттерн
    composable_pattern = ReActPattern(
        llm_provider=mock_llm_provider,
        prompt_renderer=mock_prompt_renderer,
        max_iterations=2
    )
    
    # Создаем адаптер
    adapter = ComposablePatternAdapter(composable_pattern)
    
    # Подготовим контекст задачи
    class Context:
        goal = "Тестовая задача через адаптер"
    
    state = AgentState()
    context = Context()
    capabilities = ["adapter_test", "analyze"]
    
    print(f"Цель задачи: {context.goal}")
    print(f"Имя адаптера: {adapter.name}")
    
    # Выполняем итерацию через адаптер
    result = await adapter.execute(state, context, capabilities)
    
    print(f"Действие: {result.get('action', 'N/A')}")
    print(f"Рассуждение: {result.get('thought', 'N/A')}")
    print(f"Результат: {result}")
    
    print("=== Тестирование через адаптер завершено ===")


async def test_react_pattern_without_llm():
    """Тест работы ReAct паттерна без LLM (резервная логика)"""
    print("\n=== Тестирование ReAct паттерна без LLM ===")
    
    # Создаем паттерн без LLM провайдера
    pattern = ReActPattern(max_iterations=2)
    
    # Подготовим контекст задачи
    class Context:
        goal = "Анализировать код на Python"
    
    state = AgentState()
    context = Context()
    capabilities = ["code_analyzer", "file_reader"]
    
    composable_context = {
        "state": state,
        "context": context,
        "available_capabilities": capabilities,
        "step": state.step
    }
    
    print(f"Цель задачи: {context.goal}")
    
    # Выполняем итерацию
    result = pattern.execute(composable_context)
    
    print(f"Действие: {result.get('action', 'N/A')}")
    print(f"Рассуждение: {result.get('thought', 'N/A')}")
    print(f"Используется резервная логика: {'Нет доступа к LLM' in result.get('thought', '')}")
    
    print("=== Тестирование без LLM завершено ===")


async def main():
    await test_composable_react_pattern()
    await test_react_pattern_via_adapter()
    await test_react_pattern_without_llm()


if __name__ == "__main__":
    asyncio.run(main())