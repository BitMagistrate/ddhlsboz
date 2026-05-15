# AI Study Service — полная спецификация: функции трёх референсов + как это реализовать в коде + мини-игры для маркетинга

> **⚠️ DRAFT / нужна локализация.** Документ исходно написан под западный стек (OpenAI, Anthropic, Whisper, Mistral OCR, Pinecone и т.п.). Для production в ЧитАИ нужно заменить все эти провайдеры на российский стек: **GigaChat MAX / YandexGPT 5 Pro** (LLM), **Yandex SpeechKit** (TTS/ASR), **Yandex Vision** (OCR), **локальные эмбеддинги / Yandex Foundation Models** (vector search), **Postgres + pgvector** (хранение). См. `docs/ROADMAP.md` §EX1–EX5 для текущего плана upload pipeline в Mode «Учёба».

> **🚀 Реализация Stage 2 — готова.** Универсальный ingest pipeline доступен:
> `POST /api/study/ingest` (text / url / audio / video) + `POST /api/study/ingest/pdf`.
> Полный набор endpoints для конспекта, Q&A, флэшкарт, Smart-Quiz, FIB, эссе,
> экспорта, sharing, mastery и тарифов — см. `backend/app/study.py` и
> `backend/app/main.py` (раздел «Учёба»). Прототип лендинга:
> <https://chitai.bolt.host/#>. Тариф-матрица: Free / Неделя / Месяц / Год.

> Документ объединяет функционал **Mindgrasp.ai**, **Zachet.app** и **StudyFetch.com (Spark.E + Arcade)**, описывает, **как именно** каждую такую функцию строить в коде (архитектура, данные, API/SDK, готовые библиотеки), и предлагает **2–3 мини-игры**, которые приживаются у студентов и работают как маркетинговый виральный канал — без клонирования Subway Surfers.
>
> Стек по умолчанию (от которого можно отступать): **Next.js 14 (App Router) + TypeScript + Tailwind + shadcn/ui** на фронте, **NestJS** или **FastAPI** на бэке, **PostgreSQL + pgvector**, **Redis + BullMQ**, **S3-совместимое хранилище** (AWS S3 / Yandex Object Storage / Cloudflare R2). Мобилка — **React Native (Expo)** или нативная iOS на SwiftUI.

---

## 0. Архитектура высокого уровня (общая для всех трёх продуктов)

```
┌────────────┐     ┌────────────┐     ┌──────────────┐
│  Web (Next)│     │  iOS (RN/  │     │ Chrome ext.  │
│  + PWA     │     │  SwiftUI)  │     │ (Canvas etc.)│
└─────┬──────┘     └─────┬──────┘     └──────┬───────┘
      │                  │                   │
      ▼                  ▼                   ▼
        ┌────────────────────────────────┐
        │   API Gateway (REST + WS)      │   ← NestJS / FastAPI
        │   + Auth (JWT, OAuth, magic)   │
        └──────────────┬─────────────────┘
                       │
   ┌───────────────────┼─────────────────────┐
   ▼                   ▼                     ▼
┌────────┐       ┌──────────────┐      ┌──────────────┐
│ Domain │       │ Job Queue    │      │ Realtime hub │
│ APIs   │       │ (BullMQ /    │      │ (WS / SSE /  │
│        │       │  Celery)     │      │  LiveKit)    │
└───┬────┘       └──────┬───────┘      └──────┬───────┘
    │                   │                     │
    ▼                   ▼                     ▼
┌────────┐   ┌──────────────────────┐   ┌────────────┐
│ Postgres│  │ Workers (Python/Node)│   │ TTS / ASR  │
│ +pgvect │  │ ASR / OCR / LLM /    │   │ streaming  │
│         │  │ embed / video / TTS  │   │ providers  │
└────────┘   └──────────┬───────────┘   └────────────┘
                        │
                        ▼
                ┌───────────────┐
                │ S3 (raw +     │
                │  derived) +   │
                │ CDN           │
                └───────────────┘
```

**Ключевые принципы:**
1. **Любая загрузка → джоб в очереди → артефакты в БД/S3 → событие в WS-канал сессии.** Фронт всегда подписан на канал `study_session:{id}` и просто отрисовывает прогресс-бар.
2. **Один и тот же транскрипт — источник всего остального** (notes, summary, flashcards, quizzes, mind map, audio recap). Не генерируйте один и тот же контент дважды — кэшируйте по хэшу источника.
3. **LLM-вызовы идут только через свой шлюз (LLM router)** с метриками cost/tokens, retries, fallback (OpenAI → Anthropic → локальная модель). Это сэкономит 30–60% бюджета.

---

## 1. Mindgrasp.ai — функции и реализация

### 1.1 Функции (как у них)
- **AI Notes** — структурированные конспекты из любого источника.
- **AI Summary** — короткие саммари длинных лекций / статей.
- **AI Flashcards** — авто-карточки для активного припоминания.
- **AI Quizzes** — авто-тесты по материалу.
- **AI Tutor (24/7 chat)** — объяснение концепций.
- **AI Math Expert** — пошаговое решение математики.
- **Focused Reading** — режим ускоренного чтения.
- **Источники:** PDF, PPT, MP3, MP4, YouTube/Vimeo, web-ссылки, текст, **запись лекции live** (web + iOS).
- **Study Sessions** — отдельная сессия на лекцию/главу.
- **Library Storage** — безлимитное хранилище.
- **Real-Time Tracking + per-session checklist** — что сгенерировано/осталось.
- **Платформы:** web, iOS (безлимит записи), **Chrome Extension (beta)** для Canvas/Blackboard/Panopto.
- **20+ языков.**

### 1.2 Реализация

#### Загрузка и парсинг источников
| Источник | Что делать |
|---|---|
| PDF | `PyMuPDF` (fitz) для текста и картинок, `pdfplumber` для таблиц. Если PDF сканированный — fallback на OCR (см. ниже). |
| PPT/PPTX | `python-pptx` для слайдов; для изображений — OCR. |
| Аудио (MP3, M4A, WAV) | ASR — см. ниже. |
| Видео (MP4) | `ffmpeg` → извлечь аудио → ASR. Параллельно дёргать ключевые кадры (`ffmpeg -vf select` по сцене) для последующего описания через vision-LLM. |
| YouTube/Vimeo | Сначала пытаться забрать встроенные субтитры (`youtube-transcript-api`, `yt-dlp --write-auto-sub`). Нет субтитров → `yt-dlp` тащит аудио → ASR. |
| Веб-страница | `Playwright` (рендерит JS) или `trafilatura` (для статей) → `readability-lxml` → markdown. |
| Сканы / картинки | OCR: `Tesseract` (бесплатно), **Mistral OCR API** (лучший по точности на 2025), **Google Document AI**, или vision-LLM (`gpt-4o`, `claude-sonnet-4.5`). |

**ASR-провайдеры (выбор):**
- **OpenAI Whisper** (self-hosted на GPU, `faster-whisper` / `WhisperX` с диаризацией) — дёшево, качество отличное.
- **Deepgram Nova-3** — дешевле AssemblyAI, отличный стриминг, диаризация.
- **AssemblyAI** — фичи speaker labels, chapters, sentiment из коробки.
- **Yandex SpeechKit / SaluteSpeech (Сбер)** — лучше на русском в шумных лекциях.
- На iOS используйте `SFSpeechRecognizer` для **on-device live-транскрипции**, а финальный «чистый» транскрипт догоняйте облачным ASR.

#### AI Notes / AI Summary
Промпт-цепочка `MapReduce`:
1. **Chunking** транскрипта/документа: семантически по 1500–3000 токенов (`langchain.RecursiveCharacterTextSplitter` или собственный сплиттер по абзацам/таймкодам).
2. **Map**: для каждого чанка LLM возвращает структурированный JSON (`{title, bullets, key_terms, examples, timestamps}`) — JSON Mode / `response_format: json_schema`.
3. **Reduce**: второй LLM-вызов сшивает JSON-чанки в общий конспект, дедуплицирует пункты, расставляет H2/H3.
4. **Хранение** в БД: `notes(session_id, version, structured_json, markdown, html)`. Markdown — главный формат, html — кэш для рендера (через `marked` + `KaTeX` для формул).

**Модели:** GPT-4.1/5, Claude Sonnet 4.5 (отлично для длинных конспектов), Gemini 2.5 Pro (большое контекстное окно — можно скармливать целиком главу). Для русских материалов — YandexGPT 5 Pro / GigaChat 2 Max работают сравнимо.

#### AI Flashcards (с алгоритмом повторений)
Промпт: «Сгенерируй N карточек формата `{front, back, hint, source_quote, timestamp}` по этому конспекту».
- **Алгоритм повторений:** **FSRS** (Free Spaced Repetition Scheduler) — современнее SM-2, с открытыми реализациями (`fsrs.js`, `fsrs-rs`, `py-fsrs`). Используется в Anki по умолчанию.
- Каждый ответ карточки → событие `card_review(card_id, rating, ts)` → обновление `due_at`.
- Хранить отдельно: `flashcard`, `flashcard_review`, `flashcard_state(stability, difficulty, due_at)`.

#### AI Quizzes
- Типы вопросов: `single_choice`, `multi_choice`, `true_false`, `short_answer`, `fill_blank`, `match`, `ordering`, `numeric`.
- Промпт строго в JSON Schema; верификация ответов: для multi-choice — `correct_indices`, для short-answer — LLM-grader сравнивает с эталоном (используйте «relaxed match» + цитата из источника).
- Метаданные: `difficulty (Bloom level)`, `bloom_taxonomy: remember|understand|apply|analyze|evaluate|create`, `source_chunk_id`. Это позволяет потом строить персональные практики «по слабым местам».

#### AI Tutor (24/7 chat)
- **RAG поверх материалов сессии:** при каждом вопросе ищем top-K чанков по cosine similarity (pgvector / Qdrant) **в рамках только этой сессии или явного set'а**. Это отличие от обычного чата с GPT — модель отвечает только по материалам пользователя.
- Эмбеддинги: `text-embedding-3-large` (OpenAI), `voyage-3-large` (Voyage), `bge-m3` / `e5-mistral` (open-source). Для русского — `bge-m3` хорош.
- Стрим ответа через **SSE** (Server-Sent Events) — проще, чем WS, и идеально под чат.
- Память: краткосрочная (last N сообщений) + долговременная — суммаризация диалогов в `chat_summary(session_id)`.

#### AI Math Expert (пошаговое решение)
- **OCR формул:** `Mathpix` API (точнее всего на формулы, возвращает LaTeX) или `pix2tex`. Для рукописных — Mathpix.
- **Решение:**
  - Символьно: **SymPy** (Python) — для производных, интегралов, уравнений.
  - **Wolfram Alpha API** — для широкого спектра.
  - LLM с **chain-of-thought** или **tool use** (LLM решает, когда вызвать SymPy/Wolfram).
- Рендер шагов: KaTeX/MathJax. Каждый шаг — отдельный «карточечный» блок: `step(rationale_md, formula_latex, action)`.

#### Focused Reading (ускоренное чтение)
По сути — режим **RSVP (Rapid Serial Visual Presentation)** + подсветка опорных слов (как Spritz/Bionic Reading). Реализация — простой React-компонент:
- разбиваем текст на слова → таймер по WPM (configurable 200–800), показываем по одному;
- bionic-режим: первая половина слова — `font-weight: 700`, остальная — обычная;
- горячие клавиши: пауза (Space), назад/вперёд (←/→), регулировка скорости.

#### Study Sessions / Library / Real-Time Tracking
- Модель `study_session(id, user_id, title, status, created_at, last_opened_at)`.
- К ней прикреплены `source_documents`, `notes`, `flashcards`, `quizzes`, `chat_thread`, `mind_map`.
- **Real-time tracking** = WS-канал `study_session:{id}`; воркеры пушат события `progress`, `artifact_ready`, `error`. Фронт показывает чек-лист с галочками.
- **«Never lose your place»** — храните last-position на каждом артефакте (PDF page, video timestamp, RSVP word index, quiz question index).

#### Chrome Extension (Canvas / Blackboard / Panopto)
- **Manifest V3.** `content_script` инжектится на `*.instructure.com`, `*.blackboard.com`, `*.panopto.com`.
- Кнопка «Send to Mindgrasp» в углу страницы → собирает: PDF из `<embed>`/`<iframe>`, текущий URL, текст лекции, для Panopto — `m3u8` поток + кук-сессию (для скачивания через бэкенд).
- Авторизация: extension использует JWT из `chrome.storage.local`, OAuth при первом входе.
- Загрузка: presigned upload в S3 → POST `/sessions` с `source_ref`.

#### Запись лекций live (web + iOS)
- **Web:** `MediaRecorder` API → 30-секундные `Blob`-чанки → `multipart upload` в S3 → стриминговый ASR (Deepgram/AssemblyAI realtime/Whisper streaming через `whisper-live`).
- **iOS:** `AVAudioEngine` + `AVAudioRecorder`, фоновая запись с разрешением `Background Modes: Audio`. Загрузка чанков по wifi-window (TUS protocol для возобновляемых аплоадов).
- Live-транскрипт пушится в WS, конспект/карточки генерируются после `recording.finalized`.

#### 20+ языков
- Detect: `langid.py` или поле в UI.
- Промпты пишите универсальными, язык вывода передавайте параметром: `Respond in {{user_language}}`.
- Для UI — `next-intl` / `i18next`.

---

## 2. Zachet.app — функции и реализация

### 2.1 Функции (как у них)
- **Транскрибация лекций.**
- **Конспекты** красиво оформленные.
- **Флеш-карточки** (Quizlet/Anki-like).
- **Тесты** с разбором ошибок.
- **Mind maps** — визуальная структура темы.
- **ИИ-репетитор** — чат по конспекту.
- **Мини-игры** для закрепления.
- **Экспорт в PDF, Notion, Obsidian, шеринг.**
- **Источники:** запись аудио в приложении, YouTube + VK Видео, PDF, статьи.
- **Web + iOS.**
- **Доп. в моб. приложении:** калькулятор формул, справочник студента, блог с лайфхаками, заявки на консультации (контрольные, курсовые, дипломные — 65+ типов работ, 600+ предметов), чат с менеджером, push.
- **zachet.tech (поддомен)** — генерация рефератов/курсовых/эссе/докладов/презентаций по ГОСТ, Anti-AI Score 92%, на базе Claude Sonnet 4.5.

### 2.2 Реализация (что отличается от Mindgrasp)

#### VK Видео
- Парсинг через `yt-dlp` (поддерживает VK), либо официальный VK API + получение HLS-плейлиста по `videos.get`. Дальше — как с YouTube: субтитры → ASR fallback.

#### Mind maps
- **Генерация:** LLM возвращает древовидный JSON `{ id, title, children: [...] }` строго по схеме.
- **Рендер:** `markmap` (markdown → mind map, MIT, ставится в 1 строку) или `react-flow` для интерактивных нодов с возможностью drag, добавления, экспорта PNG/SVG.
- **Экспорт:** `dom-to-image` / `html2canvas` для PNG, `svgson` для SVG, либо встроенный экспорт markmap.

#### Экспорт в PDF / Notion / Obsidian
- **PDF:** на сервере — `Puppeteer` (HTML → PDF) или `WeasyPrint` (Python, без браузера, отлично для шаблонов с CSS). На клиенте — `react-pdf` (генерирует PDF целиком на фронте, удобно для предпросмотра).
- **Notion:** Notion API (`@notionhq/client`), OAuth, метод `pages.create`. Markdown → Notion blocks: `martian` (npm).
- **Obsidian:** просто экспорт `.md` файлов в zip (Obsidian читает markdown как есть). Поддерживайте Obsidian-friendly формат: `[[wikilinks]]` между связанными нотами одной сессии.

#### Шеринг с одногруппниками
- `share_link(slug, session_id, expires_at, permissions)` → публичный read-only URL. Опционально — пароль или требование логина.
- Анти-абуз: rate-limit на просмотры, watermark для скачиваний.

#### Калькулятор формул
- Парсер выражений: `math.js` (web) или `SymPy` (бэк).
- Камера → формула: `Mathpix` или vision-LLM.
- Шаги решения: см. AI Math Expert выше.

#### Справочник студента + блог
- Обычная CMS-часть. Подойдёт **Strapi**, **Directus** или **Sanity** — у них из коробки rich text + версии + RU-локализация.

#### Заявки на консультации (контрольные/курсовые/дипломные)
По сути это **CRM + marketplace «студент ↔ менеджер»**:
- Сущности: `order(type, subject, deadline, files, budget, status)`, `order_message`, `order_attachment`, `manager`, `assignment(executor_id)`.
- Workflow: `new → in_review → quoted → paid → in_progress → review → delivered → closed/disputed`.
- Платежи: ЮKassa / Tinkoff Acquiring / CloudPayments. Эскроу — храним списания на pending до подтверждения.
- Push: APNs (iOS), FCM (Android/web), email (Postmark/Mailgun).
- Чат с менеджером — обычный WS-канал `order:{id}`, прикрепление файлов через S3 presigned URL.

#### zachet.tech — генератор работ по ГОСТ
- **Шаблон документа** по ГОСТ 7.32-2017 (исследовательские работы) и ГОСТ 7.0.100-2018 (библиография). Делается через `python-docx` (DOCX-шаблон с заранее оформленными стилями) или `Pandoc`-template.
- **Генерация:**
  1. План (LLM возвращает оглавление: введение → главы → заключение → список литературы).
  2. По каждой главе — отдельный LLM-проход с RAG (включая поиск релевантных источников через `Semantic Scholar API`, `eLibrary`, `КиберЛенинка` парсинг).
  3. Сборка в DOCX с правильными стилями (Times New Roman 14, 1.5 интервал, отступы, нумерация).
- **Anti-AI Score** (обход AI-детекторов) — рискованная зона, в публичной документации обычно описывают это как «человекоподобный стиль». Технически это:
  - перефразирование на разных моделях (ансамбль),
  - вставка натуральных «шероховатостей» и доменных идиом,
  - контролируемая burstiness (вариативность длины предложений).
  Делайте это аккуратно с т.з. этики/политики ВУЗов и пишите дисклеймер.
- **Anti-plagiarism check:** прогон через `text.ru API`, `Advego API`, или собственный shingles-чекер по корпусу eLibrary.

---

## 3. StudyFetch — функции и реализация

### 3.1 Функции (как у них)
- **Notes AI, Flashcards AI, Quizzes AI, Practice Tests, Exam-Specific Questions** — то же, что у Mindgrasp/Zachet, но + **формат конкретного экзамена**.
- **Spark.E AI (24/7 chat)** — персональный AI-репетитор.
- **Spark.E Visuals** — вопросы по картинкам/диаграммам из конспектов.
- **Tutor Me** — целостный «урок» с прогресс-баром, два режима (голос/чат).
- **Call with Spark.E** — живой голосовой звонок с AI-репетитором.
- **Record Live Lecture** — live-запись + вопросы во время лекции.
- **Audio Recap** — подкаст/лекция/саммари 6–45 мин из материалов.
- **Explainer Video** — AI-видео с объяснением темы.
- **Essay Grader** — оценка эссе с фидбэком.
- **Arcade** — мини-игры из материалов (см. их фичу `PDF to Game`: пока 2 типа — **Rocket Defender** и **Platform Jump**, выбирается визуальный стиль).
- **Plugins / Mini Apps** — кастомизация поведения Spark.E + создание своих учебных мини-приложений.
- **Study Plan + Calendar** — план обучения, расписание.
- **Text with Spark.E** — общение с AI через SMS.
- **For Teachers / For Institutions** — отдельные продукты.
- **25+ языков, NVIDIA partnership.**

### 3.2 Реализация (что отличается)

#### Spark.E Visuals (Q&A по картинкам/диаграммам)
- **Vision-модели:** GPT-4o, GPT-5 vision, Claude Sonnet 4.5 vision, Gemini 2.5 Pro.
- При парсинге PDF/PPT — выделять каждую картинку → грузить в S3 → получать `image_url` → встраивать в чанки конспекта как `{type: "image", caption, ocr_text, image_id}`.
- При вопросе с картинкой — multimodal-промпт: текст вопроса + image_url. Возвращаем bounding-box / стрелочку через mask, если важно показать «вот это место на схеме».

#### Tutor Me (полноценный урок)
Это **state machine**:
```
plan_generated → topic_intro → micro_lesson → check_for_understanding → 
   ↳ if wrong: re-explain (different angle) → re-check
   ↳ if right: next_topic
→ summary → quiz → done
```
- LLM-агент с **structured outputs** возвращает следующий шаг + content + UI-инструкцию (`show_diagram`, `ask_question`, `show_video_chunk`).
- Прогресс-бар = `current_topic_index / total_topics`. Каждое продвижение пишется в `lesson_progress`.
- Два режима — **voice** (см. ниже Call) и **chat**.

#### Call with Spark.E (голосовой звонок с AI)
**Самая хрупкая фича — нужна низкая задержка.**
- Стек: **WebRTC** + **LiveKit Cloud** (Realtime SFU). LiveKit имеет готовый `Agents SDK` — оркестратор «STT → LLM → TTS» в реальном времени.
- Альтернатива «всё-в-одном»: **OpenAI Realtime API** (`gpt-4o-realtime-preview`) — речь напрямую в речь, ~300мс латентности. Аналоги — **Gemini Live API**, **Cartesia Sonic** (TTS) + Deepgram (STT) + GPT.
- TTS-провайдеры: **ElevenLabs** (лучшее качество и multilingual), **Cartesia Sonic** (самый низколатентный), **OpenAI tts-1-hd**.
- Барджин (можно перебить ИИ): включать VAD (Silero VAD / WebRTC VAD), мгновенно глушить TTS на детект речи.

#### Record Live Lecture с возможностью задавать вопросы «без касания компьютера»
- Та же лайв-запись (см. Mindgrasp 1.2), но добавляется **wake-word** или **hands-free hotword**: например, `"Spark, ..."`. Делается через `picovoice/Porcupine` (custom wake-word) или просто кнопкой на смарт-часах / Bluetooth-наушниках.
- Когда ассистент слышит вопрос — он отвечает голосом **через TTS, в наушник**, не прерывая запись лекции в основной канал.

#### Audio Recap (6–45 мин подкаст)
1. LLM пишет **сценарий** в формате диалога двух ведущих (как NotebookLM Audio Overview).
2. Сценарий → строки с ролями `host_a` / `host_b`.
3. Каждая строка озвучивается через TTS (разные voice IDs), можно через **ElevenLabs Voice Design** — два сгенерированных голоса.
4. Склейка в `ffmpeg` (concat + кроссфейды + лёгкая фоновая музыка под лицензией). Длительность регулируется промптом и количеством секций.

#### Explainer Video (AI-видео объяснение)
Тут есть несколько уровней реализации (от простого к сложному):
- **Уровень 1 (быстро):** генерируем презентацию (slides) → каждой слайд озвучиваем TTS → склеиваем через `ffmpeg` с автоматическими переходами и подсветкой текущей буллеты. По сути — slideshow с voice-over.
- **Уровень 2:** генерация **анимаций** через **Manim** (Python, math/CS-визуализации, как у 3Blue1Brown) или **Remotion** (React-видео — анимации через JSX, рендер на сервере).
- **Уровень 3:** AI-видео целиком — **Veo 3 (Google)**, **Sora 2 (OpenAI)**, **Runway Gen-4**, **Pika**, **Kling**. Это дорого и пока сюжетно ограниченно. На практике для учёбы лучше уровни 1–2.

#### Essay Grader
- Загрузка эссе → промпт-шаблон с рубрикой (`thesis`, `evidence`, `analysis`, `organization`, `style`, `mechanics`, `citations`).
- LLM возвращает структурированный JSON: `{rubric_scores, overall_score, comments_inline: [{paragraph_id, type, suggestion}], rewrites}`.
- Фронт рендерит **inline-комментарии** поверх текста (как в Google Docs). Нужно сохранить смещения символов в исходном тексте — самое простое: парсим в `prosemirror`-документ, сопоставляем по `node_id`.
- AI-detection score: `gptzero` API / `originality.ai` API, либо собственная perplexity-метрика на open-source модели.

#### Arcade / PDF to Game
StudyFetch публично рассказывает, что в Arcade пока **2 шаблона**: **Rocket Defender** (отстреливай неправильные ответы / атакуй цели правильными) и **Platform Jump** (платформер, прыгаешь по платформам с правильными ответами). Стиль выбирается пользователем (Retro 80's, Neon Cyberpunk, Space Adventure и др.).

Их подход — прекрасный шаблон для нашей реализации (см. раздел 4).

#### Plugins / Mini Apps (кастомизация Spark.E + свои мини-приложения)
- **Plugins** — это в действительности **system prompt presets + tool whitelisting**: `plugin(id, name, system_prompt, allowed_tools, allowed_models)`.
- **Mini Apps** — лёгкая mini-app платформа:
  - DSL: декларативный JSON/YAML, описывающий формы, кнопки, шаги, обращения к LLM/API.
  - Рендерер: React-компонент, который читает DSL и рисует UI.
  - Изоляция: если разрешите user-generated JS — только в `iframe sandbox` или **WebContainers** (StackBlitz) / `qjs-emscripten` (QuickJS в браузере). Никакого `eval()` без песочницы.

#### Study Plan + Calendar
- Вход: `target_date`, `subjects[]` (загруженные сессии), `available_hours_per_day`.
- LLM возвращает план в формате `{day, blocks: [{start, end, session_id, activity_type, intensity}]}`.
- Календарь хранится локально + интеграция с **Google Calendar API**, **Apple Calendar (CalDAV)**, **iCal-export** (`.ics`-файл).
- Адаптация: если вчера не закрыл блок — алгоритм сдвигает оставшиеся, пересчитывает плотность.

#### Text with Spark.E (SMS)
- **Twilio Programmatic Messaging** (`Messages API`) или **MessageBird** для глобального SMS, **SmsAero/SMSC.ru** для РФ.
- Webhook на `POST /webhooks/sms` → `from_phone` → находим юзера → передаём в LLM с контекстом → ответ через тот же канал.
- Лимиты: пагинация длинных ответов (160 символов / SMS — **разбивайте на сообщения**), preference на iMessage / WhatsApp Business / Telegram bot, если сидит дешевле.

#### For Teachers / For Institutions
- **Класс/курс** иерархия: `org → course → section → student`.
- **LTI 1.3** (`ims-global` стандарт) — для интеграции с Canvas, Moodle, Blackboard, D2L. Используйте `node-lti-1.3` или `pylti1.3`. Это **обязательная** фича для университетов.
- **SSO:** SAML 2.0 (для университетов), OIDC, Google Workspace, Microsoft 365.
- **Аналитика преподавателя:** агрегация прогресса студентов, weak topics по классу, leaderboard класса.

---

## 4. Readwise Reader — функции и реализация

**Концепция:** «one inbox for everything you read» — единый read-it-later для статей, новостей, RSS, PDF, EPUB, YouTube, Twitter-тредов и newsletter'ов, с превосходным выделением, AI-помощником **Ghostreader**, синхронизацией хайлайтов в Readwise (Daily Review со spaced repetition) и тончайшей кастомизацией под power-readers. Это не AI-репетитор и не сервис конспектов — это **долговременная reading-инфраструктура** с инструментами активного чтения. Идеально пристраивается к нашему study-сервису, потому что закрывает дыру всех трёх референсов: они работают только с тем, что ты сам им загрузил, а Reader даёт постоянный поток входящего контента.

### 4.1 Функции (как у них)

#### Источники контента (универсальный inbox)
- **Статьи** (read-it-later) — экстракция чистого текста с любой веб-страницы.
- **PDF** (drag-drop, до сотен мегабайт; режимы text-view и original-view).
- **EPUB** (полноценный книжный ридер с пагинацией).
- **YouTube-видео** — встроенный плеер с time-synced транскриптом, навигация по транскрипту кликом, **enhanced transcripts** (AI-исправление пунктуации/абзацев у автогенерированных субтитров).
- **Twitter / X треды** — авто-сборка длинного треда в нормальную длинную статью.
- **Newsletter'ы** — у каждого пользователя личный e-mail вида `you@reader.io`, на который подписываешься в любой email-рассылке вместо личного ящика.
- **RSS-фиды** — авто-детект RSS на любой странице (кнопка `Subscribe` в сайдбаре), импорт OPML, **папки RSS**.
- **Browser extension** (Chrome / Firefox / Safari / Edge) — «save to Reader» с любой страницы, выделение прямо на live-странице (highlight overlay поверх веб-сайта).
- **Mobile share sheet** (iOS, Android) — «поделиться → Reader» из любого приложения.
- **Drag-and-drop** + **public URL upload**.
- **Миграция** из Pocket / Instapaper / Feedly / Matter одной кнопкой.

#### Организация библиотеки
- **Library configurations:** Default (`Inbox / Later / Archive`), **Triage** (более явный workflow «новое → разобрать → отложить → архив»), Custom.
- **Filtered Views** — сохранённые умные подборки на DSL-запросах: `tag:ai AND domain:nytimes.com AND saved>7days`.
- **Tags** + автоматический Ghostreader **auto-tag**.
- **Search** (полнотекстовый по всему inbox + по выделениям).
- **Folders** для RSS.
- **Document/Highlight metadata:** `title, author, source_url, domain, published_at, saved_at, reading_progress, reading_time, summary, word_count`.

#### Чтение (UX, заточенный на power-readers)
- **Distraction-free reader** — единый шрифт, ширина колонки, полное удаление трекеров, рекламы, попапов.
- **Кастомизация типографики:** шрифт, кегль, межстрочный, ширина, тёмная тема, sepia, paged scroll vs vertical.
- **Highlighting & annotations:** выделение цветами, ноут на каждый highlight, ноут на документ.
- **Ghostreader-prompt over selection** (см. ниже).
- **Resume position** на каждом документе на всех устройствах.
- **Keyboard shortcuts** на всё («killer-фича» для power-users).
- **TTS «Listen mode»** — озвучка любого документа через AI-голоса (у них через Unreal Speech).
- **Sharing** — публичная аннотированная страница документа (read-only публичный URL).

#### Ghostreader (AI-ассистент)
- **Default prompts:** define word, summarize document, look up term/character/location, expand concept, translate, blurb для newsletter, и т.д.
- **Custom prompts** — полноценный mini-DSL: переменные (`{{document.title}}`, `{{highlight.text}}`, `{{user.language}}`), subroutines, scope-привязка.
- **Scope:** `document` (для всего документа), `paragraph` (на выделение >4 слов), `word/phrase` (на 1–4 слова), `automatic` (запускается при сохранении документа).
- **Auto-summarize + auto-tag** на каждый сохранённый документ.
- **Chat with the document** — RAG-чат поверх ровно одного документа.
- **Prompt Library** — публичный community-репозиторий промптов с импортом в один клик.
- **Hotkeys:** `G` для prompt над выделением, `Shift+G` для prompt над всем документом.

#### Highlight pipeline (мост в Readwise classic)
- Хайлайты автоматически синхронизируются в Readwise.
- **Daily Review** — каждый день N случайных хайлайтов в виде «карточек» (адаптивная частотность по типу документа, **Frequency Tuning**).
- **Mastery / spaced repetition** — внутренний алгоритм; экспорт в **Anki**, Obsidian, Notion, Roam, Logseq, Markdown, Evernote, Bear; полноценная **Highlights API**.

#### Платформы
- Web + Desktop (Mac, Windows).
- iOS, Android.
- Chrome / Firefox / Safari / Edge extensions.
- Public REST API для разработчиков.

### 4.2 Реализация (что брать в код)

#### Inbox-pipeline (универсальный сейв)
Любой источник проходит **один и тот же конвейер**: `ingest → fetch → extract → store_html_text → trigger_auto_prompts → notify`.

```
user saves URL/file/email
  └─ enqueue job(kind, payload)
      └─ extractor by kind:
          - article  → readability + trafilatura
          - pdf      → PyMuPDF + pdfplumber (text + page thumbs)
          - epub     → ebooklib + xhtml extraction
          - youtube  → youtube-transcript-api → fallback Whisper
          - twitter  → unroll via API/Nitter/RSSHub
          - rss      → feedparser → per-entry sub-job
          - email    → SES/Postmark inbound → MIME parser
      └─ normalize → {html, text_md, hero_image, author, published_at, word_count, est_read_time}
      └─ chunk + embed (как у нас в основном пайплайне)
      └─ Ghostreader auto-prompts (auto-summary + auto-tag)
      └─ push WS event "document_ready"
```

**Конкретные библиотеки:**
- Article extraction: `mozilla/readability` (через `@mozilla/readability` в Node), `postlight/parser`, `trafilatura` (Python — лучше держит на разнотипных сайтах).
- PDF: `PyMuPDF` (fitz), `pdfplumber`, `pdf2image` для превью.
- EPUB: `ebooklib`, `epub.js` (web-рендер с пагинацией).
- YouTube transcript: `youtube-transcript-api`, `yt-dlp --write-auto-sub`.
- Twitter unrolling: ‘twitter-thread-unroller’ через свой API-доступ или RSSHub.
- RSS: `feedparser` (Python) / `rss-parser` (Node), polling + ETag/If-Modified-Since.
- OPML import/export: `opml.js`.
- Inbound email: AWS SES Inbound + S3, либо Postmark Inbound, либо self-host `Cloudmailin` / `Improvmx`. Каждый user получает unique alias `<random>@inbox.{ourdomain}.com`.
- Mobile Share Sheet: iOS — `Share Extension` target в Xcode; Android — Intent filter `text/plain`/`text/html`.
- Browser extension: Manifest V3, `chrome.contextMenus` + `chrome.action.onClicked`, передача активного URL + `<title>` в наш API. Highlight overlay — отдельный content_script с прослойкой для Range API (см. ниже).

#### Web Highlighting (выделение прямо на live-странице)
Главный технически нетривиальный кусок Reader.
- Работа с DOM `Selection` / `Range` API.
- При выделении — нормализуем range в **CFI**-подобный селектор: `(start_xpath, start_offset, end_xpath, end_offset)` + fallback `(text_quote, prefix, suffix)` (как в **Hypothes.is** / W3C Web Annotation Data Model).
- Сохраняем оба селектора. При повторном открытии страницы — пробуем восстановить по xpath, если страница изменилась — fallback на text-quote (поиск по тексту с учётом контекста).
- Готовая основа: **`apache/incubator-annotator`**, **`hypothesis/anchoring`**, **`web-annotation-protocol`**.
- Overlay UI: накладной shadow-DOM-контейнер с подсветками, всплывающее меню «Highlight / Note / Ghostreader».

#### Library configurations & filtered views
- Сущности: `library_location(id, user_id, kind /* inbox|later|archive|custom */, name, order)`.
- `document.location_id` — простой fk.
- **Filter DSL** — простой парсер запросов: tokenize → AST → SQL/Elastic-query.
  ```
  tag:ai domain:nytimes.com AND saved>7d AND read:false
  ```
  Реализация: `peggy.js` / `nearley.js` для парсера, далее AST → Postgres `WHERE`-клауза или Elasticsearch DSL.
- Сохранённые views — `saved_view(id, user_id, name, dsl, is_pinned)`.

#### YouTube reader (видео + time-synced transcript)
- Frontend: встроенный `<iframe>` YouTube IFrame API (либо `react-youtube`).
- Транскрипт: чанки с `start`, `end`, `text` (word-level если доступно).
- **Время → подсветка чанка:** на `onTimeUpdate` (раз в 250 мс) находим текущий чанк бинарным поиском.
- **Клик на параграф транскрипта → seek на видео:** `player.seekTo(chunk.start, true)`.
- **Autoscroll:** скроллим контейнер транскрипта, чтобы текущий чанк был в центре.
- **Enhanced transcript:** прогон автогенерированного текста через LLM (`Restore punctuation, paragraph breaks, capitalization. Preserve word-level timestamps. Output JSON.`) — кэшируем результат в БД.
- Highlights в транскрипте — на чанк или на фрагмент с word-level offsets.

#### Ghostreader (AI с custom prompts и scopes)
Ключевые сущности:
```
prompt(id, user_id|null /* null = global default */, name, scope /* document|paragraph|word|automatic */,
       template_md, model, output_target /* note|chat|highlight_note|document_note */, hotkey)
```
- Шаблонизатор: **Liquid** (`liquidjs`) или **Jinja2** — поддерживает переменные и subroutines.
- Variables, доступные в промпте:
  - `document.title`, `document.author`, `document.url`, `document.text`, `document.summary`, `document.tags`
  - `selection.text`, `selection.context_before`, `selection.context_after`
  - `user.language`, `user.preferred_voice`
- Auto-prompts (`scope:automatic`) запускаются по очереди в воркере на событии `document_extracted`.
- Output route:
  - `note` → новый Ghostreader-чат-экран
  - `highlight_note` → пишет в `highlight.note`
  - `document_note` → пишет в `document.note`
  - `chat` → отправляет как первое сообщение в чате документа
- **Hotkeys**: `G` — prompt picker над выделением, `Shift+G` — prompt picker над документом, кастомные по prompt'у.
- **Prompt Library:** сущность `public_prompt(slug, author_id, scope, template, downloads, rating)` — публичный реестр с импортом одной кнопкой.

#### Listen mode (TTS)
- Очередь параграфов → TTS-провайдер (Unreal Speech / ElevenLabs / OpenAI / Cartesia).
- Кэшируем mp3 на S3, ключ — `hash(text + voice + speed)`.
- Player: HTML5 `<audio>` с сшивкой через MediaSource API; синхронная подсветка текущего параграфа.
- Плейлист: можно слушать «весь Inbox / весь тег / view» подряд, как подкаст.

#### Mobile reader (iOS/Android)
- Offline-кэш: SQLite (Room/Core Data) + локальный файлстор.
- Sync: incremental, по `updated_at` cursor (как у Pouch/Couch). При конфликте — last-write-wins по полю; для highlights merge-by-id.
- Background fetch для RSS-обновлений (iOS BackgroundTasks).
- Mobile share-extension возвращает «Saved to Reader» toast.

#### Daily Review + spaced repetition хайлайтов
- Алгоритм: **FSRS** (тот же, что у нас для flashcards) — а не SM-2.
- Сущности: `highlight`, `highlight_state(stability, difficulty, due_at)`, `highlight_review(rating, ts)`.
- **Frequency Tuning:** множители на тип документа / тег / источник: `boost_factor in [0..3]`.
- Daily Review = выборка top-N по `due_at` + случайность; UI — карточки в свайп-стеке (как Tinder).
- Экспорт в Anki: `genanki` (Python) → `.apkg` файл с note type, который содержит `text`, `note`, `source_url`, `tags`.
- Экспорт в Obsidian/Notion/Roam: уже описано в разделе Zachet.

#### Public sharing аннотированных документов
- `share_link(slug, document_id, allow_highlights, allow_chat, expires_at, password_hash)`.
- Read-only страница рендерит `document.text_md` + `highlights[]` + `notes[]`. Для чужих хайлайтов — другая палитра.
- OG-image: SSR-рендер документа в HTML → `puppeteer` → PNG (генерим динамически по slug).

#### Public REST API (как у Readwise)
- Pattern: `/v3/documents`, `/v3/highlights`, `/v3/feeds`. Bearer-токены пользователя.
- Webhooks `document.saved`, `highlight.created` — для интеграций (Notion-sync, Obsidian-plugin и пр.).

### 4.3 Зачем это нужно нашему сервису (что выигрываем, добавив Reader-функции)

1. **Закрываем дыру всех трёх референсов.** Mindgrasp/Zachet/StudyFetch — это про «загрузил курс → подготовился». Reader — про **постоянный поток входящих знаний** (RSS по специальности, newsletter'ы профессоров, статьи на arXiv, YouTube-каналы). Без этого мы будем сервисом, в который заходят только перед сессией.
2. **Каждая статья / видео / PDF в Reader-инбоксе автоматически становится study-session нашей системы** — конспект, флешкарты, квиз, mind map уже есть в основном пайплайне. Reader — это просто продвинутый сборщик источников.
3. **Ghostreader-стиль custom-prompts** идеально лёг на наш `Plugins / Mini Apps` (см. StudyFetch). Один и тот же DSL: scope + template + variables + output target. Делаем общий движок «prompts» и переиспользуем.
4. **Daily Review хайлайтов** даёт долгосрочный engagement — не только «выучил курс и забыл», а **постоянная встреча со старым материалом**. Это и есть рецепт reten­tion'а у Readwise.
5. **API + share** = вирусная петля контента: одногруппник делится статьёй с твоими аннотациями → переходит на наш сайт → видит цену.
6. **Подписка-канал**: Reader — это $9.99/мес сам по себе. Добавив его как фичу к нашему AI-tutor'у за условные $14.99–$19.99/мес, мы оправдываем более высокую цену, чем у Mindgrasp/Zachet.

---

## 5. Сводная таблица: какие фичи в MVP, какие — позже

| Фича | MVP (1-й запуск) | v1.0 | v2.0 | Сложность реализации |
|---|:-:|:-:|:-:|:-:|
| AI Notes | ✓ |  |  | низкая |
| AI Summary | ✓ |  |  | низкая |
| AI Flashcards (+ FSRS) | ✓ |  |  | низкая |
| AI Quizzes (single/multi/short) | ✓ |  |  | средняя |
| AI Tutor (RAG-чат по сессии) | ✓ |  |  | средняя |
| Запись лекций (web + mobile) | ✓ |  |  | средняя |
| Загрузка PDF / YouTube |  ✓ |  |  | низкая |
| Загрузка PPT / VK / Vimeo |  | ✓ |  | низкая |
| OCR / Math OCR (Mathpix) |  | ✓ |  | средняя |
| Mind Maps (markmap/react-flow) |  | ✓ |  | низкая |
| Spark.E Visuals (vision Q&A) |  | ✓ |  | средняя |
| Audio Recap (NotebookLM-style) |  | ✓ |  | средняя |
| Tutor Me (state machine урок) |  | ✓ |  | высокая |
| Live Voice Call (LiveKit/Realtime) |  |  | ✓ | высокая |
| Explainer Video |  |  | ✓ | высокая |
| Essay Grader |  | ✓ |  | средняя |
| Practice Tests / Exam-Specific |  | ✓ |  | средняя |
| Chrome Extension |  | ✓ |  | средняя |
| Calendar / Study Plan |  | ✓ |  | средняя |
| Plugins / Mini Apps |  |  | ✓ | высокая |
| SMS / WhatsApp / Telegram bot |  | ✓ |  | низкая |
| Заявки на работы (orders) |  | ✓ |  | высокая |
| Генератор работ по ГОСТ |  |  | ✓ | высокая |
| LTI 1.3 / SSO для вузов |  |  | ✓ | средняя |
| **Мини-игры (Arcade) — см. ниже** | ✓ (1 шт.) | ✓ (3 шт.) |  | — |
| Reader: read-it-later + browser extension | ✓ |  |  | средняя |
| Reader: RSS + newsletter inbox (email-in) |  | ✓ |  | средняя |
| Reader: YouTube + transcript + enhanced transcript |  | ✓ |  | средняя |
| Reader: Twitter/X thread unrolling |  | ✓ |  | низкая |
| Reader: EPUB reader |  | ✓ |  | средняя |
| Reader: web highlighting (live page overlay) |  | ✓ |  | высокая |
| Reader: Ghostreader custom prompts (DSL) |  | ✓ |  | средняя |
| Reader: Listen mode (TTS playlist) |  | ✓ |  | средняя |
| Reader: Daily Review хайлайтов (FSRS) |  |  | ✓ | низкая |
| Reader: filter DSL + saved views |  | ✓ |  | средняя |
| Reader: public API + Anki/Obsidian/Notion export |  |  | ✓ | средняя |

---

## 6. Канонические модели данных (PostgreSQL, упрощённо)

```sql
user(id, email, lang, plan, created_at, ...)

study_session(id, user_id, title, status, lang, created_at, last_opened_at)

source_document(id, session_id, kind /* pdf|video|audio|youtube|web|text */,
                source_ref, s3_key, hash, duration_s, page_count, status)

transcript(id, source_id, text_md, language, words_jsonb /* word-level w/ ts */)

chunk(id, session_id, source_id, idx, text, tokens, embedding /* vector(1536) */,
      timestamps_range, page_range, image_ids)

note(id, session_id, version, structured_json, markdown, html, generated_with_model)

flashcard(id, session_id, front, back, hint, source_chunk_id, bloom_level)
flashcard_state(card_id, user_id, stability, difficulty, due_at, last_review_at)
flashcard_review(id, card_id, user_id, rating /* 1..4 */, ts)

quiz(id, session_id, kind /* practice|exam|drill */, settings_jsonb)
quiz_question(id, quiz_id, type, prompt, choices_jsonb, correct_jsonb,
              source_chunk_id, difficulty, bloom_level, exam_format)
quiz_attempt(id, quiz_id, user_id, score, started_at, finished_at)
quiz_answer(id, attempt_id, question_id, answer_jsonb, correct, ai_feedback)

mind_map(id, session_id, tree_jsonb, last_layout_jsonb)

chat_thread(id, session_id, user_id)
chat_message(id, thread_id, role /* user|assistant|tool */, content,
             retrieved_chunks_jsonb, model, tokens_in, tokens_out, ts)

artifact_job(id, session_id, kind /* notes|flashcards|quiz|recap|video|... */,
             status /* queued|running|done|failed */, started_at, finished_at, error)

study_plan(id, user_id, target_date, plan_jsonb)
study_calendar_event(id, plan_id, session_id, starts_at, ends_at, status)

org(id, name, kind /* school|university|company */)
classroom(id, org_id, name, course_code)
membership(id, user_id, org_id|classroom_id, role /* student|teacher|admin */)

share_link(id, slug, target_kind /* session|note|deck */, target_id,
           expires_at, can_edit, password_hash)

order(id, user_id, type, subject, deadline, status, files_jsonb, manager_id) -- зачет.app

-- Readwise Reader-style inbox
library_location(id, user_id, kind /* inbox|later|archive|custom */, name, order_idx)
saved_view(id, user_id, name, dsl, is_pinned)
feed_subscription(id, user_id, kind /* rss|newsletter|youtube_channel */,
                  source_url, title, folder_id, last_polled_at, etag)
inbox_email_alias(id, user_id, alias /* nanoid@inbox.ourdomain.com */)
document(id, user_id, kind /* article|pdf|epub|youtube|tweet|newsletter */,
         title, author, source_url, domain, location_id, tags_jsonb,
         word_count, reading_time_s, reading_progress, hero_image_url,
         summary, language, saved_at, published_at, status)
document_text(document_id, html, text_md, structure_jsonb)
highlight(id, document_id, user_id, text, note,
          selector_xpath /* {start_xpath, start_offset, end_xpath, end_offset} */,
          selector_quote /* {prefix, exact, suffix} */,
          color, tags_jsonb, created_at)
highlight_state(highlight_id, stability, difficulty, due_at, last_review_at)
highlight_review(id, highlight_id, user_id, rating, ts)
prompt(id, user_id|null, name, scope /* document|paragraph|word|automatic */,
       template_md, model, output_target /* note|chat|highlight_note|document_note */,
       hotkey, is_public)
public_prompt(slug, author_user_id, scope, template_md, downloads, rating)
```

---

## 7. Ключевые библиотеки и API (cheat sheet)

**LLM-роутер:** `OpenRouter`, или свой (Node — `Vercel AI SDK`, Python — `litellm`).

**Embeddings + Vector store:** `pgvector` (Postgres-extension, проще всего держать рядом с БД), `Qdrant` (если 100M+ векторов).

**ASR:**
- self-host: `faster-whisper`, `WhisperX` (с диаризацией), `whisper.cpp` (даже на iPhone).
- API: Deepgram, AssemblyAI, OpenAI Whisper API, Yandex SpeechKit, SaluteSpeech.

**TTS:** ElevenLabs (multilingual v2), Cartesia Sonic (low-latency), OpenAI tts-1-hd, Yandex SpeechKit.

**Realtime voice:** OpenAI Realtime API, Gemini Live, LiveKit Agents, Vapi, Retell.

**OCR:** Mistral OCR, Google Document AI, AWS Textract, Tesseract, Mathpix (для формул).

**Vision:** GPT-4o/5, Claude Sonnet 4.5, Gemini 2.5 Pro.

**Video AI:** Runway Gen-4, Pika, Kling, Sora 2, Veo 3, Hedra (talking head). Manim/Remotion для контролируемых анимаций.

**Документы / экспорт:** `python-docx`, `python-pptx`, `WeasyPrint`, `Puppeteer`, `Pandoc`, `react-pdf`, `martian` (md→Notion).

**Mind maps:** `markmap`, `react-flow`, `Mermaid`, `mind-elixir`.

**Read-it-later / Reader-стек:**
- Article extraction: `@mozilla/readability`, `@postlight/parser`, `trafilatura` (Python).
- RSS: `feedparser` (Python), `rss-parser` (Node), `opml.js`.
- Inbound email: AWS SES Inbound, Postmark Inbound, Cloudmailin.
- EPUB rendering: `epub.js`, `ebooklib` (Python).
- Web Annotations / highlighting on live pages: W3C Web Annotation Data Model, `apache/incubator-annotator`, `hypothesis/anchoring` (xpath + text-quote selectors).
- Twitter/X thread unrolling: RSSHub, `Nitter`-инстансы, `twitter-api-v2`.
- Browser extension boilerplate: `WXT`, `Plasmo`, `vite-plugin-web-extension`.
- Prompt templating (Ghostreader-style DSL): `liquidjs`, `Jinja2`, `nunjucks`.
- Filter/query DSL parser: `peggy.js`, `nearley.js`, `chevrotain`.
- TTS for Listen mode: ElevenLabs, Unreal Speech, OpenAI tts-1-hd, Cartesia Sonic.

**Math:** `KaTeX`, `MathJax`, `SymPy`, Wolfram Alpha API, `math.js`.

**Spaced repetition:** `fsrs.js` / `py-fsrs` (FSRS), `ts-fsrs`.

**Realtime UI:** Socket.IO / native WebSocket, SSE, **Liveblocks** (если хотите collab cursors / multiplayer notes).

**Auth:** Clerk / Auth.js (NextAuth) / Supabase Auth / Firebase Auth.

**Платежи:** Stripe (мир), ЮKassa / CloudPayments / Tinkoff (РФ), Paddle (для глобал-SaaS — берёт MoR на себя).

**Push:** APNs, FCM, OneSignal.

**Аналитика продукта:** PostHog (event analytics + feature flags + experiments + session replay), Mixpanel.

**LTI / SSO:** `node-lti-1.3`, `pylti1.3`, `passport-saml`, `simplesamlphp`.

---

## 8. Мини-игры для маркетинга (вместо Subway Surfers)

**Что важно понимать про маркетинговый эффект игр в edtech:**
- **Subway Surfers / Temple Run работают** не потому что бегут — а потому что у них **Compulsion Loop**: короткие сессии 30–90 сек, мгновенная обратная связь, рост скорости, стабильное «ещё разок».
- В edtech нужно **добавить к этому петлю обучения**: каждое действие в игре = ответ на вопрос/карточку из материала. Так игра становится не «таймкилл, а потом учусь», а сама **является учебой**.
- Виральность даёт **PvP / PvE с друзьями** и **publish-to-share** (короткое видео результата для TikTok/Reels).
- Лучшие референсы по retention (по убыванию):
  - **Blooket / Gimkit** (PIN-код, играют группами в реальном времени, 10+ режимов).
  - **Quizlet Match / Blocks / Blast** (сольные таймд-аркады поверх флешкарт).
  - **Duolingo** (стрики, лиги, hearts) — **не игра**, но уровень gamification, на который надо равняться.
  - **StudyFetch Arcade** (PDF→игра двух типов: Rocket Defender, Platform Jump).
  - **Brilliant.org** (puzzle-driven уроки, не классическая игра).
- Для маркетинга **не** делайте сложных 3D-аркад в первый запуск — они дорогие, плохо скейлятся под мобильные веб-плеера и не дают преимущества над студентским вниманием.

### Стек для всех мини-игр
- Движок: **Phaser 3** (canvas/WebGL, ровно под 2D-аркады), либо **PixiJS** + своя физика, либо **Construct 3** (no-code). Если нужно 3D — **Three.js** / **Babylon.js**, но не советую для первого релиза.
- Реактовая обвязка: один Phaser-канвас в `<div ref>`, общение «React → Phaser» через `EventEmitter`.
- Контент игры — генерится из тех же `flashcards` / `quiz_question` через адаптер `gameContentBuilder({ session_id, count, difficulty })`.

### Рекомендуемые **3 игры** в порядке приоритета

#### 7.1 «Match Race» — карточки на скорость (must-have, дёшево, виральная социалка)

**Аналоги:** Quizlet Match / Blocks, базовый mode Tinycards.
**Почему залетит:** короткая сессия (30–60 сек), мгновенный фидбэк, лидерборд по сессии (твоим друзьям / одногруппникам по shared-set'у), легко записать видео результата.

**Геймплей:**
- На экране 12 карточек: 6 терминов + 6 определений в перемешку.
- Тапаешь пары → исчезают.
- Таймер растёт; каждая ошибка — `+1 секунда`.
- В конце — твоё время и место в лидерборде (по этой сессии и среди всех друзей).
- **Daily Match challenge** — сегодня все играют по одному фиксированному набору, в пятничном дайджесте присылается «топ недели».

**Реализация:**
- Phaser 3, scene `MatchRaceScene`. Без физики. Просто `Sprite`-карточки + `pointerdown`-обработчик.
- Контент: `gameContentBuilder` отдаёт 6 пар `{front, back}` из `flashcard` сессии.
- Анти-чит: подсчёт времени на сервере (старт/финиш-эвенты с подписью), 6 пар за раунд, серия по 3–5 раундов.
- Шеринг: «Я набрал 22.4с в Match Race по теме X. Слабо побить? → ссылка с pre-loaded set».

**Виральный приём:** **Daily Match Streak** — играй ежедневно по любой своей теме, не теряй стрик. Заёмная механика у Duolingo, но в учёбе работает так же сильно.

#### 7.2 «Quiz Royale» — групповая live-игра по PIN-коду (must-have для маркетинга и B2B-учителей)

**Аналоги:** Kahoot Live, Blooket Battle Royale, Gimkit Trust No One.
**Почему залетит:** социал-механика «учитель/один студент создаёт игру → шлёт PIN → 5–300 человек заходят с телефонов» — это **главный** виральный механизм edtech 2018–202x. Это же канал захода в школы и универы.

**Геймплей (минимум 3 режима):**

1. **Classic Royale** — все отвечают на одни и те же вопросы синхронно. После каждого вопроса — лидерборд. Балл = `correct ? base + speed_bonus : 0`. Финал — топ-5.
2. **Tower Defense** — твой ответ = монета. Покупаешь башни. Сторонние игроки шлют тебе волны. Это копия Blooket Tower Defense, и студенты залипают именно туда (3-я по retention механика у Blooket, по их публичной аналитике).
3. **Imposter / «Шпион»** — 1–2 игрока (impostor) знают, что они impostor, остальные — crewmates. На каждый правильный ответ начисляется «энергия». Тратится на расследование / саботаж. Голосование — кто impostor. Это копирует Gimkit «Trust No One», работает как Among Us, и виральна именно из-за этого.

**Реализация:**
- Бэк: NestJS + `socket.io` (комната = `game:{pin}`). Состояние игры — конечный автомат на сервере (никогда не доверяйте клиенту в PvP).
- Pin: 6 цифр, in-memory (Redis), TTL 2 часа.
- Хост (учитель/студент): запускает с экрана / projector view; игроки заходят с `app.tld/join` с пином.
- Контент: `quiz_question` сессии + `study_session` или публичный «Set Marketplace».
- **Replay / shareable highlight:** записывайте серверные эвенты, можно потом прогнать через шаблон видео (Remotion) и сделать 30-сек ролик «как Иван взял первое место в Quiz Royale» → готовый TikTok.

**B2B-pro (apocrypha):** добавьте «Class Mode» с экспортом отчёта `per-student weak topics CSV` — это и закрывает учителя.

#### 7.3 «Knowledge Climb» — вертикальный платформер (наша версия «Subway Surfers, но для учёбы»)

**Аналоги:** Gimkit «Don't Look Down», старый Doodle Jump, Stack Tower.
**Почему залетит:** одиночная аркада, очень короткие раунды (45–120 сек), tactile (прыжок = тап), хорошо смотрится в TikTok / Reels (скриншот-видео).

**Геймплей:**
- Камера движется вверх. Персонаж карабкается по платформам.
- Каждые ~3 секунды появляется **карточка-вопрос** в верхнем-правом углу. Правильный ответ → платформы выше становятся стабильными, появляется бонус-импульс. Неправильный → платформа под ногами «крошится», теряешь 10м высоты.
- Каждые 100м — **boss-вопрос** (длинная задача / multistep). Решил — переход на новый «биом» (стиль).
- Биомы — это `theme = retro80 | neon_cyberpunk | space | dark_academia | nature`. Это даёт коллекционный элемент: «открыл биом — флекси на профиле».
- Раунд заканчивается падением. Топ — высота (м). **Daily seed** — все сегодня играют по одной и той же сетке платформ → честный лидерборд.

**Реализация:**
- Phaser 3 с `arcade physics`.
- Платформы: процедурно генерируемые (seeded по дню), типы: `solid | brittle | moving | bonus`. Brittle ломаются на 2-м прыжке или при неправильном ответе.
- Карточки: накладной React-компонент поверх канваса, чтобы текст вопросов был адаптивным и доступным.
- Звук: 8-bit chiptune (бесплатные пакеты на freesound), success/fail jingles.
- Анти-чит: серверный seed + детерминистичная физика → каждый кадр клиента подтверждается (упрощённо: клиент шлёт «ответ на вопрос N» + «текущая высота» в discrete checkpoints, сервер валидирует против ожидаемого окна).
- Шеринг: на финале — auto-record canvas (`MediaRecorder`-API) → 10-сек webm → конвертим в mp4 на сервере → готовый shareable ролик.

**Главное преимущество перед «runner»-играми:** игрок здесь **сам выбирает темп** между вопросом и прыжком, это снимает «рефлекторный стресс» Subway Surfers и даёт время реально подумать.

### 7.4 Дополнительные идеи (если нужен 4-й вариант)

- **Word Bullet Hell** — двигаешь персонажа стрелочками, расстреливаешь правильные термины из летящих по экрану «пуль», избегаешь неправильных. Хорошо ложится на язык/словарный запас.
- **Cafe Tycoon** — ты бариста, заказы клиентов = вопросы, чем точнее — тем больше гостей. По мотивам Blooket Cafe — там рекордный retention.
- **Drag Build** — собираешь схему / молекулу / процесс из перемешанных элементов на время. Идеально для биологии/химии/CS-схем.
- **Mind Map Race** — две команды одновременно строят мейнд-мап темы; правильные узлы дают очки, неправильные — штраф.

### 7.5 Сводная таблица игр

| Игра | Жанр | Сольно/Соц | Сложность реализации | Маркетинговый эффект |
|---|---|:-:|:-:|:-:|
| **Match Race** | таймд-аркада на пары | сольно + лидерборд + share | низкая | средний (виральный), идеален как daily challenge |
| **Quiz Royale** | live PvP с PIN-кодом | соц 5–300 | средняя | **высокий** — главный B2C/B2B виральный канал |
| **Knowledge Climb** | вертикальный платформер | сольно + daily seed | средняя | высокий — TikTok/Reels-friendly |
| Cafe Tycoon | idle/tycoon | сольно | средняя | средний — высокий retention |
| Drag Build | пазл / схема | сольно или 1v1 | средняя | средний |

**Рекомендация:** в MVP добавить **Match Race** (она дешёвая и сразу даёт «вау» от PDF→игра), сразу после — **Quiz Royale** (это и виральный канал, и заход в B2B-edu), а **Knowledge Climb** запускать с медиа-кампанией, специально под TikTok.

---

## 9. Что важно сделать с самого начала, чтобы потом не переписывать

1. **Транскрипт + чанки + эмбеддинги — фундамент всего.** Не привязывайте notes/flashcards/quizzes к «raw файлу», привязывайте к `chunk_id`. Тогда и Spark.E Visuals, и mind map, и игры просто читают один индекс.
2. **Job queue с прогрессом per-artifact** — иначе UI «крутится без ответа» = главный churn-причина в edtech.
3. **LLM router с fallback и логированием cost/quality** — иначе через месяц утонете в счетах.
4. **WS/SSE-канал на каждую сессию** — без realtime-апдейтов фичи «record live lecture», «live quiz», «collaborative notes», «voice tutor» вы не сделаете.
5. **Внедрите PostHog / аналитику на день 1**, со всеми ключевыми событиями (`upload_started/finished`, `notes_generated`, `card_reviewed`, `quiz_completed`, `game_played`, `share_clicked`, `streak_kept/broken`). Без этого нечего оптимизировать.
6. **Сразу делайте share-link-инфру** (slugs, OG-image-генерация, превью) — это ваш бесплатный канал привлечения.
7. **i18n из коробки** — RU/EN-аудитории очень разные по поведению, делайте сразу.

---

## 10. Безопасность и compliance (без чего не пустят в школы/вузы)

- **GDPR / 152-ФЗ:** для РФ — хранение персональных данных в РФ (Yandex Cloud, VK Cloud, Selectel). Соглашение об обработке.
- **COPPA / FERPA / GDPR-K** для детей <13 — запрет на ряд функций (открытые чаты, публичный лидерборд по имени), требуется согласие родителя.
- **SOC 2 Type II** — нужен для Enterprise/университетов. Заранее ведите аудит-логи, доступы, MFA.
- **AI Safety:**
  - детектор «academic dishonesty» → flag «помощь сделать домашку за студента» вместо «объяснения».
  - PII-фильтрация в чанках (паспорта в загруженных PDF).
- **Content moderation** в мини-играх и шеринге — фильтр имён, чатов.

---

## 11. Что я бы делал по шагам (если бы строил с нуля)

1. **Неделя 1–2:** аутентификация + загрузка PDF/YouTube/audio + base UI (одна `study_session`).
2. **Неделя 3–4:** Whisper + chunking + embeddings + AI Notes + AI Summary (MVP контента).
3. **Неделя 5:** AI Flashcards + FSRS + AI Quizzes (single/multi) + AI Tutor (RAG-чат).
4. **Неделя 6:** Live recording (web + iOS Expo) + push-уведомления о готовности артефакта.
5. **Неделя 7:** **Match Race** — первая мини-игра. PostHog. Share-link. Streak.
6. **Неделя 8:** Mind maps + экспорт (PDF/Notion/Obsidian) + Chrome extension (save-to-our-app).
7. **Неделя 9–10:** **Reader-MVP** — read-it-later inbox (статьи + PDF + YouTube), browser extension, web highlighting, Ghostreader auto-summary/auto-tag. Каждый сохранённый документ автоматически становится study-session.
8. **Неделя 11–12:** Reader v1.1 — RSS, newsletter email-in alias, Twitter unrolling, EPUB, custom Ghostreader-prompts (DSL), filter views.
9. **Неделя 13:** **Quiz Royale** (live multiplayer). Лидерборд. Class Mode для учителей.
10. **Неделя 14:** Vision Q&A (Spark.E Visuals) + Audio Recap.
11. **Неделя 15+:** **Knowledge Climb** + Tutor Me + Voice Call. Daily Review хайлайтов (FSRS) + Listen mode (TTS).
12. **Параллельно:** Calendar/Study Plan, Essay Grader, Practice Tests с экзамен-форматами, LTI-интеграция для вузов, Reader public REST API.

---

**Источники для проверки фич:**
mindgrasp.ai (главная и /pricing); zachet.app (главная), App Store «Zachet: помощь студентам», zachet.tech; studyfetch.com и страницы /features/* (notes, flashcards, quizzes, chat, sparke-visuals, live-lecture, arcade, tutor-me, audio-recap, explainer-video, essay-grader, practice-tests, exam-questions, study-plan, calendar, call-with-sparke, mini-apps), studyfetch.com/arcade, studyfetch.com/pdf-to-game, studyfetch.mintlify.dev/docs/tutorial-doc-format/arcade; help.blooket.com (game-modes), help.gimkit.com (Don't Look Down), gimkit.wiki (Trust No One), help.quizlet.com (Match), blog.duolingo.com (streaks); readwise.io/reader, docs.readwise.io/reader (overview, guides, ghostreader, filtering, text-to-speech, sharing, library configurations), readwise.io/reader/update-april2024 (RSS folders, Web TTS, custom summaries), help.readwise.io (Daily Review / spaced repetition algorithm).
