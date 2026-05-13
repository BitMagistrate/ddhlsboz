import { lazy, Suspense, useCallback, useEffect, useState } from 'react';
import type {
  GameId,
  GameLaunchContext,
  GameResult,
  GameSettings,
  Konspekt,
  QuizQuestion,
  User,
} from './common/types';
import { fetchQuestions } from './common/questionsClient';
import { ErrorScreen } from './common/ErrorScreen';
import './common/common.css';

const BrainDash = lazy(() =>
  import('./brain-dash').then((m) => ({ default: m.BrainDash })),
);

interface GameHostProps {
  gameId: GameId;
  konspekt: Konspekt;
  user: User;
  settings?: Partial<GameSettings>;
  onExitToKonspekt: () => void;
  onResultsPersisted?: (result: GameResult) => void;
}

const DEFAULT_SETTINGS: GameSettings = {
  soundVolume: 0.6,
  musicVolume: 0.4,
  reducedMotion: false,
  difficultyHint: 'auto',
  language: 'ru',
};

type Phase =
  | { kind: 'loading' }
  | { kind: 'error'; message: string }
  | { kind: 'playing'; questions: QuizQuestion[] };

const QUESTIONS_PER_ROUND: Record<GameId, number> = {
  'brain-dash': 5,
};

export function GameHost(props: GameHostProps) {
  const { gameId, konspekt, user, onExitToKonspekt, onResultsPersisted } = props;
  const [phase, setPhase] = useState<Phase>({ kind: 'loading' });
  const [retryToken, setRetryToken] = useState(0);

  const settings: GameSettings = { ...DEFAULT_SETTINGS, ...props.settings };

  useEffect(() => {
    let cancelled = false;
    setPhase({ kind: 'loading' });
    fetchQuestions({
      konspekt,
      gameId,
      count: QUESTIONS_PER_ROUND[gameId],
      simulateFailureRate: 0,
    })
      .then((questions) => {
        if (cancelled) return;
        if (questions.length === 0) {
          setPhase({ kind: 'error', message: 'Пул вопросов оказался пустым.' });
          return;
        }
        setPhase({ kind: 'playing', questions });
      })
      .catch(() => {
        if (cancelled) return;
        setPhase({
          kind: 'error',
          message: 'Не удалось загрузить вопросы. Проверьте соединение.',
        });
      });
    return () => {
      cancelled = true;
    };
  }, [gameId, konspekt, retryToken]);

  const handleResult = useCallback(
    (result: GameResult) => {
      onResultsPersisted?.(result);
    },
    [onResultsPersisted],
  );

  const handleExit = useCallback(
    (_reason: 'user' | 'finished' | 'error') => {
      onExitToKonspekt();
    },
    [onExitToKonspekt],
  );

  const handleRequestExtra = useCallback(
    async (count: number) =>
      fetchQuestions({ konspekt, gameId, count, simulateFailureRate: 0 }),
    [konspekt, gameId],
  );

  if (phase.kind === 'loading') {
    return (
      <div className="overlay-root">
        <div className="card" style={{ alignItems: 'center', textAlign: 'center' }}>
          <div className="spinner" />
          <div className="title-2">Готовим вопросы…</div>
          <div className="muted">Конспект: {konspekt.title}</div>
          <button className="btn ghost" onClick={onExitToKonspekt}>
            К конспекту
          </button>
        </div>
      </div>
    );
  }
  if (phase.kind === 'error') {
    return (
      <ErrorScreen
        message={phase.message}
        onRetry={() => setRetryToken((t) => t + 1)}
        onExit={onExitToKonspekt}
      />
    );
  }

  const context: GameLaunchContext = {
    user,
    konspekt,
    questions: phase.questions,
    settings,
    callbacks: {
      onExit: handleExit,
      onResult: handleResult,
      onRequestExtraQuestions: handleRequestExtra,
    },
  };

  return (
    <Suspense
      fallback={
        <div className="overlay-root">
          <div className="card" style={{ alignItems: 'center' }}>
            <div className="spinner" />
            <div className="muted">Загрузка игры…</div>
          </div>
        </div>
      }
    >
      <BrainDash context={context} />
    </Suspense>
  );
}
