# Звіт: Лабораторна робота №2 — користувачі, ролі, розмежування прав

Продовження проєкту "Galactic Artifact Auction" (лабораторна 1: Django +
Channels, WebSocket-аукціон із `SELECT ... FOR UPDATE` проти race condition).
Ця лабораторна додає реєстрацію, автентифікацію, ролі та розмежування прав
доступу поверх існуючого доменного коду (`Lot`, `Bid`, `AuctionConsumer`).

## 1. Архітектурні рішення

### 1.1 Модель користувача

Обрано стандартну `django.contrib.auth.models.User`, без кастомної моделі.

**Чому:** `settings.AUTH_USER_MODEL` у проєкті лабораторної 1 не був
перевизначений, а моделі `Lot`/`Bid` вже мають `ForeignKey` на
`settings.AUTH_USER_MODEL` — тобто на стандартного `User`. Заміна на
кастомну модель (`AbstractUser`) на цьому етапі означала б переписування
історії міграцій (`swappable_dependency`), що ризиковано і не дає жодної
практичної переваги: додаткові поля для профілю в завданні не потрібні.

### 1.2 Ролі

Без окремого поля `role` й без нової міграції: `User.is_staff` = роль
`admin`, усі інші автентифіковані користувачі = роль `user`.

**Чому:** `is_staff` — вже вбудований, семантично коректний прапорець ролі
адміністратора (він же відкриває доступ до `/admin/`). Додавання ще одного
поля `role` дублювало б ту саму інформацію і вимагало б міграції та
синхронізації двох джерел істини. Це підтверджено командою
`python manage.py makemigrations --check --dry-run` — після додавання ролей
жодної нової міграції не знадобилось.

### 1.3 Автентифікація HTTP

Сесійна автентифікація Django (`django.contrib.auth`, `AuthenticationMiddleware`
— вже був у `MIDDLEWARE` з лабораторної 1). Це стандартний і найпростіший
підхід для навчального проєкту; токени/JWT не додають нічого нового для
серверного рендерингу Django-шаблонів, яким побудовані сторінки-заглушки і
CRUD лотів у цій лабораторній.

### 1.4 Автентифікація WebSocket

`AuctionConsumer` з лабораторної 1 уже мав перевірку
`user.is_authenticated` у `receive()`. У `config/asgi.py` вже було
підключено `channels.auth.AuthMiddlewareStack` навколо `URLRouter`. Це
означає, що той самий сесійний cookie, яким браузер автентифікований по
HTTP (після сесійного логіну з цієї лабораторної), автоматично розпізнається
і на WebSocket-з'єднанні — `self.scope["user"]` в consumer'і вже готовий.
Додаткових змін у `asgi.py`/`consumers.py` не знадобилось; коректність
підтверджена тестами `auctions/tests/test_consumers.py`.

## 2. Маршрути та доступ

| Маршрут | View | Хто має доступ |
|---|---|---|
| `/accounts/register/` | `register_view` | будь-хто (анонімний) |
| `/accounts/login/` | `login_view` | будь-хто (анонімний) |
| `/accounts/logout/` | `logout_view` | будь-який автентифікований користувач |
| `/dashboard/user/` | `dashboard_user` | будь-який автентифікований користувач |
| `/dashboard/admin/` | `dashboard_admin` | лише `is_staff` (403 для звичайних) |
| `/lots/` | `lot_list` | будь-який автентифікований користувач |
| `/lots/new/` | `lot_create` | будь-який автентифікований користувач (власник = `request.user`) |
| `/lots/<id>/` | `lot_detail` | будь-який автентифікований користувач; ставки — через WebSocket `/ws/auction/<id>/` з лабораторної 1 |
| `/lots/<id>/edit/` | `lot_edit` | власник лота або `is_staff` (403 для решти — IDOR-захист) |
| `/ws/auction/<id>/` | `AuctionConsumer` | лише автентифіковані (лабораторна 1 + `AuthMiddlewareStack`) |

Усі захищені сторінки для анонімного користувача повертають **302**
(редірект на `/accounts/login/`) через `@login_required` /
`role_required(...)`, який сам обгортає `login_required`.

## 3. Розмежування прав доступу

### 3.1 Вертикальне (за роллю)

`src/auctions/decorators.py` — `role_required(role)`:

```python
def role_required(role):
    def decorator(view_func):
        @login_required
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            is_admin = request.user.is_staff
            if (role == "admin") != is_admin:
                raise PermissionDenied
            return view_func(request, *args, **kwargs)
        return wrapped
    return decorator
```

Застосовано до `dashboard_admin` (`src/auctions/views.py:48`). Неавторизований
запит → `login_required` дає 302; авторизований, але без `is_staff` →
`PermissionDenied` → Django повертає 403.

### 3.2 Горизонтальне (IDOR)

`src/auctions/views.py:86`, `lot_edit` (рядок з перевіркою власника):

```python
if lot.owner_id != request.user.id and not request.user.is_staff:
    raise PermissionDenied
```

Це унеможливлює редагування чужого лота користувачем, який не є ні
власником, ні адміністратором.

## 4. MVP бізнес-логіки

CRUD для лотів (`Lot`) поверх моделей з лабораторної 1:
- створення (`lot_create`) — прив'язує `owner = request.user`, встановлює
  `current_highest_bid = starting_price`;
- список (`lot_list`), деталі (`lot_detail`) — деталі лота включають просту
  сторінку з JS, що відкриває WebSocket на `/ws/auction/<id>/` (лабораторна
  1) і надсилає ставки в реальному часі;
- редагування (`lot_edit`) — лише власник або адміністратор.

Ставки (`Bid`) як і раніше створюються виключно через `AuctionConsumer`
(без змін у логіці `SELECT ... FOR UPDATE` з лабораторної 1) — HTTP-шар цієї
лабораторної лише додає автентифікацію й прив'язку лота до власника, яку
`AuctionConsumer` вже використовував (`user_id` зі `scope["user"]`).

## 5. Фронтенд (HTML-шаблони)

Усі views рендерять реальний HTML через `render(request, "template.html", context)`
— жоден маршрут не повертає голий текст чи JSON. Шаблони лежать у
`src/auctions/templates/auctions/`:

| Шаблон | View | Призначення |
|---|---|---|
| `base.html` | — | спільний макет: `<header>` з навігацією (Login/Register для анонімів; Lots/My dashboard/Admin dashboard/Logout для автентифікованих, посилання на admin-панель — лише для `is_staff`), єдиний inline `<style>` з мінімальною палітрою/типографікою (без Bootstrap/Tailwind) |
| `register.html` | `register_view` | форма реєстрації (`UserCreationForm` + email) |
| `login.html` | `login_view` | форма входу, повідомлення про помилку при неправильних даних |
| `dashboard_user.html` | `dashboard_user` | привітання `Вітаємо, {{ user.username }}!` + список активних лотів |
| `dashboard_admin.html` | `dashboard_admin` | привітання адміністратора + список усіх користувачів і список усіх лотів для модерації |
| `lot_list.html` | `lot_list` | список усіх лотів з посиланнями на деталі й на редагування (лише для власника/адміна) |
| `lot_detail.html` | `lot_detail` | деталі лота + `<form id="bid-form">`, що через inline JS відкриває `WebSocket` до `/ws/auction/<id>/` (consumer лабораторної 1), показує статус з'єднання, оновлює найвищу ставку в реальному часі (`bid_accepted`) і журнал подій без перезавантаження сторінки |
| `lot_create.html` | `lot_create` | форма створення лота (`LotForm`) |
| `lot_edit.html` | `lot_edit` | форма редагування лота, доступна лише власнику/адміну (перевірка — на рівні view, `views.py:86`) |

Стилізація — єдиний `<style>`-блок у `base.html` (CSS-змінні, картки
`.card`, акуратні форми/списки/кнопки), успадковується всіма сторінками
через `{% extends "auctions/base.html" %}` — жодних зовнішніх
CSS-фреймворків чи бібліотек.

### 5.1 UI/UX-тема та ефекти

Обрано темну "космічну" тему (градієнт `#05061c → #1a1040`, неонові
акценти фіолетового/бірюзового), бо вона природно пасує до домену
("галактичний аукціон") і добре відтіняє неонове підсвічування
інтерактивних елементів. Заголовки набрані шрифтом Orbitron (Google
Fonts) для футуристичного вигляду, текст — Inter для читабельності;
картки лотів — "скляні панелі" (`backdrop-filter: blur` + напівпрозорий
фон). Додано три легкі vanilla-JS ефекти без сторонніх бібліотек:
статичний CSS-патерн зірок на фоні плюс анімований `<canvas>` із
30–60 мерехтливими зірками (`base.html`); коротка (0.5с) "спалахова"
анімація суми ставки при отриманні `bid_accepted` через WebSocket;
бортовий таймер зворотного відліку до `ends_at` з миготінням, коли
лишилось менше хвилини. Усі анімації вимикаються через
`@media (prefers-reduced-motion: reduce)`, щоб не заважати людям з
чутливістю до руху/мерехтіння.

## 6. REST API

Окремий REST API (Django REST Framework) поверх тієї самої бізнес-логіки,
що й HTML-сторінки та WebSocket-консюмер з лабораторної 1.

### 6.1 Чому Token Authentication

Для API обрано `rest_framework.authentication.TokenAuthentication`
(`config/settings.py`, `REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"]`),
а не сесійну автентифікацію, яку використовують HTML-сторінки. Причина —
API за задумом призначений для клієнтів поза браузером (скрипти, `curl`,
мобільні клієнти), яким незручно нести CSRF-токен і cookie-сесію; простий
статичний токен у заголовку `Authorization: Token <key>` — стандартний і
найпростіший варіант для навчального REST API на DRF, що не заважає
паралельно існуючій сесійній автентифікації HTML-частини (обидва механізми
незалежні й не конфліктують, бо HTTP-шар лабораторної 2 і `/api/` — окремі
`urlpatterns` з різними `DEFAULT_AUTHENTICATION_CLASSES`, застосованими
лише в рамках DRF-в'юх).

### 6.2 Чому спільна `services.place_bid()`

До цієї сесії логіка прийняття ставки (`SELECT ... FOR UPDATE` +
перевірки + запис `Bid`) жила лише в `AuctionConsumer.place_bid()`
(`consumers.py`, лабораторна 1). Коли з'явилась потреба прийняти ставку
ще й через REST API (`POST /api/lots/<id>/bid/`), дублювати цю логіку в
другому місці означало б два незалежні захисти від race condition, які
могли б розійтись при майбутніх правках (наприклад хтось поправить
перевірку в одному місці й забуде про інше). Тому логіку винесено в
`src/auctions/services.py::place_bid(lot_id, user_id, amount)` — чисту
синхронну функцію без жодної залежності від Channels чи DRF. І
`AuctionConsumer.place_bid()` (обгорнутий у `@database_sync_to_async`), і
`LotViewSet.bid()` (`api_views.py`) викликають саме її. Рефактор
консюмера — суто структурний, поведінка та формат відповіді (`accepted`,
`reason`, `current_highest_bid`, `amount`, `username`) не змінились, що
підтверджено незмінним проходженням `test_consumers.py`.

### 6.3 Маршрути

| Маршрут | Метод | Права доступу |
|---|---|---|
| `/api/auth/register/` | POST | будь-хто |
| `/api/auth/login/` | POST | будь-хто |
| `/api/auth/logout/` | POST | автентифікований |
| `/api/lots/` | GET/POST | автентифікований (`owner` = поточний користувач на POST) |
| `/api/lots/<id>/` | GET | автентифікований |
| `/api/lots/<id>/` | PATCH/DELETE | власник або `is_staff` (`IsOwnerOrAdmin`, `api_views.py`) |
| `/api/lots/<id>/bids/` | GET | автентифікований |
| `/api/lots/<id>/bid/` | POST | автентифікований, викликає `services.place_bid()` |
| `/api/dashboard/user/` | GET | автентифікований |
| `/api/dashboard/admin/` | GET | лише `is_staff` (`permissions.IsAdminUser`) |

Права на `PATCH`/`DELETE` лота навмисно точно повторюють правило з HTML
`lot_edit` (`views.py:86`) — той самий власник-або-адмін критерій,
реалізований окремим DRF permission-класом `IsOwnerOrAdmin`
(`api_views.py`), що застосовується лише до `update`/`partial_update`/
`destroy`, тоді як перегляд (`GET`) і ставки (`bid`) відкриті для будь-якого
автентифікованого користувача — так само, як HTML-сторінка деталей лота
доступна будь-кому залогіненому, а не лише власнику.

## 7. Тести

Запуск: `docker compose up -d && cd src && python manage.py migrate && cd .. && pytest -v`
(потрібен реальний PostgreSQL — `select_for_update` не працює на SQLite;
для WebSocket-тестів channel layer підмінюється на
`channels.layers.InMemoryChannelLayer`, Redis для тестів не потрібен).

### Список тестів

`src/auctions/tests/test_auth.py`
- `test_register_creates_user_and_logs_them_in` — успішна реєстрація створює `User` і логінить.
- `test_register_duplicate_username_is_rejected` — дублікат `username` не проходить (200, користувач не створюється вдруге).
- `test_login_with_correct_credentials_succeeds` — вхід з правильними даними → 302 і доступ до `/dashboard/user/` (200).
- `test_login_with_wrong_password_is_rejected` — вхід з неправильним паролем → **401**, а не 200.
- `test_logout_ends_the_session` — після логауту `/dashboard/user/` знову недоступний (302).

`src/auctions/tests/test_permissions.py`
- `test_anonymous_access_to_dashboard_redirects_to_login` — анонімний доступ до захищеного маршруту → 302 на логін.
- `test_regular_user_cannot_access_admin_dashboard` — звичайний користувач на `/dashboard/admin/` → **403** (вертикальне розмежування).
- `test_admin_can_access_admin_dashboard` — адміністратор (`is_staff`) на `/dashboard/admin/` → 200.
- `test_user_cannot_edit_someone_elses_lot` — користувач Б редагує лот користувача А → **403** (IDOR).
- `test_owner_can_edit_their_own_lot` — власник редагує свій лот → 200.
- `test_admin_can_edit_any_lot` — адміністратор редагує чужий лот → 200 (адмін — виняток з IDOR-перевірки за задумом).

`src/auctions/tests/test_lots.py`
- `test_lot_create_requires_login` — анонімний доступ до створення лота → 302.
- `test_lot_create_sets_owner_and_initial_bid` — створений лот має `owner = request.user` і `current_highest_bid = starting_price`.

`src/auctions/tests/test_consumers.py` (інтеграція з `AuctionConsumer` лабораторної 1)
- `test_authenticated_user_bid_is_accepted` — автентифікований користувач через WebSocket робить ставку → `bid_accepted`.
- `test_anonymous_bid_is_rejected` — анонімне WebSocket-з'єднання надсилає ставку → `error` / `not_authenticated`.

`src/auctions/tests/test_api.py` (REST API, `rest_framework.test.APIClient`)
- `test_anonymous_get_lots_returns_401` — анонімний GET `/api/lots/` → **401**.
- `test_login_with_correct_credentials_returns_token` — логін правильними даними → 200, токен у відповіді.
- `test_login_with_wrong_password_is_rejected` — логін неправильним паролем → **400**.
- `test_regular_user_cannot_access_admin_dashboard` — звичайний користувач на `/api/dashboard/admin/` → **403**.
- `test_admin_can_access_admin_dashboard` — `is_staff` на `/api/dashboard/admin/` → 200.
- `test_user_cannot_patch_someone_elses_lot` — користувач Б робить PATCH на лот користувача А → **403** (IDOR через API).
- `test_owner_can_patch_their_own_lot` — власник PATCH свого лота → 200.
- `test_register_creates_user_and_returns_token` — реєстрація через API повертає токен одразу.
- `test_lot_create_sets_owner_via_api` — створений через API лот має правильного `owner` і `current_highest_bid = starting_price`.
- `test_bid_action_uses_shared_service` — ставка через `POST /api/lots/<id>/bid/` коректно проходить через `services.place_bid()` і оновлює `current_highest_bid`.

### Вивід `pytest -v`

```
============================= test session starts ==============================
platform darwin -- Python 3.13.15, pytest-9.1.1, pluggy-1.6.0 -- /Users/admin/PycharmProjects/WebPython Lab1/.venv/bin/python
cachedir: .pytest_cache
django: version: 6.1.1, settings: config.settings (from ini)
rootdir: /Users/admin/PycharmProjects/WebPython Lab1/galactic-auction
configfile: pyproject.toml
plugins: asyncio-1.4.0, django-4.14.0
asyncio: mode=Mode.AUTO, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collecting ... collected 25 items

src/auctions/tests/test_api.py::test_anonymous_get_lots_returns_401 PASSED [  4%]
src/auctions/tests/test_api.py::test_login_with_correct_credentials_returns_token PASSED [  8%]
src/auctions/tests/test_api.py::test_login_with_wrong_password_is_rejected PASSED [ 12%]
src/auctions/tests/test_api.py::test_regular_user_cannot_access_admin_dashboard PASSED [ 16%]
src/auctions/tests/test_api.py::test_admin_can_access_admin_dashboard PASSED [ 20%]
src/auctions/tests/test_api.py::test_user_cannot_patch_someone_elses_lot PASSED [ 24%]
src/auctions/tests/test_api.py::test_owner_can_patch_their_own_lot PASSED [ 28%]
src/auctions/tests/test_api.py::test_register_creates_user_and_returns_token PASSED [ 32%]
src/auctions/tests/test_api.py::test_lot_create_sets_owner_via_api PASSED [ 36%]
src/auctions/tests/test_api.py::test_bid_action_uses_shared_service PASSED [ 40%]
src/auctions/tests/test_auth.py::test_register_creates_user_and_logs_them_in PASSED [ 44%]
src/auctions/tests/test_auth.py::test_register_duplicate_username_is_rejected PASSED [ 48%]
src/auctions/tests/test_auth.py::test_login_with_correct_credentials_succeeds PASSED [ 52%]
src/auctions/tests/test_auth.py::test_login_with_wrong_password_is_rejected PASSED [ 56%]
src/auctions/tests/test_auth.py::test_logout_ends_the_session PASSED     [ 60%]
src/auctions/tests/test_lots.py::test_lot_create_sets_owner_and_initial_bid PASSED [ 64%]
src/auctions/tests/test_permissions.py::test_regular_user_cannot_access_admin_dashboard PASSED [ 68%]
src/auctions/tests/test_permissions.py::test_admin_can_access_admin_dashboard PASSED [ 72%]
src/auctions/tests/test_permissions.py::test_user_cannot_edit_someone_elses_lot PASSED [ 76%]
src/auctions/tests/test_permissions.py::test_owner_can_edit_their_own_lot PASSED [ 80%]
src/auctions/tests/test_permissions.py::test_admin_can_edit_any_lot PASSED [ 84%]
src/auctions/tests/test_consumers.py::test_authenticated_user_bid_is_accepted PASSED [ 88%]
src/auctions/tests/test_consumers.py::test_anonymous_bid_is_rejected PASSED [ 92%]
src/auctions/tests/test_lots.py::test_lot_create_requires_login PASSED   [ 96%]
src/auctions/tests/test_permissions.py::test_anonymous_access_to_dashboard_redirects_to_login PASSED [100%]

============================== 25 passed in 10.32s ==============================
```

## 8. Підсумок виконання

### Основні завдання (5 балів)

1. **База даних користувачів і ролі** — виконано: стандартний `User`,
   ролі через `is_staff`, підтверджено відсутність нових міграцій.
2. **Реєстрація** — виконано: `register_view` + `RegisterForm`
   (`UserCreationForm` + унікальний email), стандартні валідатори паролів
   Django.
3. **Автентифікація (вхід)** — виконано: сесійний логін/логаут,
   `AuthMiddlewareStack` для WebSocket підтверджено тестами.
4. **Домашні сторінки-заглушки** — виконано: `/dashboard/user/`,
   `/dashboard/admin/`, редірект за роллю одразу після логіну.
5. **Розмежування прав доступу** — виконано: `role_required` (вертикальне,
   403), перевірка власника в `lot_edit` (горизонтальне/IDOR, 403),
   анонімний доступ → 302.

### Додаткові завдання

6. **MVP бізнес-логіки (2 бали)** — виконано: CRUD лотів (створення,
   список, деталі, редагування), прив'язка до `owner`, ставки — через
   WebSocket лабораторної 1, прив'язані до `user`.
7. **Тести pytest (3 бали)** — виконано: 25 тестів (15 HTML/WebSocket +
   10 REST API), усі проходять (`pytest -v` вище), покриті всі 5
   обов'язкових сценаріїв (в обох шарах — HTML і API) плюс додаткові
   (реєстрація, дублікат username, CRUD лотів, WebSocket-автентифікація,
   спільна `services.place_bid()`).
8. **UI/UX-тема, JS-ефекти, seed-команда** — виконано: галактична тема
   (`base.html`), анімований зоряний фон, ефект спалаху ставки, бортовий
   таймер (розділ 5.1); `python manage.py seed` для наповнення тестовими
   даними.
9. **REST API (DRF)** — виконано: Token Authentication, `LotViewSet` з
   `IsOwnerOrAdmin`, ендпоінти реєстрації/логіну/логауту/дашбордів,
   рефакторинг `AuctionConsumer` на спільну `services.place_bid()` без
   дублювання логіки race condition (розділ 6).
