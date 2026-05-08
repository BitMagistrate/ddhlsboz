# API-спецификация ЧитАИ

## Базовый URL

- Локально: `http://localhost:8000`
- Прод (после деплоя): `https://api.chitai.ru` (или Fly.io URL для MVP)

## Аутентификация

На MVP — все эндпоинты публичные. В продакшене — JWT в заголовке `Authorization: Bearer <token>`.

## Эндпоинты

### `GET /api/health`

Проверка работоспособности сервиса.

Ответ:
```json
{ "status": "ok", "version": "0.1.0", "service": "chitai-backend" }
```

### `GET /api/sources`

Список доступных источников в корпусе.

Параметры:
- `q` (опционально) — поисковая строка.
- `limit` (опционально, по умолчанию 20) — количество результатов.

Ответ:
```json
{
  "items": [
    {
      "id": "pushkin-evgeniy-onegin",
      "title": "Евгений Онегин",
      "author": "А.С. Пушкин",
      "year": 1833,
      "category": "роман в стихах",
      "license": "общественное достояние",
      "source_url": "https://rusneb.ru/...",
      "tags": ["русская классика", "XIX век"]
    }
  ],
  "total": 1
}
```

### `POST /api/curator/chat`

Запрос к Куратору (диалог).

Запрос:
```json
{
  "message": "Хочу разобраться в Серебряном веке",
  "session_id": "uuid",
  "user_age_group": "14-18",
  "history": [
    { "role": "user", "content": "..." },
    { "role": "assistant", "content": "..." }
  ]
}
```

Ответ:
```json
{
  "reply": "Серебряный век — это период русской поэзии и культуры конца XIX — начала XX века...",
  "sources": [
    {
      "id": "blok-stikhi-o-prekrasnoy-dame",
      "title": "Стихи о Прекрасной Даме",
      "author": "А.А. Блок",
      "url": "https://rusneb.ru/..."
    }
  ],
  "suggestions": [
    "Построить маршрут на 4 недели",
    "Найти музей Серебряного века",
    "Упростить ответ"
  ],
  "session_id": "uuid"
}
```

### `POST /api/curator/route`

Построение маршрута на 4 недели.

Запрос:
```json
{
  "topic": "Серебряный век",
  "duration_weeks": 4,
  "user_age_group": "14-18",
  "session_id": "uuid"
}
```

Ответ:
```json
{
  "topic": "Серебряный век",
  "duration_weeks": 4,
  "weeks": [
    {
      "week": 1,
      "title": "Введение в эпоху",
      "items": [
        {
          "type": "reading",
          "title": "Стихи о Прекрасной Даме",
          "author": "А.А. Блок",
          "duration_min": 60,
          "source_url": "..."
        },
        {
          "type": "lecture",
          "title": "Лекция «Серебряный век: контекст и поэтика»",
          "duration_min": 45,
          "source_url": "..."
        }
      ]
    },
    {
      "week": 2,
      "title": "Символизм",
      "items": ["..."]
    }
  ]
}
```

### `GET /api/quiz/items`

Список заданий тренажёра ЕГЭ/ОГЭ.

Параметры:
- `subject` (опционально): `literature` или `history`.
- `level` (опционально): `oge` или `ege`.
- `topic` (опционально): тема.
- `limit` (опционально, по умолчанию 10).

Ответ:
```json
{
  "items": [
    {
      "id": "lit-ege-001",
      "subject": "literature",
      "level": "ege",
      "type": "К8",
      "topic": "Анализ лирического текста",
      "question": "Прочитайте стихотворение А.А. Блока «Незнакомка»...",
      "task": "Какие средства художественной выразительности использует автор?",
      "criteria": ["К1", "К2", "К3"],
      "max_points": 6
    }
  ]
}
```

### `POST /api/quiz/submit`

Отправка ответа на задание.

Запрос:
```json
{
  "item_id": "lit-ege-001",
  "answer": "В стихотворении используются метафоры...",
  "session_id": "uuid"
}
```

Ответ:
```json
{
  "score": 4,
  "max_score": 6,
  "feedback": [
    {
      "criterion": "К1",
      "points": 1,
      "max_points": 1,
      "comment": "Проблема сформулирована корректно."
    },
    {
      "criterion": "К2",
      "points": 2,
      "max_points": 3,
      "comment": "Комментарий присутствует, но недостаточно развёрнут."
    }
  ],
  "suggestions": ["Прочитайте разбор задания К8 в кабинете"]
}
```

### `GET /api/teacher/scenarios`

Список сценариев уроков.

Параметры:
- `subject`: `literature` или `history`.
- `grade`: 5–11.
- `topic` (опционально).

Ответ:
```json
{
  "items": [
    {
      "id": "lit-10-onegin",
      "subject": "literature",
      "grade": 10,
      "topic": "А.С. Пушкин «Евгений Онегин»",
      "duration_min": 45,
      "objectives": ["..."],
      "stages": [
        { "name": "Орг. момент", "duration_min": 3 },
        { "name": "Актуализация", "duration_min": 7 }
      ],
      "homework": "Письменный анализ главы 1, задание ФИПИ К8"
    }
  ]
}
```

### `GET /api/dashboard/metrics`

Метрики для регионального дашборда.

Параметры:
- `region` (опционально): код региона.
- `period` (опционально): `7d`, `30d`, `90d`.

Ответ:
```json
{
  "region": "77",
  "region_name": "Москва",
  "period": "30d",
  "metrics": {
    "active_users": 2348,
    "active_users_change_pct": 12,
    "routes_completed": 487,
    "pushkin_card_transactions": 156,
    "average_route_duration_days": 18,
    "nps": 52
  },
  "top_topics": [
    { "topic": "Серебряный век", "count": 312 },
    { "topic": "Война и мир", "count": 287 }
  ],
  "weekly_activity": [
    { "week": "2026-W01", "users": 1820 },
    { "week": "2026-W02", "users": 1990 }
  ]
}
```

### `POST /api/feedback`

Обратная связь от пользователя.

Запрос:
```json
{
  "session_id": "uuid",
  "type": "thumbs_up | thumbs_down | comment",
  "comment": "Текст обратной связи (опционально)",
  "context": { "message_id": "uuid" }
}
```

Ответ:
```json
{ "status": "received" }
```

## Коды ошибок

| Код | Описание |
|---|---|
| 400 | Неверный запрос |
| 401 | Не авторизован |
| 403 | Доступ запрещён |
| 404 | Не найдено |
| 422 | Ошибка валидации |
| 429 | Превышен лимит запросов |
| 500 | Внутренняя ошибка |

## Лимиты на MVP

- 60 запросов/минуту с IP.
- Максимальная длина message — 2000 символов.
- Максимальная история — 20 сообщений.

## Контракт стабильности

API версионируется через префикс `/api/v1/...` (на MVP — без префикса `/v1`, в продакшене добавляется). Backwards-совместимые изменения — в MINOR версии. Breaking changes — в MAJOR.

## OpenAPI

Полная спецификация доступна по `/docs` (Swagger UI) и `/openapi.json`.
