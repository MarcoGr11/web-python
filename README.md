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
для двох клієнтів, що ставлять одночасно).

## Стек

- Django + Django Channels (ASGI, WebSocket)
- PostgreSQL — персистентне зберігання лотів, ставок, користувачів
- Redis — channel layer (pub/sub для broadcast ставок) і кеш "гарячих" даних лоту
- Daphne — ASGI-сервер

## Структура проєкту

```
galactic-auction/
├── docs/                 # архітектура, діаграми, демо pre-commit
├── src/                  # код Django-проєкту (config + auctions)
├── config/               # приклади конфігурації / інфраструктурні файли
├── scripts/              # допоміжні скрипти
├── docker-compose.yml    # PostgreSQL + Redis для локальної розробки
├── .env.example          # приклад змінних середовища
├── pyproject.toml        # конфігурація ruff / black
├── .pre-commit-config.yaml
└── requirements.txt
```

## Запуск

### 1. Залежності Python

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. PostgreSQL і Redis через Docker Compose

```bash
cp .env.example .env
docker compose up -d
```

Це підніме PostgreSQL (порт 5432) і Redis (порт 6379) з параметрами,
узгодженими з `.env.example`.

Якщо Docker не використовується — встановіть PostgreSQL і Redis локально і
пропишіть відповідні `POSTGRES_*` / `REDIS_*` значення у `.env`.

### 3. Міграції та запуск сервера

```bash
cd src
python manage.py migrate
python manage.py createsuperuser   # опційно
python manage.py runserver         # для звичайного HTTP/адмінки

# або через ASGI-сервер (потрібен для WebSocket):
daphne -b 0.0.0.0 -p 8000 config.asgi:application
```

WebSocket-ендпоінт для ставок на лот: `ws://localhost:8000/ws/auction/<lot_id>/`.

### 4. Перевірка конфігурації

```bash
python manage.py check
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
