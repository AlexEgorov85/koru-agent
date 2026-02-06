# Система инструментов

Система инструментов (Tools System) - это важная часть Composable AI Agent Framework, обеспечивающая агентам доступ к различным внешним возможностям и функциям. Инструменты позволяют агентам взаимодействовать с внешней средой, выполнять специфические задачи и расширять свои возможности за счет интеграции с различными системами.

## Определение

Инструмент - это программная абстракция, предоставляющая агенту возможность выполнить определенную функцию или взаимодействовать с внешней системой. Инструменты отличаются от атомарных действий тем, что они часто интегрируются с внешними API и сервисами, в то время как атомарные действия более ориентированы на внутренние операции системы.

## Архитектура системы инструментов

Система инструментов включает следующие компоненты:

### 1. Интерфейс инструмента
- Определяет общий интерфейс для всех инструментов
- Обеспечивает единообразие в использовании различных инструментов
- Поддерживает валидацию параметров и обработку ошибок

### 2. Фабрика инструментов
- Создает экземпляры инструментов
- Управляет зависимостями инструментов
- Обеспечивает конфигурацию инструментов

### 3. Регистр инструментов
- Хранит информацию о доступных инструментах
- Обеспечивает поиск и выбор инструментов
- Управляет метаданными инструментов

## Интерфейс инструмента

Инструменты реализуют общий интерфейс, определенный в `infrastructure/tools/`:

```python
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from pydantic import BaseModel

class ToolMetadata(BaseModel):
    """Метаданные инструмента"""
    name: str
    description: str
    parameters_schema: Dict[str, Any]
    return_schema: Dict[str, Any]
    category: str
    version: str = "1.0.0"

class ITool(ABC):
    """Интерфейс инструмента"""
    
    @property
    @abstractmethod
    def metadata(self) -> ToolMetadata:
        """Метаданные инструмента"""
        pass
    
    @abstractmethod
    async def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Выполнить инструмент с указанными параметрами"""
        pass
    
    @abstractmethod
    def validate_parameters(self, parameters: Dict[str, Any]) -> bool:
        """Проверить корректность параметров"""
        pass

class BaseTool(ITool, ABC):
    """Базовый класс для инструментов"""
    
    def __init__(self):
        self._is_initialized = False
    
    async def initialize(self):
        """Инициализировать инструмент"""
        self._is_initialized = True
    
    async def cleanup(self):
        """Очистить ресурсы инструмента"""
        self._is_initialized = False
```

## Типы инструментов

### 1. Системные инструменты
- **File Reader Tool**: Чтение файлов с файловой системы
- **File Writer Tool**: Запись файлов в файловую систему
- **File Lister Tool**: Перечисление файлов в директории
- **Safe File Reader Tool**: Безопасное чтение файлов с ограничениями

### 2. Инструменты анализа
- **AST Parser Tool**: Парсинг AST (Abstract Syntax Tree) для различных языков
- **Code Analysis Tool**: Анализ кода на наличие паттернов, уязвимостей и т.д.
- **Text Similarity Tool**: Анализ схожести текстов

### 3. Инструменты баз данных
- **SQL Tool**: Выполнение SQL-запросов к базам данных
- **Query Builder Tool**: Построение SQL-запросов
- **Database Connection Tool**: Управление подключениями к базам данных

### 4. Сетевые инструменты
- **HTTP Client Tool**: Выполнение HTTP-запросов
- **API Integration Tool**: Интеграция с внешними API
- **Web Scraper Tool**: Извлечение данных с веб-сайтов

## Примеры инструментов

### 1. Инструмент чтения файлов
```python
class FileReaderTool(BaseTool):
    """Инструмент для чтения файлов"""
    
    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="file_reader",
            description="Чтение содержимого файла",
            parameters_schema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Путь к файлу для чтения"
                    }
                },
                "required": ["path"]
            },
            return_schema={
                "type": "object",
                "properties": {
                    "success": {"type": "boolean"},
                    "content": {"type": "string"},
                    "error": {"type": "string"}
                }
            },
            category="filesystem"
        )
    
    async def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Выполнить чтение файла"""
        if not self.validate_parameters(parameters):
            return {
                "success": False,
                "error": "Некорректные параметры"
            }
        
        file_path = parameters["path"]
        
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read()
            
            return {
                "success": True,
                "content": content
            }
        except FileNotFoundError:
            return {
                "success": False,
                "error": f"Файл не найден: {file_path}"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def validate_parameters(self, parameters: Dict[str, Any]) -> bool:
        """Проверить параметры"""
        return "path" in parameters and isinstance(parameters["path"], str)
```

### 2. Инструмент выполнения SQL-запросов
```python
class SqlTool(BaseTool):
    """Инструмент для выполнения SQL-запросов"""
    
    def __init__(self, connection_string: str):
        super().__init__()
        self.connection_string = connection_string
    
    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="sql_tool",
            description="Выполнение SQL-запроса к базе данных",
            parameters_schema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "SQL-запрос для выполнения"
                    }
                },
                "required": ["query"]
            },
            return_schema={
                "type": "object",
                "properties": {
                    "success": {"type": "boolean"},
                    "results": {"type": "array"},
                    "row_count": {"type": "integer"},
                    "error": {"type": "string"}
                }
            },
            category="database"
        )
    
    async def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Выполнить SQL-запрос"""
        if not self.validate_parameters(parameters):
            return {
                "success": False,
                "error": "Некорректные параметры"
            }
        
        query = parameters["query"]
        
        try:
            # Логика выполнения запроса
            # ...
            results = []
            row_count = len(results)
            
            return {
                "success": True,
                "results": results,
                "row_count": row_count
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def validate_parameters(self, parameters: Dict[str, Any]) -> bool:
        """Проверить параметры"""
        return "query" in parameters and isinstance(parameters["query"], str)
```

## Фабрика инструментов

Система включает фабрику инструментов для создания экземпляров:

```python
from infrastructure.factories.tool_factory import ToolFactory

class ToolFactory:
    """Фабрика для создания инструментов"""
    
    def __init__(self):
        self.tool_classes = {}
    
    def register_tool_class(self, name: str, tool_class: type):
        """Зарегистрировать класс инструмента"""
        self.tool_classes[name] = tool_class
    
    async def create_tool(self, name: str, **kwargs) -> ITool:
        """Создать экземпляр инструмента"""
        if name not in self.tool_classes:
            raise ValueError(f"Инструмент {name} не зарегистрирован")
        
        tool_class = self.tool_classes[name]
        tool_instance = tool_class(**kwargs)
        await tool_instance.initialize()
        
        return tool_instance
```

## Интеграция с агентами

Инструменты интегрируются с агентами следующим образом:

```python
# Регистрация инструментов в агенте
tool_factory = ToolFactory()
file_reader = await tool_factory.create_tool("file_reader")

# Использование инструмента в паттерне мышления
result = await file_reader.execute({
    "path": "/path/to/file.txt"
})

if result["success"]:
    # Обработка результата
    analysis_result = await agent.execute_composable_pattern(
        pattern_name="text_analysis",
        context={
            "text": result["content"]
        }
    )
```

## Безопасность и валидация

Система инструментов включает механизмы безопасности:

### 1. Валидация параметров
- Проверка соответствия параметров схеме
- Проверка типов данных
- Проверка допустимых значений

### 2. Ограничение доступа
- Контроль доступа к файловой системе
- Ограничение сетевых запросов
- Ограничение ресурсов

### 3. Аудит использования
- Логирование вызовов инструментов
- Мониторинг использования
- Обнаружение аномального поведения

## Навыки (Skills)

В дополнение к инструментам система поддерживает концепцию навыков (Skills) - более высокоуровневых абстракций, которые могут комбинировать несколько инструментов и атомарных действий:

```python
from abc import ABC, abstractmethod
from typing import Any, Dict

class ISkill(ABC):
    """Интерфейс навыка"""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Название навыка"""
        pass
    
    @abstractmethod
    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Выполнить навык"""
        pass

class CodeAnalysisSkill(ISkill):
    """Навык анализа кода"""
    
    def __init__(self, file_reader_tool: ITool, ast_parser_tool: ITool):
        self.file_reader = file_reader_tool
        self.ast_parser = ast_parser_tool
    
    @property
    def name(self) -> str:
        return "code_analysis_skill"
    
    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Выполнить анализ кода"""
        file_path = context["file_path"]
        
        # Чтение файла
        read_result = await self.file_reader.execute({"path": file_path})
        if not read_result["success"]:
            return {"success": False, "error": read_result["error"]}
        
        # Парсинг AST
        parse_result = await self.ast_parser.execute({
            "code": read_result["content"],
            "language": context.get("language", "python")
        })
        
        return {
            "success": True,
            "analysis": parse_result
        }
```

## Преимущества системы инструментов

- **Модульность**: Четкое разделение функциональности на независимые инструменты
- **Повторное использование**: Возможность использования инструментов в разных контекстах
- **Расширяемость**: Легкое добавление новых инструментов
- **Безопасность**: Встроенные механизмы валидации и контроля доступа
- **Тестируемость**: Простота тестирования отдельных инструментов
- **Интеграция**: Легкая интеграция с внешними системами
- **Гибкость**: Возможность комбинации инструментов в навыки

## Интеграция с другими компонентами

Система инструментов интегрирована с:
- **Агентами**: Предоставление дополнительных возможностей
- **Паттернами мышления**: Использование как строительные блоки
- **Атомарными действиями**: Совместное использование для решения задач
- **Системой событий**: Генерация событий при выполнении инструментов
- **Системой управления доменами**: Активация доменно-специфических инструментов