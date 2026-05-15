import { useCallback, useEffect, useMemo, useState } from "react"

import { safeHref, sanitizeText } from "./lib/sanitize"

/**
 * Учёба — обёртка над `/api/study/*` (PR#9/24/25/G2/FIB/WT/MASTERY/27a).
 *
 * Сценарий пользователя:
 *  1. Загружает материал (text/url/audio-link/youtube/PDF).
 *  2. Получает AI-конспект (summary + key_moments + tips + glossary).
 *  3. Общается с Q&A-чатом по материалу 24/7.
 *  4. Тренируется на флэшкартах / Smart-Quiz / fill-in-the-blank / эссе.
 *  5. Делится материалом (viewer/editor invite) и смотрит mastery.
 *  6. На /pricing видит тарифы и записывается в waitlist.
 */

const API_BASE = (import.meta.env.VITE_API_BASE as string) || "http://localhost:8000"

const PROTOTYPE_URL = "https://chitai.bolt.host/#"

const HEADERS_USER = (): Record<string, string> => ({
  "X-User-Id": getOrCreateUserId(),
})

function getOrCreateUserId(): string {
  if (typeof window === "undefined") return "anon"
  let id = window.localStorage.getItem("chitai_user_id")
  if (!id) {
    id = "u-" + Math.random().toString(36).slice(2, 10)
    window.localStorage.setItem("chitai_user_id", id)
  }
  return id
}

type Material = {
  id: string
  user_id: string
  kind: string
  title: string
  status: string
  source_uri?: string | null
  language: string
  tariff: string
  created_at: number
  chunks_count?: number
  meta?: Record<string, unknown>
  conspect?: Conspect | null
  flashcards?: Flashcard[]
  quiz?: QuizItem[]
  fib?: FibItem[]
}

type Conspect = {
  summary: string
  key_moments: string[]
  tips: string[]
  glossary: Record<string, string>
}

type Flashcard = { id: string; front: string; back: string; hint: string }
type QuizItem = {
  id: string
  question: string
  options: string[]
  correct_index: number
  explanation: string
  explanation_wrong: string[]
}
type FibItem = { id: string; sentence_with_blank: string; answer: string; hint: string }

type QAAnswer = {
  question: string
  answer: string
  citations: { chunk_id: string; position: number; preview: string }[]
}

type Mastery = {
  buckets: { unfamiliar: number; learning: number; familiar: number; mastered: number }
  total_cards: number
  total_materials: number
}

type Tariffs = {
  tariffs: Record<
    string,
    {
      materials_per_month: number
      audio_minutes_per_month: number
      qa_per_day: number
      podcast: boolean
      essay_grading_per_month: number
      retention_days: number
      ru_residency_only: boolean
    }
  >
}

async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const resp = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      ...HEADERS_USER(),
      ...(init.headers || {}),
    },
  })
  if (!resp.ok) {
    const text = await resp.text().catch(() => "")
    throw new Error(`HTTP ${resp.status}: ${text || resp.statusText}`)
  }
  return (await resp.json()) as T
}

function fmtDate(ts: number): string {
  if (!ts) return "—"
  const d = new Date(ts * 1000)
  return d.toLocaleString("ru-RU")
}

export default function StudyTab() {
  const [materials, setMaterials] = useState<Material[]>([])
  const [active, setActive] = useState<Material | null>(null)
  const [mastery, setMastery] = useState<Mastery | null>(null)
  const [tariffs, setTariffs] = useState<Tariffs | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const refreshList = useCallback(async () => {
    try {
      setError(null)
      const data = await api<{ items: Material[] }>("/api/study/materials")
      setMaterials(data.items || [])
      // Если активный материал есть в списке — обновляем его поля.
      if (active) {
        const fresh = (data.items || []).find((m) => m.id === active.id)
        if (fresh) setActive(fresh)
      }
    } catch (e) {
      setError((e as Error).message)
    }
  }, [active])

  useEffect(() => {
    void refreshList()
    void api<Mastery>("/api/study/mastery").then(setMastery).catch(() => undefined)
    void api<Tariffs>("/api/study/tariffs").then(setTariffs).catch(() => undefined)
  }, [refreshList])

  async function ingestText(title: string, text: string): Promise<void> {
    if (!text.trim()) return
    setLoading(true)
    try {
      const created = await api<Material>("/api/study/ingest/text", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title, text }),
      })
      setActive(created)
      await refreshList()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }

  async function ingestUrl(url: string): Promise<void> {
    setLoading(true)
    try {
      const created = await api<Material>("/api/study/ingest/url", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url }),
      })
      setActive(created)
      await refreshList()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }

  async function ingestPdf(file: File): Promise<void> {
    setLoading(true)
    try {
      const fd = new FormData()
      fd.append("file", file)
      fd.append("title", file.name)
      const resp = await fetch(`${API_BASE}/api/study/ingest/pdf`, {
        method: "POST",
        headers: HEADERS_USER(),
        body: fd,
      })
      if (!resp.ok) {
        const text = await resp.text().catch(() => "")
        throw new Error(`HTTP ${resp.status}: ${text || resp.statusText}`)
      }
      const created = (await resp.json()) as Material
      setActive(created)
      await refreshList()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }

  async function ingestAudio(title: string, consent: boolean, ageOk: boolean): Promise<void> {
    setLoading(true)
    try {
      const created = await api<Material>("/api/study/ingest/audio", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title, biometry_consent: consent, age_ok: ageOk }),
      })
      setActive(created)
      await refreshList()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }

  async function ingestVideo(url: string): Promise<void> {
    setLoading(true)
    try {
      const created = await api<Material>("/api/study/ingest/video", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url }),
      })
      setActive(created)
      await refreshList()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }

  async function deleteMaterial(id: string): Promise<void> {
    if (!window.confirm("Удалить материал? Все чанки, флэшкарты и эссе будут стёрты (152-ФЗ).")) {
      return
    }
    try {
      await api(`/api/study/material/${id}`, { method: "DELETE" })
      if (active?.id === id) setActive(null)
      await refreshList()
    } catch (e) {
      setError((e as Error).message)
    }
  }

  return (
    <section className="py-7 space-y-6">
      <header className="space-y-2">
        <h2 className="text-2xl font-semibold">Учёба</h2>
        <p className="max-w-3xl text-sm text-zinc-300">
          Загрузите любой материал — текст, веб-страницу, PDF, видео или аудио. ИИ-ассистент
          ЧитАИ сделает конспект, ключевые моменты, флэшкарты, Smart-Quiz и проведёт по нему
          интерактивную сессию вопрос-ответ. Все данные — на серверах в РФ, 152-ФЗ.
        </p>
        <p className="text-xs text-zinc-500">
          Прототип лендинга:{" "}
          <a
            className="underline text-amber-300 hover:text-amber-200"
            href={safeHref(PROTOTYPE_URL)}
            target="_blank"
            rel="noopener noreferrer"
          >
            {sanitizeText(PROTOTYPE_URL)}
          </a>
        </p>
      </header>

      {error && (
        <div className="rounded-md border border-rose-700 bg-rose-950/40 px-4 py-3 text-sm text-rose-200">
          {sanitizeText(error)}
        </div>
      )}

      <Uploader
        loading={loading}
        onText={ingestText}
        onUrl={ingestUrl}
        onPdf={ingestPdf}
        onAudio={ingestAudio}
        onVideo={ingestVideo}
      />

      <div className="grid gap-6 lg:grid-cols-[260px_1fr]">
        <MaterialList
          items={materials}
          active={active?.id || null}
          onPick={setActive}
          onDelete={deleteMaterial}
        />
        <div className="space-y-6">
          {active ? (
            <MaterialPane material={active} onChanged={refreshList} />
          ) : (
            <EmptyHint />
          )}
        </div>
      </div>

      <MasteryRow mastery={mastery} />

      <Pricing tariffs={tariffs} />
    </section>
  )
}

function EmptyHint() {
  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-950/40 p-6 text-sm text-zinc-400">
      <h3 className="text-sm font-semibold text-zinc-200 mb-2">Как это работает</h3>
      <ol className="list-decimal pl-5 space-y-1">
        <li>Загрузите материал в любом формате выше.</li>
        <li>Получите AI-конспект и ключевые моменты.</li>
        <li>Спрашивайте у Q&A-чата всё, что непонятно.</li>
        <li>Тренируйтесь на флэшкартах, Smart-Quiz и эссе.</li>
        <li>Делитесь материалом с одноклассниками или учителем.</li>
      </ol>
    </div>
  )
}

type UploaderProps = {
  loading: boolean
  onText: (title: string, text: string) => Promise<void>
  onUrl: (url: string) => Promise<void>
  onPdf: (file: File) => Promise<void>
  onAudio: (title: string, consent: boolean, ageOk: boolean) => Promise<void>
  onVideo: (url: string) => Promise<void>
}

function Uploader(props: UploaderProps): JSX.Element {
  const [mode, setMode] = useState<"text" | "url" | "pdf" | "audio" | "video">("text")
  const [title, setTitle] = useState("")
  const [text, setText] = useState("")
  const [url, setUrl] = useState("")
  const [pdf, setPdf] = useState<File | null>(null)
  const [consent, setConsent] = useState(false)
  const [ageOk, setAgeOk] = useState(false)

  const submit = async (): Promise<void> => {
    if (mode === "text") return props.onText(title || "Без названия", text)
    if (mode === "url") return props.onUrl(url)
    if (mode === "pdf" && pdf) return props.onPdf(pdf)
    if (mode === "audio") return props.onAudio(title || "Аудиозапись", consent, ageOk)
    if (mode === "video") return props.onVideo(url)
  }

  const Modes: { id: typeof mode; label: string }[] = [
    { id: "text", label: "Текст" },
    { id: "url", label: "Ссылка / статья" },
    { id: "pdf", label: "PDF" },
    { id: "audio", label: "Аудио" },
    { id: "video", label: "YouTube / VK" },
  ]

  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-950/40 p-5 space-y-4">
      <div className="flex flex-wrap gap-2">
        {Modes.map((m) => (
          <button
            key={m.id}
            type="button"
            onClick={() => setMode(m.id)}
            className={`rounded-md border px-3 py-1.5 text-sm transition-colors ${
              mode === m.id
                ? "border-amber-300 bg-amber-300/10 text-amber-200"
                : "border-zinc-700 text-zinc-400 hover:text-zinc-200"
            }`}
          >
            {m.label}
          </button>
        ))}
      </div>

      <div className="grid gap-3 lg:grid-cols-2">
        {mode === "text" && (
          <>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Заголовок материала"
              className="rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100"
            />
            <span className="text-xs text-zinc-500 self-center">
              Вставьте любой текст (учебник, статья, ваш конспект)
            </span>
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="Вставьте текст до 200 000 символов…"
              rows={6}
              className="rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 lg:col-span-2"
            />
          </>
        )}
        {mode === "url" && (
          <input
            type="url"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://example.ru/article"
            className="rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 lg:col-span-2"
          />
        )}
        {mode === "pdf" && (
          <input
            type="file"
            accept="application/pdf"
            onChange={(e) => setPdf(e.target.files?.[0] || null)}
            className="rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 lg:col-span-2"
          />
        )}
        {mode === "audio" && (
          <>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Название (например, «Лекция №3»)"
              className="rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100"
            />
            <span className="text-xs text-zinc-500 self-center">
              Аудио = биометрия. Для загрузки нужны согласия (152-ФЗ).
            </span>
            <label className="flex items-center gap-2 text-sm text-zinc-300 lg:col-span-2">
              <input
                type="checkbox"
                checked={consent}
                onChange={(e) => setConsent(e.target.checked)}
              />
              Я гарантирую согласие участников записи и/или запись в публичном месте
            </label>
            <label className="flex items-center gap-2 text-sm text-zinc-300 lg:col-span-2">
              <input type="checkbox" checked={ageOk} onChange={(e) => setAgeOk(e.target.checked)} />
              Мне 18+, либо есть согласие родителей (для 14–17)
            </label>
          </>
        )}
        {mode === "video" && (
          <input
            type="url"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://youtu.be/… или https://vk.com/video…"
            className="rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 lg:col-span-2"
          />
        )}
      </div>

      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={() => void submit()}
          disabled={props.loading}
          className="rounded-md bg-amber-300 px-4 py-2 text-sm font-semibold text-zinc-900 disabled:opacity-40"
        >
          {props.loading ? "Загружаем…" : "Создать материал"}
        </button>
        <span className="text-xs text-zinc-500">
          Все данные хранятся в РФ. Удаление — каскадно по 152-ФЗ.
        </span>
      </div>
    </div>
  )
}

function MaterialList({
  items,
  active,
  onPick,
  onDelete,
}: {
  items: Material[]
  active: string | null
  onPick: (m: Material) => void
  onDelete: (id: string) => Promise<void>
}): JSX.Element {
  if (!items.length) {
    return (
      <div className="rounded-lg border border-zinc-800 bg-zinc-950/40 p-4 text-xs text-zinc-500">
        Пока нет материалов.
      </div>
    )
  }
  return (
    <ul className="space-y-2">
      {items.map((m) => (
        <li
          key={m.id}
          className={`rounded-md border px-3 py-2 text-sm transition-colors ${
            active === m.id
              ? "border-amber-300 bg-amber-300/5"
              : "border-zinc-800 bg-zinc-950/40 hover:border-zinc-600"
          }`}
        >
          <button
            type="button"
            onClick={() => onPick(m)}
            className="w-full text-left"
          >
            <div className="font-medium text-zinc-100">{sanitizeText(m.title)}</div>
            <div className="text-xs text-zinc-500 flex items-center gap-2">
              <span>{m.kind}</span>
              <span>·</span>
              <span>{fmtDate(m.created_at)}</span>
              <span className={`ml-auto ${m.status === "ready" ? "text-emerald-400" : "text-amber-300"}`}>
                {m.status}
              </span>
            </div>
          </button>
          <button
            type="button"
            onClick={() => void onDelete(m.id)}
            className="mt-1 text-xs text-rose-300 hover:text-rose-200"
          >
            Удалить
          </button>
        </li>
      ))}
    </ul>
  )
}

function MaterialPane({
  material,
  onChanged,
}: {
  material: Material
  onChanged: () => Promise<void>
}): JSX.Element {
  const [tab, setTab] = useState<"conspect" | "qa" | "cards" | "quiz" | "fib" | "essay">(
    "conspect",
  )

  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-950/40 p-5 space-y-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h3 className="text-lg font-semibold text-zinc-100">{sanitizeText(material.title)}</h3>
          <p className="text-xs text-zinc-500">
            {material.kind} · {fmtDate(material.created_at)} · чанков: {material.chunks_count || 0}
          </p>
        </div>
        <a
          href={safeHref(
            `${API_BASE}/api/study/material/${material.id}/export.html`,
          )}
          target="_blank"
          rel="noopener noreferrer"
          className="text-xs text-amber-300 underline hover:text-amber-200"
        >
          Экспорт в PDF (Print)
        </a>
      </div>

      <div className="flex flex-wrap gap-2 border-b border-zinc-800 -mb-px">
        {[
          { id: "conspect", label: "Конспект" },
          { id: "qa", label: "Q&A" },
          { id: "cards", label: "Флэшкарты" },
          { id: "quiz", label: "Smart-Quiz" },
          { id: "fib", label: "Пропуски" },
          { id: "essay", label: "Эссе" },
        ].map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => setTab(t.id as typeof tab)}
            className={`px-3 py-2 text-sm border-b-2 ${
              tab === t.id
                ? "border-amber-300 text-zinc-100"
                : "border-transparent text-zinc-400 hover:text-zinc-200"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "conspect" && <ConspectView materialId={material.id} onChanged={onChanged} />}
      {tab === "qa" && <QAView materialId={material.id} />}
      {tab === "cards" && <CardsView materialId={material.id} onChanged={onChanged} />}
      {tab === "quiz" && <QuizView materialId={material.id} onChanged={onChanged} />}
      {tab === "fib" && <FibView materialId={material.id} onChanged={onChanged} />}
      {tab === "essay" && <EssayView materialId={material.id} />}
    </div>
  )
}

function ConspectView({
  materialId,
  onChanged,
}: {
  materialId: string
  onChanged: () => Promise<void>
}): JSX.Element {
  const [data, setData] = useState<Conspect | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    setLoading(true)
    try {
      const c = await api<Conspect>(`/api/study/material/${materialId}/conspect`, {
        method: "POST",
      })
      setData(c)
      await onChanged()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }, [materialId, onChanged])

  useEffect(() => {
    void refresh()
  }, [refresh])

  if (loading) return <div className="text-sm text-zinc-400">Готовим конспект…</div>
  if (error) return <div className="text-sm text-rose-300">{sanitizeText(error)}</div>
  if (!data) return <div className="text-sm text-zinc-400">Конспект ещё не готов.</div>

  return (
    <div className="space-y-4 text-sm">
      <div>
        <h4 className="text-sm font-semibold text-zinc-200 mb-1">Короткий конспект</h4>
        <p className="whitespace-pre-line text-zinc-300">{sanitizeText(data.summary)}</p>
      </div>
      {data.key_moments?.length ? (
        <div>
          <h4 className="text-sm font-semibold text-zinc-200 mb-1">Ключевые моменты</h4>
          <ul className="list-disc pl-5 space-y-1 text-zinc-300">
            {data.key_moments.map((k, i) => (
              <li key={i}>{sanitizeText(k)}</li>
            ))}
          </ul>
        </div>
      ) : null}
      {data.tips?.length ? (
        <div>
          <h4 className="text-sm font-semibold text-zinc-200 mb-1">Идеи использования</h4>
          <ul className="list-disc pl-5 space-y-1 text-zinc-300">
            {data.tips.map((t, i) => (
              <li key={i}>{sanitizeText(t)}</li>
            ))}
          </ul>
        </div>
      ) : null}
      {data.glossary && Object.keys(data.glossary).length > 0 && (
        <div>
          <h4 className="text-sm font-semibold text-zinc-200 mb-1">Глоссарий</h4>
          <dl className="grid gap-2 text-zinc-300 sm:grid-cols-2">
            {Object.entries(data.glossary).map(([k, v]) => (
              <div key={k}>
                <dt className="font-medium">{sanitizeText(k)}</dt>
                <dd className="text-xs text-zinc-400">{sanitizeText(v)}</dd>
              </div>
            ))}
          </dl>
        </div>
      )}
      <button
        type="button"
        onClick={() => void refresh()}
        className="rounded-md border border-zinc-700 px-3 py-1.5 text-xs hover:border-amber-300"
      >
        Перегенерировать
      </button>
    </div>
  )
}

function QAView({ materialId }: { materialId: string }): JSX.Element {
  const [history, setHistory] = useState<QAAnswer[]>([])
  const [q, setQ] = useState("")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const ask = async (): Promise<void> => {
    if (!q.trim()) return
    setLoading(true)
    try {
      const ans = await api<QAAnswer>(`/api/study/material/${materialId}/qa`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: q }),
      })
      setHistory((h) => [ans, ...h])
      setQ("")
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-col gap-2 sm:flex-row">
        <input
          type="text"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Спросите что-то по материалу…"
          className="flex-1 rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100"
          onKeyDown={(e) => {
            if (e.key === "Enter" && !loading) void ask()
          }}
        />
        <button
          type="button"
          onClick={() => void ask()}
          disabled={loading || !q.trim()}
          className="rounded-md bg-amber-300 px-4 py-2 text-sm font-semibold text-zinc-900 disabled:opacity-40"
        >
          {loading ? "Думаем…" : "Спросить"}
        </button>
      </div>
      {error && <div className="text-sm text-rose-300">{sanitizeText(error)}</div>}
      <ul className="space-y-3">
        {history.map((h, i) => (
          <li key={i} className="rounded-md border border-zinc-800 bg-zinc-950/60 p-3 text-sm">
            <p className="font-medium text-zinc-100">— {sanitizeText(h.question)}</p>
            <p className="mt-2 whitespace-pre-line text-zinc-300">{sanitizeText(h.answer)}</p>
            {h.citations?.length ? (
              <div className="mt-2 text-xs text-zinc-500">
                Цитаты:{" "}
                {h.citations.map((c) => (
                  <span key={c.chunk_id} className="mr-2">
                    [chunk #{c.position}]
                  </span>
                ))}
              </div>
            ) : null}
          </li>
        ))}
      </ul>
    </div>
  )
}

function CardsView({
  materialId,
  onChanged,
}: {
  materialId: string
  onChanged: () => Promise<void>
}): JSX.Element {
  const [items, setItems] = useState<Flashcard[]>([])
  const [loading, setLoading] = useState(false)

  const gen = async (count = 8): Promise<void> => {
    setLoading(true)
    try {
      const out = await api<{ items: Flashcard[] }>(
        `/api/study/material/${materialId}/flashcards`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ count }),
        },
      )
      setItems(out.items)
      await onChanged()
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-3">
      <button
        type="button"
        onClick={() => void gen(8)}
        disabled={loading}
        className="rounded-md bg-amber-300 px-3 py-1.5 text-sm font-semibold text-zinc-900 disabled:opacity-40"
      >
        {loading ? "Готовим колоду…" : "Сгенерировать 8 карточек"}
      </button>
      <ul className="grid gap-3 sm:grid-cols-2">
        {items.map((c) => (
          <li key={c.id} className="rounded-md border border-zinc-800 bg-zinc-950/60 p-3 text-sm">
            <details>
              <summary className="cursor-pointer font-medium text-zinc-100">
                {sanitizeText(c.front)}
              </summary>
              <p className="mt-2 text-zinc-300">{sanitizeText(c.back)}</p>
              {c.hint && <p className="mt-1 text-xs text-zinc-500">{sanitizeText(c.hint)}</p>}
            </details>
          </li>
        ))}
      </ul>
    </div>
  )
}

function QuizView({
  materialId,
  onChanged,
}: {
  materialId: string
  onChanged: () => Promise<void>
}): JSX.Element {
  const [items, setItems] = useState<QuizItem[]>([])
  const [picks, setPicks] = useState<Record<string, number>>({})
  const [loading, setLoading] = useState(false)

  const gen = async (count = 6): Promise<void> => {
    setLoading(true)
    try {
      const out = await api<{ items: QuizItem[] }>(`/api/study/material/${materialId}/quiz`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ count }),
      })
      setItems(out.items)
      setPicks({})
      await onChanged()
    } finally {
      setLoading(false)
    }
  }

  const explanationFor = (q: QuizItem, idx: number): string => {
    if (idx === q.correct_index) return q.explanation
    let wi = 0
    for (let i = 0; i < q.options.length; i++) {
      if (i === q.correct_index) continue
      if (i === idx) return q.explanation_wrong[wi] || q.explanation
      wi++
    }
    return q.explanation
  }

  return (
    <div className="space-y-3">
      <button
        type="button"
        onClick={() => void gen(6)}
        disabled={loading}
        className="rounded-md bg-amber-300 px-3 py-1.5 text-sm font-semibold text-zinc-900 disabled:opacity-40"
      >
        {loading ? "Готовим вопросы…" : "Сгенерировать Smart-Quiz"}
      </button>
      <ol className="space-y-4">
        {items.map((q, qi) => (
          <li key={q.id} className="rounded-md border border-zinc-800 bg-zinc-950/60 p-3 text-sm">
            <p className="font-medium text-zinc-100">
              {qi + 1}. {sanitizeText(q.question)}
            </p>
            <div className="mt-2 grid gap-2 sm:grid-cols-2">
              {q.options.map((opt, oi) => {
                const picked = picks[q.id]
                const isPicked = picked === oi
                const isCorrect = oi === q.correct_index
                const cls = isPicked
                  ? isCorrect
                    ? "border-emerald-500 bg-emerald-500/10 text-emerald-100"
                    : "border-rose-500 bg-rose-500/10 text-rose-100"
                  : "border-zinc-700 hover:border-zinc-500"
                return (
                  <button
                    key={oi}
                    type="button"
                    onClick={() => setPicks({ ...picks, [q.id]: oi })}
                    className={`rounded-md border px-3 py-2 text-left ${cls}`}
                  >
                    {sanitizeText(opt)}
                  </button>
                )
              })}
            </div>
            {picks[q.id] != null && (
              <p className="mt-2 text-xs text-zinc-400">
                {sanitizeText(explanationFor(q, picks[q.id]))}
              </p>
            )}
          </li>
        ))}
      </ol>
    </div>
  )
}

function FibView({
  materialId,
  onChanged,
}: {
  materialId: string
  onChanged: () => Promise<void>
}): JSX.Element {
  const [items, setItems] = useState<FibItem[]>([])
  const [answers, setAnswers] = useState<Record<string, string>>({})
  const [loading, setLoading] = useState(false)

  const gen = async (count = 5): Promise<void> => {
    setLoading(true)
    try {
      const out = await api<{ items: FibItem[] }>(`/api/study/material/${materialId}/fib`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ count }),
      })
      setItems(out.items)
      setAnswers({})
      await onChanged()
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-3">
      <button
        type="button"
        onClick={() => void gen(5)}
        disabled={loading}
        className="rounded-md bg-amber-300 px-3 py-1.5 text-sm font-semibold text-zinc-900 disabled:opacity-40"
      >
        {loading ? "Готовим пропуски…" : "Сгенерировать пропуски"}
      </button>
      <ol className="space-y-3 text-sm">
        {items.map((f, i) => {
          const myAnswer = (answers[f.id] || "").trim().toLowerCase()
          const ok = myAnswer && myAnswer === f.answer.toLowerCase()
          return (
            <li
              key={f.id}
              className="rounded-md border border-zinc-800 bg-zinc-950/60 p-3"
            >
              <p className="text-zinc-100">
                {i + 1}. {sanitizeText(f.sentence_with_blank)}
              </p>
              <input
                type="text"
                value={answers[f.id] || ""}
                onChange={(e) => setAnswers({ ...answers, [f.id]: e.target.value })}
                placeholder={f.hint || "Введите слово"}
                className="mt-2 w-full rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2"
              />
              {answers[f.id] && (
                <p className={`mt-1 text-xs ${ok ? "text-emerald-400" : "text-rose-300"}`}>
                  {ok ? "Верно!" : `Правильный ответ: ${sanitizeText(f.answer)}`}
                </p>
              )}
            </li>
          )
        })}
      </ol>
    </div>
  )
}

function EssayView({ materialId }: { materialId: string }): JSX.Element {
  const [prompt, setPrompt] = useState("")
  const [essay, setEssay] = useState("")
  const [result, setResult] = useState<{
    total: number
    per_criterion: Record<string, number>
    feedback: string[]
    strengths: string[]
    weaknesses: string[]
  } | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const grade = async (): Promise<void> => {
    setLoading(true)
    try {
      const r = await api<{
        result: typeof result
      }>(`/api/study/material/${materialId}/essay/grade`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt, essay }),
      })
      setResult(r.result)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-3 text-sm">
      <input
        type="text"
        value={prompt}
        onChange={(e) => setPrompt(e.target.value)}
        placeholder="Тема эссе"
        className="w-full rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2 text-zinc-100"
      />
      <textarea
        value={essay}
        onChange={(e) => setEssay(e.target.value)}
        placeholder="Текст вашего эссе…"
        rows={8}
        className="w-full rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2 text-zinc-100"
      />
      <button
        type="button"
        onClick={() => void grade()}
        disabled={loading || essay.length < 20}
        className="rounded-md bg-amber-300 px-3 py-1.5 text-sm font-semibold text-zinc-900 disabled:opacity-40"
      >
        {loading ? "Проверяем…" : "Получить оценку"}
      </button>
      {error && <div className="text-sm text-rose-300">{sanitizeText(error)}</div>}
      {result && (
        <div className="rounded-md border border-zinc-800 bg-zinc-950/60 p-3 text-zinc-200">
          <p className="text-lg font-semibold">
            Итог: {result.total} / 25
          </p>
          <ul className="mt-2 grid gap-1 text-xs text-zinc-400 sm:grid-cols-2">
            {Object.entries(result.per_criterion).map(([k, v]) => (
              <li key={k}>
                {sanitizeText(k)}: {v}/5
              </li>
            ))}
          </ul>
          {result.feedback?.length ? (
            <ul className="mt-2 list-disc pl-5 text-xs text-zinc-400">
              {result.feedback.map((f, i) => (
                <li key={i}>{sanitizeText(f)}</li>
              ))}
            </ul>
          ) : null}
        </div>
      )}
    </div>
  )
}

function MasteryRow({ mastery }: { mastery: Mastery | null }): JSX.Element {
  const total = useMemo(() => {
    if (!mastery) return 0
    return (
      mastery.buckets.unfamiliar +
      mastery.buckets.learning +
      mastery.buckets.familiar +
      mastery.buckets.mastered
    )
  }, [mastery])
  if (!mastery) return <></>
  const order: { id: keyof Mastery["buckets"]; label: string; color: string }[] = [
    { id: "unfamiliar", label: "Не знакомо", color: "bg-zinc-700" },
    { id: "learning", label: "Учится", color: "bg-amber-500/70" },
    { id: "familiar", label: "Знакомо", color: "bg-sky-500/70" },
    { id: "mastered", label: "Освоено", color: "bg-emerald-500/70" },
  ]
  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-950/40 p-5">
      <h3 className="text-sm font-semibold text-zinc-200 mb-3">Мой прогресс</h3>
      <div className="grid gap-3 sm:grid-cols-4">
        {order.map((b) => (
          <div key={b.id} className="rounded-md border border-zinc-800 bg-zinc-900 px-3 py-3">
            <div className="text-xs text-zinc-500">{b.label}</div>
            <div className="mt-1 flex items-baseline gap-2">
              <div className="text-2xl font-semibold text-zinc-100">
                {mastery.buckets[b.id]}
              </div>
              <div className="text-xs text-zinc-500">
                / {total || 0}
              </div>
            </div>
            <div className={`mt-2 h-1 rounded ${b.color}`} />
          </div>
        ))}
      </div>
      <p className="mt-3 text-xs text-zinc-500">
        Материалы: {mastery.total_materials}. Карт в SRS: {mastery.total_cards}.
      </p>
    </div>
  )
}

function Pricing({ tariffs }: { tariffs: Tariffs | null }): JSX.Element {
  const [email, setEmail] = useState("")
  const [done, setDone] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [picked, setPicked] = useState<string>("month")

  if (!tariffs) return <></>

  const join = async (): Promise<void> => {
    try {
      await api("/api/study/waitlist", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, source: `pricing:${picked}` }),
      })
      await api("/api/study/subscription", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tariff: picked }),
      })
      setDone(true)
    } catch (e) {
      setError((e as Error).message)
    }
  }

  const TARIFF_LABEL: Record<string, { title: string; price: string; note: string }> = {
    free: { title: "Free", price: "0 ₽", note: "3 материала, 10 Q&A/день" },
    week: { title: "Неделя", price: "149 ₽", note: "30 материалов, 200 Q&A/день" },
    month: { title: "Месяц", price: "390 ₽", note: "200 материалов, подкасты" },
    year: { title: "Год", price: "2 990 ₽", note: "5 000 материалов, всё включено" },
  }

  return (
    <section id="pricing" className="rounded-lg border border-zinc-800 bg-zinc-950/40 p-5">
      <h3 className="text-sm font-semibold text-zinc-200 mb-3">Тарифы</h3>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {Object.entries(tariffs.tariffs).map(([key, limits]) => {
          const meta = TARIFF_LABEL[key] || { title: key, price: "—", note: "" }
          const selected = picked === key
          return (
            <button
              type="button"
              key={key}
              onClick={() => setPicked(key)}
              className={`text-left rounded-md border p-3 transition-colors ${
                selected
                  ? "border-amber-300 bg-amber-300/5"
                  : "border-zinc-800 bg-zinc-900 hover:border-zinc-600"
              }`}
            >
              <div className="text-base font-semibold text-zinc-100">{meta.title}</div>
              <div className="text-xs text-zinc-400">{meta.note}</div>
              <div className="mt-1 text-lg font-semibold text-amber-200">{meta.price}</div>
              <ul className="mt-2 text-xs text-zinc-500 space-y-0.5">
                <li>{limits.materials_per_month} материалов / мес</li>
                <li>{limits.qa_per_day} Q&A / день</li>
                <li>{limits.audio_minutes_per_month} мин аудио</li>
                <li>
                  {limits.podcast ? "Подкасты включены" : "Без подкастов"}
                </li>
                <li>Хранение: {limits.retention_days} дней</li>
              </ul>
            </button>
          )
        })}
      </div>

      {!done ? (
        <div className="mt-4 flex flex-col gap-2 sm:flex-row sm:items-center">
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="email для запуска платежей"
            className="flex-1 rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100"
          />
          <button
            type="button"
            onClick={() => void join()}
            disabled={!email}
            className="rounded-md bg-amber-300 px-4 py-2 text-sm font-semibold text-zinc-900 disabled:opacity-40"
          >
            Записаться в waitlist
          </button>
        </div>
      ) : (
        <p className="mt-3 text-sm text-emerald-300">
          Спасибо! Сообщим, как только запустим оплату через YooKassa / СБП.
        </p>
      )}
      {error && <p className="mt-2 text-sm text-rose-300">{sanitizeText(error)}</p>}
      <p className="mt-3 text-xs text-zinc-500">
        Оплата ещё не запущена — мы добавим её отдельным PR (YooKassa / СБП). Сейчас можно
        попробовать любой тариф и записаться в очередь.
      </p>
    </section>
  )
}
