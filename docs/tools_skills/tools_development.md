# Разработка инструментов (Tools)

Инструменты (Tools) в Koru AI Agent Framework представляют собой специализированные компоненты, обеспечивающие доступ к внешним системам, API, файловой системе и другим ресурсам. В этом разделе описан процесс создания и интеграции пользовательских инструментов.

## Архитектура инструментов

### 1. Интерфейс инструмента

Все инструменты реализуют общий интерфейс:

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
    permissions: list = []

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
        self._required_permissions = []
    
    async def initialize(self):
        """Инициализировать инструмент"""
        self._is_initialized = True
    
    async def cleanup(self):
        """Очистить ресурсы инструмента"""
        self._is_initialized = False
```

### 2. Фабрика инструментов

Фабрика для создания экземпляров инструментов:

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

## Создание пользовательских инструментов

### 1. Простой инструмент для чтения файлов

```python
import os
from pathlib import Path

class FileReaderTool(BaseTool):
    """Инструмент для чтения файлов"""
    
    def __init__(self, max_file_size: int = 10 * 1024 * 1024):  # 10MB
        super().__init__()
        self.max_file_size = max_file_size
        self._required_permissions = ["read_file"]
    
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
                    },
                    "encoding": {
                        "type": "string",
                        "default": "utf-8",
                        "description": "Кодировка файла"
                    }
                },
                "required": ["path"]
            },
            return_schema={
                "type": "object",
                "properties": {
                    "success": {"type": "boolean"},
                    "content": {"type": "string"},
                    "size": {"type": "integer"},
                    "encoding": {"type": "string"},
                    "error": {"type": "string"}
                }
            },
            category="filesystem",
            permissions=["read_file"]
        )
    
    async def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Выполнить чтение файла"""
        if not self.validate_parameters(parameters):
            return {
                "success": False,
                "error": "Некорректные параметры"
            }
        
        file_path = parameters["path"]
        encoding = parameters.get("encoding", "utf-8")
        
        try:
            # Проверка безопасности пути
            if not self._is_safe_path(file_path):
                return {
                    "success": False,
                    "error": "Небезопасный путь к файлу"
                }
            
            path = Path(file_path)
            
            # Проверка существования файла
            if not path.exists():
                return {
                    "success": False,
                    "error": f"Файл не найден: {file_path}"
                }
            
            # Проверка размера файла
            file_size = path.stat().st_size
            if file_size > self.max_file_size:
                return {
                    "success": False,
                    "error": f"Файл слишком большой: {file_size} байт, максимум {self.max_file_size}"
                }
            
            # Чтение файла
            with open(path, 'r', encoding=encoding) as file:
                content = file.read()
            
            return {
                "success": True,
                "content": content,
                "size": file_size,
                "encoding": encoding
            }
        except UnicodeDecodeError:
            return {
                "success": False,
                "error": f"Не удалось декодировать файл с кодировкой {encoding}"
            }
        except PermissionError:
            return {
                "success": False,
                "error": f"Нет доступа к файлу: {file_path}"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Ошибка при чтении файла: {str(e)}"
            }
    
    def validate_parameters(self, parameters: Dict[str, Any]) -> bool:
        """Проверить параметры"""
        if "path" not in parameters:
            return False
        
        path = parameters["path"]
        if not isinstance(path, str) or not path.strip():
            return False
        
        # Дополнительные проверки могут быть добавлены здесь
        return True
    
    def _is_safe_path(self, path: str) -> bool:
        """Проверить, является ли путь безопасным для чтения"""
        try:
            # Преобразовать в абсолютный путь
            abs_path = Path(path).resolve()
            
            # Получить корневой каталог (где запущен фреймворк)
            root_path = Path.cwd().resolve()
            
            # Проверить, что путь находится внутри корневого каталога
            abs_path.relative_to(root_path)
            return True
        except ValueError:
            # Если путь вне корневого каталога, он небезопасен
            return False
```

### 2. Инструмент для выполнения SQL-запросов

```python
import sqlite3
import asyncio
from contextlib import contextmanager

class SQLTool(BaseTool):
    """Инструмент для выполнения SQL-запросов"""
    
    def __init__(self, connection_string: str, max_rows: int = 1000):
        super().__init__()
        self.connection_string = connection_string
        self.max_rows = max_rows
        self._required_permissions = ["execute_sql"]
    
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
                    },
                    "parameters": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Параметры для параметризованного запроса"
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
                    "columns": {"type": "array"},
                    "error": {"type": "string"}
                }
            },
            category="database",
            permissions=["execute_sql"]
        )
    
    async def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Выполнить SQL-запрос"""
        if not self.validate_parameters(parameters):
            return {
                "success": False,
                "error": "Некорректные параметры"
            }
        
        query = parameters["query"]
        query_params = parameters.get("parameters", [])
        
        try:
            # Проверка безопасности запроса
            if not self._is_safe_query(query):
                return {
                    "success": False,
                    "error": "Запрос содержит потенциально опасные операции"
                }
            
            # Выполнение запроса
            result = await self._execute_query(query, query_params)
            
            return {
                "success": True,
                "results": result["rows"],
                "row_count": result["count"],
                "columns": result["columns"]
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Ошибка при выполнении SQL-запроса: {str(e)}"
            }
    
    def validate_parameters(self, parameters: Dict[str, Any]) -> bool:
        """Проверить параметры"""
        if "query" not in parameters:
            return False
        
        query = parameters["query"]
        if not isinstance(query, str) or not query.strip():
            return False
        
        return True
    
    async def _execute_query(self, query: str, params: list = None) -> Dict[str, Any]:
        """Выполнить SQL-запрос"""
        # Используем пул подключений или создаем новое подключение
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Выполняем запрос
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            # Для SELECT-запросов получаем результаты
            if query.strip().upper().startswith('SELECT'):
                rows = cursor.fetchall()
                
                # Ограничиваем количество возвращаемых строк
                if len(rows) > self.max_rows:
                    rows = rows[:self.max_rows]
                
                columns = [description[0] for description in cursor.description]
                
                return {
                    "rows": rows,
                    "count": len(rows),
                    "columns": columns
                }
            else:
                # Для других запросов возвращаем количество затронутых строк
                conn.commit()
                return {
                    "rows": [],
                    "count": cursor.rowcount,
                    "columns": []
                }
    
    @contextmanager
    def _get_connection(self):
        """Получить соединение с базой данных"""
        conn = sqlite3.connect(self.connection_string)
        try:
            yield conn
        finally:
            conn.close()
    
    def _is_safe_query(self, query: str) -> bool:
        """Проверить, является ли запрос безопасным"""
        # Привести к нижнему регистру для проверки
        lower_query = query.lower().strip()
        
        # Проверить на потенциально опасные операции
        dangerous_keywords = [
            'drop', 'delete', 'truncate', 'alter', 'create', 'insert',
            'update', 'grant', 'revoke', 'exec', 'execute'
        ]
        
        # Разрешить только безопасные операции (в основном SELECT)
        if not lower_query.startswith('select'):
            # Но позволим некоторые UPDATE/DELETE с условиями
            if any(keyword in lower_query for keyword in ['drop', 'truncate', 'grant', 'revoke']):
                return False
        
        return True
```

### 3. Инструмент для взаимодействия с API

```python
import aiohttp
import json

class APIClientTool(BaseTool):
    """Инструмент для взаимодействия с REST API"""
    
    def __init__(self, base_url: str, default_headers: Dict[str, str] = None):
        super().__init__()
        self.base_url = base_url.rstrip('/')
        self.default_headers = default_headers or {}
        self._required_permissions = ["make_http_requests"]
    
    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="api_client",
            description="Взаимодействие с REST API",
            parameters_schema={
                "type": "object",
                "properties": {
                    "endpoint": {
                        "type": "string",
                        "description": "Конечная точка API"
                    },
                    "method": {
                        "type": "string",
                        "enum": ["GET", "POST", "PUT", "DELETE", "PATCH"],
                        "default": "GET",
                        "description": "HTTP метод"
                    },
                    "headers": {
                        "type": "object",
                        "description": "Дополнительные заголовки запроса"
                    },
                    "params": {
                        "type": "object",
                        "description": "Параметры запроса (для GET)"
                    },
                    "data": {
                        "type": "object",
                        "description": "Тело запроса (для POST, PUT, PATCH)"
                    },
                    "timeout": {
                        "type": "integer",
                        "default": 30,
                        "description": "Таймаут запроса в секундах"
                    }
                },
                "required": ["endpoint"]
            },
            return_schema={
                "type": "object",
                "properties": {
                    "success": {"type": "boolean"},
                    "status_code": {"type": "integer"},
                    "response": {"type": "object"},
                    "headers": {"type": "object"},
                    "error": {"type": "string"}
                }
            },
            category="api",
            permissions=["make_http_requests"]
        )
    
    async def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Выполнить API-запрос"""
        if not self.validate_parameters(parameters):
            return {
                "success": False,
                "error": "Некорректные параметры"
            }
        
        endpoint = parameters["endpoint"]
        method = parameters.get("method", "GET").upper()
        headers = parameters.get("headers", {})
        params = parameters.get("params", {})
        data = parameters.get("data", {})
        timeout = parameters.get("timeout", 30)
        
        try:
            # Проверка безопасности URL
            if not self._is_safe_endpoint(endpoint):
                return {
                    "success": False,
                    "error": "Небезопасная конечная точка API"
                }
            
            # Объединение заголовков
            all_headers = {**self.default_headers, **headers}
            
            # Выполнение запроса
            async with aiohttp.ClientSession() as session:
                request_kwargs = {
                    'url': f"{self.base_url}{endpoint}",
                    'headers': all_headers,
                    'timeout': aiohttp.ClientTimeout(total=timeout)
                }
                
                if method == "GET":
                    request_kwargs['params'] = params
                elif method in ["POST", "PUT", "PATCH"]:
                    request_kwargs['json'] = data
                elif method == "DELETE":
                    # DELETE обычно не имеет тела
                    pass
                
                async with session.request(method, **request_kwargs) as response:
                    response_data = await response.text()
                    
                    try:
                        # Попытаться распарсить JSON
                        json_data = json.loads(response_data)
                    except json.JSONDecodeError:
                        # Если не JSON, вернуть как текст
                        json_data = {"raw_response": response_data}
                    
                    return {
                        "success": True,
                        "status_code": response.status,
                        "response": json_data,
                        "headers": dict(response.headers)
                    }
        except aiohttp.ClientError as e:
            return {
                "success": False,
                "error": f"Ошибка HTTP-запроса: {str(e)}"
            }
        except asyncio.TimeoutError:
            return {
                "success": False,
                "error": f"Таймаут запроса: {timeout} секунд"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Ошибка при выполнении API-запроса: {str(e)}"
            }
    
    def validate_parameters(self, parameters: Dict[str, Any]) -> bool:
        """Проверить параметры"""
        if "endpoint" not in parameters:
            return False
        
        endpoint = parameters["endpoint"]
        if not isinstance(endpoint, str) or not endpoint.strip():
            return False
        
        method = parameters.get("method", "GET").upper()
        if method not in ["GET", "POST", "PUT", "DELETE", "PATCH"]:
            return False
        
        return True
    
    def _is_safe_endpoint(self, endpoint: str) -> bool:
        """Проверить, является ли конечная точка безопасной"""
        # Проверить на потенциально опасные паттерны
        unsafe_patterns = [
            '../',  # Попытка выхода из директории
            '..\\', # Windows стиль
            '%2e%2e',  # URL-кодированный ../
            'javascript:',  # XSS попытка
            'data:'  # Data URL
        ]
        
        normalized_endpoint = endpoint.lower()
        
        for pattern in unsafe_patterns:
            if pattern in normalized_endpoint:
                return False
        
        return True
```

## Интеграция инструментов с агентами

### 1. Регистрация инструментов

```python
# tools_registration.py
from infrastructure.factories.tool_factory import ToolFactory

async def register_agent_tools():
    """Регистрация инструментов для агентов"""
    
    # Создание фабрики инструментов
    tool_factory = ToolFactory()
    
    # Регистрация классов инструментов
    tool_factory.register_tool_class("file_reader", FileReaderTool)
    tool_factory.register_tool_class("sql_tool", SQLTool)
    tool_factory.register_tool_class("api_client", APIClientTool)
    
    # Создание экземпляров инструментов
    file_reader = await tool_factory.create_tool("file_reader", max_file_size=5 * 1024 * 1024)  # 5MB
    sql_tool = await tool_factory.create_tool("sql_tool", connection_string="db.sqlite", max_rows=500)
    api_client = await tool_factory.create_tool(
        "api_client", 
        base_url="https://api.example.com",
        default_headers={"User-Agent": "Composable-AI-Agent/1.0"}
    )
    
    return {
        "file_reader": file_reader,
        "sql_tool": sql_tool,
        "api_client": api_client
    }
```

### 2. Использование инструментов в агентах

```python
# agent_with_tools.py
from application.factories.agent_factory import AgentFactory
from domain.value_objects.domain_type import DomainType

class ToolEquippedAgent:
    """Агент с поддержкой инструментов"""
    
    def __init__(self, agent, tools_dict):
        self.agent = agent
        self.tools = tools_dict
    
    async def execute_tool(self, tool_name: str, parameters: Dict[str, Any]):
        """Выполнить инструмент через агента"""
        if tool_name not in self.tools:
            raise ValueError(f"Инструмент {tool_name} не доступен")
        
        tool = self.tools[tool_name]
        result = await tool.execute(parameters)
        
        return result
    
    async def execute_task_with_tools(self, task_description: str, required_tools: list = None):
        """Выполнить задачу с использованием инструментов"""
        if not required_tools:
            # Если инструменты не указаны, агент сам определит, какие нужны
            return await self.agent.execute_task(task_description)
        
        tool_results = {}
        
        # Выполнить необходимые инструменты
        for tool_name in required_tools:
            if tool_name in self.tools:
                # Для простоты, используем пустые параметры
                # В реальности параметры будут зависеть от задачи
                result = await self.execute_tool(tool_name, {})
                tool_results[tool_name] = result
        
        # Передать результаты инструментов в агент для дальнейшей обработки
        enhanced_context = {
            "original_task": task_description,
            "tool_results": tool_results
        }
        
        agent_result = await self.agent.execute_task(
            task_description=f"{task_description} с учетом результатов инструментов",
            context=enhanced_context
        )
        
        return {
            "tool_results": tool_results,
            "agent_result": agent_result
        }

# Пример использования
async def tool_equipped_agent_example():
    """Пример использования агента с инструментами"""
    
    # Создание агента
    agent = await AgentFactory().create_agent(
        agent_type="composable",
        domain=DomainType.DATA_PROCESSING
    )
    
    # Регистрация инструментов
    tools = await register_agent_tools()
    
    # Создание агента с инструментами
    tool_agent = ToolEquippedAgent(agent, tools)
    
    # Выполнение задачи с использованием инструмента чтения файлов
    result = await tool_agent.execute_task_with_tools(
        task_description="Проанализируй содержимое файла ./data/input.txt",
        required_tools=["file_reader"]
    )
    
    print(f"Результат выполнения: {result}")
    
    return result
```

## Лучшие практики создания инструментов

### 1. Безопасность

Обязательно реализуйте проверки безопасности:

```python
def _is_safe_path(self, path: str) -> bool:
    """Проверить, является ли путь безопасным для чтения"""
    try:
        # Преобразовать в абсолютный путь
        abs_path = Path(path).resolve()
        
        # Получить корневой каталог (где запущен фреймворк)
        root_path = Path.cwd().resolve()
        
        # Проверить, что путь находится внутри корневого каталога
        abs_path.relative_to(root_path)
        return True
    except ValueError:
        # Если путь вне корневого каталога, он небезопасен
        return False
```

### 2. Валидация параметров

Обязательно проверяйте входные параметры:

```python
def validate_parameters(self, parameters: Dict[str, Any]) -> bool:
    """Проверить параметры инструмента"""
    required_fields = ["path"]  # или другие обязательные поля
    if not all(field in parameters for field in required_fields):
        return False
    
    # Дополнительные проверки типов и значений
    if "path" in parameters and not isinstance(parameters["path"], str):
        return False
    
    # Проверка на потенциально опасные значения
    if "path" in parameters and "../" in parameters["path"]:
        return False
    
    return True
```

### 3. Обработка ошибок

Обеспечьте надежную обработку ошибок:

```python
async def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
    """Выполнить инструмент с обработкой ошибок"""
    try:
        # Валидация параметров
        if not self.validate_parameters(parameters):
            return {
                "success": False,
                "error": "Некорректные параметры"
            }
        
        # Основная логика выполнения
        result = await self._execute_main_logic(parameters)
        return {"success": True, **result}
    except ValidationError as e:
        return {
            "success": False,
            "error": f"Ошибка валидации: {str(e)}"
        }
    except ExternalServiceError as e:
        return {
            "success": False,
            "error": f"Ошибка внешнего сервиса: {str(e)}"
        }
    except SecurityError as e:
        return {
            "success": False,
            "error": f"Ошибка безопасности: {str(e)}"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Неожиданная ошибка: {str(e)}"
        }
```

### 4. Тестирование инструментов

Создавайте тесты для каждого инструмента:

```python
# test_tools.py
import pytest
from unittest.mock import Mock, patch, AsyncMock
import tempfile
import os

class TestFileReaderTool:
    @pytest.mark.asyncio
    async def test_file_reader_success(self):
        """Тест успешного чтения файла"""
        # Создание временного файла для теста
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as tmp:
            tmp.write("Тестовое содержимое файла")
            temp_file_path = tmp.name
        
        try:
            # Создание инструмента
            tool = FileReaderTool()
            
            # Выполнение инструмента
            result = await tool.execute({"path": temp_file_path})
            
            # Проверка результата
            assert result["success"] is True
            assert "Тестовое содержимое файла" in result["content"]
            assert result["size"] > 0
        finally:
            # Удаление временного файла
            os.unlink(temp_file_path)
    
    @pytest.mark.asyncio
    async def test_file_reader_file_not_found(self):
        """Тест обработки ошибки отсутствия файла"""
        tool = FileReaderTool()
        
        result = await tool.execute({"path": "/nonexistent/file.txt"})
        
        assert result["success"] is False
        assert "не найден" in result["error"].lower()

class TestSQLTool:
    @pytest.mark.asyncio
    async def test_sql_select_query(self):
        """Тест выполнения SELECT-запроса"""
        # Создание временной базы данных для теста
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_db:
            tmp_db_path = tmp_db.name
        
        try:
            # Создание тестовой таблицы
            import sqlite3
            conn = sqlite3.connect(tmp_db_path)
            conn.execute("CREATE TABLE test_table (id INTEGER, name TEXT)")
            conn.execute("INSERT INTO test_table VALUES (1, 'test')")
            conn.commit()
            conn.close()
            
            # Создание инструмента
            tool = SQLTool(tmp_db_path)
            
            # Выполнение запроса
            result = await tool.execute({
                "query": "SELECT * FROM test_table"
            })
            
            # Проверка результата
            assert result["success"] is True
            assert len(result["results"]) == 1
            assert result["results"][0][1] == "test"
        finally:
            # Удаление временной базы данных
            os.unlink(tmp_db_path)
```

## Интеграция с системой

### 1. Регистрация в системе

Инструменты должны быть зарегистрированы в системе для использования:

```python
# system_initialization.py
from application.services.system_initialization_service import SystemInitializationService

class ToolRegistrationService(SystemInitializationService):
    """Сервис регистрации инструментов в системе"""
    
    async def initialize_tools(self):
        """Инициализировать и зарегистрировать инструменты"""
        tools = await register_agent_tools()
        
        # Здесь может быть логика регистрации инструментов в центральном реестре
        for tool_name, tool_instance in tools.items():
            self.system_registry.register_tool(tool_name, tool_instance)
        
        print(f"Зарегистрировано {len(tools)} инструментов")
```

### 2. Мониторинг и логирование

Система должна логировать использование инструментов:

```python
import logging

class ToolWithLogging(BaseTool):
    """Инструмент с логированием"""
    
    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(self.metadata.name)
    
    async def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Выполнить инструмент с логированием"""
        self.logger.info(f"Executing tool with parameters keys: {list(parameters.keys())}")
        
        start_time = time.time()
        result = await super().execute(parameters)
        execution_time = time.time() - start_time
        
        self.logger.info(f"Tool execution completed in {execution_time:.2f}s")
        self.logger.info(f"Result success: {result.get('success', False)}")
        
        return result
```

Эти примеры показывают, как создавать и интегрировать пользовательские инструменты в Koru AI Agent Framework, обеспечивая безопасность, надежность и расширяемость системы.