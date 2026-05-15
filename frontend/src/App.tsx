import { lazy, Suspense, useEffect, useMemo, useState } from "react"
import StudyTab from "./StudyTab"
import {
  BookOpen,
  GraduationCap,
  BarChart3,
  Sparkles,
  Library,
  Send,
  CheckCircle2,
  XCircle,
  ExternalLink,
  Compass,
  ShieldCheck,
  Search,
  Network,
  Ticket,
  Download,
  Calendar,
  Gamepad2,
} from "lucide-react"
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"

import { safeHref, sanitizeText } from "./lib/sanitize"

const API_BASE = (import.meta.env.VITE_API_BASE as string) || "http://localhost:8000"

type Tab =
  | "curator"
  | "study"
  | "search"
  | "mindmap"
  | "trainer"
  | "pushkin"
  | "dashboard"
  | "games"
  | "about"

type SearchSource = {
  id: string
  author: string
  title: string
  year: number
  genre: string
  school_grade: number | null
  ege_topics: string[]
  pushkin_card: boolean
  summary: string
  fragment: string
  citation: string
  public_domain_url: string
}

type SearchResponse = {
  query: string
  engine: "hybrid" | "keyword"
  count: number
  items: SearchSource[]
}

type MindmapNode = {
  id: string
  label: string
  kind: "query" | "author" | "book" | "theme"
  weight: number
  metadata?: Record<string, unknown>
}

type MindmapEdge = {
  source: string
  target: string
  label: string
  weight: number
}

type MindmapCitation = {
  source_id: string
  author: string
  title: string
  fragment: string
  citation: string
  url: string
}

type MindmapResponse = {
  query: string
  nodes: MindmapNode[]
  edges: MindmapEdge[]
  citations: MindmapCitation[]
}

type PushkinEvent = {
  id: string
  title: string
  venue: string
  city: string
  region: string
  date: string
  price_rub: number
  age_range: string
  themes: string[]
  book_ids: string[]
  booking_url: string
}

type PushkinResponse = {
  count: number
  items: PushkinEvent[]
}

type RouteWeek = {
  week: number
  title: string
  description: string
  book: string
  book_id: string
  fragment: string
  citation: string
  public_domain_url: string
  actions: string[]
  pushkin_card_event: string | null
}

type RouteResponse = {
  query: string
  summary: string
  weeks: RouteWeek[]
  sources: { id: string; author: string; title: string; year: number }[]
  disclaimer: string
}

type QuizItem = {
  id: string
  topic: string
  subject: string
  question: string
  options: string[]
  source_id: string
}

type AnswerResult = {
  question_id: string
  correct: boolean
  correct_index: number
  explanation: string
}

type RegionalDash = {
  region: string
  period: string
  snapshot: Record<string, number>
  engagement: Record<string, number>
  education_metrics: { subject: string; ege_score_change_pp: number; schools: number }[]
  library_metrics: Record<string, number>
  top_themes: { theme: string; demand_index: number }[]
  rag_quality: Record<string, number>
  compliance: Record<string, string | boolean>
  disclaimer?: string
}

type KpiItem = {
  metric: string
  value: string
  target: string
  comment: string
}

const EXAMPLE_QUERIES = [
  "Хочу понять Пушкина за 4 недели",
  "Маршрут по Серебряному веку для 11 класса",
  "Подготовка к ЕГЭ по Достоевскому",
  "История России XIX века для подростка",
  "Толстой и Чехов: эпопея и драма",
  "Лермонтов и тип лишнего человека",
]

function Logo() {
  return (
    <div className="flex items-center gap-3">
      <div className="h-11 w-11 rounded-lg bg-gradient-to-br from-amber-300 to-sky-300 flex items-center justify-center text-zinc-900 font-bold tracking-wide">
        ЧИ
      </div>
      <div>
        <div className="text-lg font-semibold leading-tight">ЧитАИ</div>
        <div className="text-xs text-zinc-400 leading-tight">
          ИИ-куратор русского культурного и образовательного контента
        </div>
      </div>
    </div>
  )
}

function Header({ tab, setTab }: { tab: Tab; setTab: (t: Tab) => void }) {
  const tabs: { id: Tab; label: string; icon: React.ReactNode }[] = [
    { id: "curator", label: "Куратор", icon: <Compass size={16} aria-hidden /> },
    { id: "study", label: "Учёба", icon: <BookOpen size={16} aria-hidden /> },
    { id: "search", label: "Поиск по фондам", icon: <Search size={16} aria-hidden /> },
    { id: "mindmap", label: "Ментальная карта", icon: <Network size={16} aria-hidden /> },
    { id: "trainer", label: "Тренажёр ЕГЭ", icon: <GraduationCap size={16} aria-hidden /> },
    { id: "pushkin", label: "Пушкинская карта", icon: <Ticket size={16} aria-hidden /> },
    { id: "dashboard", label: "Дашборд региона", icon: <BarChart3 size={16} aria-hidden /> },
    { id: "games", label: "Игра", icon: <Gamepad2 size={16} aria-hidden /> },
    { id: "about", label: "О проекте", icon: <Sparkles size={16} aria-hidden /> },
  ]
  return (
    <header className="border-b border-zinc-800">
      <div className="mx-auto max-w-6xl px-6 pt-7 pb-1">
        <Logo />
        <nav
          role="tablist"
          aria-label="Разделы ЧитАИ"
          className="mt-5 flex flex-wrap gap-1 border-b border-zinc-800"
        >
          {tabs.map((t) => {
            const selected = tab === t.id
            return (
              <button
                key={t.id}
                role="tab"
                type="button"
                id={`tab-${t.id}`}
                aria-selected={selected}
                aria-controls={`panel-${t.id}`}
                tabIndex={selected ? 0 : -1}
                onClick={() => setTab(t.id)}
                className={`flex items-center gap-2 px-4 py-3 text-sm border-b-2 -mb-px transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-300 focus-visible:rounded-sm ${
                  selected
                    ? "border-amber-300 text-zinc-100"
                    : "border-transparent text-zinc-400 hover:text-zinc-200"
                }`}
              >
                {t.icon}
                {t.label}
              </button>
            )
          })}
        </nav>
      </div>
    </header>
  )
}

function Pill({
  children,
  tone = "default",
}: {
  children: React.ReactNode
  tone?: "default" | "good" | "accent"
}) {
  const cls =
    tone === "good"
      ? "border-emerald-900 text-emerald-300 bg-emerald-950/40"
      : tone === "accent"
        ? "border-amber-900 text-amber-300 bg-amber-950/30"
        : "border-zinc-700 text-zinc-300 bg-zinc-900"
  return (
    <span className={`inline-block rounded-full border px-3 py-1 text-xs ${cls}`}>{children}</span>
  )
}

function Card({
  children,
  className = "",
}: {
  children: React.ReactNode
  className?: string
}) {
  return (
    <div className={`rounded-xl border border-zinc-800 bg-zinc-900/60 p-5 ${className}`}>{children}</div>
  )
}

function CuratorTab() {
  const [query, setQuery] = useState(EXAMPLE_QUERIES[0])
  const [route, setRoute] = useState<RouteResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [exporting, setExporting] = useState<"markdown" | "ics" | null>(null)
  const [ttsLoading, setTtsLoading] = useState<number | null>(null)
  const [audioUrl, setAudioUrl] = useState<string | null>(null)
  const [exportError, setExportError] = useState<string | null>(null)

  async function buildRoute(q: string = query) {
    if (!q || q.trim().length < 2) return
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`${API_BASE}/api/curator/route`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: q, weeks: 4 }),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data: RouteResponse = await res.json()
      setRoute(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Сервис недоступен")
    } finally {
      setLoading(false)
    }
  }

  async function exportRoute(kind: "markdown" | "ics") {
    if (!query || query.trim().length < 2) return
    setExporting(kind)
    setExportError(null)
    try {
      const res = await fetch(`${API_BASE}/api/curator/export/${kind}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, weeks: 4 }),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement("a")
      a.href = url
      a.download = kind === "markdown" ? "chitai-route.md" : "chitai-route.ics"
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)
    } catch (err) {
      setExportError(err instanceof Error ? err.message : "Сервис недоступен")
    } finally {
      setExporting(null)
    }
  }

  async function speak(text: string, weekIdx: number) {
    setTtsLoading(weekIdx)
    setAudioUrl(null)
    try {
      const res = await fetch(`${API_BASE}/api/tts/synth`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, voice: "ermil", emotion: "neutral" }),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      setAudioUrl(url)
      const audio = new Audio(url)
      void audio.play()
    } catch (err) {
      setExportError(
        err instanceof Error ? `TTS: ${err.message}` : "TTS: сервис недоступен"
      )
    } finally {
      setTtsLoading(null)
    }
  }

  useEffect(() => {
    buildRoute(EXAMPLE_QUERIES[0])
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <section className="py-7">
      <h2 className="text-2xl font-semibold mb-2">Маршрут чтения по фондам</h2>
      <p className="text-sm text-zinc-400 max-w-3xl">
        Запрос свободной формой. Демо подбирает 4-недельный маршрут по корпусу public domain. В
        продакшене источники — фонды РГБ и НЭБ; генерация — YandexGPT 5 Pro / GigaChat MAX поверх
        pgvector.
      </p>

      <Card className="mt-5">
        <textarea
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          rows={3}
          placeholder="Например: Хочу понять Пушкина за 4 недели"
          className="w-full resize-y rounded-lg border border-zinc-800 bg-zinc-950 px-4 py-3 text-sm outline-none focus:border-sky-300"
        />
        <div className="mt-3 flex flex-wrap gap-2">
          <button
            onClick={() => buildRoute()}
            disabled={loading}
            className="inline-flex items-center gap-2 rounded-lg bg-amber-300 px-5 py-2 text-sm font-semibold text-zinc-900 hover:brightness-110 disabled:opacity-60"
          >
            <Send size={16} />
            {loading ? "Собираю маршрут…" : "Собрать маршрут"}
          </button>
          {EXAMPLE_QUERIES.map((q) => (
            <button
              key={q}
              onClick={() => {
                setQuery(q)
                buildRoute(q)
              }}
              className="rounded-lg border border-zinc-800 bg-zinc-950 px-3 py-2 text-xs text-zinc-300 hover:border-sky-300"
            >
              {q}
            </button>
          ))}
        </div>
        {error && (
          <p className="mt-3 text-sm text-red-400">
            Не удалось обратиться к API ({error}). Backend: {API_BASE}
          </p>
        )}
      </Card>

      {route && (
        <Card className="mt-6">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h3 className="text-lg font-semibold">Маршрут на 4 недели</h3>
              <p className="mt-1 text-sm text-zinc-400">{route.summary}</p>
            </div>
            <div className="flex flex-wrap gap-2" aria-label="Экспорт маршрута">
              <button
                onClick={() => exportRoute("markdown")}
                disabled={exporting !== null}
                className="inline-flex items-center gap-2 rounded-lg border border-zinc-800 bg-zinc-950 px-3 py-2 text-xs text-zinc-200 hover:border-amber-300 disabled:opacity-60 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-300"
                aria-label="Скачать маршрут в формате Markdown"
              >
                <Download size={14} aria-hidden />
                {exporting === "markdown" ? "Готовлю…" : "Скачать .md"}
              </button>
              <button
                onClick={() => exportRoute("ics")}
                disabled={exporting !== null}
                className="inline-flex items-center gap-2 rounded-lg border border-zinc-800 bg-zinc-950 px-3 py-2 text-xs text-zinc-200 hover:border-amber-300 disabled:opacity-60 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-300"
                aria-label="Скачать маршрут как календарь .ics"
              >
                <Calendar size={14} aria-hidden />
                {exporting === "ics" ? "Готовлю…" : "Календарь .ics"}
              </button>
            </div>
          </div>
          {exportError && (
            <p className="mt-2 text-xs text-red-400" role="alert">
              {exportError}
            </p>
          )}
          {audioUrl && (
            <audio
              src={audioUrl}
              controls
              aria-label="Аудио-озвучка фрагмента"
              className="mt-3 w-full"
            />
          )}
          <div className="mt-5 space-y-5">
            {route.weeks.map((w, idx) => (
              <div key={w.week} className="border-l-2 border-amber-300 pl-4">
                <div className="text-base font-semibold">{w.title}</div>
                <div className="mt-1 text-sm">{w.description}</div>
                <div className="mt-2 flex items-start gap-2">
                  <div className="border-l-2 border-sky-300 pl-3 text-sm italic text-zinc-200 flex-1">
                    {w.fragment}
                  </div>
                  <button
                    onClick={() => speak(w.fragment, idx)}
                    disabled={ttsLoading !== null}
                    className="shrink-0 inline-flex items-center gap-1 rounded-lg border border-zinc-800 bg-zinc-950 px-2 py-1 text-xs text-zinc-300 hover:border-amber-300 disabled:opacity-60 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-300"
                    aria-label="Озвучить фрагмент"
                  >
                    {ttsLoading === idx ? "…" : "🔊 Озвучить"}
                  </button>
                </div>
                <div className="mt-2 text-xs text-zinc-400">
                  Источник: {w.citation}
                  <br />
                  Текст:{" "}
                  <a
                    href={safeHref(w.public_domain_url)}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-amber-300 hover:underline inline-flex items-center gap-1"
                  >
                    {w.public_domain_url}
                    <ExternalLink size={12} />
                  </a>
                </div>
                <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-zinc-300">
                  {w.actions.map((a, i) => (
                    <li key={i}>{a}</li>
                  ))}
                </ul>
                {w.pushkin_card_event && (
                  <div className="mt-2 inline-flex items-center gap-2 text-xs">
                    <Pill tone="accent">Пушкинская карта</Pill>
                    <span className="text-zinc-300">{w.pushkin_card_event}</span>
                  </div>
                )}
              </div>
            ))}
          </div>
          <p className="mt-5 text-xs text-zinc-500">{route.disclaimer}</p>
        </Card>
      )}
    </section>
  )
}

function SearchTab() {
  const [query, setQuery] = useState("Пушкин и тема чести")
  const [hybrid, setHybrid] = useState(true)
  const [data, setData] = useState<SearchResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function runSearch(q: string = query, useHybrid: boolean = hybrid) {
    if (!q || q.trim().length < 2) return
    setLoading(true)
    setError(null)
    try {
      const url = `${API_BASE}/api/corpus/search?q=${encodeURIComponent(q)}&limit=8&hybrid=${useHybrid}`
      const res = await fetch(url)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const body: SearchResponse = await res.json()
      setData(body)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Сервис недоступен")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    runSearch("Пушкин и тема чести", true)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <section className="py-7">
      <h2 className="text-2xl font-semibold mb-2">Поиск по фондам (гибридный)</h2>
      <p className="text-sm text-zinc-400 max-w-3xl">
        Гибридный поиск: BM25 (морфология русского языка) + плотные эмбеддинги поверх корпуса
        public domain. В проде — pgvector с фондами РГБ и НЭБ. Переключатель ниже сравнивает
        гибридный поиск с чистым keyword-режимом.
      </p>

      <Card className="mt-5">
        <div className="flex flex-col gap-3 md:flex-row md:items-center">
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && runSearch()}
            placeholder="Что ищем?"
            aria-label="Поисковый запрос"
            className="flex-1 rounded-lg border border-zinc-800 bg-zinc-950 px-4 py-3 text-sm outline-none focus:border-sky-300"
          />
          <label className="flex items-center gap-2 text-xs text-zinc-300">
            <input
              type="checkbox"
              checked={hybrid}
              onChange={(e) => setHybrid(e.target.checked)}
              className="h-4 w-4"
            />
            Гибридный режим (BM25 + dense)
          </label>
          <button
            onClick={() => runSearch()}
            disabled={loading}
            className="inline-flex items-center justify-center gap-2 rounded-lg bg-amber-300 px-5 py-2 text-sm font-semibold text-zinc-900 hover:brightness-110 disabled:opacity-60 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-300"
          >
            <Search size={16} aria-hidden />
            {loading ? "Ищу…" : "Искать"}
          </button>
        </div>
        {error && (
          <p className="mt-3 text-sm text-red-400" role="alert">
            Не удалось обратиться к API ({error}). Backend: {API_BASE}
          </p>
        )}
      </Card>

      {data && (
        <Card className="mt-6">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h3 className="text-lg font-semibold">
              Найдено: {data.count}{" "}
              <span className="text-xs font-normal text-zinc-400">
                режим: {data.engine === "hybrid" ? "гибридный" : "ключевые слова"}
              </span>
            </h3>
            <Pill tone={data.engine === "hybrid" ? "accent" : "default"}>{data.engine}</Pill>
          </div>
          <ol className="mt-4 space-y-4">
            {data.items.map((item, i) => (
              <li
                key={item.id}
                className="rounded-lg border border-zinc-800 bg-zinc-950/60 p-4"
              >
                <div className="flex flex-wrap items-baseline gap-2">
                  <span className="text-xs text-zinc-500">#{i + 1}</span>
                  <span className="text-base font-semibold">{item.title}</span>
                  <span className="text-xs text-zinc-400">— {item.author}, {item.year}</span>
                  {item.pushkin_card && <Pill tone="accent">Пушкинская карта</Pill>}
                </div>
                <p className="mt-2 text-sm text-zinc-300">{item.summary}</p>
                <p className="mt-2 border-l-2 border-sky-300 pl-3 text-sm italic text-zinc-200">
                  {item.fragment}
                </p>
                <div className="mt-2 flex flex-wrap gap-2">
                  {item.ege_topics.map((t) => (
                    <Pill key={t}>{t}</Pill>
                  ))}
                </div>
                <div className="mt-2 text-xs text-zinc-400">
                  <a
                    href={safeHref(item.public_domain_url)}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-amber-300 hover:underline inline-flex items-center gap-1"
                  >
                    {item.public_domain_url}
                    <ExternalLink size={12} aria-hidden />
                  </a>
                </div>
              </li>
            ))}
          </ol>
        </Card>
      )}
    </section>
  )
}

function MindmapTab() {
  const [query, setQuery] = useState("Пушкин")
  const [data, setData] = useState<MindmapResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function buildMap(q: string = query) {
    if (!q || q.trim().length < 2) return
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`${API_BASE}/api/curator/mindmap`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: q, limit: 6 }),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const body: MindmapResponse = await res.json()
      setData(body)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Сервис недоступен")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    buildMap("Пушкин")
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const grouped = useMemo(() => {
    const out: Record<MindmapNode["kind"], MindmapNode[]> = {
      query: [],
      author: [],
      book: [],
      theme: [],
    }
    if (!data) return out
    for (const n of data.nodes) {
      if (out[n.kind]) out[n.kind].push(n)
    }
    return out
  }, [data])

  return (
    <section className="py-7">
      <h2 className="text-2xl font-semibold mb-2">Ментальная карта корпуса</h2>
      <p className="text-sm text-zinc-400 max-w-3xl">
        Семантический граф: автор → книги → темы ЕГЭ. Узлы и связи строятся на основе
        public-domain корпуса; цитаты приводятся внизу. В проде — связи через pgvector + KG.
      </p>

      <Card className="mt-5">
        <div className="flex flex-col gap-3 md:flex-row">
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && buildMap()}
            placeholder="Автор, книга или тема"
            aria-label="Запрос для ментальной карты"
            className="flex-1 rounded-lg border border-zinc-800 bg-zinc-950 px-4 py-3 text-sm outline-none focus:border-sky-300"
          />
          <button
            onClick={() => buildMap()}
            disabled={loading}
            className="inline-flex items-center justify-center gap-2 rounded-lg bg-amber-300 px-5 py-2 text-sm font-semibold text-zinc-900 hover:brightness-110 disabled:opacity-60 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-300"
          >
            <Network size={16} aria-hidden />
            {loading ? "Строю…" : "Построить карту"}
          </button>
        </div>
        {error && (
          <p className="mt-3 text-sm text-red-400" role="alert">
            Не удалось обратиться к API ({error}). Backend: {API_BASE}
          </p>
        )}
      </Card>

      {data && (
        <>
          <Card className="mt-6">
            <h3 className="text-lg font-semibold">Узлы карты ({data.nodes.length})</h3>
            <div className="mt-4 grid gap-4 md:grid-cols-3">
              {(["author", "book", "theme"] as const).map((kind) => (
                <div key={kind} aria-label={`категория ${kind}`}>
                  <div className="mb-2 text-xs font-semibold uppercase text-zinc-400">
                    {kind === "author"
                      ? "Авторы"
                      : kind === "book"
                        ? "Книги"
                        : "Темы ЕГЭ"}
                  </div>
                  <ul className="space-y-2">
                    {grouped[kind].map((n) => (
                      <li
                        key={n.id}
                        className="rounded-lg border border-zinc-800 bg-zinc-950/60 px-3 py-2 text-sm"
                      >
                        {n.label}
                      </li>
                    ))}
                    {grouped[kind].length === 0 && (
                      <li className="text-xs text-zinc-500">— пусто —</li>
                    )}
                  </ul>
                </div>
              ))}
            </div>
          </Card>

          <Card className="mt-4">
            <h3 className="text-lg font-semibold">Связи ({data.edges.length})</h3>
            <ul className="mt-3 space-y-1 text-sm text-zinc-300">
              {data.edges.slice(0, 12).map((e, i) => (
                <li key={i} className="font-mono text-xs">
                  {e.source.split("::").pop()}
                  <span className="mx-2 text-zinc-500">→[{e.label}]→</span>
                  {e.target.split("::").pop()}
                </li>
              ))}
            </ul>
          </Card>

          <Card className="mt-4">
            <h3 className="text-lg font-semibold">
              Цитаты public domain ({data.citations.length})
            </h3>
            <ul className="mt-3 space-y-3">
              {data.citations.map((c) => (
                <li key={c.source_id} className="border-l-2 border-amber-300 pl-3 text-sm">
                  <div className="font-semibold">
                    {c.author} — {c.title}
                  </div>
                  <div className="mt-1 italic text-zinc-200">{c.fragment}</div>
                  <div className="mt-1 text-xs text-zinc-400">{c.citation}</div>
                  <a
                    href={c.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs text-amber-300 hover:underline inline-flex items-center gap-1"
                  >
                    {c.url}
                    <ExternalLink size={12} aria-hidden />
                  </a>
                </li>
              ))}
            </ul>
          </Card>
        </>
      )}
    </section>
  )
}

function PushkinTab() {
  const [region, setRegion] = useState<string>("")
  const [data, setData] = useState<PushkinResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function loadEvents(reg: string = region) {
    setLoading(true)
    setError(null)
    try {
      const url = reg
        ? `${API_BASE}/api/pushkin/events?region=${encodeURIComponent(reg)}`
        : `${API_BASE}/api/pushkin/events`
      const res = await fetch(url)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const body: PushkinResponse = await res.json()
      setData(body)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Сервис недоступен")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadEvents("")
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const regions = useMemo(() => {
    if (!data) return []
    const set = new Set<string>()
    for (const e of data.items) set.add(e.region)
    return Array.from(set).sort()
  }, [data])

  return (
    <section className="py-7">
      <h2 className="text-2xl font-semibold mb-2">Пушкинская карта — события</h2>
      <p className="text-sm text-zinc-400 max-w-3xl">
        Демо-каталог культурных событий 14–22 лет, совместимых с программой «Пушкинская карта».
        В проде — синхронизация с реестром «Культура.РФ» и API Минкульта.
      </p>

      <Card className="mt-5">
        <div className="flex flex-col gap-3 md:flex-row md:items-center">
          <label className="text-xs text-zinc-300">
            Регион:
            <select
              value={region}
              onChange={(e) => {
                setRegion(e.target.value)
                loadEvents(e.target.value)
              }}
              aria-label="Фильтр по региону"
              className="ml-2 rounded-md border border-zinc-800 bg-zinc-950 px-3 py-2 text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-300"
            >
              <option value="">Все регионы</option>
              {regions.map((r) => (
                <option key={r} value={r}>
                  {r}
                </option>
              ))}
            </select>
          </label>
          <button
            onClick={() => loadEvents()}
            disabled={loading}
            className="inline-flex items-center gap-2 rounded-lg border border-zinc-800 px-3 py-2 text-xs text-zinc-300 hover:border-sky-300 disabled:opacity-60 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-300"
          >
            {loading ? "Обновляю…" : "Обновить"}
          </button>
        </div>
        {error && (
          <p className="mt-3 text-sm text-red-400" role="alert">
            Не удалось обратиться к API ({error}). Backend: {API_BASE}
          </p>
        )}
      </Card>

      {data && (
        <Card className="mt-6">
          <h3 className="text-lg font-semibold">События ({data.count})</h3>
          <ul className="mt-4 space-y-3">
            {data.items.map((e) => (
              <li
                key={e.id}
                className="rounded-lg border border-zinc-800 bg-zinc-950/60 p-4"
              >
                <div className="flex flex-wrap items-baseline gap-2">
                  <span className="text-base font-semibold">{e.title}</span>
                  <Pill tone="accent">Пушкинская карта</Pill>
                  <span className="text-xs text-zinc-400">{e.age_range}</span>
                </div>
                <div className="mt-1 text-sm text-zinc-300">
                  {e.venue} · {e.city} · {e.region}
                </div>
                <div className="mt-2 flex flex-wrap items-center gap-3 text-xs text-zinc-400">
                  <span>📅 {e.date}</span>
                  <span>💳 {e.price_rub} ₽</span>
                  {e.themes.map((t) => (
                    <Pill key={t}>{t}</Pill>
                  ))}
                </div>
                <a
                  href={safeHref(e.booking_url)}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="mt-2 inline-flex items-center gap-1 text-xs text-amber-300 hover:underline"
                >
                  Забронировать <ExternalLink size={12} aria-hidden />
                </a>
              </li>
            ))}
            {data.items.length === 0 && (
              <li className="text-sm text-zinc-400">События не найдены.</li>
            )}
          </ul>
        </Card>
      )}
    </section>
  )
}

type SrsCard = {
  card_id: string
  user_id: string
  front: string
  back: string
  tags: string[]
  ease: number
  interval_days: number
  reps: number
  lapses: number
  due_at: string
}

type SrsDueResponse = {
  user_id: string
  count: number
  items: SrsCard[]
}

const SRS_USER = "demo-user"

function TrainerTab() {
  const [subject, setSubject] = useState<"Литература" | "История">("Литература")
  const [questions, setQuestions] = useState<QuizItem[]>([])
  const [results, setResults] = useState<Record<string, AnswerResult>>({})
  const [loading, setLoading] = useState(false)
  const [srsCards, setSrsCards] = useState<SrsCard[]>([])
  const [srsRevealed, setSrsRevealed] = useState<Record<string, boolean>>({})
  const [srsLoading, setSrsLoading] = useState(false)
  const [srsBuilding, setSrsBuilding] = useState(false)
  const [srsError, setSrsError] = useState<string | null>(null)

  async function loadQuiz(s: "Литература" | "История") {
    setSubject(s)
    setLoading(true)
    setResults({})
    try {
      const res = await fetch(`${API_BASE}/api/trainer/quiz?subject=${encodeURIComponent(s)}&limit=5`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      setQuestions(data.items || [])
    } finally {
      setLoading(false)
    }
  }

  async function answer(q: QuizItem, idx: number) {
    const res = await fetch(`${API_BASE}/api/trainer/answer`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question_id: q.id, answer_index: idx }),
    })
    if (!res.ok) return
    const data: AnswerResult = await res.json()
    setResults((prev) => ({ ...prev, [q.id]: data }))
  }

  async function loadSrsDue() {
    setSrsLoading(true)
    setSrsError(null)
    try {
      const res = await fetch(
        `${API_BASE}/api/srs/due?user_id=${encodeURIComponent(SRS_USER)}&limit=10`
      )
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data: SrsDueResponse = await res.json()
      setSrsCards(data.items || [])
      setSrsRevealed({})
    } catch (err) {
      setSrsError(err instanceof Error ? err.message : "Сервис недоступен")
    } finally {
      setSrsLoading(false)
    }
  }

  async function buildSrsFromRoute() {
    setSrsBuilding(true)
    setSrsError(null)
    try {
      const res = await fetch(`${API_BASE}/api/srs/from-route`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: SRS_USER,
          query: "Хочу понять Пушкина за 4 недели",
          weeks: 4,
        }),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      await loadSrsDue()
    } catch (err) {
      setSrsError(err instanceof Error ? err.message : "Сервис недоступен")
    } finally {
      setSrsBuilding(false)
    }
  }

  async function reviewCard(card: SrsCard, quality: number) {
    try {
      const res = await fetch(`${API_BASE}/api/srs/review`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ card_id: card.card_id, quality }),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      setSrsCards((prev) => prev.filter((c) => c.card_id !== card.card_id))
    } catch (err) {
      setSrsError(err instanceof Error ? err.message : "Сервис недоступен")
    }
  }

  useEffect(() => {
    loadQuiz("Литература")
    loadSrsDue()
  }, [])

  return (
    <section className="py-7">
      <h2 className="text-2xl font-semibold mb-2">Тренажёр ЕГЭ — литература и история</h2>
      <p className="text-sm text-zinc-400 max-w-3xl">
        Демо-вопросы по корпусу. В продакшене покрытие — кодификаторы ФИПИ; прогресс пишется в
        дашборд учителя.
      </p>

      <div className="mt-4 flex gap-2">
        {(["Литература", "История"] as const).map((s) => (
          <button
            key={s}
            onClick={() => loadQuiz(s)}
            className={`rounded-lg border px-4 py-2 text-sm ${
              subject === s
                ? "border-amber-300 bg-amber-300 text-zinc-900"
                : "border-zinc-800 bg-zinc-950 text-zinc-300 hover:border-sky-300"
            }`}
          >
            {s}
          </button>
        ))}
      </div>

      <div className="mt-5 space-y-5">
        {loading && <p className="text-sm text-zinc-400">Загрузка…</p>}
        {!loading &&
          questions.map((q, idx) => {
            const r = results[q.id]
            return (
              <Card key={q.id}>
                <div className="text-xs uppercase tracking-wide text-zinc-500">
                  Вопрос {idx + 1} · {q.topic}
                </div>
                <div className="mt-2 text-base">{q.question}</div>
                <div className="mt-3 grid gap-2 sm:grid-cols-2">
                  {q.options.map((opt, i) => {
                    const isAnswered = r != null
                    const isCorrect = isAnswered && r.correct_index === i
                    let cls = "border-zinc-800 bg-zinc-950 text-zinc-200 hover:border-sky-300"
                    if (isAnswered && isCorrect)
                      cls = "border-emerald-700 bg-emerald-950/40 text-emerald-200"
                    if (isAnswered && !isCorrect) cls = "border-zinc-800 bg-zinc-950 text-zinc-500"
                    return (
                      <button
                        key={i}
                        disabled={isAnswered}
                        onClick={() => answer(q, i)}
                        className={`flex items-start gap-2 rounded-lg border px-3 py-2 text-left text-sm transition-colors ${cls}`}
                      >
                        <span className="mt-0.5 inline-block w-5 text-zinc-500">{i + 1}.</span>
                        <span>{opt}</span>
                        {isAnswered && isCorrect && (
                          <CheckCircle2 size={16} className="ml-auto text-emerald-400" />
                        )}
                      </button>
                    )
                  })}
                </div>
                {r && (
                  <div
                    className={`mt-3 rounded-lg border px-3 py-2 text-sm ${
                      r.correct
                        ? "border-emerald-800 bg-emerald-950/30 text-emerald-200"
                        : "border-amber-800 bg-amber-950/30 text-amber-200"
                    }`}
                  >
                    <div className="flex items-center gap-2 font-medium">
                      {r.correct ? <CheckCircle2 size={14} /> : <XCircle size={14} />}
                      {r.correct ? "Верно." : "Не верно."}
                    </div>
                    <p className="mt-1 text-zinc-300">{r.explanation}</p>
                  </div>
                )}
              </Card>
            )
          })}
      </div>

      <div className="mt-10 border-t border-zinc-800 pt-7">
        <h3 className="text-xl font-semibold">Интервальные повторения (SRS)</h3>
        <p className="mt-1 text-sm text-zinc-400 max-w-3xl">
          Алгоритм SM-2: карточки с фрагментами и цитатами появляются в нужный момент. Демо
          использует учётную запись <code className="text-zinc-300">{SRS_USER}</code>; в проде —
          привязка к ученику и дашборду учителя.
        </p>

        <div className="mt-3 flex flex-wrap items-center gap-2">
          <button
            onClick={loadSrsDue}
            disabled={srsLoading}
            className="inline-flex items-center gap-2 rounded-lg border border-zinc-800 bg-zinc-950 px-3 py-2 text-xs text-zinc-200 hover:border-sky-300 disabled:opacity-60 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-300"
          >
            {srsLoading ? "Загрузка…" : "Обновить очередь"}
          </button>
          <button
            onClick={buildSrsFromRoute}
            disabled={srsBuilding}
            className="inline-flex items-center gap-2 rounded-lg border border-amber-300 bg-amber-300 px-3 py-2 text-xs font-semibold text-zinc-900 hover:brightness-110 disabled:opacity-60 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-300"
          >
            {srsBuilding ? "Создаю…" : "Создать карточки из маршрута"}
          </button>
          <span className="text-xs text-zinc-500">К повторению: {srsCards.length}</span>
        </div>

        {srsError && (
          <p className="mt-3 text-xs text-red-400" role="alert">
            {srsError}
          </p>
        )}

        <div className="mt-5 space-y-3">
          {srsCards.length === 0 && !srsLoading && (
            <p className="text-sm text-zinc-400">
              На сегодня карточек нет. Постройте маршрут и нажмите «Создать карточки из маршрута».
            </p>
          )}
          {srsCards.map((c) => {
            const revealed = !!srsRevealed[c.card_id]
            return (
              <Card key={c.card_id}>
                <div className="text-xs uppercase tracking-wide text-zinc-500">
                  Карточка · повторение #{c.reps + 1}{c.tags.length > 0 && ` · ${c.tags.join(", ")}`}
                </div>
                <div className="mt-2 text-base font-semibold">{sanitizeText(c.front, 1000)}</div>
                {revealed ? (
                  <div className="mt-3 rounded-lg border border-zinc-800 bg-zinc-950/60 p-3 text-sm text-zinc-200 whitespace-pre-line">
                    {sanitizeText(c.back, 4000)}
                  </div>
                ) : (
                  <button
                    onClick={() =>
                      setSrsRevealed((prev) => ({ ...prev, [c.card_id]: true }))
                    }
                    className="mt-3 inline-flex items-center gap-2 rounded-lg border border-zinc-800 bg-zinc-950 px-3 py-2 text-xs text-zinc-200 hover:border-sky-300 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-300"
                  >
                    Показать ответ
                  </button>
                )}
                {revealed && (
                  <div className="mt-3 flex flex-wrap items-center gap-2">
                    <span className="text-xs text-zinc-400 mr-2">Оценка:</span>
                    {[
                      { q: 0, label: "Не помню", tone: "border-red-700 text-red-200" },
                      { q: 2, label: "Сложно", tone: "border-amber-700 text-amber-200" },
                      { q: 4, label: "Хорошо", tone: "border-sky-700 text-sky-200" },
                      { q: 5, label: "Отлично", tone: "border-emerald-700 text-emerald-200" },
                    ].map((b) => (
                      <button
                        key={b.q}
                        onClick={() => reviewCard(c, b.q)}
                        className={`rounded-lg border bg-zinc-950 px-3 py-1 text-xs hover:brightness-110 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-300 ${b.tone}`}
                      >
                        {b.label}
                      </button>
                    ))}
                  </div>
                )}
              </Card>
            )
          })}
        </div>
      </div>
    </section>
  )
}

function DashboardTab() {
  const [data, setData] = useState<RegionalDash | null>(null)
  const [kpis, setKpis] = useState<KpiItem[]>([])

  useEffect(() => {
    fetch(`${API_BASE}/api/dashboard/regional`)
      .then((r) => r.json())
      .then(setData)
      .catch(() => null)
    fetch(`${API_BASE}/api/dashboard/kpi`)
      .then((r) => r.json())
      .then((d) => setKpis(d.items || []))
      .catch(() => null)
  }, [])

  const themesChart = useMemo(() => {
    if (!data) return []
    return data.top_themes.map((t) => ({ name: t.theme, value: t.demand_index }))
  }, [data])

  const trendChart = useMemo(() => {
    return [
      { quarter: "Q4'25", literature: 0, history: 0, russian: 0 },
      { quarter: "Q1'26", literature: 2.1, history: 1.4, russian: 0.8 },
      { quarter: "Q2'26", literature: 4.0, history: 2.3, russian: 1.7 },
      { quarter: "Q3'26", literature: 5.6, history: 3.4, russian: 2.6 },
      { quarter: "Q4'26", literature: 6.4, history: 4.1, russian: 3.2 },
    ]
  }, [])

  if (!data) {
    return (
      <section className="py-7">
        <h2 className="text-2xl font-semibold mb-2">Дашборд региона</h2>
        <p className="text-sm text-zinc-400">Загрузка…</p>
      </section>
    )
  }

  const snap = data.snapshot
  const eng = data.engagement

  return (
    <section className="py-7">
      <h2 className="text-2xl font-semibold mb-2">Дашборд региона</h2>
      <p className="text-sm text-zinc-400 max-w-3xl">
        Период: {data.period}. Все цифры синтетические — для демонстрации структуры. В проде
        читаются из ClickHouse / Yandex DataLens; сегментация по школам, библиотекам и музеям.
      </p>

      <div className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {[
          { label: "Активных пользователей", value: snap.active_users.toLocaleString("ru-RU") },
          { label: "Молодёжь 14–22", value: snap.youth_14_22.toLocaleString("ru-RU") },
          { label: "Учителя", value: snap.teachers.toLocaleString("ru-RU") },
          {
            label: "Библиотеки и музеи",
            value: `${snap.libraries_connected + snap.museums_connected}`,
          },
        ].map((k) => (
          <Card key={k.label}>
            <div className="text-xs text-zinc-400">{k.label}</div>
            <div className="mt-2 text-2xl font-bold text-amber-300">{k.value}</div>
          </Card>
        ))}
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <Card>
          <div className="mb-3 flex items-center gap-2">
            <BarChart3 size={16} className="text-amber-300" />
            <h3 className="text-sm font-semibold">Топ-темы по запросам</h3>
          </div>
          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={themesChart} layout="vertical" margin={{ left: 8, right: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                <XAxis type="number" stroke="#a1a1aa" />
                <YAxis type="category" dataKey="name" stroke="#a1a1aa" width={170} fontSize={11} />
                <Tooltip
                  contentStyle={{ background: "#0E1116", border: "1px solid #27272a" }}
                  cursor={{ fill: "#1f2937" }}
                />
                <Bar dataKey="value" fill="#fbbf24" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card>
          <div className="mb-3 flex items-center gap-2">
            <GraduationCap size={16} className="text-amber-300" />
            <h3 className="text-sm font-semibold">Динамика среднего балла ЕГЭ (п.п.)</h3>
          </div>
          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={trendChart} margin={{ left: 0, right: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                <XAxis dataKey="quarter" stroke="#a1a1aa" />
                <YAxis stroke="#a1a1aa" />
                <Tooltip
                  contentStyle={{ background: "#0E1116", border: "1px solid #27272a" }}
                />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Line type="monotone" dataKey="literature" name="Литература" stroke="#fbbf24" />
                <Line type="monotone" dataKey="history" name="История" stroke="#7dd3fc" />
                <Line type="monotone" dataKey="russian" name="Русский язык" stroke="#a3e635" />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </Card>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <Card>
          <div className="mb-3 flex items-center gap-2">
            <Library size={16} className="text-amber-300" />
            <h3 className="text-sm font-semibold">Вовлечённость и Пушкинская карта</h3>
          </div>
          <table className="w-full text-sm">
            <tbody>
              <tr className="border-b border-zinc-800">
                <td className="py-2 text-zinc-400">Средняя длительность сессии, мин</td>
                <td className="py-2 text-right text-zinc-100">{eng.average_session_minutes}</td>
              </tr>
              <tr className="border-b border-zinc-800">
                <td className="py-2 text-zinc-400">Завершённых маршрутов</td>
                <td className="py-2 text-right text-zinc-100">
                  {eng.routes_completed.toLocaleString("ru-RU")}
                </td>
              </tr>
              <tr className="border-b border-zinc-800">
                <td className="py-2 text-zinc-400">Открытий книг</td>
                <td className="py-2 text-right text-zinc-100">
                  {eng.books_opened.toLocaleString("ru-RU")}
                </td>
              </tr>
              <tr className="border-b border-zinc-800">
                <td className="py-2 text-zinc-400">Решений в тренажёре</td>
                <td className="py-2 text-right text-zinc-100">
                  {eng.trainer_attempts.toLocaleString("ru-RU")}
                </td>
              </tr>
              <tr>
                <td className="py-2 text-zinc-400">Переходы на Пушкинскую карту</td>
                <td className="py-2 text-right text-zinc-100">
                  {eng.pushkin_card_referrals.toLocaleString("ru-RU")}
                </td>
              </tr>
            </tbody>
          </table>
        </Card>

        <Card>
          <div className="mb-3 flex items-center gap-2">
            <ShieldCheck size={16} className="text-emerald-400" />
            <h3 className="text-sm font-semibold">Качество RAG и соответствие</h3>
          </div>
          <table className="w-full text-sm">
            <tbody>
              <tr className="border-b border-zinc-800">
                <td className="py-2 text-zinc-400">Precision@5</td>
                <td className="py-2 text-right">{data.rag_quality.precision_at_5}</td>
              </tr>
              <tr className="border-b border-zinc-800">
                <td className="py-2 text-zinc-400">Recall@10</td>
                <td className="py-2 text-right">{data.rag_quality.recall_at_10}</td>
              </tr>
              <tr className="border-b border-zinc-800">
                <td className="py-2 text-zinc-400">MRR</td>
                <td className="py-2 text-right">{data.rag_quality.mrr}</td>
              </tr>
              <tr className="border-b border-zinc-800">
                <td className="py-2 text-zinc-400">Уровень галлюцинаций</td>
                <td className="py-2 text-right">
                  {(data.rag_quality.hallucination_rate * 100).toFixed(1)}%
                </td>
              </tr>
              <tr>
                <td className="py-2 text-zinc-400">Покрытие источниками</td>
                <td className="py-2 text-right">
                  {(data.rag_quality.citation_coverage * 100).toFixed(0)}%
                </td>
              </tr>
            </tbody>
          </table>
          <div className="mt-3 flex flex-wrap gap-2">
            <Pill tone="good">152-ФЗ</Pill>
            <Pill tone="good">44-ФЗ</Pill>
            <Pill tone="good">Указ Президента №490</Pill>
            <Pill tone="good">Yandex Cloud (РФ)</Pill>
          </div>
        </Card>
      </div>

      {kpis.length > 0 && (
        <Card className="mt-4">
          <div className="mb-3 flex items-center gap-2">
            <BarChart3 size={16} className="text-amber-300" />
            <h3 className="text-sm font-semibold">KPI продукта (демо)</h3>
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-zinc-400">
                <th className="pb-2">Метрика</th>
                <th className="pb-2">Значение</th>
                <th className="pb-2">Цель</th>
                <th className="pb-2">Комментарий</th>
              </tr>
            </thead>
            <tbody>
              {kpis.map((k, i) => (
                <tr key={i} className="border-t border-zinc-800">
                  <td className="py-2 text-zinc-200">{k.metric}</td>
                  <td className="py-2 text-amber-300">{k.value}</td>
                  <td className="py-2 text-zinc-400">{k.target}</td>
                  <td className="py-2 text-zinc-400">{k.comment}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}

      {data.disclaimer && <p className="mt-4 text-xs text-zinc-500">{data.disclaimer}</p>}
    </section>
  )
}

function AboutTab() {
  return (
    <section className="py-7">
      <h2 className="text-2xl font-semibold mb-2">О проекте</h2>
      <p className="max-w-3xl text-sm text-zinc-300">
        ЧитАИ — ИИ-куратор: персональные маршруты по русской литературе, истории и культуре через
        фонды Российской государственной библиотеки и Национальной электронной библиотеки.
        Аудитории: молодёжь 14–22 (Пушкинская карта), учителя, библиотеки, музеи, региональные
        ведомства.
      </p>

      <div className="mt-5 grid gap-4 lg:grid-cols-2">
        <Card>
          <div className="mb-3 flex items-center gap-2">
            <Sparkles size={16} className="text-amber-300" />
            <h3 className="text-sm font-semibold">Российский стек</h3>
          </div>
          <div className="flex flex-wrap gap-2">
            <Pill>YandexGPT 5 Pro</Pill>
            <Pill>GigaChat MAX</Pill>
            <Pill>Kandinsky 3.1</Pill>
            <Pill>Yandex SpeechKit</Pill>
            <Pill>PostgreSQL + pgvector</Pill>
            <Pill>Yandex Cloud (РФ)</Pill>
          </div>
        </Card>

        <Card>
          <div className="mb-3 flex items-center gap-2">
            <ShieldCheck size={16} className="text-emerald-400" />
            <h3 className="text-sm font-semibold">Соответствие требованиям</h3>
          </div>
          <div className="flex flex-wrap gap-2">
            <Pill tone="good">152-ФЗ</Pill>
            <Pill tone="good">44-ФЗ</Pill>
            <Pill tone="good">Указ Президента №490</Pill>
            <Pill tone="good">Нацпроект «Культура»</Pill>
            <Pill tone="good">Нацпроект «Образование»</Pill>
          </div>
        </Card>
      </div>

      <Card className="mt-4">
        <div className="mb-3 flex items-center gap-2">
          <BookOpen size={16} className="text-amber-300" />
          <h3 className="text-sm font-semibold">Что в этом макете и что — в проде</h3>
        </div>
        <ul className="list-disc space-y-2 pl-5 text-sm text-zinc-200">
          <li>
            Корпус: 25 произведений public domain (Пушкин, Лермонтов, Гоголь, Достоевский, Толстой,
            Чехов, Серебряный век, Карамзин, Ключевский, Соловьёв).
          </li>
          <li>Поиск по корпусу: ключевые слова, жанр, класс, темы ЕГЭ.</li>
          <li>Маршрут на 4 недели с цитатами и ссылками на public domain.</li>
          <li>Тренажёр: 18 демо-вопросов (литература и история).</li>
          <li>Дашборды: регион / учитель / партнёр (синтетические данные).</li>
          <li className="text-zinc-400">
            В проде: pgvector-индекс фондов РГБ и НЭБ, реальные SLA, антипромпт-инжекция, фильтр
            галлюцинаций, журнал поиска, Yandex Cloud в РФ.
          </li>
        </ul>
      </Card>

      <Card className="mt-4">
        <h3 className="text-sm font-semibold mb-2">Партнёрства</h3>
        <p className="text-sm text-zinc-400">
          Все партнёрства указаны как гипотезы или находятся в проработке. Финальные письма
          поддержки оформляются после согласования с учреждениями. Демо-стенд работает на корпусе
          public domain без подключения к фондам РГБ и НЭБ.
        </p>
      </Card>

      <Card className="mt-4">
        <h3 className="text-sm font-semibold mb-2">Прототип лендинга</h3>
        <p className="text-sm text-zinc-300">
          Маркетинговый макет лендинга:{" "}
          <a
            className="underline text-amber-300 hover:text-amber-200"
            href={safeHref("https://chitai.bolt.host/#")}
            target="_blank"
            rel="noopener noreferrer"
          >
            chitai.bolt.host
          </a>
          {". Этот демо-стенд — рабочий бэкенд + интерактив, лендинг — продуктовая обложка."}
        </p>
      </Card>
    </section>
  )
}

const GameHost = lazy(() =>
  import("./games/GameHost").then((m) => ({ default: m.GameHost })),
)

type GameId = "brain-dash"

const GAME_BOOK_OPTIONS: { id: string; title: string }[] = [
  { id: "capitanskaya-dochka", title: "Капитанская дочка (А. С. Пушкин)" },
  { id: "evgeniy-onegin", title: "Евгений Онегин (А. С. Пушкин)" },
  { id: "geroy-nashego-vremeni", title: "Герой нашего времени (М. Ю. Лермонтов)" },
  { id: "myortvye-dushi", title: "Мёртвые души (Н. В. Гоголь)" },
  { id: "voyna-i-mir", title: "Война и мир (Л. Н. Толстой)" },
  { id: "prestuplenie-i-nakazanie", title: "Преступление и наказание (Ф. М. Достоевский)" },
]

function GamesTab() {
  const selectedGame: GameId = "brain-dash"
  const [selectedBook, setSelectedBook] = useState<string>(GAME_BOOK_OPTIONS[0]!.id)
  const [running, setRunning] = useState(false)

  const book = GAME_BOOK_OPTIONS.find((b) => b.id === selectedBook) ?? GAME_BOOK_OPTIONS[0]!

  if (running) {
    return (
      <section className="py-8 space-y-6">
        <Card>
          <Suspense
            fallback={
              <div className="text-zinc-300">Загружаем 3D-движок и вопросы из конспекта…</div>
            }
          >
            <GameHost
              gameId={selectedGame}
              konspekt={{ id: book.id, title: book.title, subject: "Литература" }}
              user={{
                id: "demo-user",
                displayName: "Демо-ученик",
                level: 1,
                xp: 0,
                coins: 0,
              }}
              onExitToKonspekt={() => setRunning(false)}
            />
          </Suspense>
        </Card>
      </section>
    )
  }

  return (
    <section className="py-8 space-y-6">
      <Card>
        <div className="flex items-center gap-3">
          <Gamepad2 size={20} className="text-amber-300" aria-hidden />
          <h2 className="text-xl font-semibold">Игра по конспекту</h2>
        </div>
        <p className="mt-2 text-sm text-zinc-400">
          Вопросы для игры генерируются из конспекта пользователя (mode «Учёба») или из произведения
          публичного корпуса. Brain Dash — 3D-runner с короткими блиц-вопросами по тексту произведения.
        </p>

        <div className="mt-5 grid gap-4 md:grid-cols-1">
          <label className="flex flex-col gap-2 text-sm">
            <span className="text-zinc-400">Произведение</span>
            <select
              value={selectedBook}
              onChange={(e) => setSelectedBook(e.target.value)}
              className="rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2 text-zinc-100 focus-visible:ring-2 focus-visible:ring-sky-300"
            >
              {GAME_BOOK_OPTIONS.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.title}
                </option>
              ))}
            </select>
          </label>
        </div>

        <div className="mt-6 flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={() => setRunning(true)}
            className="rounded-md bg-amber-300 px-4 py-2 text-sm font-semibold text-zinc-900 hover:bg-amber-200 focus-visible:ring-2 focus-visible:ring-sky-300"
          >
            Запустить игру
          </button>
          <span className="text-xs text-zinc-500">
            Управление: ← → (или A / D) — перемещение, пробел — прыжок, Esc — пауза.
          </span>
        </div>
      </Card>
    </section>
  )
}

export default function App() {
  const [tab, setTab] = useState<Tab>("curator")
  return (
    <div className="min-h-screen flex flex-col">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-50 focus:rounded-md focus:bg-amber-300 focus:px-3 focus:py-2 focus:text-sm focus:font-semibold focus:text-zinc-900"
      >
        Перейти к основному содержимому
      </a>
      <Header tab={tab} setTab={setTab} />
      <main id="main" tabIndex={-1} className="mx-auto w-full max-w-6xl px-6 flex-1 outline-none">
        <div role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`}>
          {tab === "curator" && <CuratorTab />}
          {tab === "study" && <StudyTab />}
          {tab === "search" && <SearchTab />}
          {tab === "mindmap" && <MindmapTab />}
          {tab === "trainer" && <TrainerTab />}
          {tab === "pushkin" && <PushkinTab />}
          {tab === "dashboard" && <DashboardTab />}
          {tab === "games" && <GamesTab />}
          {tab === "about" && <AboutTab />}
        </div>
      </main>
      <footer className="border-t border-zinc-800 py-5 text-xs text-zinc-500">
        <div className="mx-auto max-w-6xl px-6">
          Демо-стенд ЧитАИ. Все цитаты — public domain. Соответствие 152-ФЗ. © 2026.
        </div>
      </footer>
    </div>
  )
}
