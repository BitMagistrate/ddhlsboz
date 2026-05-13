// Регистрация service worker для ЧитАИ.
// В dev (vite serve) намеренно отключаем SW, чтобы не кешировать HMR-апдейты.

export function registerServiceWorker(): void {
  if (typeof window === "undefined") return
  if (!("serviceWorker" in navigator)) return
  if (import.meta.env.DEV) return

  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch((err) => {
      console.warn("[chitai] service worker registration failed", err)
    })
  })
}
