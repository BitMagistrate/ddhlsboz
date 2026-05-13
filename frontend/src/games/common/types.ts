// Shared contracts between the host application and individual games.
// Mirrors the spec in games_spec.md section 1.2.

export interface User {
  id: string;
  displayName: string;
  avatarUrl?: string;
  level: number;
  xp: number;
  coins: number;
}

export interface Konspekt {
  id: string;
  title: string;
  subject?: string;
  topicTags?: string[];
}

export interface QuizQuestion {
  id: string;
  text: string;
  options: QuizOption[];
  correctOptionId: string;
  explanation?: string;
  difficulty: 1 | 2 | 3 | 4 | 5;
  sourceParagraphId?: string;
}

export interface QuizOption {
  id: string;
  text: string;
}

export interface GameSettings {
  soundVolume: number;
  musicVolume: number;
  reducedMotion: boolean;
  difficultyHint?: 'auto' | 'easy' | 'normal' | 'hard';
  language: 'ru' | 'en';
}

export interface AnswerEvent {
  questionId: string;
  selectedOptionId: string | null;
  correct: boolean;
  timeToAnswerMs: number;
  difficulty: number;
}

export interface GameProgressTick {
  tMs: number;
  score: number;
  health: number;
}

export interface GameResult {
  gameId: 'brain-dash';
  konspektId: string;
  durationMs: number;
  score: number;
  coinsEarned: number;
  xpEarned: number;
  questionsAsked: number;
  questionsCorrect: number;
  perQuestion: AnswerEvent[];
  highlights?: string[];
}

export interface GameCallbacks {
  onExit: (reason: 'user' | 'finished' | 'error') => void;
  onResult: (result: GameResult) => void;
  onProgressTick?: (tick: GameProgressTick) => void;
  onAnswer?: (event: AnswerEvent) => void;
  onRequestExtraQuestions?: (count: number) => Promise<QuizQuestion[]>;
}

export interface GameLaunchContext {
  user: User;
  konspekt: Konspekt;
  questions: QuizQuestion[];
  settings: GameSettings;
  callbacks: GameCallbacks;
}

export type GameId = 'brain-dash';
