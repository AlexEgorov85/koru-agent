import asyncio
import sys
from pathlib import Path

# Добавляем корневую директорию проекта в путь Python
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.config.config_loader import ConfigLoader
from core.infrastructure.context.infrastructure_context import InfrastructureContext
from core.application.context.application_context import ApplicationContext
from core.config.app_config import AppConfig
from core.application.context.application_context import ComponentType


async def main():
    # 1. Поднимаем инфраструктурный контекст
    # Загрузка конфигурации из dev.yaml
    config_loader = ConfigLoader()
    config = config_loader.load()  # Загрузит dev.yaml по умолчанию
    # Создание инфраструктурного контекста с загруженной конфигурацией
    infra = InfrastructureContext(config)

    print("Инициализация инфраструктурного контекста с параметрами из dev.yaml...")
    await infra.initialize()
    print("1. Инфраструктурный контекст успешно инициализирован!")

    # 2. Создаём контекст
    ctx1 = ApplicationContext(
        infrastructure_context=infra,
        config=AppConfig.from_registry(profile="prod"),
        profile='prod'
    )
    await ctx1.initialize()

    # Выводим все зарегистрированные компоненты для анализа полноты заполнения параметров
    print("\n=== Анализ полноты заполнения параметров компонентов ===")
    
    # Проверяем внутреннюю структуру объекта components
    print(f"Структура объекта components: {dir(ctx1.components)}")
    
    # Попробуем получить список всех атрибутов, которые могут быть компонентами
    all_attrs = [attr for attr in dir(ctx1.components) if not attr.startswith('_')]
    print(f"Все атрибуты компонентов: {all_attrs}")
    
    # Проходим по всем типам компонентов
    for comp_type in ComponentType:
        print(f"\n--- {comp_type.value.upper()} ---")
        
        # Пробуем получить компоненты через метод all_of_type
        try:
            if hasattr(ctx1.components, 'all_of_type'):
                all_components = ctx1.components.all_of_type(comp_type)
                
                if isinstance(all_components, dict):
                    print(f"Получены все компоненты типа {comp_type.value}: {list(all_components.keys())}")
                    for name, component in all_components.items():
                        print_component_details(name, component)
                elif isinstance(all_components, list):
                    print(f"Получено {len(all_components)} компонентов типа {comp_type.value}")
                    # Для списка компонентов, нужно определить их имена по другому
                    for i, component in enumerate(all_components):
                        # Попробуем использовать имя класса или атрибут name как имя компонента
                        component_name = getattr(component, 'name', f"{comp_type.value}_{i}")
                        print_component_details(component_name, component)
                else:
                    print(f"Компоненты типа {comp_type.value} не являются словарем или списком, тип: {type(all_components)}")
            else:
                print(f"Метод all_of_type недоступен в ComponentRegistry")
                
        except Exception as e:
            print(f"Ошибка при получении компонентов типа {comp_type.value}: {str(e)}")

    # Также выведем общую информацию о компонентах
    print(f"\n--- Общая информация о компонентах ---")
    print(f"Объект components: {ctx1.components}")
    print(f"Его атрибуты: {[attr for attr in dir(ctx1.components) if not attr.startswith('__')]}")

    # 3. Получаем сервис sql_query_service
    sql_query_service = ctx1.components.get(ComponentType.SERVICE, 'sql_query_service')
    if sql_query_service:
        print(f"\n=== Дополнительная информация по конкретным компонентам ===")
        print("3. Сервис sql_query_service:", sql_query_service.__dict__)
    else:
        print("3. Сервис sql_query_service не найден или равен None")

    # 4. Получаем инструмент sql_tool
    sql_tool = ctx1.components.get(ComponentType.TOOL, 'sql_tool')
    if sql_tool:
        print("4. Инструмент sql_tool:", sql_tool.__dict__)
    else:
        print("4. Инструмент sql_tool не найден или равен None")


# Функция для печати деталей компонента
def print_component_details(name, component):
    print(f"\nКомпонент: {name}")
    print(f"Тип: {type(component).__name__}")

    # Проверяем атрибуты компонента
    if hasattr(component, '__dict__'):
        attrs = component.__dict__
        print(f"Количество атрибутов: {len(attrs)}")
        for attr_name, attr_value in attrs.items():
            # Укорачиваем длинные значения для лучшей читаемости
            if isinstance(attr_value, (list, dict)) and len(str(attr_value)) > 100:
                print(f"  {attr_name}: {str(attr_value)[:100]}... (обрезано)")
            else:
                print(f"  {attr_name}: {attr_value}")
    elif hasattr(component, '__slots__'):
        # Для классов с __slots__
        print("Атрибуты (через __slots__):")
        for slot in component.__slots__:
            try:
                attr_value = getattr(component, slot)
                print(f"  {slot}: {attr_value}")
            except AttributeError:
                print(f"  {slot}: <атрибут не установлен>")
    else:
        print("  Компонент не имеет атрибутов (__dict__ или __slots__) для анализа")


if __name__ == "__main__":
    asyncio.run(main())