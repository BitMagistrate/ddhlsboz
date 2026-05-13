import type { BrainDashHud } from './types';
import './styles.css';

interface QuestionOverlayProps {
  hud: BrainDashHud;
}

const LANE_LABELS = ['Левая полоса', 'Центр', 'Правая полоса'];

export function QuestionOverlay({ hud }: QuestionOverlayProps) {
  if (!hud.question) return null;
  const q = hud.question;
  return (
    <div className="bd-question-bar">
      <div className="bd-question-text">{q.question.text}</div>
      <div className="bd-question-options">
        {[0, 1, 2].map((lane) => {
          const optId = q.laneToOptionId[lane as 0 | 1 | 2];
          const opt = q.question.options.find((o) => o.id === optId);
          return (
            <div key={lane} className="bd-question-option">
              <span className="bd-question-lane">{LANE_LABELS[lane]}</span>
              <span className="bd-question-opt-text">{opt?.text ?? '—'}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
