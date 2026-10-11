# Galactic Artifact Auction

Навчальний навантажений проєкт для лабораторної роботи з архітектури ПЗ.

## Про проєкт

"Galactic Artifact Auction" — аукціон рідкісних міжгалактичних артефактів у
реальному часі. Учасники підключаються до лоту через WebSocket і в останні
секунди торгів надсилають ставки одночасно з десятків клієнтів.

**Чому саме цей домен обраний для лабораторної роботи:** гоночні умови
(race conditions) на WebSocket-з'єднаннях — показовий і водночас компактний
кейс для навантажувальних систем реального часу:

- вимагає **атомарних транзакцій** на рівні БД (`SELECT ... FOR UPDATE`),
  бо кілька конкурентних запитів змагаються за одну й ту саму мутацію стану
  (хто зараз лідирує з найвищою ставкою);
- вимагає коректної **синхронізації стану між клієнтами** — усі підключені
  учасники повинні побачити однаковий результат практично одночасно, що
  демонструє роль pub/sub-шару (Django Channels + Redis) як механізму
  горизонтального масштабування WebSocket-з'єднань;
- дає змогу наочно продемонструвати різницю між "наївною" (без блокувань)
  та коректною обробкою конкурентних запитів на реальному прикладі, а не
  на абстрактній ілюстрації.

Детальний опис архітектури, компонентів і потоку даних — у
[`docs/architecture.md`](docs/architecture.md) (включно з sequence diagram
для двох клієнтів, що ставлять одночасно). Звіт про лабораторну №2
(ролі, автентифікація, розмежування прав, тести) — у
[`docs/lab2_report.md`](docs/lab2_report.md).

## Ролі та автентифікація

- Використовується стандартна модель `django.contrib.auth.models.User`.
  Ролі не потребують окремого поля чи міграції: `is_staff` = адміністратор,
  усі інші автентифіковані користувачі = звичайний користувач (`user`).
- Автентифікація — сесійна (`django.contrib.auth`), стандартна для Django.
  WebSocket-з'єднання (`AuctionConsumer` з лабораторної 1) отримує того
  самого автентифікованого користувача через `AuthMiddlewareStack`,
  підключений в `config/asgi.py`.
- Маршрути:
  - `/accounts/register/` — реєстрація нового користувача.
  - `/accounts/login/` / `/accounts/logout/` — вхід і вихід.
  - `/dashboard/user/` — головна сторінка звичайного користувача (активні лоти).
  - `/dashboard/admin/` — головна сторінка адміністратора (усі користувачі й лоти); доступна лише `is_staff`.
  - `/lots/`, `/lots/new/`, `/lots/<id>/`, `/lots/<id>/edit/` — CRUD лотів; ставки робляться через WebSocket з лабораторної 1.
- Адміністраторів створюють через `python manage.py createsuperuser` або
  Django admin — окремої форми реєстрації для них немає (за завданням не
  вимагається).

### Тестові дані

`docker compose up --build` уже прожене `python manage.py seed`
автоматично через сервіс `migrate` (див. розділ "Запуск"). Вручну —
наповнити базу демо-адміном, кількома користувачами й лотами без ручного
шеллу:

```bash
cd src
python manage.py seed
```

Команда ідемпотентна (повторний запуск нічого не дублює) і в кінці виводить
логіни/паролі створених користувачів.

## REST API

Окремий REST API (Django REST Framework) поверх тієї самої бізнес-логіки,
що й HTML-сторінки й WebSocket-консюмер — авторизація через токен
(`Authorization: Token <key>`).

| Маршрут | Метод | Опис |
|---|---|---|
| `/api/auth/register/` | POST | реєстрація, повертає токен одразу |
| `/api/auth/login/` | POST | `username`+`password` → токен |
| `/api/auth/logout/` | POST | видаляє токен поточного користувача |
| `/api/lots/` | GET/POST | список лотів / створення (власник = поточний користувач) |
| `/api/lots/<id>/` | GET/PATCH/DELETE | деталі (будь-хто автентифікований) / редагування, видалення (лише власник або `is_staff`) |
| `/api/lots/<id>/bids/` | GET | історія ставок на лот |
| `/api/lots/<id>/bid/` | POST | зробити ставку — через ту саму `services.place_bid()`, що й WebSocket `AuctionConsumer` |
| `/api/dashboard/user/` | GET | активні лоти + ставки поточного користувача |
| `/api/dashboard/admin/` | GET | усі користувачі й лоти; лише `is_staff` (403 інакше) |

Приклад через `curl` — реєстрація → логін → запит з токеном:

```bash
# 1. Реєстрація (одразу повертає токен)
curl -X POST http://localhost:8000/api/auth/register/ \
  -H "Content-Type: application/json" \
  -d '{"username":"pilot3","email":"pilot3@example.com","password":"S3curePass!23"}'

# 2. Або логін, якщо користувач вже існує
curl -X POST http://localhost:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"username":"pilot3","password":"S3curePass!23"}'
# -> {"token": "<TOKEN>", "user": {...}}

# 3. Запит з токеном
curl http://localhost:8000/api/lots/ -H "Authorization: Token <TOKEN>"

# 4. Ставка на лот (та сама race-condition-захищена логіка, що й у WebSocket)
curl -X POST http://localhost:8000/api/lots/1/bid/ \
  -H "Authorization: Token <TOKEN>" -H "Content-Type: application/json" \
  -d '{"amount": "150.00"}'
```

## Тести

```bash
source .venv/bin/activate  # або своє venv
docker compose up -d       # потрібен реальний PostgreSQL для select_for_update
cd src && python manage.py migrate
cd ..
pytest -v
```

### CI/CD

`.github/workflows/ci.yml` (GitHub Actions) запускається на `push` і
`pull_request` у `main`: встановлює Python 3.13 і залежності, проганяє
`ruff check`, `black --check`, `manage.py check` і `pytest -v` проти
service-контейнерів PostgreSQL та Redis (середовище `sandbox`). Будь-яка
помилка лінтера чи тесту валить пайплайн.

## Стек

- Django + Django Channels (ASGI, WebSocket)
- PostgreSQL — персистентне зберігання лотів, ставок, користувачів
- Redis — channel layer (pub/sub для broadcast ставок) і кеш "гарячих" даних лоту
- Daphne — ASGI-сервер

## Структура проєкту

```
galactic-auction/
├── docs/                 # архітектура, діаграми, демо pre-commit
├── src/                  # код Django-проєкту
│   ├── config/           # settings, asgi/wsgi, root urls
│   └── auctions/
│       ├── models.py         # спільна доменна логіка (Lot, Bid)
│       ├── services.py       # place_bid() — спільна для WS і REST API
│       ├── consumers.py      # WebSocket (лабораторна 1)
│       ├── routing.py
│       ├── management/       # python manage.py seed
│       ├── web/               # фронтенд: HTML-сторінки
│       │   ├── views.py, forms.py, decorators.py, urls.py
│       │   └── templates/auctions/*.html
│       ├── api/                # бекенд: REST API (DRF)
│       │   ├── views.py, serializers.py, urls.py
│       └── tests/
├── config/               # приклади конфігурації / інфраструктурні файли
├── scripts/              # допоміжні скрипти
├── Dockerfile            # образ застосунку (спільний для web і migrate)
├── docker-compose.yml    # postgres, redis, migrate (init), web (застосунок)
├── .env.sandbox          # змінні sandbox-середовища (заглушки)
├── .env.production       # змінні production-середовища (заглушки)
├── .github/workflows/ci.yml  # CI: ruff, black, pytest на push/PR у main
├── pyproject.toml        # конфігурація ruff / black
├── .pre-commit-config.yaml
└── requirements.txt
```

## Запуск

Проєкт має два середовища — **sandbox** (тестове) і **production** (робоче).
Яке з них використовується, визначає змінна оточення `DJANGO_ENV`
(`sandbox` за замовчуванням). `src/config/settings.py` за нею підвантажує
`.env.sandbox` або `.env.production`.

Обидва файли закомічені, але містять лише **значення-заглушки**. Справжні
секрети передаються звичайними змінними оточення — вони мають пріоритет над
файлом (`load_dotenv` не перезаписує вже задані змінні). Якщо якоїсь
обов'язкової змінної немає, Django не стартує (`ImproperlyConfigured`).
Локальний `.env` у `.gitignore` і проєктом більше не читається.

### Чим відрізняються середовища

|                     | Sandbox                              | Production                                      |
|---------------------|--------------------------------------|-------------------------------------------------|
| База даних          | `galactic_auction_sandbox`           | `galactic_auction_production`                   |
| Docker volume       | `galactic-auction-sandbox_postgres_data` | `galactic-auction-production_postgres_data` |
| `DEBUG`             | `True`                               | `False`                                         |
| Помилки 404/500     | сторінки Django зі стектрейсом       | власні `404.html` / `500.html` без деталей      |
| `ALLOWED_HOSTS`     | `localhost,127.0.0.1`                | конкретні хости з `.env.production` (не `*`); запит з іншим `Host` → 400 |
| Демо-дані (`seed`)  | так                                  | ні (демо-паролі в production не потрібні)       |

### Чому один compose-файл, а не два

Обрано **один `docker-compose.yml`** з `env_file: .env.${DJANGO_ENV:-sandbox}`
і `name: galactic-auction-${DJANGO_ENV:-sandbox}` замість пари
`docker-compose.sandbox.yml` / `docker-compose.production.yml` чи profiles.
Сервіси в обох середовищах однакові — різняться лише змінні, тож окремі
файли дублювали б майже все. Ім'я проєкту залежить від `DJANGO_ENV`, тому
кожне середовище отримує власні контейнери, мережу і volume з базою —
тестові дані фізично лежать в іншій базі в іншому сховищі.

Обидва стеки публікують ті самі порти (8000, 5432, 6379), тому одночасно
запускається одне середовище; перед перемиканням зупиніть інше.

### Sandbox

```bash
docker compose up --build
# зупинити
docker compose down
```

Стек: `postgres`, `redis`, одноразовий `migrate` (`migrate` + `seed` —
демо-адмін, користувачі, лоти; `Exited (0)` у `docker compose ps -a` — це
очікувано) і `web` (Django/Channels через `daphne`, стартує після успішного
`migrate`) на `http://localhost:8000/`: HTML (`/`), REST API (`/api/`),
WebSocket (`/ws/auction/<lot_id>/`).

```bash
docker compose ps -a
docker compose logs web
docker compose logs migrate
```

### Production

```bash
DJANGO_ENV=production docker compose up --build
# зупинити
DJANGO_ENV=production docker compose down
```

Справжні секрети задаються змінними оточення поверх заглушок, наприклад:

```bash
export DJANGO_ENV=production
export SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(50))')"
export POSTGRES_PASSWORD='...'
docker compose up --build
```

`migrate` у production лише застосовує міграції; адміністратора створіть
вручну: `DJANGO_ENV=production docker compose exec web python manage.py createsuperuser`.

`python manage.py check --deploy` у production ще попереджає про HTTPS
(`SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, HSTS) — ці налаштування
вмикаються, коли перед застосунком стоїть HTTPS-проксі; для локального
запуску по HTTP вони зламали б логін.

### Локально без Docker (для розробки)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

docker compose up -d postgres redis   # лише БД і кеш sandbox-середовища

cd src
python manage.py migrate
python manage.py seed
python manage.py runserver            # або: daphne -b 0.0.0.0 -p 8000 config.asgi:application
```

### Перевірка конфігурації

```bash
cd src
python manage.py check                                  # sandbox
DJANGO_ENV=production python manage.py check --deploy   # production
```

## Лінтери та pre-commit

Лінтери (`ruff`, `black`) налаштовані в `pyproject.toml` (target Python
3.11+, міграції ігноруються).

Запустити вручну:

```bash
ruff check src
black --check src
```

Автовиправлення:

```bash
ruff check src --fix
black src
```

### pre-commit

Встановлення хука (одноразово):

```bash
pip install pre-commit
pre-commit install
```

Після цього `git commit` автоматично прожене `ruff`, `black` та базові
перевірки (`trailing-whitespace`, `end-of-file-fixer`,
`check-added-large-files` тощо) на змінених файлах.

Запустити pre-commit вручну на всіх файлах:

```bash
pre-commit run --all-files
```

Демонстрація реального блокування коміту через порушення лінтера —
у [`docs/precommit_demo.md`](docs/precommit_demo.md).
