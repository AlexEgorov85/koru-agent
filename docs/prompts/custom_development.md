# Разработка промтов под свои задачи

В этом разделе описаны рекомендации и практики по созданию и настройке промтов для специфических задач и требований. Вы узнаете, как адаптировать существующие промты и создавать новые для удовлетворения уникальных потребностей вашего проекта.

## Создание новых промтов

### 1. Планирование промта

Перед созданием нового промта важно определить его назначение и структуру:

#### Шаг 1: Определение цели
- Какую задачу должен решать промт?
- Какой результат ожидается?
- В каком домене будет использоваться?
- Какие данные будут передаваться в качестве переменных?

#### Шаг 2: Выбор роли
Определите подходящую роль для промта:
- `system` - для задания общего контекста и правил
- `user` - для передачи конкретных данных и запросов
- `assistant` - для предоставления примеров ответов
- `tool` - для форматирования вызовов инструментов

#### Шаг 3: Определение переменных
Создайте список переменных, которые будут использоваться в промте:

```yaml
variables:
  - name: task_description
    type: string
    required: true
    description: "Описание задачи для обработки"
  - name: priority
    type: string
    required: false
    default_value: "normal"
    description: "Приоритет выполнения задачи"
  - name: deadline
    type: string
    required: false
    description: "Крайний срок выполнения"
```

### 2. Структура нового промта

Создайте файл промта в соответствии с иерархией:

```
prompts/
└── {your_domain}/
    └── {your_capability}/
        └── {role}/
            └── v{version}.md
```

Пример: `prompts/custom_tasks/report_generation/system/v1.0.0.md`

### 3. Пример создания промта

**Пример системного промта для генерации отчетов:**

```markdown
---
provider: openai
role: system
status: draft
variables:
  - name: report_type
    type: string
    required: true
    description: "Тип генерируемого отчета"
  - name: audience
    type: string
    required: true
    description: "Целевая аудитория отчета"
  - name: period
    type: string
    required: false
    description: "Период, за который составляется отчет"
expected_response:
  type: object
  properties:
    report:
      type: string
      description: "Сгенерированный отчет"
    summary:
      type: string
      description: "Краткое резюме отчета"
    key_points:
      type: array
      items:
        type: string
      description: "Ключевые моменты отчета"
---

# Инструкции для генерации отчетов

Ты являешься профессиональным аналитиком и писателем отчетов. При создании отчетов следуй следующим принципам:

1. Соответствуй стилю и уровню сложности целевой аудитории
2. Обеспечивай логическую структуру и связность
3. Используй фактически точную информацию
4. Формулируй четкие и понятные выводы

## Тип отчета
{{report_type}}

## Целевая аудитория
{{audience}}

## Период
{% if period %}{{period}}{% else %}Текущий период{% endif %}

Создай отчет, соответствующий этим требованиям.
```

## Адаптация существующих промтов

### 1. Копирование и модификация

Для адаптации существующего промта:

1. Скопируйте существующий промт в новую директорию
2. Измените структуру под свои нужды
3. Обновите переменные и ожидаемый ответ
4. Протестируйте изменения

### 2. Пример адаптации

**Существующий промт (general_analysis/system/v1.0.0.md):**

```markdown
---
provider: openai
role: system
status: active
variables:
  - name: data
    type: string
    required: true
    description: "Данные для анализа"
---

Ты аналитик данных. Проанализируй предоставленные данные и предоставь выводы.
```

**Адаптированный промт (financial_analysis/system/v1.0.0.md):**

```markdown
---
provider: openai
role: system
status: draft
variables:
  - name: financial_data
    type: string
    required: true
    description: "Финансовые данные для анализа"
  - name: reporting_period
    type: string
    required: false
    description: "Отчетный период"
  - name: stakeholders
    type: array
    required: false
    description: "Заинтересованные стороны"
expected_response:
  type: object
  properties:
    financial_summary:
      type: string
    risk_assessment:
      type: string
    recommendations:
      type: array
      items:
        type: string
---

# Инструкции для финансового анализа

Ты являешься сертифицированным финансовым аналитиком. При анализе финансовых данных следуй следующим принципам:

1. Используй только достоверные финансовые метрики
2. Обеспечивай точность расчетов
3. Учитывай рыночные тенденции
4. Формулируй практические рекомендации

## Отчетный период
{% if reporting_period %}{{reporting_period}}{% else %}Текущий период{% endif %}

## Заинтересованные стороны
{% if stakeholders %}
Анализ должен быть подготовлен для:
{% for stakeholder in stakeholders %}
- {{stakeholder}}
{% endfor %}
{% endif %}

Проанализируй предоставленные финансовые данные и предоставь структурированный отчет.
```

## Тестирование и валидация

### 1. Создание тестовых сценариев

Для каждого нового промта создайте тестовые сценарии:

```python
# test_custom_prompts.py
import pytest
from application.services.prompt_loader import PromptLoader
from application.services.prompt_renderer import PromptRenderer

class TestCustomPrompts:
    @pytest.mark.asyncio
    async def test_financial_analysis_prompt(self):
        """Тестирование пользовательского промта финансового анализа"""
        
        # Загрузка промта
        loader = PromptLoader(base_path="./prompts")
        prompts, errors = loader.load_all_prompts()
        
        # Поиск нужного промта
        financial_prompt = next(
            (p for p in prompts if p.capability_name == "financial_analysis"),
            None
        )
        
        assert financial_prompt is not None, "Financial analysis prompt not found"
        
        # Подготовка тестовых данных
        test_context = {
            "financial_data": "Revenue: $1M, Expenses: $800K, Profit: $200K",
            "reporting_period": "Q4 2023",
            "stakeholders": ["Executive Team", "Investors"]
        }
        
        # Рендеринг промта
        renderer = PromptRenderer()
        rendered_prompt = renderer.render(financial_prompt.content, test_context)
        
        # Проверка, что все переменные были заменены
        assert "{{financial_data}}" not in rendered_prompt
        assert "Revenue: $1M, Expenses: $800K, Profit: $200K" in rendered_prompt
        
        # Проверка структуры ожидаемого ответа
        assert financial_prompt.expected_response_schema is not None
```

### 2. A/B тестирование

Для оценки эффективности новых промтов используйте A/B тестирование:

```python
# ab_testing_example.py
import asyncio
from application.factories.agent_factory import AgentFactory
from domain.value_objects.domain_type import DomainType

async def ab_test_prompts():
    """A/B тестирование двух версий промтов"""
    
    # Создание агентов с разными версиями промтов
    agent_v1 = await AgentFactory().create_agent(
        agent_type="composable",
        domain=DomainType.CUSTOM_TASKS
    )
    
    agent_v2 = await AgentFactory().create_agent(
        agent_type="composable",
        domain=DomainType.CUSTOM_TASKS
    )
    
    # Подготовка тестового контекста
    test_context = {
        "task_description": "Analyze quarterly sales data",
        "data": "Q4 sales: $1.2M, Q3 sales: $900K, target: $1M",
        "audience": "Sales team"
    }
    
    # Выполнение задачи с первой версией
    result_v1 = await agent_v1.execute_task(
        task_description="Generate sales analysis report",
        context=test_context
    )
    
    # Выполнение задачи со второй версией
    result_v2 = await agent_v2.execute_task(
        task_description="Generate sales analysis report",
        context=test_context
    )
    
    # Сравнение результатов
    print("Результаты A/B тестирования:")
    print(f"Версия 1 - Время выполнения: {result_v1.get('execution_time', 'N/A')}")
    print(f"Версия 2 - Время выполнения: {result_v2.get('execution_time', 'N/A')}")
    print(f"Версия 1 - Качество оценки: {evaluate_quality(result_v1)}")
    print(f"Версия 2 - Качество оценки: {evaluate_quality(result_v2)}")
    
    return result_v1, result_v2

def evaluate_quality(result):
    """Оценка качества результата"""
    # Реализация оценки качества (например, по длине, структуре, ключевым словам)
    pass
```

## Лучшие практики

### 1. Документирование изменений

Для каждого нового промта или изменения документируйте:

- Цель изменения
- Описание изменений
- Влияние на существующую функциональность
- Результаты тестирования

### 2. Итеративное улучшение

- Начинайте с простых версий промтов
- Постепенно усложняйте структуру
- Регулярно пересматривайте эффективность
- Обновляйте промты на основе обратной связи

### 3. Резервные стратегии

Предусмотрите резервные стратегии на случай проблем:

```python
# fallback_strategies.py
class PromptWithFallback:
    """Промт с резервной стратегией"""
    
    def __init__(self, primary_prompt, fallback_prompts=None):
        self.primary_prompt = primary_prompt
        self.fallback_prompts = fallback_prompts or []
    
    async def execute_with_fallback(self, context):
        """Выполнение с резервной стратегией"""
        prompts_to_try = [self.primary_prompt] + self.fallback_prompts
        
        for prompt in prompts_to_try:
            try:
                # Попытка выполнения с текущим промтом
                result = await self.execute_prompt(prompt, context)
                if self.validate_result(result):
                    return result
            except Exception as e:
                print(f"Ошибка с промтом {prompt.id}: {e}")
                continue
        
        # Если все промты не сработали, возвращаем стандартный ответ
        return self.get_standard_response(context)
    
    def validate_result(self, result):
        """Проверка корректности результата"""
        # Реализация валидации результата
        pass
```

## Интеграция с системой

### 1. Регистрация новых промтов

Для интеграции новых промтов в систему:

1. Поместите файлы промтов в соответствующую директорию
2. Убедитесь, что структура соответствует требованиям
3. Протестируйте загрузку через `PromptLoader`
4. Обновите документацию

### 2. Конфигурация

При необходимости создайте конфигурацию для новых промтов:

```yaml
# config/custom_prompts.yaml
custom_prompts:
  enabled: true
  domains:
    - custom_tasks
    - financial_analysis
  default_timeout: 30
  validation_enabled: true
  cache_settings:
    ttl: 3600
    enabled: true
```

## Мониторинг и анализ

### 1. Логирование использования

Система должна логировать использование пользовательских промтов:

```python
# logging_example.py
import logging

logger = logging.getLogger(__name__)

class CustomPromptLogger:
    """Логгер использования пользовательских промтов"""
    
    def log_prompt_usage(self, prompt_id, context, result, execution_time):
        """Логирование использования промта"""
        logger.info(
            f"Prompt {prompt_id} used with context keys: {list(context.keys())}, "
            f"execution time: {execution_time}s, result length: {len(str(result)) if result else 0}"
        )
    
    def log_prompt_error(self, prompt_id, context, error):
        """Логирование ошибок промта"""
        logger.error(
            f"Error in prompt {prompt_id}: {str(error)}, context: {context}",
            exc_info=True
        )
```

### 2. Метрики эффективности

Отслеживайте метрики эффективности пользовательских промтов:

- Время выполнения
- Успешность выполнения
- Качество результатов
- Частота использования

## Примеры специфических задач

### 1. Промт для юридического анализа

```markdown
---
provider: openai
role: system
status: draft
variables:
  - name: legal_document
    type: string
    required: true
    description: "Юридический документ для анализа"
  - name: jurisdiction
    type: string
    required: true
    description: "Юрисдикция"
  - name: document_type
    type: string
    required: false
    description: "Тип документа"
expected_response:
  type: object
  properties:
    compliance_check:
      type: object
    risk_factors:
      type: array
      items:
        type: string
    recommendations:
      type: array
      items:
        type: string
---

# Инструкции для юридического анализа

Ты являешься сертифицированным юристом. При анализе юридических документов следуй следующим принципам:

1. Строго придерживайся норм законодательства указанной юрисдикции
2. Идентифицируй потенциальные правовые риски
3. Указывай конкретные статьи и положения законов
4. Формулируй практические рекомендации по устранению рисков

## Юрисдикция
{{jurisdiction}}

## Тип документа
{% if document_type %}{{document_type}}{% else %}Неопределен{% endif %}

Проанализируй предоставленный юридический документ и предоставь структурированный анализ.
```

### 2. Промт для медицинского анализа

```markdown
---
provider: openai
role: system
status: draft
variables:
  - name: medical_data
    type: string
    required: true
    description: "Медицинские данные пациента"
  - name: symptoms
    type: array
    required: true
    description: "Симптомы пациента"
  - name: age_group
    type: string
    required: false
    description: "Возрастная группа"
expected_response:
  type: object
  properties:
    preliminary_assessment:
      type: string
    recommended_tests:
      type: array
      items:
        type: string
    urgency_level:
      type: string
---

# Инструкции для медицинского анализа

Ты являешься квалифицированным врачом. При анализе медицинских данных следуй следующим принципам:

1. Оценивай данные на основе клинических протоколов
2. Учитывай возрастные особенности пациента
3. Определяй приоритетность симптомов
4. Рекомендуй соответствующие диагностические процедуры

## Возрастная группа
{% if age_group %}{{age_group}}{% else %}Взрослый{% endif %}

## Симптомы
{% for symptom in symptoms %}
- {{symptom}}
{% endfor %}

Проанализируй предоставленные медицинские данные и симптомы.
```

Эти примеры показывают, как можно адаптировать систему промтов под специфические области знаний и требования.