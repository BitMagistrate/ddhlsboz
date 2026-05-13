import type { BrainDashHud } from './types';
import './styles.css';

interface HudProps {
  hud: BrainDashHud;
  konspektTitle: string;
  onPause: () => void;
  onExit: () => void;
}

export function Hud({ hud, konspektTitle, onPause, onExit }: HudProps) {
  const livesMax = Math.max(hud.lives, hud.livesMax ?? 3);
  return (
    <>
      <div className="bd-hud bd-hud-top">
        <div className="bd-hud-block">
          <div className="bd-hud-label">Жизни</div>
          <div className="bd-hud-hearts">
            {Array.from({ length: livesMax }).map((_, i) => (
              <span
                key={i}
                className={`bd-heart ${i < hud.lives ? 'on' : 'off'}`}
                aria-hidden
              />
            ))}
          </div>
        </div>
        <div className="bd-hud-block">
          <div className="bd-hud-label">Счёт</div>
          <div className="bd-hud-value">{hud.score.toLocaleString('ru-RU')}</div>
        </div>
        <div className="bd-hud-block">
          <div className="bd-hud-label">Монеты</div>
          <div className="bd-hud-value">⦿ {hud.coins}</div>
        </div>
        <div className="bd-hud-block">
          <div className="bd-hud-label">Дистанция</div>
          <div className="bd-hud-value">{hud.distance} м</div>
        </div>
        <div className="bd-hud-block">
          <div className="bd-hud-label">Скорость</div>
          <div className="bd-hud-value">{hud.speedKmh} км/ч</div>
        </div>
        {hud.combo > 1 && (
          <div className="bd-hud-block bd-combo">
            <div className="bd-hud-label">Комбо</div>
            <div className="bd-hud-value">×{hud.combo}</div>
          </div>
        )}
        {hud.multiplier > 1 && (
          <div className="bd-hud-block bd-mult">
            <div className="bd-hud-label">Множитель</div>
            <div className="bd-hud-value">×{hud.multiplier}</div>
          </div>
        )}
        <div className="bd-hud-spacer" />
        <button className="btn ghost bd-pause-btn" onClick={onPause}>
          Пауза
        </button>
        <button className="btn ghost bd-exit-btn" onClick={onExit}>
          К конспекту
        </button>
      </div>

      <div className="bd-konspekt-tag">{konspektTitle}</div>

      {hud.pickups.length > 0 && (
        <div className="bd-pickup-tray">
          {hud.pickups.map((p, i) => (
            <span key={i} className={`bd-pickup-pill bd-pickup-${p.kind}`}>
              {labelForPickup(p.kind)} · {Math.ceil(p.remainingMs / 1000)}s
            </span>
          ))}
        </div>
      )}

      {hud.lastExplanation && (
        <div className="bd-explanation">{hud.lastExplanation}</div>
      )}

      {hud.countdown !== undefined && (
        <div className="bd-countdown">
          {hud.countdown > 0 ? hud.countdown : 'GO!'}
        </div>
      )}
    </>
  );
}

function labelForPickup(kind: BrainDashHud['pickups'][number]['kind']): string {
  switch (kind) {
    case 'shield':
      return 'Щит';
    case 'magnet':
      return 'Магнит';
    case 'x2':
      return 'x2';
    case 'boost':
      return 'Ускорение';
  }
}
