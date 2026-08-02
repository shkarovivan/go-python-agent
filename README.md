# Go + Python Agent

Демонстрационный проект полиглотной микросервисной архитектуры: **Go**-сервер
выступает в роли API-шлюза, а **Python** (Flask) — backend-воркером, который
выполняет полезную работу. Сервисы общаются между собой по HTTP+JSON и
поднимаются вместе через Docker Compose.

В качестве «бизнес-логики» Python-воркер при старте загружает **локальную
GGUF LLM-модель** и в `/process` возвращает её ответ на присланный текст.
Запрос несёт флаг `local`, но пока сервис всегда отвечает локальной моделью
(флаг пробрасывается через систему и возвращается обратно — ветвление по
нему в Python пока не реализовано).

## Архитектура

```
Internet ──:80──> [ go-server (:8080) ] ──HTTP──> [ python-worker (:5000, Flask) ]
                     API-шлюз / фасад                  локальная GGUF LLM (llama-cpp-python)
```

- `go-server` слушает порт **8080** внутри контейнера и проброшен наружу на
  хостовый порт **80** (см. `docker-compose.yml`). Сам бизнес-логику не выполняет —
  валидирует запрос и пересылает его в Python-сервис.
- `python-worker` (Flask + gunicorn) слушает **5000**, доступен только внутри
  docker-сети. При старте загружает GGUF-модель (путь из `MODEL_PATH`) и для
  каждого запроса возвращает сгенерированный моделью текст.

## Переменные окружения

| Сервис          | Переменная     | По умолчанию             | Назначение                                        |
|-----------------|----------------|--------------------------|---------------------------------------------------|
| `python-worker` | `MODEL_PATH`   | `/models/model.gguf`     | Путь к GGUF-файлу внутри контейнера               |
| `python-worker` | `MAX_TOKENS`   | `256`                    | Лимит токенов в ответе модели                     |
| `python-worker` | `N_CTX`        | `2048`                   | Размер контекста модели                           |
| `python-worker` | `N_THREADS`    | `0`                      | Потоки CPU (`0` = авто, все физические ядра)      |
| `go-server`     | `PYTHON_SERVICE_URL` | `http://python-worker:5000/process` | Адрес Python-сервиса |

## Эндпоинты

| Метод | Путь       | Тело                              | Ответ                              |
|-------|------------|-----------------------------------|------------------------------------|
| GET   | `/health`  | —                                 | `{"status":"ok","model_loaded":true}` |
| POST  | `/process` | `{"text":"hello","local":true}`   | `{"result":"<ответ модели>","local":true}` |

## Запуск

### Через Docker Compose (основной способ)

1. Положите GGUF-модель в `models/model.gguf` (см. [models/README.md](models/README.md)).
2. Соберите и запустите сервисы:

```bash
docker compose up -d --build
```

> Первая сборка долгая: собирается `llama-cpp-python` (нужны build-зависимости
> из Dockerfile). Последующие — быстро.

Проверка:

```bash
curl http://localhost/health
# {"model_loaded":true,"status":"ok"}

curl -X POST http://localhost/process \
  -H 'Content-Type: application/json' \
  -d '{"text":"Расскажи короткую шутку","local":true}'
# {"local":true,"result":"<ответ модели>"}
```

Остановка: `docker compose down`

### Локально без Docker

Python-воркер (с переменной `MODEL_PATH`, иначе `/process` вернёт 503):

```bash
cd python-worker
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
MODEL_PATH=/абсолютный/путь/к/model.gguf flask --app app run --port 5000
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
├── models/                   # GGUF-модели (монтируются в python-worker)
├── go-server/
│   ├── main.go               # Go HTTP-сервер (API-шлюз)
│   ├── go.mod
│   └── Dockerfile
└── python-worker/
    ├── app.py                # Flask: загрузка модели + /process
    ├── requirements.txt
    └── Dockerfile
```

## Деплой на сервер

1. Установить Docker: `curl -fsSL https://get.docker.com | sh`.
2. Открыть хостовый порт **80** (security group / firewall).
3. Скопировать проект на сервер и положить GGUF-модель в `models/model.gguf`.
4. Запустить `docker compose up -d --build`.
5. Проверить снаружи: `curl http://<IP>/health` (убедиться, что `model_loaded: true`).

> Для production рекомендуется добавить reverse-proxy (nginx/Caddy) с HTTPS
> и закрыть прямой порт, оставив только 80/443.
