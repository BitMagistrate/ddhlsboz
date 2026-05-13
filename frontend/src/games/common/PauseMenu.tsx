import './common.css';

interface PauseMenuProps {
  onResume: () => void;
  onRestart?: () => void;
  onExit: () => void;
}

export function PauseMenu({ onResume, onRestart, onExit }: PauseMenuProps) {
  return (
    <div className="overlay-root">
      <div className="card">
        <div className="title-1">Пауза</div>
        <p className="muted" style={{ margin: 0 }}>
          Нажмите <span className="kbd">Esc</span> чтобы продолжить.
        </p>
        <div className="row">
          <button className="btn primary" onClick={onResume}>
            Продолжить
          </button>
          {onRestart && (
            <button className="btn" onClick={onRestart}>
              Начать заново
            </button>
          )}
          <button className="btn ghost" onClick={onExit}>
            К конспекту
          </button>
        </div>
      </div>
    </div>
  );
}
