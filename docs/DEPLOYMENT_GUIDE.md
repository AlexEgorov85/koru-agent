# 🚀 Руководство по развёртыванию koru-agent

> **Версия:** 5.1.0
> **Дата обновления:** 2026-02-17
> **Статус:** approved
> **Владелец:** @system

---

## 📋 Оглавление

- [Обзор](#-обзор)
- [Требования](#-требования)
- [Установка](#-установка)
- [Конфигурация](#-конфигурация)
- [Запуск](#-запуск)
- [Docker](#-docker)
- [Production](#-production)
- [Мониторинг](#-мониторинг)

---

## 🔍 Обзор

Руководство по развёртыванию koru-agent в различных окружениях.

---

## 📦 Требования

### Минимальные

| Компонент | Требование |
|-----------|------------|
| **CPU** | 4 ядра |
| **RAM** | 8 ГБ |
| **Disk** | 10 ГБ |
| **Python** | 3.10+ |

### Рекомендуемые

| Компонент | Требование |
|-----------|------------|
| **CPU** | 8+ ядер |
| **RAM** | 16+ ГБ |
| **Disk** | 50+ ГБ SSD |
| **GPU** | NVIDIA 8+ ГБ VRAM (опционально) |

---

## 🛠️ Установка

### Клонирование

```bash
git clone <repository_url>
cd koru-agent
```

### Виртуальное окружение

```bash
# Создание
python -m venv venv

# Активация (Linux/macOS)
source venv/bin/activate

# Активация (Windows)
venv\Scripts\activate
```

### Зависимости

```bash
# Базовые
pip install -r requirements.txt

# Для разработки
pip install -r requirements-dev.txt
```

---

## ⚙️ Конфигурация

### Базовая настройка

```bash
# Копирование шаблона
cp .env.example .env

# Редактирование
nano .env
```

### Пример .env

```bash
# Профиль
AGENT_PROFILE=prod

# База данных
DB_HOST=localhost
DB_PORT=5432
DB_NAME=agent_db
DB_USER=agent
DB_PASSWORD=secure_password

# LLM
LLM_PROVIDER_TYPE=vllm
LLM_MODEL=mistral-7b-instruct-v0.2

# Логирование
LOG_LEVEL=INFO
LOG_DIR=/var/log/agent
```

### Валидация

```bash
python scripts/validate_registry.py
python scripts/validate_all_manifests.py
```

---

## ▶️ Запуск

### Локальный

```bash
# Базовый
python main.py

# С вопросом
python main.py "Проанализируй рынок ИИ"

# С профилем
python main.py --profile=dev

# С отладкой
python main.py --debug
```

### Тесты

```bash
# Все тесты
python -m pytest tests/ -v

# С покрытием
python -m pytest tests/ --cov=core
```

---

## 🐳 Docker

### Сборка образа

```bash
docker build -t koru-agent:latest .
```

### Запуск контейнера

```bash
docker run -it --rm \
  -e AGENT_PROFILE=prod \
  -e DB_HOST=db \
  -e DB_PASSWORD=secret \
  koru-agent:latest
```

### Docker Compose

```yaml
# docker-compose.yaml
version: '3.8'

services:
  agent:
    build: .
    environment:
      - AGENT_PROFILE=prod
      - DB_HOST=db
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
    depends_on:
      - db
  
  db:
    image: postgres:15
    environment:
      - POSTGRES_DB=agent_db
      - POSTGRES_PASSWORD=${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

```bash
# Запуск
docker-compose up -d

# Логи
docker-compose logs -f agent
```

---

## 🌐 Production

### Подготовка сервера (Ubuntu)

```bash
# Обновление
sudo apt update && sudo apt upgrade -y

# Зависимости
sudo apt install -y python3.10 python3.10-venv python3-pip
sudo apt install -y postgresql-client nginx supervisor

# Пользователь
sudo useradd -m -s /bin/bash agent
```

### Установка приложения

```bash
# Клонирование
git clone <repository_url> ~/koru-agent
cd ~/koru-agent

# Виртуальное окружение
python3 -m venv venv
source venv/bin/activate

# Зависимости
pip install -r requirements-prod.txt
```

### Настройка supervisor

```ini
# /etc/supervisor/conf.d/agent.conf
[program:agent]
command=/home/agent/koru-agent/venv/bin/python /home/agent/koru-agent/main.py
directory=/home/agent/koru-agent
user=agent
autostart=true
autorestart=true
stdout_logfile=/var/log/agent/agent.out.log
```

```bash
# Перезапуск
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start agent
```

---

## 📊 Мониторинг

### Логирование

```bash
# Просмотр логов
tail -f /var/log/agent/agent.log

# Поиск ошибок
grep -i error /var/log/agent/agent.log
```

### Health checks

```python
@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": "5.1.0"}
```

### Метрики

```python
from prometheus_client import Counter, Histogram

AGENT_STEPS = Counter('agent_steps_total', 'Total steps', ['capability'])
STEP_DURATION = Histogram('agent_step_duration_seconds', 'Step duration')
```

---

## 🔧 Troubleshooting

| Проблема | Решение |
|----------|---------|
| Ошибка подключения к БД | Проверьте переменные DB_* |
| Модель LLM не загружается | Проверьте путь и память |
| Агент не отвечает | Проверьте логи |
| Высокое потребление памяти | Уменьшите n_ctx |

### Диагностика

```bash
# Статус
sudo supervisorctl status agent

# Логи
tail -f /var/log/agent/agent.log

# Проверка БД
psql -h localhost -U agent -d agent_db -c "SELECT 1"
```

---

## 🔗 Ссылки

- [Конфигурация](./CONFIGURATION_MANUAL.md)
- [Устранение неполадок](./TROUBLESHOOTING.md)
- [main.py](../main.py)

---

*Документ автоматически сгенерирован. Не редактируйте вручную.*
