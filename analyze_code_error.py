# analyze_code_error.py
"""
Пример анализа ошибки в коде через агент с использованием CodeAnalysisStrategy.
ДЕМОНСТРИРУЕТ ПОЛНЫЙ ЦИКЛ:
1. Автоматическое определение необходимости анализа кода на основе цели
2. Построение карты проекта (если отсутствует)
3. Универсальный цикл анализа с динамическим планированием через LLM
4. Формирование структурированного отчета
5. Вывод результатов из контекста сессии

ВАЖНО: Стратегия выбирается АВТОМАТИЧЕСКИ на основе цели пользователя.
НЕ требуется ручное переключение стратегий.
"""
import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime

# Добавляем корень проекта в путь
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

from core.config import get_config
from core.system_context.system_context import SystemContext
from core.session_context.session_context import SessionContext
from core.agent_runtime.runtime import AgentRuntime
from models.execution import ExecutionStatus


async def analyze_code_error_example():
    """
    Пример анализа реальной ошибки из лога пользователя:
    "sequence item 0: expected str instance, dict found"
    File "models/code_unit.py", line 296, in get_signature
    """
    print("=" * 80)
    print("АНАЛИЗ ОШИБКИ В КОДЕ ЧЕРЕЗ АГЕНТ")
    print("=" * 80)
    
    # 1. Загрузка конфигурации и инициализация
    config = get_config(profile='dev')
    system_context = SystemContext(config)
    
    print("\nИнициализация системного контекста...")
    success = await system_context.initialize()
    if not success:
        print("❌ Ошибка инициализации системы")
        return False
    
    print("✅ Система успешно инициализирована")
    
    # 2. Создание сессии
    session = SessionContext()
    
    # 3. Формулировка цели анализа ошибки
    # ВАЖНО: Цель должна содержать ключевые слова для автоматического выбора стратегии
    error_log = """
2026-01-28 10:05:28,346 - core.skills.project_navigator.skill - ERROR - Ошибка навигации: sequence item 0: expected str instance, dict found
Traceback (most recent call last):
  File "C:\\Users\\Алексей\\Documents\\WORK\\Agent_code\\core\\skills\\project_navigator\\skill.py", line 282, in _navigate
    result = await self._navigate_to_class(input_data, project_map, context)
  File "C:\\Users\\Алексей\\Documents\\WORK\\Agent_code\\core\\skills\\project_navigator\\skill.py", line 734, in _navigate_to_class
    signature=target_unit.get_signature(),
              ^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\\Users\\Алексей\\Documents\\WORK\\Agent_code\\models\\code_unit.py", line 296, in get_signature
    bases_str = f"({', '.join(bases)})" if bases else ""
                    ^^^^^^^^^^^^^^^^
TypeError: sequence item 0: expected str instance, dict found
"""
    
    goal = f"""
Проанализируй следующую ошибку в коде и предоставь структурированный отчет:

ТИП ЗАДАЧИ: Диагностика ошибки времени выполнения

СТЕК ОШИБКИ:
{error_log}

ТРЕБУЕМЫЙ ОТЧЕТ:
1. Точная причина ошибки (почему в методе get_signature() ожидается список строк, но получает список словарей)
2. Источник данных, возвращающий некорректный тип (какой метод/сервис возвращает словари вместо строк)
3. Конкретное предложение по исправлению кода
4. Уровень уверенности в анализе (0.0-1.0)

ИНСТРУКЦИИ ДЛЯ АГЕНТА:
- Используй структурный анализ кода через существующие навыки
- Применяй динамическое планирование шагов анализа
- Формируй отчет на основе фактов из кода, а не предположений
"""
    
    session.set_goal(goal)
    print("\nЦель анализа установлена:")
    print("-" * 80)
    print(f"Тип задачи: Диагностика ошибки")
    print(f"Место ошибки: models/code_unit.py, строка 296, метод get_signature()")
    print(f"Тип ошибки: несоответствие типов (ожидается список строк, получает список словарей)")
    print("-" * 80)
    
    # 4. Создание и запуск агента
    # ВАЖНО: Стратегия выбирается АВТОМАТИЧЕСКИ на основе цели
    # НЕ требуется указывать параметр strategy="code_analysis"
    print("\nЗапуск агента для анализа ошибки...")
    
    agent = AgentRuntime(
        system_context=system_context,
        session_context=session,
        max_steps=25,  # Увеличено для полного цикла анализа (инициализация + 10 шагов + финал)
        strategy="code_analysis"  # Начинаем с ReAct, он сам переключится на code_analysis при необходимости
    )
    
    # Запуск агента
    try:
        start_time = datetime.now()
        print(f"Начало анализа: {start_time.strftime('%H:%M:%S')}")
        print("-" * 80)
        
        result = await agent.run(goal)
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        print("-" * 80)
        print(f"Завершение анализа: {end_time.strftime('%H:%M:%S')} (длительность: {duration:.1f} сек)")
        
        # 5. Вывод результатов анализа
        print("\n" + "=" * 80)
        print("РЕЗУЛЬТАТЫ АНАЛИЗА ОШИБКИ")
        print("=" * 80)
        
        # Получение шагов анализа
        steps = session.step_context.steps
        if steps:
            print(f"\nВыполнено шагов: {len(steps)}")
            print("\nДЕТАЛИЗАЦИЯ ШАГОВ АНАЛИЗА:")
            print("-" * 80)
            
            for i, step in enumerate(steps, 1):
                status_icon = "✅" if step.status == ExecutionStatus.SUCCESS else "❌" if step.status == ExecutionStatus.FAILED else "⏳"
                skill_info = f"{step.skill_name}.{step.capability_name}" if step.capability_name else step.skill_name
                
                print(f"\nШаг #{step.step_number} {status_icon}")
                print(f"  Навык/Capability: {skill_info}")
                print(f"  Статус: {step.status.value}")
                if step.summary:
                    print(f"  Результат: {step.summary[:150]}...")
                
                # Вывод наблюдений для шага
                if step.observation_item_ids:
                    for obs_id in step.observation_item_ids[:2]:  # Первые 2 наблюдения
                        observation = session.data_context.items.get(obs_id)
                        if observation and observation.item_type.name == "OBSERVATION":
                            content = observation.content
                            if isinstance(content, dict):
                                action = content.get("action", "unknown")
                                if action in ["step_planning", "step_execution", "step_evaluation", "analysis_complete"]:
                                    print(f"  Наблюдение: {action}")
                                    if action == "analysis_complete":
                                        report = content.get("report", {})
                                        if report:
                                            print(f"    📊 Отчет анализа:")
                                            print(f"       Итог: {report.get('summary', 'нет данных')[:100]}...")
                                            print(f"       Уверенность: {report.get('confidence', 0.0):.2f}")
                                            if report.get("requires_human_review"):
                                                print(f"       ⚠️  Требуется ручная проверка")
        
        # Поиск финального отчета анализа
        final_report = None
        for item_id, item in session.data_context.items.items():
            if item.item_type.name == "OBSERVATION" and item.meta:
                content = item.content
                if isinstance(content, dict):
                    # Поиск финального отчета
                    if content.get("action") == "analysis_complete":
                        final_report = content.get("report")
                        break
                    # Поиск черновика отчета
                    if content.get("action") == "report_generation":
                        final_report = content.get("report")
                        break
        
        if final_report:
            print("\n" + "=" * 80)
            print("СТРУКТУРИРОВАННЫЙ ОТЧЕТ АНАЛИЗА")
            print("=" * 80)
            print(f"\n📋 РЕЗЮМЕ:")
            print(f"   {final_report.get('summary', 'нет данных')}")
            
            print(f"\n🔍 ОПИСАНИЕ ПРОБЛЕМЫ:")
            print(f"   {final_report.get('problem_description', 'нет данных')}")
            
            if final_report.get('root_cause'):
                print(f"\n🎯 КОРНЕВАЯ ПРИЧИНА:")
                print(f"   {final_report.get('root_cause')}")
            
            evidence = final_report.get('evidence', [])
            if evidence:
                print(f"\n📊 ДОКАЗАТЕЛЬСТВА:")
                for i, ev in enumerate(evidence[:5], 1):
                    print(f"   {i}. {ev}")
            
            recommendations = final_report.get('recommendations', [])
            if recommendations:
                print(f"\n💡 РЕКОМЕНДАЦИИ:")
                for i, rec in enumerate(recommendations[:5], 1):
                    print(f"   {i}. {rec}")
            
            if final_report.get('suggested_fix'):
                print(f"\n🛠️  ПРЕДЛОЖЕННОЕ ИСПРАВЛЕНИЕ:")
                print(f"   {final_report.get('suggested_fix')}")
            
            print(f"\n📈 УВЕРЕННОСТЬ АНАЛИЗА: {final_report.get('confidence', 0.0):.2f}")
            if final_report.get('requires_human_review'):
                print("⚠️  ТРЕБУЕТСЯ РУЧНАЯ ПРОВЕРКА РЕЗУЛЬТАТОВ")
        
        else:
            print("\n⚠️  Структурированный отчет не найден в контексте.")
            print("   Возможные причины:")
            print("   - Анализ не завершен (достигнут лимит шагов)")
            print("   - Стратегия переключилась на fallback из-за ошибки")
            print("   - Ошибка при генерации отчета")
            
            # Вывод последних наблюдений для диагностики
            print("\nПоследние наблюдения из контекста (для диагностики):")
            last_items = list(session.data_context.items.items())[-5:]
            for item_id, item in last_items:
                if item.item_type.name == "OBSERVATION":
                    content = item.content
                    if isinstance(content, dict):
                        action = content.get("action", "unknown")
                        print(f"  • {action}: {str(content)[:100]}...")
        
        # 6. Сохранение полного контекста для отладки
        output_file = f"code_analysis_result_{int(datetime.now().timestamp())}.json"
        
        # Подготовка данных для сохранения
        context_dump = {
            "analysis_goal": session.get_goal()[:500] + "...",
            "analysis_summary": session.get_summary(),
            "total_steps": len(session.step_context.steps),
            "total_observations": len(session.data_context.items),
            "steps": [
                {
                    "step_number": step.step_number,
                    "capability": step.capability_name,
                    "skill": step.skill_name,
                    "status": step.status.value if step.status else None,
                    "summary": step.summary[:200] if step.summary else None,
                    "observation_count": len(step.observation_item_ids) if step.observation_item_ids else 0
                }
                for step in session.step_context.steps
            ],
            "final_report": final_report,
            "timestamp": datetime.now().isoformat(),
            "duration_seconds": duration
        }
        
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(context_dump, f, indent=2, ensure_ascii=False)
        
        print(f"\nПолный контекст сохранен в: {output_file}")
        print(f"Размер файла: {Path(output_file).stat().st_size} байт")
        
        # Оценка успешности анализа
        analysis_successful = (
            final_report is not None and
            final_report.get('confidence', 0.0) >= 0.7 and
            len(steps) > 3  # Минимум 3 шага = инициализация + анализ + финал
        )
        
        return analysis_successful
        
    except Exception as e:
        print(f"\n❌ Критическая ошибка при запуске агента: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Завершение работы системы
        print("\nЗавершение работы системы...")
        await system_context.shutdown()
        print("✅ Система завершила работу")


def print_usage():
    """Вывод справки по использованию скрипта."""
    print("""
ИСПОЛЬЗОВАНИЕ:
  python analyze_code_error.py [options]

ОПЦИИ:
  --help, -h      Показать эту справку
  --max-steps N   Установить максимальное количество шагов анализа (по умолчанию: 25)
  --timeout N     Установить таймаут анализа в секундах (по умолчанию: 120)

ПРИМЕРЫ:
  # Анализ ошибки с настройками по умолчанию
  python analyze_code_error.py
  
  # Анализ с ограничением в 15 шагов
  python analyze_code_error.py --max-steps 15
  
  # Быстрый анализ с таймаутом 60 секунд
  python analyze_code_error.py --timeout 60
""")


async def main():
    """Основная функция с обработкой аргументов командной строки."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Анализ ошибки в коде через агент с использованием CodeAnalysisStrategy",
        add_help=False
    )
    parser.add_argument('--help', '-h', action='store_true', help='Показать справку')
    parser.add_argument('--max-steps', type=int, default=25, help='Максимальное количество шагов анализа')
    parser.add_argument('--timeout', type=int, default=120, help='Таймаут анализа в секундах')
    parser.add_argument('--verbose', '-v', action='store_true', help='Подробный вывод отладочной информации')
    
    args = parser.parse_args()
    
    if args.help:
        print_usage()
        return
    
    if args.verbose:
        import logging
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    print("\nЗапуск примера анализа ошибки в коде...")
    print("Этот скрипт продемонстрирует работу агента с задачей:")
    print("  'sequence item 0: expected str instance, dict found'")
    print(f"Максимальное количество шагов: {args.max_steps}")
    print(f"Таймаут анализа: {args.timeout} секунд\n")
    
    # Установка таймаута через asyncio
    try:
        success = await asyncio.wait_for(
            analyze_code_error_example(),
            timeout=args.timeout
        )
    except asyncio.TimeoutError:
        print(f"\n❌ Анализ превысил таймаут ({args.timeout} секунд)")
        success = False
    
    print("\n" + "=" * 80)
    if success:
        print("✅ Пример анализа ошибки успешно завершен")
        print("   Результаты сохранены в файл с префиксом 'code_analysis_result_'")
    else:
        print("❌ Пример анализа ошибки завершился с ошибками или неполным результатом")
        print("   Проверьте сохраненный файл контекста для диагностики")
    print("=" * 80 + "\n")
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())