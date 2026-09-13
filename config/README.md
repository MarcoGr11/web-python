# config/

Ця директорія містить приклади конфігурації та інфраструктурні файли проєкту
(на відміну від `src/config/`, яка є пакетом налаштувань самого Django-проєкту).

- Приклад змінних середовища: [`../.env.example`](../.env.example) — скопіюйте
  його в `../.env` і підставте свої значення перед запуском.
- Django settings: `../src/config/settings.py`.
- Docker Compose (PostgreSQL + Redis) для локальної розробки: [`../docker-compose.yml`](../docker-compose.yml).
