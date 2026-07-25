# Go + Python Agent

Демонстрационный проект полиглотной микросервисной архитектуры: **Go**-сервер
выступает в роли API-шлюза, а **Python** (Flask) — backend-воркером, который
выполняет полезную работу. Сервисы общаются между собой по HTTP+JSON и
поднимаются вместе через Docker Compose.

## Архитектура

```
Internet ──:80──> [ go-server (:8080) ] ──HTTP──> [ python-worker (:5000, Flask) ]
                     API-шлюз / фасад                  бизнес-логика
```

- `go-server` слушает порт **8080** внутри контейнера и проброшен наружу на
  хостовый порт **80** (см. `docker-compose.yml`). Сам бизнес-логику не выполняет —
  валидирует запрос и пересылает его в Python-сервис.
- `python-worker` (Flask + gunicorn) слушает **5000**, доступен только внутри
  docker-сети. Принимает поле `text` и возвращает результат.

## Эндпоинты

| Метод | Путь       | Тело                  | Ответ                       |
|-------|------------|-----------------------|-----------------------------|
| GET   | `/health`  | —                     | `{"status":"ok"}`           |
| POST  | `/process` | `{"text":"hello "}`   | `{"result":"hello hello "}` |

> Логика `text * 2` в Python — заглушка-плейсхолдер: для строк это повторение
> (`"ab"` → `"abab"`). Замените её на реальную обработку в `python-worker/app.py`.

## Запуск

### Через Docker Compose (основной способ)

```bash
docker compose up -d --build
```

Проверка:

```bash
curl http://localhost/health
# {"status":"ok"}

curl -X POST http://localhost/process \
  -H 'Content-Type: application/json' \
  -d '{"text":"hello "}'
# {"result":"hello hello "}
```

Остановка: `docker compose down`

### Локально без Docker

Python-воркер:

```bash
cd python-worker
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
flask --app app run --port 5000
```

Go-сервер (в другом терминале, направляем на локальный Flask):

```bash
cd go-server
PYTHON_SERVICE_URL=http://localhost:5000/process go run main.go
```

Запросы уходят на `http://localhost:8080`.

## Структура проекта

```
.
├── docker-compose.yml        # оркестрация двух сервисов
├── go-server/
│   ├── main.go               # Go HTTP-сервер (API-шлюз)
│   ├── go.mod
│   └── Dockerfile
└── python-worker/
    ├── app.py                # Flask-приложение (бизнес-логика)
    ├── requirements.txt
    └── Dockerfile
```

## Деплой на сервер

1. Установить Docker: `curl -fsSL https://get.docker.com | sh`.
2. Открыть хостовый порт **80** (security group / firewall).
3. Скопировать проект на сервер и запустить `docker compose up -d --build`.
4. Проверить снаружи: `curl http://<IP>/health`.

> Для production рекомендуется добавить reverse-proxy (nginx/Caddy) с HTTPS
> и закрыть прямой порт, оставив только 80/443.
