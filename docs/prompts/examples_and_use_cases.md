# Примеры и сценарии использования промтов

В этом разделе рассматриваются практические примеры и сценарии использования промтов в Koru AI Agent Framework. Примеры демонстрируют различные подходы к применению промтов в реальных задачах и показывают, как они интегрируются с агентами и паттернами мышления.

## Основные сценарии использования

### 1. Анализ кода

Сценарий анализа кода на наличие уязвимостей и проблем качества.

#### Пример структуры промтов для анализа кода

**Системный промт (prompts/code_analysis/security_analysis/system/v1.0.md):**

```markdown
---
provider: openai
role: system
status: active
variables:
  - name: task_description
    type: string
    required: true
    description: "Описание задачи анализа"
 - name: target_vulnerabilities
    type: array
    required: false
    description: "Список уязвимостей для поиска"
expected_response:
  type: object
  properties:
    findings:
      type: array
      items:
        type: object
        properties:
          type:
            type: string
          severity:
            type: string
          location:
            type: object
          description:
            type: string
          recommendation:
            type: string
---

# Инструкции для агента анализа безопасности кода

Ты являешься экспертом в области безопасности кода. При анализе кода следуй следующим принципам:

1. Идентифицируй потенциальные уязвимости в коде
2. Оцени уровень риска каждой уязвимости
3. Предложи конкретные рекомендации по устранению
4. Объясни, почему каждая уязвимость представляет риск

## Задача

{{task_description}}

{% if target_vulnerabilities %}
## Фокусируйся на этих типах уязвимостей:
{% for vuln in target_vulnerabilities %}
- {{vuln}}
{% endfor %}
{% endif %}

Ты должен отвечать только в формате JSON с определенной структурой.
```

**Пользовательский промт (prompts/code_analysis/security_analysis/user/v1.0.0.md):**

```markdown
---
provider: openai
role: user
status: active
variables:
  - name: code_snippet
    type: string
    required: true
    description: "Фрагмент кода для анализа"
  - name: language
    type: string
    required: false
    default_value: "python"
    description: "Язык программирования"
---

Проанализируй следующий фрагмент {{language}} кода на наличие уязвимостей:

```
{{code_snippet}}
```

Обрати особое внимание на:
- Ввод и обработку пользовательских данных
- SQL-запросы и возможность инъекций
- Файловые операции
- Системные вызовы
- Управление аутентификацией и авторизацией
```

#### Пример использования в агенте

```python
# example_code_analysis.py
import asyncio
from domain.value_objects.domain_type import DomainType
from application.factories.agent_factory import AgentFactory
from infrastructure.services.prompt_loader import PromptLoader

async def analyze_code_example():
    """Пример анализа кода с использованием промтов"""
    
    # Инициализация сервисов
    prompt_loader = PromptLoader(base_path="./prompts")
    await prompt_loader.refresh_prompts()
    
    # Создание агента для анализа кода
    agent = await AgentFactory().create_agent(
        agent_type="composable",
        domain=DomainType.CODE_ANALYSIS
    )
    
    # Подготовка кода для анализа
    vulnerable_code = """
def login(username, password):
    query = f"SELECT * FROM users WHERE username='{username}' AND password='{password}'"
    result = execute_query(query)
    return result

def execute_user_command(cmd):
    import subprocess
    result = subprocess.check_output(cmd, shell=True)
    return result
"""
    
    # Подготовка контекста задачи
    context = {
        "code_snippet": vulnerable_code,
        "language": "python",
        "task_description": "Анализ безопасности Python-кода",
        "target_vulnerabilities": ["sql_injection", "command_injection", "shell_execution"]
    }
    
    # Выполнение анализа
    result = await agent.execute_task(
        task_description="Проанализируй этот код на наличие уязвимостей безопасности",
        context=context
    )
    
    print("Результаты анализа:")
    for finding in result.get("findings", []):
        print(f"- {finding['type']} ({finding['severity']}): {finding['description']}")
    
    return result

if __name__ == "__main__":
    asyncio.run(analyze_code_example())
```

### 2. Обработка данных

Сценарий обработки и анализа данных с использованием SQL-инструментов и аналитических промтов.

#### Пример промтов для обработки данных

**Системный промт (prompts/data_processing/data_analysis/system/v1.0.0.md):**

```markdown
---
provider: openai
role: system
status: active
variables:
  - name: analysis_goal
    type: string
    required: true
    description: "Цель анализа данных"
expected_response:
  type: object
  properties:
    summary:
      type: string
    insights:
      type: array
      items:
        type: string
    recommendations:
      type: array
      items:
        type: string
---

# Инструкции для агента анализа данных

Ты являешься экспертом в области анализа данных. При анализе данных следуй следующим принципам:

1. Выделяй ключевые метрики и показатели
2. Идентифицируй аномалии и отклонения
3. Формулируй бизнес-выводы
4. Предлагай конкретные рекомендации по улучшению

## Цель анализа

{{analysis_goal}}

Анализируй предоставленные данные и предоставь структурированный отчет.
```

**Пользовательский промт (prompts/data_processing/data_analysis/user/v1.0.0.md):**

```markdown
---
provider: openai
role: user
status: active
variables:
  - name: data_summary
    type: string
    required: true
    description: "Сводка данных"
  - name: query_results
    type: string
    required: true
    description: "Результаты SQL-запроса"
---

Проанализируй следующие данные:

## Сводка данных
{{data_summary}}

## Результаты запроса
{{query_results}}

Предоставь анализ с акцентом на:
- Ключевые тенденции
- Аномалии и отклонения
- Бизнес-выводы
- Рекомендации по улучшению
```

#### Пример использования

```python
# example_data_processing.py
import asyncio
from domain.value_objects.domain_type import DomainType
from infrastructure.tools.sql_tool import SQLTool

async def data_processing_example():
    """Пример обработки данных с использованием промтов"""
    
    # Подключение к базе данных
    sql_tool = SQLTool(connection_string="sqlite:///example.db")
    
    # Выполнение SQL-запроса
    query_result = await sql_tool.execute({
        "query": "SELECT user_id, purchase_amount, date FROM purchases ORDER BY date DESC LIMIT 100"
    })
    
    if not query_result["success"]:
        print(f"Ошибка выполнения запроса: {query_result['error']}")
        return
    
    # Подготовка данных для анализа
    data_summary = "Таблица покупок пользователей за последние 30 дней"
    query_results = str(query_result["results"])
    
    # Подготовка контекста
    context = {
        "data_summary": data_summary,
        "query_results": query_results,
        "analysis_goal": "Выявление тенденций покупательского поведения и аномалий"
    }
    
    # Создание агента для обработки данных
    agent = await AgentFactory().create_agent(
        agent_type="composable",
        domain=DomainType.DATA_PROCESSING
    )
    
    # Выполнение анализа
    result = await agent.execute_task(
        task_description="Проанализируй данные о покупках пользователей",
        context=context
    )
    
    print("Результаты анализа данных:")
    print(f"Сводка: {result.get('summary', 'N/A')}")
    print("Ключевые инсайты:")
    for insight in result.get('insights', []):
        print(f"- {insight}")
    print("Рекомендации:")
    for rec in result.get('recommendations', []):
        print(f"- {rec}")
    
    return result

if __name__ == "__main__":
    asyncio.run(data_processing_example())
```

### 3. Генерация контента

Сценарий генерации текстового контента на основе спецификаций и требований.

#### Пример промтов для генерации контента

**Системный промт (prompts/content_generation/report_generation/system/v1.0.0.md):**

```markdown
---
provider: openai
role: system
status: active
variables:
  - name: document_type
    type: string
    required: true
    description: "Тип генерируемого документа"
  - name: audience
    type: string
    required: true
    description: "Целевая аудитория"
expected_response:
  type: object
  properties:
    document:
      type: string
    summary:
      type: string
    key_points:
      type: array
      items:
        type: string
---

# Инструкции для генерации документов

Ты являешься профессиональным писателем и аналитиком. При создании документов следуй следующим принципам:

1. Соответствуй стилю и уровню сложности целевой аудитории
2. Обеспечивай логическую структуру и связность
3. Используй фактически точную информацию
4. Формулируй четкие и понятные выводы

## Тип документа
{{document_type}}

## Целевая аудитория
{{audience}}

Создай документ, соответствующий этим требованиям.
```

**Пользовательский промт (prompts/content_generation/report_generation/user/v1.0.0.md):**

```markdown
---
provider: openai
role: user
status: active
variables:
  - name: topic
    type: string
    required: true
    description: "Тема документа"
  - name: key_findings
    type: string
    required: false
    description: "Ключевые находки для включения"
  - name: requirements
    type: string
    required: false
    description: "Специфические требования"
---

# Задание на создание документа

## Тема
{{topic}}

{% if key_findings %}
## Ключевые находки для включения
{{key_findings}}
{% endif %}

{% if requirements %}
## Специфические требования
{{requirements}}
{% endif %}

Создай документ по указанной теме, следуя установленным стандартам и стилю.
```

#### Пример использования

```python
# example_content_generation.py
import asyncio
from domain.value_objects.domain_type import DomainType

async def content_generation_example():
    """Пример генерации контента с использованием промтов"""
    
    # Подготовка данных для генерации
    topic = "Анализ эффективности маркетинговых кампаний за Q4"
    key_findings = """
    - ROI первой кампании: 240%
    - ROI второй кампании: 180%
    - ROI третьей кампании: 320%
    - Лучший канал: email-маркетинг
    - Наихудший канал: печатная реклама
    """
    requirements = """
    - Формат: официальный бизнес-отчет
    - Объем: 2-3 страницы
    - Структура: executive summary, analysis, recommendations
    - Язык: английский
    """
    
    # Подготовка контекста
    context = {
        "topic": topic,
        "key_findings": key_findings,
        "requirements": requirements,
        "document_type": "business_report",
        "audience": "executive_management"
    }
    
    # Создание агента для генерации контента
    agent = await AgentFactory().create_agent(
        agent_type="composable",
        domain=DomainType.CONTENT_GENERATION
    )
    
    # Выполнение генерации
    result = await agent.execute_task(
        task_description="Создай бизнес-отчет по эффективности маркетинговых кампаний",
        context=context
    )
    
    print("Сгенерированный документ:")
    print(result.get('document', 'N/A'))
    
    print("\nКлючевые моменты:")
    for point in result.get('key_points', []):
        print(f"- {point}")
    
    return result

if __name__ == "__main__":
    asyncio.run(content_generation_example())
```

## Расширенные сценарии

### 1. Комбинированный анализ

Использование нескольких промтов для комплексного анализа:

```python
# complex_analysis_example.py
async def complex_analysis_example():
    """Пример комплексного анализа с несколькими этапами"""
    
    agent = await AgentFactory().create_agent(
        agent_type="composable",
        domain=DomainType.CODE_ANALYSIS
    )
    
    # Этап 1: Статический анализ кода
    static_analysis_context = {
        "code_snippet": sample_code,
        "analysis_type": "static",
        "focus_areas": ["security", "performance", "maintainability"]
    }
    
    static_result = await agent.execute_composable_pattern(
        pattern_name="code_analysis",
        context=static_analysis_context
    )
    
    # Этап 2: Динамический анализ на основе результатов статического
    dynamic_context = {
        "code_snippet": sample_code,
        "static_findings": static_result,
        "analysis_type": "dynamic",
        "test_scenarios": ["edge_cases", "performance_limits", "error_conditions"]
    }
    
    dynamic_result = await agent.execute_composable_pattern(
        pattern_name="dynamic_analysis",
        context=dynamic_context
    )
    
    # Этап 3: Комбинированный отчет
    combined_context = {
        "static_analysis": static_result,
        "dynamic_analysis": dynamic_result,
        "report_type": "comprehensive_security_review"
    }
    
    final_report = await agent.execute_composable_pattern(
        pattern_name="report_generation",
        context=combined_context
    )
    
    return final_report
```

### 2. Адаптивные промты

Создание адаптивных промтов, которые изменяются в зависимости от контекста:

```python
# adaptive_prompts_example.py
async def adaptive_prompt_example():
    """Пример адаптивных промтов"""
    
    # Определение сложности задачи
    task_complexity = await determine_task_complexity(task_description)
    
    # Выбор соответствующего промта на основе сложности
    if task_complexity == "low":
        prompt_version = "v1.0.0"  # Простой промт
    elif task_complexity == "medium":
        prompt_version = "v2.0.0"  # Средний уровень детализации
    else:
        prompt_version = "v3.0.0"  # Подробный промт с пошаговыми инструкциями
    
    # Использование выбранного промта
    context = {
        "task_description": task_description,
        "complexity_level": task_complexity,
        "required_detail_level": get_detail_requirement(task_complexity)
    }
    
    result = await agent.execute_task(
        task_description=f"Execute with prompt version {prompt_version}",
        context=context
    )
    
    return result
```

## Лучшие практики

### 1. Структурирование промтов

- Используйте четкую структуру с разделами
- Определяйте цели и задачи в начале промта
- Включайте примеры ожидаемого поведения
- Указывайте формат ожидаемого ответа

### 2. Использование переменных

- Используйте переменные для параметризации промтов
- Обеспечьте валидацию переменных перед использованием
- Используйте значения по умолчанию для необязательных переменных
- Документируйте назначение каждой переменной

### 3. Тестирование промтов

- Тестируйте промты с различными наборами данных
- Проверяйте граничные случаи и ошибочные входные данные
- Оценивайте качество и согласованность результатов
- Мониторьте производительность и время отклика

### 4. Версионирование

- Используйте семантическое версионирование
- Документируйте изменения между версиями
- Обеспечьте обратную совместимость при возможности
- Планируйте миграцию между версиями

## Интеграция с системой

Примеры показывают, как промты интегрируются с различными компонентами системы:

- **С агентами**: Промты используются для выполнения задач и адаптации к доменам
- **С паттернами мышления**: Промты интегрируются в паттерны для решения сложных задач
- **С инструментами**: Результаты инструментов могут использоваться в промтах
- **С системой событий**: Использование промтов может генерировать события
- **С системой логирования**: Использование промтов логируется для анализа