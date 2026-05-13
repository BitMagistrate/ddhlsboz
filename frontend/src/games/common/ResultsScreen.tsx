import type { GameResult } from './types';
import './common.css';

interface ResultsScreenProps {
  result: GameResult;
  onRestart: () => void;
  onExit: () => void;
}

function formatDuration(ms: number): string {
  const total = Math.round(ms / 1000);
  const m = Math.floor(total / 60);
  const s = total - m * 60;
  return `${m}:${s.toString().padStart(2, '0')}`;
}

export function ResultsScreen({ result, onRestart, onExit }: ResultsScreenProps) {
  const accuracy =
    result.questionsAsked > 0
      ? Math.round((result.questionsCorrect / result.questionsAsked) * 100)
      : 0;
  return (
    <div className="overlay-root">
      <div className="card wide">
        <div className="row between">
          <div className="title-1">Итоги раунда</div>
          <div className="muted">Brain Dash</div>
        </div>

        <div className="stat-grid">
          <div className="stat">
            <span className="label">Счёт</span>
            <span className="value">{result.score.toLocaleString('ru-RU')}</span>
          </div>
          <div className="stat">
            <span className="label">Время</span>
            <span className="value">{formatDuration(result.durationMs)}</span>
          </div>
          <div className="stat">
            <span className="label">Правильно</span>
            <span className="value">
              {result.questionsCorrect}/{result.questionsAsked} ({accuracy}%)
            </span>
          </div>
          <div className="stat">
            <span className="label">Монеты / XP</span>
            <span className="value">
              +{result.coinsEarned} / +{result.xpEarned}
            </span>
          </div>
        </div>

        {result.highlights && result.highlights.length > 0 && (
          <div>
            <div className="muted" style={{ marginBottom: 6 }}>
              Достижения раунда:
            </div>
            <ul style={{ margin: 0, paddingLeft: 18 }}>
              {result.highlights.map((h) => (
                <li key={h}>{h}</li>
              ))}
            </ul>
          </div>
        )}

        <div className="row">
          <button className="btn primary" onClick={onRestart}>
            Ещё раз
          </button>
          <button className="btn ghost" onClick={onExit}>
            К конспекту
          </button>
        </div>
      </div>
    </div>
  );
}
