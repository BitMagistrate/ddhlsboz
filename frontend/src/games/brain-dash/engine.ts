import * as THREE from 'three';
import type { AnswerEvent, QuizQuestion } from '../common/types';
import type { BrainDashConfig } from './config';
import type {
  ActivePickup,
  ActiveQuestion,
  BrainDashHud,
  BrainDashStatus,
} from './types';

const FORWARD = -1; // forward direction along z

interface ObstacleObj {
  group: THREE.Group;
  kind: 'car' | 'cone' | 'barrier';
  lane: number;
  // For cars only — wheel groups for rotation animation
  wheels?: THREE.Object3D[];
  // For cars only — brake-light intensity flicker target
  brakeMats?: THREE.MeshStandardMaterial[];
}

interface CoinObj {
  mesh: THREE.Mesh;
  lane: number;
}

interface PickupObj {
  mesh: THREE.Mesh;
  lane: number;
  kind: ActivePickup['kind'];
}

interface GatePlate {
  mesh: THREE.Mesh;
  lane: 0 | 1 | 2;
  optionId: string;
  texture: THREE.CanvasTexture;
}

interface ActiveGate {
  questionId: string;
  question: QuizQuestion;
  zTrigger: number;
  laneToOptionId: Record<0 | 1 | 2, string>;
  plates: GatePlate[];
  banner?: { mesh: THREE.Mesh; texture: THREE.CanvasTexture };
  arch?: THREE.Group;
  resolved: boolean;
  spawnedAtMs: number;
  spawnedAtDistance: number;
}

interface ParticleBurst {
  group: THREE.Group;
  vy: number[];
  vx: number[];
  vz: number[];
  spin: number[];
  ageMs: number;
  lifeMs: number;
  meshes: THREE.Mesh[];
  materials: THREE.Material[];
}

export interface BrainDashEngineHandlers {
  onHudChange: (hud: BrainDashHud) => void;
  onAnswer: (event: AnswerEvent) => void;
  onFinished: (summary: {
    score: number;
    coins: number;
    questionsAsked: number;
    questionsCorrect: number;
    distance: number;
    durationMs: number;
    perQuestion: AnswerEvent[];
  }) => void;
}

export interface BrainDashEngineOptions {
  canvas: HTMLCanvasElement;
  questions: QuizQuestion[];
  fetchMoreQuestions?: (n: number) => Promise<QuizQuestion[]>;
  config: BrainDashConfig;
  handlers: BrainDashEngineHandlers;
  reducedMotion: boolean;
}

type Status = BrainDashStatus;

const LANE_OFFSETS = (cfg: BrainDashConfig) => [-cfg.laneWidth, 0, cfg.laneWidth];

const CAR_PALETTE: { body: number; accent: number }[] = [
  { body: 0xff5470, accent: 0xffd34a }, // red+gold
  { body: 0x6c5ce7, accent: 0xa6e1ff }, // purple+ice
  { body: 0x00b894, accent: 0xfff097 }, // green+lemon
  { body: 0xffb547, accent: 0x1c2742 }, // amber+dark
  { body: 0xeeeeee, accent: 0xff5470 }, // white+red
  { body: 0x1c2742, accent: 0x6c5ce7 }, // dark navy+purple
  { body: 0x2dd4bf, accent: 0xfff097 }, // teal+lemon
  { body: 0xff79c6, accent: 0x281e6e }, // pink+purple
];

type CarKind = 'sedan' | 'suv' | 'pickup' | 'sports' | 'truck';

export class BrainDashEngine {
  private readonly cfg: BrainDashConfig;
  private readonly canvas: HTMLCanvasElement;
  private readonly handlers: BrainDashEngineHandlers;
  private readonly reducedMotion: boolean;

  private renderer!: THREE.WebGLRenderer;
  private scene!: THREE.Scene;
  private camera!: THREE.PerspectiveCamera;

  private playerGroup!: THREE.Group;
  private playerTorso!: THREE.Mesh;
  private playerHead!: THREE.Mesh;
  private playerLeftArm!: THREE.Group;
  private playerRightArm!: THREE.Group;
  private playerLeftLeg!: THREE.Group;
  private playerRightLeg!: THREE.Group;
  private playerShadow!: THREE.Mesh;
  private lanePositions: number[];

  // ground & decor
  private groundTiles: THREE.Mesh[] = [];
  private neonStripes: THREE.Mesh[] = [];

  // moving objects
  private obstacles: ObstacleObj[] = [];
  private coins: CoinObj[] = [];
  private pickups: PickupObj[] = [];
  private gates: ActiveGate[] = [];

  // static (world-anchored) roadside decor that scrolls with the player
  private streetLamps: { group: THREE.Group; bulb: THREE.PointLight }[] = [];
  private billboards: THREE.Group[] = [];
  private buildings: THREE.Group[] = [];
  private roadsideTrees: THREE.Group[] = [];

  // active particle bursts (e.g. correct-answer confetti)
  private particles: ParticleBurst[] = [];

  // shared materials / geometries
  private mats = {
    coin: new THREE.MeshStandardMaterial({ color: 0xffd34a, roughness: 0.3, metalness: 0.7, emissive: 0x553300, emissiveIntensity: 0.6 }),
    pickupShield: new THREE.MeshStandardMaterial({ color: 0x00b894, emissive: 0x004436, emissiveIntensity: 0.5 }),
    pickupMagnet: new THREE.MeshStandardMaterial({ color: 0x6c5ce7, emissive: 0x2a2470, emissiveIntensity: 0.5 }),
    pickupX2: new THREE.MeshStandardMaterial({ color: 0xff79c6, emissive: 0x5a1e44, emissiveIntensity: 0.5 }),
    pickupBoost: new THREE.MeshStandardMaterial({ color: 0x4cd964, emissive: 0x1b5a25, emissiveIntensity: 0.5 }),
    ground: new THREE.MeshStandardMaterial({ color: 0x161f36, roughness: 0.9, metalness: 0 }),
    groundAlt: new THREE.MeshStandardMaterial({ color: 0x101728, roughness: 0.95, metalness: 0 }),
    stripeWhite: new THREE.MeshBasicMaterial({ color: 0xf6f7fb }),
    stripeAccent: new THREE.MeshBasicMaterial({ color: 0x6c5ce7 }),
    stripeAccent2: new THREE.MeshBasicMaterial({ color: 0x00b894 }),
    skirt: new THREE.MeshStandardMaterial({ color: 0x2a3a66, roughness: 0.9 }),
    cone: new THREE.MeshStandardMaterial({ color: 0xff7a00, emissive: 0x441f00, emissiveIntensity: 0.4 }),
    coneStripe: new THREE.MeshBasicMaterial({ color: 0xffffff }),
    wheel: new THREE.MeshStandardMaterial({ color: 0x111111, roughness: 0.9 }),
    glass: new THREE.MeshStandardMaterial({
      color: 0x9bd6ff,
      roughness: 0.05,
      metalness: 0.4,
      transparent: true,
      opacity: 0.55,
    }),
    headlight: new THREE.MeshStandardMaterial({ color: 0xfff7c2, emissive: 0xfff7c2, emissiveIntensity: 1.4 }),
    taillight: new THREE.MeshStandardMaterial({ color: 0xff3a3a, emissive: 0xff3a3a, emissiveIntensity: 1.2 }),
    playerBody: new THREE.MeshStandardMaterial({ color: 0x6c5ce7, roughness: 0.45, metalness: 0.2 }),
    playerLimb: new THREE.MeshStandardMaterial({ color: 0x4836b8, roughness: 0.5, metalness: 0.2 }),
    playerSkin: new THREE.MeshStandardMaterial({ color: 0xf5d6c6, roughness: 0.7 }),
    playerHit: new THREE.MeshStandardMaterial({ color: 0xff5470, roughness: 0.45 }),
    shadow: new THREE.MeshBasicMaterial({ color: 0x000000, transparent: true, opacity: 0.35 }),
  };

  private geos = {
    coin: new THREE.CylinderGeometry(0.35, 0.35, 0.08, 18),
    pickup: new THREE.IcosahedronGeometry(0.4, 0),
    cone: new THREE.ConeGeometry(0.35, 0.9, 12),
    coneStripe: new THREE.CylinderGeometry(0.32, 0.32, 0.1, 12, 1, true),
    barrier: new THREE.BoxGeometry(1.6, 0.7, 0.5),
    carWindshield: new THREE.PlaneGeometry(0.9, 0.5),
    carWheel: new THREE.CylinderGeometry(0.24, 0.24, 0.2, 18),
    carWheelHub: new THREE.CylinderGeometry(0.1, 0.1, 0.22, 10),
    carHeadlight: new THREE.SphereGeometry(0.08, 8, 8),
    torso: new THREE.BoxGeometry(0.5, 0.65, 0.35),
    head: new THREE.SphereGeometry(0.28, 18, 16),
    armUpper: new THREE.CapsuleGeometry(0.09, 0.35, 4, 8),
    legUpper: new THREE.CapsuleGeometry(0.11, 0.45, 4, 8),
    hand: new THREE.SphereGeometry(0.1, 8, 8),
    foot: new THREE.BoxGeometry(0.18, 0.1, 0.32),
    eye: new THREE.SphereGeometry(0.045, 8, 6),
    shadow: new THREE.CircleGeometry(0.55, 24),
    ground: new THREE.PlaneGeometry(10, 1),
    gatePlate: new THREE.BoxGeometry(1.85, 1.5, 0.14),
    gateBanner: new THREE.PlaneGeometry(8.6, 1.4),
    confetti: new THREE.PlaneGeometry(0.12, 0.18),
    spark: new THREE.SphereGeometry(0.06, 6, 6),
    lampPole: new THREE.CylinderGeometry(0.08, 0.1, 4.4, 8),
    lampHead: new THREE.SphereGeometry(0.22, 12, 10),
    billboardPole: new THREE.CylinderGeometry(0.1, 0.12, 3.4, 8),
    billboardPanel: new THREE.BoxGeometry(3.2, 1.8, 0.16),
    treeTrunk: new THREE.CylinderGeometry(0.15, 0.22, 1.6, 8),
    treeCrown: new THREE.IcosahedronGeometry(0.95, 0),
    bldgFloor: new THREE.BoxGeometry(2.4, 1.0, 2.4),
    archPillar: new THREE.BoxGeometry(0.35, 4.2, 0.35),
    archTop: new THREE.BoxGeometry(8.6, 0.45, 0.5),
  };

  // player state
  private playerLane = 1;
  private playerTargetX = 0;
  private playerY = 0;
  private playerVY = 0;
  private playerState: 'running' | 'jumping' | 'sliding' | 'hit' | 'dead' = 'running';
  private playerStateTimer = 0;
  private hitInvulnTimer = 0;

  // game state
  private status: Status = 'INTRO';
  private elapsedMs = 0;
  private startedAtMs = 0;
  private distance = 0;
  private lives = 0;
  private score = 0;
  private coinsCollected = 0;
  private combo = 0;
  private multiplier = 1;
  private activePickups: ActivePickup[] = [];
  private nextQuestionAtDistance = 0;
  private questionPool: QuizQuestion[];
  private questionCursor = 0;
  private currentQuestion: ActiveQuestion | undefined;
  private answers: AnswerEvent[] = [];
  private lastExplanation: string | undefined;
  private lastExplanationTimer = 0;
  private fetchMoreQuestions: BrainDashEngineOptions['fetchMoreQuestions'];
  private prefetching = false;

  // spawn timers
  private obstacleTimer = 3.5;
  private coinTimer = 1.5;
  private pickupTimer = 6;

  // countdown
  private countdownTimer = 0;

  // loop
  private rafId: number | null = null;
  private lastTimeMs = 0;
  private fixedDt = 1 / 60;
  private accumulatorMs = 0;
  private destroyed = false;

  // input
  private keyHandler: (e: KeyboardEvent) => void;
  private blurHandler: () => void;
  private resizeObserver?: ResizeObserver;
  private touchStart: { x: number; y: number; t: number } | null = null;
  private touchEndHandler?: (e: TouchEvent) => void;
  private touchStartHandler?: (e: TouchEvent) => void;

  // hud
  private lastHud: BrainDashHud | null = null;

  constructor(opts: BrainDashEngineOptions) {
    this.canvas = opts.canvas;
    this.cfg = opts.config;
    this.handlers = opts.handlers;
    this.reducedMotion = opts.reducedMotion;
    this.questionPool = [...opts.questions];
    this.fetchMoreQuestions = opts.fetchMoreQuestions;
    this.lives = this.cfg.livesMax;
    this.lanePositions = LANE_OFFSETS(this.cfg);
    this.nextQuestionAtDistance = this.cfg.questionEveryMeters * 0.5;
    this.keyHandler = this.onKey.bind(this);
    this.blurHandler = () => {
      if (this.status === 'RUNNING') {
        this.setStatus('PAUSED');
      }
    };

    this.initThree();
    this.initWorld();
    this.bindInput();
    this.emitHud();
  }

  // ----- public -----

  start() {
    if (this.destroyed) return;
    this.startedAtMs = performance.now();
    this.lastTimeMs = this.startedAtMs;
    this.countdownTimer = 3;
    this.setStatus('COUNTDOWN');
    this.tick();
  }
  pause() {
    if (this.status === 'RUNNING' || this.status === 'COUNTDOWN') {
      this.setStatus('PAUSED');
    }
  }
  resume() {
    if (this.status === 'PAUSED') {
      this.setStatus('RUNNING');
      this.lastTimeMs = performance.now();
    }
  }
  togglePause() {
    if (this.status === 'PAUSED') this.resume();
    else this.pause();
  }
  destroy() {
    this.destroyed = true;
    if (this.rafId !== null) cancelAnimationFrame(this.rafId);
    window.removeEventListener('keydown', this.keyHandler);
    window.removeEventListener('blur', this.blurHandler);
    if (this.touchStartHandler)
      this.canvas.removeEventListener('touchstart', this.touchStartHandler);
    if (this.touchEndHandler)
      this.canvas.removeEventListener('touchend', this.touchEndHandler);
    this.resizeObserver?.disconnect();
    this.renderer.dispose();
    for (const g of Object.values(this.geos)) g.dispose();
    for (const m of Object.values(this.mats)) {
      if (m instanceof THREE.Material) m.dispose();
    }
    for (const g of this.gates) {
      for (const p of g.plates) {
        (p.mesh.material as THREE.Material).dispose();
        p.texture.dispose();
      }
      if (g.banner) {
        (g.banner.mesh.material as THREE.Material).dispose();
        g.banner.texture.dispose();
      }
    }
  }
  endNow(reason: 'user' | 'finished') {
    if (reason === 'user' || reason === 'finished') {
      this.finish();
    }
  }

  // ----- init -----

  private initThree() {
    this.renderer = new THREE.WebGLRenderer({ canvas: this.canvas, antialias: true });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.renderer.shadowMap.enabled = !this.reducedMotion;
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 1.05;

    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(0x0d142a);
    this.scene.fog = new THREE.FogExp2(0x0d142a, 0.018);

    this.camera = new THREE.PerspectiveCamera(64, 1, 0.1, 200);
    this.camera.position.set(0, 4.5, 8);
    this.camera.lookAt(0, 1, -4);

    // Lights
    const hemi = new THREE.HemisphereLight(0x6c5ce7, 0x0a0f1c, 0.7);
    this.scene.add(hemi);

    const dir = new THREE.DirectionalLight(0xfff097, 1.05);
    dir.position.set(-6, 12, 4);
    dir.castShadow = !this.reducedMotion;
    if (dir.castShadow) {
      dir.shadow.mapSize.set(1024, 1024);
      dir.shadow.camera.left = -8;
      dir.shadow.camera.right = 8;
      dir.shadow.camera.top = 8;
      dir.shadow.camera.bottom = -8;
      dir.shadow.camera.near = 1;
      dir.shadow.camera.far = 40;
    }
    this.scene.add(dir);

    const rimL = new THREE.PointLight(0x6c5ce7, 2.0, 22);
    rimL.position.set(-5, 4, -8);
    this.scene.add(rimL);
    const rimR = new THREE.PointLight(0x00b894, 1.6, 22);
    rimR.position.set(5, 4, -12);
    this.scene.add(rimR);

    // Sky gradient via large background plane behind the runner
    const skyGeo = new THREE.PlaneGeometry(140, 70);
    const skyCanvas = document.createElement('canvas');
    skyCanvas.width = 256;
    skyCanvas.height = 256;
    const ctx = skyCanvas.getContext('2d')!;
    const grad = ctx.createLinearGradient(0, 0, 0, skyCanvas.height);
    grad.addColorStop(0, '#1c0d3a');
    grad.addColorStop(0.55, '#3c1a59');
    grad.addColorStop(0.85, '#ff5470');
    grad.addColorStop(1, '#ffd34a');
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, skyCanvas.width, skyCanvas.height);
    const skyTex = new THREE.CanvasTexture(skyCanvas);
    const skyMat = new THREE.MeshBasicMaterial({ map: skyTex, fog: false });
    const sky = new THREE.Mesh(skyGeo, skyMat);
    sky.position.set(0, 12, -80);
    this.scene.add(sky);

    this.resize();
    this.resizeObserver = new ResizeObserver(() => this.resize());
    this.resizeObserver.observe(this.canvas.parentElement ?? this.canvas);
  }

  private initWorld() {
    this.buildPlayer();
    this.buildRoad();
    this.buildRoadside();
  }

  private buildRoadside() {
    // Generate a long ribbon of decor on both sides that we recycle as it
    // passes behind the player (handled in cullBehind).
    const ROADSIDE_X = this.cfg.laneWidth * 2.4;
    const tileLen = this.cfg.worldChunkLength;
    const numChunks = 16;

    // Street lamps every ~22 m, alternating sides.
    for (let i = 0; i < numChunks * 2; i++) {
      const side: -1 | 1 = i % 2 === 0 ? -1 : 1;
      const { group, bulb } = this.buildStreetLamp(side);
      group.position.set(side * ROADSIDE_X, 0, -i * 22 + 8);
      this.scene.add(group);
      this.streetLamps.push({ group, bulb });
    }

    // Billboards every ~110 m, alternating sides.
    const BILLBOARDS = [
      'Brain Dash',
      'Учись играя',
      'Мнохиамыг',
      'Brain Dash',
      '+10 за верный ответ',
      'Беги быстрее!',
      'Знание — сила',
      'Конспект → Игра',
    ];
    for (let i = 0; i < 12; i++) {
      const side: -1 | 1 = i % 2 === 0 ? 1 : -1;
      const text = BILLBOARDS[i % BILLBOARDS.length];
      const b = this.buildBillboard(side, text);
      b.position.set(side * (ROADSIDE_X + 1.4), 0, -i * 110 + 30);
      b.rotation.y = side > 0 ? -Math.PI / 12 : Math.PI / 12;
      this.scene.add(b);
      this.billboards.push(b);
    }

    // Mid-range trees scattered across the roadside band.
    for (let i = 0; i < 36; i++) {
      const side: -1 | 1 = Math.random() < 0.5 ? -1 : 1;
      const t = this.buildRoadsideTree();
      const xJitter = 0.7 + Math.random() * 2.5;
      const zJitter = Math.random() * tileLen * numChunks;
      t.position.set(side * (ROADSIDE_X + xJitter), 0, -zJitter + 8);
      this.scene.add(t);
      this.roadsideTrees.push(t);
    }

    // Distant skyline buildings — kept far from the road so the player
    // reads them as background.
    for (let i = 0; i < 20; i++) {
      const side: -1 | 1 = Math.random() < 0.5 ? -1 : 1;
      const b = this.buildBuilding();
      const xJitter = 4 + Math.random() * 3;
      const zJitter = Math.random() * tileLen * numChunks;
      b.position.set(side * (ROADSIDE_X + xJitter), 0, -zJitter + 4);
      b.rotation.y = Math.random() * 0.4 - 0.2;
      this.scene.add(b);
      this.buildings.push(b);
    }
  }

  private buildPlayer() {
    const group = new THREE.Group();
    this.playerTorso = new THREE.Mesh(this.geos.torso, this.mats.playerBody);
    this.playerTorso.position.y = 0.95;
    this.playerTorso.castShadow = !this.reducedMotion;
    group.add(this.playerTorso);

    this.playerHead = new THREE.Mesh(this.geos.head, this.mats.playerSkin);
    this.playerHead.position.y = 1.55;
    this.playerHead.castShadow = !this.reducedMotion;
    group.add(this.playerHead);

    // Hair / hood — small cap to make head more humanoid
    const hoodGeo = new THREE.SphereGeometry(0.32, 18, 12, 0, Math.PI * 2, 0, Math.PI / 2.1);
    const hoodMat = new THREE.MeshStandardMaterial({ color: 0x281e6e, roughness: 0.6 });
    const hood = new THREE.Mesh(hoodGeo, hoodMat);
    hood.position.y = 1.6;
    hood.castShadow = !this.reducedMotion;
    group.add(hood);

    // Face: two small eyes so the avatar reads as a character at distance.
    const eyeL = new THREE.Mesh(
      this.geos.eye,
      new THREE.MeshStandardMaterial({ color: 0x0e1530 }),
    );
    eyeL.position.set(-0.09, 1.6, 0.24);
    this.playerHead.add(eyeL);
    const eyeR = new THREE.Mesh(
      this.geos.eye,
      new THREE.MeshStandardMaterial({ color: 0x0e1530 }),
    );
    eyeR.position.set(0.09, 1.6, 0.24);
    this.playerHead.add(eyeR);

    // Arms: pivot at shoulder, with a small hand at the tip
    this.playerLeftArm = makeLimb(this.geos.armUpper, this.mats.playerLimb, 0.18);
    this.playerLeftArm.position.set(-0.3, 1.2, 0);
    const handL = new THREE.Mesh(this.geos.hand, this.mats.playerSkin);
    handL.position.y = -0.44;
    this.playerLeftArm.add(handL);
    group.add(this.playerLeftArm);
    this.playerRightArm = makeLimb(this.geos.armUpper, this.mats.playerLimb, 0.18);
    this.playerRightArm.position.set(0.3, 1.2, 0);
    const handR = new THREE.Mesh(this.geos.hand, this.mats.playerSkin);
    handR.position.y = -0.44;
    this.playerRightArm.add(handR);
    group.add(this.playerRightArm);

    // Legs: pivot at hip, with a small sneaker at the tip
    this.playerLeftLeg = makeLimb(this.geos.legUpper, this.mats.playerLimb, 0.24);
    this.playerLeftLeg.position.set(-0.15, 0.65, 0);
    const footL = new THREE.Mesh(
      this.geos.foot,
      new THREE.MeshStandardMaterial({ color: 0xeeeeee, roughness: 0.6 }),
    );
    footL.position.set(0, -0.6, 0.06);
    this.playerLeftLeg.add(footL);
    group.add(this.playerLeftLeg);
    this.playerRightLeg = makeLimb(this.geos.legUpper, this.mats.playerLimb, 0.24);
    this.playerRightLeg.position.set(0.15, 0.65, 0);
    const footR = new THREE.Mesh(
      this.geos.foot,
      new THREE.MeshStandardMaterial({ color: 0xeeeeee, roughness: 0.6 }),
    );
    footR.position.set(0, -0.6, 0.06);
    this.playerRightLeg.add(footR);
    group.add(this.playerRightLeg);

    this.playerShadow = new THREE.Mesh(this.geos.shadow, this.mats.shadow);
    this.playerShadow.rotation.x = -Math.PI / 2;
    this.playerShadow.position.y = 0.02;
    group.add(this.playerShadow);

    group.position.set(0, 0, 0);
    this.scene.add(group);
    this.playerGroup = group;
  }

  private buildRoad() {
    const tileLen = this.cfg.worldChunkLength;
    const numTiles = 8;
    for (let i = 0; i < numTiles; i++) {
      const g = new THREE.PlaneGeometry(this.cfg.laneWidth * 3 + 6, tileLen);
      const mat = i % 2 === 0 ? this.mats.ground : this.mats.groundAlt;
      const mesh = new THREE.Mesh(g, mat);
      mesh.rotation.x = -Math.PI / 2;
      mesh.position.z = -i * tileLen + tileLen / 2;
      mesh.receiveShadow = true;
      this.scene.add(mesh);
      this.groundTiles.push(mesh);
    }

    // Lane stripes
    for (let lane = 0; lane <= 1; lane++) {
      const x = -this.cfg.laneWidth / 2 + lane * this.cfg.laneWidth;
      for (let i = 0; i < 30; i++) {
        const sg = new THREE.PlaneGeometry(0.14, 1.5);
        const stripe = new THREE.Mesh(sg, this.mats.stripeWhite);
        stripe.rotation.x = -Math.PI / 2;
        stripe.position.set(x, 0.03, -i * 3 + 6);
        this.scene.add(stripe);
        this.neonStripes.push(stripe);
      }
    }

    // Neon side rails (animated colour)
    for (const side of [-1, 1]) {
      for (let i = 0; i < 30; i++) {
        const g = new THREE.PlaneGeometry(0.18, 2.0);
        const mat = i % 2 === 0 ? this.mats.stripeAccent : this.mats.stripeAccent2;
        const stripe = new THREE.Mesh(g, mat);
        stripe.rotation.x = -Math.PI / 2;
        stripe.position.set(side * (this.cfg.laneWidth * 1.65), 0.06, -i * 3 + 6);
        this.scene.add(stripe);
        this.neonStripes.push(stripe);
      }
    }

    // Side curbs
    for (const side of [-1, 1]) {
      const skirtGeo = new THREE.BoxGeometry(0.5, 0.4, tileLen * numTiles);
      const skirt = new THREE.Mesh(skirtGeo, this.mats.skirt);
      skirt.position.set(
        side * (this.cfg.laneWidth * 1.85),
        0.2,
        -tileLen * numTiles * 0.5 + tileLen / 2,
      );
      this.scene.add(skirt);
    }
  }

  private buildCar(): THREE.Group {
    // Pick a varied silhouette per spawn so the road feels populated.
    const kinds: CarKind[] = ['sedan', 'suv', 'pickup', 'sports', 'truck'];
    const kind = kinds[Math.floor(Math.random() * kinds.length)];
    return this.buildCarOfKind(kind);
  }

  private buildCarOfKind(kind: CarKind): THREE.Group {
    const palette = CAR_PALETTE[Math.floor(Math.random() * CAR_PALETTE.length)];
    const group = new THREE.Group();
    const bodyMat = new THREE.MeshStandardMaterial({
      color: palette.body,
      roughness: 0.38,
      metalness: 0.65,
      emissive: 0x000000,
    });
    const accentMat = new THREE.MeshStandardMaterial({
      color: palette.accent,
      roughness: 0.5,
      metalness: 0.3,
    });
    const trimMat = new THREE.MeshStandardMaterial({
      color: 0x12182a,
      roughness: 0.6,
      metalness: 0.3,
    });

    // Per-kind dimensions and silhouette.
    let bodyW: number;
    let bodyH: number;
    let bodyL: number;
    let cabinW: number;
    let cabinH: number;
    let cabinL: number;
    let cabinZ: number;
    let wheelbase: number;
    let wheelTrack: number;
    let bodyY: number;
    let cabinY: number;
    let extra: 'pickup-bed' | 'spoiler' | 'truck-cargo' | null = null;
    switch (kind) {
      case 'sedan':
        bodyW = 1.1; bodyH = 0.45; bodyL = 2.1;
        cabinW = 0.95; cabinH = 0.55; cabinL = 1.0;
        cabinZ = -0.05; wheelbase = 0.75; wheelTrack = 0.55;
        bodyY = 0.45; cabinY = 0.88;
        break;
      case 'suv':
        bodyW = 1.2; bodyH = 0.6; bodyL = 2.0;
        cabinW = 1.05; cabinH = 0.75; cabinL = 1.25;
        cabinZ = -0.1; wheelbase = 0.7; wheelTrack = 0.6;
        bodyY = 0.52; cabinY = 1.12;
        break;
      case 'pickup':
        bodyW = 1.15; bodyH = 0.5; bodyL = 2.4;
        cabinW = 1.0; cabinH = 0.65; cabinL = 0.95;
        cabinZ = 0.45; wheelbase = 0.85; wheelTrack = 0.58;
        bodyY = 0.5; cabinY = 1.05;
        extra = 'pickup-bed';
        break;
      case 'sports':
        bodyW = 1.05; bodyH = 0.35; bodyL = 2.2;
        cabinW = 0.85; cabinH = 0.42; cabinL = 0.9;
        cabinZ = 0.05; wheelbase = 0.8; wheelTrack = 0.55;
        bodyY = 0.4; cabinY = 0.72;
        extra = 'spoiler';
        break;
      case 'truck':
        bodyW = 1.4; bodyH = 1.3; bodyL = 2.4;
        cabinW = 1.2; cabinH = 0.8; cabinL = 0.9;
        cabinZ = 0.7; wheelbase = 0.9; wheelTrack = 0.65;
        bodyY = 0.95; cabinY = 1.6;
        extra = 'truck-cargo';
        break;
    }

    const body = new THREE.Mesh(
      new THREE.BoxGeometry(bodyW, bodyH, bodyL),
      kind === 'truck' ? trimMat : bodyMat,
    );
    body.position.y = bodyY;
    body.castShadow = !this.reducedMotion;
    group.add(body);

    if (kind !== 'truck') {
      const cabin = new THREE.Mesh(
        new THREE.BoxGeometry(cabinW, cabinH, cabinL),
        accentMat,
      );
      cabin.position.set(0, cabinY, cabinZ);
      cabin.castShadow = !this.reducedMotion;
      group.add(cabin);
      const windshield = new THREE.Mesh(this.geos.carWindshield, this.mats.glass);
      windshield.position.set(0, cabinY + 0.05, cabinZ + cabinL * 0.45);
      windshield.rotation.x = -0.35;
      windshield.scale.set(cabinW / 0.9, cabinH / 0.5, 1);
      group.add(windshield);
      const rearWindow = new THREE.Mesh(this.geos.carWindshield, this.mats.glass);
      rearWindow.position.set(0, cabinY + 0.05, cabinZ - cabinL * 0.55);
      rearWindow.rotation.x = 0.35;
      rearWindow.scale.set(cabinW / 0.9, cabinH / 0.5, 1);
      group.add(rearWindow);
    } else {
      // Truck has the cab AND a tall cargo box behind it.
      const cab = new THREE.Mesh(
        new THREE.BoxGeometry(cabinW, cabinH, cabinL),
        bodyMat,
      );
      cab.position.set(0, cabinY, cabinZ);
      cab.castShadow = !this.reducedMotion;
      group.add(cab);
      const cabWindow = new THREE.Mesh(this.geos.carWindshield, this.mats.glass);
      cabWindow.position.set(0, cabinY + 0.05, cabinZ + cabinL * 0.5);
      cabWindow.rotation.x = -0.3;
      cabWindow.scale.set(cabinW / 0.9, cabinH / 0.5, 1);
      group.add(cabWindow);
    }

    if (extra === 'pickup-bed') {
      const bedFloor = new THREE.Mesh(
        new THREE.BoxGeometry(bodyW * 0.98, 0.05, 1.05),
        trimMat,
      );
      bedFloor.position.set(0, bodyY + bodyH * 0.5 + 0.02, -0.55);
      group.add(bedFloor);
      const bedRailL = new THREE.Mesh(
        new THREE.BoxGeometry(0.06, 0.18, 1.05),
        trimMat,
      );
      bedRailL.position.set(-bodyW * 0.46, bodyY + bodyH * 0.5 + 0.12, -0.55);
      group.add(bedRailL);
      const bedRailR = bedRailL.clone();
      bedRailR.position.x = bodyW * 0.46;
      group.add(bedRailR);
      const tailgate = new THREE.Mesh(
        new THREE.BoxGeometry(bodyW * 0.98, 0.32, 0.06),
        trimMat,
      );
      tailgate.position.set(0, bodyY + bodyH * 0.5 + 0.18, -bodyL * 0.5 + 0.05);
      group.add(tailgate);
    } else if (extra === 'spoiler') {
      const spStand1 = new THREE.Mesh(
        new THREE.BoxGeometry(0.08, 0.22, 0.08),
        trimMat,
      );
      spStand1.position.set(-0.35, bodyY + 0.32, -bodyL * 0.45);
      group.add(spStand1);
      const spStand2 = spStand1.clone();
      spStand2.position.x = 0.35;
      group.add(spStand2);
      const spBlade = new THREE.Mesh(
        new THREE.BoxGeometry(1.1, 0.06, 0.32),
        accentMat,
      );
      spBlade.position.set(0, bodyY + 0.45, -bodyL * 0.45);
      group.add(spBlade);
    } else if (extra === 'truck-cargo') {
      const cargo = new THREE.Mesh(
        new THREE.BoxGeometry(bodyW * 1.02, 1.6, bodyL * 0.7),
        accentMat,
      );
      cargo.position.set(0, bodyY + 0.4, -bodyL * 0.18);
      cargo.castShadow = !this.reducedMotion;
      group.add(cargo);
      // Side stripe for contrast
      const stripe = new THREE.Mesh(
        new THREE.BoxGeometry(bodyW * 1.04, 0.18, bodyL * 0.7),
        trimMat,
      );
      stripe.position.set(0, bodyY + 0.4, -bodyL * 0.18);
      group.add(stripe);
    }

    // Wheels with brighter alloy hubs so they read against the dark tire.
    const wheels: THREE.Object3D[] = [];
    const hubMat = new THREE.MeshStandardMaterial({
      color: 0xdbe1f0,
      roughness: 0.3,
      metalness: 0.85,
    });
    const wheelY = 0.24;
    const wheelPositions: Array<[number, number, number]> = [
      [-wheelTrack, wheelY, wheelbase],
      [wheelTrack, wheelY, wheelbase],
      [-wheelTrack, wheelY, -wheelbase],
      [wheelTrack, wheelY, -wheelbase],
    ];
    for (const [x, y, z] of wheelPositions) {
      const tire = new THREE.Mesh(this.geos.carWheel, this.mats.wheel);
      tire.rotation.z = Math.PI / 2;
      tire.position.set(x, y, z);
      tire.castShadow = !this.reducedMotion;
      const hub = new THREE.Mesh(this.geos.carWheelHub, hubMat);
      hub.rotation.z = Math.PI / 2;
      hub.position.set(x, y, z);
      group.add(tire);
      group.add(hub);
      wheels.push(tire);
      wheels.push(hub);
    }

    // Headlights & taillights (positioned per silhouette).
    const hlZ = bodyL * 0.5 + 0.05;
    const tlZ = -bodyL * 0.5 - 0.05;
    const hlL = new THREE.Mesh(this.geos.carHeadlight, this.mats.headlight);
    hlL.position.set(-bodyW * 0.32, bodyY + 0.05, hlZ);
    group.add(hlL);
    const hlR = new THREE.Mesh(this.geos.carHeadlight, this.mats.headlight);
    hlR.position.set(bodyW * 0.32, bodyY + 0.05, hlZ);
    group.add(hlR);
    // Slim front grille between the headlights
    const grille = new THREE.Mesh(
      new THREE.BoxGeometry(bodyW * 0.55, 0.1, 0.06),
      trimMat,
    );
    grille.position.set(0, bodyY + 0.02, hlZ - 0.01);
    group.add(grille);

    const brakeMats: THREE.MeshStandardMaterial[] = [];
    const tlL = new THREE.Mesh(
      this.geos.carHeadlight,
      new THREE.MeshStandardMaterial({ color: 0xff3a3a, emissive: 0xff3a3a, emissiveIntensity: 1.0 }),
    );
    tlL.position.set(-bodyW * 0.32, bodyY + 0.05, tlZ);
    tlL.scale.set(0.9, 0.55, 0.9);
    group.add(tlL);
    brakeMats.push(tlL.material as THREE.MeshStandardMaterial);
    const tlR = new THREE.Mesh(
      this.geos.carHeadlight,
      new THREE.MeshStandardMaterial({ color: 0xff3a3a, emissive: 0xff3a3a, emissiveIntensity: 1.0 }),
    );
    tlR.position.set(bodyW * 0.32, bodyY + 0.05, tlZ);
    tlR.scale.set(0.9, 0.55, 0.9);
    group.add(tlR);
    brakeMats.push(tlR.material as THREE.MeshStandardMaterial);

    group.userData['bodyMat'] = bodyMat;
    group.userData['accentMat'] = accentMat;
    group.userData['wheels'] = wheels;
    group.userData['brakeMats'] = brakeMats;
    return group;
  }

  private buildCone(): THREE.Group {
    const group = new THREE.Group();
    const cone = new THREE.Mesh(this.geos.cone, this.mats.cone);
    cone.position.y = 0.45;
    cone.castShadow = !this.reducedMotion;
    group.add(cone);
    const stripe = new THREE.Mesh(this.geos.coneStripe, this.mats.coneStripe);
    stripe.position.y = 0.45;
    stripe.scale.y = 0.6;
    group.add(stripe);
    return group;
  }

  private buildBarrier(): THREE.Group {
    const group = new THREE.Group();
    const mat = new THREE.MeshStandardMaterial({ color: 0xffb547, emissive: 0x4a3300, emissiveIntensity: 0.4 });
    const body = new THREE.Mesh(this.geos.barrier, mat);
    body.position.y = 0.35;
    body.castShadow = !this.reducedMotion;
    group.add(body);
    const stripeMat = new THREE.MeshBasicMaterial({ color: 0x1c2742 });
    for (let i = 0; i < 5; i++) {
      const sGeo = new THREE.PlaneGeometry(0.2, 0.55);
      const s = new THREE.Mesh(sGeo, stripeMat);
      s.position.set(-0.6 + i * 0.3, 0.35, 0.26);
      group.add(s);
    }
    group.userData['bodyMat'] = mat;
    group.userData['stripeMat'] = stripeMat;
    return group;
  }

  private buildStreetLamp(side: -1 | 1): {
    group: THREE.Group;
    bulb: THREE.PointLight;
  } {
    const group = new THREE.Group();
    const poleMat = new THREE.MeshStandardMaterial({
      color: 0x2a3a66,
      roughness: 0.5,
      metalness: 0.6,
    });
    const pole = new THREE.Mesh(this.geos.lampPole, poleMat);
    pole.position.set(0, 2.2, 0);
    pole.castShadow = !this.reducedMotion;
    group.add(pole);
    const armGeo = new THREE.BoxGeometry(1.0, 0.12, 0.12);
    const arm = new THREE.Mesh(armGeo, poleMat);
    arm.position.set(-side * 0.5, 4.25, 0);
    group.add(arm);
    const bulbMat = new THREE.MeshStandardMaterial({
      color: 0xfff097,
      emissive: 0xfff097,
      emissiveIntensity: 2.2,
    });
    const bulbMesh = new THREE.Mesh(this.geos.lampHead, bulbMat);
    bulbMesh.position.set(-side * 1.0, 4.2, 0);
    group.add(bulbMesh);
    const bulb = new THREE.PointLight(0xfff097, 0.55, 14, 1.6);
    bulb.position.copy(bulbMesh.position);
    group.add(bulb);
    return { group, bulb };
  }

  private buildBillboard(side: -1 | 1, text: string): THREE.Group {
    const group = new THREE.Group();
    const poleMat = new THREE.MeshStandardMaterial({
      color: 0x2a3a66,
      roughness: 0.6,
      metalness: 0.4,
    });
    const pole1 = new THREE.Mesh(this.geos.billboardPole, poleMat);
    pole1.position.set(-1.2, 1.7, 0);
    group.add(pole1);
    const pole2 = new THREE.Mesh(this.geos.billboardPole, poleMat);
    pole2.position.set(1.2, 1.7, 0);
    group.add(pole2);

    const tex = makeBillboardTexture(text);
    const panelMat = new THREE.MeshBasicMaterial({ map: tex });
    const panel = new THREE.Mesh(this.geos.billboardPanel, panelMat);
    panel.position.set(0, 3.5, 0);
    panel.rotation.y = side > 0 ? -Math.PI / 16 : Math.PI / 16;
    group.add(panel);

    const frame = new THREE.Mesh(
      new THREE.BoxGeometry(3.34, 1.94, 0.08),
      poleMat,
    );
    frame.position.copy(panel.position);
    frame.position.z -= 0.04;
    frame.rotation.copy(panel.rotation);
    group.add(frame);
    group.userData['panelTex'] = tex;
    group.userData['panelMat'] = panelMat;
    return group;
  }

  private buildRoadsideTree(): THREE.Group {
    const group = new THREE.Group();
    const trunkMat = new THREE.MeshStandardMaterial({
      color: 0x3a2a1a,
      roughness: 0.9,
    });
    const trunk = new THREE.Mesh(this.geos.treeTrunk, trunkMat);
    trunk.position.y = 0.8;
    trunk.castShadow = !this.reducedMotion;
    group.add(trunk);
    const palette = [0x1d6b3a, 0x2bb673, 0x86c34d, 0x4cd964];
    const crownMat = new THREE.MeshStandardMaterial({
      color: palette[Math.floor(Math.random() * palette.length)],
      roughness: 0.8,
    });
    const crown = new THREE.Mesh(this.geos.treeCrown, crownMat);
    crown.position.y = 1.9;
    crown.scale.setScalar(0.9 + Math.random() * 0.5);
    crown.castShadow = !this.reducedMotion;
    group.add(crown);
    return group;
  }

  private buildBuilding(): THREE.Group {
    const group = new THREE.Group();
    const palette = [0x1c2742, 0x281e6e, 0x142345, 0x0e1530, 0x223558];
    const baseColor = palette[Math.floor(Math.random() * palette.length)];
    const floors = 3 + Math.floor(Math.random() * 5);
    const facadeMat = new THREE.MeshStandardMaterial({
      color: baseColor,
      roughness: 0.7,
      metalness: 0.3,
    });
    for (let i = 0; i < floors; i++) {
      const floor = new THREE.Mesh(this.geos.bldgFloor, facadeMat);
      floor.position.y = 0.5 + i * 1.05;
      floor.castShadow = !this.reducedMotion;
      group.add(floor);
      const windowMat = new THREE.MeshBasicMaterial({
        color: 0xfff097,
        transparent: true,
        opacity: 0.55 + Math.random() * 0.4,
      });
      for (let wx = -0.8; wx <= 0.8; wx += 0.4) {
        if (Math.random() < 0.55) continue;
        const win = new THREE.Mesh(
          new THREE.PlaneGeometry(0.22, 0.32),
          windowMat,
        );
        win.position.set(wx, floor.position.y, 1.21);
        group.add(win);
      }
    }
    return group;
  }

  private buildArch(): THREE.Group {
    const group = new THREE.Group();
    const pillarMat = new THREE.MeshStandardMaterial({
      color: 0x6c5ce7,
      emissive: 0x281e6e,
      emissiveIntensity: 0.55,
      roughness: 0.4,
      metalness: 0.55,
    });
    const pillarL = new THREE.Mesh(this.geos.archPillar, pillarMat);
    pillarL.position.set(-4.0, 2.1, 0);
    pillarL.castShadow = !this.reducedMotion;
    group.add(pillarL);
    const pillarR = new THREE.Mesh(this.geos.archPillar, pillarMat);
    pillarR.position.set(4.0, 2.1, 0);
    pillarR.castShadow = !this.reducedMotion;
    group.add(pillarR);
    const top = new THREE.Mesh(this.geos.archTop, pillarMat);
    top.position.set(0, 4.2, 0);
    top.castShadow = !this.reducedMotion;
    group.add(top);
    const glowMat = new THREE.MeshBasicMaterial({ color: 0xa6e1ff });
    const glowL = new THREE.Mesh(new THREE.PlaneGeometry(0.12, 4.0), glowMat);
    glowL.position.set(-4.0 + 0.19, 2.1, 0.001);
    group.add(glowL);
    const glowR = new THREE.Mesh(new THREE.PlaneGeometry(0.12, 4.0), glowMat);
    glowR.position.set(4.0 - 0.19, 2.1, 0.001);
    group.add(glowR);
    return group;
  }

  private spawnConfetti(z: number, x: number, count = 28) {
    if (this.reducedMotion) return;
    const colors = [0x4cd964, 0xffd34a, 0xff79c6, 0x6c5ce7, 0xa6e1ff, 0xfff097];
    const group = new THREE.Group();
    const meshes: THREE.Mesh[] = [];
    const materials: THREE.Material[] = [];
    const vx: number[] = [];
    const vy: number[] = [];
    const vz: number[] = [];
    const spin: number[] = [];
    for (let i = 0; i < count; i++) {
      const mat = new THREE.MeshBasicMaterial({
        color: colors[Math.floor(Math.random() * colors.length)],
        side: THREE.DoubleSide,
        transparent: true,
        opacity: 1,
      });
      const m = new THREE.Mesh(this.geos.confetti, mat);
      m.position.set(0, 0, 0);
      m.rotation.z = Math.random() * Math.PI;
      group.add(m);
      meshes.push(m);
      materials.push(mat);
      const angle = Math.random() * Math.PI * 2;
      const speed = 2 + Math.random() * 3.5;
      vx.push(Math.cos(angle) * speed);
      vz.push(Math.sin(angle) * speed * 0.4);
      vy.push(2.5 + Math.random() * 2.5);
      spin.push((Math.random() - 0.5) * 12);
    }
    group.position.set(x, 1.0, z);
    this.scene.add(group);
    this.particles.push({
      group,
      vx,
      vy,
      vz,
      spin,
      ageMs: 0,
      lifeMs: 1400,
      meshes,
      materials,
    });
  }

  private updateParticles(dt: number) {
    const remaining: ParticleBurst[] = [];
    for (const p of this.particles) {
      p.ageMs += dt * 1000;
      const t = p.ageMs / p.lifeMs;
      if (t >= 1) {
        this.scene.remove(p.group);
        for (const m of p.materials) m.dispose();
        continue;
      }
      const gravity = -6;
      for (let i = 0; i < p.meshes.length; i++) {
        const m = p.meshes[i];
        p.vy[i] += gravity * dt;
        m.position.x += p.vx[i] * dt;
        m.position.y += p.vy[i] * dt;
        m.position.z += p.vz[i] * dt;
        m.rotation.z += p.spin[i] * dt;
        (m.material as THREE.MeshBasicMaterial).opacity = Math.max(
          0,
          1 - Math.max(0, (t - 0.5) * 2),
        );
      }
      remaining.push(p);
    }
    this.particles = remaining;
  }

  private resize() {
    const parent = this.canvas.parentElement;
    if (!parent) return;
    const w = parent.clientWidth;
    const h = parent.clientHeight;
    if (w <= 0 || h <= 0) return;
    this.renderer.setSize(w, h, false);
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
  }

  // ----- input -----

  private bindInput() {
    window.addEventListener('keydown', this.keyHandler);
    window.addEventListener('blur', this.blurHandler);

    this.touchStartHandler = (e: TouchEvent) => {
      const t = e.touches[0];
      if (!t) return;
      this.touchStart = { x: t.clientX, y: t.clientY, t: performance.now() };
    };
    this.touchEndHandler = (e: TouchEvent) => {
      if (!this.touchStart) return;
      const t = e.changedTouches[0];
      if (!t) return;
      const dx = t.clientX - this.touchStart.x;
      const dy = t.clientY - this.touchStart.y;
      const dt = performance.now() - this.touchStart.t;
      this.touchStart = null;
      if (dt > 600) return;
      const absX = Math.abs(dx);
      const absY = Math.abs(dy);
      if (absX < 20 && absY < 20) {
        this.actionJump();
      } else if (absX > absY) {
        if (dx > 0) this.actionLane(1);
        else this.actionLane(-1);
      } else if (dy > 0) {
        this.actionSlide();
      } else {
        this.actionJump();
      }
    };
    this.canvas.addEventListener('touchstart', this.touchStartHandler, { passive: true });
    this.canvas.addEventListener('touchend', this.touchEndHandler, { passive: true });
  }

  private onKey(e: KeyboardEvent) {
    if (this.destroyed) return;
    const k = e.key.toLowerCase();
    if (k === 'escape' || k === 'p') {
      this.togglePause();
      e.preventDefault();
      return;
    }
    if (this.status !== 'RUNNING') return;
    switch (k) {
      case 'arrowleft':
      case 'a':
        this.actionLane(-1);
        e.preventDefault();
        break;
      case 'arrowright':
      case 'd':
        this.actionLane(1);
        e.preventDefault();
        break;
      case 'arrowup':
      case 'w':
      case ' ':
      case 'space':
      case 'spacebar':
        this.actionJump();
        e.preventDefault();
        break;
      case 'arrowdown':
      case 's':
        this.actionSlide();
        e.preventDefault();
        break;
    }
  }

  private actionLane(dir: -1 | 1) {
    const target = Math.max(0, Math.min(2, this.playerLane + dir));
    if (target !== this.playerLane) {
      this.playerLane = target;
      this.playerTargetX = this.lanePositions[target];
    }
  }
  private actionJump() {
    if (this.playerState === 'running') {
      this.playerState = 'jumping';
      const jumpInitial =
        (2 * this.cfg.jumpHeight) / (this.cfg.jumpDuration / 2);
      this.playerVY = jumpInitial;
    }
  }
  private actionSlide() {
    if (this.playerState === 'running') {
      this.playerState = 'sliding';
      this.playerStateTimer = this.cfg.slideDuration;
    }
  }

  // ----- main loop -----

  private tick = () => {
    if (this.destroyed) return;
    this.rafId = requestAnimationFrame(this.tick);
    const now = performance.now();
    let frameMs = now - this.lastTimeMs;
    this.lastTimeMs = now;
    if (frameMs > 100) frameMs = 100;

    if (this.status === 'PAUSED' || this.status === 'RESULTS') {
      this.renderer.render(this.scene, this.camera);
      return;
    }

    if (this.status === 'COUNTDOWN') {
      this.countdownTimer -= frameMs / 1000;
      this.animateIdle(frameMs / 1000);
      this.emitHud();
      if (this.countdownTimer <= 0) {
        this.setStatus('RUNNING');
      }
      this.renderer.render(this.scene, this.camera);
      return;
    }

    this.accumulatorMs += frameMs;
    const dtMs = this.fixedDt * 1000;
    let safety = 0;
    while (this.accumulatorMs >= dtMs && safety < 5) {
      this.update(this.fixedDt);
      this.accumulatorMs -= dtMs;
      safety++;
    }

    this.animatePlayer(frameMs / 1000);
    this.updateCamera();
    this.renderer.render(this.scene, this.camera);
  };

  private animateIdle(dt: number) {
    this.playerY = 0;
    this.playerGroup.position.x +=
      (this.playerTargetX - this.playerGroup.position.x) *
      Math.min(1, this.cfg.laneSwitchSpeed * dt);
    this.playerHead.rotation.y = Math.sin(performance.now() / 300) * 0.1;
  }

  private update(dt: number) {
    if (this.status !== 'RUNNING') return;
    this.elapsedMs += dt * 1000;

    const speed = this.currentSpeed();
    const deltaZ = speed * dt;
    this.distance += deltaZ;

    this.playerGroup.position.z += FORWARD * deltaZ;

    this.playerGroup.position.x +=
      (this.playerTargetX - this.playerGroup.position.x) *
      Math.min(1, this.cfg.laneSwitchSpeed * dt);

    this.updatePlayerState(dt);

    if (this.hitInvulnTimer > 0) this.hitInvulnTimer -= dt;

    this.obstacleTimer -= dt;
    this.coinTimer -= dt;
    this.pickupTimer -= dt;
    if (this.obstacleTimer <= 0) {
      this.spawnObstacleRow();
      this.obstacleTimer = this.cfg.obstacleEverySec * (0.7 + Math.random() * 0.5);
    }
    if (this.coinTimer <= 0) {
      this.spawnCoinRun();
      this.coinTimer = this.cfg.coinEverySec * (0.8 + Math.random() * 0.4);
    }
    if (this.pickupTimer <= 0) {
      this.spawnPickup();
      this.pickupTimer = 12 + Math.random() * 8;
    }
    if (this.distance >= this.nextQuestionAtDistance && !this.currentQuestion) {
      this.spawnQuestionGate();
    }

    this.cullBehind();

    for (const c of this.coins) c.mesh.rotation.y += dt * 6;
    for (const p of this.pickups) {
      p.mesh.rotation.y += dt * 3;
      p.mesh.position.y = 0.9 + Math.sin(this.elapsedMs / 400 + p.mesh.position.x) * 0.15;
    }
    // Animate car wheels — visible spin
    for (const o of this.obstacles) {
      if (o.kind === 'car' && o.wheels) {
        for (const w of o.wheels) {
          w.rotation.x += dt * 10;
        }
      }
    }

    this.detectCollisions();
    this.resolveGates();
    this.updateParticles(dt);

    for (const pk of this.activePickups) pk.remainingMs -= dt * 1000;
    this.activePickups = this.activePickups.filter((p) => p.remainingMs > 0);
    this.multiplier = this.activePickups.find((p) => p.kind === 'x2') ? 2 : 1;

    if (this.lastExplanationTimer > 0) {
      this.lastExplanationTimer -= dt;
      if (this.lastExplanationTimer <= 0) {
        this.lastExplanation = undefined;
      }
    }

    if (
      !this.prefetching &&
      this.fetchMoreQuestions &&
      this.questionPool.length - this.questionCursor <= 2
    ) {
      this.prefetching = true;
      this.fetchMoreQuestions(5)
        .then((more) => this.questionPool.push(...more))
        .catch(() => undefined)
        .finally(() => {
          this.prefetching = false;
        });
    }

    this.emitHud();
  }

  private currentSpeed(): number {
    const elapsedSec = this.elapsedMs / 1000;
    const raw = this.cfg.baseSpeed + this.cfg.speedRamp * Math.sqrt(elapsedSec);
    const boosted = this.activePickups.some((p) => p.kind === 'boost') ? raw * 1.4 : raw;
    return Math.min(boosted, this.cfg.maxSpeed);
  }

  private updatePlayerState(dt: number) {
    if (this.playerState === 'jumping') {
      const gravity = -((2 * this.cfg.jumpHeight) /
        Math.pow(this.cfg.jumpDuration / 2, 2));
      this.playerVY += gravity * dt;
      this.playerY += this.playerVY * dt;
      if (this.playerY <= 0) {
        this.playerY = 0;
        this.playerVY = 0;
        this.playerState = 'running';
      }
    } else if (this.playerState === 'sliding') {
      this.playerStateTimer -= dt;
      if (this.playerStateTimer <= 0) {
        this.playerState = 'running';
      }
    } else if (this.playerState === 'hit') {
      this.playerStateTimer -= dt;
      if (this.playerStateTimer <= 0) {
        this.playerState = 'running';
      }
    }
  }

  private animatePlayer(_dt: number) {
    this.playerGroup.position.y = this.playerY;
    const running = this.playerState === 'running' && this.status === 'RUNNING';
    const t = this.elapsedMs / 120;
    if (this.playerState === 'sliding') {
      this.playerTorso.rotation.x = -0.9;
      this.playerTorso.position.set(0, 0.5, 0.15);
      this.playerHead.position.set(0, 0.9, 0.4);
      this.playerLeftArm.rotation.x = -1.2;
      this.playerRightArm.rotation.x = -1.2;
      this.playerLeftLeg.rotation.x = -1.0;
      this.playerRightLeg.rotation.x = -1.0;
    } else {
      this.playerTorso.rotation.x = 0;
      this.playerTorso.position.set(0, 0.95, 0);
      this.playerHead.position.set(0, 1.55, 0);
      if (running && !this.reducedMotion) {
        const swing = Math.sin(t) * 0.9;
        this.playerLeftArm.rotation.x = swing;
        this.playerRightArm.rotation.x = -swing;
        this.playerLeftLeg.rotation.x = -swing;
        this.playerRightLeg.rotation.x = swing;
        this.playerTorso.rotation.z = Math.sin(t * 2) * 0.04;
      } else {
        this.playerLeftArm.rotation.x = 0;
        this.playerRightArm.rotation.x = 0;
        this.playerLeftLeg.rotation.x = 0;
        this.playerRightLeg.rotation.x = 0;
        this.playerTorso.rotation.z = 0;
      }
    }
    // Hit flicker
    if (this.hitInvulnTimer > 0) {
      const showHit = Math.floor(this.elapsedMs / 80) % 2 === 0;
      this.playerTorso.material = showHit ? this.mats.playerHit : this.mats.playerBody;
    } else {
      this.playerTorso.material = this.mats.playerBody;
    }
  }

  private updateCamera() {
    const target = this.playerGroup.position;
    const desired = new THREE.Vector3(target.x * 0.4, 4.8, target.z + 8.0);
    this.camera.position.lerp(desired, 0.15);
    this.camera.lookAt(target.x * 0.25, 1.2, target.z - 4);
  }

  // ----- spawning -----

  private spawnObstacleRow() {
    const spawnZ = this.playerGroup.position.z - 80;
    // 70% car, 22% cone, 8% barrier — cars dominate per user feedback
    const occupied = new Set<number>();
    const count = Math.random() < 0.82 ? 1 : 2;
    for (let i = 0; i < count; i++) {
      let lane = Math.floor(Math.random() * 3);
      let tries = 0;
      while (occupied.has(lane) && tries < 5) {
        lane = (lane + 1) % 3;
        tries++;
      }
      occupied.add(lane);
      const r = Math.random();
      let kind: ObstacleObj['kind'];
      let group: THREE.Group;
      let wheels: THREE.Object3D[] | undefined;
      if (r < 0.7) {
        kind = 'car';
        group = this.buildCar();
        wheels = group.userData['wheels'] as THREE.Object3D[];
      } else if (r < 0.92) {
        kind = 'cone';
        group = this.buildCone();
      } else {
        kind = 'barrier';
        group = this.buildBarrier();
      }
      group.position.set(this.lanePositions[lane], 0, spawnZ - i * 1.5);
      this.scene.add(group);
      this.obstacles.push({ group, kind, lane, wheels });
    }
  }

  private spawnCoinRun() {
    const spawnZ = this.playerGroup.position.z - 80;
    const lane = Math.floor(Math.random() * 3);
    const len = 3 + Math.floor(Math.random() * 4);
    for (let i = 0; i < len; i++) {
      const mesh = new THREE.Mesh(this.geos.coin, this.mats.coin);
      mesh.position.set(this.lanePositions[lane], 0.7, spawnZ - i * 1.4);
      mesh.rotation.x = Math.PI / 2;
      this.scene.add(mesh);
      this.coins.push({ mesh, lane });
    }
  }

  private spawnPickup() {
    const spawnZ = this.playerGroup.position.z - 80;
    const lane = Math.floor(Math.random() * 3);
    const kindRoll = Math.random();
    let kind: ActivePickup['kind'];
    let mat: THREE.Material;
    if (kindRoll < 0.35) {
      kind = 'shield';
      mat = this.mats.pickupShield;
    } else if (kindRoll < 0.6) {
      kind = 'magnet';
      mat = this.mats.pickupMagnet;
    } else if (kindRoll < 0.8) {
      kind = 'x2';
      mat = this.mats.pickupX2;
    } else {
      kind = 'boost';
      mat = this.mats.pickupBoost;
    }
    const mesh = new THREE.Mesh(this.geos.pickup, mat);
    mesh.position.set(this.lanePositions[lane], 1.1, spawnZ);
    this.scene.add(mesh);
    this.pickups.push({ mesh, lane, kind });
  }

  private spawnQuestionGate() {
    if (this.questionCursor >= this.questionPool.length) {
      this.nextQuestionAtDistance = this.distance + this.cfg.questionEveryMeters;
      return;
    }
    const question = this.questionPool[this.questionCursor++];
    const spawnZ = this.playerGroup.position.z - 65;
    const correctOpt = question.options.find((o) => o.id === question.correctOptionId);
    if (!correctOpt) return;
    const others = question.options.filter((o) => o.id !== correctOpt.id);
    const distractors = shuffle(others).slice(0, 2);
    const lineup = shuffle([correctOpt, ...distractors]);
    const laneToOptionId: Record<0 | 1 | 2, string> = {
      0: lineup[0].id,
      1: lineup[1].id,
      2: lineup[2].id,
    };

    // Arch over the road as a dramatic visual cue for the question gate.
    const arch = this.buildArch();
    arch.position.set(0, 0, spawnZ - 1.6);
    this.scene.add(arch);

    // Question banner above the road, mounted on the arch.
    const banner = makeBannerMesh(question.text);
    banner.mesh.position.set(0, 4.5, spawnZ - 1.55);
    banner.mesh.rotation.x = -0.1;
    this.scene.add(banner.mesh);

    const plates: GatePlate[] = [];
    for (let lane: 0 | 1 | 2 = 0; lane <= 2; lane = (lane + 1) as 0 | 1 | 2) {
      const opt = lineup[lane];
      const texture = makeOptionTexture(opt.text, ['A', 'B', 'C'][lane]);
      const mat = new THREE.MeshBasicMaterial({
        map: texture,
        transparent: true,
        opacity: 0.95,
      });
      const mesh = new THREE.Mesh(this.geos.gatePlate, mat);
      mesh.position.set(this.lanePositions[lane], 1.6, spawnZ);
      this.scene.add(mesh);
      plates.push({ mesh, lane, optionId: opt.id, texture });
      if (lane === 2) break;
    }

    const gate: ActiveGate = {
      questionId: question.id,
      question,
      zTrigger: spawnZ,
      laneToOptionId,
      plates,
      banner,
      arch,
      resolved: false,
      spawnedAtMs: this.elapsedMs,
      spawnedAtDistance: this.distance,
    };
    this.gates.push(gate);
    this.currentQuestion = {
      question,
      laneToOptionId,
      spawnedAt: this.elapsedMs,
      resolveAtDistance: this.distance + this.cfg.questionResolveAfterMeters,
      resolved: false,
    };
    this.nextQuestionAtDistance =
      this.distance + this.cfg.questionEveryMeters + 80;
  }

  // ----- collisions -----

  private detectCollisions() {
    const magnetActive = this.activePickups.some((p) => p.kind === 'magnet');

    // Coins
    const remainingCoins: CoinObj[] = [];
    for (const c of this.coins) {
      if (magnetActive && Math.abs(c.mesh.position.z - this.playerGroup.position.z) < 5) {
        c.mesh.position.x += (this.playerGroup.position.x - c.mesh.position.x) * 0.2;
        c.mesh.position.y += (1 - c.mesh.position.y) * 0.15;
      }
      const dx = c.mesh.position.x - this.playerGroup.position.x;
      const dz = c.mesh.position.z - this.playerGroup.position.z;
      const dy = c.mesh.position.y - (this.playerY + 0.6);
      if (Math.abs(dx) < 0.55 && Math.abs(dz) < 0.55 && Math.abs(dy) < 1.0) {
        this.coinsCollected += 1;
        this.score += 1 * this.multiplier;
        this.scene.remove(c.mesh);
        continue;
      }
      remainingCoins.push(c);
    }
    this.coins = remainingCoins;

    // Pickups
    const remainingPickups: PickupObj[] = [];
    for (const p of this.pickups) {
      const dx = p.mesh.position.x - this.playerGroup.position.x;
      const dz = p.mesh.position.z - this.playerGroup.position.z;
      if (Math.abs(dx) < 0.7 && Math.abs(dz) < 0.7) {
        this.applyPickup(p.kind);
        this.scene.remove(p.mesh);
        continue;
      }
      remainingPickups.push(p);
    }
    this.pickups = remainingPickups;

    // Obstacles
    const remainingObs: ObstacleObj[] = [];
    for (const o of this.obstacles) {
      const dz = o.group.position.z - this.playerGroup.position.z;
      const dx = o.group.position.x - this.playerGroup.position.x;
      const sameLane = Math.abs(dx) < 1.0;
      const closeZ = dz > -0.7 && dz < 0.7;
      if (sameLane && closeZ && this.hitInvulnTimer <= 0) {
        const passCone = o.kind === 'cone' && this.playerY > 0.6;
        const passBarrier = o.kind === 'barrier' && this.playerY > 0.9;
        // Cars cannot be jumped or slid — only side-step.
        if (!passCone && !passBarrier) {
          this.onHit('obstacle');
          this.scene.remove(o.group);
          continue;
        }
      }
      remainingObs.push(o);
    }
    this.obstacles = remainingObs;
  }

  private resolveGates() {
    const remainingGates: ActiveGate[] = [];
    for (const g of this.gates) {
      if (!g.resolved && this.playerGroup.position.z <= g.zTrigger + 0.2) {
        const lane = this.playerLane as 0 | 1 | 2;
        const chosenOpt = g.laneToOptionId[lane];
        const correct = chosenOpt === g.question.correctOptionId;
        const timeMs = this.elapsedMs - g.spawnedAtMs;
        const ans: AnswerEvent = {
          questionId: g.question.id,
          selectedOptionId: chosenOpt,
          correct,
          timeToAnswerMs: timeMs,
          difficulty: g.question.difficulty,
        };
        this.answers.push(ans);
        this.handlers.onAnswer(ans);
        g.resolved = true;
        // Flash the plates: correct→green, wrong→red
        for (const p of g.plates) {
          const isRight = p.optionId === g.question.correctOptionId;
          const m = p.mesh.material as THREE.MeshBasicMaterial;
          m.color = new THREE.Color(isRight ? 0x4cd964 : 0xff5470);
          m.map = null;
          m.needsUpdate = true;
        }
        if (correct) {
          this.combo += 1;
          this.score += 10 * this.multiplier; // +10 per correct as user requested
          this.coinsCollected += 5;
          // Burst of confetti at the chosen plate to celebrate.
          const plateX = this.lanePositions[lane];
          this.spawnConfetti(g.zTrigger, plateX, 36);
        } else {
          this.combo = 0;
          this.onHit('wrong_answer');
        }
        if (g.question.explanation) {
          this.lastExplanation =
            (correct ? '✓ ' : '✗ ') + g.question.explanation;
          this.lastExplanationTimer = 2.5;
        } else {
          this.lastExplanation = correct ? '+10 очков!' : 'Неверно — −1 жизнь';
          this.lastExplanationTimer = 1.6;
        }
        this.currentQuestion = undefined;
        // End of round?
        if (this.answers.length >= this.cfg.questionsPerRound) {
          this.finish();
        }
      }
      if (this.playerGroup.position.z < g.zTrigger - 6) {
        for (const p of g.plates) {
          this.scene.remove(p.mesh);
          (p.mesh.material as THREE.Material).dispose();
          p.texture.dispose();
        }
        if (g.banner) {
          this.scene.remove(g.banner.mesh);
          (g.banner.mesh.material as THREE.Material).dispose();
          g.banner.texture.dispose();
        }
        if (g.arch) {
          this.scene.remove(g.arch);
        }
      } else {
        remainingGates.push(g);
      }
    }
    this.gates = remainingGates;
  }

  private applyPickup(kind: ActivePickup['kind']) {
    if (kind === 'shield') {
      this.activePickups = this.activePickups.filter((p) => p.kind !== 'shield');
      this.activePickups.push({ kind: 'shield', remainingMs: 30000 });
    } else if (kind === 'magnet') {
      this.activePickups.push({ kind: 'magnet', remainingMs: 5000 });
    } else if (kind === 'x2') {
      this.activePickups.push({ kind: 'x2', remainingMs: 5000 });
    } else if (kind === 'boost') {
      this.activePickups.push({ kind: 'boost', remainingMs: 3000 });
      this.hitInvulnTimer = 3;
    }
  }

  private onHit(_reason: 'obstacle' | 'wrong_answer') {
    const hasShield = this.activePickups.some((p) => p.kind === 'shield');
    if (hasShield) {
      this.activePickups = this.activePickups.filter((p) => p.kind !== 'shield');
      this.hitInvulnTimer = 1.2;
      return;
    }
    this.lives -= 1;
    this.combo = 0;
    this.hitInvulnTimer = 1.6;
    this.playerState = 'hit';
    this.playerStateTimer = 0.6;
    if (this.lives <= 0) {
      this.finish();
    }
  }

  private cullBehind() {
    const limit = this.playerGroup.position.z + 6;
    this.obstacles = this.obstacles.filter((o) => {
      if (o.group.position.z > limit) {
        this.scene.remove(o.group);
        return false;
      }
      return true;
    });
    this.coins = this.coins.filter((c) => {
      if (c.mesh.position.z > limit) {
        this.scene.remove(c.mesh);
        return false;
      }
      return true;
    });
    this.pickups = this.pickups.filter((p) => {
      if (p.mesh.position.z > limit) {
        this.scene.remove(p.mesh);
        return false;
      }
      return true;
    });
    for (const tile of this.groundTiles) {
      if (tile.position.z > this.playerGroup.position.z + this.cfg.worldChunkLength) {
        const furthest = this.groundTiles.reduce(
          (acc, t) => Math.min(acc, t.position.z),
          Infinity,
        );
        tile.position.z = furthest - this.cfg.worldChunkLength;
      }
    }
    for (const stripe of this.neonStripes) {
      if (stripe.position.z > this.playerGroup.position.z + 6) {
        const farthest = this.neonStripes.reduce(
          (acc, s) => Math.min(acc, s.position.z),
          Infinity,
        );
        stripe.position.z = farthest - 3;
      }
    }
    // Recycle roadside lamps (alternating sides preserved).
    for (const lamp of this.streetLamps) {
      if (lamp.group.position.z > this.playerGroup.position.z + 8) {
        const farthest = this.streetLamps.reduce(
          (acc, l) => Math.min(acc, l.group.position.z),
          Infinity,
        );
        lamp.group.position.z = farthest - 22;
      }
    }
    for (const b of this.billboards) {
      if (b.position.z > this.playerGroup.position.z + 12) {
        const farthest = this.billboards.reduce(
          (acc, x) => Math.min(acc, x.position.z),
          Infinity,
        );
        b.position.z = farthest - 110;
      }
    }
    for (const t of this.roadsideTrees) {
      if (t.position.z > this.playerGroup.position.z + 8) {
        const farthest = this.roadsideTrees.reduce(
          (acc, x) => Math.min(acc, x.position.z),
          Infinity,
        );
        t.position.z = farthest - (12 + Math.random() * 20);
      }
    }
    for (const b of this.buildings) {
      if (b.position.z > this.playerGroup.position.z + 12) {
        const farthest = this.buildings.reduce(
          (acc, x) => Math.min(acc, x.position.z),
          Infinity,
        );
        b.position.z = farthest - (24 + Math.random() * 30);
      }
    }
  }

  // ----- finish -----

  private finish() {
    if (this.status === 'GAME_OVER' || this.status === 'RESULTS') return;
    this.setStatus('GAME_OVER');
    const summary = {
      score: Math.round(this.score),
      coins: this.coinsCollected,
      questionsAsked: this.answers.length,
      questionsCorrect: this.answers.filter((a) => a.correct).length,
      distance: Math.round(this.distance),
      durationMs: this.elapsedMs,
      perQuestion: this.answers,
    };
    this.handlers.onFinished(summary);
    this.setStatus('RESULTS');
  }

  // ----- HUD plumbing -----

  private setStatus(status: Status) {
    this.status = status;
    this.emitHud();
  }

  private emitHud() {
    const hud: BrainDashHud = {
      status: this.status,
      lives: this.lives,
      livesMax: this.cfg.livesMax,
      distance: Math.round(this.distance),
      score: Math.round(this.score),
      combo: this.combo,
      multiplier: this.multiplier,
      coins: this.coinsCollected,
      speedKmh: Math.round(this.currentSpeed() * 3.6),
      countdown: this.status === 'COUNTDOWN' ? Math.max(0, Math.ceil(this.countdownTimer)) : undefined,
      question: this.currentQuestion,
      lastExplanation: this.lastExplanation,
      pickups: this.activePickups,
      questionsAsked: this.answers.length,
      questionsCorrect: this.answers.filter((a) => a.correct).length,
    };
    if (!hudEquals(this.lastHud, hud)) {
      this.handlers.onHudChange(hud);
      this.lastHud = hud;
    }
  }
}

function shuffle<T>(arr: T[]): T[] {
  const out = arr.slice();
  for (let i = out.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [out[i], out[j]] = [out[j], out[i]];
  }
  return out;
}

function makeLimb(
  geo: THREE.BufferGeometry,
  mat: THREE.Material,
  pivotOffset: number,
): THREE.Group {
  const group = new THREE.Group();
  const mesh = new THREE.Mesh(geo, mat);
  mesh.position.y = -pivotOffset;
  mesh.castShadow = true;
  group.add(mesh);
  return group;
}

function hudEquals(a: BrainDashHud | null, b: BrainDashHud) {
  if (!a) return false;
  return (
    a.status === b.status &&
    a.lives === b.lives &&
    a.distance === b.distance &&
    a.score === b.score &&
    a.combo === b.combo &&
    a.multiplier === b.multiplier &&
    a.coins === b.coins &&
    a.speedKmh === b.speedKmh &&
    a.countdown === b.countdown &&
    a.question?.question.id === b.question?.question.id &&
    a.lastExplanation === b.lastExplanation &&
    a.pickups.length === b.pickups.length &&
    a.questionsAsked === b.questionsAsked &&
    a.questionsCorrect === b.questionsCorrect
  );
}

function makeOptionTexture(text: string, letter: string): THREE.CanvasTexture {
  const canvas = document.createElement('canvas');
  canvas.width = 512;
  canvas.height = 384;
  const ctx = canvas.getContext('2d')!;
  const grad = ctx.createLinearGradient(0, 0, 0, canvas.height);
  grad.addColorStop(0, 'rgba(28,39,66,0.96)');
  grad.addColorStop(1, 'rgba(11,15,26,0.96)');
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.strokeStyle = 'rgba(108,92,231,0.95)';
  ctx.lineWidth = 8;
  ctx.strokeRect(8, 8, canvas.width - 16, canvas.height - 16);

  // Letter badge
  ctx.fillStyle = '#6c5ce7';
  ctx.beginPath();
  ctx.arc(canvas.width / 2, 70, 38, 0, Math.PI * 2);
  ctx.fill();
  ctx.fillStyle = '#fff';
  ctx.font = 'bold 44px "Inter", system-ui, sans-serif';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillText(letter, canvas.width / 2, 72);

  ctx.fillStyle = '#f5f7fb';
  ctx.font = 'bold 44px "Inter", system-ui, sans-serif';
  wrapText(ctx, text, canvas.width / 2, canvas.height / 2 + 50, canvas.width - 60, 52);

  const tex = new THREE.CanvasTexture(canvas);
  tex.anisotropy = 4;
  tex.needsUpdate = true;
  return tex;
}

function makeBannerMesh(text: string): { mesh: THREE.Mesh; texture: THREE.CanvasTexture } {
  const canvas = document.createElement('canvas');
  canvas.width = 1024;
  canvas.height = 192;
  const ctx = canvas.getContext('2d')!;
  const grad = ctx.createLinearGradient(0, 0, canvas.width, 0);
  grad.addColorStop(0, 'rgba(108,92,231,0.95)');
  grad.addColorStop(1, 'rgba(0,184,148,0.95)');
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.strokeStyle = '#fff';
  ctx.lineWidth = 10;
  ctx.strokeRect(10, 10, canvas.width - 20, canvas.height - 20);

  ctx.fillStyle = '#fff';
  ctx.font = 'bold 64px "Inter", system-ui, sans-serif';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.shadowColor = 'rgba(0,0,0,0.45)';
  ctx.shadowBlur = 8;
  wrapText(ctx, text, canvas.width / 2, canvas.height / 2, canvas.width - 80, 70);
  ctx.shadowBlur = 0;

  const tex = new THREE.CanvasTexture(canvas);
  tex.anisotropy = 4;
  tex.needsUpdate = true;
  const mat = new THREE.MeshBasicMaterial({ map: tex, transparent: true, side: THREE.DoubleSide });
  const geo = new THREE.PlaneGeometry(7.5, 1.2);
  const mesh = new THREE.Mesh(geo, mat);
  return { mesh, texture: tex };
}

function wrapText(
  ctx: CanvasRenderingContext2D,
  text: string,
  x: number,
  y: number,
  maxWidth: number,
  lineHeight: number,
) {
  const words = text.split(/\s+/);
  const lines: string[] = [];
  let current = '';
  for (const word of words) {
    const test = current ? `${current} ${word}` : word;
    if (ctx.measureText(test).width > maxWidth && current) {
      lines.push(current);
      current = word;
    } else {
      current = test;
    }
  }
  if (current) lines.push(current);
  const startY = y - ((lines.length - 1) * lineHeight) / 2;
  lines.forEach((line, i) => {
    ctx.fillText(line, x, startY + i * lineHeight);
  });
}

function makeBillboardTexture(text: string): THREE.CanvasTexture {
  const canvas = document.createElement('canvas');
  canvas.width = 640;
  canvas.height = 360;
  const ctx = canvas.getContext('2d')!;
  const grad = ctx.createLinearGradient(0, 0, canvas.width, canvas.height);
  grad.addColorStop(0, '#281e6e');
  grad.addColorStop(0.5, '#6c5ce7');
  grad.addColorStop(1, '#00b894');
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.strokeStyle = 'rgba(255,255,255,0.65)';
  ctx.lineWidth = 8;
  ctx.strokeRect(14, 14, canvas.width - 28, canvas.height - 28);
  ctx.fillStyle = '#fff097';
  ctx.font = 'bold 60px "Inter", system-ui, sans-serif';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.shadowColor = 'rgba(0,0,0,0.5)';
  ctx.shadowBlur = 12;
  wrapText(ctx, text, canvas.width / 2, canvas.height / 2, canvas.width - 60, 72);
  ctx.shadowBlur = 0;
  const tex = new THREE.CanvasTexture(canvas);
  tex.anisotropy = 4;
  tex.needsUpdate = true;
  return tex;
}
