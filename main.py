"""
Точка входа для запуска агента с использованием инкапсулированной системы.
ОСОБЕННОСТИ:
- Все детали инкапсулированы в класс Application
- Четкий жизненный цикл приложения
- Полные определения всех используемых классов и функций
- Легко переносится в SystemContext в будущем
"""
import asyncio
import argparse
import sys
import os
import logging
import json
from typing import Any, Dict
import signal
from datetime import datetime

# Импорт из core
from core.config import get_config
from core.system_context.system_context import SystemContext

# Настройка корневого логгера
def setup_logging(config: Any) -> None:
    """
    Настройка логирования на основе конфигурации.
    """
    log_level = getattr(logging, config.log_level.upper(), logging.INFO)
    log_dir = config.log_dir
    
    # Создание директории для логов
    os.makedirs(log_dir, exist_ok=True)
    
    # Определение файла логов
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file_path = os.path.join(log_dir, f"agent_{timestamp}.log")
    
    # Настройка форматтеров
    console_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Настройка обработчиков
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(console_formatter)
    console_handler.setLevel(log_level)
    
    file_handler = logging.FileHandler(log_file_path, encoding='utf-8')
    file_handler.setFormatter(file_formatter)
    file_handler.setLevel(log_level)
    
    # Настройка корневого логгера
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.handlers = []  # Очистка существующих обработчиков
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    
    # Логирование путей к логам
    logger = logging.getLogger("main")
    logger.info(f"Логирование настроено. Уровень: {config.log_level}")
    logger.info(f"Логи сохраняются в: {log_file_path}")
    
    # Добавление пути к логам в конфигурацию для других компонентов
    config.log_file_path = log_file_path

class CustomException(Exception):
    """Базовый класс для кастомных исключений приложения"""
    pass

class ConfigurationError(CustomException):
    """Ошибка конфигурации системы"""
    pass

class AgentExecutionError(CustomException):
    """Ошибка выполнения агента"""
    pass

class AgentRuntimeError(CustomException):
    """Ошибка во время выполнения агента"""
    pass

class Application:
    """
    Основной класс приложения, инкапсулирующий всю логику инициализации и выполнения.
    Предназначен для последующего переноса в SystemContext.
    """
    
    def __init__(self, args: argparse.Namespace):
        """
        Инициализация приложения с аргументами командной строки.
        """
        self.args = args
        self.config = None
        self.system_context = None

    async def initialize(self) -> None:
        """
        Полная инициализация системы.
        """
        # 1. Загрузка конфигурации
        self.config = get_config(profile=self.args.profile)
        
        # 2. Применение переопределений из аргументов
        self._apply_config_overrides()
        
        # 3. Настройка логирования
        setup_logging(self.config)
        
        logger = logging.getLogger("main")
        logger.info("Создание системного контекста...")
        
        # 4. Создание системного контекста
        self.system_context = SystemContext(self.config)
        
        # 5. Инициализация системного контекста
        logger.info("Инициализация системного контекста...")
        success = await self.system_context.initialize()
        if not success:
            logger.error("Ошибка инициализации системного контекста")
            raise ConfigurationError("Не удалось инициализировать систему")
        
        logger.info("Система успешно инициализирована")
    
    def _apply_config_overrides(self) -> None:
        """
        Применение переопределений конфигурации из аргументов командной строки.
        """
        logger = logging.getLogger("main")
        
        # Переопределение режима отладки
        if self.args.debug:
            self.config.debug = True
            self.config.log_level = "DEBUG"
            logger.info("Включен режим отладки")
        
        # Переопределение параметров агента
        if hasattr(self.config, 'agent'):
            if self.args.max_steps is not None:
                self.config.agent.max_steps = self.args.max_steps
                logger.info(f"Максимальное количество шагов установлено в {self.args.max_steps}")
            
            if self.args.temperature is not None:
                if hasattr(self.config.agent, 'parameters'):
                    self.config.agent.parameters.temperature = self.args.temperature
                else:
                    self.config.agent.temperature = self.args.temperature
                logger.info(f"Температура установлена в {self.args.temperature}")
            
            if self.args.max_tokens is not None:
                if hasattr(self.config.agent, 'parameters'):
                    self.config.agent.parameters.max_tokens = self.args.max_tokens
                logger.info(f"Максимальное количество токенов установлено в {self.args.max_tokens}")
            
            if self.args.strategy:
                self.config.agent.default_strategy = self.args.strategy
                logger.info(f"Стратегия установлена в {self.args.strategy}")
    
    async def run(self) -> Dict[str, Any]:
        """
        Запуск основного процесса выполнения агента.
        Возвращает результаты выполнения в виде словаря.
        """
        logger = logging.getLogger("main")
        
        try:

            logger.info(f"Запуск агента с целью: {self.args.goal}")
            
            # 2. Создание и запуск агента
            agent = await self.system_context.create_agent(
                parameters=getattr(self.config.agent, 'parameters', {})
            )

            agent.session.set_goal(self.args.goal)
            
            # 3. Выполнение агента
            start_time = datetime.now()
            result = await agent.execute(self.args.goal)
            end_time = datetime.now()
            
            # 4. Сохранение результатов в сессию
            self.session.set_result(result)
            self.session.execution_time = (end_time - start_time).total_seconds()
            
            logger.info(f"Агент успешно завершил выполнение за {self.session.execution_time:.2f} секунд")
            
            return {
                "success": True,
                "goal": self.args.goal,
                "result": result,
                "session_id": self.session.session_id,
                "execution_time": self.session.execution_time,
                "steps_taken": self.session.steps_taken
            }
            
        except Exception as e:
            logger.error(f"Ошибка во время выполнения агента: {str(e)}", exc_info=True)
            return {
                "success": False,
                "goal": self.args.goal,
                "error": str(e),
                "error_type": type(e).__name__
            }
    
    async def shutdown(self) -> None:
        """
        Корректное завершение работы приложения.
        """
        logger = logging.getLogger("main")
        
        if self.system_context:
            logger.info("Завершение работы системного контекста...")
            await self.system_context.shutdown()
        
        if self.session_manager:
            logger.info("Завершение работы менеджера сессий...")
            await self.session_manager.shutdown()
    
    def save_results(self, result: Dict[str, Any]) -> None:
        """
        Сохранение результатов выполнения в файл при необходимости.
        """
        if self.args.output and result.get("success", False):
            try:
                # Логика сохранения результатов в файл
                os.makedirs(os.path.dirname(os.path.abspath(self.args.output)), exist_ok=True)
                
                with open(self.args.output, 'w', encoding='utf-8') as f:
                    if self.args.output.endswith('.json'):
                        json.dump(result, f, indent=2, ensure_ascii=False)
                    else:
                        f.write(f"Цель: {result['goal']}\n")
                        f.write(f"Результат: {result['result']}\n")
                        f.write(f"ID сессии: {result['session_id']}\n")
                        f.write(f"Время выполнения: {result['execution_time']:.2f} секунд\n")
                
                print(f"\nРезультаты сохранены в файл: {self.args.output}")
                
            except Exception as e:
                print(f"Ошибка при сохранении результатов: {str(e)}")
    
    def print_results(self, result: Dict[str, Any]) -> None:
        """
        Вывод результатов выполнения в консоль.
        """
        print("\n" + "="*80)
        print("РЕЗУЛЬТАТ ВЫПОЛНЕНИЯ")
        print("="*80)
        print(f"Цель: {result['goal']}")
        
        if result.get("success", False):
            print(f"Ответ: {result['result']}")
            print(f"ID сессии: {result['session_id']}")
            print(f"Время выполнения: {result['execution_time']:.2f} секунд")
            if "steps_taken" in result:
                print(f"Шагов выполнено: {result['steps_taken']}")
        else:
            print(f"Ошибка: {result['error']}")
            print(f"Тип ошибки: {result['error_type']}")
        
        print("="*80)

def parse_arguments() -> argparse.Namespace:
    """
    Парсинг аргументов командной строки.
    """
    parser = argparse.ArgumentParser(description="Запуск агента для выполнения задач")
    
    # Основной параметр - вопрос
    parser.add_argument("goal", type=str, nargs="?", default="Какие книги написал Пушкин?",
                        help="Цель для агента (вопрос или задача)")
    
    # Параметры для переопределения конфигурации
    parser.add_argument("--profile", type=str, choices=["dev", "staging", "prod"], default="dev",
                        help="Профиль конфигурации (dev/staging/prod)")
    parser.add_argument("--debug", action="store_true",
                        help="Включить режим отладки")
    parser.add_argument("--max-steps", type=int, default=None,
                        help="Максимальное количество шагов рассуждений")
    parser.add_argument("--max-tokens", type=int, default=None,
                        help="Максимальное количество токенов для генерации")
    parser.add_argument("--temperature", type=float, default=None,
                        help="Температура генерации (0.0-1.0)")
    parser.add_argument("--output", type=str,
                        help="Файл для сохранения результатов")
    parser.add_argument("--strategy", type=str, choices=["react", "plan_and_execute", "chain_of_thought"],
                        help="Стратегия рассуждений агента")
    
    return parser.parse_args()

async def main_async() -> int:
    """
    Асинхронная основная функция приложения.
    """
    # 1. Парсинг аргументов
    args = parse_arguments()
    
    # 2. Создание и инициализация приложения
    app = Application(args)
    
    try:
        # Настройка обработчика сигналов для graceful shutdown
        def signal_handler(sig, frame):
            print(f"\nПолучен сигнал {sig}. Завершаем работу...")
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        await app.initialize()
        
        # 3. Выполнение основной логики
        result = await app.run()
        
        # 4. Вывод и сохранение результатов
        app.print_results(result)
        app.save_results(result)
        
        return 0 if result.get("success", False) else 1
        
    except ConfigurationError as e:
        print(f"Ошибка конфигурации: {str(e)}")
        return 2
    except AgentExecutionError as e:
        print(f"Ошибка выполнения агента: {str(e)}")
        return 3
    except Exception as e:
        print(f"Необработанное исключение: {str(e)}")
        return 4
    finally:
        # 5. Graceful shutdown
        await app.shutdown()

def main() -> int:
    """
    Синхронная точка входа в программу.
    """
    try:
        return asyncio.run(main_async())
    except KeyboardInterrupt:
        print("\nПрограмма прервана пользователем")
        return 0
    except Exception as e:
        print(f"Критическая ошибка: {str(e)}")
        return 5

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)