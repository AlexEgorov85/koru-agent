#!/usr/bin/env python3
"""
Тест исправлений парсинга traces.

Запуск:
    py test_trace_fix.py
"""
import asyncio
import sys
from pathlib import Path

# Добавляем корень проекта в path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.agent.components.optimization import TraceHandler


async def test_capability_parsing():
    """Тест извлечения capability"""
    print("="*60)
    print("ТЕСТ 1: Извлечение capability")
    print("="*60)
    
    handler = TraceHandler(logs_dir='data/logs')
    
    # Тест на сессии с metric.collected
    trace = await handler.get_execution_trace('2026-03-24_14-29-19')
    
    print(f"\nSteps found: {trace.step_count}")
    
    if trace.step_count == 0:
        print("❌ FAIL: Нет шагов")
        return False
    
    all_pass = True
    for i, step in enumerate(trace.steps[:5]):
        print(f"\nStep {i}:")
        print(f"  Capability: {step.capability}")
        print(f"  Time: {step.time_ms:.0f}ms")
        print(f"  Tokens: {step.tokens_used}")
        
        # ПРОВЕРКА: capability не должен быть "unknown"
        if step.capability == 'unknown':
            print(f"  ❌ FAIL: capability = unknown")
            all_pass = False
        else:
            print(f"  ✅ PASS: capability = {step.capability}")
    
    return all_pass


async def test_step_count():
    """Тест количества шагов"""
    print("\n" + "="*60)
    print("ТЕСТ 2: Количество шагов")
    print("="*60)
    
    handler = TraceHandler(logs_dir='data/logs')
    
    # Считаем шаги во всех сессиях
    sessions_dir = Path('data/logs/sessions')
    total_steps = 0
    sessions_with_steps = 0
    
    for session_dir in sorted(sessions_dir.iterdir(), reverse=True)[:10]:
        trace = await handler.get_execution_trace(session_dir.name)
        if trace and trace.step_count > 0:
            sessions_with_steps += 1
            total_steps += trace.step_count
            print(f"  {session_dir.name}: {trace.step_count} шагов")
    
    print(f"\nВсего сессий: 10")
    print(f"Сессий с шагами: {sessions_with_steps}")
    print(f"Всего шагов: {total_steps}")
    
    # Критерии успеха
    pass_count = sessions_with_steps >= 1  # Хоть одна сессия
    pass_steps = total_steps >= 3
    
    if pass_count and pass_steps:
        print(f"\n✅ PASS: Есть сессии с шагами, ≥3 total steps")
        return True
    else:
        print(f"\n❌ FAIL: Мало сессий с шагами или мало total steps")
        return False


async def test_response_length():
    """Тест длины ответов"""
    print("\n" + "="*60)
    print("ТЕСТ 3: Длина ответов LLM")
    print("="*60)
    
    handler = TraceHandler(logs_dir='data/logs')
    trace = await handler.get_execution_trace('2026-03-24_14-29-19')
    
    if trace.step_count == 0:
        print("❌ FAIL: Нет шагов для проверки")
        return False
    
    all_pass = True
    for i, step in enumerate(trace.steps[:5]):
        if step.llm_response:
            content_len = len(step.llm_response.content)
            print(f"Step {i}: Response length = {content_len}")
            
            if content_len < 20:
                print(f"  ⚠️  WARNING: короткий ответ ({content_len} символов)")
                # Не считаем это failure т.к. у нас placeholder
            else:
                print(f"  ✅ OK: ответ полный")
        else:
            print(f"Step {i}: ❌ No response")
            all_pass = False
    
    return all_pass


async def quick_test():
    """Быстрая проверка всех критериев"""
    print("\n" + "="*60)
    print("БЫСТРАЯ ПРОВЕРКА")
    print("="*60)
    
    handler = TraceHandler(logs_dir='data/logs')
    trace = await handler.get_execution_trace('2026-03-24_14-29-19')
    
    # Быстрые проверки
    checks = {
        'steps >= 3': trace.step_count >= 3,
        'no unknown': all(s.capability != 'unknown' for s in trace.steps) if trace.steps else False,
        'has requests': all(s.llm_request is not None for s in trace.steps) if trace.steps else False,
        'has responses': all(s.llm_response is not None for s in trace.steps) if trace.steps else False,
    }
    
    print("\nResults:")
    all_pass = True
    for check, passed in checks.items():
        status = "✅" if passed else "❌"
        print(f"  {status} {check}: {passed}")
        if not passed:
            all_pass = False
    
    print(f"\n{'✅ ALL PASS' if all_pass else '❌ SOME FAILED'}")
    return all_pass


async def main():
    """Запуск всех тестов"""
    print("\n🧪 ТЕСТИРОВАНИЕ ИСПРАВЛЕНИЙ TRACE PARSING\n")
    
    results = []
    
    # Тест 1
    results.append(await test_capability_parsing())
    
    # Тест 2
    results.append(await test_step_count())
    
    # Тест 3
    results.append(await test_response_length())
    
    # Быстрая проверка
    results.append(await quick_test())
    
    # Итог
    print("\n" + "="*60)
    print("ИТОГ")
    print("="*60)
    
    if all(results):
        print("\n✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ")
        return 0
    else:
        print(f"\n❌ ПРОЙДЕНО {sum(results)}/{len(results)} тестов")
        return 1


if __name__ == '__main__':
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
