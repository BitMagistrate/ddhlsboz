# ЧитАИ — Developer Kit (для будущих PR #6–#17)

> Этот документ — компаньон к `chitai_finishing_prompts.md`.
> Цель: дать готовые куски кода / конфиги / шпаргалки, которые
> любая сессия Devin / Cursor / разработчика может скопировать
> as-is, чтобы не терять время на рутину. Всё проверено против
> текущего состояния репо (после PR #5).

---

## 1. AGENTS.md (положить в корень репо одним из первых PR'ов)

> Создаётся в **PR #6** (или отдельным маленьким PR-0). Каждая
> следующая Devin/Cursor-сессия читает его автоматически и
> подхватывает конвенции — не нужно повторять их в каждом промпте.

```markdown
# AGENTS.md

> Инструкции для AI-ассистентов (Devin, Cursor, Codex), работающих
> в этом репозитории. Перед любым изменением — прочитать целиком.

## Стек

- Python 3.12 + Poetry, FastAPI, pydantic v2 (backend)
- React 18 + TypeScript + Vite + Tailwind + vitest (frontend)
- aiogram 3 (Telegram bot — оставлен рабочим, мигрирован
  в backend/app/bots/telegram_bot/)
- httpx + tenacity (MAX, VK, Alice — все через unified core)
- pytest + respx + pytest-asyncio (тесты)
- ruff + mypy (linting)
- GitHub Actions (CI: lint + tests + bandit + benchmark gate)

## Правила

1. Базовая ветка — `main`. Feature-branch: `devin/$(date +%s)-{slug}`.
2. Не амендить коммиты, не push --force в main, не --no-verify.
3. ruff и `npm run lint` проходят локально перед `git push`.
4. Все публичные функции и роуты — с типами и docstring (RU).
5. Тесты пишутся в том же PR. Coverage ≥ 70% (backend), не падает.
6. Никаких секретов в коде — только через `os.getenv` + `.env.example`.
7. Любой новый модуль для бот-канала — это **адаптер** под
   `backend/app/bots/core.py`, бизнес-логика в core, не в адаптере.
8. **Telegram-бот ломать запрещено.** При миграции/изменении —
   существующие 9 тестов в `bot/tests/` (или их перенесённые
   аналоги в `backend/app/bots/telegram_bot/tests/`) должны
   проходить.
9. CI failure = блокер мержа. Если CI красный — чинить PR, не мержить.
10. На каждый PR — обновление `README.md` или `docs/` (если фича
    требует объяснения).
11. После пуша — git_create_pr → git_pr_checks → ждать зелёного CI.

## Команды

```bash
# Backend
cd backend && poetry install
poetry run ruff check app
poetry run pytest -q
poetry run pytest --cov=app --cov-report=term-missing --cov-fail-under=70

# Frontend
cd frontend && npm install
npm run lint
npm test
npm run build

# Bot (legacy bot/, до PR10) — оставлен для совместимости
cd bot && pip install -r requirements.txt
ruff check .
pytest -q

# Бенчмарк (CI gate: MRR ≥ 0.85, Recall@5 ≥ 0.90 на текущем корпусе;
# после PR13: P@5 ≥ 0.55, MRR ≥ 0.92, Recall@5 ≥ 0.95)
cd backend && poetry run python -m app.benchmark > benchmark.json

# Persistence (опц.)
export CHITAI_STATE_DIR=/tmp/chitai-state

# Postgres (после PR8)
export POSTGRES_DSN=postgresql+asyncpg://postgres:chitai@localhost:5432/chitai
poetry run alembic upgrade head
```

## Структура

```
backend/
├── app/
│   ├── main.py                 # FastAPI app, lifespan
│   ├── rag.py                  # Hybrid retrieval (BM25 + dense + reranker)
│   ├── safety.py               # Pre-LLM screening
│   ├── audit.py                # Append-only audit log
│   ├── privacy.py              # 152-ФЗ (consent / export / forget)
│   ├── observability.py        # Метрики + structured logs
│   ├── state.py                # JSON persistence backend (CHITAI_STATE_DIR)
│   ├── benchmark.py            # RAG-оценка
│   ├── llm/
│   │   ├── router.py
│   │   ├── gigachat.py
│   │   ├── yandex.py
│   │   └── mock.py
│   ├── search/
│   │   └── hybrid.py
│   ├── bots/                   # ← создаётся в PR10
│   │   ├── core.py             # абстракция канала
│   │   ├── pipeline.py         # safety → route/mindmap → response
│   │   ├── telegram_bot/       # МИГРИРОВАН из bot/
│   │   ├── max_bot/            # PR10
│   │   ├── vk_bot/             # PR11
│   │   └── alice_skill/        # PR17 (опц.)
│   └── auth/                   # ← PR9 (VK ID + Sber ID + JWT)
└── tests/

frontend/
├── src/
│   ├── App.tsx
│   ├── lib/
│   │   └── sanitize.ts         # ← PR6 (DOMPurify)
│   └── maxapp/                 # ← PR16 (MAX mini-app)

bot/                            # legacy, удалится после PR10 миграции
infra/                          # ← PR12 (Terraform + Docker)
corpus/                         # ← PR13 (100+ произведений)
docs/
.github/workflows/
```

## Что нельзя делать (anti-patterns)

- ❌ Хардкодить `verify_ssl=False` без env-переключателя.
- ❌ Хранить state в памяти без JSON / Postgres-fallback.
- ❌ Делать `dangerouslySetInnerHTML` без `sanitizeHtml()` (см. PR6).
- ❌ Разносить бизнес-логику по адаптерам ботов — она в `bots/pipeline.py`.
- ❌ Использовать `Any`, `getattr`, `setattr` для обхода типов.
- ❌ Вмешиваться в `bot/` без переноса в `bots/telegram_bot/`.
- ❌ Менять схему БД без alembic-миграции (после PR8).
- ❌ Push'ить корпус (corpus/*.txt) в git — он лежит в S3 / lfs.

## Что нужно делать (best practices)

- ✅ В каждом PR — RU docstring + типы.
- ✅ Любой LLM-вызов проходит через `llm.router` (никаких прямых
  обращений к gigachat/yandex из feature-кода).
- ✅ Любой выходящий HTTP-вызов — через `httpx.AsyncClient` +
  `tenacity` retry + структурированное логирование.
- ✅ Любая запись персональных данных пользователя проходит через
  `privacy` модуль (consent + audit).
- ✅ Все новые env-переменные → `.env.example` + раздел в `README.md`.
```

---

## 2. .env.example (полный, со всеми ключами на все 12 PR'ов)

> Создаётся в PR #6 одним файлом, потом дополняется по мере PR.

```bash
# === Core ===
ENV=local                                # local | staging | production
PUBLIC_BASE_URL=https://chitai.example   # для регистрации webhook'ов

# === LLM провайдеры ===
GIGACHAT_AUTHORIZATION_KEY=              # Ключ авторизации (не client_id+secret!)
GIGACHAT_VERIFY_SSL=true                 # false только для local
GIGACHAT_CA_BUNDLE=/etc/ssl/min_digital.pem  # cert Минцифры

YANDEX_API_KEY=                          # IAM API key
YANDEX_FOLDER_ID=                        # Cloud folder
YANDEX_SPEECHKIT_API_KEY=                # SpeechKit отдельный

# === Persistence ===
CHITAI_STATE_DIR=/var/lib/chitai/state   # JSON fallback
POSTGRES_DSN=                            # PR8: postgresql+asyncpg://...

# === Auth (PR9) ===
JWT_SECRET=                              # openssl rand -hex 64
VK_ID_CLIENT_ID=                         # https://id.vk.com — для логина юзеров
VK_ID_CLIENT_SECRET=
SBER_ID_CLIENT_ID=                       # https://developer.sberbank.ru
SBER_ID_CLIENT_SECRET=

# === Bots (PR10–11, 17) ===
TELEGRAM_BOT_TOKEN=                      # уже есть, BotFather
MAX_BOT_TOKEN=                           # max.ru/MasterBot
MAX_WEBHOOK_SECRET=                      # openssl rand -hex 32
MAX_API_BASE=https://platform-api.max.ru
VK_GROUP_TOKEN=                          # ВНИМАНИЕ: НЕ путать с VK_ID_CLIENT_*
VK_GROUP_ID=                             # ID сообщества
VK_CONFIRMATION_CODE=                    # из Callback API сообщества
VK_SECRET_KEY=                           # вы задаёте сами в Callback API
VK_API_VERSION=5.199
ALICE_SKILL_ID=                          # PR17 (опц.)
ALICE_OAUTH_TOKEN=                       # PR17 (опц.)

# === Rate-limit / idempotency (PR7) ===
REDIS_URL=                               # опц., если нет — in-memory

# === Cloud / IaC (PR12) ===
YC_TOKEN=                                # IAM token для Terraform
YC_CLOUD_ID=
YC_FOLDER_ID=
S3_BUCKET_CORPUS=chitai-corpus
S3_BUCKET_EXPORTS=chitai-exports
S3_BUCKET_TTS=chitai-tts-cache
S3_ACCESS_KEY_ID=
S3_SECRET_ACCESS_KEY=

# === Observability (PR14) ===
YANDEX_MONITORING_FOLDER=
LOG_LEVEL=INFO

# === Legal (PR15) ===
ORG_INN=
ORG_OGRN=
ORG_NAME=
ORG_ADDRESS=
```

---

## 3. Скелет `backend/app/bots/core.py` (создаётся в PR #10)

```python
"""Унифицированное ядро для всех бот-каналов.

Все бот-адаптеры (Telegram, MAX, VK, Alice) реализуют BotChannel
и делегируют обработку входящих сообщений сюда. Это гарантирует:
- бизнес-логика (safety, route, mindmap) живёт в одном месте;
- добавление нового канала = новый адаптер + 5–10 строк маршрутизации;
- одинаковая аудит-цепочка на всех каналах.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Protocol, runtime_checkable

ChannelName = Literal["telegram", "max", "vk", "alice", "web"]


@dataclass(frozen=True, slots=True)
class BotMessage:
    """Нормализованное входящее сообщение от пользователя."""

    channel: ChannelName
    user_ref: str  # str(user_id), формат свой у каждого канала
    text: str
    locale: str = "ru"
    raw: dict | None = None  # сырой payload канала (для отладки)


@dataclass(slots=True)
class BotButton:
    """Кнопка inline-клавиатуры в нейтральном формате."""

    text: str
    kind: Literal["callback", "link", "open_app"] = "callback"
    payload: str | None = None  # для callback — данные; для link/open_app — URL


@dataclass(slots=True)
class BotResponse:
    """Нормализованный ответ бота."""

    text: str
    buttons: list[list[BotButton]] = field(default_factory=list)
    format: Literal["plain", "markdown", "html"] = "markdown"
    tts: str | None = None  # озвучка (Alice + опц. SpeechKit для MAX)


@runtime_checkable
class BotChannel(Protocol):
    """Протокол, который реализует каждый адаптер."""

    name: ChannelName

    async def send(self, user_ref: str, response: BotResponse) -> None:
        """Отправить ответ пользователю."""
        ...

    async def set_webhook(self, url: str, secret: str) -> bool:
        """Зарегистрировать webhook (вызывается на старте, опц.)."""
        ...


async def handle_user_message(
    channel: BotChannel,
    msg: BotMessage,
) -> BotResponse:
    """Главный пайплайн: safety → route → response.

    Адаптеры вызывают эту функцию, получают BotResponse и отправляют
    через channel.send().

    Шаги:
    1. safety.screen(text) — pre-LLM модерация
    2. если refusal — вернуть отказ с категорией
    3. иначе вызвать curator.route() — ВНУТРЕННИЙ сервис, без HTTP
    4. собрать BotResponse с inline-кнопками для листания
    5. audit.log_event(channel=channel.name, ...) — обязательно
    """
    # TODO: реализуется в PR10. Псевдокод:
    #
    # from app import safety, audit
    # from app.curator import route_service
    #
    # screen = safety.screen(msg.text)
    # if not screen.ok:
    #     audit.log_refusal(user=msg.user_ref, channel=msg.channel,
    #                       category=screen.category)
    #     return BotResponse(text=screen.refusal_text, buttons=[])
    #
    # plan = await route_service.build_route(
    #     user_id=msg.user_ref, query=msg.text, channel=msg.channel,
    # )
    # buttons = [[
    #     BotButton(text="Неделя 2", kind="callback", payload=f"route:next:{plan.id}"),
    #     BotButton(text="Озвучить", kind="callback", payload=f"tts:{plan.fragment_id}"),
    # ]]
    # audit.log_event(user=msg.user_ref, channel=msg.channel,
    #                 kind="route", payload=plan.dict())
    # return BotResponse(text=plan.markdown, buttons=buttons)
    raise NotImplementedError("Implement in PR #10")
```

---

## 4. Скелет адаптера MAX (PR #10)

```python
# backend/app/bots/max_bot/client.py
"""Тонкий httpx-клиент для MAX Bot API.

Документация: https://dev.max.ru/docs-api
Аутентификация: заголовок `Authorization: <access_token>`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential


@dataclass(slots=True)
class MaxMessage:
    message_id: str
    user_id: int
    text: str


class MaxClient:
    def __init__(
        self,
        token: str | None = None,
        base_url: str | None = None,
        timeout: float = 10.0,
    ) -> None:
        self.token = token or os.environ["MAX_BOT_TOKEN"]
        self.base_url = base_url or os.getenv(
            "MAX_API_BASE", "https://platform-api.max.ru"
        )
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=timeout,
            headers={"Authorization": self.token},
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    @retry(
        retry=retry_if_exception_type(httpx.HTTPStatusError),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        reraise=True,
    )
    async def send_message(
        self,
        user_id: int,
        text: str,
        *,
        format: str = "markdown",
        buttons: list | None = None,
        notify: bool = True,
        idempotency_key: str | None = None,
    ) -> MaxMessage:
        payload: dict = {"text": text, "format": format, "notify": notify}
        if buttons:
            payload["attachments"] = [
                {"type": "inline_keyboard", "payload": {"buttons": buttons}}
            ]
        headers = {}
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        r = await self._client.post(
            "/messages",
            params={"user_id": user_id},
            json=payload,
            headers=headers,
        )
        # 5xx → retry; 4xx → подняли наружу без ретрая
        if 500 <= r.status_code < 600:
            r.raise_for_status()
        if r.status_code >= 400:
            raise httpx.HTTPStatusError(
                f"MAX rejected: {r.text}",
                request=r.request,
                response=r,
            )
        data = r.json()
        return MaxMessage(
            message_id=data["message"]["mid"],
            user_id=user_id,
            text=text,
        )

    async def get_me(self) -> dict:
        r = await self._client.get("/me")
        r.raise_for_status()
        return r.json()

    async def set_webhook(self, url: str, secret: str) -> bool:
        r = await self._client.post(
            "/subscriptions",
            json={"url": url, "secret": secret},
        )
        r.raise_for_status()
        return r.json().get("success", False)
```

---

## 5. Test fixtures cheatsheet

> Все эти фикстуры можно положить в `backend/tests/conftest.py` или в
> `bots/<channel>/tests/conftest.py`. Использует `respx` для httpx-моков.

### 5.1. MAX webhook fixture

```python
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def max_update_message():
    return {
        "update_type": "message_created",
        "timestamp": 1730000000,
        "message": {
            "sender": {"user_id": 12345, "name": "Иван"},
            "recipient": {"chat_id": 12345, "chat_type": "dialog"},
            "body": {"mid": "msg-1", "seq": 1, "text": "Привет"},
        },
    }


def test_max_webhook_dispatches(client: TestClient, max_update_message):
    r = client.post(
        "/max/webhook",
        json=max_update_message,
        headers={"X-MAX-Webhook-Secret": "test-secret"},
    )
    assert r.status_code == 200
```

### 5.2. MAX client fixture (respx-mock)

```python
import httpx
import pytest
import respx
from app.bots.max_bot.client import MaxClient


@pytest.fixture
async def max_client():
    client = MaxClient(token="test-token", base_url="https://platform-api.max.ru")
    yield client
    await client.aclose()


@pytest.mark.asyncio
async def test_send_message_uses_authorization_header(max_client):
    with respx.mock(base_url="https://platform-api.max.ru") as m:
        route = m.post("/messages", params={"user_id": 1}).mock(
            return_value=httpx.Response(
                200, json={"message": {"mid": "m1", "seq": 1}}
            )
        )
        msg = await max_client.send_message(user_id=1, text="hi")
        assert route.called
        assert route.calls[0].request.headers["authorization"] == "test-token"
        assert msg.message_id == "m1"
```

### 5.3. VK Callback API fixtures

```python
@pytest.fixture
def vk_confirmation_payload():
    return {
        "type": "confirmation",
        "group_id": 12345,
    }


@pytest.fixture
def vk_message_new_payload():
    return {
        "type": "message_new",
        "group_id": 12345,
        "secret": "test-vk-secret",
        "object": {
            "message": {
                "from_id": 99,
                "peer_id": 99,
                "text": "Привет",
                "date": 1730000000,
            }
        },
    }


def test_vk_confirmation_returns_code(client, monkeypatch):
    monkeypatch.setenv("VK_CONFIRMATION_CODE", "abcdef")
    r = client.post("/vk/webhook", json={"type": "confirmation"})
    assert r.status_code == 200
    assert r.text == "abcdef"


def test_vk_rejects_bad_secret(client, vk_message_new_payload, monkeypatch):
    monkeypatch.setenv("VK_SECRET_KEY", "real-secret")
    payload = {**vk_message_new_payload, "secret": "wrong"}
    r = client.post("/vk/webhook", json=payload)
    assert r.status_code == 403
```

### 5.4. Alice JSON fixture (PR #17)

```python
@pytest.fixture
def alice_request_payload():
    return {
        "version": "1.0",
        "session": {
            "session_id": "s1",
            "user_id": "u1",
            "skill_id": "skill-test",
            "new": True,
        },
        "request": {
            "command": "посоветуй книгу про любовь",
            "original_utterance": "Алиса, посоветуй книгу про любовь",
            "type": "SimpleUtterance",
            "nlu": {"tokens": [...], "entities": [], "intents": {}},
        },
    }


def test_alice_response_format(client, alice_request_payload, monkeypatch):
    monkeypatch.setenv("ALICE_SKILL_ID", "skill-test")
    r = client.post("/alice/webhook", json=alice_request_payload)
    assert r.status_code == 200
    body = r.json()
    assert body["version"] == "1.0"
    assert "response" in body
    assert "text" in body["response"]
    assert len(body["response"]["text"]) <= 1024
```

### 5.5. GigaChat / Yandex / SpeechKit мок

```python
@pytest.fixture
def llm_mock_router(monkeypatch):
    from app.llm import router

    async def fake_complete(prompt: str, **kw):
        return router.LLMResponse(
            text="mock-response",
            tokens=10,
            provider="mock",
            latency_ms=50,
        )

    monkeypatch.setattr(router, "complete", fake_complete)
    return fake_complete
```

---

## 6. Makefile (создаётся в PR #6 одним из первых)

```makefile
# === ЧитАИ Makefile ===
.PHONY: help install lint test test-cov backend-lint backend-test \
        frontend-lint frontend-test bot-lint bot-test bench migrate \
        run-backend run-frontend run-bot

help:
	@echo "Targets:"
	@echo "  install         — установить все зависимости (backend + frontend + bot)"
	@echo "  lint            — ruff + npm run lint + bot-lint"
	@echo "  test            — все тесты (backend + frontend + bot)"
	@echo "  test-cov        — тесты с coverage report"
	@echo "  bench           — RAG benchmark"
	@echo "  migrate         — alembic upgrade head (PR8+)"
	@echo "  run-backend     — uvicorn dev"
	@echo "  run-frontend    — vite dev"

install:
	cd backend && poetry install
	cd frontend && npm install
	cd bot && pip install -r requirements.txt

backend-lint:
	cd backend && poetry run ruff check app

backend-test:
	cd backend && poetry run pytest -q

frontend-lint:
	cd frontend && npm run lint

frontend-test:
	cd frontend && npm test

bot-lint:
	cd bot && ruff check .

bot-test:
	cd bot && pytest -q

lint: backend-lint frontend-lint bot-lint

test: backend-test frontend-test bot-test

test-cov:
	cd backend && poetry run pytest --cov=app --cov-report=term-missing --cov-fail-under=70

bench:
	cd backend && poetry run python -m app.benchmark > ../benchmark.json

migrate:
	cd backend && poetry run alembic upgrade head

run-backend:
	cd backend && poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

run-frontend:
	cd frontend && npm run dev
```

---

## 7. .github/pull_request_template.md

```markdown
## PR номер

PR #__ — короткое название.

## Описание

Что делает этот PR (1–3 предложения).

## Изменения

- [ ] Backend
- [ ] Frontend
- [ ] Bot
- [ ] CI / Infra
- [ ] Docs

## Чек-лист

- [ ] `make lint` зелёный локально
- [ ] `make test` зелёный локально (количество тестов: ___)
- [ ] Coverage не упал ниже 70%
- [ ] `.env.example` обновлён (если добавлены env-переменные)
- [ ] README.md / docs/ обновлены
- [ ] Telegram-бот не сломан (если PR трогает `bot/` или `bots/`)
- [ ] Pre-commit хуки прошли
- [ ] Нет секретов в коде
- [ ] CI зелёный после push
```

---

## 8. .pre-commit-config.yaml

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.6.9
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.0.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
        args: ['--maxkb=1024']
      - id: detect-private-key
  - repo: https://github.com/PyCQA/bandit
    rev: 1.8.0
    hooks:
      - id: bandit
        args: ['-r', 'backend/app', '-x', 'backend/tests']
```

---

## 9. Типичные грабли (anti-patterns log)

| Грабли | Как избежать |
| ------ | ------------ |
| `verify_ssl=False` хардкод в GigaChat | Через env (`GIGACHAT_VERIFY_SSL`, `GIGACHAT_CA_BUNDLE`) — уже сделано в PR5 |
| Стейт ломается на рестарте | `CHITAI_STATE_DIR` (PR5) → Postgres (PR8) |
| `forget()` теряет audit-stub | Хранить stub под `stub_id`, а не `user_id` (PR5) |
| `dangerouslySetInnerHTML` без sanitize | `sanitizeHtml()` обёртка из PR6 |
| Двойной вызов LLM при retry клиента | `Idempotency-Key` (PR7) |
| Telegram-бот ломается при добавлении MAX | Миграция в `bots/telegram_bot/`, все 9 тестов остаются (PR10) |
| VK Callback API «не подтверждается» | type=confirmation → return PlainTextResponse (PR11) |
| `secret` в VK не проверяется → spoofing | Сравнивать с `VK_SECRET_KEY` env (PR11) |
| MAX webhook без X-MAX-Webhook-Secret | Сравнивать с `MAX_WEBHOOK_SECRET` env (PR10) |
| Alice ответ > 3 секунд | «Короткий режим» curator + таймаут на LLM (PR17) |
| LLM-провайдер отвалился → весь backend стоит | Circuit breaker per-provider (PR14) |
| Бенчмарк регрессирует, никто не замечает | CI-gate уже есть (PR5) — не убирать |
| Корпус в git → репо разбухает | Хранить в S3 / Git LFS (PR12+13) |
| Юр. лицо не подано в РКН | PR15 генерирует форму, далее вручную |

---

## 10. Шаблон промпта для запуска одного PR

> Скопируйте, замените `{N}` и `{NAME}`, пришлите в новую сессию Devin.

```
Прочитай два прикреплённых файла:
- chitai_finishing_prompts.md (полный план PR'ов)
- chitai_dev_kit.md (готовые скелеты, фикстуры, шпаргалки)

Открой chitai_finishing_prompts.md и найди раздел «PR #{N} — {NAME}».
Выполни весь промпт оттуда:
1. ОБЯЗАТЕЛЬНО прочитай AGENTS.md (если уже создан) и универсальный
   пролог из chitai_finishing_prompts.md.
2. Используй готовые скелеты из chitai_dev_kit.md (если применимо
   к этому PR).
3. Создай feature-branch, реализуй фичу, напиши тесты.
4. Перед коммитом: `make lint && make test` локально.
5. Создай PR через git_create_pr на ветку main.
6. Дождись зелёного CI через git_pr_checks.
7. Если CI красный — почини; не амендь, добавь новый коммит.
8. Когда CI зелёный — напиши мне «PR #{N} готов, ссылка: <url>».
9. Жди подтверждения от меня перед PR #{N+1}.

Если что-то непонятно или нужны секреты — спрашивай ДО старта работы.
```

---

## 11. Что положить в `docs/` перед PR #6 (если хочешь форы)

- `docs/bots.md` — пустой файл с заголовком; пополняется PR10/11/17
- `docs/legal/checklist.md` — пустой; PR15
- `docs/deploy.md` — пустой; PR12

Создать пустые скелеты (5 минут работы) — следующая сессия не будет
тратить время на «куда положить».

---

## 12. Команда «zero-to-PR» для разработчика на новой машине

```bash
git clone https://github.com/BitMagistrate/ddhlsboz.git
cd ddhlsboz
cp .env.example .env
# отредактируйте .env, заполните секреты
make install
make lint
make test
make bench
# всё зелёное?  → готовы делать PR
```

---

## Итог

Если применишь это до PR #6:
- AGENTS.md в корне → каждая сессия Devin сразу знает правила.
- `.env.example` полный → не блокируешься на «а где взять MAX_BOT_TOKEN».
- `bots/core.py` скелет → PR10 стартует сразу с реализации, не с дизайна.
- Test fixtures cheatsheet → каждый бот-PR пишет тесты быстрее.
- Makefile → команды одинаковы у всех.
- PR template → не забыл проверить чек-лист.
- Pre-commit → не словил CI red на форматировании.
- Anti-patterns log → не повторяешь известные ошибки.

Экономия времени на 12 PR-ов: примерно **15–25%**.
