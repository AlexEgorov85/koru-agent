# Руководство по интеграции Koru AI Agent Framework

В этом разделе описаны рекомендации и практики по интеграции Koru AI Agent Framework с внешними системами, API, базами данных и другими компонентами. Вы узнаете, как подключать фреймворк к различным внешним ресурсам и как обеспечивать безопасное и надежное взаимодействие.

## Общие принципы интеграции

### 1. Адаптеры и шлюзы

Фреймворк использует паттерны адаптеров и шлюзов для интеграции с внешними системами:

- **Адаптеры**: Преобразуют интерфейсы внешних систем к внутренним абстракциям
- **Шлюзы**: Обеспечивают доступ к внешним системам через унифицированный интерфейс
- **Порт и адаптер**: Разделяют внутреннюю логику от внешних зависимостей

### 2. Безопасность интеграции

При интеграции с внешними системами обязательно учитывайте:

- **Проверку безопасности**: Проверка всех внешних вызовов на безопасность
- **Ограничение доступа**: Ограничение ресурсов и возможностей
- **Фильтрацию данных**: Очистка чувствительных данных при передаче
- **Аутентификацию и авторизацию**: Проверка прав доступа к внешним системам

## Интеграция с внешними API

### 1. Создание API-адаптеров

Для интеграции с внешними API создайте специфические адаптеры:

```python
# infrastructure/gateways/api_gateway.py
import aiohttp
import asyncio
import time
from typing import Any, Dict, List
from domain.abstractions.gateway import IGateway
from domain.models.gateway.response import GatewayResponse

class IAPIGateway(IGateway):
    """Интерфейс для шлюза к внешним API"""
    
    @abstractmethod
    async def call_api(self, endpoint: str, method: str = "GET", data: Dict[str, Any] = None, headers: Dict[str, str] = None) -> GatewayResponse:
        """Вызвать внешнее API"""
        pass
    
    @abstractmethod
    async def batch_call_apis(self, requests: List[Dict[str, Any]]) -> List[GatewayResponse]:
        """Выполнить несколько вызовов API"""
        pass

class GenericAPIGateway(IAPIGateway):
    """Общий шлюз для взаимодействия с внешними API"""
    
    def __init__(self, base_url: str, default_headers: Dict[str, str] = None, rate_limit: int = 10):
        self.base_url = base_url.rstrip('/')
        self.default_headers = default_headers or {}
        self.rate_limit = rate_limit
        self._session = None
        self._rate_limiter = asyncio.Semaphore(rate_limit)
        self._request_history = []
        self._max_history_size = 1000
    
    async def initialize(self):
        """Инициализировать шлюз"""
        if not self._session:
            self._session = aiohttp.ClientSession(
                headers=self.default_headers,
                timeout=aiohttp.ClientTimeout(total=30)
            )
    
    async def call_api(self, endpoint: str, method: str = "GET", data: Dict[str, Any] = None, headers: Dict[str, str] = None) -> GatewayResponse:
        """Вызвать внешнее API с безопасностью и ограничениями"""
        
        # Проверить безопасность вызова
        if not self._is_safe_api_call(endpoint, method, data):
            return GatewayResponse(
                success=False,
                error="Небезопасный вызов API",
                status_code=400
            )
        
        # Проверить ограничения
        if not await self._check_rate_limit():
            return GatewayResponse(
                success=False,
                error="Превышен лимит вызовов API",
                status_code=429
            )
        
        # Добавить к базовым заголовкам
        all_headers = {**self.default_headers}
        if headers:
            all_headers.update(headers)
        
        url = f"{self.base_url}{endpoint}"
        
        try:
            async with self._rate_limiter:
                start_time = time.time()
                
                async with self._session.request(
                    method=method.upper(),
                    url=url,
                    json=data if method.upper() in ["POST", "PUT", "PATCH"] else None,
                    params=data if method.upper() == "GET" else None,
                    headers=all_headers
                ) as response:
                    response_data = await response.text()
                    response_time = time.time() - start_time
                    
                    # Проверить статус ответа
                    if response.status == 200:
                        try:
                            import json
                            json_data = json.loads(response_data)
                            success = True
                        except json.JSONDecodeError:
                            json_data = {"raw_response": response_data}
                            success = True
                    else:
                        json_data = {"error": response_data}
                        success = False
                    
                    gateway_response = GatewayResponse(
                        success=success,
                        data=json_data,
                        status_code=response.status,
                        response_time=response_time,
                        headers=dict(response.headers)
                    )
                    
                    # Залогировать вызов
                    self._log_api_call(endpoint, method, gateway_response)
                    
                    return gateway_response
        except aiohttp.ClientError as e:
            return GatewayResponse(
                success=False,
                error=f"Ошибка клиента API: {str(e)}",
                status_code=0
            )
        except asyncio.TimeoutError:
            return GatewayResponse(
                success=False,
                error="Таймаут вызова API",
                status_code=408
            )
        except Exception as e:
            return GatewayResponse(
                success=False,
                error=f"Внутренняя ошибка при вызове API: {str(e)}",
                status_code=500
            )
    
    async def batch_call_apis(self, requests: List[Dict[str, Any]]) -> List[GatewayResponse]:
        """Выполнить несколько вызовов API параллельно"""
        tasks = []
        
        for req in requests:
            task = self.call_api(
                endpoint=req.get("endpoint", ""),
                method=req.get("method", "GET"),
                data=req.get("data"),
                headers=req.get("headers")
            )
            tasks.append(task)
        
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Обработать исключения
        processed_responses = []
        for response in responses:
            if isinstance(response, Exception):
                processed_responses.append(GatewayResponse(
                    success=False,
                    error=f"Ошибка вызова API: {str(response)}",
                    status_code=500
                ))
            else:
                processed_responses.append(response)
        
        return processed_responses
    
    def _is_safe_api_call(self, endpoint: str, method: str, data: Dict[str, Any]) -> bool:
        """Проверить, является ли вызов API безопасным"""
        # Проверить endpoint на безопасность
        if not self._is_safe_endpoint(endpoint):
            return False
        
        # Проверить метод на безопасность
        allowed_methods = {"GET", "POST", "PUT", "PATCH", "DELETE"}
        if method.upper() not in allowed_methods:
            return False
        
        # Проверить данные на безопасность
        if data:
            return self._validate_api_data(data)
        
        return True
    
    def _is_safe_endpoint(self, endpoint: str) -> bool:
        """Проверить, является ли endpoint безопасным"""
        # Проверить на потенциально опасные паттерны
        unsafe_patterns = [
            r'\.\./',  # Попытка выхода из директории
            r'\.\.\\', # Windows стиль
            r'javascript:',  # XSS попытка
            r'data:',  # Data URL
            r'<script'  # HTML тег
        ]
        
        normalized_endpoint = endpoint.lower()
        
        for pattern in unsafe_patterns:
            import re
            if re.search(pattern, normalized_endpoint):
                return False
        
        return True
    
    def _validate_api_data(self, data: Dict[str, Any]) -> bool:
        """Проверить данные API на безопасность"""
        # Проверить чувствительные поля
        sensitive_fields = ["password", "token", "api_key", "secret", "credentials"]
        for field in sensitive_fields:
            if field in data:
                return False  # Не разрешать чувствительные данные в вызовах API
        
        # Проверить размер данных
        data_size = len(str(data))
        max_size = 10 * 1024 * 1024  # 10MB
        if data_size > max_size:
            return False
        
        return True
    
    async def _check_rate_limit(self) -> bool:
        """Проверить ограничение частоты вызовов"""
        # В реальной реализации здесь будет проверка
        # с использованием системы ограничения частоты
        return True
    
    def _log_api_call(self, endpoint: str, method: str, response: GatewayResponse):
        """Залогировать вызов API"""
        call_entry = {
            "timestamp": time.time(),
            "endpoint": endpoint,
            "method": method,
            "status_code": response.status_code,
            "response_time": response.response_time,
            "success": response.success
        }
        
        self._request_history.append(call_entry)
        
        # Ограничить размер истории
        if len(self._request_history) > self._max_history_size:
            self._request_history = self._request_history[-self._max_history_size:]
    
    async def cleanup(self):
        """Очистить ресурсы шлюза"""
        if self._session:
            await self._session.close()
    
    def get_request_stats(self) -> Dict[str, Any]:
        """Получить статистику по вызовам API"""
        if not self._request_history:
            return {
                "total_requests": 0,
                "successful_requests": 0,
                "failed_requests": 0,
                "avg_response_time": 0,
                "error_rate": 0
            }
        
        total_requests = len(self._request_history)
        successful_requests = len([r for r in self._request_history if r["success"]])
        failed_requests = total_requests - successful_requests
        
        total_response_time = sum(r["response_time"] for r in self._request_history if "response_time" in r)
        avg_response_time = total_response_time / successful_requests if successful_requests > 0 else 0
        
        error_rate = failed_requests / total_requests if total_requests > 0 else 0
        
        return {
            "total_requests": total_requests,
            "successful_requests": successful_requests,
            "failed_requests": failed_requests,
            "avg_response_time": avg_response_time,
            "error_rate": error_rate
        }
```

### 2. Интеграция с конкретными API

Пример интеграции с популярными API:

```python
# infrastructure/gateways/specific_api_gateways.py
from infrastructure.gateways.api_gateway import GenericAPIGateway

class GitHubAPIGateway(GenericAPIGateway):
    """Шлюз для интеграции с GitHub API"""
    
    def __init__(self, token: str, rate_limit: int = 5000):
        super().__init__(
            base_url="https://api.github.com",
            default_headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github.v3+json"
            },
            rate_limit=rate_limit
        )
        self.token = token
    
    async def get_repo_contents(self, owner: str, repo: str, path: str = "/") -> GatewayResponse:
        """Получить содержимое репозитория"""
        return await self.call_api(
            endpoint=f"/repos/{owner}/{repo}/contents{path}",
            method="GET"
        )
    
    async def create_issue(self, owner: str, repo: str, title: str, body: str) -> GatewayResponse:
        """Создать issue в репозитории"""
        data = {
            "title": title,
            "body": body
        }
        
        return await self.call_api(
            endpoint=f"/repos/{owner}/{repo}/issues",
            method="POST",
            data=data
        )
    
    async def get_pull_requests(self, owner: str, repo: str, state: str = "open") -> GatewayResponse:
        """Получить pull requests из репозитория"""
        params = {"state": state}
        
        return await self.call_api(
            endpoint=f"/repos/{owner}/{repo}/pulls",
            method="GET",
            data=params
        )

class OpenAIGateway(GenericAPIGateway):
    """Шлюз для интеграции с OpenAI API"""
    
    def __init__(self, api_key: str, rate_limit: int = 3500):
        super().__init__(
            base_url="https://api.openai.com/v1",
            default_headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            rate_limit=rate_limit
        )
        self.api_key = api_key
    
    async def generate_text(self, model: str, prompt: str, **kwargs) -> GatewayResponse:
        """Генерация текста через OpenAI API"""
        data = {
            "model": model,
            "prompt": prompt,
            **kwargs
        }
        
        return await self.call_api(
            endpoint="/completions",
            method="POST",
            data=data
        )
    
    async def chat_completion(self, model: str, messages: List[Dict[str, str]], **kwargs) -> GatewayResponse:
        """Чат-завершение через OpenAI API"""
        data = {
            "model": model,
            "messages": messages,
            **kwargs
        }
        
        return await self.call_api(
            endpoint="/chat/completions",
            method="POST",
            data=data
        )
    
    async def analyze_code(self, code: str, language: str = "python") -> GatewayResponse:
        """Анализ кода через OpenAI API"""
        messages = [
            {
                "role": "system",
                "content": "Ты эксперт в области анализа кода безопасности. Найди потенциальные уязвимости и проблемы качества."
            },
            {
                "role": "user",
                "content": f"Проанализируй этот {language} код на наличие уязвимостей безопасности и проблем качества:\n\n```\n{code}\n```"
            }
        ]
        
        return await self.chat_completion(
            model="gpt-4",
            messages=messages,
            temperature=0.3,
            max_tokens=1000
        )

class DatabaseGateway(IGateway):
    """Шлюз для интеграции с базами данных"""
    
    def __init__(self, connection_string: str, max_connections: int = 10):
        self.connection_string = connection_string
        self.max_connections = max_connections
        self._pool = None
        self._initialized = False
    
    async def initialize(self):
        """Инициализировать шлюз к базе данных"""
        import aiomysql
        
        self._pool = await aiomysql.create_pool(
            dsn=self.connection_string,
            minsize=1,
            maxsize=self.max_connections
        )
        self._initialized = True
    
    async def execute_query(self, query: str, parameters: List[Any] = None) -> GatewayResponse:
        """Выполнить SQL-запрос"""
        if not self._initialized:
            await self.initialize()
        
        # Проверить безопасность запроса
        if not self._is_safe_query(query):
            return GatewayResponse(
                success=False,
                error="Небезопасный SQL-запрос",
                status_code=400
            )
        
        try:
            async with self._pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    start_time = time.time()
                    
                    if parameters:
                        await cursor.execute(query, parameters)
                    else:
                        await cursor.execute(query)
                    
                    if query.strip().upper().startswith('SELECT'):
                        results = await cursor.fetchall()
                        columns = [desc[0] for desc in cursor.description]
                        
                        response_data = {
                            "results": results,
                            "columns": columns,
                            "row_count": len(results)
                        }
                    else:
                        await conn.commit()
                        response_data = {
                            "row_count": cursor.rowcount,
                            "last_row_id": cursor.lastrowid
                        }
                    
                    response_time = time.time() - start_time
                    
                    return GatewayResponse(
                        success=True,
                        data=response_data,
                        status_code=200,
                        response_time=response_time
                    )
        except Exception as e:
            return GatewayResponse(
                success=False,
                error=f"Ошибка выполнения запроса: {str(e)}",
                status_code=500
            )
    
    def _is_safe_query(self, query: str) -> bool:
        """Проверить, является ли SQL-запрос безопасным"""
        # Проверить на потенциально опасные операции
        dangerous_keywords = [
            'DROP', 'DELETE', 'ALTER', 'CREATE', 'INSERT', 'UPDATE',
            'EXEC', 'EXECUTE', 'SP_', 'XP_', 'BACKUP', 'RESTORE'
        ]
        
        query_upper = query.upper()
        
        # Проверить, что запрос не содержит опасных команд
        for keyword in dangerous_keywords:
            if keyword in query_upper:
                # Разрешить безопасные использования (например, SELECT из таблицы с именем DROP)
                if not self._is_likely_safe_usage(query_upper, keyword):
                    return False
        
        return True
    
    def _is_likely_safe_usage(self, query: str, keyword: str) -> bool:
        """Проверить, является ли использование ключевого слова безопасным"""
        # Для простоты, считаем безопасным, если ключевое слово не в начале выражения
        # В реальной системе потребуется более сложная проверка
        import re
        pattern = rf'\b{keyword}\b'
        matches = re.finditer(pattern, query)
        
        for match in matches:
            # Проверить, не является ли это частью безопасного выражения
            context_before = query[:match.start()].strip()[-10:]  # Последние 10 символов перед ключевым словом
            if context_before.endswith('SELECT'):
                # Если ключевое слово идет после SELECT, возможно, это имя таблицы
                return True
        
        return keyword not in ['DROP', 'DELETE', 'ALTER', 'CREATE']  # Эти команды всегда небезопасны
    
    async def execute_batch_queries(self, queries: List[Dict[str, Any]]) -> List[GatewayResponse]:
        """Выполнить несколько запросов"""
        responses = []
        
        for query_data in queries:
            query = query_data["query"]
            params = query_data.get("parameters", [])
            response = await self.execute_query(query, params)
            responses.append(response)
        
        return responses
    
    async def cleanup(self):
        """Очистить ресурсы шлюза"""
        if self._pool:
            self._pool.close()
            await self._pool.wait_closed()
```

## Интеграция с файловой системой

### 1. Безопасная интеграция с файловой системой

```python
# infrastructure/gateways/file_system_gateway.py
from domain.abstractions.gateway import IGateway
from pathlib import Path
import os
import stat
from typing import List, Dict, Any

class IFileSystemGateway(IGateway):
    """Интерфейс шлюза к файловой системе"""
    
    @abstractmethod
    async def read_file(self, path: str, encoding: str = "utf-8") -> GatewayResponse:
        """Прочитать файл"""
        pass
    
    @abstractmethod
    async def write_file(self, path: str, content: str, encoding: str = "utf-8") -> GatewayResponse:
        """Записать файл"""
        pass
    
    @abstractmethod
    async def list_directory(self, path: str) -> GatewayResponse:
        """Список файлов в директории"""
        pass

class SecureFileSystemGateway(IFileSystemGateway):
    """Безопасный шлюз к файловой системе"""
    
    def __init__(self, allowed_directories: List[str] = None, max_file_size: int = 10 * 1024 * 1024):
        self.allowed_directories = allowed_directories or ["./projects", "./data", "./outputs", "./temp"]
        self.max_file_size = max_file_size
        self._supported_extensions = {".py", ".js", ".ts", ".java", ".cs", ".cpp", ".c", 
                                     ".html", ".css", ".json", ".yaml", ".xml", ".txt", ".md"}
    
    async def read_file(self, path: str, encoding: str = "utf-8") -> GatewayResponse:
        """Безопасное чтение файла"""
        
        # Проверить безопасность пути
        if not self._is_safe_path(path):
            return GatewayResponse(
                success=False,
                error="Небезопасный путь к файлу",
                status_code=403
            )
        
        # Проверить, находится ли файл в разрешенных директориях
        if not self._is_in_allowed_directory(path):
            return GatewayResponse(
                success=False,
                error="Файл находится вне разрешенных директорий",
                status_code=403
            )
        
        file_path = Path(path)
        
        # Проверить существование файла
        if not file_path.exists():
            return GatewayResponse(
                success=False,
                error=f"Файл не найден: {path}",
                status_code=404
            )
        
        # Проверить, является ли это файлом (а не директорией)
        if file_path.is_dir():
            return GatewayResponse(
                success=False,
                error=f"Путь указывает на директорию, а не на файл: {path}",
                status_code=400
            )
        
        # Проверить расширение файла
        if file_path.suffix.lower() not in self._supported_extensions:
            return GatewayResponse(
                success=False,
                error=f"Формат файла {file_path.suffix} не поддерживается",
                status_code=400
            )
        
        # Проверить размер файла
        file_size = file_path.stat().st_size
        if file_size > self.max_file_size:
            return GatewayResponse(
                success=False,
                error=f"Файл слишком большой: {file_size} байт, максимум {self.max_file_size}",
                status_code=400
            )
        
        try:
            with open(file_path, 'r', encoding=encoding) as file:
                content = file.read()
            
            return GatewayResponse(
                success=True,
                data={
                    "content": content,
                    "size": file_size,
                    "encoding": encoding,
                    "absolute_path": str(file_path.absolute())
                },
                status_code=200
            )
        except UnicodeDecodeError:
            return GatewayResponse(
                success=False,
                error=f"Не удалось декодировать файл с кодировкой {encoding}",
                status_code=400
            )
        except PermissionError:
            return GatewayResponse(
                success=False,
                error=f"Нет доступа к файлу: {path}",
                status_code=403
            )
        except Exception as e:
            return GatewayResponse(
                success=False,
                error=f"Ошибка при чтении файла: {str(e)}",
                status_code=500
            )
    
    async def write_file(self, path: str, content: str, encoding: str = "utf-8") -> GatewayResponse:
        """Безопасная запись файла"""
        
        # Проверить безопасность пути
        if not self._is_safe_path(path):
            return GatewayResponse(
                success=False,
                error="Небезопасный путь к файлу",
                status_code=403
            )
        
        # Проверить, находится ли файл в разрешенных директориях
        if not self._is_in_allowed_directory(path):
            return GatewayResponse(
                success=False,
                error="Файл находится вне разрешенных директорий",
                status_code=403
            )
        
        file_path = Path(path)
        
        # Проверить размер содержимого
        content_size = len(content.encode(encoding))
        if content_size > self.max_file_size:
            return GatewayResponse(
                success=False,
                error=f"Содержимое файла слишком велико: {content_size} байт, максимум {self.max_file_size}",
                status_code=400
            )
        
        # Создать директории при необходимости
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            with open(file_path, 'w', encoding=encoding) as file:
                file.write(content)
            
            return GatewayResponse(
                success=True,
                data={
                    "written_bytes": content_size,
                    "absolute_path": str(file_path.absolute())
                },
                status_code=200
            )
        except PermissionError:
            return GatewayResponse(
                success=False,
                error=f"Нет доступа для записи в файл: {path}",
                status_code=403
            )
        except Exception as e:
            return GatewayResponse(
                success=False,
                error=f"Ошибка при записи файла: {str(e)}",
                status_code=500
            )
    
    async def list_directory(self, path: str) -> GatewayResponse:
        """Безопасный список файлов в директории"""
        
        # Проверить безопасность пути
        if not self._is_safe_path(path):
            return GatewayResponse(
                success=False,
                error="Небезопасный путь к директории",
                status_code=403
            )
        
        # Проверить, находится ли директория в разрешенных директориях
        if not self._is_in_allowed_directory(path):
            return GatewayResponse(
                success=False,
                error="Директория находится вне разрешенных директорий",
                status_code=403
            )
        
        dir_path = Path(path)
        
        # Проверить существование директории
        if not dir_path.exists():
            return GatewayResponse(
                success=False,
                error=f"Директория не найдена: {path}",
                status_code=404
            )
        
        # Проверить, является ли это директорией
        if not dir_path.is_dir():
            return GatewayResponse(
                success=False,
                error=f"Путь указывает на файл, а не на директорию: {path}",
                status_code=400
            )
        
        try:
            # Получить список файлов и директорий
            entries = []
            for entry in dir_path.iterdir():
                entry_stat = entry.stat()
                entries.append({
                    "name": entry.name,
                    "type": "directory" if entry.is_dir() else "file",
                    "size": entry_stat.st_size if entry.is_file() else 0,
                    "modified": entry_stat.st_mtime,
                    "absolute_path": str(entry.absolute())
                })
            
            return GatewayResponse(
                success=True,
                data={
                    "entries": entries,
                    "directory_path": str(dir_path.absolute()),
                    "entry_count": len(entries)
                },
                status_code=200
            )
        except PermissionError:
            return GatewayResponse(
                success=False,
                error=f"Нет доступа к директории: {path}",
                status_code=403
            )
        except Exception as e:
            return GatewayResponse(
                success=False,
                error=f"Ошибка при перечислении директории: {str(e)}",
                status_code=500
            )
    
    def _is_safe_path(self, path: str) -> bool:
        """Проверить, является ли путь безопасным для использования"""
        try:
            # Преобразовать в абсолютный путь
            abs_path = Path(path).resolve()
            
            # Получить корневой каталог проекта
            project_root = Path.cwd().resolve()
            
            # Проверить, что путь находится внутри корневого каталога проекта
            abs_path.relative_to(project_root)
            return True
        except ValueError:
            # Если путь вне корневого каталога проекта, он небезопасен
            return False
    
    def _is_in_allowed_directory(self, path: str) -> bool:
        """Проверить, находится ли путь в разрешенных директориях"""
        abs_path = Path(path).resolve()
        
        for allowed_dir in self.allowed_directories:
            allowed_abs_path = Path(allowed_dir).resolve()
            try:
                abs_path.relative_to(allowed_abs_path)
                return True
            except ValueError:
                continue
        
        return False
    
    async def initialize(self):
        """Инициализировать шлюз"""
        # Проверить, существуют ли разрешенные директории, и создать их при необходимости
        for allowed_dir in self.allowed_directories:
            Path(allowed_dir).mkdir(parents=True, exist_ok=True)
    
    async def cleanup(self):
        """Очистить ресурсы шлюза"""
        pass
```

## Интеграция с системой событий

### 1. Адаптеры событийной системы

```python
# infrastructure/adapters/event_system_adapter.py
from typing import Any, Dict, Callable, List
from domain.abstractions.event_system import IEventPublisher, IEventSubscriber
from enum import Enum

class EventType(Enum):
    """Типы событий для интеграции"""
    AGENT_TASK_STARTED = "agent_task_started"
    AGENT_TASK_COMPLETED = "agent_task_completed"
    AGENT_TASK_FAILED = "agent_task_failed"
    PROMPT_EXECUTED = "prompt_executed"
    ACTION_EXECUTED = "action_executed"
    PATTERN_EXECUTED = "pattern_executed"
    SECURITY_VIOLATION_DETECTED = "security_violation_detected"
    RESOURCE_LIMIT_EXCEEDED = "resource_limit_exceeded"
    ERROR_OCCURRED = "error_occurred"

class EventSystemAdapter(IEventPublisher, IEventSubscriber):
    """Адаптер для интеграции с системой событий"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self._subscribers: Dict[EventType, List[Callable]] = {}
        self._event_queue = asyncio.Queue()
        self._running = False
        self._max_queue_size = self.config.get("max_queue_size", 1000)
        self._event_filters = self.config.get("event_filters", [])
        self._event_processors = self.config.get("event_processors", [])
        self._security_monitor = SecurityMonitor() if self.config.get("enable_security_monitoring", True) else None
    
    async def initialize(self):
        """Инициализировать адаптер событийной системы"""
        # Запустить фоновый процесс обработки событий
        self._running = True
        self._worker_task = asyncio.create_task(self._event_worker())
    
    async def publish(self, event_type: EventType, data: Dict[str, Any]):
        """Опубликовать событие с фильтрацией и обработкой"""
        if not self._running:
            raise RuntimeError("Адаптер событийной системы не инициализирован")
        
        # Применить фильтры безопасности
        if not self._apply_security_filters(event_type, data):
            return  # Событие отфильтровано
        
        # Применить пользовательские фильтры
        if not self._apply_custom_filters(event_type, data):
            return  # Событие отфильтровано
        
        # Создать событие
        event = {
            "type": event_type,
            "data": data,
            "timestamp": time.time(),
            "source": self.__class__.__name__
        }
        
        # Применить процессоры
        processed_event = event.copy()
        for processor in self._event_processors:
            processed_event = await processor(processed_event)
        
        try:
            await self._event_queue.put(processed_event)
        except asyncio.QueueFull:
            print(f"Очередь событий переполнена, событие {event_type} потеряно")
    
    def subscribe(self, event_type: EventType, handler: Callable):
        """Подписаться на событие"""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        
        self._subscribers[event_type].append(handler)
    
    def _apply_security_filters(self, event_type: EventType, data: Dict[str, Any]) -> bool:
        """Применить фильтры безопасности к событию"""
        if self._security_monitor:
            return self._security_monitor.check_event_safety(event_type, data)
        
        # Проверить чувствительные данные в событии
        sensitive_fields = ["password", "token", "api_key", "secret", "credentials"]
        for field in sensitive_fields:
            if field in data:
                return False  # Не разрешать чувствительные данные в событиях
        
        return True
    
    def _apply_custom_filters(self, event_type: EventType, data: Dict[str, Any]) -> bool:
        """Применить пользовательские фильтры к событию"""
        for filter_func in self._event_filters:
            if not filter_func(event_type, data):
                return False  # Событие отфильтровано
        
        return True
    
    async def _event_worker(self):
        """Фоновый процесс обработки событий"""
        while self._running:
            try:
                event = await self._event_queue.get()
                
                # Опубликовать событие подписчикам
                event_type = event["type"]
                if event_type in self._subscribers:
                    for handler in self._subscribers[event_type]:
                        try:
                            if asyncio.iscoroutinefunction(handler):
                                await handler(event_type, event["data"])
                            else:
                                handler(event_type, event["data"])
                        except Exception as e:
                            print(f"Ошибка при обработке события {event_type}: {str(e)}")
                
                self._event_queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Ошибка в воркере событий: {str(e)}")
    
    async def cleanup(self):
        """Очистить ресурсы адаптера"""
        self._running = False
        
        if hasattr(self, '_worker_task'):
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        
        # Ожидать завершения обработки всех событий
        await self._event_queue.join()
```

## Интеграция с агентами

### 1. Подключение внешних систем к агентам

```python
# application/agents/agent_with_integrations.py
from application.agents.composable_agent import ComposableAgent
from infrastructure.gateways.api_gateway import IAPIGateway
from infrastructure.gateways.file_system_gateway import IFileSystemGateway
from infrastructure.adapters.event_system_adapter import EventSystemAdapter

class IntegratedAgent(ComposableAgent):
    """Агент с интеграцией внешних систем"""
    
    def __init__(
        self,
        domain: DomainType,
        api_gateway: IAPIGateway = None,
        file_system_gateway: IFileSystemGateway = None,
        event_adapter: EventSystemAdapter = None,
        config: Dict[str, Any] = None
    ):
        super().__init__(domain, config)
        self.api_gateway = api_gateway
        self.file_system_gateway = file_system_gateway
        self.event_adapter = event_adapter
        self._external_services = {}
        
        # Регистрация внешних сервисов
        self._register_external_services()
    
    def _register_external_services(self):
        """Зарегистрировать внешние сервисы как инструменты"""
        services = {}
        
        if self.api_gateway:
            services["api_gateway"] = self.api_gateway
            # Зарегистрировать в исполнителе действий как инструмент
            from application.orchestration.atomic_action_executor import AtomicActionExecutor
            api_tool = APIIntegrationTool(self.api_gateway)
            self.action_executor.register_action(api_tool)
        
        if self.file_system_gateway:
            services["file_system_gateway"] = self.file_system_gateway
            file_tool = FileSystemIntegrationTool(self.file_system_gateway)
            self.action_executor.register_action(file_tool)
        
        self._external_services = services
    
    async def execute_task(self, task_description: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Выполнить задачу с интеграцией внешних систем"""
        
        # Опубликовать событие начала задачи
        if self.event_adapter:
            await self.event_adapter.publish(EventType.AGENT_TASK_STARTED, {
                "agent_id": id(self),
                "task_description": task_description,
                "context_keys": list(context.keys()) if context else []
            })
        
        try:
            # Выполнить базовую логику задачи
            result = await super().execute_task(task_description, context)
            
            # Опубликовать событие завершения задачи
            if self.event_adapter:
                await self.event_adapter.publish(EventType.AGENT_TASK_COMPLETED, {
                    "agent_id": id(self),
                    "task_description": task_description,
                    "result": result
                })
            
            return result
        except Exception as e:
            # Опубликовать событие ошибки
            if self.event_adapter:
                await self.event_adapter.publish(EventType.AGENT_TASK_FAILED, {
                    "agent_id": id(self),
                    "task_description": task_description,
                    "error": str(e)
                })
            
            raise
    
    async def execute_external_service_call(self, service_name: str, method: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Выполнить вызов внешнего сервиса"""
        if service_name not in self._external_services:
            return {
                "success": False,
                "error": f"Внешний сервис {service_name} не зарегистрирован"
            }
        
        service = self._external_services[service_name]
        
        if not hasattr(service, method):
            return {
                "success": False,
                "error": f"Метод {method} не доступен для сервиса {service_name}"
            }
        
        try:
            method_callable = getattr(service, method)
            result = await method_callable(**parameters)
            return {"success": True, "result": result}
        except Exception as e:
            return {
                "success": False,
                "error": f"Ошибка при вызове внешнего сервиса: {str(e)}"
            }

class APIIntegrationTool(ITool):
    """Инструмент для интеграции с API"""
    
    def __init__(self, api_gateway: IAPIGateway):
        self.api_gateway = api_gateway
        self._name = "api_integration"
    
    @property
    def name(self) -> str:
        return self._name
    
    async def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Выполнить вызов API"""
        if not self.validate_parameters(parameters):
            return {
                "success": False,
                "error": "Некорректные параметры вызова API"
            }
        
        endpoint = parameters["endpoint"]
        method = parameters.get("method", "GET")
        data = parameters.get("data")
        headers = parameters.get("headers", {})
        
        response = await self.api_gateway.call_api(
            endpoint=endpoint,
            method=method,
            data=data,
            headers=headers
        )
        
        return {
            "success": response.success,
            "data": response.data,
            "status_code": response.status_code,
            "error": response.error if not response.success else None
        }
    
    def validate_parameters(self, parameters: Dict[str, Any]) -> bool:
        """Проверить параметры вызова API"""
        required_fields = ["endpoint"]
        if not all(field in parameters for field in required_fields):
            return False
        
        endpoint = parameters["endpoint"]
        if not isinstance(endpoint, str) or not endpoint.strip():
            return False
        
        method = parameters.get("method", "GET").upper()
        allowed_methods = {"GET", "POST", "PUT", "PATCH", "DELETE"}
        if method not in allowed_methods:
            return False
        
        return True

class FileSystemIntegrationTool(ITool):
    """Инструмент для интеграции с файловой системой"""
    
    def __init__(self, fs_gateway: IFileSystemGateway):
        self.fs_gateway = fs_gateway
        self._name = "file_system_integration"
    
    @property
    def name(self) -> str:
        return self._name
    
    async def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Выполнить операцию с файловой системой"""
        if not self.validate_parameters(parameters):
            return {
                "success": False,
                "error": "Некорректные параметры операции с файловой системой"
            }
        
        operation = parameters["operation"]
        path = parameters["path"]
        
        if operation == "read_file":
            encoding = parameters.get("encoding", "utf-8")
            response = await self.fs_gateway.read_file(path, encoding)
        elif operation == "write_file":
            content = parameters["content"]
            encoding = parameters.get("encoding", "utf-8")
            response = await self.fs_gateway.write_file(path, content, encoding)
        elif operation == "list_directory":
            response = await self.fs_gateway.list_directory(path)
        else:
            return {
                "success": False,
                "error": f"Операция {operation} не поддерживается"
            }
        
        return {
            "success": response.success,
            "data": response.data,
            "status_code": response.status_code,
            "error": response.error if not response.success else None
        }
    
    def validate_parameters(self, parameters: Dict[str, Any]) -> bool:
        """Проверить параметры операции с файловой системой"""
        required_fields = ["operation", "path"]
        if not all(field in parameters for field in required_fields):
            return False
        
        operation = parameters["operation"]
        allowed_operations = {"read_file", "write_file", "list_directory"}
        if operation not in allowed_operations:
            return False
        
        path = parameters["path"]
        if not isinstance(path, str) or not path.strip():
            return False
        
        # Проверить содержимое для write_file
        if operation == "write_file" and "content" not in parameters:
            return False
        
        return True
```

## Практики безопасной интеграции

### 1. Проверка безопасности интеграции

```python
def validate_integration_security(self, service_config: Dict[str, Any]) -> List[str]:
    """Проверить безопасность конфигурации интеграции"""
    errors = []
    
    # Проверить чувствительные поля в конфигурации
    sensitive_fields = ["password", "token", "api_key", "secret", "credentials"]
    for field in sensitive_fields:
        if field in service_config:
            errors.append(f"Чувствительное поле '{field}' обнаружено в конфигурации сервиса")
    
    # Проверить URL-адреса на безопасность
    if "base_url" in service_config:
        base_url = service_config["base_url"]
        if not self._is_safe_url(base_url):
            errors.append(f"Небезопасный URL: {base_url}")
    
    # Проверить размер конфигурации
    config_size = len(str(service_config))
    max_size = 1 * 1024 * 1024  # 1MB
    if config_size > max_size:
        errors.append(f"Конфигурация сервиса слишком велика: {config_size} байт, максимум {max_size}")
    
    return errors

def _is_safe_url(self, url: str) -> bool:
    """Проверить, является ли URL безопасным"""
    from urllib.parse import urlparse
    
    parsed = urlparse(url)
    
    # Проверить схему
    if parsed.scheme not in ["http", "https"]:
        return False
    
    # Проверить хост на безопасность
    dangerous_hosts = [
        "localhost", "127.0.0.1", "::1",  # Локальные адреса
        "internal", "private", "local"   # Подозрительные домены
    ]
    
    host_lower = parsed.hostname.lower() if parsed.hostname else ""
    for dangerous_host in dangerous_hosts:
        if dangerous_host in host_lower:
            # Разрешить локальные адреса только в тестовой среде
            if not os.getenv("TEST_ENVIRONMENT", False):
                return False
    
    return True
```

### 2. Ограничение ресурсов при интеграции

```python
class ResourceLimitedIntegration:
    """Интеграция с ограничением ресурсов"""
    
    def __init__(self, max_requests_per_minute: int = 100, max_concurrent_calls: int = 10):
        self.max_requests_per_minute = max_requests_per_minute
        self.max_concurrent_calls = max_concurrent_calls
        self._request_times = []
        self._concurrent_semaphore = asyncio.Semaphore(max_concurrent_calls)
        self._rate_limiter = RateLimiter(max_requests_per_minute)
    
    async def _check_resource_limits(self) -> bool:
        """Проверить ограничения ресурсов"""
        # Проверить количество одновременных вызовов
        if self._concurrent_semaphore.locked():
            # Если семафор заблокирован, проверить, можно ли выполнить вызов
            if self._concurrent_semaphore._value == 0:
                return False
        
        # Проверить рейт-лимит
        if not await self._rate_limiter.is_allowed():
            return False
        
        return True
    
    async def execute_with_resource_limit(self, operation: Callable, *args, **kwargs) -> Dict[str, Any]:
        """Выполнить операцию с учетом ограничений ресурсов"""
        if not await self._check_resource_limits():
            return {
                "success": False,
                "error": "Превышены ограничения ресурсов",
                "error_type": "resource_limit"
            }
        
        async with self._concurrent_semaphore:
            # Отметить выполнение запроса для рейт-лимитера
            await self._rate_limiter.record_request()
            
            # Выполнить операцию
            try:
                result = await operation(*args, **kwargs)
                return {"success": True, "result": result}
            except Exception as e:
                return {
                    "success": False,
                    "error": f"Ошибка при выполнении операции: {str(e)}"
                }

class RateLimiter:
    """Простой рейт-лимитер"""
    
    def __init__(self, max_requests_per_minute: int):
        self.max_requests_per_minute = max_requests_per_minute
        self._requests_in_window = []
        self._window_size = 60  # 1 minute window
    
    async def is_allowed(self) -> bool:
        """Проверить, разрешен ли запрос"""
        current_time = time.time()
        
        # Удалить старые запросы из окна
        self._requests_in_window = [
            req_time for req_time in self._requests_in_window
            if current_time - req_time < self._window_size
        ]
        
        # Проверить, не превышено ли ограничение
        return len(self._requests_in_window) < self.max_requests_per_minute
    
    async def record_request(self):
        """Записать выполнение запроса"""
        current_time = time.time()
        self._requests_in_window.append(current_time)
```

## Тестирование интеграции

### 1. Модульные тесты интеграции

```python
# test_integration.py
import pytest
from unittest.mock import AsyncMock, Mock, patch
import tempfile
import os

class TestAPIIntegration:
    @pytest.mark.asyncio
    async def test_github_api_gateway_integration(self):
        """Тест интеграции с GitHub API"""
        
        # Создать мок для HTTP-клиента
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            mock_session_class.return_value.__aenter__.return_value = mock_session
            
            # Создать шлюз
            gateway = GitHubAPIGateway(token="test_token", rate_limit=100)
            await gateway.initialize()
            
            # Мокнуть ответ
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.text.return_value = '{"test": "data"}'
            mock_session.request.return_value.__aenter__.return_value = mock_response
            
            # Выполнить вызов API
            result = await gateway.call_api("/user/repos", "GET")
            
            # Проверить результат
            assert result.success is True
            assert "test" in result.data
    
    @pytest.mark.asyncio
    async def test_openai_gateway_integration(self):
        """Тест интеграции с OpenAI API"""
        
        gateway = OpenAIGateway(api_key="test_key", rate_limit=100)
        await gateway.initialize()
        
        # Мокнуть HTTP-ответ
        with patch.object(gateway, '_session') as mock_session:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.text.return_value = '{"choices": [{"text": "Generated text"}]}'
            mock_session.request.return_value.__aenter__.return_value = mock_response
            
            result = await gateway.generate_text("text-davinci-003", "Test prompt")
            
            assert result.success is True
            assert "choices" in result.data

class TestFileSystemIntegration:
    @pytest.mark.asyncio
    async def test_secure_file_system_gateway_read(self):
        """Тест безопасного чтения файлов"""
        
        # Создать временный файл для теста
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write("print('Hello, World!')")
            temp_file_path = f.name
        
        try:
            # Создать безопасный шлюз к файловой системе
            gateway = SecureFileSystemGateway(
                allowed_directories=[str(Path(temp_file_path).parent)],
                max_file_size=1024*1024  # 1MB
            )
            await gateway.initialize()
            
            # Прочитать файл
            result = await gateway.read_file(temp_file_path)
            
            # Проверить результат
            assert result.success is True
            assert "Hello, World!" in result.data["content"]
            assert result.data["size"] > 0
        finally:
            # Удалить временный файл
            os.unlink(temp_file_path)
    
    @pytest.mark.asyncio
    async def test_file_system_gateway_security_check(self):
        """Тест проверки безопасности файловой системы"""
        
        gateway = SecureFileSystemGateway(
            allowed_directories=["./safe_dir"],
            max_file_size=1024*1024
        )
        
        # Попробовать прочитать файл вне разрешенной директории
        result = await gateway.read_file("../../etc/passwd")
        
        # Проверить, что запрос был отклонен
        assert result.success is False
        assert "Небезопасный путь" in result.error

class TestIntegratedAgent:
    @pytest.mark.asyncio
    async def test_agent_external_service_integration(self):
        """Тест интеграции агента с внешними сервисами"""
        
        # Создать моки внешних сервисов
        mock_api_gateway = AsyncMock()
        mock_fs_gateway = AsyncMock()
        mock_event_adapter = AsyncMock()
        
        # Создать агента с интеграциями
        agent = IntegratedAgent(
            domain=DomainType.CODE_ANALYSIS,
            api_gateway=mock_api_gateway,
            file_system_gateway=mock_fs_gateway,
            event_adapter=mock_event_adapter
        )
        
        # Проверить, что сервисы зарегистрированы
        assert "api_gateway" in agent._external_services
        assert "file_system_gateway" in agent._external_services
        
        # Выполнить задачу
        result = await agent.execute_task(
            task_description="Проанализируй этот код на безопасность",
            context={
                "code": "def test(): pass",
                "language": "python"
            }
        )
        
        # Проверить, что события были опубликованы
        mock_event_adapter.publish.assert_called()
        
        assert result["success"] is True
```

## Лучшие практики интеграции

### 1. Модульность интеграции

Создавайте модульные и легко заменяемые интеграции:

```python
# Хорошо: модульные интеграции
class BaseIntegration:
    """Базовая интеграция"""
    pass

class APIIntegration(BaseIntegration):
    """Интеграция с API"""
    pass

class DatabaseIntegration(APIIntegration):
    """Интеграция с базой данных через API"""
    pass

# Плохо: монолитная интеграция
class MonolithicIntegration:
    """Монолитная интеграция - сложно расширять и тестировать"""
    pass
```

### 2. Обработка ошибок

Обеспечьте надежную обработку ошибок в интеграциях:

```python
async def execute_external_call(self, service_name: str, method: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
    """Выполнить внешний вызов с надежной обработкой ошибок"""
    try:
        # Проверить ограничения безопасности
        if not self._check_security_policy(service_name, method, parameters):
            return {
                "success": False,
                "error": "Вызов не соответствует политике безопасности",
                "error_type": "security_violation"
            }
        
        # Проверить ограничения ресурсов
        if not await self._check_resource_limits(service_name):
            return {
                "success": False,
                "error": "Недостаточно ресурсов для выполнения вызова",
                "error_type": "resource_limit"
            }
        
        # Выполнить вызов
        result = await self._execute_call_logic(service_name, method, parameters)
        
        return {"success": True, **result}
    except AuthenticationError as e:
        return {
            "success": False,
            "error": f"Ошибка аутентификации: {str(e)}",
            "error_type": "authentication"
        }
    except AuthorizationError as e:
        return {
            "success": False,
            "error": f"Ошибка авторизации: {str(e)}",
            "error_type": "authorization"
        }
    except RateLimitExceededError as e:
        return {
            "success": False,
            "error": f"Превышен лимит запросов: {str(e)}",
            "error_type": "rate_limit"
        }
    except ConnectionError as e:
        return {
            "success": False,
            "error": f"Ошибка подключения: {str(e)}",
            "error_type": "connection"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Внутренняя ошибка интеграции: {str(e)}",
            "error_type": "internal"
        }
```

Эти рекомендации помогут вам безопасно и надежно интегрировать Koru AI Agent Framework с внешними системами, обеспечивая модульность, безопасность и тестируемость интеграций.