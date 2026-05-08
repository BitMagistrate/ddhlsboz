import { useEffect, useMemo, useState } from "react"
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

const API_BASE = (import.meta.env.VITE_API_BASE as string) || "http://localhost:8000"

type Tab = "curator" | "trainer" | "dashboard" | "about"

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
    { id: "curator", label: "Куратор", icon: <Compass size={16} /> },
    { id: "trainer", label: "Тренажёр ЕГЭ", icon: <GraduationCap size={16} /> },
    { id: "dashboard", label: "Дашборд региона", icon: <BarChart3 size={16} /> },
    { id: "about", label: "О проекте", icon: <Sparkles size={16} /> },
  ]
  return (
    <header className="border-b border-zinc-800">
      <div className="mx-auto max-w-6xl px-6 pt-7 pb-1">
        <Logo />
        <nav className="mt-5 flex flex-wrap gap-1 border-b border-zinc-800">
          {tabs.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`flex items-center gap-2 px-4 py-3 text-sm border-b-2 -mb-px transition-colors ${
                tab === t.id
                  ? "border-amber-300 text-zinc-100"
                  : "border-transparent text-zinc-400 hover:text-zinc-200"
              }`}
            >
              {t.icon}
              {t.label}
            </button>
          ))}
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
          <h3 className="text-lg font-semibold">Маршрут на 4 недели</h3>
          <p className="mt-1 text-sm text-zinc-400">{route.summary}</p>
          <div className="mt-5 space-y-5">
            {route.weeks.map((w) => (
              <div key={w.week} className="border-l-2 border-amber-300 pl-4">
                <div className="text-base font-semibold">{w.title}</div>
                <div className="mt-1 text-sm">{w.description}</div>
                <div className="mt-2 border-l-2 border-sky-300 pl-3 text-sm italic text-zinc-200">
                  {w.fragment}
                </div>
                <div className="mt-2 text-xs text-zinc-400">
                  Источник: {w.citation}
                  <br />
                  Текст:{" "}
                  <a
                    href={w.public_domain_url}
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

function TrainerTab() {
  const [subject, setSubject] = useState<"Литература" | "История">("Литература")
  const [questions, setQuestions] = useState<QuizItem[]>([])
  const [results, setResults] = useState<Record<string, AnswerResult>>({})
  const [loading, setLoading] = useState(false)

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

  useEffect(() => {
    loadQuiz("Литература")
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
    </section>
  )
}

export default function App() {
  const [tab, setTab] = useState<Tab>("curator")
  return (
    <div className="min-h-screen flex flex-col">
      <Header tab={tab} setTab={setTab} />
      <main className="mx-auto w-full max-w-6xl px-6 flex-1">
        {tab === "curator" && <CuratorTab />}
        {tab === "trainer" && <TrainerTab />}
        {tab === "dashboard" && <DashboardTab />}
        {tab === "about" && <AboutTab />}
      </main>
      <footer className="border-t border-zinc-800 py-5 text-xs text-zinc-500">
        <div className="mx-auto max-w-6xl px-6">
          Демо-стенд ЧитАИ. Все цитаты — public domain. Соответствие 152-ФЗ. © 2026.
        </div>
      </footer>
    </div>
  )
}
