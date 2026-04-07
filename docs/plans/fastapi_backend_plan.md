# План: FastAPI Backend + Streamlit UI + Admin Panel

## Переиспользование существующего в `web_ui/`

| Компонент | Файл | Что переиспользовать |
|-----------|------|---------------------|
| Инициализация контекстов | `agent_holder.py:70-95` | `init_contexts()` — полностью |
| Подписка на EventBus | `agent_holder.py:98-180` | Логика подписки — для WebSocket |
| Управление системой | `agent_holder.py:182-205` | `shutdown_contexts()` |
| UI чата | `app.py:100-385` | Визуальная часть, стили |
| Управление агентом | `app.py:387-622` | Кнопки старт/стоп, мониторинг |
| Системная инфа | `agent_holder.py:230-242` | `get_system_info()` |

---

## Этап 1: FastAPI Backend (`backend/`)

### 1.1 Структура директории
```
backend/
├── main.py           # FastAPI + lifespan
├── requirements.txt  # fastapi, uvicorn, pydantic
└── .env              # API_KEY, PORT
```

### 1.2 backend/main.py

**Lifespan** — инициализация контекстов один раз при старте:
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    state = AppState()
    config = get_config(profile="prod", data_dir="data")
    state.infra = InfrastructureContext(config)
    await state.infra.initialize()
    state.app_ctx = ApplicationContext(state.infra, config, "prod")
    await state.app_ctx.initialize()
    state.factory = AgentFactory(state.app_ctx)
    app.state.core = state
    yield
    await state.infra.shutdown()
```

**Эндпоинты**:
- `POST /api/v1/chat` — создать агента, выполнить goal, вернуть результат
- `GET /api/v1/admin/health` — статус компонентов (использует `get_system_info()`)
- `POST /api/v1/admin/reload` — перезагрузка промптов/контрактов
- `GET /api/v1/admin/prompts` — список промптов
- `WS /ws/events/{session_id}` — стриминг событий из EventBus

**Аутентификация**:
- `HTTPBearer` для `/api/v1/admin/*`
- API key из `.env`

---

## Этап 2: Streamlit User UI (`frontend/app.py`)

### 2.1 Переиспользовать из `web_ui/app.py`
- Стили (тёмная тема через CSS)
- Логику отображения сообщений (chat style)
- Логику отображения мыслей агента (`thinking_placeholder`)
- Форматирование ответа с деталями (sources, confidence, steps)

### 2.2 Изменить
- Заменить прямые вызовы `AgentFactory` на `requests.post("http://localhost:8000/api/v1/chat")`
- WebSocket клиент для стрима событий вместо `get_logs()` polling
- Сохранение `session_id` в `st.session_state`

### 2.3 Новое
- Автоматическое подключение к бэкенду при запуске (без кнопки "Запустить систему")
- Fallback: если бэкенд недоступен — показать ошибку

---

## Этап 3: Admin Panel (`frontend/admin.py`)

### 3.1 Переиспользовать из `web_ui/app.py:387-622`
- Метрики: Infra/App/Готов (через `/api/v1/admin/health`)
- Кнопки: Перезапуск системы (POST `/api/v1/admin/reload`)
- Отображение компонентов: сервисы, навыки, инструменты, паттерны
- Логи LLM провайдеров и БД

### 3.2 Новое
- Редактирование промптов: GET `/api/v1/admin/prompts` → text_area → POST сохранение
- Просмотр логов: чтение из `logs/sessions/`
- Конфигурация: просмотр версий

---

## Этап 4: Docker Compose

```yaml
services:
  backend:
    build: ./backend
    ports: ["8000:8000"]
    volumes: ["../data:/app/data", "../logs:/app/logs"]
    env_file: [".env"]

  streamlit-ui:
    build: ./frontend
    command: streamlit run app.py
    ports: ["8501:8501"]
    depends_on: [backend]

  streamlit-admin:
    build: ./frontend
    command: streamlit run admin.py
    ports: ["8502:8501"]
    depends_on: [backend]
```

---

## Карта переходов

```
web_ui/                    →   backend/           →   frontend/
────────────────────────────────────────────────────────────────
agent_holder.py:init_contexts  →   main.py:lifespan    →   (удалить)
agent_holder.py:get_system_info →   /admin/health      →   (удалить)
app.py: чат логика           →   /chat               →   app.py (HTTP)
app.py: стиль               →   (WS стриминг)       →   app.py (WS клиент)
app.py: управление          →   /admin/*            →   admin.py
```

---

## Ключевые изменения

| Было | Станет |
|------|--------|
| `web_ui/agent_holder.py` — глобальные переменные | `backend/main.py` — единственный источник контекстов |
| UI напрямую создаёт агентов | UI только шлёт HTTP запросы |
| Polling `get_logs()` | WebSocket стриминг |
| Кнопка "Запустить систему" в UI | Система запущена всегда (в бэкенде) |
| Нет аутентификации | Basic Auth + API Key |

---

## Порядок реализации

1. **Backend** — создать `backend/main.py` с lifespan и эндпоинтами
2. **Frontend App** — адаптировать `web_ui/app.py` для HTTP
3. **Frontend Admin** — создать `admin.py` на основе вкладки "Управление"
4. **Docker** — собрать всё вместе
5. **Удалить** — старое `web_ui/` (после проверки)