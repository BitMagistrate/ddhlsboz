

Что сделано (зелёные CI локально: 224 backend + 41 frontend + 9 bot + 14 bots-core)
Инфраструктура (PRs #6/#7/#14)

XSS hardening: frontend/src/lib/sanitize.ts (DOMPurify allowlist, safeHref, control-char strip), 14 тестов в sanitize.test.ts, safeHref/sanitizeText подключены в App.tsx для public_domain_url, booking_url, SRS-карт.
Rate-limit + idempotency: backend/app/ratelimit.py (token-bucket per user/IP, idempotency-кэш с TTL), 11 тестов. Включено на /api/curator/route, /api/curator/mindmap, /api/exam/plan, /api/characters/ask. ENV: CHITAI_RATE_LIMIT_PER_MIN, CHITAI_RATE_LIMIT_BURST, CHITAI_IDEMPOTENCY_TTL_SECONDS.
Circuit breaker в backend/app/llm/router.py — состояние closed/open/half_open per provider, 8 тестов. ENV: CHITAI_LLM_FAILURE_THRESHOLD, CHITAI_LLM_COOLDOWN_SECONDS.
Фичи (C-серия) — backend готов

app/characters.py + /api/characters{,/ask} — «Спроси Раскольникова», 5 героев с RAG-якорем и принудительными цитатами.
app/challenge.py + /api/challenge/{books,progress,mark-read,unmark} — «100 книг», 9 бейджей, kv-persistence через state.py.
app/exam_plan.py + /api/exam/plan — недельный ЕГЭ-план по корпусу + темам ФИПИ.
app/quickread.py + /api/quickread/{book_id} — «5 минут на книгу».
app/quote_game.py + /api/quote-game/{new,check} — «Угадай по цитате».
app/literary_calendar.py + /api/calendar/{today,month/M} — 23 события.
app/roi.py + /api/roi/compute — B2G ROI-калькулятор.
app/i18n.py + /api/i18n{,/locales} — каркас ru/tt/ba.
PR #10 — multi-channel bots core (без слома существующего bot/)

что еще не сделано:  Universal inbox — загрузка произвольных PDF/EPUB/DOCX/YouTube/URL и парсинг. У нас сейчас только хардкоженый корпус из 36 public-domain произведений. Это самая важная отсутствующая фича — без неё это не Mindgrasp.
❌ AI Tutor 24/7 chat по произвольному документу (есть только character chat по корпусу).
❌ AI Math Expert (пошаговое решение задач).
❌ Focused Reading (ускоренное чтение).
❌ Chrome Extension (Canvas/Blackboard/Panopto).
❌ Запись лекций live (web + iOS) и Q&A по записи — нужен Whisper-equiv ASR.
❌ Audio Recap (подкаст 6–45 мин из учебного материала) — нужен TTS поверх длинных текстов + chapter-splitter.
❌ Explainer Video (AI-видео типа Synthesia).
❌ Essay Grader (оценка эссе с рубрикой ЕГЭ).
❌ Call with AI (голосовой звонок, LiveKit/Daily.co).
❌ Web Highlighting (Readwise-style выделение на live-странице).
❌ YouTube reader с time-synced transcript.
❌ Daily Review хайлайтов.
❌ Public REST API с ключами + per-key лимитами (есть только наш внутренний API).
❌ iOS / Android нативные приложения (есть только PWA).
❌ 20+ языков (есть только каркас ru/tt/ba).
❌ Zachet генератор работ по ГОСТ, VK Видео-разборы, калькулятор формул, заявки на консультации.
Из pushkinskaya_card_monetization.md (Пушкинская карта + игры)
Сделано:

Только то, что уже было до меня: рекомендации событий по Пушкинской карте — app/pushkin.py + /api/pushkin/match. Это просто список событий, не выпуск билетов.
НЕ сделано (всё остальное):

❌ Регистрация юр.лица + ОКВЭД (это юридический шаг, не код).
❌ Подключение к PRO.Культура.РФ — нужна аккредитация Минкульта.
❌ «Белый» терминал + эквайринг + касса по 54-ФЗ.
❌ «Просветительский абонемент» (способ 1 монетизации) — выпуск билетов на абонемент через ПК.
❌ Турниры Quiz Royale на ПК (способ 2) — нужна мини-игра + ticketing.
❌ «Чат с классиком» как платный билет на ПК (способ 3) — у нас есть бекенд чата, но не как продаваемое мероприятие.
❌ Кинолекторий + AI-разбор (способ 4).
❌ B2B school/college класс под ключ (способ 5) — есть только ROI-калькулятор.
❌ Мастер-классы «Как написать эссе» (способ 6).
❌ Аудиолекторий-подкаст (способ 7) — нужен Audio Recap.
❌ White-label для библиотек/музеев (способ 8).
Игры (3 must-have из документа)
❌ «Match Race» — карточки на скорость, виральная социалка. Не сделано.
❌ «Quiz Royale» — групповая live-игра по PIN-коду (WebSocket). Не сделано.
❌ «Knowledge Climb» — вертикальный платформер «Subway Surfers для учёбы». Не сделано.
Из «игровых» фич я сделал только мини-игру «Угадай произведение по цитате» (/api/quote-game/{new,check}) — её не было в списке, но она бесплатная по контенту и быстро ложится в продукт.

Что нужно, чтобы это сделать
Фича	Что блокирует
Universal inbox (PDF/YouTube/URL)	+ pypdf, youtube-transcript-api, trafilatura + chunking + dense embeddings
Audio Recap	Длинный TTS (Yandex SpeechKit), генерация SSML, S3 storage
Essay Grader	Промпт-инжиниринг + рубрика ЕГЭ + GigaChat MAX + калибровка
Call with AI	LiveKit/Daily.co сервер, голосовой ASR, streaming TTS
Quiz Royale live	WebSocket-сервер, Redis для синхронизации сессий по PIN
Match Race / Knowledge Climb	Phaser.js или PixiJS — фронт; нужно отдельное направление работы
Пушкинская карта (билеты)	Юр.лицо + регистрация в ПРО.Культура.РФ — это не код, это бизнес-шаги
Chrome Extension	Отдельный пакет, Manifest V3, store-аккаунт
iOS/Android	React Native или Capacitor, store-аккаунты
Public REST API	+ API-ключи, JWT, лимиты, OpenAPI спек

bots/core.py — Channel ABC, MemoryChannel, Router, ChitaiClient, дефолтные хэндлеры для меню/маршрута/Раскольникова/quickread/about.
bots/adapters/vk.py — VK Communities (long-poll + messages.send + inline keyboard + payload-intents).
bots/adapters/max.py — MAX/TamTam-style REST stub.
bots/tests/test_core.py — 14 тестов. Старые 9 тестов в bot/tests/ целы.
F2 / F8 / CI

evaluation/report.json (MRR 0.979, Recall@5 0.985) + evaluation/README.md (методика, воспроизведение).
docs/pitch/pitch.md — 12-слайдовый Marp-дек + docs/pitch/README.md (рендер).
.github/workflows/ci.yml — два новых job-а: bots-core (lint+tests) и security (gitleaks).
Что НЕ сделано (требует отдельных PR / больше времени)
Большие куски — нужны новые миграции/деплои/SDK:

PR #8: PostgreSQL 16 + Alembic миграции (2–3 дня) — сейчас всё ещё in-memory + JSON-persistence.
PR #9: OAuth2 VK ID + Sber ID — нужны клиентские секреты от провайдеров.
PR #11: VK Communities full long-poll loop + сценарии модераций — есть только адаптер, не запуск 24×7.
PR #12: Yandex Cloud deploy (Compute + Object Storage + Managed PostgreSQL) — Terraform + CI deploy не написаны.
PR #13: расширить корпус с 36 до 60–100 произведений + golden set — нужен ручной отбор public-domain текстов.
PR #15: автогенерация юридического ОПД (152-ФЗ) — нужны шаблоны от юриста региона.
PR #16: Mini-app в MAX (WebApp + Bridge) — нужен доступ к MAX API.
PR #17: Alice Yandex skill — опционально, ждёт решения.
Мелочи, которые не успел:

C-12 spoiler-filter (фильтр по «текущей главе») — нужен модуль chapters.py с разметкой границ.
D8-доп экспорты в PDF/.docx/.apkg — требуют reportlab + python-docx + genanki (новые зависимости + лицензии).
Frontend-UI для новых эндпоинтов — есть только backend. Чтобы их вывести в интерфейс, нужно добавить 3–4 вкладки в App.tsx (Раскольников, 100 книг, ЕГЭ-план, Quickread). Это безопасно делать отдельным PR.
Axe-core/a11y в CI — пропустил, нужен запуск Playwright в actions.
Pitch.pdf — Marp .md есть, но автогенерация .pdf в CI не добавлена (marp-team/marp-cli action).
