# ЛР №5 — Контейнеризація веб-системи за допомогою Docker

Частина інфраструктури (Dockerfile, `docker-compose.yml` з `postgres` / `redis` /
`migrate` / `web`, поділ sandbox/production через `DJANGO_ENV`) існувала з
попередніх лабораторних. У цій роботі проведено аудит і закрито те, чого
бракувало до вимог методички.

## 1. Виконання вимог

| Вимога | Було | Зроблено |
|---|---|---|
| Dockerfile: базовий образ, WORKDIR, команда запуску | `python:3.13-slim`, `/app/src`, `daphne` (ASGI + WebSocket) | залишено; переписано на multi-stage (див. §3) |
| `.dockerignore` | лише `.git`, `.venv`, кеші, `.env`, `docs` | + `.env*` (жодних env-файлів в образі), `*.log`, `locust/results`, `.github`, `.idea` |
| Env на рантаймі | `env_file: .env.${DJANGO_ENV}` | без змін; `load_dotenv` при відсутньому файлі просто нічого не робить, змінні приходять з `env_file` |
| БД: офіційний `postgres`, іменований volume | `postgres:16-alpine`, `postgres_data` | persistence перевірено (§4) |
| Явна внутрішня мережа | default-мережа compose | `networks: backend`, усі сервіси підключені явно |
| Healthchecks + `depends_on: service_healthy` | `postgres`, `redis` | + `web` (HTTP `GET /` через `urllib`, бо в slim-образі немає curl) |
| Порт PostgreSQL | `5432:5432` (усі інтерфейси) | `127.0.0.1:5432:5432`; так само `redis` → `127.0.0.1:6379` |
| Multi-stage | одностадійний, gcc у фінальному образі | `builder` → `slim`, 929 MB → 402 MB |
| Non-root | root | користувач `app` (uid 1000) |
| Hot-reload | — | `docker-compose.dev.yml`: bind mount `./src` + `watchfiles` |

## 2. Контейнери і мережі

```
                    хост
  :8000 ─────────────┐        127.0.0.1:5432   127.0.0.1:6379
                     │               │                │
 ┌───────────────────┼───── network: backend ─────────┼────────┐
 │                   ▼               ▼                ▼        │
 │  migrate ──►   web (daphne)    postgres          redis      │
 │  (одноразовий)  healthy         healthy          healthy    │
 │                                   │                         │
 └───────────────────────────────────┼─────────────────────────┘
                                     ▼
                       volume: galactic-auction-<env>_postgres_data
```

Порядок старту: `postgres`, `redis` (healthy) → `migrate` (`migrate` + `seed`
у sandbox, `Exited (0)`) → `web` → healthcheck `web` → `(healthy)`.
Ім'я проєкту `galactic-auction-${DJANGO_ENV}`, тому sandbox і production мають
окремі контейнери, мережу (`galactic-auction-sandbox_backend`) і volume.

```
$ docker network inspect galactic-auction-sandbox_backend
galactic-auction-sandbox-web-1 172.24.0.4/16
galactic-auction-sandbox-postgres-1 172.24.0.3/16
galactic-auction-sandbox-redis-1 172.24.0.2/16
```

## 3. Multi-stage build і розмір образу

- `builder` (`python:3.13-slim` + `build-essential`, `libpq-dev`) —
  `pip wheel -r requirements.txt` у `/wheels`.
- фінальна стадія (`python:3.13-slim`) — `pip install --no-index /wheels/*.whl`
  через `RUN --mount=type=bind,from=builder` (wheels не лишаються шаром в образі),
  код копіюється з `--chown=app:app`, `USER app`.
- Dev-інструменти (ruff, black, pytest, pre-commit) винесено в
  `requirements-dev.txt` (його ставлять локально і в CI), тож в образ потрапляють
  лише рантайм-залежності.

```
$ docker images
IMAGE                                   DISK USAGE   CONTENT SIZE
galactic-auction:before-multistage           929MB          213MB   # старий Dockerfile
galactic-auction:after-multistage            398MB         81.1MB   # multi-stage
galactic-auction-sandbox-web:latest          402MB         81.9MB   # + watchfiles для dev-режиму
```

```
$ docker compose exec web id
uid=1000(app) gid=1000(app) groups=1000(app)
```

## 4. Persistence даних

```
$ psql: create table persistence_check + insert
CREATE TABLE
INSERT 0 1
written before down|2026-10-18 16:22:51.243541+00
$ docker compose down   (без -v)
 Container galactic-auction-sandbox-web-1 Removed
 Container galactic-auction-sandbox-migrate-1 Removed
 Container galactic-auction-sandbox-postgres-1 Removed
 Container galactic-auction-sandbox-redis-1 Removed
 Network galactic-auction-sandbox_backend Removed
$ docker volume ls | grep sandbox_postgres
local     galactic-auction-sandbox_postgres_data
$ docker compose up -d --wait
 Container galactic-auction-sandbox-web-1 Healthy
written before down|2026-10-18 16:22:51.243541+00
$ docker compose up -d --force-recreate --wait postgres
 Container galactic-auction-sandbox-postgres-1 Recreated
 Container galactic-auction-sandbox-postgres-1 Healthy
written before down|2026-10-18 16:22:51.243541+00
DROP TABLE
```

Рядок пережив і `docker compose down`, і перестворення контейнера `postgres`:
дані живуть у volume, а не в контейнері. `docker compose down -v` видалив би їх.

## 5. Hot-reload

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

`daphne` не має `--reload`, а `daphne` немає в `INSTALLED_APPS` (без нього
`runserver` працює як WSGI і без WebSocket), тому dev-override запускає
`watchfiles "daphne ..." /app/src`. Код монтується bind mount'ом `./src:/app/src`;
в основному `docker-compose.yml` bind mount немає, тож production бере код з образу.

Перевірка: у `home.html` змінено `<h1>` → у логах автоперезапуск, сторінка
віддає новий текст без перезбірки:

```
$ curl -s localhost:8000/ | grep -o "<h1>.*</h1>"
<h1>🪐 Galactic Artifact Auction</h1>
$ sed -i '' 's|Auction</h1>|Auction (hot-reload)</h1>|' src/auctions/web/templates/auctions/home.html
$ docker compose logs web
web-1  | [16:21:01] 1 change detected
web-1  | 2026-10-18 16:21:01,647 INFO     Killed 0 pending application instances
web-1  | 2026-10-18 16:21:02,324 INFO     Starting server at tcp:port=8000:interface=0.0.0.0
web-1  | 2026-10-18 16:21:02,324 INFO     Listening on TCP address 0.0.0.0:8000
$ curl -s localhost:8000/ | grep -o "<h1>.*</h1>"
<h1>🪐 Galactic Artifact Auction (hot-reload)</h1>
```

## 6. Перевірка роботи системи

```
$ docker compose ps
NAME                                  STATUS                    PORTS
galactic-auction-sandbox-postgres-1   Up (healthy)              127.0.0.1:5432->5432/tcp
galactic-auction-sandbox-redis-1      Up (healthy)              127.0.0.1:6379->6379/tcp
galactic-auction-sandbox-web-1        Up (healthy)              0.0.0.0:8000->8000/tcp

$ curl ...
GET / -> 200
GET /accounts/login/ -> 200
GET /lots/ -> 302                      # редирект на логін
GET /api/lots/ -> 401                  # без токена
POST /api/auth/login/ -> {"token": "...", "user": {"id":2,"username":"pilot1",...}}
GET /api/lots/ (token) -> 8 lots
GET /api/dashboard/user/ (token) -> 200

$ docker compose exec web python manage.py showmigrations auctions
 [X] 0001_initial
 [X] 0002_userprofile
 [X] 0003_lot_is_closed
$ docker compose exec postgres psql ... -c "select count(*) from auctions_lot;"
    8
```

Production (`DJANGO_ENV=production docker compose up --build`): усі сервіси
`healthy`, `GET /` → 200, `manage.py check` — без зауважень.

На хості проти контейнерних postgres/redis: `ruff`, `black --check`,
`manage.py check` (sandbox і production), `pytest -v` — 54 passed;
Locust (10 користувачів, 15 с) — 167 запитів, 0 помилок.
