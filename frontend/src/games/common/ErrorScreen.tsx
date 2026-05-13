import './common.css';

interface ErrorScreenProps {
  message?: string;
  onRetry: () => void;
  onExit: () => void;
}

export function ErrorScreen({ message, onRetry, onExit }: ErrorScreenProps) {
  return (
    <div className="overlay-root">
      <div className="card">
        <div className="title-2">Не удалось загрузить вопросы</div>
        <p className="muted" style={{ margin: 0 }}>
          {message ??
            'Что-то пошло не так при подготовке раунда. Проверьте соединение и попробуйте ещё раз.'}
        </p>
        <div className="row">
          <button className="btn primary" onClick={onRetry}>
            Попробовать снова
          </button>
          <button className="btn ghost" onClick={onExit}>
            К конспекту
          </button>
        </div>
      </div>
    </div>
  );
}
