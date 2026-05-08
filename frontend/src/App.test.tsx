import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import App from "./App"

type FetchMock = ReturnType<typeof vi.fn>

function mockFetch(): FetchMock {
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const url = typeof input === "string" ? input : input.toString()
    if (url.includes("/api/curator/route")) {
      return new Response(
        JSON.stringify({
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
        }),
        { status: 200, headers: { "content-type": "application/json" } },
      )
    }
    if (url.includes("/api/trainer/quiz")) {
      return new Response(
        JSON.stringify({
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
        }),
        { status: 200, headers: { "content-type": "application/json" } },
      )
    }
    if (url.includes("/api/dashboard/regional")) {
      return new Response(
        JSON.stringify({
          region: "Москва",
          period: "Q4 2025",
          snapshot: { active_users: 1000, youth_14_22: 500, teachers: 50, libraries_connected: 5, museums_connected: 3 },
          engagement: { average_session_minutes: 12, routes_completed: 200, books_opened: 800, trainer_attempts: 1500, pushkin_card_referrals: 60 },
          education_metrics: [],
          library_metrics: {},
          top_themes: [{ theme: "Пушкин", demand_index: 100 }],
          rag_quality: { precision_at_5: 0.9, recall_at_10: 0.85, mrr: 0.91, hallucination_rate: 0.03, citation_coverage: 0.98 },
          compliance: { "152-ФЗ": true },
        }),
        { status: 200, headers: { "content-type": "application/json" } },
      )
    }
    if (url.includes("/api/dashboard/kpi")) {
      return new Response(JSON.stringify({ items: [] }), { status: 200 })
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

  it("рендерит все четыре вкладки навигации (role=tab)", () => {
    render(<App />)
    expect(screen.getByRole("tab", { name: /Куратор/i })).toBeInTheDocument()
    expect(screen.getByRole("tab", { name: /Тренажёр ЕГЭ/i })).toBeInTheDocument()
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

  it("при ошибке fetch выводит сообщение об ошибке API", async () => {
    globalThis.fetch = vi.fn().mockRejectedValue(new Error("boom")) as unknown as typeof fetch
    render(<App />)
    await waitFor(() =>
      expect(screen.getByText(/Не удалось обратиться к API/i)).toBeInTheDocument(),
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
