# Сценарии использования Composable AI Agent Framework

В этом разделе представлены практические сценарии использования Composable AI Agent Framework для решения различных задач. Примеры демонстрируют, как можно адаптировать и использовать фреймворк в реальных ситуациях.

## 1. Анализ безопасности кода

### Описание задачи
Анализ Python-кода на наличие уязвимостей безопасности, таких как SQL-инъекции, XSS, небезопасное выполнение команд и т.д.

### Пример использования

```python
# examples/code_security_analysis.py
import asyncio
from application.factories.agent_factory import AgentFactory
from domain.value_objects.domain_type import DomainType

async def code_security_analysis_example():
    """Пример анализа безопасности кода"""
    
    # Создать агента для анализа кода
    agent = await AgentFactory().create_agent(
        agent_type="composable",
        domain=DomainType.CODE_ANALYSIS
    )
    
    # Код для анализа с уязвимостями
    vulnerable_code = """
class UserAuth:
    def authenticate(self, username, password):
        # Уязвимость: SQL-инъекция
        query = f"SELECT * FROM users WHERE username='{username}' AND password='{password}'"
        return execute_query(query)
    
    def execute_user_command(self, cmd):
        # Уязвимость: выполнение команд
        import subprocess
        result = subprocess.check_output(cmd, shell=True)
        return result
    
    def process_file_path(self, file_path):
        # Уязвимость: путьTraversal
        import os
        full_path = os.path.join("/safe/dir/", file_path)
        with open(full_path, 'r') as file:
            return file.read()
"""

    # Выполнить анализ безопасности
    result = await agent.execute_task(
        task_description="Проанализируй этот Python код на наличие уязвимостей безопасности",
        context={
            "code": vulnerable_code,
            "language": "python",
            "analysis_requirements": {
                "focus_areas": ["sql_injection", "command_execution", "path_traversal"],
                "report_format": "detailed",
                "severity_threshold": "medium"
            }
        }
    )
    
    print("Результаты анализа безопасности:")
    print(f"Успешно: {result.get('success')}")
    if result.get('success'):
        findings = result.get('findings', [])
        for finding in findings:
            print(f"- {finding['type']}: {finding['description']} (Степень: {finding['severity']})")
    else:
        print(f"Ошибка: {result.get('error')}")
    
    return result

if __name__ == "__main__":
    asyncio.run(code_security_analysis_example())
```

### Специфические компоненты

Для этого сценария могут быть созданы специфические компоненты:

- **Паттерн анализа безопасности**: Определяет стратегию поиска уязвимостей
- **Инструменты анализа**: Парсер AST, сканер уязвимостей, анализатор SQL-запросов
- **Промты безопасности**: Специфические инструкции для LLM по поиску уязвимостей

## 2. Обработка и анализ данных

### Описание задачи
Обработка данных из различных источников (файлы, базы данных, API) с выполнением анализа, трансформации и генерации отчетов.

### Пример использования

```python
# examples/data_processing_analysis.py
import asyncio
from application.factories.agent_factory import AgentFactory
from domain.value_objects.domain_type import DomainType

async def data_processing_analysis_example():
    """Пример обработки и анализа данных"""
    
    # Создать агента для обработки данных
    agent = await AgentFactory().create_agent(
        agent_type="composable",
        domain=DomainType.DATA_PROCESSING
    )
    
    # Выполнить задачу обработки данных
    result = await agent.execute_task(
        task_description="Проанализируй данные из CSV-файла и сформируй отчет о ключевых метриках",
        context={
            "source": {
                "type": "file",
                "path": "./data/users.csv",
                "format": "csv"
            },
            "analysis_type": "statistical",
            "metrics": ["count", "mean", "std", "min", "max"],
            "requirements": {
                "output_format": "json",
                "include_visualizations": True
            }
        }
    )
    
    print("Результаты обработки данных:")
    print(f"Успешно: {result.get('success')}")
    if result.get('success'):
        analysis = result.get('analysis', {})
        print(f"Обработано записей: {analysis.get('record_count')}")
        print(f"Колонок: {analysis.get('column_count')}")
        print(f"Ключевые метрики: {analysis.get('metrics')}")
    else:
        print(f"Ошибка: {result.get('error')}")
    
    return result

if __name__ == "__main__":
    asyncio.run(data_processing_analysis_example())
```

### Специфические компоненты

- **Инструменты обработки данных**: CSV-парсер, SQL-инструмент, визуализатор данных
- **Паттерны анализа**: Статистический анализ, анализ трендов, поиск аномалий
- **Промты анализа**: Инструкции для генерации отчетов и анализа данных

## 3. Генерация контента

### Описание задачи
Создание текстового или другого контента на основе спецификаций, требований и шаблонов.

### Пример использования

```python
# examples/content_generation.py
import asyncio
from application.factories.agent_factory import AgentFactory
from domain.value_objects.domain_type import DomainType

async def content_generation_example():
    """Пример генерации контента"""
    
    # Создать агента для генерации контента
    agent = await AgentFactory().create_agent(
        agent_type="composable",
        domain=DomainType.CONTENT_GENERATION
    )
    
    # Выполнить задачу генерации
    result = await agent.execute_task(
        task_description="Создай техническую документацию для Python-библиотеки",
        context={
            "library_info": {
                "name": "MyLibrary",
                "version": "1.0.0",
                "description": "Библиотека для обработки данных",
                "functions": [
                    {
                        "name": "process_data",
                        "signature": "process_data(data: List[Dict], options: Dict = None) -> List[Dict]",
                        "description": "Обрабатывает список словарей с данными"
                    },
                    {
                        "name": "validate_input", 
                        "signature": "validate_input(data: Any) -> bool",
                        "description": "Проверяет корректность входных данных"
                    }
                ]
            },
            "target_audience": "разработчики Python",
            "output_format": "markdown",
            "style_requirements": {
                "tone": "technical",
                "complexity": "intermediate",
                "sections": ["overview", "installation", "usage", "api_reference"]
            }
        }
    )
    
    print("Результаты генерации контента:")
    print(f"Успешно: {result.get('success')}")
    if result.get('success'):
        generated_content = result.get('content', '')
        print(f"Сгенерировано символов: {len(generated_content)}")
        print(f"Формат: {result.get('format')}")
    else:
        print(f"Ошибка: {result.get('error')}")
    
    return result

if __name__ == "__main__":
    asyncio.run(content_generation_example())
```

### Специфические компоненты

- **Паттерны генерации**: Шаблонные генераторы, структурированные генераторы
- **Инструменты форматирования**: Markdown-форматтер, HTML-генератор, документационные инструменты
- **Промты генерации**: Инструкции для создания контента в различных стилях и форматах

## 4. Комплексный анализ проекта

### Описание задачи
Комплексный анализ проекта с оценкой безопасности, качества кода, архитектурных проблем и соответствия стандартам.

### Пример использования

```python
# examples/project_analysis.py
import asyncio
from application.factories.advanced_agent_factory import AdvancedAgentFactory
from domain.value_objects.domain_type import DomainType

async def project_analysis_example():
    """Пример комплексного анализа проекта"""
    
    # Создать расширенную фабрику
    factory = AdvancedAgentFactory()
    
    # Создать агента с расширенными возможностями
    agent = await factory.create_agent_with_config(
        agent_type="composable",
        domain=DomainType.CODE_ANALYSIS,
        config={
            "enable_security_analysis": True,
            "enable_quality_analysis": True,
            "enable_dependency_analysis": True,
            "max_concurrent_analyses": 5
        }
    )
    
    # Выполнить комплексный анализ проекта
    result = await agent.execute_task(
        task_description="Выполни полный анализ безопасности, качества и зависимостей этого Python-проекта",
        context={
            "project_path": "./my_python_project",
            "analysis_types": ["security", "quality", "dependencies"],
            "exclude_patterns": ["**/tests/**", "**/node_modules/**", "**/__pycache__/**"],
            "include_patterns": ["**/*.py", "**/*.js", "**/*.ts"],
            "report_requirements": {
                "format": "comprehensive",
                "include_recommendations": True,
                "severity_filter": "medium-high",
                "output_path": "./analysis_report.md"
            }
        }
    )
    
    print("Результаты комплексного анализа проекта:")
    print(f"Успешно: {result.get('success')}")
    if result.get('success'):
        analysis_results = result.get('analysis_results', {})
        print(f"Проанализировано файлов: {analysis_results.get('files_analyzed')}")
        print(f"Найдено уязвимостей: {analysis_results.get('security_findings_count')}")
        print(f"Найдено проблем качества: {analysis_results.get('quality_issues_count')}")
        print(f"Найдено проблем зависимостей: {analysis_results.get('dependency_issues_count')}")
    else:
        print(f"Ошибка: {result.get('error')}")
    
    return result

if __name__ == "__main__":
    asyncio.run(project_analysis_example())
```

### Специфические компоненты

- **Композитный агент**: Интегрирует несколько специализированных анализаторов
- **Многофайловый анализатор**: Специфический паттерн для анализа проектов
- **Система отчетности**: Генератор комплексных отчетов
- **Промты анализа**: Интеграционные промты для объединения результатов

## 5. Автоматическое тестирование

### Описание задачи
Генерация и выполнение тестов для кода, включая модульные, интеграционные и функциональные тесты.

### Пример использования

```python
# examples/automated_testing.py
import asyncio
from application.factories.agent_factory import AgentFactory
from domain.value_objects.domain_type import DomainType

async def automated_testing_example():
    """Пример автоматического тестирования"""
    
    # Создать агента для тестирования
    agent = await AgentFactory().create_agent(
        agent_type="composable",
        domain=DomainType.TESTING
    )
    
    # Код для которого нужно сгенерировать тесты
    target_code = """
def calculate_discount(price, discount_percent):
    if discount_percent < 0 or discount_percent > 100:
        raise ValueError("Discount percent must be between 0 and 100")
    
    if price < 0:
        raise ValueError("Price cannot be negative")
    
    discount_amount = price * (discount_percent / 100)
    final_price = price - discount_amount
    
    return round(final_price, 2)

def apply_coupon(price, coupon_code):
    coupons = {
        "SAVE10": 10,
        "SAVE20": 20,
        "SAVE30": 30
    }
    
    if coupon_code not in coupons:
        raise ValueError("Invalid coupon code")
    
    discount_percent = coupons[coupon_code]
    return calculate_discount(price, discount_percent)
"""

    # Выполнить генерацию тестов
    result = await agent.execute_task(
        task_description="Сгенерируй модульные тесты для этих функций Python",
        context={
            "code": target_code,
            "language": "python",
            "test_framework": "pytest",
            "coverage_requirements": {
                "minimum_coverage": 80,
                "test_types": ["unit", "edge_cases", "error_handling"]
            },
            "requirements": {
                "assertion_style": "pytest_assertions",
                "mock_usage": True,
                "parametrized_tests": True
            }
        }
    )
    
    print("Результаты генерации тестов:")
    print(f"Успешно: {result.get('success')}")
    if result.get('success'):
        generated_tests = result.get('tests', '')
        print(f"Сгенерировано тестов: {result.get('test_count')}")
        print(f"Ожидаемое покрытие: {result.get('expected_coverage')}")
        print("Пример сгенерированного теста:")
        print(generated_tests[:500] + "..." if len(generated_tests) > 500 else generated_tests)
    else:
        print(f"Ошибка: {result.get('error')}")
    
    return result

if __name__ == "__main__":
    asyncio.run(automated_testing_example())
```

### Специфические компоненты

- **Генератор тестов**: Паттерн для создания тестов на основе кода
- **Анализатор покрытия**: Инструмент для оценки покрытия тестами
- **Тестовый исполнитель**: Компонент для выполнения сгенерированных тестов
- **Промты тестирования**: Инструкции для генерации тестов различных типов

## 6. Инфраструктурные задачи

### Описание задачи
Управление инфраструктурой, выполнение системных команд, мониторинг и диагностика.

### Пример использования

```python
# examples/infrastructure_management.py
import asyncio
from application.factories.agent_factory import AgentFactory
from domain.value_objects.domain_type import DomainType

async def infrastructure_management_example():
    """Пример управления инфраструктурой"""
    
    # Создать агента для инфраструктурных задач
    agent = await AgentFactory().create_agent(
        agent_type="composable",
        domain=DomainType.INFRASTRUCTURE
    )
    
    # Выполнить инфраструктурную задачу
    result = await agent.execute_task(
        task_description="Выполни диагностику состояния сервера и сформируй отчет",
        context={
            "target_server": "localhost",
            "diagnostic_checks": [
                "cpu_usage", 
                "memory_usage", 
                "disk_space", 
                "network_status",
                "running_processes"
            ],
            "requirements": {
                "include_recommendations": True,
                "report_format": "structured",
                "performance_thresholds": {
                    "cpu_warning": 70,
                    "cpu_critical": 90,
                    "memory_warning": 80,
                    "memory_critical": 95
                }
            }
        }
    )
    
    print("Результаты диагностики инфраструктуры:")
    print(f"Успешно: {result.get('success')}")
    if result.get('success'):
        diagnostics = result.get('diagnostics', {})
        print(f"Сервер: {diagnostics.get('server')}")
        print(f"CPU использование: {diagnostics.get('cpu_usage')}")
        print(f"Память использование: {diagnostics.get('memory_usage')}")
        print(f"Диск использование: {diagnostics.get('disk_usage')}")
        print(f"Рекомендации: {diagnostics.get('recommendations')}")
    else:
        print(f"Ошибка: {result.get('error')}")
    
    return result

if __name__ == "__main__":
    asyncio.run(infrastructure_management_example())
```

### Специфические компоненты

- **Системные инструменты**: Инструменты для выполнения команд, мониторинга ресурсов
- **Паттерны диагностики**: Специфические стратегии диагностики системы
- **Мониторинговые компоненты**: Инструменты для сбора метрик и мониторинга
- **Промты управления**: Инструкции для безопасного выполнения системных задач

## 7. Адаптация под специфические домены

### Пример создания специфического домена

```python
# examples/custom_domain_example.py
import asyncio
from application.factories.specialized_agent_factory import SpecializedAgentFactory
from domain.value_objects.domain_type import DomainType

# Создать кастомный тип домена
from enum import Enum

class CustomDomainType(Enum):
    """Дополнительные типы доменов"""
    FINANCIAL_ANALYSIS = "financial_analysis"
    MEDICAL_DIAGNOSIS = "medical_diagnosis"
    LEGAL_REVIEW = "legal_review"
    EDUCATIONAL_CONTENT = "educational_content"

async def custom_domain_example():
    """Пример использования кастомного домена"""
    
    # Создать фабрику с поддержкой кастомных доменов
    factory = SpecializedAgentFactory()
    
    # Зарегистрировать кастомный домен
    await factory.domain_manager.register_domain(
        domain_type=CustomDomainType.FINANCIAL_ANALYSIS,
        config={
            "capabilities": [
                "financial_data_analysis",
                "risk_assessment", 
                "compliance_checking",
                "report_generation"
            ],
            "security_policy": {
                "data_encryption_required": True,
                "audit_logging_enabled": True
            }
        }
    )
    
    # Создать агента для кастомного домена
    agent = await factory.create_agent(
        agent_type="composable",
        domain=CustomDomainType.FINANCIAL_ANALYSIS
    )
    
    # Выполнить задачу в кастомном домене
    result = await agent.execute_task(
        task_description="Проанализируй эти финансовые данные на риски и соответствие нормативам",
        context={
            "financial_data": {
                "transactions": [...],  # Данные транзакций
                "accounts": [...],      # Данные счетов
                "period": "Q4_2023"
            },
            "regulations": ["SOX", "GDPR", "PCI_DSS"],
            "requirements": {
                "risk_model": "conservative",
                "report_format": "regulatory_compliant",
                "include_recommendations": True
            }
        }
    )
    
    print(f"Результат анализа в кастомном домене: {result}")
    
    return result

if __name__ == "__main__":
    asyncio.run(custom_domain_example())
```

## 8. Интеграция с внешними системами

### Пример интеграции с внешним API

```python
# examples/external_api_integration.py
import asyncio
from application.factories.agent_factory import AgentFactory
from domain.value_objects.domain_type import DomainType

async def external_api_integration_example():
    """Пример интеграции с внешним API"""
    
    # Создать агента
    agent = await AgentFactory().create_agent(
        agent_type="composable",
        domain=DomainType.DATA_PROCESSING
    )
    
    # Интегрировать с внешним API
    from infrastructure.tools.api_client_tool import APIClientTool
    
    api_tool = APIClientTool(
        base_url="https://api.example.com",
        headers={"Authorization": "Bearer ${API_TOKEN}"}
    )
    
    # Зарегистрировать инструмент в агенте
    agent.register_tool("external_api_client", api_tool)
    
    # Выполнить задачу с использованием внешнего API
    result = await agent.execute_task(
        task_description="Получи данные пользователей из внешнего API и проанализируй их",
        context={
            "api_endpoint": "/users",
            "api_params": {
                "limit": 100,
                "offset": 0,
                "filter": {"status": "active"}
            },
            "analysis_requirements": {
                "data_fields": ["name", "email", "registration_date", "last_login"],
                "anomalies_to_check": ["inactive_accounts", "duplicate_emails", "suspicious_activity"]
            }
        }
    )
    
    print(f"Результат интеграции с внешним API: {result}")
    
    return result

if __name__ == "__main__":
    asyncio.run(external_api_integration_example())
```

## Лучшие практики использования

### 1. Модульность и повторное использование

Создавайте компоненты, которые можно повторно использовать:

```python
# Хорошо: модульные и переиспользуемые компоненты
class BaseAnalysisPattern:
    """Базовый паттерн анализа"""
    pass

class SecurityAnalysisPattern(BaseAnalysisPattern):
    """Паттерн анализа безопасности"""
    pass

class CodeQualityAnalysisPattern(BaseAnalysisPattern):
    """Паттерн анализа качества кода"""
    pass

# Плохо: монолитные компоненты
class MonolithicAnalysisPattern:
    """Монолитный паттерн анализа - сложно расширять и тестировать"""
    pass
```

### 2. Безопасность и валидация

Обязательно учитывайте безопасность при создании сценариев:

```python
def validate_task_context(self, context: Dict[str, Any]) -> List[str]:
    """Проверить контекст задачи на безопасность"""
    errors = []
    
    # Проверить чувствительные поля
    sensitive_fields = ["password", "token", "api_key", "secret", "credentials"]
    for field in sensitive_fields:
        if field in context:
            errors.append(f"Чувствительное поле '{field}' обнаружено в контексте задачи")
    
    # Проверить размер контекста
    context_size = len(str(context))
    max_size = 10 * 1024 * 1024  # 10MB
    if context_size > max_size:
        errors.append(f"Контекст задачи слишком велик: {context_size} байт, максимум {max_size}")
    
    return errors
```

### 3. Обработка ошибок

Обеспечьте надежную обработку ошибок:

```python
async def execute_task(self, task_description: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
    """Выполнить задачу с надежной обработкой ошибок"""
    try:
        # Проверить ограничения
        if self.state.error_count > self.max_error_threshold:
            return {
                "success": False,
                "error": "Превышено максимальное количество ошибок",
                "needs_reset": True
            }
        
        # Проверить безопасность задачи
        security_check = await self._check_task_security(task_description, context)
        if not security_check["allowed"]:
            return {
                "success": False,
                "error": f"Задача не прошла проверку безопасности: {security_check['reason']}",
                "security_violation": True
            }
        
        # Выполнить основную логику
        result = await self._execute_extended_logic(task_description, context)
        
        # Обновить состояние при успехе
        self.state.register_progress(progressed=True)
        
        return {"success": True, **result}
    except SecurityError as e:
        self.state.register_error()
        self.state.complete()  # Критическая ошибка безопасности
        return {
            "success": False,
            "error": f"Ошибка безопасности: {str(e)}",
            "error_type": "security",
            "terminated": True
        }
    except ResourceLimitExceededError as e:
        self.state.register_error()
        return {
            "success": False,
            "error": f"Превышено ограничение ресурсов: {str(e)}",
            "error_type": "resource_limit"
        }
    except Exception as e:
        self.state.register_error()
        return {
            "success": False,
            "error": f"Внутренняя ошибка: {str(e)}",
            "error_type": "internal"
        }
```

### 4. Тестирование сценариев

Создавайте тесты для каждого сценария использования:

```python
# test_usage_scenarios.py
import pytest
from unittest.mock import AsyncMock, Mock
import tempfile
import os

class TestCodeSecurityAnalysisScenario:
    @pytest.mark.asyncio
    async def test_security_analysis_with_vulnerabilities(self):
        """Тест анализа кода с уязвимостями"""
        # Создать агента
        agent = await AgentFactory().create_agent(
            agent_type="composable",
            domain=DomainType.CODE_ANALYSIS
        )
        
        # Код с уязвимостями
        vulnerable_code = """
def login(username, password):
    query = f"SELECT * FROM users WHERE username='{username}' AND password='{password}'"
    return execute_query(query)
"""
        
        # Выполнить анализ
        result = await agent.execute_task(
            task_description="Проанализируй этот код на безопасность",
            context={
                "code": vulnerable_code,
                "language": "python"
            }
        )
        
        # Проверить результат
        assert result["success"] is True
        assert "findings" in result
        assert len(result["findings"]) > 0
        assert any(f["type"] == "SQL_INJECTION" for f in result["findings"])

class TestDataProcessingScenario:
    @pytest.mark.asyncio
    async def test_csv_data_analysis(self):
        """Тест анализа данных из CSV"""
        # Создать агента
        agent = await AgentFactory().create_agent(
            agent_type="composable",
            domain=DomainType.DATA_PROCESSING
        )
        
        # Создать временный CSV файл для теста
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("name,age,city\nJohn,30,NYC\nJane,25,LA\nBob,35,NYC")
            temp_csv_path = f.name
        
        try:
            # Выполнить анализ CSV
            result = await agent.execute_task(
                task_description="Проанализируй этот CSV файл и сформируй отчет",
                context={
                    "source": {
                        "type": "file",
                        "path": temp_csv_path,
                        "format": "csv"
                    },
                    "analysis_type": "statistical"
                }
            )
            
            # Проверить результат
            assert result["success"] is True
            assert "analysis" in result
            assert "record_count" in result["analysis"]
            assert result["analysis"]["record_count"] == 3
        finally:
            # Удалить временный файл
            os.unlink(temp_csv_path)

class TestContentGenerationScenario:
    @pytest.mark.asyncio
    async def test_documentation_generation(self):
        """Тест генерации документации"""
        # Создать агента
        agent = await AgentFactory().create_agent(
            agent_type="composable",
            domain=DomainType.CONTENT_GENERATION
        )
        
        # Выполнить генерацию документации
        result = await agent.execute_task(
            task_description="Создай документацию для этой функции Python",
            context={
                "function_info": {
                    "name": "calculate_tax",
                    "signature": "calculate_tax(amount: float, rate: float) -> float",
                    "description": "Вычисляет налог на основе суммы и ставки"
                },
                "target_audience": "разработчики",
                "output_format": "markdown"
            }
        )
        
        # Проверить результат
        assert result["success"] is True
        assert "content" in result
        assert len(result["content"]) > 0
        assert "calculate_tax" in result["content"]
```

Эти сценарии использования демонстрируют разнообразные возможности Composable AI Agent Framework и показывают, как его можно адаптировать под различные задачи и домены, обеспечивая гибкость, безопасность и надежность системы.