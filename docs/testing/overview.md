# Обзор системы тестирования и бенчмарков

Система тестирования и бенчмарков Koru AI Agent Framework обеспечивает всестороннюю проверку корректности, производительности и надежности компонентов фреймворка. Система включает в себя модульные, интеграционные и системные тесты, а также комплекс бенчмарков для оценки производительности.

## Определение

Система тестирования - это совокупность инструментов, фреймворков и методологий, предназначенных для проверки корректности работы компонентов фреймворка. Бенчмарки - это стандартизированные тесты, предназначенные для измерения производительности и сравнения различных реализаций или конфигураций.

## Архитектура системы тестирования

Система тестирования включает следующие уровни:

### 1. Модульные тесты (Unit Tests)
- Проверяют отдельные функции и классы
- Используют mock-объекты для изоляции тестируемого кода
- Быстро выполняются и обеспечивают покрытие логики

### 2. Интеграционные тесты (Integration Tests)
- Проверяют взаимодействие между компонентами
- Тестируют интеграцию с внешними системами
- Используют тестовые двойники или песочницы

### 3. Системные тесты (System Tests)
- Проверяют работу системы в целом
- Тестируют сквозные сценарии использования
- Оценивают соответствие требованиям

### 4. Бенчмарки (Benchmarks)
- Измеряют производительность компонентов
- Сравнивают различные реализации
- Оценивают масштабируемость и надежность

## Структура тестов

Тесты организованы в соответствии с архитектурой фреймворка:

```
tests/
├── unit/                    # Модульные тесты
│   ├── domain/             # Тесты слоя Domain
│   ├── application/        # Тесты слоя Application
│   └── infrastructure/     # Тесты слоя Infrastructure
├── integration/            # Интеграционные тесты
│   ├── repositories/       # Тесты репозиториев
│   ├── services/           # Тесты сервисов
│   └── adapters/           # Тесты адаптеров
├── system/                 # Системные тесты
│   └── end_to_end/         # Сквозные тесты
├── benchmarks/             # Бенчмарки
│   ├── performance/        # Тесты производительности
│   └── scalability/        # Тесты масштабируемости
├── fixtures/               # Тестовые фикстуры
├── conftest.py             # Общие настройки pytest
└── support/                # Вспомогательные утилиты для тестирования
```

## Модульные тесты

Модульные тесты проверяют отдельные компоненты системы:

```python
# tests/unit/domain/test_agent_state.py
import pytest
from domain.models.agent.agent_state import AgentState

class TestAgentState:
    def test_initial_state(self):
        """Тест начального состояния агента"""
        state = AgentState()
        
        assert state.step == 0
        assert state.error_count == 0
        assert state.no_progress_steps == 0
        assert state.finished is False
        assert state.metrics == {}
        assert state.history == []
    
    def test_register_error(self):
        """Тест регистрации ошибки"""
        state = AgentState()
        
        initial_error_count = state.error_count
        state.register_error()
        
        assert state.error_count == initial_error_count + 1
    
    def test_register_progress(self):
        """Тест регистрации прогресса"""
        state = AgentState()
        state.no_progress_steps = 5  # Имитация отсутствия прогресса
        
        state.register_progress(True)  # Есть прогресс
        
        assert state.no_progress_steps == 0
    
    def test_register_no_progress(self):
        """Тест регистрации отсутствия прогресса"""
        state = AgentState()
        state.no_progress_steps = 3  # Имитация предыдущего состояния
        
        state.register_progress(False)  # Нет прогресса
        
        assert state.no_progress_steps == 4
    
    def test_complete(self):
        """Тест завершения выполнения"""
        state = AgentState()
        
        state.complete()
        
        assert state.finished is True
```

## Интеграционные тесты

Интеграционные тесты проверяют взаимодействие между компонентами:

```python
# tests/integration/services/test_prompt_loader.py
import pytest
from pathlib import Path
import tempfile
import yaml
from application.services.prompt_loader import PromptLoader
from domain.value_objects.domain_type import DomainType
from domain.value_objects.provider_type import LLMProviderType
from domain.models.prompt.prompt_version import PromptRole

class TestPromptLoaderIntegration:
    @pytest.fixture
    def temp_prompt_dir(self):
        """Создать временную директорию с промтами для тестов"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Создать структуру директорий
            domain_dir = Path(temp_dir) / "test_domain"
            capability_dir = domain_dir / "test_capability"
            system_role_dir = capability_dir / "system"
            system_role_dir.mkdir(parents=True)
            
            # Создать файл промта
            prompt_file = system_role_dir / "v1.0.0.md"
            frontmatter = {
                "provider": "openai",
                "role": "system",
                "status": "active",
                "variables": [
                    {
                        "name": "task_description",
                        "type": "string",
                        "required": True,
                        "description": "Описание задачи"
                    }
                ]
            }
            
            content = """---
provider: openai
role: system
status: active
variables:
  - name: task_description
    type: string
    required: True
    description: "Описание задачи"
---

# Инструкции для выполнения задачи

Ты помощник в выполнении задачи: {{task_description}}
"""
            
            prompt_file.write_text(content)
            
            yield temp_dir
    
    async def test_load_prompts_from_directory(self, temp_prompt_dir):
        """Тест загрузки промтов из директории"""
        loader = PromptLoader(base_path=str(temp_prompt_dir))
        
        prompts, errors = loader.load_all_prompts()
        
        assert len(errors) == 0
        assert len(prompts) == 1
        
        prompt = prompts[0]
        assert prompt.domain == DomainType("test_domain")
        assert prompt.capability_name == "test_capability"
        assert prompt.role == PromptRole.SYSTEM
        assert prompt.semantic_version == "1.0.0"
        assert prompt.provider_type == LLMProviderType.OPENAI
        assert len(prompt.variables_schema) == 1
        assert prompt.variables_schema[0].name == "task_description"
```

## Бенчмарки

Бенчмарки измеряют производительность компонентов:

```python
# benchmarks/performance/prompt_loading_benchmark.py
import asyncio
import time
from pathlib import Path
import tempfile
from application.services.prompt_loader import PromptLoader

class PromptLoadingBenchmark:
    """Бенчмарк загрузки промтов"""
    
    def __init__(self):
        self.results = {}
    
    def create_test_prompts(self, num_prompts: int, base_path: str):
        """Создать тестовые промты для бенчмарка"""
        base_path = Path(base_path)
        
        for i in range(num_prompts):
            domain_dir = base_path / f"domain_{i}"
            capability_dir = domain_dir / f"capability_{i}"
            system_role_dir = capability_dir / "system"
            system_role_dir.mkdir(parents=True, exist_ok=True)
            
            # Создать файл промта
            prompt_file = system_role_dir / "v1.0.0.md"
            content = f"""---
provider: openai
role: system
status: active
variables:
  - name: task_{i}
    type: string
    required: true
    description: "Задача {i}"
---

# Тестовый промт {i}

Содержимое промта для задачи {{task_{i}}}.
"""
            
            prompt_file.write_text(content)
    
    async def run_benchmark(self, num_prompts_list: list = [10, 50, 100]):
        """Запустить бенчмарк с разным количеством промтов"""
        for num_prompts in num_prompts_list:
            with tempfile.TemporaryDirectory() as temp_dir:
                # Создать тестовые промты
                self.create_test_prompts(num_prompts, temp_dir)
                
                # Замерить время загрузки
                start_time = time.time()
                
                loader = PromptLoader(base_path=temp_dir)
                prompts, errors = loader.load_all_prompts()
                
                end_time = time.time()
                
                loading_time = end_time - start_time
                
                self.results[num_prompts] = {
                    "loading_time": loading_time,
                    "num_loaded_prompts": len(prompts),
                    "num_errors": len(errors),
                    "prompts_per_second": num_prompts / loading_time if loading_time > 0 else 0
                }
        
        return self.results
    
    def print_results(self):
        """Вывести результаты бенчмарка"""
        print("Результаты бенчмарка загрузки промтов:")
        print("-" * 60)
        print(f"{'Кол-во промтов':<15} {'Время загрузки':<15} {'Промтов/сек':<15}")
        print("-" * 60)
        
        for num_prompts, result in self.results.items():
            print(f"{num_prompts:<15} {result['loading_time']:<15.4f} {result['prompts_per_second']:<15.2f}")
```

## Тестовые фикстуры

Фреймворк предоставляет фикстуры для упрощения написания тестов:

```python
# tests/conftest.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from domain.models.agent.agent_state import AgentState
from domain.models.prompt.prompt_version import PromptVersion
from domain.value_objects.domain_type import DomainType
from domain.value_objects.provider_type import LLMProviderType
from domain.models.prompt.prompt_version import PromptRole

@pytest.fixture
def sample_agent_state():
    """Фикстура для тестирования состояния агента"""
    return AgentState(
        step=5,
        error_count=2,
        no_progress_steps=3,
        finished=False,
        metrics={"accuracy": 0.95},
        history=["step1", "step2", "step3"]
    )

@pytest.fixture
def sample_prompt_version():
    """Фикстура для тестирования версии промта"""
    return PromptVersion(
        id="test_prompt_123456",
        semantic_version="1.0.0",
        domain=DomainType.CODE_ANALYSIS,
        provider_type=LLMProviderType.OPENAI,
        capability_name="code_review",
        role=PromptRole.SYSTEM,
        content="# Code Review Instructions\nReview the code...",
        variables_schema=[],
        status="active"
    )

@pytest.fixture
def mock_event_publisher():
    """Фикстура для тестирования публикатора событий"""
    return AsyncMock()

@pytest.fixture
def mock_atomic_action_executor():
    """Фикстура для тестирования исполнителя атомарных действий"""
    executor = AsyncMock()
    executor.execute_action = AsyncMock(return_value={"success": True, "result": "mock_result"})
    return executor
```

## Запуск тестов

Тесты запускаются с использованием pytest с определенными параметрами:

```bash
# Запуск всех тестов
pytest

# Запуск тестов с показом подробного вывода
pytest -v

# Запуск только модульных тестов
pytest tests/unit/

# Запуск тестов с измерением покрытия
pytest --cov=application --cov=domain --cov=infrastructure tests/

# Запуск тестов без медленных тестов
pytest -m "not slow"

# Запуск конкретного теста
pytest tests/unit/domain/test_agent_state.py::TestAgentState::test_initial_state
```

## Запуск бенчмарков

Бенчмарки можно запускать как отдельные скрипты:

```python
# demo/benchmark_demo.py
from benchmarks.performance.prompt_loading_benchmark import PromptLoadingBenchmark

async def run_benchmark_demo():
    """Демонстрация запуска бенчмарка"""
    benchmark = PromptLoadingBenchmark()
    results = await benchmark.run_benchmark([10, 50, 100])
    benchmark.print_results()

if __name__ == "__main__":
    asyncio.run(run_benchmark_demo())
```

## Типы тестов

### 1. Функциональные тесты
- Проверяют корректность реализации требований
- Тестируют API и интерфейсы компонентов
- Проверяют граничные условия и обработку ошибок

### 2. Нагрузочные тесты
- Оценивают производительность системы
- Проверяют поведение под нагрузкой
- Оценивают масштабируемость

### 3. Тесты отказоустойчивости
- Проверяют поведение при сбоях компонентов
- Тестируют механизмы восстановления
- Оценивают надежность системы

### 4. Тесты безопасности
- Проверяют защиту от неправильного использования
- Тестируют валидацию входных данных
- Оценивают изоляцию выполнения

## Практики тестирования

### 1. Тестирование по принципу AAA
- **Arrange** (подготовка): Настройка тестовых данных и окружения
- **Act** (действие): Выполнение тестируемого кода
- **Assert** (проверка): Проверка результата

### 2. Использование фикстур
- Централизованное создание тестовых данных
- Повторное использование тестовых объектов
- Упрощение сопровождения тестов

### 3. Мокирование внешних зависимостей
- Изоляция тестируемого компонента
- Контроль поведения зависимостей
- Ускорение выполнения тестов

### 4. Покрытие кода
- Отслеживание процента покрытия тестами
- Увеличение уверенности в корректности
- Выявление непротестированных участков кода

## Интеграция с CI/CD

Система тестирования интегрирована с процессами CI/CD:

- Автоматический запуск тестов при каждом коммите
- Проверка покрытия кода тестами
- Запуск бенчмарков для оценки производительности
- Блокировка мерджа при падении тестов

## Преимущества системы тестирования

- **Надежность**: Раннее выявление ошибок и регрессий
- **Качество**: Повышение качества кода за счет покрытия тестами
- **Конфиденциальность**: Уверенность в корректности изменений
- **Скорость разработки**: Ускорение процесса разработки за счет автоматизации
- **Документация**: Тесты служат живой документацией для API
- **Стабильность**: Поддержание стабильности системы при изменениях

## Интеграция с другими компонентами

Система тестирования интегрирована с:
- **Системой непрерывной интеграции**: Автоматический запуск тестов
- **Системой мониторинга**: Сравнение производительности с предыдущими версиями
- **Системой логирования**: Сбор информации для отладки тестов
- **Системой конфигурации**: Использование различных конфигураций для тестирования