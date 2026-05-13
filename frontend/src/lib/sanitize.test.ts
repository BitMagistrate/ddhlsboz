import { describe, expect, it } from "vitest"

import { escapeHtml, safeHref, sanitizeHtml, sanitizeText, truncate } from "./sanitize"

describe("sanitizeText", () => {
  it("возвращает пустую строку для non-string", () => {
    expect(sanitizeText(undefined)).toBe("")
    expect(sanitizeText(null)).toBe("")
    expect(sanitizeText(42 as unknown as string)).toBe("")
  })

  it("удаляет управляющие символы и нормализует переводы строк", () => {
    expect(sanitizeText("a\u0000b\u0007c")).toBe("a b c")
    expect(sanitizeText("a\r\nb\rc")).toBe("a\nb\nc")
    expect(sanitizeText("\uFEFFhello")).toBe("hello")
  })

  it("уважает max-длину", () => {
    expect(sanitizeText("a".repeat(20), 5).length).toBeLessThanOrEqual(6)
  })
})

describe("truncate", () => {
  it("оставляет короткие как есть", () => {
    expect(truncate("hi", 10)).toBe("hi")
  })
  it("обрезает с многоточием", () => {
    expect(truncate("hello world", 5)).toMatch(/^h.{1,5}…$/)
  })
})

describe("escapeHtml", () => {
  it("экранирует ключевые символы", () => {
    expect(escapeHtml('<script>alert("xss")</script>')).toBe(
      "&lt;script&gt;alert(&quot;xss&quot;)&lt;/script&gt;",
    )
    expect(escapeHtml("Bobby's Tables & Co")).toBe("Bobby&#39;s Tables &amp; Co")
  })
  it("игнорирует non-string", () => {
    expect(escapeHtml(undefined)).toBe("")
  })
})

describe("sanitizeHtml", () => {
  it("вырезает скрипты", () => {
    const out = sanitizeHtml('<p>safe</p><script>alert(1)</script>')
    expect(out).toContain("safe")
    expect(out).not.toContain("<script")
  })

  it("режет on* атрибуты", () => {
    const out = sanitizeHtml('<a href="https://example.com" onclick="x()">link</a>')
    expect(out).toContain("href=\"https://example.com\"")
    expect(out).not.toContain("onclick")
  })

  it("оставляет разрешённые теги", () => {
    const out = sanitizeHtml("<p><strong>жирный</strong> + <em>курсив</em></p>")
    expect(out).toContain("<strong>жирный</strong>")
    expect(out).toContain("<em>курсив</em>")
  })
})

describe("safeHref", () => {
  it("блокирует javascript:", () => {
    expect(safeHref("javascript:alert(1)")).toBe("#")
    expect(safeHref("JAVAScript:alert(1)")).toBe("#")
  })
  it("блокирует data:/vbscript:", () => {
    expect(safeHref("data:text/html,<script>")).toBe("#")
    expect(safeHref("vbscript:msg")).toBe("#")
  })
  it("разрешает http/https/mailto/tel/якоря/относительные", () => {
    expect(safeHref("https://chitai.education/about")).toBe("https://chitai.education/about")
    expect(safeHref("mailto:a@b.ru")).toBe("mailto:a@b.ru")
    expect(safeHref("tel:+79991234567")).toBe("tel:+79991234567")
    expect(safeHref("#anchor")).toBe("#anchor")
    expect(safeHref("/route")).toBe("/route")
  })
  it("возвращает # для мусора", () => {
    expect(safeHref(123 as unknown as string)).toBe("#")
    expect(safeHref("")).toBe("#")
    expect(safeHref("nonsense")).toBe("#")
  })
})
