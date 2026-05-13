// Thin, versioned wrapper around localStorage with namespace per spec section 1.6.

export interface Versioned<T> {
  version: number;
  data: T;
}

export function loadJSON<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return fallback;
    const parsed = JSON.parse(raw) as Versioned<T>;
    if (typeof parsed === 'object' && parsed !== null && 'data' in parsed) {
      return parsed.data;
    }
    return fallback;
  } catch {
    return fallback;
  }
}

export function saveJSON<T>(key: string, data: T, version = 1): void {
  try {
    const payload: Versioned<T> = { version, data };
    localStorage.setItem(key, JSON.stringify(payload));
  } catch {
    // Ignore quota / privacy mode errors.
  }
}
