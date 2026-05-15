import { describe, expect, it, vi, afterEach } from 'vitest';
import { fetchQuestions } from './questionsClient';

const mockKonspekt = {
  id: 'capitanskaya-dochka',
  title: 'Капитанская дочка',
  subject: 'Литература',
};

const okResponse = (questions: unknown) =>
  new Response(JSON.stringify({ questions }), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  });

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('fetchQuestions', () => {
  it('passes konspekt id and count through query params', async () => {
    const fetchSpy = vi.fn().mockResolvedValue(okResponse([]));
    vi.stubGlobal('fetch', fetchSpy);

    await fetchQuestions({ konspekt: mockKonspekt, gameId: 'brain-dash', count: 7 });

    expect(fetchSpy).toHaveBeenCalledTimes(1);
    const url = String(fetchSpy.mock.calls[0]![0]);
    expect(url).toContain('/api/study/quiz?');
    expect(url).toContain('konspekt_id=capitanskaya-dochka');
    expect(url).toContain('count=7');
  });

  it('parses well-formed question payload', async () => {
    const fetchSpy = vi.fn().mockResolvedValue(
      okResponse([
        {
          id: 'q-0',
          text: 'Вопрос',
          options: [
            { id: 'q-0-opt-0', text: 'A' },
            { id: 'q-0-opt-1', text: 'B' },
          ],
          correctOptionId: 'q-0-opt-0',
          explanation: 'Пояснение',
          difficulty: 3,
        },
      ]),
    );
    vi.stubGlobal('fetch', fetchSpy);

    const out = await fetchQuestions({
      konspekt: mockKonspekt,
      gameId: 'brain-dash',
      count: 1,
    });

    expect(out).toHaveLength(1);
    expect(out[0]!.id).toBe('q-0');
    expect(out[0]!.text).toBe('Вопрос');
    expect(out[0]!.options).toHaveLength(2);
    expect(out[0]!.correctOptionId).toBe('q-0-opt-0');
    expect(out[0]!.difficulty).toBe(3);
  });

  it('normalises control characters and zero-width chars in text fields', async () => {
    const fetchSpy = vi.fn().mockResolvedValue(
      okResponse([
        {
          id: 'q-0',
          text: 'Вопрос\u0000\u0001 с\u200B BOM',
          options: [
            { id: 'q-0-opt-0', text: 'A\uFEFF' },
            { id: 'q-0-opt-1', text: 'B\u202E' },
          ],
          correctOptionId: 'q-0-opt-0',
          explanation: 'Пояснение\u0008',
        },
      ]),
    );
    vi.stubGlobal('fetch', fetchSpy);

    const out = await fetchQuestions({
      konspekt: mockKonspekt,
      gameId: 'brain-dash',
      count: 1,
    });

    // sanitizeText удаляет ASCII-управляющие, BOM/RLO/zero-width.
    // eslint-disable-next-line no-control-regex
    expect(out[0]!.text).not.toMatch(/[\u0000-\u0008]/);
    expect(out[0]!.text).not.toMatch(/[\u200B-\u200F\u202A-\u202E\uFEFF]/);
    expect(out[0]!.options[0]!.text).not.toContain('\uFEFF');
    expect(out[0]!.options[1]!.text).not.toContain('\u202E');
    // eslint-disable-next-line no-control-regex
    expect(out[0]!.explanation).not.toMatch(/[\u0000-\u0008]/);
  });

  it('truncates oversized text to the configured max', async () => {
    const huge = 'А'.repeat(600);
    const fetchSpy = vi.fn().mockResolvedValue(
      okResponse([
        {
          id: 'q-0',
          text: huge,
          options: [
            { id: '0', text: 'a' },
            { id: '1', text: 'b' },
          ],
          correctOptionId: '0',
        },
      ]),
    );
    vi.stubGlobal('fetch', fetchSpy);

    const out = await fetchQuestions({
      konspekt: mockKonspekt,
      gameId: 'brain-dash',
      count: 1,
    });

    // sanitizeText(..., 500) → не больше 500 знаков (плюс одно троеточие).
    expect(out[0]!.text.length).toBeLessThanOrEqual(501);
  });

  it('clamps difficulty into [1, 5] integer range', async () => {
    const fetchSpy = vi.fn().mockResolvedValue(
      okResponse([
        {
          id: 'q-0',
          text: 'a',
          options: [
            { id: '0', text: 'a' },
            { id: '1', text: 'b' },
          ],
          correctOptionId: '0',
          difficulty: 999,
        },
        {
          id: 'q-1',
          text: 'b',
          options: [
            { id: '0', text: 'a' },
            { id: '1', text: 'b' },
          ],
          correctOptionId: '0',
          difficulty: -5,
        },
        {
          id: 'q-2',
          text: 'c',
          options: [
            { id: '0', text: 'a' },
            { id: '1', text: 'b' },
          ],
          correctOptionId: '0',
        },
      ]),
    );
    vi.stubGlobal('fetch', fetchSpy);

    const out = await fetchQuestions({
      konspekt: mockKonspekt,
      gameId: 'brain-dash',
      count: 3,
    });

    expect(out[0]!.difficulty).toBe(5);
    expect(out[1]!.difficulty).toBe(1);
    expect(out[2]!.difficulty).toBe(2);
  });

  it('filters out excluded ids', async () => {
    const fetchSpy = vi.fn().mockResolvedValue(
      okResponse([
        {
          id: 'q-0',
          text: 'a',
          options: [
            { id: '0', text: 'a' },
            { id: '1', text: 'b' },
          ],
          correctOptionId: '0',
        },
        {
          id: 'q-1',
          text: 'b',
          options: [
            { id: '0', text: 'a' },
            { id: '1', text: 'b' },
          ],
          correctOptionId: '0',
        },
      ]),
    );
    vi.stubGlobal('fetch', fetchSpy);

    const out = await fetchQuestions({
      konspekt: mockKonspekt,
      gameId: 'brain-dash',
      count: 2,
      exclude: ['q-0'],
    });
    expect(out).toHaveLength(1);
    expect(out[0]!.id).toBe('q-1');
  });

  it('throws on non-2xx HTTP responses', async () => {
    const fetchSpy = vi.fn().mockResolvedValue(
      new Response('Server error', { status: 503 }),
    );
    vi.stubGlobal('fetch', fetchSpy);

    await expect(
      fetchQuestions({ konspekt: mockKonspekt, gameId: 'brain-dash', count: 1 }),
    ).rejects.toThrow(/HTTP 503/);
  });
});
