import type { Konspekt, QuizQuestion, GameId } from './types';
import { sanitizeText } from '../../lib/sanitize';

// Контракт: backend `/api/study/quiz` принимает либо konspekt_id, либо
// book_id (произведение из публичного корпуса), отдаёт массив вопросов
// в shape, совместимом с типом QuizQuestion. Здесь только парсинг + XSS-санитайз.

export interface FetchQuestionsOptions {
  konspekt: Konspekt;
  gameId: GameId;
  count: number;
  difficulty?: 'auto' | 'easy' | 'normal' | 'hard';
  exclude?: string[];
  simulateFailureRate?: number;
}

interface RawQuizQuestion {
  id: string;
  text: string;
  options: { id: string; text: string }[];
  correctOptionId: string;
  explanation?: string;
  difficulty?: number;
  sourceParagraphId?: string;
}

const ALLOWED_DIFFICULTIES = new Set<1 | 2 | 3 | 4 | 5>([1, 2, 3, 4, 5]);

function normaliseDifficulty(raw: unknown): 1 | 2 | 3 | 4 | 5 {
  const n = typeof raw === 'number' ? raw : Number.parseInt(String(raw ?? ''), 10);
  if (Number.isFinite(n)) {
    const clamped = Math.max(1, Math.min(5, Math.round(n))) as 1 | 2 | 3 | 4 | 5;
    if (ALLOWED_DIFFICULTIES.has(clamped)) return clamped;
  }
  return 2;
}

export async function fetchQuestions(
  opts: FetchQuestionsOptions,
): Promise<QuizQuestion[]> {
  const params = new URLSearchParams({
    konspekt_id: opts.konspekt.id,
    count: String(opts.count),
  });
  const response = await fetch(`/api/study/quiz?${params.toString()}`);
  if (!response.ok) {
    throw new Error(`Не удалось загрузить вопросы (HTTP ${response.status})`);
  }
  const data = (await response.json()) as { questions?: RawQuizQuestion[] };
  const raw = Array.isArray(data.questions) ? data.questions : [];
  const excludeSet = new Set(opts.exclude ?? []);

  return raw
    .filter((q) => q && q.id && !excludeSet.has(q.id))
    .map((q) => ({
      id: String(q.id),
      text: sanitizeText(q.text ?? '', 500),
      options: (q.options ?? []).map((o) => ({
        id: String(o.id),
        text: sanitizeText(o.text ?? '', 200),
      })),
      correctOptionId: String(q.correctOptionId),
      explanation: q.explanation ? sanitizeText(q.explanation, 2000) : undefined,
      difficulty: normaliseDifficulty(q.difficulty),
      sourceParagraphId: q.sourceParagraphId,
    }));
}
