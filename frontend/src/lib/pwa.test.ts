import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { registerServiceWorker } from "./pwa"

describe("registerServiceWorker", () => {
  const realWindow = globalThis.window
  const realNavigator = globalThis.navigator

  beforeEach(() => {
    vi.resetAllMocks()
  })

  afterEach(() => {
    Object.defineProperty(globalThis, "window", { configurable: true, value: realWindow })
    Object.defineProperty(globalThis, "navigator", { configurable: true, value: realNavigator })
  })

  it("выходит без ошибки, если serviceWorker отсутствует", () => {
    Object.defineProperty(globalThis, "navigator", { configurable: true, value: {} })
    expect(() => registerServiceWorker()).not.toThrow()
  })

  it("регистрирует /sw.js при window.load в production-режиме", async () => {
    vi.stubEnv("DEV", false)
    const register = vi.fn().mockResolvedValue({})
    Object.defineProperty(globalThis, "navigator", {
      configurable: true,
      value: { serviceWorker: { register } },
    })
    const handlers: Record<string, () => void> = {}
    const addEventListener = vi.fn((evt: string, cb: () => void) => {
      handlers[evt] = cb
    })
    Object.defineProperty(globalThis, "window", {
      configurable: true,
      value: { addEventListener },
    })

    registerServiceWorker()
    expect(addEventListener).toHaveBeenCalledWith("load", expect.any(Function))
    handlers.load?.()
    expect(register).toHaveBeenCalledWith("/sw.js")
    vi.unstubAllEnvs()
  })

  it("в dev-режиме не регистрирует SW", () => {
    vi.stubEnv("DEV", true)
    const register = vi.fn()
    Object.defineProperty(globalThis, "navigator", {
      configurable: true,
      value: { serviceWorker: { register } },
    })
    const addEventListener = vi.fn()
    Object.defineProperty(globalThis, "window", {
      configurable: true,
      value: { addEventListener },
    })
    registerServiceWorker()
    expect(addEventListener).not.toHaveBeenCalled()
    expect(register).not.toHaveBeenCalled()
    vi.unstubAllEnvs()
  })
})
