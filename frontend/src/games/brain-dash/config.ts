export interface BrainDashConfig {
  laneCount: 3;
  laneWidth: number;
  baseSpeed: number;
  speedRamp: number;
  maxSpeed: number;
  livesMax: number;
  worldChunkLength: number;
  obstacleEverySec: number;
  coinEverySec: number;
  questionEveryMeters: number;
  questionResolveAfterMeters: number;
  questionsPerRound: number;
  laneSwitchSpeed: number;
  jumpHeight: number;
  jumpDuration: number;
  slideDuration: number;
}

export const DEFAULT_CONFIG: BrainDashConfig = {
  laneCount: 3,
  laneWidth: 2,
  baseSpeed: 10,
  speedRamp: 0.5,
  maxSpeed: 22,
  livesMax: 4,
  worldChunkLength: 40,
  obstacleEverySec: 2.4,
  coinEverySec: 0.55,
  questionEveryMeters: 90,
  questionResolveAfterMeters: 60,
  questionsPerRound: 3,
  laneSwitchSpeed: 9,
  jumpHeight: 1.6,
  jumpDuration: 0.7,
  slideDuration: 0.5,
};
