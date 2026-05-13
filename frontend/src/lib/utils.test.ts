import { describe, expect, it } from "vitest"
import { cn } from "./utils"

describe("cn (class merger)", () => {
  it("объединяет несколько классов через пробел", () => {
    expect(cn("px-2", "py-1")).toBe("px-2 py-1")
  })

  it("игнорирует falsy-значения (undefined / null / false)", () => {
    expect(cn("a", undefined, null, false, "b")).toBe("a b")
  })

  it("резолвит конфликтующие tailwind-классы — побеждает последний", () => {
    expect(cn("px-2", "px-4")).toBe("px-4")
  })

  it("корректно обрабатывает массивы и объекты (clsx-API)", () => {
    expect(cn(["a", "b"], { active: true, hidden: false })).toBe("a b active")
  })

  it("возвращает пустую строку без аргументов", () => {
    expect(cn()).toBe("")
  })
})
