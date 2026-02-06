# Установка Composable AI Agent Framework

В этом руководстве описан процесс установки и начальной настройки Composable AI Agent Framework. Следуйте инструкциям для быстрого старта работы с фреймворком.

## Требования

Перед установкой убедитесь, что в вашей системе установлены следующие компоненты:

### Минимальные требования
- Python 3.9 или выше
- pip (менеджер пакетов Python)
- Git (для клонирования репозитория)

### Рекомендуемые требования
- Python 3.10 или выше
- Виртуальное окружение (virtualenv или conda)
- Текстовый редактор или IDE с поддержкой Python

## Установка

### 1. Клонирование репозитория

```bash
git clone https://github.com/your-repo/agent_code.git
cd agent_code
```

### 2. Создание виртуального окружения (рекомендуется)

```bash
# Создание виртуального окружения
python -m venv venv

# Активация виртуального окружения
# На Windows:
venv\Scripts\activate
# На macOS/Linux:
source venv/bin/activate
```

### 3. Установка зависимостей

```bash
pip install -r requirements.txt
```

Файл `requirements.txt` содержит все необходимые зависимости:

```
# Основные зависимости для AST парсинга
tree-sitter==0.21.0
tree-sitter-languages==1.9.1
pydantic>=2.5.0

# Зависимости для SQL
sqlparse>=0.4.4
```

### 4. Настройка конфигурации

Создайте файл конфигурации `config.yaml` в корне проекта:

```yaml
# config.yaml
agent:
  name: "default_agent"
  max_iterations: 50
  timeout: 300
  enable_logging: true
  max_concurrent_actions: 5
  memory_limit: "1GB"
  retry_attempts: 3

llm:
  provider: "openai"
  model: "gpt-4"
  api_key: "${OPENAI_API_KEY}"  # Будет загружен из переменной окружения
  temperature: 0.7
  max_tokens: 2048
  base_url: null

prompts:
  storage_path: "./prompts"
  cache_enabled: true
  cache_ttl: 3600
  validation_enabled: true

debug_mode: false
log_level: "INFO"
enable_monitoring: true
```

### 5. Установка переменных окружения

Создайте файл `.env` в корне проекта для хранения конфиденциальных данных:

```bash
# .env
OPENAI_API_KEY=your_openai_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here
```

Загрузите переменные окружения:

```bash
# На большинстве систем Python автоматически загружает .env файлы
# или используйте python-dotenv:
pip install python-dotenv
```

## Проверка установки

После установки вы можете проверить корректность установки, запустив один из примеров:

```bash
python -m examples.composable_agent_example
```

Или выполнить тесты:

```bash
# Запуск всех тестов
pytest

# Запуск тестов с показом подробного вывода
pytest -v

# Запуск только модульных тестов
pytest tests/unit/
```

## Быстрый старт

### Простой пример использования

Создайте файл `quick_start.py`:

```python
# quick_start.py
import asyncio
from application.factories.agent_factory import AgentFactory
from domain.value_objects.domain_type import DomainType

async def main():
    # Создание фабрики агентов
    agent_factory = AgentFactory()
    
    # Создание агента для анализа кода
    agent = await agent_factory.create_agent(
        agent_type="composable",
        domain=DomainType.CODE_ANALYSIS
    )
    
    # Определение задачи
    task_description = "Проанализируй этот Python код на наличие уязвимостей"
    
    # Выполнение задачи
    result = await agent.execute_task(task_description)
    
    print(f"Результат выполнения задачи: {result}")

if __name__ == "__main__":
    asyncio.run(main())
```

Запустите пример:

```bash
python quick_start.py
```

## Альтернативные методы установки

### Установка через pip (если фреймворк опубликован как пакет)

```bash
pip install composable-ai-agent-framework
```

### Установка с помощью Docker

Если доступен Dockerfile:

```bash
# Сборка образа
docker build -t composable-agent .

# Запуск контейнера
docker run -it composable-agent
```

## Устранение неполадок

### Общие проблемы и решения

#### 1. Ошибки при установке tree-sitter

Если возникают ошибки при установке tree-sitter, попробуйте:

```bash
pip install --upgrade pip setuptools wheel
pip install tree-sitter
```

#### 2. Ошибки с pydantic

Убедитесь, что у вас установлена совместимая версия:

```bash
pip install "pydantic>=2.5.0,<3.0.0"
```

#### 3. Проблемы с виртуальным окружением

Если возникают проблемы с виртуальным окружением:

```bash
# Удалите старое окружение
rm -rf venv  # или rmdir /s venv на Windows

# Создайте новое
python -m venv venv
source venv/bin/activate  # или venv\Scripts\activate на Windows

# Установите зависимости
pip install --upgrade pip
pip install -r requirements.txt
```

#### 4. Проблемы с API ключами

Убедитесь, что переменные окружения правильно установлены:

```python
import os
print(os.getenv("OPENAI_API_KEY"))  # Должно вывести ваш API ключ
```

## Дальнейшие шаги

После успешной установки рекомендуется:

1. Ознакомиться с [руководством по быстрому старту](./quickstart.md)
2. Изучить [доступные примеры](../examples/overview.md)
3. Познакомиться с [архитектурой фреймворка](../architecture/overview.md)
4. Прочитать о [паттернах мышления](../concepts/thinking_patterns.md)
5. Изучить [систему промтов](../prompts/overview.md)

## Поддержка

Если у вас возникли проблемы с установкой, вы можете:

- Проверить [FAQ](../faq.md) (если доступно)
- Создать issue в репозитории GitHub
- Обратиться к документации по конкретным компонентам
- Посмотреть примеры в директории `examples/`