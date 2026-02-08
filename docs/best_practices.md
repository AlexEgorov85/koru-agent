# Лучшие практики Koru AI Agent Framework

В этом разделе описаны рекомендации и лучшие практики по использованию Koru AI Agent Framework. Эти практики помогут вам эффективно разрабатывать, настраивать и использовать фреймворк для решения ваших задач.

## Архитектурные практики

### 1. Чистая архитектура

Следуйте принципам чистой архитектуры:

#### Зависимости направлены внутрь

- Внешние слои зависят от внутренних, а не наоборот
- Ядро системы не зависит от конкретных фреймворков или внешних библиотек
- Внешние зависимости инжектируются через интерфейсы

```python
# Правильно: зависимости направлены внутрь
from domain.abstractions.event_types import IEventPublisher

class MyClass:
    def __init__(self, event_publisher: IEventPublisher):
        self._event_publisher = event_publisher
```

#### Слои архитектуры

Разделяйте систему на три основных слоя:

- **Domain Layer**: Содержит бизнес-логику и правила
- **Application Layer**: Координирует работу компонентов домена
- **Infrastructure Layer**: Реализует внешние зависимости

### 2. Инверсия зависимостей

Используйте интерфейсы для инверсии зависимостей:

- Модули верхнего уровня не должны зависеть от модулей нижнего уровня
- Оба должны зависеть от абстракций
- Абстракции не должны зависеть от деталей, детали должны зависеть от абстракций

```python
# Правильно: зависимость инвертирована через интерфейс
from domain.abstractions.repository import IRepository

class UserService:
    def __init__(self, repository: IRepository):
        self._repository = repository
```

### 3. Единственная ответственность

Каждый класс должен иметь только одну причину для изменения:

- Один класс - одна задача
- Если класс решает несколько разных задач - разделите его
- Следите за количеством методов и строк кода в классе

### 4. Открытость/закрытость

Классы должны быть открыты для расширения, но закрыты для модификации:

- Используйте наследование или композицию для расширения функциональности
- Не изменяйте существующий код, если не требуется изменить основную логику

## Практики разработки

### 1. Типизация и аннотации

Используйте аннотации типов для повышения читаемости кода:

```python
from typing import List, Dict, Optional

def process_users(users: List[Dict[str, str]]) -> Optional[str]:
    # Обработка пользователей
    pass
```

### 2. Обработка ошибок

Реализуйте надежную обработку ошибок:

- Используйте конкретные типы исключений
- Логируйте ошибки с достаточной информацией для диагностики
- Обрабатывайте ошибки на соответствующем уровне абстракции

### 3. Тестирование

Покрывайте код тестами:

- Модульные тесты для отдельных компонентов
- Интеграционные тесты для взаимодействия между компонентами
- Используйте фикстуры и моки для изоляции тестируемого кода

## Практики безопасности

### 1. Валидация данных

Всегда валидируйте входные данные:

```python
from typing import Dict, Any

class PromptManager:
    def validate_prompt_parameters(self, parameters: Dict[str, Any]) -> bool:
        """Проверяет параметры промта на корректность и безопасность"""
        errors = []
        
        # Проверка чувствительных полей
        sensitive_fields = ["password", "token", "api_key", "secret", "credentials",
                           "private_key", "certificate", "oauth_token", "email", "phone"]
        for field in sensitive_fields:
            if field in parameters:
                errors.append(f"Чувствительное поле '{field}' не должно передаваться напрямую")
        
        # Проверка размера параметров
        params_size = len(str(parameters))
        max_size = 10 * 1024 * 1024  # 10MB
        if params_size > max_size:
            errors.append(f"Размер параметров превышает лимит: {params_size} байт, максимум {max_size}")
        
        # Проверка безопасного пути
        if "path" in parameters:
            if not self._is_safe_path(parameters["path"]):
                errors.append("Небезопасный путь в параметрах")
        
        return len(errors) == 0
```

### 2. Управление доступом

Реализуйте надежное управление доступом:

- Проверяйте права доступа перед выполнением операций
- Используйте ролевую модель для управления правами
- Логируйте попытки несанкционированного доступа

## Практики конфигурации

### 1. Настройка приложения

Используйте структурированную конфигурацию:

```python
# config/app_config.py
from pydantic import BaseModel, Field
from typing import Dict, Any, List

class AgentConfig(BaseModel):
    """Конфигурация агента"""
    max_iterations: int = Field(default=50, ge=1, le=1000)
    timeout: int = Field(default=300, ge=1)
    enable_logging: bool = Field(default=True)
    max_concurrent_actions: int = Field(default=5, ge=1, le=50)
    memory_limit: str = Field(default="1GB")
    retry_attempts: int = Field(default=3, ge=0, le=10)

class LLMConfig(BaseModel):
    """Конфигурация LLM"""
    provider: str = Field(default="openai")
    model: str = Field(default="gpt-4")
    api_key: str = Field(default="")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=2048, ge=1, le=4096)

class AppConfig(BaseModel):
    """Основная конфигурация приложения"""
    agent: AgentConfig = Field(default_factory=AgentConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    debug_mode: bool = Field(default=False)
    log_level: str = Field(default="INFO")
    enable_monitoring: bool = Field(default=True)
```

### 2. Управление настройками

Используйте систему управления настройками:

```python
import os
from pydantic import BaseSettings

class Settings(BaseSettings):
    """Настройки приложения"""
    # LLM настройки
    llm_provider: str = "openai"
    llm_model: str = "gpt-4"
    llm_api_key: str = ""
    llm_temperature: float = 0.7
    
    # Настройки агента
    agent_max_iterations: int = 50
    agent_timeout: int = 300
    agent_enable_logging: bool = True
    
    # Настройки безопасности
    encrypt_sensitive_data: bool = True
    enable_audit_logging: bool = True
    
    class Config:
        env_file = ".env"  # Используем .env файл для настроек
        env_prefix = "AGENT_"  # Префикс для переменных окружения: AGENT_LLM_API_KEY

settings = Settings()
```

## Практики документирования

### 1. Документирование кода

Используйте docstrings для документирования классов и методов:

```python
class UserService:
    """
    Сервис для управления пользователями.
    
    Отвечает за создание, обновление и удаление пользователей.
    """
    
    def create_user(self, user_data: dict) -> dict:
        """
        Создает нового пользователя.
        
        Args:
            user_data: Данные пользователя для создания
            
        Returns:
            Словарь с информацией о созданном пользователе
        """
        pass
```

### 2. Комментарии

Пишите комментарии, объясняющие "почему", а не "что":

- Не комментируйте очевидный код
- Объясняйте нетривиальные решения
- Используйте комментарии для обозначения временных решений (TODO, FIXME)

## Практики паттернов мышления

### 1. Создание специализированных паттернов

Создавайте специализированные паттерны мышления для конкретных задач:

```python
class SecurityAnalysisPattern(IThinkingPattern):
    """
    Паттерн для анализа безопасности кода.
    
    Обеспечивает безопасное выполнение анализа уязвимостей
    в коде с использованием различных методов проверки.
    
    Поддерживает:
    - SQL-инъекции
    - XSS-атаки
    - Небезопасное использование внешних ресурсов
    - Нарушения безопасности в API
    """
    
    @property
    def name(self) -> str:
        """Уникальное имя паттерна для анализа безопасности."""
        return "security_analysis_pattern"
    
    async def execute(
        self,
        state: AgentState,
        context: Any,
        available_capabilities: List[str]
    ) -> Dict[str, Any]:
        """
        Выполняет анализ безопасности кода.
        
        Args:
            state: Состояние агента на момент выполнения
            context: Контекст выполнения (например, код для анализа)
            available_capabilities: Список доступных возможностей для выполнения
            
        Returns:
            Словарь с результатами выполнения паттерна:
            - success: Успешно ли выполнено задание
            - findings: Список найденных уязвимостей
            - summary: Краткое описание выполнения задания
        """
        pass
```

### 2. Обработка специфических случаев

Обрабатывайте специфические случаи в паттернах:

```python
# examples/security_analysis_example.py
"""
Пример использования паттерна анализа безопасности кода.

В этом примере показано, как использовать паттерн анализа безопасности
для проверки Python-кода на наличие уязвимостей.
"""

from application.factories.agent_factory import AgentFactory
from domain.value_objects.domain_type import DomainType

async def security_analysis_example():
    """
    Пример выполнения задания по анализу безопасности.
    
    Возвращает результат выполнения задания по
    анализу безопасности кода на наличие уязвимостей.
    """
    
    # Создание агента для выполнения задания
    agent = await AgentFactory().create_agent(
        agent_type="composable",
        domain=DomainType.CODE_ANALYSIS
    )
    
    # Подготовка кода для анализа
    vulnerable_code = """
def login(username, password):
    query = f"SELECT * FROM users WHERE username='{username}' AND password='{password}'"
    return execute_query(query)
"""
    
    # Выполнение задания по анализу
    result = await agent.execute_task(
        task_description="Проанализируй этот код на наличие уязвимостей безопасности в веб-приложении",
        context={
            "code": vulnerable_code,
            "language": "python",
            "analysis_type": "security"
        }
    )
    
    print("Результаты выполнения задания по анализу безопасности:")
    if result.get("success"):
        findings = result.get("findings", [])
        for finding in findings:
            print(f"- {finding['type']}: {finding['description']}")
    else:
        print(f"Ошибка выполнения задания: {result.get('error')}")
    
    return result

if __name__ == "__main__":
    import asyncio
    asyncio.run(security_analysis_example())
```

## Практики логирования и мониторинга

### 1. Структурированное логирование

Используйте структурированное логирование:

```python
import logging
import json
from datetime import datetime

class StructuredLogger:
    """Структурированный логгер для приложения"""
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)
    
    def log_event(self, event_type: str, data: dict, level: str = "INFO"):
        """Записывает событие в структурированном формате с метаданными"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "event_type": event_type,
            "level": level,
            "data": data
        }
        
        log_message = json.dumps(log_entry, ensure_ascii=False)
        
        if level == "ERROR":
            self.logger.error(log_message)
        elif level == "WARNING":
            self.logger.warning(log_message)
        elif level == "DEBUG":
            self.logger.debug(log_message)
        else:
            self.logger.info(log_message)

# Пример использования в сервисе
class AgentService:
    def __init__(self):
        self.logger = StructuredLogger(self.__class__.__name__)
    
    async def execute_task(self, task_description: str, context: dict):
        """Выполняет задачу с логированием этапов выполнения"""
        self.logger.log_event("task_started", {
            "task_description": task_description[:50],  # Ограничиваем 50 символами
            "context_keys": list(context.keys()) if context else []
        })
        
        try:
            # Выполнение задачи
            result = await self._execute_task_logic(task_description, context)
            
            self.logger.log_event("task_completed", {
                "task_description": task_description[:50],
                "success": True,
                "result_keys": list(result.keys()) if result else []
            })
            
            return result
        except Exception as e:
            self.logger.log_event("task_failed", {
                "task_description": task_description[:50],
                "error": str(e),
                "error_type": type(e).__name__
            }, level="ERROR")
            
            raise
```

### 2. Сбор метрик

Собирайте метрики производительности:

```python
class MetricsCollector:
    """Сборщик метрик выполнения задач"""
    
    def __init__(self):
        self.metrics = {
            "tasks_completed": 0,
            "tasks_failed": 0,
            "average_execution_time": 0,
            "total_execution_time": 0,
            "error_rate": 0
        }
        self.execution_times = []
    
    def record_task_completion(self, execution_time: float):
        """Фиксирует завершение задачи с учетом времени выполнения"""
        self.metrics["tasks_completed"] += 1
        self.execution_times.append(execution_time)
        self.metrics["total_execution_time"] += execution_time
        
        if self.metrics["tasks_completed"] > 0:
            self.metrics["average_execution_time"] = (
                self.metrics["total_execution_time"] / self.metrics["tasks_completed"]
            )
    
    def record_task_failure(self):
        """Фиксирует ошибку выполнения задачи"""
        self.metrics["tasks_failed"] += 1
        self.metrics["error_rate"] = (
            self.metrics["tasks_failed"] / 
            max(1, self.metrics["tasks_completed"] + self.metrics["tasks_failed"])
        )
    
    def get_current_metrics(self) -> Dict[str, Any]:
        """Возвращает текущие метрики выполнения задач"""
        current_metrics = self.metrics.copy()
        current_metrics["execution_times"] = self.execution_times.copy()
        current_metrics["current_error_rate"] = self.metrics["error_rate"]
        
        return current_metrics
```

## Практики развертывания

### 1. Контейнеризация

Используйте Docker для контейнеризации:

```dockerfile
# Dockerfile
FROM python:3.10-slim

WORKDIR /app

# Установка зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование кода
COPY . .

# Создание пользователя для запуска приложения
RUN useradd --create-home --shell /bin/bash app
USER app

# Запуск приложения
CMD ["python", "-m", "application.main"]
```

### 2. Конфигурация для разных сред

Используйте разные конфигурации для разных сред:

```yaml
# config/production.yaml
agent:
  max_iterations: 100
  timeout: 600
  enable_logging: true
  max_concurrent_actions: 10

llm:
  provider: openai
  model: gpt-4
  temperature: 0.3
  max_tokens: 4096

system:
  debug_mode: false
  log_level: "INFO"
  enable_monitoring: true
  resource_limits:
    memory: "4GB"
    cpu: 80.0
```

```yaml
# config/development.yaml
agent:
  max_iterations: 50
  timeout: 300
  enable_logging: true
  max_concurrent_actions: 5

llm:
  provider: openai
  model: gpt-3.5-turbo
  temperature: 0.7
  max_tokens: 2048

system:
  debug_mode: true
  log_level: "DEBUG"
  enable_monitoring: false
  resource_limits:
    memory: "2GB"
    cpu: 50.0
```

Эти практики помогут вам эффективно использовать Koru AI Agent Framework и создавать надежные, безопасные и масштабируемые решения.