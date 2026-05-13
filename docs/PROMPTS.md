# ЧитАИ — полная инструкция и промпты до production-state (v2, мульти-канал)

> **Цель документа.** Дать вам набор последовательных промптов, по
> которым любой исполнитель (Devin, Cursor, junior-инженер) доведёт
> ЧитАИ от текущего состояния (PR #5, ~91 / 100) до **абсолютной
> production-готовности** (~98 / 100), с **мульти-канальной**
> доставкой: Telegram (существующий — оставляем рабочим), **MAX**,
> **VK Сообщества** и опционально **Алиса Яндекса**.

---

## 0. Текущая база

- Репо: `https://github.com/BitMagistrate/ddhlsboz`
- Корневая ветка для всех новых работ: **`main`** (после мержа PR4 → PR5)
- Текущее состояние:
  - Backend FastAPI, 5,976 LOC, 171 теста
  - Frontend React+TS+Vite+Tailwind, 2,031 LOC, 27 тестов
  - **Telegram-бот aiogram, 348 LOC, 9 тестов — не выкидываем,
    мигрируем на единое ядро вместе с MAX**
  - CI: 3 джобы зелёные (lint + tests + bandit + benchmark gate)
  - Опциональная JSON-персистентность через `CHITAI_STATE_DIR`
  - GigaChat MAX + YandexGPT 5 Pro + mock провайдеры
- Стек российский: GigaChat MAX, YandexGPT 5 Pro, Yandex SpeechKit,
  Yandex Cloud, **Telegram + MAX + VK + (опц.) Алиса как точки входа**.

### Что нужно довести до 100%

| #  | Задача                                                  | Критичность | PR    |
| -- | ------------------------------------------------------- | ----------- | ----- |
| 1  | Frontend XSS hardening (DOMPurify + escape on render)   | HIGH        | PR6   |
| 2  | Rate-limit middleware + idempotency-keys                | HIGH        | PR7   |
| 3  | PostgreSQL 16 + Alembic миграции + replace JSON store   | HIGH        | PR8   |
| 4  | Авторизация: VK ID + Sber ID OAuth2 / OIDC              | HIGH        | PR9   |
| 5  | **Мульти-канальное ядро ботов + MAX** (TG живой)        | HIGH        | PR10  |
| 6  | **VK Сообщества** (VK Bot API для сообществ)            | HIGH        | PR11  |
| 7  | Yandex Cloud деплой (Compute + Object Storage + PG)     | HIGH        | PR12  |
| 8  | Корпус 100+ произведений + расширенный benchmark        | MEDIUM      | PR13  |
| 9  | Circuit breaker + observability (Yandex Monitoring)     | MEDIUM      | PR14  |
| 10 | Юридический ОПД: автогенерация уведомления Роскомнадзору| MEDIUM      | PR15  |
| 11 | Mini-app внутри MAX (WebApp + Bridge)                   | LOW         | PR16  |
| 12 | **Алиса Яндекса** — голосовой навык (опционально)       | LOW         | PR17  |

11 обязательных + 1 опциональный PR. Промпты ниже **самодостаточны**:
каждый можно дать новой сессии Devin без контекста, и он закроет один PR.

---

## 1. Перед запуском промптов — что подготовить вам лично

> Эти секреты исполнитель получить не сможет. Соберите заранее.

### 1.1. Учётки и токены

| Имя env-переменной         | Где брать                                                           |
| -------------------------- | ------------------------------------------------------------------- |
| `TELEGRAM_BOT_TOKEN`       | (уже есть) https://t.me/BotFather                                   |
| `MAX_BOT_TOKEN`            | https://max.ru/MasterBot → создать бота → «Получить токен»          |
| `MAX_WEBHOOK_SECRET`       | сгенерируйте сами: `openssl rand -hex 32`                           |
| `VK_GROUP_TOKEN`           | https://vk.com/dev → ваше сообщество → «Управление» → «Работа с API» → «Создать ключ доступа» (доступы: messages, photos) |
| `VK_GROUP_ID`              | ID вашего сообщества (число)                                        |
| `VK_CONFIRMATION_CODE`     | строка из настроек Callback API сообщества (выдаст VK при подключении webhook) |
| `VK_SECRET_KEY`            | сгенерируйте сами и впишите в Callback API сообщества               |
| `ALICE_SKILL_ID`           | (опц.) https://dialogs.yandex.ru → создать навык                    |
| `ALICE_OAUTH_TOKEN`        | (опц.) выдаётся при публикации навыка                               |
| `GIGACHAT_AUTHORIZATION_KEY` | https://developers.sber.ru/portal/products/gigachat-api → выпустить ключ |
| `GIGACHAT_CA_BUNDLE`       | путь до `min_digital.pem` (cert Минцифры) на сервере                |
| `YANDEX_API_KEY`           | https://console.cloud.yandex.ru → IAM → API Keys                    |
| `YANDEX_FOLDER_ID`         | ID каталога Yandex Cloud                                            |
| `YANDEX_SPEECHKIT_API_KEY` | отдельный API-ключ для SpeechKit                                    |
| `VK_ID_CLIENT_ID`          | https://id.vk.com → создать приложение (для логина пользователя в SPA, **не путать** с VK_GROUP_TOKEN) |
| `VK_ID_CLIENT_SECRET`      | оттуда же                                                           |
| `SBER_ID_CLIENT_ID`        | https://developer.sberbank.ru → SberID → создать приложение         |
| `SBER_ID_CLIENT_SECRET`    | оттуда же                                                           |
| `POSTGRES_DSN`             | формируется при создании Managed PostgreSQL в Yandex Cloud          |
| `JWT_SECRET`               | сгенерируйте: `openssl rand -hex 64`                                |

> **Важно про VK.** Есть **два разных VK-токена**: `VK_GROUP_TOKEN` —
> для бота сообщества (PR11). `VK_ID_CLIENT_ID/SECRET` — для логина
> пользователей через VK ID OAuth (PR9). Это разные API.

### 1.2. Юридическое
- Зарегистрировать **верифицированный профиль организации** на
  https://max.ru/business (требуется для создания бота — только юрлицо
  или ИП, резидент РФ).
- В VK создать сообщество (паблик), переключить в режим бота
  (Управление → Сообщения → Включить сообщения сообщества).
- Подать уведомление в Роскомнадзор как ОПД (PR #15 сгенерирует форму).
- Купить домен (`читаи.рф` или `chitai.education`).

### 1.3. Машина для запуска промптов
- Devin или Cursor с настроенным GitHub-доступом к
  `BitMagistrate/ddhlsboz`.
- Перед каждым промптом — `git checkout main && git pull`.

---

## 2. Архитектура после всех PR-ов (мульти-канал)

```
                              Пользователи
   ┌──────────┬──────────────┬─────────┬──────────────┬──────────────┐
   │          │              │         │              │              │
┌──┴──┐   ┌───┴────┐    ┌────┴────┐ ┌──┴────────┐ ┌───┴─────────┐
│ Web │   │Telegram│    │  MAX    │ │ VK сооб-  │ │ Алиса (опц.)│
│ SPA │   │ aiogram│    │ webhook │ │ щество    │ │ Yandex Dial │
└──┬──┘   └────┬───┘    └────┬────┘ │ Callback  │ │ skill       │
   │           │             │      └─────┬─────┘ └──────┬──────┘
   │           │             │            │              │
   └───────────┴─────────────┴────────────┴──────────────┘
                             │
                  ┌──────────┴──────────────┐
                  │ FastAPI: Bot Channels   │
                  │  router (унифицирующий) │
                  │  bots/core.py           │
                  └──────────┬──────────────┘
                             │
                  ┌──────────┴──────────────┐
                  │ ChitAI Backend          │
                  │  RAG + LLM router +     │
                  │  Safety + Privacy +     │
                  │  Audit + Observability  │
                  └──────────┬──────────────┘
                             │
       ┌─────────────────────┼─────────────────────────┐
       │                     │                         │
┌──────┴────┐   ┌────────────┴────────┐   ┌────────────┴─────────┐
│PostgreSQL │   │ Object Storage (S3) │   │ Yandex Monitoring +  │
│16 + Repl  │   │ exports/tts/corpus  │   │ Cloud Logging        │
└───────────┘   └─────────────────────┘   └──────────────────────┘
```

Ключевая идея: **`backend/app/bots/core.py`** — единый абстрактный
канал:
- `BotChannel.send(user, text, buttons=...)` — отправить ответ
- `handle_user_message(channel, msg)` — общий пайплайн
- адаптеры: `telegram_bot/`, `max_bot/`, `vk_bot/`, `alice_skill/`
  переводят протокол канала в этот общий контракт.

Это значит: бизнес-логика (safety, route, mindmap) живёт в одном
месте; добавить четвёртый канал = новый адаптер + 5–10 строк
маршрутизации, без переписывания.

---

## 3. Промпты

### Универсальный пролог (склеивайте перед каждым промптом)

```
Ты работаешь в репо https://github.com/BitMagistrate/ddhlsboz.
Стек: Python 3.12 / Poetry / FastAPI / pydantic v2 для backend,
React 18 + TS + Vite + Tailwind + vitest для frontend,
GitHub Actions для CI.
Базовая ветка: main. Создавай feature-branch в формате
`devin/$(date +%s)-{slug}`.
ОБЯЗАТЕЛЬНО:
- ruff и npm run lint должны проходить локально перед PR.
- Все новые публичные функции и роуты — с типами и docstring (RU).
- Тесты пишутся в том же PR, что и фича. Coverage не должно падать ниже 70%.
- Не трогай main.py монолитом — выноси новые роуты в отдельные модули.
- Pre-commit хуки не отключай (--no-verify запрещено).
- В коммите указывай scope: `feat(prN): ...`, `fix: ...`, `test: ...`.
- Никаких секретов в коде. Все ключи — через `os.getenv` + .env.example.
- README.md и docs/ обновляются в том же PR, что и фича.
- ВАЖНО: существующий Telegram-бот (`bot/`) ломать запрещено. Любые
  изменения в нём — только через миграцию на единый bots/core.py
  с проверкой обратной совместимости (все 9 текущих тестов остаются
  и проходят).
- После пуша создавай PR через тулзу git_create_pr и жди CI.
```

---

### PR #6 — Frontend XSS hardening

```
ПРОЛОГ + ...

ЗАДАЧА: Закрыть XSS-вектор в SRS-textarea и любых пользовательских
полях, которые рендерятся обратно во фронте.

КОНТЕКСТ:
- frontend/src/App.tsx использует контролируемые inputs, но в SRS-табе
  user input (front side / back side карточки) рендерится через
  dangerouslySetInnerHTML или прямой text node без экранирования.
- Используется React 18 — обычный JSX уже экранирует, но любой
  dangerouslySetInnerHTML или markdown-render должен пройти через
  DOMPurify.

ШАГИ:
1. `cd frontend && npm install --save isomorphic-dompurify marked`.
2. Создать `frontend/src/lib/sanitize.ts`:
   - `sanitizeHtml(input: string): string` — обёртка над DOMPurify
     с allow-list тегов
     (b, i, em, strong, p, br, ul, ol, li, a[href, target=_blank, rel=noreferrer]).
   - `renderUserMarkdown(input: string): string` —
     marked.parse + sanitizeHtml.
3. Заменить ВСЕ места dangerouslySetInnerHTML на sanitizeHtml.
4. Если markdown в карточках не нужен — рендерить как plain text.
5. `frontend/src/lib/sanitize.test.ts` — 6+ кейсов:
   - <script>alert(1)</script> вырезан
   - onerror= атрибут вырезан
   - allowed: <b>, <i>, <a href="https://...">
   - blocked: <a href="javascript:alert(1)">, <iframe>, <object>
   - markdown с XSS-payload через image link нейтрализуется
6. grep по проекту: не должно остаться `dangerouslySetInnerHTML`
   без оборачивания.

КРИТЕРИИ ПРИЁМКИ:
- npm test 27 + 6 = 33 passed, npm run lint OK, npm run build OK.
- Ручной prov: вставить `<img src=x onerror=alert(1)>` в SRS textarea,
  открыть карточку — alert не появляется.

PR title: feat(pr6): frontend XSS hardening (DOMPurify on render)
```

---

### PR #7 — Rate-limit middleware + idempotency

```
ПРОЛОГ + ...

ЗАДАЧА: Защитить дорогие endpoint'ы от спама и от двойного списания
квот GigaChat / Yandex.

КОНТЕКСТ:
- /api/curator/route и /api/curator/mindmap уходят в LLM (~1₽/запрос).
- Один user_id может за минуту спалить 1000₽.
- При retry на стороне клиента LLM вызовется дважды.

ШАГИ:
1. `cd backend && poetry add slowapi`.
2. `backend/app/limits.py`:
   - Limiter на основе in-memory storage по умолчанию,
     с опциональным Redis storage (если REDIS_URL задан).
   - Лимиты:
       /api/curator/route       — 10/min, 100/day per user_id
       /api/curator/mindmap     — 20/min, 200/day per user_id
       /api/tts                 — 30/min, 300/day per user_id
       /api/curator/explain     — 30/min, 500/day per user_id
       /api/privacy/*           — 60/min per user_id
       прочие                    — 120/min per user_id
   - Ключ ограничения: user_id из JWT (после PR9) или из тела;
     если нет — IP.
3. Подключить `app.state.limiter = limiter` в main.py.
4. На 429 возвращать `{ "error": "rate_limit", "retry_after": int }`
   и заголовок Retry-After.
5. `backend/app/idempotency.py`:
   - IdempotencyStore с TTL=24h (in-memory + JSON persist через
     CHITAI_STATE_DIR).
   - Middleware читает заголовок `Idempotency-Key` (UUID v4):
     первый раз — выполняет и кэширует ответ; повторно — возвращает
     закэшированный.
   - Применять только к POST /api/curator/route, /api/curator/explain.
6. Тесты:
   - test_rate_limit_per_user, test_rate_limit_per_ip_when_no_user_id
   - test_idempotency_returns_cached, test_idempotency_different_keys
   - test_429_includes_retry_after_header

КРИТЕРИИ ПРИЁМКИ:
- 171 + 5 = 176 backend tests pass.
- hey -n 100 -c 10 на /api/curator/route → видим 429.

PR title: feat(pr7): rate-limit middleware + idempotency keys
```

---

### PR #8 — PostgreSQL 16 + Alembic + replace JSON store

```
ПРОЛОГ + ...

ЗАДАЧА: Перейти с JSON-персистентности на PostgreSQL 16. JSON-mode
оставить как fallback для local dev / тестов.

ШАГИ:
1. `poetry add sqlalchemy[asyncio]==2.0.* asyncpg alembic psycopg2-binary`.
2. `backend/app/db/`:
   - `__init__.py`, `models.py`, `session.py`.
   - Engine берёт DSN из POSTGRES_DSN. Если не задан — fallback
     на SQLite в $CHITAI_STATE_DIR/chitai.db.
   - SessionLocal — async_sessionmaker.
3. SQLAlchemy-модели:
   - users(id PK, telegram_id NULL, max_id NULL, vk_id NULL,
     sber_id NULL, created_at, deleted_at NULL)
   - privacy_consents(id PK, user_id FK, purpose, granted, ts, revoked_ts NULL)
   - privacy_history(id PK, user_id FK, payload JSONB, ts)
   - srs_cards(id PK, user_id FK, front, back, easiness, repetitions,
     interval_days, due_at)
   - refusals(id PK, user_id NULL, category, reason, request_excerpt, ts)
   - benchmark_runs(id PK, ts, metrics JSONB, notes)
   - audit_events(id PK, user_id NULL, kind, payload JSONB, ts,
     channel — telegram/max/vk/web/alice)
4. Alembic init + первая миграция. `alembic upgrade head` работает в CI.
5. Переписать стора privacy/srs/safety/audit поверх SQLAlchemy.
   Сохранить публичный API. JSON-fallback включается, если
   POSTGRES_DSN не задан.
6. CI:
   - В job backend поднимать `services.postgres: postgres:16-alpine`
     с health-check (env: POSTGRES_PASSWORD=chitai, POSTGRES_DB=chitai).
   - export POSTGRES_DSN=postgresql+asyncpg://postgres:chitai@localhost:5432/chitai
   - run alembic upgrade head перед pytest.
7. Тесты:
   - test_alembic_migration_idempotent
   - test_privacy_store_postgres_round_trip
   - test_srs_due_query_uses_index
   - test_pg_fallback_to_sqlite_when_dsn_missing

КРИТЕРИИ ПРИЁМКИ:
- 176 + 4 = 180 backend tests pass на PG в CI.
- alembic upgrade head + downgrade -1 + upgrade head: OK.

PR title: feat(pr8): PostgreSQL 16 + Alembic migrations
```

---

### PR #9 — Авторизация VK ID + Sber ID

```
ПРОЛОГ + ...

ЗАДАЧА: Перевести user_id из «передаётся в теле запроса» в JWT,
выдаваемый после OAuth2-логина через VK ID или Sber ID.

КОНТЕКСТ:
- Сейчас каждый запрос содержит user_id в теле — уязвимо
  (можно подделать и читать чужие данные).
- Два OAuth2-провайдера: VK ID и Sber ID. Маппим на vk_id / sber_id
  в users.

ШАГИ:
1. `poetry add authlib python-jose[cryptography]`.
2. `backend/app/auth/`:
   - `oauth.py`: регистрация двух клиентов (vk, sber) через Authlib.
     Conf берётся из env: VK_ID_CLIENT_ID/SECRET, SBER_ID_CLIENT_ID/SECRET.
   - `jwt.py`: issue_token(user_id, ttl=30min) + verify(token).
     HS256 на JWT_SECRET. Refresh-token TTL=30 дней.
   - `routes.py`:
       GET  /auth/{provider}/login    → redirect to OAuth.
       GET  /auth/{provider}/callback → обмен кода, JWT в cookie + body.
       POST /auth/refresh             → новый JWT по refresh.
       POST /auth/logout              → инвалидация refresh.
3. FastAPI dependency `get_current_user(jwt: HTTPBearer)`.
4. ВСЕ существующие endpoint'ы заменяют `body.user_id` на
   `Depends(get_current_user)`. user_id из body просто игнорируется.
5. Frontend:
   - /login страница с двумя кнопками: VK ID, Sber ID.
   - После callback fetchToken и сохранить в HttpOnly cookie.
   - 401 → redirect на /login.
6. В bot/ (Telegram), max_bot/, vk_bot/ (PR10/PR11) использовать
   service-account JWT с scope=bot.
7. Тесты:
   - test_jwt_issue_verify_round_trip
   - test_protected_endpoint_returns_401_without_token
   - test_oauth_callback_creates_or_updates_user (mock)
   - test_user_id_from_body_is_ignored
   - frontend: test_login_redirect_when_401

КРИТЕРИИ ПРИЁМКИ:
- 180 + 5 = 185 backend tests + frontend test pass.
- Запрос на /api/curator/route без токена → 401.

PR title: feat(pr9): VK ID + Sber ID OAuth2 + JWT auth
```

---

### PR #10 — Мульти-канальное ядро ботов + MAX-адаптер ⭐

```
ПРОЛОГ + ...

ЗАДАЧА: Ввести единое ядро для всех каналов
(`backend/app/bots/core.py`), мигрировать существующего Telegram-бота
на это ядро БЕЗ изменения внешнего поведения, и добавить второй
адаптер — MAX.

КОНТЕКСТ:
- Telegram-бот (`bot/`) на aiogram — оставляем работающим. Мигрируем
  логику в bots/telegram_bot/, но внешнее поведение не меняем.
- MAX API: HTTPS на https://platform-api.max.ru.
  Авторизация — заголовок `Authorization: <access_token>`.
  Получение апдейтов в DEV — Long Polling GET /updates;
  в PROD — webhook (рекомендация офиц. доков).
  Отправка: POST /messages?user_id={uid} (или ?chat_id={cid}),
  body { text, attachments, format: "markdown"|"html" }.
  Inline keyboards: attachments[].type="inline_keyboard",
  payload.buttons = [[{type:"link"|"callback"|"open_app"}]].
  Для Python нет офиц. SDK — пишем тонкий httpx-клиент.

СТРУКТУРА ПОСЛЕ PR:
backend/app/bots/
├── __init__.py
├── core.py               # абстракция канала
├── pipeline.py           # safety → route/mindmap → ответ
├── telegram_bot/         # МИГРИРОВАН: тонкая обёртка над core
│   ├── adapter.py
│   └── tests/
├── max_bot/              # НОВЫЙ
│   ├── client.py
│   ├── webhook.py
│   ├── handlers.py
│   ├── keyboards.py
│   └── tests/

ШАГИ:
1. backend/app/bots/core.py:
   - класс BotMessage(channel, user, text, attachments?)
   - класс BotResponse(text, buttons=[], format="markdown")
   - protocol BotChannel:
       async def send(self, user_ref, response: BotResponse)
       async def set_webhook(self, url, secret) (опционально)
   - функция handle_user_message(channel: BotChannel, msg: BotMessage):
     1) safety.screen(msg.text)
     2) если refusal — отправить отказ с категорией
     3) иначе вызвать /api/curator/route внутренним вызовом
        (без HTTP, через сервисный слой)
     4) собрать BotResponse с inline-кнопками для листания недель
     5) channel.send(user_ref, response)
2. Миграция Telegram:
   - Создать backend/app/bots/telegram_bot/adapter.py:
     класс TelegramChannel(BotChannel) на базе текущего aiogram-кода.
   - Старая логика из bot/ переезжает: handlers становятся тонкими
     обёртками, всё содержательное — в core.handle_user_message.
   - Все 9 существующих тестов Telegram-бота остаются и проходят.
3. backend/app/bots/max_bot/client.py — MaxClient:
   - send_message(user_id, text, *, format="markdown", buttons=None,
     notify=True, idempotency_key=None) → Message
   - get_me() → BotInfo
   - set_my_commands(commands)
   - set_webhook(url, secret) → bool
   - retry: tenacity, exp backoff, 3 попытки
   - rate-limit: внутренний лимитер 30 msg/min
4. backend/app/bots/max_bot/webhook.py:
   - POST /max/webhook принимает Update от MAX.
   - Проверка X-MAX-Webhook-Secret против MAX_WEBHOOK_SECRET.
   - Маппинг update → BotMessage → core.handle_user_message.
5. backend/app/bots/max_bot/handlers.py:
   - on_start(ctx): приветствие + меню (inline_keyboard).
   - on_message(ctx): прокидывает в core.handle_user_message
     через MaxChannel.
   - on_callback(ctx): payload "route:next:<uuid>" — листание;
     "tts:<fragment_id>" — озвучка через SpeechKit.
6. backend/app/bots/max_bot/keyboards.py — фабрики клавиатур.
7. backend/app/main.py подключает max_bot.webhook.router.
8. Lifespan: если MAX_BOT_TOKEN задан — MaxClient.set_webhook(
       url=f"{PUBLIC_BASE_URL}/max/webhook",
       secret=MAX_WEBHOOK_SECRET,
   ).
9. ENV:
   - TELEGRAM_BOT_TOKEN (как было)
   - MAX_BOT_TOKEN, MAX_WEBHOOK_SECRET, MAX_API_BASE
   - PUBLIC_BASE_URL
10. Тесты:
    - core: test_pipeline_refuses_extremism, test_pipeline_routes_to_curator
    - telegram: 9 существующих + 2 новых
      (test_adapter_calls_core, test_telegram_buttons_built)
    - max client: test_send_message_uses_authorization_header (respx),
      test_retries_on_5xx, test_rejects_4xx_without_retry
    - max webhook: test_rejects_bad_secret, test_dispatches_message_event
    - max handlers: test_start_returns_keyboard, test_message_routes,
      test_callback_route_next, test_callback_tts
11. docs/bots.md: общее описание core + MAX setup.

КРИТЕРИИ ПРИЁМКИ:
- 185 + 13 = 198 backend tests pass.
- Telegram бот реально работает после миграции (ручная проверка
  /start → ответ).
- curl GET https://platform-api.max.ru/me с MAX_BOT_TOKEN возвращает
  BotInfo.
- В MAX отправка сообщения боту → ответ, кнопки навигации работают.

PR title: feat(pr10): unified bot core + MAX channel (Telegram migrated)
```

---

### PR #11 — VK Сообщества (Callback API)

```
ПРОЛОГ + ...

ЗАДАЧА: Добавить третий канал — бот в сообществе VK через
VK Callback API (`api.vk.com`, methods.execute / messages.send,
events приходят на наш webhook).

КОНТЕКСТ:
- VK Bot API — это Bot API «для сообществ»: пользователь пишет
  в чат сообщества, VK шлёт нам событие message_new на webhook.
- Авторизация: токен сообщества (VK_GROUP_TOKEN, scope=messages,photos).
- API base: https://api.vk.com/method/, версия v=5.199.
- Callback API confirmation: при первом подключении VK шлёт POST
  с type=confirmation; нужно ответить строкой = VK_CONFIRMATION_CODE.
- Проверка подлинности — поле `secret` в каждом событии должно
  совпадать с VK_SECRET_KEY (настройка в Callback API).
- Ответ всем event'ам — text/plain "ok" в течение 25 секунд.

СТРУКТУРА:
backend/app/bots/vk_bot/
├── client.py        # обёртка над messages.send / users.get
├── webhook.py       # POST /vk/webhook с verify + dispatch
├── handlers.py      # on_message_new, on_message_event
├── keyboards.py     # VK keyboard JSON
└── tests/

ШАГИ:
1. `poetry add vk-api` (или собственный httpx-клиент — лёгкий и без
   зависимости от стороннего пакета).
2. backend/app/bots/vk_bot/client.py — VkClient:
   - send_message(user_id, text, *, keyboard=None, payload=None,
     random_id=...) → int
   - users_get(ids) → list[User]
   - retry tenacity 3x, internal rate-limit 20 req/sec.
3. backend/app/bots/vk_bot/webhook.py:
   - POST /vk/webhook принимает Update.
   - Если type=="confirmation" → return PlainTextResponse(VK_CONFIRMATION_CODE).
   - Проверка secret == VK_SECRET_KEY (иначе 403).
   - type=="message_new" → BotMessage → core.handle_user_message
     через VkChannel.
   - type=="message_event" (нажатие callback-кнопки) → handlers.
   - В конце return PlainTextResponse("ok").
4. backend/app/bots/vk_bot/keyboards.py:
   - Сборка JSON в формате VK:
       {"one_time": false, "buttons": [[{"action": {...}, "color": "primary"}]]}
   - Кнопки: text-callback (с payload), open_link.
5. VkChannel(BotChannel):
   - send(user_ref, response): client.send_message(...).
6. Lifespan: проверка соединения via users.get(1) — если ответ
   не 200 → лог, но не падать.
7. ENV:
   - VK_GROUP_TOKEN, VK_GROUP_ID, VK_CONFIRMATION_CODE, VK_SECRET_KEY
   - VK_API_VERSION (default 5.199)
8. Тесты:
   - test_confirmation_returns_code
   - test_rejects_bad_secret_returns_403
   - test_message_new_routes_to_core
   - test_callback_event_navigates_route
   - test_keyboard_payload_serialized_correctly
   - test_client_send_message_uses_access_token
9. docs/bots.md обновить — VK setup и Callback API confirmation.

КРИТЕРИИ ПРИЁМКИ:
- 198 + 6 = 204 backend tests pass.
- В сообществе VK Callback API статус «Подтверждён».
- Реальная отправка сообщения боту в сообщество → ответ за <2 сек.

PR title: feat(pr11): VK communities bot adapter (Callback API)
```

---

### PR #12 — Yandex Cloud деплой

```
ПРОЛОГ + ...

ЗАДАЧА: Развернуть в Yandex Cloud production-копию: Compute Cloud
(Docker), Managed PostgreSQL 16, Object Storage для статики/корпуса/TTS,
Cloud DNS, Application Load Balancer с TLS, регистрация webhook'ов
для всех каналов.

ШАГИ:
1. infra/terraform/ — IaC:
   - main.tf, vpc.tf (2 подсети, 2 AZ).
   - compute.tf: 1× VM (4 vCPU / 8 GB / 50 GB SSD / Ubuntu 22.04),
     cloud-init: docker, docker-compose, fail2ban.
   - postgres.tf: yandex_mdb_postgresql_cluster
     (master + reserve replica, PG 16, бэкапы 7 дней).
   - s3.tf: chitai-corpus, chitai-exports, chitai-tts-cache.
   - alb.tf: Application Load Balancer с Let's Encrypt для chitai.example.
   - dns.tf: CNAME chitai.example → ALB.
   - outputs.tf: postgres_dsn, alb_url, bucket_names.
2. infra/docker/Dockerfile.backend (Python 3.12-slim + Poetry).
3. infra/docker/Dockerfile.frontend (node 22 build → nginx).
4. infra/docker-compose.yml — backend + nginx-proxy.
5. infra/scripts/deploy.sh:
   - terraform init/plan/apply
   - scp docker-compose.yml на VM
   - docker compose pull && docker compose up -d
   - smoke test: curl https://chitai.example/healthz
   - регистрация webhook MAX (set_webhook),
     регистрация Callback API VK через консоль (полу-автоматом).
6. .github/workflows/deploy.yml — на push в main:
   - build & push image в Yandex Container Registry
   - ssh deploy.sh
7. README.md — раздел «Развёртывание».

КРИТЕРИИ ПРИЁМКИ:
- terraform apply без ошибок (на staging-folder).
- https://chitai.example/healthz возвращает 200.
- Бэкапы PostgreSQL включены и проверены восстановлением.
- /max/webhook и /vk/webhook доступны извне и сами зарегистрировались.

PR title: feat(pr12): Yandex Cloud production deployment (Terraform)
```

---

### PR #13 — Корпус 100+ произведений

```
ПРОЛОГ + ...

ЗАДАЧА: Расширить literature corpus с ~10 до 100+ произведений
(программа ЕГЭ + школьная программа 5–11 кл + 20 произведений
региональной литературы по выбору).

ШАГИ:
1. corpus/sources.yaml — список (автор, название, период, источник).
2. corpus/fetch.py — скачивание с https://ilibrary.ru,
   https://az.lib.ru, https://rvb.ru (только public domain до 1953 г.
   и явно permissive-источники).
3. corpus/clean.py — strip HTML, фикс мягких переносов, нормализация
   ё, удаление сносок.
4. backend/app/corpus.py — индексация всех 100+ в BM25 + dense
   (Yandex Embeddings или ru-sbert).
5. tests/test_corpus_size_floor.py — assert len(books) >= 100.
6. backend/app/benchmark.py — расширить эталон до 200 запросов
   (5 типов: сюжет / автор / эпоха / тема / цитата) × 40 произведений.
7. CI: гейт MRR ≥ 0.92, Recall@5 ≥ 0.95, P@5 ≥ 0.55.

КРИТЕРИИ ПРИЁМКИ:
- 204 + 1 = 205 tests pass.
- benchmark.json: P@5 ≥ 0.55, MRR ≥ 0.92, Recall@5 ≥ 0.95.
- В UI выбор произведения: 100+ позиций, поиск по автору работает.

PR title: feat(pr13): expand corpus to 100+ works + tighten benchmark
```

---

### PR #14 — Circuit breaker + Yandex Monitoring

```
ПРОЛОГ + ...

ЗАДАЧА: Сделать LLM-роутер устойчивым к сбоям и завести метрики
в Yandex Monitoring.

ШАГИ:
1. `poetry add purgatory yandex-cloud-py` (или httpx-based custom CB).
2. backend/app/llm/circuit.py — CircuitBreaker per-provider с
   состояниями closed → open → half-open. Открывается после 5 ошибок
   за 60 секунд. half-open после 30 секунд.
3. Обернуть GigaChatProvider и YandexProvider в circuit-breaker
   на уровне router'а.
4. backend/app/observability.py:
   - Yandex Monitoring writer: каждые 30 секунд push'ит метрики:
     llm_requests_total, llm_latency_p50/p95, llm_circuit_state,
     rag_p_at_5_last, refusal_rate, active_users,
     bot_messages_total{channel="telegram"|"max"|"vk"|"web"|"alice"}.
   - Cloud Logging structured logs (JSON, поле channel).
5. backend/app/main.py — middleware request_id (UUID v4) проброс
   в headers и логи.
6. Тесты:
   - test_circuit_opens_after_5_failures
   - test_circuit_half_open_after_30s
   - test_router_falls_back_when_first_circuit_open
   - test_metrics_pushed_to_monitoring_endpoint (mock)
   - test_request_id_middleware_propagates

КРИТЕРИИ ПРИЁМКИ:
- 205 + 5 = 210 tests pass.
- Yandex Monitoring дашборд: 6 графиков, обновляются.

PR title: feat(pr14): LLM circuit breaker + Yandex Monitoring observability
```

---

### PR #15 — Юридический ОПД (auto-Roskomnadzor)

```
ПРОЛОГ + ...

ЗАДАЧА: Сделать страницу /privacy/legal-status, где автогенерируется
заявка-уведомление в Роскомнадзор как ОПД (152-ФЗ ст. 22).

ШАГИ:
1. backend/app/privacy/legal.py:
   - generate_roskomnadzor_form(org: dict) -> bytes (PDF).
   - reportlab или weasyprint.
   - Поля: ИНН, ОГРН, юр. адрес, цели обработки, категории субъектов,
     методы защиты, даты начала.
2. backend/app/main.py:
   - GET /privacy/legal/template?org_inn=...&org_name=... → PDF.
3. frontend/PrivacyLegalTab — форма + кнопка «скачать заявку».
4. docs/legal/checklist.md — чек-лист подачи в Роскомнадзор онлайн.
5. Тесты:
   - test_pdf_form_contains_all_required_fields
   - test_pdf_renders_unicode_correctly

КРИТЕРИИ ПРИЁМКИ:
- 210 + 2 = 212 tests pass.
- Скачанная заявка валидируется на pd.rkn.gov.ru без правок.

PR title: feat(pr15): Roskomnadzor ОПД notification auto-generator
```

---

### PR #16 — Mini-app внутри MAX

```
ПРОЛОГ + ...

ЗАДАЧА: Сделать MAX WebApp (mini-app) с кнопкой open_app в боте,
чтобы пользователь мог пройти куратор-флоу прямо в MAX.

ШАГИ:
1. frontend/src/maxapp/ — отдельный entry-point Vite (multi-page):
   - main.tsx инициализирует MAX Bridge: window.MaxBridge.ready().
   - Получаем initData из bridge.getInitData().
   - Отправляем на /api/maxapp/auth для верификации
     (HMAC по MAX_BOT_TOKEN, алгоритм описан в MAX docs).
2. backend/app/maxapp/auth.py — verify_init_data(payload, token) → bool.
3. backend/app/maxapp/routes.py:
   - POST /api/maxapp/auth → JWT (как в PR9).
4. В bots/max_bot/keyboards.py добавить кнопку open_app:
   - {type:"open_app", text:"Открыть в MAX",
      payload:"https://chitai.example/maxapp"}
5. Тесты:
   - test_verify_init_data_valid
   - test_verify_init_data_invalid_signature
   - test_maxapp_jwt_issued_on_valid_initdata

КРИТЕРИИ ПРИЁМКИ:
- 212 + 3 = 215 backend tests pass.
- В мобильном клиенте MAX нажатие на кнопку открывает mini-app
  без перелогина.

PR title: feat(pr16): MAX mini-app integration (WebApp + Bridge)
```

---

### PR #17 (опционально) — Алиса Яндекса (голосовой канал)

```
ПРОЛОГ + ...

ЗАДАЧА: Добавить четвёртый канал — голосовой навык в Яндекс.Диалогах.
Получаем доступ через Яндекс Станцию и приложение Алиса.

КОНТЕКСТ:
- Платформа: https://dialogs.yandex.ru/developer.
- Контракт: Alice POST'ит JSON на наш webhook, ждёт JSON-ответ
  до 3 секунд.
- Структура запроса: { "request": { "command": "...", "nlu": {...} },
  "session": {...}, "version": "1.0" }.
- Ответ: { "response": { "text": "...", "tts": "...",
  "buttons": [...] }, "session": {...}, "version": "1.0" }.
- Авторизация — нет (Alice верифицирует по skill_id в session).

СТРУКТУРА:
backend/app/bots/alice_skill/
├── webhook.py       # POST /alice/webhook
├── handlers.py      # обработчики интентов
├── nlu.py           # маппинг сырого text → намерение
└── tests/

ШАГИ:
1. backend/app/bots/alice_skill/webhook.py:
   - POST /alice/webhook принимает JSON.
   - Проверка session.skill_id == ALICE_SKILL_ID.
   - command → BotMessage → core.handle_user_message
     через AliceChannel.
   - Особенность: ответ должен укладываться в 3 секунды.
     Поэтому LLM-маршрут заменяем на «короткий ответ» mode
     (1 рекомендация), полный route только текстом со ссылкой.
2. AliceChannel.send: формирует ответ с tts (озвучивание Alice'ой).
   Длинные ответы режем на 1024 символа.
3. ENV:
   - ALICE_SKILL_ID
4. Тесты:
   - test_webhook_rejects_wrong_skill_id
   - test_simple_command_routes_to_curator_short_mode
   - test_response_under_3s_budget (mock LLM с задержкой 5s →
     должен таймаутить и отвечать «секундочку…»)
   - test_response_format_matches_alice_contract

КРИТЕРИИ ПРИЁМКИ:
- 215 + 4 = 219 tests pass.
- В консоли разработчика Яндекс.Диалогов навык успешно проходит
  модерацию: «Алиса, запусти ЧитАИ» → ответ.

PR title: feat(pr17): Yandex Alice voice skill (optional 4th channel)
```

---

## 4. Порядок и зависимости

```
PR6 (XSS) ────┐
              │
PR7 (Limits) ─┤
              │
PR8 (PG) ─────┼──→ PR9 (Auth) ──┬──→ PR10 (core + MAX) ─┐
                                │                       │
                                └──→ PR11 (VK) ─────────┤
                                                        │
                                       ┌────────────────┤
                                       │                │
                              PR12 (Yandex Cloud)       │
                                       │                │
                              PR13 (Corpus 100+)        │
                                       │                │
                              PR14 (Circuit + Mon) ←────┘
                                       │
                              PR15 (ОПД)
                                       │
                              PR16 (MAX mini-app)
                                       │
                              PR17 (Alice, опц.)
```

Рекомендуемая очередь: **PR6 → PR7 → PR8 → PR9 → PR10 → PR11 →
PR12 → PR13 → PR14 → PR15 → PR16 → (PR17)**.

Запускайте по одному промпту, дожидайтесь зелёного CI, мержите,
и только после этого запускайте следующий.

---

## 5. Финальный чек-лист «100/100»

- [ ] PR6 merged: XSS hardening + 6 тестов
- [ ] PR7 merged: rate-limit + idempotency + 5 тестов
- [ ] PR8 merged: Postgres + Alembic + 4 тестов + CI gate alembic upgrade
- [ ] PR9 merged: VK ID + Sber ID + JWT + 5 тестов
- [ ] PR10 merged: единое ядро ботов + MAX, **Telegram продолжает работать**, +13 тестов
- [ ] PR11 merged: VK Сообщества канал, +6 тестов
- [ ] PR12 merged: Yandex Cloud, https://chitai.example отвечает
- [ ] PR13 merged: 100+ произведений, P@5 ≥ 0.55
- [ ] PR14 merged: circuit breaker, 6 графиков в Yandex Monitoring
- [ ] PR15 merged: ОПД заявка скачивается
- [ ] PR16 merged: MAX mini-app открывается
- [ ] PR17 (опц.) merged: голосовой навык Алисы

После всех 11 (+1) PR-ов:
- ~219 тестов
- Все CI-jobs зелёные
- Production развёрнут, домен резолвится
- **4 канала**: Telegram, MAX, VK Сообщества, (опц.) Алиса +
  Web SPA + MAX mini-app
- Корпус 100+, метрики реальные
- Заявка в Роскомнадзор подана

Реалистичная оценка: **97–98 / 100**.

---

## 6. Единая команда «дай Devin'у этот промпт»

Скопируйте этот блок в чат Devin для запуска первого PR:

```
Прочитай chitai_finishing_prompts.md (приложу). Открой файл, найди
раздел «PR #6 — Frontend XSS hardening». Выполни весь промпт оттуда
с прологом, создай PR на main. Жди CI. После того как CI зелёный,
напиши мне «PR #6 готов» и жди подтверждения от меня перед PR #7.
```

После каждого зелёного CI отвечайте «продолжай PR #N+1» — и так до
PR #16 (или PR #17, если хотите голос). На каждом этапе у вас будет
рабочий мерж и возможность проверить вживую в Telegram, MAX, VK,
а потом и в Алисе.
