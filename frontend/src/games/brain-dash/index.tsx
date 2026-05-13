import { useCallback, useEffect, useRef, useState } from 'react';
import type {
  AnswerEvent,
  GameLaunchContext,
  GameResult,
} from '../common/types';
import { PauseMenu } from '../common/PauseMenu';
import { ResultsScreen } from '../common/ResultsScreen';
import { BrainDashEngine } from './engine';
import { DEFAULT_CONFIG } from './config';
import type { BrainDashHud } from './types';
import { Hud } from './Hud';
import { QuestionOverlay } from './QuestionOverlay';
import './styles.css';

interface BrainDashProps {
  context: GameLaunchContext;
}

const INITIAL_HUD: BrainDashHud = {
  status: 'INTRO',
  lives: DEFAULT_CONFIG.livesMax,
  livesMax: DEFAULT_CONFIG.livesMax,
  distance: 0,
  score: 0,
  combo: 0,
  multiplier: 1,
  coins: 0,
  speedKmh: Math.round(DEFAULT_CONFIG.baseSpeed * 3.6),
  pickups: [],
  questionsAsked: 0,
  questionsCorrect: 0,
};

export function BrainDash({ context }: BrainDashProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const engineRef = useRef<BrainDashEngine | null>(null);
  const [hud, setHud] = useState<BrainDashHud>(INITIAL_HUD);
  const [intro, setIntro] = useState(true);
  const [result, setResult] = useState<GameResult | null>(null);
  const [runToken, setRunToken] = useState(0);
  const answersRef = useRef<AnswerEvent[]>([]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    answersRef.current = [];
    const engine = new BrainDashEngine({
      canvas,
      config: DEFAULT_CONFIG,
      questions: context.questions,
      fetchMoreQuestions: context.callbacks.onRequestExtraQuestions,
      reducedMotion: context.settings.reducedMotion,
      handlers: {
        onHudChange: (h) => setHud(h),
        onAnswer: (a) => {
          answersRef.current.push(a);
          context.callbacks.onAnswer?.(a);
        },
        onFinished: (summary) => {
          const correctness = summary.questionsAsked
            ? summary.questionsCorrect / summary.questionsAsked
            : 0;
          const xpEarned =
            summary.questionsCorrect *
            (10 +
              Math.round(
                summary.perQuestion.reduce((s, p) => s + p.difficulty, 0) /
                  Math.max(1, summary.perQuestion.length),
              ) *
                2);
          const r: GameResult = {
            gameId: 'brain-dash',
            konspektId: context.konspekt.id,
            durationMs: summary.durationMs,
            score: summary.score,
            coinsEarned: summary.coins + summary.questionsCorrect * 5,
            xpEarned,
            questionsAsked: summary.questionsAsked,
            questionsCorrect: summary.questionsCorrect,
            perQuestion: summary.perQuestion,
            highlights: highlightsFor(summary, correctness),
          };
          setResult(r);
          context.callbacks.onResult(r);
        },
      },
    });
    engineRef.current = engine;
    if (!intro) engine.start();
    return () => {
      engine.destroy();
      engineRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runToken]);

  const handleStart = useCallback(() => {
    setIntro(false);
    setTimeout(() => {
      engineRef.current?.start();
    }, 0);
  }, []);

  const handleResume = useCallback(() => {
    engineRef.current?.resume();
  }, []);
  const handlePause = useCallback(() => {
    engineRef.current?.pause();
  }, []);
  const handleExit = useCallback(() => {
    context.callbacks.onExit('user');
  }, [context.callbacks]);
  const handleRestart = useCallback(() => {
    setResult(null);
    setHud({ ...INITIAL_HUD });
    setIntro(false);
    setRunToken((t) => t + 1);
  }, []);

  const paused = hud.status === 'PAUSED';

  return (
    <div className="bd-root">
      <canvas ref={canvasRef} className="bd-canvas" />
      {!intro && !result && <Hud hud={hud} konspektTitle={context.konspekt.title} onPause={handlePause} onExit={handleExit} />}
      {!intro && !result && hud.question && <QuestionOverlay hud={hud} />}
      {intro && (
        <div className="bd-intro">
          <div className="card">
            <div className="title-1">Brain Dash</div>
            <div className="muted">
              Бесконечный раннер с вопросами по конспекту «{context.konspekt.title}».
            </div>
            <div className="bd-controls-hint">
              <span className="kbd">← / A</span>
              <span>Сменить полосу влево</span>
              <span className="kbd">→ / D</span>
              <span>Сменить полосу вправо</span>
              <span className="kbd">↑ / W / Space</span>
              <span>Прыжок</span>
              <span className="kbd">↓ / S</span>
              <span>Подкат</span>
              <span className="kbd">Esc / P</span>
              <span>Пауза</span>
            </div>
            <p className="muted" style={{ margin: 0 }}>
              Каждые ~220 метров впереди появляются <b>3 ворот</b> с вариантами ответа. Заезжайте в нужную полосу — правильный ответ даёт очки и комбо, ошибка стоит жизни.
            </p>
            <div className="row">
              <button className="btn primary" onClick={handleStart}>
                Начать забег
              </button>
              <button className="btn ghost" onClick={handleExit}>
                К конспекту
              </button>
            </div>
          </div>
        </div>
      )}
      {paused && !result && (
        <PauseMenu
          onResume={handleResume}
          onRestart={handleRestart}
          onExit={handleExit}
        />
      )}
      {result && (
        <ResultsScreen
          result={result}
          onRestart={handleRestart}
          onExit={handleExit}
        />
      )}
    </div>
  );
}

function highlightsFor(
  summary: {
    score: number;
    coins: number;
    questionsAsked: number;
    questionsCorrect: number;
    distance: number;
  },
  correctness: number,
): string[] {
  const out: string[] = [];
  if (summary.questionsCorrect >= 5) out.push('5+ верных ответов подряд во время бега');
  if (correctness >= 0.9 && summary.questionsAsked >= 3) out.push('Точность ≥ 90% — отличник!');
  if (summary.distance >= 800) out.push('Дистанция 800+ м — выносливость');
  if (summary.coins >= 30) out.push('30+ монет — собиратель');
  return out;
}
