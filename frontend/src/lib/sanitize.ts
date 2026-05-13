/**
 * sanitize.ts — централизованный санитайзер пользовательского ввода.
 *
 * React 18 уже автоматически экранирует строки в JSX, поэтому
 * простой текст безопасен из коробки. Этот модуль нужен для трёх
 * случаев, где XSS-вектор реален:
 *
 * 1) Рендер пользовательского markdown / HTML (любой `dangerouslySetInnerHTML`).
 * 2) Прямая запись в DOM через document.* / innerHTML.
 * 3) Безопасные строки для атрибутов href / src (открытие в новой вкладке).
 *
 * Поверх стандартного `escapeHtml` мы используем DOMPurify
 * (isomorphic-dompurify), чтобы изоморфно работать и в Node (vitest),
 * и в браузере. Для строковых сценариев (front/back карточек,
 * ошибок API) достаточно `sanitizeText`.
 */
import DOMPurify from "isomorphic-dompurify"

// Мы намеренно фильтруем все ASCII-управляющие символы (кроме \t \n \r),
// чтобы они не попали в UI и не сломали layout / акс.
// eslint-disable-next-line no-control-regex
const CONTROL_CHARS = /[\u0000-\u0008\u000B\u000C\u000E-\u001F\u007F]/g

/** Жёстко обрезает строку до `max` знаков, добавляет … если был обрез. */
export function truncate(value: string, max = 4000): string {
  if (value.length <= max) return value
  return value.slice(0, max).trimEnd() + "…"
}

/**
 * Нормализует и обрезает текст для безопасного отображения в JSX.
 *
 * - Заменяет управляющие символы (кроме \t/\n/\r) пробелом.
 * - Схлопывает CRLF/CR в LF.
 * - Удаляет невидимые BOM/RLO/zero-width.
 * - Жёсткий лимит длины.
 *
 * Не превращает текст в HTML — это просто чистая строка.
 */
export function sanitizeText(value: unknown, max = 4000): string {
  if (typeof value !== "string") return ""
  return truncate(
    value
      .replace(/\r\n?/g, "\n")
      .replace(CONTROL_CHARS, " ")
      .replace(/[\u200B-\u200F\u202A-\u202E\uFEFF]/g, ""),
    max,
  )
}

/** Экранирование служебных HTML-символов (для случаев, где надо вставить в HTML). */
export function escapeHtml(value: unknown): string {
  if (typeof value !== "string") return ""
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;")
}

/**
 * Полное санирование HTML (используется только при необходимости
 * `dangerouslySetInnerHTML`, например для markdown-рендера).
 *
 * Запрещает скрипты, формы, объекты, iframe-ы и любые `on*` атрибуты.
 */
export function sanitizeHtml(html: string): string {
  return DOMPurify.sanitize(html, {
    ALLOWED_TAGS: [
      "a",
      "b",
      "blockquote",
      "br",
      "code",
      "em",
      "h1",
      "h2",
      "h3",
      "h4",
      "h5",
      "h6",
      "hr",
      "i",
      "li",
      "ol",
      "p",
      "pre",
      "small",
      "span",
      "strong",
      "u",
      "ul",
    ],
    ALLOWED_ATTR: ["href", "title", "lang", "dir"],
    ALLOW_DATA_ATTR: false,
    FORBID_TAGS: ["script", "iframe", "object", "embed", "style", "form", "input", "button"],
    FORBID_ATTR: ["onerror", "onload", "onclick", "onmouseover", "onfocus", "srcdoc"],
  })
}

/** Безопасный URL для `href`. Разрешены только http(s) и mailto/tel. */
export function safeHref(value: unknown): string {
  if (typeof value !== "string") return "#"
  const trimmed = value.trim()
  if (!trimmed) return "#"
  if (/^(javascript|data|vbscript):/i.test(trimmed)) return "#"
  if (/^(https?:|mailto:|tel:|\/|#)/i.test(trimmed)) return trimmed
  return "#"
}
