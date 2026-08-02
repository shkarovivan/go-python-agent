# Модели

Сюда кладётся файл локальной GGUF-модели. По умолчанию `docker-compose.yml`
монтирует эту директорию в контейнер read-only и ждёт файл `model.gguf`
(см. переменную окружения `MODEL_PATH`).

```bash
# Пример: скачать небольшую модель (запускать на хосте, в этой папке)
curl -L -o model.gguf \
  https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/qwen2.5-0-5b-instruct-q8_0.gguf
```

После этого пересобирать образ не нужно — достаточно перезапустить сервис:

```bash
docker compose restart python-worker
```

Проверить, что модель загрузилась:

```bash
curl http://localhost/health   # от go-server
# или напрямую в контейнер: docker exec ... curl localhost:5000/health
# -> {"model_loaded": true, "status": "ok"}
```

Файлы `*.gguf` исключены из git (см. корневой `.gitignore`) — добавьте свой
файл локально и не коммитьте его.
