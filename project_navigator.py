#!/usr/bin/env python3
"""
Практические сценарии использования переработанного ProjectNavigatorSkill.
ИСПРАВЛЕНИЯ:
1. Безопасная обработка отсутствующего source_code (проверка на None)
2. Корректная работа с нормализованными путями
3. Информативные сообщения при ошибках
"""
import sys
import asyncio
import logging
from pathlib import Path
from core.config import get_config
from core.system_context.system_context import SystemContext
from core.session_context.session_context import SessionContext
from models.execution import ExecutionStatus

root_dir = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(root_dir))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("project_navigator_test")


async def analyze_project_structure(system_context: SystemContext, session_context: SessionContext) -> bool:
    """Анализ структуры проекта и сохранение ProjectMap в контекст."""
    logger.info("=" * 80)
    logger.info("ЭТАП 1: Анализ структуры проекта через ProjectMapSkill")
    logger.info("=" * 80)
    
    project_map_skill = system_context.get_resource("project_map")
    if not project_map_skill:
        logger.error("Навык 'project_map' не найден в системном контексте")
        return False
    
    parameters = {
        "directory": ".",
        "max_items": 1000,
        "file_extensions": ["py"],
        "include_tests": False,
        "include_hidden": False,
        "include_code_units": True
    }
    
    try:
        result = await project_map_skill.execute(
            capability=system_context.get_capability("project_map.analyze_project"),
            parameters=parameters,
            context=session_context
        )
        
        if result.status == ExecutionStatus.SUCCESS:
            project_structure = result.result
            
            logger.info(f"✅ Проект успешно проанализирован")
            logger.info(f"   Файлов: {project_structure.total_files}")
            logger.info(f"   Единиц кода: {project_structure.total_code_units}")
            
            session_context.project_map = project_structure
            logger.info("✅ ProjectMap сохранён в контекст сессии")
            return True
        else:
            logger.error(f"❌ Ошибка анализа проекта: {result.summary}")
            if result.error:
                logger.error(f"   Детали ошибки: {result.error}")
            return False
            
    except Exception as e:
        logger.exception(f"❌ Критическая ошибка при анализе проекта: {str(e)}")
        return False


async def scenario_1_navigate_to_file(system_context: SystemContext, session_context: SessionContext):
    """Сценарий 1: Навигация к файлу и получение его содержимого."""
    logger.info("\n" + "=" * 80)
    logger.info("СЦЕНАРИЙ 1: Навигация к файлу и получение его содержимого")
    logger.info("=" * 80)
    
    navigator = system_context.get_resource("project_navigator")
    if not navigator:
        logger.error("Навык 'project_navigator' не найден")
        return
    
    parameters = {
        "target_type": "file",
        "identifier": "core/skills/project_navigator/skill.py",
        "detail_level": "full"
    }
    
    try:
        result = await navigator.execute(
            capability=system_context.get_capability("project_navigator.navigate"),
            parameters=parameters,
            context=session_context
        )
        
        if result.status == ExecutionStatus.SUCCESS:
            nav_result = result.result
            
            file_path = nav_result.get('file_path', 'неизвестно')
            source_code = nav_result.get('source_code', '')
            source_size = len(source_code) if source_code else 0
            
            logger.info(f"✅ Файл успешно найден: {file_path}")
            logger.info(f"   Размер: {source_size} символов")
            
            if source_code:
                code_lines = source_code.split('\n')[:15]
                logger.info("\nКод файла (первые 15 строк):")
                logger.info("-" * 40)
                for i, line in enumerate(code_lines, 1):
                    logger.info(f"{i:3d}: {line[:80]}")  # Обрезаем длинные строки
                logger.info("-" * 40)
            else:
                logger.warning("⚠️  Исходный код не загружен (возможно, ошибка чтения файла)")
                
        else:
            logger.error(f"❌ Ошибка навигации: {result.summary}")
            if result.error:
                logger.error(f"   Детали: {result.error}")
                
    except Exception as e:
        logger.exception(f"❌ Критическая ошибка в сценарии 1: {str(e)}")


async def scenario_2_navigate_to_class(system_context: SystemContext, session_context: SessionContext):
    """Сценарий 2: Навигация к классу и получение его сигнатуры."""
    logger.info("\n" + "=" * 80)
    logger.info("СЦЕНАРИЙ 2: Навигация к классу и получение его сигнатуры")
    logger.info("=" * 80)
    
    navigator = system_context.get_resource("project_navigator")
    if not navigator:
        logger.error("Навык 'project_navigator' не найден")
        return
    
    parameters = {
        "target_type": "class",
        "identifier": "ProjectNavigatorSkill",
        "file_path": "core/skills/project_navigator/skill.py",
        "detail_level": "signature"
    }
    
    try:
        result = await navigator.execute(
            capability=system_context.get_capability("project_navigator.navigate"),
            parameters=parameters,
            context=session_context
        )
        
        if result.status == ExecutionStatus.SUCCESS:
            nav_result = result.result
            
            logger.info(f"✅ Класс успешно найден: {nav_result.get('identifier', 'неизвестно')}")
            logger.info(f"   Файл: {nav_result.get('file_path', 'неизвестно')}")
            logger.info(f"   Сигнатура: {nav_result.get('signature', 'не доступна')}")
            
            # Показываем расположение в файле
            location = nav_result.get('location', {})
            if location:
                logger.info(f"   Расположение: строки {location.get('start_line', '?')}–{location.get('end_line', '?')}")
                
        else:
            logger.error(f"❌ Ошибка навигации к классу: {result.summary}")
            if result.error:
                logger.error(f"   Детали: {result.error}")
                
    except Exception as e:
        logger.exception(f"❌ Критическая ошибка в сценарии 2: {str(e)}")


async def scenario_3_navigate_to_method(system_context: SystemContext, session_context: SessionContext):
    """Сценарий 3: Навигация к методу класса."""
    logger.info("\n" + "=" * 80)
    logger.info("СЦЕНАРИЙ 3: Навигация к методу класса")
    logger.info("=" * 80)
    
    navigator = system_context.get_resource("project_navigator")
    if not navigator:
        logger.error("Навык 'project_navigator' не найден")
        return
    
    parameters = {
        "target_type": "method",
        "identifier": "_navigate_to_class",
        "class_name": "ProjectNavigatorSkill",
        "file_path": "core/skills/project_navigator/skill.py",
        "detail_level": "signature"
    }
    
    try:
        result = await navigator.execute(
            capability=system_context.get_capability("project_navigator.navigate"),
            parameters=parameters,
            context=session_context
        )
        
        if result.status == ExecutionStatus.SUCCESS:
            nav_result = result.result
            
            logger.info(f"✅ Метод успешно найден: {nav_result.get('identifier', 'неизвестно')}")
            logger.info(f"   Класс: {nav_result.get('class_name', 'неизвестно')}")
            logger.info(f"   Файл: {nav_result.get('file_path', 'неизвестно')}")
            logger.info(f"   Сигнатура: {nav_result.get('signature', 'не доступна')}")
            
        else:
            logger.error(f"❌ Ошибка навигации к методу: {result.summary}")
            if result.error:
                logger.error(f"   Детали: {result.error}")
                
    except Exception as e:
        logger.exception(f"❌ Критическая ошибка в сценарии 3: {str(e)}")


async def scenario_4_search_code_elements(system_context: SystemContext, session_context: SessionContext):
    """Сценарий 4: Поиск элементов кода по имени."""
    logger.info("\n" + "=" * 80)
    logger.info("СЦЕНАРИЙ 4: Поиск элементов кода по имени")
    logger.info("=" * 80)
    
    navigator = system_context.get_resource("project_navigator")
    if not navigator:
        logger.error("Навык 'project_navigator' не найден")
        return
    
    parameters = {
        "query": "execute",
        "scope": "global",
        "element_types": ["class", "function", "method"],
        "exact_match": False,
        "max_results": 5
    }
    
    try:
        result = await navigator.execute(
            capability=system_context.get_capability("project_navigator.search"),
            parameters=parameters,
            context=session_context
        )
        
        if result.status == ExecutionStatus.SUCCESS:
            search_result = result.result
            
            total = search_result.get("total_results", 0)
            results = search_result.get("results", [])
            
            logger.info(f"✅ Найдено {total} элементов с 'execute' в названии")
            logger.info(f"   Показано результатов: {len(results)}")
            
            for i, item in enumerate(results[:5], 1):
                name = item.get("name", "неизвестно")
                file_path = item.get("file_path", "неизвестно")
                element_type = item.get("type", "неизвестно")
                line = item.get("line", 0)
                relevance = item.get("relevance_score", 0.0)
                
                logger.info(f"\n{i}. {element_type.capitalize()}: {name}")
                logger.info(f"   Файл: {file_path}")
                logger.info(f"   Строка: {line}")
                logger.info(f"   Релевантность: {relevance:.2f}")
                
            if total > 5:
                logger.info(f"\n... и ещё {total - 5} элементов")
                
        else:
            logger.error(f"❌ Ошибка поиска: {result.summary}")
            if result.error:
                logger.error(f"   Детали: {result.error}")
                
    except Exception as e:
        logger.exception(f"❌ Критическая ошибка в сценарии 4: {str(e)}")


async def scenario_5_get_file_structure(system_context: SystemContext, session_context: SessionContext):
    """Сценарий 5: Получение структуры файла."""
    logger.info("\n" + "=" * 80)
    logger.info("СЦЕНАРИЙ 5: Получение структуры файла")
    logger.info("=" * 80)
    
    navigator = system_context.get_resource("project_navigator")
    if not navigator:
        logger.error("Навык 'project_navigator' не найден")
        return
    
    parameters = {
        "file_path": "core/skills/project_navigator/skill.py"
    }
    
    try:
        result = await navigator.execute(
            capability=system_context.get_capability("project_navigator.get_file_structure"),
            parameters=parameters,
            context=session_context
        )
        
        if result.status == ExecutionStatus.SUCCESS:
            structure = result.result
            
            logger.info(f"✅ Структура файла получена: {structure.get('file_path', 'неизвестно')}")
            logger.info(f"   Количество единиц кода: {structure.get('unit_count', 0)}")
            
            code_units = structure.get("code_units", [])
            if code_units:
                # Группировка по типам
                type_counts = {}
                for unit in code_units:
                    u_type = unit.get("type", "unknown")
                    type_counts[u_type] = type_counts.get(u_type, 0) + 1
                
                logger.info("\nРаспределение по типам:")
                for u_type, count in sorted(type_counts.items(), key=lambda x: x[1], reverse=True):
                    logger.info(f"   {u_type}: {count}")
                    
                # Показываем первые 5 классов/функций
                logger.info("\nКлючевые элементы (первые 5):")
                shown = 0
                for unit in code_units:
                    if unit.get("type") in ["class", "function", "method"]:
                        name = unit.get("name", "неизвестно")
                        line = unit.get("location", {}).get("start_line", 0)
                        logger.info(f"   • {unit['type']} '{name}' (строка {line})")
                        shown += 1
                        if shown >= 5:
                            break
                    
        else:
            logger.error(f"❌ Ошибка получения структуры: {result.summary}")
            if result.error:
                logger.error(f"   Детали: {result.error}")
                
    except Exception as e:
        logger.exception(f"❌ Критическая ошибка в сценарии 5: {str(e)}")


async def scenario_6_get_dependencies(system_context: SystemContext, session_context: SessionContext):
    """Сценарий 6: Получение зависимостей файла."""
    logger.info("\n" + "=" * 80)
    logger.info("СЦЕНАРИЙ 6: Получение зависимостей файла")
    logger.info("=" * 80)
    
    navigator = system_context.get_resource("project_navigator")
    if not navigator:
        logger.error("Навык 'project_navigator' не найден")
        return
    
    parameters = {
        "file_path": "core/skills/project_navigator/skill.py",
        "depth": 1
    }
    
    try:
        result = await navigator.execute(
            capability=system_context.get_capability("project_navigator.get_dependencies"),
            parameters=parameters,
            context=session_context
        )
        
        if result.status == ExecutionStatus.SUCCESS:
            deps_result = result.result
            
            file_path = deps_result.get("file_path", "неизвестно")
            deps = deps_result.get("dependencies", [])
            count = deps_result.get("dependency_count", len(deps))
            
            logger.info(f"✅ Зависимости файла получены: {file_path}")
            logger.info(f"   Всего зависимостей: {count}")
            
            if deps:
                shown = min(10, len(deps))
                for i in range(shown):
                    dep = deps[i]
                    target = dep.get("target_file", dep.get("file_path", "неизвестно"))
                    dep_type = dep.get("dependency_type", "import")
                    logger.info(f"   {i+1:2d}. {target} ({dep_type})")
                
                if count > shown:
                    logger.info(f"   ... и ещё {count - shown} зависимостей")
            else:
                logger.warning("⚠️  Зависимости не найдены (нормально для файлов навыков)")
                
        else:
            logger.error(f"❌ Ошибка получения зависимостей: {result.summary}")
            if result.error:
                logger.error(f"   Детали: {result.error}")
                
    except Exception as e:
        logger.exception(f"❌ Критическая ошибка в сценарии 6: {str(e)}")


async def main():
    """Основная функция запуска всех сценариев."""
    logger.info("=" * 80)
    logger.info("ЗАПУСК ТЕСТОВОГО СЦЕНАРИЯ переработанного ProjectNavigatorSkill")
    logger.info("=" * 80)
    
    try:
        config = get_config(profile='dev')
        system_context = SystemContext(config)
        
        success = await system_context.initialize()
        if not success:
            logger.error("❌ Ошибка инициализации системы")
            return
        
        logger.info("✅ Система успешно инициализирована")
        
        session_context = SessionContext()
        session_context.set_goal("Тестирование навыка навигации по проекту")
        logger.info("✅ Сессия создана")
        
        if not await analyze_project_structure(system_context, session_context):
            logger.error("\n❌ Невозможно продолжить тестирование без анализа проекта")
            await system_context.shutdown()
            return
        
        logger.info("\n✅ Анализ проекта завершён успешно. Запуск сценариев навигации...")
        
        scenarios = [
            scenario_1_navigate_to_file,
            scenario_2_navigate_to_class,
            scenario_3_navigate_to_method,
            scenario_4_search_code_elements,
            scenario_5_get_file_structure,
            scenario_6_get_dependencies
        ]
        
        for i, scenario in enumerate(scenarios, 1):
            logger.info(f"\n{'=' * 80}")
            logger.info(f"ЗАПУСК СЦЕНАРИЯ #{i}")
            logger.info(f"{'=' * 80}")
            await scenario(system_context, session_context)
            await asyncio.sleep(0.3)
        
        logger.info("\n" + "=" * 80)
        logger.info("ВСЕ СЦЕНАРИИ ЗАВЕРШЕНЫ УСПЕШНО")
        logger.info("=" * 80)
        logger.info(f"Количество выполненных сценариев: {len(scenarios)}")
        logger.info(f"ID сессии: {session_context.session_id}")
        
    except KeyboardInterrupt:
        logger.info("\n⚠️  Выполнение прервано пользователем")
    except Exception as e:
        logger.exception(f"\n❌ Критическая ошибка при выполнении сценариев: {str(e)}")
    finally:
        logger.info("\n" + "-" * 80)
        logger.info("ЗАВЕРШЕНИЕ РАБОТЫ")
        logger.info("-" * 80)
        
        if 'system_context' in locals():
            await system_context.shutdown()
            logger.info("✅ Системный контекст завершил работу")
        
        logger.info("Тестирование переработанного ProjectNavigatorSkill завершено")


if __name__ == "__main__":
    asyncio.run(main())