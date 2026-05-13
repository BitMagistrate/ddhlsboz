import type { QuizQuestion } from '../common/types';

export type BrainDashStatus =
  | 'INTRO'
  | 'COUNTDOWN'
  | 'RUNNING'
  | 'HIT'
  | 'PAUSED'
  | 'GAME_OVER'
  | 'RESULTS';

export interface ActiveQuestion {
  question: QuizQuestion;
  laneToOptionId: Record<0 | 1 | 2, string>;
  spawnedAt: number;
  resolveAtDistance: number;
  resolved: boolean;
}

export interface ActivePickup {
  kind: 'magnet' | 'shield' | 'x2' | 'boost';
  remainingMs: number;
}

export interface BrainDashHud {
  status: BrainDashStatus;
  lives: number;
  livesMax: number;
  distance: number;
  score: number;
  combo: number;
  multiplier: number;
  coins: number;
  speedKmh: number;
  countdown?: number;
  question?: ActiveQuestion;
  lastExplanation?: string;
  pickups: ActivePickup[];
  questionsAsked: number;
  questionsCorrect: number;
}
