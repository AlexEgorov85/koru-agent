# Agent_code

Проект представляет собой модульную систему управления искусственным интеллектом с поддержкой плагинов и распределённого выполнения задач. Предоставляет гибкий API для интеграции с внешними системами и LLM.

## 🚀 Особенности
- Модульная архитектура с возможностью расширения возможностей
- Поддержка различных провайдеров LLM (vLLM, llama.cpp)
- Гибкая система конфигурации с профилями среды
- Система управления контекстом выполнения задач
- Автоматический перезапуск при ошибках через политики retry

## 📦 Быстрый старт
### Установка зависимостей
```bash
pip install -r requirements.txt
npm install  # для использования инструментов Node.js (если нужно)
```

### Запуск базового сценария
```bash
python main.py
```

### Пример с конкретным вопросом
```bash
python main.py "Проанализируй рынок искусственного интеллекта"
```

## 🛠️ Примеры использования
```bash
# Режим разработки с отладкой
python main.py "Какие книги написал Пушкин?" --profile=dev --debug

# Ограничение шагов выполнения (3 шага) с сохранением результата в JSON
python main.py "Сравни различные подходы к машинному обучению" --max-steps=3 --output=results.json

# Использование пользовательского конфигурационного файла
python main.py "Проанализируй данные" --config-path=./configs/production.yaml
```

## 🧪 Тестирование
Запуск всех тестов в проекте:
```bash
python -m pytest -v tests/
```

Отдельные тестовые сценарии:
```bash
# Тестирование контекста сессии
python -m pytest tests/test_session_context.py -v

# Тестирование провайдеров баз данных
python -m pytest tests/providers/test_postgres_provider.py -v
```

## 🏗️ Архитектура

### Системный контекст (SystemContext)
```plaintext
SystemContext (Facade)
├── ResourceRegistry - управление ресурсами
├── LifecycleManager - контроль жизненного цикла
├── CapabilityRegistry - реестр возможностей
├── AgentFactory - создание агентов
└── Config - централизованное управление конфигурацией
```

### Контекст выполнения агента (AgentRuntime)
- **think**: Анализ задачи через LLM
- **select capability**: Выбор подходящей возможности
- **describe action**: Формат текстового/JSON описания действия
- **execute_capability**: Выполнение действия через SystemContext

## ⚙️ Конфигурация
Проект использует систему профилей конфигурации YAML:

### Основные файлы конфигурации
- `config/settings.yaml` - базовая конфигурация (разработка)
- `config/settings_prod.yaml` - продакшн конфиг
- `config/settings_test.yaml` - тестовое окружение

### Структура конфигурации
```yaml
profile: "dev"
log_level: "DEBUG"

providers:
  llm:
    provider_type: "vllm"
    model_name: "mistral-7b-instruct-v0.2"
    parameters:
      tensor_parallel_size: 1
      gpu_memory_utilization: 0.9

  database:
    provider_type: "postgres"
    parameters:
      host: "localhost"
      password: "${DB_PASSWORD|default_password}"
```

### Переменные окружения
Поддерживается подстановка значений через переменные среды по формату: `${ENV_VAR|default_value}`

## 📂 Структура проекта
```
agent_code/
├── core/ - ядро системы
├── configs/ - конфигурационные файлы
├── tests/ - тесты
└── models/ - модели данных
```

## 🤝 Вклад в проект
1. Делайте форк репозитория
2. Создайте ветку для своей фичи (`git checkout -b feature/amazing-feature`)
3. Коммитьте изменения (`git commit -m 'Add amazing feature'`)
4. Пушите в репозиторий (`git push origin feature/amazing-feature`)
5. Открывайте Pull Request

## 📜 Лицензия
Распространяется под [MIT лицензией](LICENSE.md).