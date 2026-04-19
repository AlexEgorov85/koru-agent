# E2E Тестирование Агента

Полноценные End-to-End тесты агента с реальным контекстом и инфраструктурой.

## Отличия от других типов тестов

| Тип тестов | Инфраструктура | LLM | БД | Промпты | Сервисы |
|------------|----------------|-----|----|---------|---------|
| **Unit** | Fake/Mock | Mock | Mock | Mock | Mock |
| **Integration** | Частично реальная | Mock/Real | Real | Real | Real |
| **E2E** | **Полностью реальная** | Mock | **Real** | **Real** | **Real** |

## Что проверяют E2E тесты

1. **Реальная инициализация InfrastructureContext**
   - Подключение к PostgreSQL
   - Векторное хранилище (FAISS)
   - Шина событий (EventBus)
   - Логирование
   - Хранилища промптов и контрактов

2. **Реальная инициализация ApplicationContext**
   - Загрузка промптов из `data/prompts/`
   - Загрузка контрактов из `data/contracts/`
   - Создание сервисов через ComponentFactory
   - Настройка паттернов поведения

3. **Полный цикл работы агента**
   - ReAct цикл (Thought → Action → Observation)
   - Генерация SQL через LLM
   - Выполнение запросов в БД
   - Анализ результатов
   - Формирование финального ответа

4. **Обработка ошибок**
   - Recovery механизмы
   - Fallback стратегии
   - Ограничение шагов (max_steps)

## Запуск тестов

### Все E2E тесты
```bash
pytest tests/e2e/test_agent_e2e.py -v -s
```

### Конкретный класс тестов
```bash
# Тесты инфраструктуры
pytest tests/e2e/test_agent_e2e.py::TestInfrastructureInitialization -v -s

# Тесты приложения
pytest tests/e2e/test_agent_e2e.py::TestApplicationInitialization -v -s

# Сценарии работы агента
pytest tests/e2e/test_agent_e2e.py::TestAgentScenarios -v -s

# Паттерны и навыки
pytest tests/e2e/test_agent_e2e.py::TestPatternsAndSkills -v -s

# Обработка ошибок
pytest tests/e2e/test_agent_e2e.py::TestErrorHandling -v -s
```

### Конкретный тест
```bash
pytest tests/e2e/test_agent_e2e.py::TestAgentScenarios::test_success_scenario -v -s
```

## Архитектура тестов

### Fixtures

#### `e2e_config`
Конфигурация для E2E тестов. Использует prod профиль для загрузки реальных промптов и контрактов.

#### `scenario_mock_llm`
MockLLM с поддержкой сценариев. Предопределённые ответы для различных ситуаций:
- `success_with_data` - успешный запрос с данными
- `empty_results` - пустые результаты из БД
- `quick_stop` - быстрая остановка (stop_condition=True)
- `multi_step` - многошаговый ReAct цикл
- `error_recovery` - восстановление после ошибок

#### `real_infrastructure`
Реальный InfrastructureContext со всеми сервисами:
- Инициализирует БД, вектор, шину событий, логирование
- Заменяет LLM на MockLLM (для детерминированности)
- Сохраняет все остальные реальные ресурсы

#### `real_application_context`
Реальный ApplicationContext:
- Загружает промпты и контракты через discovery
- Создаёт сервисы через ComponentFactory
- Настраивает паттерны поведения

### Сценарии тестирования

#### 1. Успешный сценарий (`test_success_scenario`)
**Цель**: Проверить полный цикл работы агента

**Шаги**:
1. Агент получает цель
2. Генерирует ReasoningResult с решением
3. Генерирует SQL запрос
4. Выполняет запрос в БД
5. Формирует финальный ответ

**Ожидания**:
- Агент делает 1-3 шага
- SQL выполняется успешно
- Возвращается ExecutionResult с данными

#### 2. Пустые результаты (`test_empty_results_scenario`)
**Цель**: Проверить реакцию на отсутствие данных

**Ожидания**:
- Агент не уходит в бесконечный цикл
- Формируется корректный ответ пользователю

#### 3. Быстрая остановка (`test_quick_stop_scenario`)
**Цель**: Проверить stop_condition=True

**Ожидания**:
- Агент останавливается сразу
- Не выполняет лишних шагов

#### 4. Ограничение шагов (`test_max_steps_limit`)
**Цель**: Проверить max_steps

**Ожидания**:
- Агент останавливается при достижении лимита
- Корректно сообщает о причине остановки

#### 5. Восстановление после ошибок (`test_error_recovery`)
**Цель**: Проверить recovery механизмы

**Ожидания**:
- Агент пытается восстановить ошибку
- Использует fallback стратегии
- Не падает критически

## Добавление новых сценариев

### 1. Добавить сценарий в MockLLM

```python
mock.register_scenario("my_scenario", {
    " ReasoningResult": '{"stop_condition": false, "decision": {...}}',
    "SQLGenerationOutput": '{"generated_sql": "SELECT ..."}',
    "final_answer.generate": "Ответ",
})
```

### 2. Создать тест

```python
@pytest.mark.asyncio
async def test_my_scenario(
    self,
    real_application_context,
    scenario_mock_llm
):
    scenario_mock_llm.set_scenario("my_scenario")
    
    runtime = AgentRuntime(
        application_context=real_application_context,
        goal="Моя цель",
        max_steps=5,
        correlation_id="test-my-scenario-001",
        agent_id="e2e_test_agent"
    )
    
    result = await runtime.run()
    
    assert result is not None
    # Дополнительные проверки
```

## Best Practices

### 1. Используйте сценарии
Не создавайте новые экземпляры MockLLM для каждого теста. Используйте предопределённые сценарии через `scenario_mock_llm.set_scenario()`.

### 2. Сбрасывайте состояние
Вызывайте `scenario_mock_llm.reset()` перед каждым тестом для очистки истории вызовов.

### 3. Логируйте ключевые моменты
Используйте logger для отладки:
```python
logger.info("=" * 60)
logger.info("Тест: Название теста")
logger.info("=" * 60)
```

### 4. Проверяйте метрики
Используйте metadata результата для проверок:
```python
steps = result.metadata.get('total_steps', 0)
assert steps <= max_expected_steps
```

### 5. Изолируйте тесты
Каждый тест должен быть независимым. Не полагайтесь на состояние от предыдущих тестов.

## Troubleshooting

### Ошибка: "ApplicationContext не удалось инициализировать"

**Причина**: Компонент не найден или ошибка при создании сервиса.

**Решение**:
1. Проверьте логи component_factory
2. Убедитесь что промпты и контракты существуют
3. Проверьте зависимости компонентов

### Ошибка: "Нет подключенных БД"

**Причина**: PostgreSQL недоступен или неверная конфигурация.

**Решение**:
1. Проверьте подключение к БД
2. Убедитесь что переменные окружения настроены
3. Проверьте логи InfrastructureContext

### Тесты выполняются медленно

**Причина**: Реальная инициализация инфраструктуры занимает время.

**Решение**:
1. Используйте `-k` для запуска конкретных тестов
2. Кэшируйте fixtures через `scope="module"`
3. Рассмотрите возможность использования Testcontainers для изоляции

## Сравнение с другими тестами

### Integration тесты (`tests/integration/`)
- Быстрее (меньше инициализации)
- Мокают больше компонентов
- Хороши для отладки конкретной функциональности

### E2E тесты (`tests/e2e/`)
- Медленнее (полная инициализация)
- Минимум моков (только LLM)
- Хороши для проверки полной интеграции
- Ближе к продакшену

## Рекомендации

1. **Разработка**: Используйте integration тесты для быстрой обратной связи
2. **CI/CD**: Запускайте E2E тесты перед деплоем
3. **Регрессия**: E2E тесты для критических сценариев
4. **Отладка**: Integration тесты для локализации проблем

## Метки pytest

Используйте метки для категоризации:
```bash
# Только быстрые тесты
pytest tests/e2e/ -m "not slow"

# Только тесты инфраструктуры
pytest tests/e2e/ -m "infrastructure"

# Только сценарии агента
pytest tests/e2e/ -m "agent"
```

Для добавления меток украсьте тесты:
```python
@pytest.mark.slow
@pytest.mark.agent
@pytest.mark.asyncio
async def test_example(...):
    ...
```
