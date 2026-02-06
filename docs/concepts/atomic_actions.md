# Атомарные действия

Атомарные действия (Atomic Actions) - это минимальные неделимые операции, которые могут быть выполнены агентом в рамках решения задачи. Атомарные действия являются строительными блоками более сложных операций и обеспечивают взаимодействие агента с внешней средой.

## Определение

Атомарное действие - это операция, которая:
- Имеет четко определенный интерфейс
- Выполняет одну конкретную задачу
- Имеет фиксированный набор входных и выходных параметров
- Является неделимой (не может быть прервана в процессе выполнения)
- Обеспечивает согласованность состояния

## Архитектура атомарных действий

Атомарные действия интегрированы в систему следующим образом:

### 1. Определение действия
- Интерфейс действия с четко определенными входными и выходными параметрами
- Валидация параметров перед выполнением
- Обработка ошибок и исключений

### 2. Исполнение действия
- Вызов действия через исполнителя атомарных действий
- Обработка результата действия
- Обновление состояния агента

### 3. Интеграция с паттернами мышления
- Использование действий в рамках паттернов мышления
- Комбинация действий для решения сложных задач
- Управление зависимостями между действиями

## Интерфейс атомарного действия

Атомарные действия реализуют общий интерфейс, определенный в `application/orchestration/atomic_actions/`:

```python
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from pydantic import BaseModel

class AtomicActionConfig(BaseModel):
    """Конфигурация атомарного действия"""
    timeout: int = 30  # Таймаут выполнения в секундах
    retry_count: int = 3  # Количество попыток выполнения
    required_resources: list = []  # Требуемые ресурсы

class IAtomicAction(ABC):
    """Интерфейс атомарного действия"""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Уникальное имя действия"""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Описание действия"""
        pass
    
    @property
    @abstractmethod
    def config(self) -> AtomicActionConfig:
        """Конфигурация действия"""
        pass
    
    @abstractmethod
    async def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Выполнить атомарное действие
        
        Args:
            parameters: Параметры выполнения действия
            
        Returns:
            Результат выполнения действия
        """
        pass
    
    @abstractmethod
    def validate_parameters(self, parameters: Dict[str, Any]) -> bool:
        """Проверить корректность параметров"""
        pass
```

## Типы атомарных действий

### 1. Системные действия
- **file_operations**: Операции с файловой системой (чтение, запись, удаление файлов)
- **process_execution**: Запуск и управление внешними процессами
- **network_operations**: Сетевые операции (HTTP-запросы, соединения)
- **database_operations**: Операции с базами данных

### 2. Интеллектуальные действия
- **llm_interaction**: Взаимодействие с LLM (генерация текста, анализ)
- **data_analysis**: Анализ данных и извлечение информации
- **pattern_matching**: Поиск и сопоставление паттернов
- **validation**: Проверка и валидация данных

### 3. Интеграционные действия
- **api_calls**: Вызов внешних API
- **service_integration**: Интеграция с внешними сервисами
- **notification**: Отправка уведомлений
- **logging**: Ведение логов

## Примеры атомарных действий

### 1. Действие чтения файла
```python
class FileReaderAction(IAtomicAction):
    """Действие для чтения содержимого файла"""
    
    @property
    def name(self) -> str:
        return "file_reader"
    
    @property
    def description(self) -> str:
        return "Чтение содержимого файла"
    
    @property
    def config(self) -> AtomicActionConfig:
        return AtomicActionConfig(
            timeout=10,
            retry_count=2,
            required_resources=["filesystem"]
        )
    
    async def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Выполнить чтение файла"""
        if not self.validate_parameters(parameters):
            raise ValueError("Некорректные параметры")
        
        file_path = parameters["path"]
        
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read()
            
            return {
                "success": True,
                "content": content,
                "size": len(content)
            }
        except FileNotFoundError:
            return {
                "success": False,
                "error": "Файл не найден",
                "file_path": file_path
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "file_path": file_path
            }
    
    def validate_parameters(self, parameters: Dict[str, Any]) -> bool:
        """Проверить параметры"""
        return "path" in parameters and isinstance(parameters["path"], str)
```

### 2. Действие выполнения SQL-запроса
```python
class SqlQueryAction(IAtomicAction):
    """Действие для выполнения SQL-запроса"""
    
    @property
    def name(self) -> str:
        return "sql_query"
    
    @property
    def description(self) -> str:
        return "Выполнение SQL-запроса к базе данных"
    
    @property
    def config(self) -> AtomicActionConfig:
        return AtomicActionConfig(
            timeout=30,
            retry_count=3,
            required_resources=["database"]
        )
    
    async def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Выполнить SQL-запрос"""
        if not self.validate_parameters(parameters):
            raise ValueError("Некорректные параметры")
        
        query = parameters["query"]
        connection_string = parameters.get("connection_string")
        
        # Логика выполнения запроса
        # ...
        
        return {
            "success": True,
            "results": results,
            "row_count": len(results)
        }
    
    def validate_parameters(self, parameters: Dict[str, Any]) -> bool:
        """Проверить параметры"""
        return "query" in parameters and isinstance(parameters["query"], str)
```

## Исполнитель атомарных действий

Система включает исполнитель атомарных действий, который управляет их выполнением:

```python
class AtomicActionExecutor:
    """Исполнитель атомарных действий"""
    
    def __init__(self):
        self.actions = {}
    
    def register_action(self, action: IAtomicAction):
        """Зарегистрировать атомарное действие"""
        self.actions[action.name] = action
    
    async def execute_action(
        self,
        action_name: str,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Выполнить атомарное действие"""
        if action_name not in self.actions:
            raise ValueError(f"Действие {action_name} не зарегистрировано")
        
        action = self.actions[action_name]
        
        # Валидация параметров
        if not action.validate_parameters(parameters):
            raise ValueError("Некорректные параметры действия")
        
        # Выполнение действия
        result = await action.execute(parameters)
        
        return result
```

## Интеграция с агентами

Атомарные действия интегрируются с агентами следующим образом:

```python
# Выполнение атомарного действия через агента
result = await agent.execute_atomic_action(
    action_name="file_reader",
    parameters={
        "path": "/path/to/file.txt"
    }
)

# Использование результата действия в паттерне мышления
if result["success"]:
    analysis_result = await agent.execute_composable_pattern(
        pattern_name="text_analysis",
        context={
            "text": result["content"]
        }
    )
```

## Валидация и безопасность

Система атомарных действий включает механизмы валидации и безопасности:

- **Валидация параметров**: Проверка входных данных перед выполнением
- **Ограничение ресурсов**: Контроль использования системных ресурсов
- **Изоляция выполнения**: Защита от побочных эффектов действий
- **Логирование**: Отслеживание всех выполненных действий
- **Таймауты**: Предотвращение бесконечного выполнения

## Преимущества атомарных действий

- **Модульность**: Четкое разделение функциональности на независимые блоки
- **Повторное использование**: Возможность использования действий в разных контекстах
- **Тестируемость**: Простота тестирования отдельных компонентов
- **Безопасность**: Контроль и ограничение возможных операций
- **Масштабируемость**: Легкое добавление новых действий
- **Прозрачность**: Ясное понимание того, какие операции выполняются

## Примеры использования

### 1. Анализ кода
Агент может использовать следующую последовательность атомарных действий:
- `file_reader`: Чтение исходного кода
- `ast_parser`: Парсинг AST
- `pattern_matcher`: Поиск паттернов
- `report_generator`: Генерация отчета

### 2. Обработка данных
- `file_reader`: Чтение данных
- `data_validator`: Проверка данных
- `sql_query`: Выполнение запросов
- `data_transformer`: Преобразование данных

### 3. Взаимодействие с API
- `http_request`: Вызов внешнего API
- `response_parser`: Парсинг ответа
- `data_processor`: Обработка данных
- `notification_sender`: Отправка уведомлений

## Интеграция с другими компонентами

Атомарные действия тесно интегрированы с:
- **Паттернами мышления**: Используются как строительные блоки
- **Системой инструментов**: Могут быть представлены как специальные инструменты
- **Управлением состоянием**: Влияют на состояние агента
- **Системой событий**: Генерируют события при выполнении
- **Системой логирования**: Обеспечивают информацию для отладки