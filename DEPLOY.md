# Деплой на ВМ (Yandex Cloud)

Подробная инструкция по запуску проекта на удалённой Linux-ВМ со статическим
публичным IP, чтобы сервис был доступен по `curl` из любой точки интернета.

Рассчитано на **чистую ВМ** (без Docker) с **Ubuntu/Debian**. Репозиторий
приватный (`shkarovivan/go-python-agent`), сервис слушает хостовый порт **80**.

Во всех командах замени:
- `<IP>` — публичный статический IP ВМ;
- `<user>` — ssh-пользователь (для Ubuntu-образов Yandex Cloud обычно `ycuser`,
  либо тот, что задан при создании ВМ);
- `<PAT>` — Personal Access Token GitHub для приватного репозитория (шаг 2).

---

## Шаг 1. Открыть порт 80 в Security Group (Yandex Cloud)

Без этого сервис снаружи недоступен — это главное «окно».

1. Консоль Yandex Cloud → **VPC → Группы безопасности**.
2. Выбрать группу, привязанную к ВМ (привязка видна в карточке ВМ → «Группы безопасности»).
3. **Добавить правило → Входящее (Ingress)**:
   - Протокол: `TCP`
   - Порт: `80`
   - Источник: `0.0.0.0/0` (весь интернет; либо свой IP для ограничения).
4. Сохранить.

> Порт 22 (SSH) уже открыт — иначе на ВМ нельзя было бы зайти.

---

## Шаг 2. Получить код проекта на ВМ

Два варианта.

### Вариант A — `git clone` (удобно обновлять через `git pull`)

Создать **Personal Access Token**: GitHub → Settings → Developer settings →
Personal access tokens → **Tokens (classic)** → Generate new → отметить scope
**`repo`** → скопировать токен (это `<PAT>`).

```bash
ssh <user>@<IP>

# если git не установлен:
sudo apt update && sudo apt install -y git

git clone https://github.com/shkarovivan/go-python-agent.git
# Username: shkarovivan
# Password: <ВСТАВЬ PAT>      (символы при вводе не видны — это нормально)
cd go-python-agent
ls -la
```

### Вариант B — `scp` без токенов

На **своей машине**:
```bash
cd /Users/ivan/Documents/GitHub/go-python-agent
tar --exclude='python-worker/venv' --exclude='*.tar' --exclude='.DS_Store' --exclude='.git' -czf /tmp/go-python-agent.tar.gz .
scp /tmp/go-python-agent.tar.gz <user>@<IP>:~/
```
На **ВМ**:
```bash
mkdir -p ~/go-python-agent && cd ~/go-python-agent
tar -xzf ~/go-python-agent.tar.gz
```

Дальнейшие шаги одинаковы для обоих вариантов.

---

## Шаг 3. Установить Docker

Официальный скрипт сам подбирает дистрибутив:
```bash
curl -fsSL https://get.docker.com | sh
```

Разрешить запуск `docker` без `sudo` и **перелогиниться**:
```bash
sudo usermod -aG docker $USER
exit
```

Зайти снова и проверить:
```bash
ssh <user>@<IP>
docker --version
docker compose version      # обе команды должны показать версии
```

---

## Шаг 4. Собрать и запустить

В папке проекта:
```bash
docker compose up -d --build
docker compose ps           # оба контейнера Up; у go-server — 0.0.0.0:80->8080
```

Локальная проверка с ВМ:
```bash
curl http://localhost/health
# {"status":"ok"}
```

---

## Шаг 5. Проверка из интернета

С любого устройства:
```bash
curl http://<IP>/health
# {"status":"ok"}

curl -X POST http://<IP>/process \
  -H 'Content-Type: application/json' \
  -d '{"text":"hello "}'
# {"result":"hello hello "}
```

---

## Шаг 6. Если снаружи не отвечает

По частоте причин:

1. **Security Group** (причина №1) — перепроверить ingress TCP 80 из `0.0.0.0/0`
   и что правило в группе, привязанной к ВМ.
2. **Слушает ли Docker** (на ВМ):
   ```bash
   sudo ss -tlnp | grep ':80 '
   ```
   Должна быть строка с `docker-proxy` на `0.0.0.0:80`. Пусто → смотреть контейнеры и логи.
3. **Логи:**
   ```bash
   docker compose logs --tail=50
   ```
4. **Хостовый фаервол** (на образах Yandex Cloud обычно не блокирует, но проверить):
   ```bash
   sudo ufw status
   # если active и нет 80:
   sudo ufw allow 80/tcp
   ```

---

## Обслуживание

- **Обновить код** (вариант A): `git pull && docker compose up -d --build`.
- **Логи в реальном времени:** `docker compose logs -f`.
- **Остановить:** `docker compose down`.
- **Перезапустить:** `docker compose restart`.

---

## Production-заметки

Сейчас сервис доступен по **голому HTTP на порту 80** — для демо/теста достаточно.
Для постоянного использования рекомендуется:
- reverse-proxy (nginx/Caddy) с HTTPS (Let's Encrypt) и привязка домена;
- закрыть все порты в Security Group, кроме 22/80/443.
