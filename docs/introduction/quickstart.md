# Быстрый старт с Koru AI Agent Framework

В этом руководстве вы узнаете, как быстро начать работу с Koru AI Agent Framework. Мы рассмотрим создание простого агента, выполнение базовой задачи и интеграцию с основными компонентами фреймворка.

## Подготовка к работе

Перед началом убедитесь, что вы выполнили [установку фреймворка](./installation.md) и настроили все необходимые зависимости.

## Простой пример: Создание агента для анализа кода

Начнем с простого примера, который демонстрирует создание агента и выполнение базовой задачи анализа кода.

### 1. Создание базового агента

```python
# simple_agent_demo.py
import asyncio
from application.factories.agent_factory import AgentFactory
from domain.value_objects.domain_type import DomainType

async def create_and_run_simple_agent():
    """Создание и запуск простого агента для анализа кода"""
    
    # Создание фабрики агентов
    agent_factory = AgentFactory()
    
    # Создание агента для домена анализа кода
    agent = await agent_factory.create_agent(
        agent_type="composable",  # Используем компонуемый агент
        domain=DomainType.CODE_ANALYSIS  # Указываем домен задачи
    )
    
    # Определяем задачу для агента
    task_description = "Проанализируй этот Python код наличие распространенных уязвимостей: \n\n" \
                      "def login(username, password):\n" \
                      "    query = f\"SELECT * FROM users WHERE username='{username}' AND password='{password}'\"\n" \
                      "    result = execute_query(query)\n" \
                      "    return result"
    
    print(f"Запуск агента для выполнения задачи: {task_description[:50]}...")
    
    # Выполнение задачи агентом
    result = await agent.execute_task(task_description)
    
    print(f"Результат выполнения задачи: {result}")
    
    return agent, result

# Запуск примера
if __name__ == "__main__":
    agent, result = asyncio.run(create_and_run_simple_agent())
```

### 2. Запуск примера

Сохраните код в файл `simple_agent_demo.py` и выполните:

```bash
python simple_agent_demo.py
```

## Более сложный пример: Использование инструментов и паттернов

Теперь давайте создадим более сложный пример, который демонстрирует использование инструментов и паттернов мышления.

### 1. Создание агента с инструментами

```python
# advanced_agent_demo.py
import asyncio
from application.factories.agent_factory import AgentFactory
from domain.value_objects.domain_type import DomainType
from infrastructure.tools.file_reader_tool import FileReaderTool
from infrastructure.tools.ast_parser_tool import ASTParserTool
from application.orchestration.atomic_actions import AtomicActionExecutor

async def create_advanced_agent_with_tools():
    """Создание агента с интеграцией инструментов"""
    
    # Создание агента
    agent = await AgentFactory().create_agent(
        agent_type="composable",
        domain=DomainType.CODE_ANALYSIS
    )
    
    # Создание инструментов
    file_reader = FileReaderTool()
    ast_parser = ASTParserTool()
    
    # Создание исполнителя атомарных действий
    action_executor = AtomicActionExecutor()
    
    # Регистрация инструментов как атомарных действий
    action_executor.register_action(file_reader)
    action_executor.register_action(ast_parser)
    
    # Путь к файлу для анализа (в реальном примере укажите реальный путь)
    sample_code = '''
def vulnerable_function(user_input):
    # Уязвимость: SQL-инъекция
    query = f"SELECT * FROM users WHERE id = {user_input}"
    result = execute_query(query)
    return result

def safe_function(user_input):
    # Безопасный код: использует параметризованные запросы
    query = "SELECT * FROM users WHERE id = ?"
    result = execute_query(query, (user_input,))
    return result
'''
    
    # Сохраняем пример кода во временный файл
    with open('temp_sample_code.py', 'w', encoding='utf-8') as f:
        f.write(sample_code)
    
    # Выполнение анализа с использованием инструментов
    print("Анализ кода с использованием инструментов...")
    
    # Шаг 1: Чтение файла
    read_result = await action_executor.execute_action(
        "file_reader",
        {"path": "temp_sample_code.py"}
    )
    
    if not read_result["success"]:
        print(f"Ошибка чтения файла: {read_result['error']}")
        return None
    
    print("Файл успешно прочитан")
    
    # Шаг 2: Парсинг AST
    ast_result = await action_executor.execute_action(
        "ast_parser",
        {
            "code": read_result["content"],
            "language": "python"
        }
    )
    
    print("AST успешно проанализирован")
    
    # Шаг 3: Адаптация агента к задаче
    task_description = f"Проанализируй этот Python код на наличие уязвимостей безопасности: {read_result['content']}"
    await agent.adapt_to_task(task_description)
    
    # Шаг 4: Выполнение анализа с использованием паттерна мышления
    analysis_result = await agent.execute_composable_pattern(
        pattern_name="security_analysis",
        context={
            "code": read_result["content"],
            "ast": ast_result,
            "target_file": "temp_sample_code.py"
        }
    )
    
    print(f"Результат анализа: {analysis_result}")
    
    # Удаляем временный файл
    import os
    os.remove('temp_sample_code.py')
    
    return agent, analysis_result

# Запуск продвинутого примера
if __name__ == "__main__":
    agent, result = asyncio.run(create_advanced_agent_with_tools())
```

## Интеграция с системой промтов

Теперь давайте посмотрим, как интегрировать агента с системой промтов:

```python
# prompt_integration_demo.py
import asyncio
from application.factories.agent_factory import AgentFactory
from application.services.prompt_loader import PromptLoader
from domain.value_objects.domain_type import DomainType

async def demonstrate_prompt_integration():
    """Демонстрация интеграции с системой промтов"""
    
    # Создание агента
    agent = await AgentFactory().create_agent(
        agent_type="composable",
        domain=DomainType.CODE_ANALYSIS
    )
    
    # Создание загрузчика промтов
    prompt_loader = PromptLoader(base_path="./prompts")
    
    # Загрузка промтов для анализа кода
    prompts, errors = prompt_loader.load_all_prompts()
    
    print(f"Загружено промтов: {len(prompts)}, ошибок: {len(errors)}")
    
    # Фильтрация промтов для анализа безопасности
    security_analysis_prompts = [
        prompt for prompt in prompts
        if prompt.domain == DomainType.CODE_ANALYSIS
        and "security" in prompt.capability_name.lower()
    ]
    
    print(f"Найдено промтов для анализа безопасности: {len(security_analysis_prompts)}")
    
    # Пример использования промта
    if security_analysis_prompts:
        security_prompt = security_analysis_prompts[0]
        print(f"Используемый промт: {security_prompt.id}")
        print(f"Роль: {security_prompt.role}")
        print(f"Версия: {security_prompt.semantic_version}")
        
        # Адаптация агента с использованием промта
        sample_code = """
def insecure_login(username, password):
    query = f"SELECT * FROM users WHERE username='{username}' AND password='{password}'"
    return execute_query(query)
"""
        
        # Выполнение задачи с использованием промта
        task_result = await agent.execute_task(
            f"Проанализируй этот код на уязвимости: {sample_code}"
        )
        
        print(f"Результат выполнения задачи: {task_result}")
    
    return agent, security_analysis_prompts

# Запуск примера с промтами
if __name__ == "__main__":
    agent, prompts = asyncio.run(demonstrate_prompt_integration())
```

## Создание кастомного паттерна мышления

Теперь создадим собственный паттерн мышления для специфической задачи:

```python
# custom_pattern_demo.py
import asyncio
from domain.abstractions.thinking_pattern import IThinkingPattern
from domain.models.agent.agent_state import AgentState
from application.factories.agent_factory import AgentFactory
from domain.value_objects.domain_type import DomainType

class CustomSecurityAnalysisPattern(IThinkingPattern):
    """Пользовательский паттерн для анализа безопасности кода"""
    
    @property
    def name(self) -> str:
        return "custom_security_analysis"
    
    async def execute(
        self,
        state: AgentState,
        context: dict,
        available_capabilities: list
    ) -> dict:
        """Выполнение пользовательского анализа безопасности"""
        
        code = context.get("code", "")
        file_path = context.get("file_path", "unknown")
        
        # Простой анализ на наличие потенциальных уязвимостей
        vulnerabilities = []
        
        if "execute_query" in code and "'" in code and "WHERE" in code:
            vulnerabilities.append({
                "type": "SQL Injection",
                "description": "Potential SQL injection vulnerability detected",
                "location": "Multiple occurrences",
                "severity": "HIGH"
            })
        
        if "eval(" in code or "exec(" in code:
            vulnerabilities.append({
                "type": "Code Injection",
                "description": "Dangerous eval()/exec() usage detected",
                "location": "Multiple occurrences",
                "severity": "CRITICAL"
            })
        
        if "password" in code.lower() and "=" in code and "hash" not in code.lower():
            vulnerabilities.append({
                "type": "Weak Password Storage",
                "description": "Password might be stored in plain text",
                "location": "Multiple occurrences",
                "severity": "MEDIUM"
            })
        
        return {
            "vulnerabilities_found": len(vulnerabilities),
            "vulnerabilities": vulnerabilities,
            "file_analyzed": file_path,
            "analysis_complete": True
        }
    
    async def adapt_to_task(self, task_description: str) -> dict:
        """Адаптация паттерна к задаче"""
        return {
            "analysis_depth": "comprehensive",
            "focus_areas": ["security", "input_validation", "authentication"]
        }

async def demonstrate_custom_pattern():
    """Демонстрация использования кастомного паттерна"""
    
    # Создание агента
    agent = await AgentFactory().create_agent(
        agent_type="composable",
        domain=DomainType.CODE_ANALYSIS
    )
    
    # Регистрация кастомного паттерна (псевдокод, так как конкретная реализация зависит от архитектуры)
    # В реальной системе нужно будет зарегистрировать паттерн в паттерн-менеджере
    
    # Пример кода с уязвимостями
    vulnerable_code = """
def login(username, password):
    query = f"SELECT * FROM users WHERE username='{username}' AND password='{password}'"
    return execute_query(query)

def execute_user_command(cmd):
    result = eval(cmd)
    return result

def save_password(password):
    with open('passwords.txt', 'w') as f:
        f.write(password)  # Плохая практика!
"""
    
    # Выполнение анализа с использованием кастомного паттерна
    result = await agent.execute_composable_pattern(
        pattern_name="custom_security_analysis",  # Это имя должно соответствовать свойству name в классе
        context={
            "code": vulnerable_code,
            "file_path": "example_vulnerable_code.py"
        }
    )
    
    print("Результаты анализа безопасности:")
    print(f"Найдено уязвимостей: {result.get('vulnerabilities_found', 0)}")
    
    for vuln in result.get('vulnerabilities', []):
        print(f"- {vuln['type']} ({vuln['severity']}): {vuln['description']}")
    
    return result

# Запуск примера с кастомным паттерном
if __name__ == "__main__":
    result = asyncio.run(demonstrate_custom_pattern())
```

## Практические советы для быстрого старта

### 1. Начните с простого

- Начинайте с базовых примеров и постепенно усложняйте
- Используйте готовые домены и паттерны до создания собственных
- Тестируйте каждый компонент по отдельности

### 2. Используйте доступные инструменты

- Ознакомьтесь с доступными инструментами в `infrastructure.tools`
- Используйте атомарные действия для выполнения базовых операций
- Интегрируйте инструменты через `AtomicActionExecutor`

### 3. Экспериментируйте с промтами

- Изучите структуру промтов в директории `prompts`
- Создавайте собственные промты для специфических задач
- Используйте версионирование промтов для отслеживания изменений

### 4. Следите за состоянием агента

- Мониторьте состояние агента через `AgentState`
- Используйте встроенные методы для регистрации ошибок и прогресса
- Реализуйте логику восстановления при необходимости

## Следующие шаги

После освоения базовых примеров рекомендуется:

1. Изучить [архитектуру фреймворка](../architecture/overview.md)
2. Ознакомиться с [паттернами мышления](../concepts/thinking_patterns.md) более подробно
3. Изучить [систему промтов](../prompts/overview.md)
4. Попробовать [другие примеры](../examples/overview.md)
5. Запустить [тесты](../testing/overview.md) для лучшего понимания работы компонентов

## Заключение

Это руководство дало вам базовое понимание того, как начать работу с Koru AI Agent Framework. Вы научились:

- Создавать базовых агентов
- Использовать инструменты и атомарные действия
- Интегрироваться с системой промтов
- Создавать собственные паттерны мышления

Продолжайте экспериментировать с фреймворком и изучать дополнительную документацию для более глубокого понимания возможностей системы.