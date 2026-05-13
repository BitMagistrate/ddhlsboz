import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import App from "./App"

type FetchMock = ReturnType<typeof vi.fn>

function jsonResponse(payload: unknown): Response {
  return new Response(JSON.stringify(payload), {
    status: 200,
    headers: { "content-type": "application/json" },
  })
}

function mockFetch(): FetchMock {
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const url = typeof input === "string" ? input : input.toString()
    if (url.includes("/api/curator/route")) {
      return jsonResponse({
        query: "Хочу понять Пушкина за 4 недели",
        summary: "Маршрут на 4 недели по Пушкину.",
        weeks: [
          {
            week: 1,
            title: "Неделя 1",
            description: "Описание недели",
            book: "Капитанская дочка",
            book_id: "kap-doch",
            fragment: "Береги честь смолоду.",
            citation: "Пушкин А.С., Капитанская дочка, гл. 1",
            public_domain_url: "https://example.org/kap-doch",
            actions: ["Прочитать главу 1"],
            pushkin_card_event: null,
          },
        ],
        sources: [{ id: "kap-doch", author: "Пушкин", title: "Капитанская дочка", year: 1836 }],
        disclaimer: "Demo disclaimer",
      })
    }
    if (url.includes("/api/curator/mindmap")) {
      return jsonResponse({
        query: "Пушкин",
        nodes: [
          { id: "q::Пушкин", label: "Пушкин", kind: "query", weight: 1.0 },
          { id: "author::pushkin", label: "А.С. Пушкин", kind: "author", weight: 0.9 },
          { id: "book::kap-doch", label: "Капитанская дочка", kind: "book", weight: 0.8 },
          { id: "theme::ege::Пушкин", label: "Тема ЕГЭ: Пушкин", kind: "theme", weight: 0.7 },
        ],
        edges: [
          { source: "q::Пушкин", target: "author::pushkin", label: "автор", weight: 1.0 },
          { source: "author::pushkin", target: "book::kap-doch", label: "написал", weight: 1.0 },
          { source: "book::kap-doch", target: "theme::ege::Пушкин", label: "тема", weight: 0.7 },
        ],
        citations: [
          {
            source_id: "kap-doch",
            author: "А.С. Пушкин",
            title: "Капитанская дочка",
            fragment: "Береги честь смолоду.",
            citation: "Пушкин А.С., Капитанская дочка, гл. 1",
            url: "https://example.org/kap-doch",
          },
        ],
        safety: { ok: true, reasons: [] },
      })
    }
    if (url.includes("/api/corpus/search")) {
      return jsonResponse({
        query: "Пушкин",
        engine: "hybrid",
        count: 1,
        items: [
          {
            id: "kap-doch",
            author: "А.С. Пушкин",
            title: "Капитанская дочка",
            year: 1836,
            genre: "роман",
            school_grade: 8,
            ege_topics: ["Пушкин"],
            pushkin_card: true,
            summary: "Историческая повесть о пугачёвском бунте.",
            fragment: "Береги честь смолоду.",
            citation: "Пушкин А.С., Капитанская дочка, гл. 1",
            public_domain_url: "https://example.org/kap-doch",
          },
        ],
      })
    }
    if (url.includes("/api/pushkin/events")) {
      return jsonResponse({
        count: 1,
        items: [
          {
            id: "ev-1",
            title: "Пушкинский музей: тематическая экскурсия",
            venue: "Пушкинский музей",
            city: "Москва",
            region: "Москва",
            date: "2026-05-15",
            price_rub: 500,
            age_range: "14-22",
            themes: ["Пушкин"],
            book_ids: ["kap-doch"],
            booking_url: "https://example.org/booking/ev-1",
          },
        ],
      })
    }
    if (url.includes("/api/srs/due")) {
      return jsonResponse({ user_id: "demo-user", count: 0, items: [] })
    }
    if (url.includes("/api/trainer/quiz")) {
      return jsonResponse({
        items: [
          {
            id: "q1",
            topic: "Пушкин",
            subject: "Литература",
            question: "Что значит «Береги честь смолоду»?",
            options: ["А", "Б", "В", "Г"],
            source_id: "kap-doch",
          },
        ],
      })
    }
    if (url.includes("/api/dashboard/regional")) {
      return jsonResponse({
        region: "Москва",
        period: "Q4 2025",
        snapshot: {
          active_users: 1000,
          youth_14_22: 500,
          teachers: 50,
          libraries_connected: 5,
          museums_connected: 3,
        },
        engagement: {
          average_session_minutes: 12,
          routes_completed: 200,
          books_opened: 800,
          trainer_attempts: 1500,
          pushkin_card_referrals: 60,
        },
        education_metrics: [],
        library_metrics: {},
        top_themes: [{ theme: "Пушкин", demand_index: 100 }],
        rag_quality: {
          precision_at_5: 0.9,
          recall_at_10: 0.85,
          mrr: 0.91,
          hallucination_rate: 0.03,
          citation_coverage: 0.98,
        },
        compliance: { "152-ФЗ": true },
      })
    }
    if (url.includes("/api/dashboard/kpi")) {
      return jsonResponse({ items: [] })
    }
    return new Response("{}", { status: 200 })
  })
  globalThis.fetch = fetchMock as unknown as typeof fetch
  return fetchMock as unknown as FetchMock
}

describe("App", () => {
  let fetchMock: FetchMock

  beforeEach(() => {
    fetchMock = mockFetch()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it("рендерит логотип и подпись бренда", async () => {
    render(<App />)
    expect(screen.getAllByText("ЧитАИ").length).toBeGreaterThan(0)
    expect(
      screen.getByText(/ИИ-куратор русского культурного и образовательного контента/i),
    ).toBeInTheDocument()
  })

  it("рендерит все вкладки навигации (role=tab)", () => {
    render(<App />)
    expect(screen.getByRole("tab", { name: /Куратор/i })).toBeInTheDocument()
    expect(screen.getByRole("tab", { name: /Поиск по фондам/i })).toBeInTheDocument()
    expect(screen.getByRole("tab", { name: /Ментальная карта/i })).toBeInTheDocument()
    expect(screen.getByRole("tab", { name: /Тренажёр ЕГЭ/i })).toBeInTheDocument()
    expect(screen.getByRole("tab", { name: /Пушкинская карта/i })).toBeInTheDocument()
    expect(screen.getByRole("tab", { name: /Дашборд региона/i })).toBeInTheDocument()
    expect(screen.getByRole("tab", { name: /О проекте/i })).toBeInTheDocument()
  })

  it("по умолчанию открыта вкладка «Куратор» (aria-selected)", async () => {
    render(<App />)
    expect(
      screen.getByRole("heading", { name: /Маршрут чтения по фондам/i }),
    ).toBeInTheDocument()
    expect(screen.getByRole("tab", { name: /Куратор/i })).toHaveAttribute(
      "aria-selected",
      "true",
    )
    await waitFor(() => expect(fetchMock).toHaveBeenCalled())
  })

  it("переключение на «О проекте» показывает соответствующий текст", async () => {
    render(<App />)
    const user = userEvent.setup()
    await user.click(screen.getByRole("tab", { name: /О проекте/i }))
    expect(screen.getByRole("heading", { name: /О проекте/i })).toBeInTheDocument()
    expect(screen.getByText(/Российский стек/i)).toBeInTheDocument()
    expect(screen.getByText("YandexGPT 5 Pro")).toBeInTheDocument()
  })

  it("переключение на «Тренажёр ЕГЭ» подгружает вопросы и показывает их", async () => {
    render(<App />)
    const user = userEvent.setup()
    await user.click(screen.getByRole("tab", { name: /Тренажёр ЕГЭ/i }))
    await waitFor(() =>
      expect(screen.getByText(/Что значит «Береги честь смолоду»/i)).toBeInTheDocument(),
    )
  })

  it("переключение на «Дашборд региона» рендерит KPI-карточки", async () => {
    render(<App />)
    const user = userEvent.setup()
    await user.click(screen.getByRole("tab", { name: /Дашборд региона/i }))
    await waitFor(() =>
      expect(screen.getByText(/Активных пользователей/i)).toBeInTheDocument(),
    )
    expect(screen.getByText(/Качество RAG и соответствие/i)).toBeInTheDocument()
  })

  it("на вкладке «Куратор» показывает 4 недели маршрута после загрузки", async () => {
    render(<App />)
    await waitFor(() => expect(screen.getByText("Маршрут на 4 недели")).toBeInTheDocument())
    expect(screen.getByText(/Береги честь смолоду/i)).toBeInTheDocument()
  })

  it("на вкладке «Куратор» есть кнопки экспорта .md и .ics", async () => {
    render(<App />)
    await waitFor(() => expect(screen.getByText("Маршрут на 4 недели")).toBeInTheDocument())
    expect(
      screen.getByRole("button", { name: /Скачать маршрут в формате Markdown/i }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole("button", { name: /Скачать маршрут как календарь/i }),
    ).toBeInTheDocument()
  })

  it("на вкладке «Куратор» есть кнопка озвучивания фрагмента (TTS)", async () => {
    render(<App />)
    await waitFor(() => expect(screen.getByText("Маршрут на 4 недели")).toBeInTheDocument())
    expect(
      screen.getAllByRole("button", { name: /Озвучить фрагмент/i }).length,
    ).toBeGreaterThan(0)
  })

  it("вкладка «Поиск по фондам» рендерит результаты гибридного поиска", async () => {
    render(<App />)
    const user = userEvent.setup()
    await user.click(screen.getByRole("tab", { name: /Поиск по фондам/i }))
    await waitFor(() =>
      expect(screen.getByRole("heading", { name: /Поиск по фондам/i })).toBeInTheDocument(),
    )
    await waitFor(() =>
      expect(screen.getAllByText(/Капитанская дочка/i).length).toBeGreaterThan(0),
    )
    expect(screen.getByLabelText(/Поисковый запрос/i)).toBeInTheDocument()
    expect(screen.getByText(/Гибридный режим/i)).toBeInTheDocument()
  })

  it("вкладка «Ментальная карта» рендерит узлы и связи", async () => {
    render(<App />)
    const user = userEvent.setup()
    await user.click(screen.getByRole("tab", { name: /Ментальная карта/i }))
    await waitFor(() =>
      expect(screen.getByRole("heading", { name: /Ментальная карта корпуса/i })).toBeInTheDocument(),
    )
    await waitFor(() => expect(screen.getByText(/Узлы карты/i)).toBeInTheDocument())
    expect(screen.getAllByText(/А\.С\. Пушкин/i).length).toBeGreaterThan(0)
    expect(screen.getByText(/Связи \(/i)).toBeInTheDocument()
  })

  it("вкладка «Пушкинская карта» рендерит события из API", async () => {
    render(<App />)
    const user = userEvent.setup()
    await user.click(screen.getByRole("tab", { name: /Пушкинская карта/i }))
    await waitFor(() =>
      expect(
        screen.getByRole("heading", { name: /Пушкинская карта — события/i }),
      ).toBeInTheDocument(),
    )
    await waitFor(() =>
      expect(
        screen.getByText(/Пушкинский музей: тематическая экскурсия/i),
      ).toBeInTheDocument(),
    )
    expect(screen.getByLabelText(/Фильтр по региону/i)).toBeInTheDocument()
  })

  it("вкладка «Тренажёр ЕГЭ» содержит секцию SRS (интервальные повторения)", async () => {
    render(<App />)
    const user = userEvent.setup()
    await user.click(screen.getByRole("tab", { name: /Тренажёр ЕГЭ/i }))
    await waitFor(() =>
      expect(
        screen.getByRole("heading", { name: /Интервальные повторения/i }),
      ).toBeInTheDocument(),
    )
    expect(
      screen.getByRole("button", { name: /Создать карточки из маршрута/i }),
    ).toBeInTheDocument()
    expect(screen.getByText(/На сегодня карточек нет/i)).toBeInTheDocument()
  })

  it("при ошибке fetch выводит сообщение об ошибке API", async () => {
    globalThis.fetch = vi.fn().mockRejectedValue(new Error("boom")) as unknown as typeof fetch
    render(<App />)
    await waitFor(() =>
      expect(screen.getAllByText(/Не удалось обратиться к API/i).length).toBeGreaterThan(0),
    )
  })

  it("в футере есть строка соответствия 152-ФЗ", () => {
    render(<App />)
    expect(screen.getByText(/Соответствие 152-ФЗ/i)).toBeInTheDocument()
  })

  it("отрисовывает 6 примеров запросов (chip-кнопки)", () => {
    render(<App />)
    expect(
      screen.getByRole("button", { name: /Хочу понять Пушкина за 4 недели/i }),
    ).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /Маршрут по Серебряному веку/i })).toBeInTheDocument()
  })

  it("в About показаны pill-плашки соответствия (152-ФЗ, 44-ФЗ)", async () => {
    render(<App />)
    const user = userEvent.setup()
    await user.click(screen.getByRole("tab", { name: /О проекте/i }))
    expect(screen.getAllByText("152-ФЗ").length).toBeGreaterThan(0)
    expect(screen.getByText("44-ФЗ")).toBeInTheDocument()
  })

  it("есть skip-link «Перейти к основному содержимому» (WCAG 2.4.1)", () => {
    render(<App />)
    const link = screen.getByRole("link", { name: /Перейти к основному содержимому/i })
    expect(link).toHaveAttribute("href", "#main")
  })

  it("у выбранной вкладки tabIndex=0, у остальных tabIndex=-1 (roving)", () => {
    render(<App />)
    expect(screen.getByRole("tab", { name: /Куратор/i })).toHaveAttribute("tabindex", "0")
    expect(screen.getByRole("tab", { name: /Тренажёр ЕГЭ/i })).toHaveAttribute("tabindex", "-1")
    expect(screen.getByRole("tab", { name: /Дашборд региона/i })).toHaveAttribute("tabindex", "-1")
  })
})
