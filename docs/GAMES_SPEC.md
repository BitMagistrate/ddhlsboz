# Игры для учебного приложения — техническая спецификация

> Документ описывает **архитектуру, механику, состояния, модели данных, события и контракты интеграции** для двух мини-игр внутри учебного приложения. Сами игры в этом документе **не реализуются** — это техническое задание для разработчика, чтобы можно было быстро встроить игры в приложение.

---

## 0. Контекст и цели

В приложении уже есть страница «Игра» (см. макет — раннер с подписями «Влево / Вправо / Прыжок», блоком «Не удалось загрузить вопросы», кнопками «Попробовать снова» и «К конспекту»). Из этой страницы понятны базовые контракты:

- Игры запускаются из конкретного **конспекта** пользователя (учебной заметки/курса).
- Перед запуском игра загружает **набор вопросов**, сгенерированных по конспекту.
- В игре пользователь и **играет**, и **отвечает на вопросы**.
- При ошибке загрузки показывается фолбэк-экран с «Попробовать снова» и «К конспекту».
- По итогу игры пользователь возвращается обратно к конспекту с результатом.

Этот документ описывает **две игры** в едином стиле интеграции:

| #   | Рабочее название (предложено)           | Стиль референса                  | Жанр                                     |
| --- | --------------------------------------- | -------------------------------- | ---------------------------------------- |
| 1   | **Brain Dash** (альт. «Quiz Sprint»)    | Subway Surfers / Study Surfers   | 3D endless-runner с вопросами в забеге   |

> Альтернативное название `Quiz Sprint` можно взять за основное; ниже по тексту используется `Brain Dash`.

---

## 1. Общие предпосылки

### 1.1 Стек

Предполагается, что приложение — это веб-приложение (на основе скриншота: HTML/CSS, тёмная тема, кириллица). Рекомендации:

- **Рендер игр:** `three.js` (3D) либо `PixiJS` / `Phaser 3` (2.5D-фолбэк для слабых устройств).
- **Игровой цикл:** собственный fixed-timestep loop поверх `requestAnimationFrame`.
- **Управление состоянием игры:** конечный автомат (FSM) внутри игры; наружу — события через шину.
- **Интеграция с приложением:** игра — это **изолированный модуль** (например, React-компонент `<GameHost game="brain-dash" />`), который монтируется на отдельный маршрут и принимает только данные/коллбэки.
- **Звук:** `Howler.js` или Web Audio API; настройки громкости берутся из общего профиля пользователя.

### 1.2 Контракт между приложением и игрой

Любая игра принимает на вход одинаковый объект `GameLaunchContext` и возвращает результаты одинаковой формы. Это позволяет добавить третью/четвёртую игру без изменений в приложении.

```ts
// shared/types.ts

export interface User {
  id: string;
  displayName: string;
  avatarUrl?: string;
  // Прогресс пользователя, общий для всех игр
  level: number;
  xp: number;
  coins: number;
}

export interface Konspekt {
  id: string;
  title: string;
  subject?: string;       // например "Биология", "История"
  topicTags?: string[];
}

export interface QuizQuestion {
  id: string;
  text: string;
  options: QuizOption[];  // обычно 3-4 варианта
  correctOptionId: string;
  explanation?: string;   // показывается после ответа
  difficulty: 1 | 2 | 3 | 4 | 5;
  sourceParagraphId?: string; // привязка к фрагменту конспекта
}

export interface QuizOption {
  id: string;
  text: string;
}

export interface GameLaunchContext {
  user: User;
  konspekt: Konspekt;
  questions: QuizQuestion[];      // уже загруженные (если null — игра грузит сама)
  settings: GameSettings;         // громкость, доступность, сложность
  callbacks: GameCallbacks;
}

export interface GameSettings {
  soundVolume: number;        // 0..1
  musicVolume: number;        // 0..1
  reducedMotion: boolean;
  difficultyHint?: 'auto' | 'easy' | 'normal' | 'hard';
  language: 'ru' | 'en';
}

export interface GameCallbacks {
  onExit: (reason: 'user' | 'finished' | 'error') => void;
  onResult: (result: GameResult) => void;     // итог раунда
  onProgressTick?: (tick: GameProgressTick) => void; // онлайн-телеметрия
  onAnswer?: (event: AnswerEvent) => void;    // на каждый ответ (для аналитики/SRS)
  onRequestExtraQuestions?: (count: number) => Promise<QuizQuestion[]>;
}

export interface GameResult {
  gameId: 'brain-dash';
  konspektId: string;
  durationMs: number;
  score: number;
  coinsEarned: number;
  xpEarned: number;
  questionsAsked: number;
  questionsCorrect: number;
  perQuestion: AnswerEvent[];
  highlights?: string[]; // достижения за раунд
}

export interface AnswerEvent {
  questionId: string;
  selectedOptionId: string | null; // null = пропуск/время вышло
  correct: boolean;
  timeToAnswerMs: number;
  difficulty: number;
}

export interface GameProgressTick {
  tMs: number;
  score: number;
  health: number;
}
```

### 1.3 Загрузка вопросов

Приложение либо передаёт `questions` напрямую, либо игра запрашивает их через `onRequestExtraQuestions(count)`. Рекомендуемый API на бэкенде:

```
GET  /api/konspekts/:id/quiz?game=brain-dash&count=N&difficulty=auto
     → { questions: QuizQuestion[] }
POST /api/games/results
     ← GameResult
     → { newXp, newLevel, newCoins, unlocked: [...] }
```

Если запрос упал — показывается тот самый фолбэк-экран:
- сообщение «Не удалось загрузить вопросы»
- кнопка **Попробовать снова** (повтор запроса)
- кнопка **К конспекту** (вызов `callbacks.onExit('error')`)

### 1.4 Общие UI-состояния каждой игры

```
INTRO  →  LOADING  →  PLAYING  ↔  PAUSED
                          │
                          ↓
                       RESULTS  →  (exit)

  При ошибке загрузки: LOADING → ERROR → (retry → LOADING) | (exit)
```

### 1.5 Общая обработка ввода

- **Клавиатура (десктоп):** стрелки + WASD + Space (см. макет) + `Esc` (пауза).
- **Тач (мобайл):** свайпы + тап. Кнопки на экране — опционально (для accessibility).
- **Геймпад:** опционально, стандартный mapping (D-pad/левый стик, A/B).
- Игра не должна перехватывать события вне своего DOM-контейнера.

### 1.6 Сохранение прогресса

Каждая игра имеет:

- **Раундовое состояние** (теряется при выходе/смерти, в `sessionStorage`).
- **Метапрогресс** (XP, монеты, открытые шапки/миры) — на сервере, реплика в `localStorage` для офлайна.

Ключи в `localStorage`:

```
game:brain-dash:meta:v1  → { coins, bestScore, ownedItems[], dailyStreak, ... }
shared:profile:v1        → { soundVolume, musicVolume, reducedMotion, ... }
```

### 1.7 Анти-чит (минимум)

- Очки и монеты, начисляемые **только** по `GameResult`, проверяет сервер: длительность раунда × коэффициенты сложности должны быть в разумных пределах.
- Сервер ре-валидирует `questionsCorrect` против `perQuestion[]`.
- Нельзя начислять XP/монеты, если `durationMs < 5 c` или `questionsAsked == 0`.

### 1.8 Доступность

- `reducedMotion` → отключает параллакс, тряску камеры, мигания.
- Цветовой контраст для текста вопросов ≥ AA.
- Альтернатива свайпам/жестам — экранные кнопки.
- Озвучка вопроса (TTS) — опционально, флаг в `GameSettings`.

---

## 2. Игра 1 — «Brain Dash» (раннер + квиз)

> Альтернативные названия на выбор: **Brain Dash**, **Quiz Sprint**, «Знай-Беги», «Мозго-Раш». Дальше — `Brain Dash`.

### 2.1 Концепт в одной фразе

Бесконечный 3D-раннер от третьего лица: персонаж бежит по дороге/улице, уворачивается от препятствий, собирает монеты, а каждые ~20–25 секунд впереди появляются **3 «ворот» с вариантами ответа** — нужно выехать в полосу с правильным ответом.

### 2.2 Аудитория и цель

- Цель пользователя: «быстро освежить тему конспекта», получить XP/монеты, побить рекорд.
- Целевая длительность раунда: **2–4 минуты**.
- Желаемое количество вопросов за раунд: **5–10**.

### 2.3 Игровой мир

- **Сцена:** стилизованная городская улица / тоннель / трасса (3 темы оформления на выбор; вариант темы можно привязать к `konspekt.subject`).
- **Полосы:** 3 параллельные дорожки. Игрок занимает одну из них.
- **Скорость:** растёт со временем по кривой `v(t) = v0 + k * sqrt(t)`, с потолком.
- **Длина забега:** ограничена либо здоровьем (3 жизни/удара), либо лимитом вопросов.

### 2.4 Управление

| Действие              | Клавиши          | Тач                |
| --------------------- | ---------------- | ------------------ |
| Сменить полосу влево  | `←` / `A`        | свайп влево        |
| Сменить полосу вправо | `→` / `D`        | свайп вправо       |
| Прыжок                | `↑` / `W` / `Space` | свайп вверх / тап |
| Подкат                | `↓` / `S`        | свайп вниз         |
| Пауза                 | `Esc` / `P`      | кнопка-«гамбургер» |

### 2.5 Сущности

- **Игрок (Runner):** позиция (lane, y, z), состояния `running / jumping / sliding / hit / dead`. Хитбокс адаптируется к состоянию.
- **Препятствия (Obstacle):**
  - `LowObstacle` — нужно прыгнуть (барьер).
  - `HighObstacle` — нужно подкатиться (балка).
  - `FullObstacle` — нужно сменить полосу.
  - `MovingObstacle` (машина) — движется навстречу/попутно.
- **Пикапы (Pickup):**
  - `Coin` — +1 монета.
  - `Magnet` (5 c) — притягивает монеты.
  - `Shield` (один удар поглощается).
  - `x2` (5 c) — двойной счёт.
  - `Boost` (3 c) — рывок и неуязвимость.
- **Ворота вопроса (QuestionGate):** триггер, при пересечении показывается оверлей с текстом вопроса и 3 полосы помечаются вариантами ответа.

### 2.6 Цикл «вопрос»

1. На дистанции `D_q` после старта/последнего вопроса спавнится **серия пред-маркеров**: над полосами появляются плашки с вариантами `A / B / C`, текст вопроса всплывает сверху (в HUD).
2. Игрок едет вперёд, может менять полосу.
3. Через `T_q` секунд (или при достижении линии-ворот) фиксируется полоса игрока.
4. Если ответ правильный — комбо +1, +score, опц. бонус-монеты, короткий VFX.
5. Если неправильный или нет ответа — комбо обнуляется, -1 здоровье, может быть лёгкое замедление.
6. Показывается `explanation` 1.5 c (можно отключить в настройках).
7. Возврат к гонке.

> Вопрос **не останавливает** бег. Это намеренно: «учеба под давлением» — фирменная фишка жанра.

### 2.7 Сложность и подача вопросов

- Стартовая сложность вопросов = средняя из `questions[]`.
- Если игрок ответил верно 3 раза подряд — приоритет следующего вопроса сдвигается в сторону `difficulty+1`.
- Если 2 раза подряд неверно — сдвиг в `difficulty-1`.
- Если в `GameLaunchContext.questions` кончились вопросы — вызывается `onRequestExtraQuestions(5)` (background prefetch при остатке ≤ 2).

### 2.8 Очки и валюта

```
score      = distance/10 + sum(coin)*1*multiplier + correctAnswer*100*multiplier
            - wrongAnswer*0  // штрафа очками нет, штраф здоровьем
coinsEarned = floor(coinsCollected) + correctAnswers * 5
xpEarned   = correctAnswers * (10 + difficulty*2)
```

`multiplier` — текущий бонус (`x2` пикап, комбо-серия и т.п.).

### 2.9 Состояния игры (FSM)

```
INTRO        — показ управления и темы
LOADING      — fetch вопросов и ассетов
COUNTDOWN    — 3 / 2 / 1 / GO
RUNNING      — основной геймплей (вкл. QUESTION_OVERLAY как substate)
HIT          — короткая анимация удара, потеря 1 жизни
PAUSED       — пауза по Esc / blur вкладки
GAME_OVER    — анимация падения
RESULTS      — итоги раунда, кнопки «Ещё раз» / «К конспекту»
ERROR        — фолбэк (повтор/выход)
```

### 2.10 Сетевые/файловые модели

```ts
// game/brain-dash/types.ts

export interface BrainDashConfig {
  laneCount: 3;
  baseSpeed: number;
  speedRamp: number;
  spawnIntervals: { obstacle: number; coin: number; pickup: number };
  questionEveryMeters: number; // например 600
  questionWindowMeters: number;
  livesMax: number;
}

export interface BrainDashRoundState {
  status: 'INTRO' | 'LOADING' | 'COUNTDOWN' | 'RUNNING' | 'HIT'
        | 'PAUSED' | 'GAME_OVER' | 'RESULTS' | 'ERROR';
  lives: number;
  distance: number;
  score: number;
  combo: number;
  multiplier: number;
  coins: number;
  activeQuestion?: ActiveQuestion;
  pickups: ActivePickup[];
}

export interface ActiveQuestion {
  question: QuizQuestion;
  laneToOptionId: Record<0 | 1 | 2, string>; // какая полоса = какой вариант
  spawnedAt: number; // ms
  resolveAtDistance: number;
}

export interface ActivePickup {
  kind: 'magnet' | 'shield' | 'x2' | 'boost';
  remainingMs: number;
}
```

### 2.11 Декомпозиция модулей

```
game/brain-dash/
  index.tsx              // <BrainDash /> — публичный компонент
  config.ts              // BrainDashConfig + балансировка
  engine/
    loop.ts              // fixed-step + render
    scene.ts             // three.js сцена, камера, освещение
    spawner.ts           // генерация препятствий/монет/пикапов/ворот
    player.ts            // контроллер игрока (lane, jump, slide, hitbox)
    physics.ts           // простая AABB-коллизия
    questionDirector.ts  // когда спавнить вопрос, привязка lane→option
    difficulty.ts        // подбор сложности следующего вопроса
    audio.ts             // SFX/музыка
  ui/
    Hud.tsx              // монеты, дистанция, жизни, мультипликатор
    QuestionOverlay.tsx  // вопрос сверху, всплывающее объяснение
    PauseMenu.tsx
    ResultsScreen.tsx
    ErrorScreen.tsx
  assets/                // модели/текстуры/звуки (lazy-loaded)
  state/
    fsm.ts               // конечный автомат
    store.ts             // RoundState (zustand/redux/локальный)
```

### 2.12 Публичный API компонента

```tsx
<BrainDash
  context={launchContext}
  onResult={ctx.callbacks.onResult}
  onExit={ctx.callbacks.onExit}
/>
```

Внутренний контракт:

- Компонент монтируется → `INTRO` → автостарт через 1 c или по клику.
- Компонент использует только `launchContext.questions` + `onRequestExtraQuestions`.
- На `Esc` / blur — `PAUSED`. На `Esc` второй раз — продолжение.

### 2.13 События телеметрии

```
brain_dash.round_started   { konspektId, questionsAvailable }
brain_dash.question_shown  { questionId, difficulty }
brain_dash.answer_given    { questionId, correct, ms }
brain_dash.hit             { reason: 'obstacle' | 'wrong_answer' | 'timeout' }
brain_dash.pickup_taken    { kind }
brain_dash.round_finished  { score, coins, xp, durationMs }
brain_dash.exit            { reason }
```

### 2.14 Производительность

- LOD для препятствий, инстансинг повторяющихся мешей.
- Тени — `low` по умолчанию, off при `reducedMotion`.
- Сегментированная генерация мира кусками по 50 м (пул объектов).
- Цель: 60 fps на ноутбуке среднего класса, ≥ 30 fps на средних смартфонах.

### 2.15 Балансировка (стартовые значения)

```
baseSpeed              = 12 m/s
speedRamp (per sec)    = 0.08
livesMax               = 3
questionEveryMeters    = 550
questionWindowMeters   = 80
spawnIntervals.obstacle= 1.6 s
spawnIntervals.coin    = 0.4 s
spawnIntervals.pickup  = 18 s
```

---

## 4. Общие компоненты

Чтобы добавить третью игру было дёшево, выносим в общий пакет:

```
game/common/
  types.ts            // см. п. 1.2
  contracts.ts        // GameLaunchContext / GameCallbacks
  questionsClient.ts  // загрузка/префетч вопросов
  hudPrimitives/      // ScoreText, LivesIcons, ComboMeter, ResultRow...
  fsm.ts              // generic FSM
  audio.ts            // обёртка над Howler
  input.ts            // унифицированный input (kb, touch, gamepad)
  telemetry.ts        // обёртка над аналитикой
  errorScreen.tsx     // тот самый фолбэк «Не удалось загрузить вопросы»
  resultsScreen.tsx   // унифицированный итог раунда
  pauseMenu.tsx
  accessibility.ts    // reducedMotion, TTS, font scale
  storage.ts          // обёртка над localStorage с версионированием
```

`<GameHost>` — высокоуровневый компонент в приложении:

```tsx
<GameHost
  gameId="brain-dash"
  konspekt={selectedKonspekt}
  user={currentUser}
  onExitToKonspekt={() => router.push(`/konspekt/${konspekt.id}`)}
/>
```

Он сам:
1. Грузит `questions` через `questionsClient`.
2. Рендерит нужную игру (lazy-import).
3. На `onResult` пушит результат на бэкенд и пересчитывает профиль.
4. На `onExit` уводит обратно к конспекту.

---

## 5. Точки интеграции в существующее приложение

Опираясь на скриншот, минимально нужны:

1. **Маршрут запуска игры** — `/konspekt/:id/play/:gameId` (или модальное окно поверх конспекта).
2. **Кнопка «Играть»** в карточке конспекта — на ней `<select>` или вкладки для выбора игры. Если игра одна — без выбора.
3. **Экран лоадинга/ошибки** — тот, что уже есть; вынести в `errorScreen.tsx` и переиспользовать обеими играми.
4. **Кнопка «К конспекту»** — на всех экранах игры (включая результаты), вызывает `onExit('user')`.
5. **Результат раунда** — модалка в стиле приложения, кнопки «Ещё раз» и «К конспекту».
6. **Метапрогресс** — на странице профиля пользователя: суммарный XP / уровень / монеты / коллекция лор-карточек.
7. **Ежедневные задания** (опционально, общие на обе игры):
   - «Сыграй 1 раунд Brain Dash»
   - «Ответь правильно на 20 вопросов за день»
   - Серии (streak) дней.
8. **Серверная сторона**:
   - `POST /api/games/results` — приём `GameResult`, валидация, начисление, ответ с новым `xp/coins/unlocks`.
   - `GET /api/konspekts/:id/quiz` — генерация/возврат вопросов; поддержка `?difficulty=auto&exclude=[]`.
   - `GET /api/user/profile` — для синка метапрогресса при логине.

---

## 6. Дорожная карта (предлагаемый порядок внедрения)

1. **Каркас `game/common`** + `GameHost` + контракты типов + `errorScreen` + `resultsScreen`.
2. **Brain Dash MVP**: 1 тема оформления, 1 типа препятствий, ворота вопросов, базовая сложность, без пикапов.
3. Полировка Brain Dash: пикапы, мультипликаторы, баланс, ассеты темы.
4. Серверные эндпоинты `quiz` и `results` + анти-чит.
5. Метапрогресс / ежедневки / серии.
8. Доступность, TTS, локализация (ru/en).
9. Мобильная адаптация (touch-controls).
10. Аналитика и A/B балансировки.

---

## 7. Предлагаемая структура файлов в репозитории

```
src/
  app/
    routes/
      konspekt.[id].play.[gameId].tsx   // запуск игры
  components/
    GameHost.tsx
  game/
    common/
      ... (см. п. 4)
    brain-dash/
      ... (см. п. 2.11)
  api/
    games.ts                            // questionsClient, resultsClient
```

---

## 8. Чек-лист «готово к внедрению»

- [ ] Согласовано финальное название (Brain Dash или альтернатива).
- [ ] Типы из п. 1.2 утверждены и положены в `src/game/common/types.ts`.
- [ ] Бэкенд умеет отдавать `QuizQuestion[]` по конспекту и принимать `GameResult`.
- [ ] Дизайнер выдал 1 тему для Brain Dash.
- [ ] Звукорежиссёр выдал минимальный набор SFX (шаг, прыжок, удар, монета, верный/неверный ответ, музыка лупом).
- [ ] Решено, как генерируются вопросы (LLM по конспекту? Ручная разметка? Смешанно?).
- [ ] Согласована политика анти-чита и максимум XP/день.
- [ ] Подключена телеметрия.

---

### Приложение A. Варианты названий

| Brain Dash (раннер)    |
| ---------------------- |
| Brain Dash             |
| Quiz Sprint            |
| Knowledge Rush         | Knowledge Saga            |
| Smart Surfers          | Story Lands               |
| «Знай-Беги»            | «Эрудит-Мир»              |
| «Мозго-Раш»            | «Конспект-Сага»           |
| «КвизРан»              | «МирЗнаний»               |

> Рекомендуемое название по благозвучию и узнаваемости: **Brain Dash**.
