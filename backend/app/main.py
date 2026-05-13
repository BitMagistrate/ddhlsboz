"""
ЧитАИ — backend (FastAPI + RAG + YandexGPT/GigaChat router).

LLM-роутер пытается сначала primary (по умолчанию YandexGPT 5 Pro), затем
secondary (GigaChat MAX), затем падает в детерминированный mock — чтобы
демо и CI работали без ключей. Ключи берутся из backend/.env (gitignored).

Сверху — middleware наблюдаемости (request_id, latency, /metrics) и фильтр
безопасности (red-team). Эндпоинты ниже сгруппированы:
* corpus  — корпус и поиск (включая гибридный BM25+vector)
* curator — RAG-маршрут, mind map, экспорт
* trainer — тест-тренажёр
* srs     — SM-2 карточки
* safety  — экранирование и журнал отказов
* privacy — 152-ФЗ (consent / export / forget)
* audit   — model card, реестр промптов, бенчмарк
* pushkin — каталог событий по Пушкинской карте
* tts     — Yandex SpeechKit с mock-фолбэком
* dashboards — для региональных партнёров и учителей
"""

from __future__ import annotations

import datetime as _dt
import logging
import os
import time

from dotenv import load_dotenv

# Загружаем .env максимально рано, до создания FastAPI и инициализации роутера.
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

from fastapi import FastAPI, HTTPException, Request, Response  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from . import audit as audit_mod  # noqa: E402
from . import benchmark as bench_mod  # noqa: E402
from . import challenge as challenge_mod  # noqa: E402
from . import characters as characters_mod  # noqa: E402
from . import corpus as corpus_mod  # noqa: E402
from . import dashboard as dash  # noqa: E402
from . import exam_plan as exam_plan_mod  # noqa: E402
from . import exports as exports_mod  # noqa: E402
from . import i18n as i18n_mod  # noqa: E402
from . import literary_calendar as calendar_mod  # noqa: E402
from . import mindmap as mindmap_mod  # noqa: E402
from . import observability as obs  # noqa: E402
from . import privacy as privacy_mod  # noqa: E402
from . import pushkin as pushkin_mod  # noqa: E402
from . import quickread as quickread_mod  # noqa: E402
from . import quote_game as quote_game_mod  # noqa: E402
from . import rag as rag_mod  # noqa: E402
from . import ratelimit as ratelimit_mod  # noqa: E402
from . import retrieval as retrieval_mod  # noqa: E402
from . import roi as roi_mod  # noqa: E402
from . import safety as safety_mod  # noqa: E402
from . import srs as srs_mod  # noqa: E402
from . import trainer as trainer_mod  # noqa: E402
from . import tts as tts_mod  # noqa: E402
from .llm import get_router  # noqa: E402
from .schemas import validate_curator_route  # noqa: E402

# Логи и метрики настраиваются один раз при импорте модуля.
obs.configure_logging(level=logging.INFO, json=True)


app = FastAPI(
    title="ЧитАИ API",
    version="0.2.0",
    description="ИИ-куратор русского культурного и образовательного контента (RAG + 152-ФЗ)",
)

# Disable CORS. Do not remove this for full-stack development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)


@app.middleware("http")
async def _observability_middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
    """Прозрачный сбор request_id, latency и кодов ответа для /metrics."""
    request_id = request.headers.get("x-request-id") or obs.new_request_id()
    obs.set_request_id(request_id)
    metrics = obs.get_metrics()
    started = time.perf_counter()
    response: Response | None = None
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    finally:
        elapsed = time.perf_counter() - started
        labels = {
            "method": request.method,
            "path": request.url.path,
            "status": str(status_code),
        }
        metrics.counter("chitai_requests_total", 1.0, labels)
        metrics.observe("chitai_request_latency_seconds", elapsed, labels)
        if response is not None:
            response.headers["X-Request-Id"] = request_id


# ── Service / discoverability ────────────────────────────────────────────────


@app.get("/healthz")
async def healthz() -> dict:
    return {"status": "ok", "service": "chitai-api", "version": "0.2.0"}


@app.get("/api/info")
async def info() -> dict:
    return {
        "name": "ЧитАИ",
        "tagline": "ИИ-куратор русского культурного и образовательного контента",
        "stack": [
            "YandexGPT 5 Pro",
            "GigaChat MAX",
            "Kandinsky 3.1",
            "Yandex SpeechKit",
            "PostgreSQL + pgvector",
            "Yandex Cloud (РФ)",
        ],
        "audiences": [
            "Молодёжь 14–22 (Пушкинская карта)",
            "Учителя",
            "Библиотеки",
            "Музеи",
            "Региональные ведомства",
        ],
        "compliance": [
            "152-ФЗ",
            "44-ФЗ",
            "Указ Президента №490",
            "Нацпроект «Культура»",
            "Нацпроект «Образование»",
        ],
        "disclaimer": (
            "Демо-стенд. Все материалы — public domain. "
            "Партнёрства указаны как гипотезы и в работе."
        ),
    }


@app.get("/")
async def root() -> dict:
    return {
        "service": "chitai-api",
        "docs": "/docs",
        "endpoints": [
            "/api/info",
            "/api/corpus/sources",
            "/api/corpus/search?q=Пушкин",
            "/api/curator/route (POST)",
            "/api/curator/example-queries",
            "/api/curator/mindmap (POST)",
            "/api/curator/export/markdown (POST)",
            "/api/curator/export/ics (POST)",
            "/api/llm/status",
            "/api/trainer/topics",
            "/api/trainer/quiz?subject=Литература",
            "/api/trainer/answer (POST)",
            "/api/srs/upsert (POST)",
            "/api/srs/due?user_id=demo",
            "/api/srs/review (POST)",
            "/api/srs/from-route (POST)",
            "/api/safety/screen?q=…",
            "/api/safety/refusals",
            "/api/privacy/policy",
            "/api/privacy/consent (POST)",
            "/api/privacy/export?user_id=…",
            "/api/privacy/forget (POST)",
            "/api/audit/model-card",
            "/api/audit/prompts",
            "/api/audit/evaluation",
            "/api/audit/run-benchmark (POST)",
            "/api/pushkin/events",
            "/api/pushkin/recommend (POST)",
            "/api/tts/synth (POST)",
            "/api/dashboard/regional",
            "/api/dashboard/teacher",
            "/api/dashboard/partner",
            "/api/dashboard/kpi",
            "/metrics",
        ],
    }


# ── Corpus ───────────────────────────────────────────────────────────────────


@app.get("/api/corpus/sources")
async def list_sources() -> dict:
    return {
        "count": len(corpus_mod.CORPUS),
        "items": [s.to_dict() for s in corpus_mod.CORPUS],
    }


@app.get("/api/corpus/source/{source_id}")
async def get_source(source_id: str) -> dict:
    s = corpus_mod.by_id(source_id)
    if not s:
        raise HTTPException(status_code=404, detail="source_not_found")
    return s.to_dict()


@app.get("/api/corpus/search")
async def search_corpus(q: str, limit: int = 5, hybrid: bool = True) -> dict:
    if hybrid:
        sources = await retrieval_mod.hybrid_search_sources(q, limit=limit)
    else:
        sources = corpus_mod.search(q, limit=limit)
    return {
        "query": q,
        "engine": "hybrid" if hybrid else "keyword",
        "count": len(sources),
        "items": [s.to_dict() for s in sources],
    }


# ── Curator (RAG) ────────────────────────────────────────────────────────────


class CuratorRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=300)
    weeks: int = Field(default=4, ge=1, le=8)


@app.post("/api/curator/route")
async def curator_route(req: CuratorRequest, request: Request) -> dict:
    async def handler() -> dict:
        verdict = safety_mod.screen(req.query)
        if verdict.verdict == safety_mod.SafetyVerdict.REFUSE:
            obs.get_metrics().counter(
                "chitai_safety_refusals_total", 1.0, {"category": verdict.category}
            )
            payload = {
                "query": req.query,
                "summary": verdict.reason,
                "weeks": [],
                "sources": [],
                "disclaimer": (
                    "Запрос отклонён политикой безопасности ЧитАИ. "
                    "Решение задокументировано в /api/audit/model-card."
                ),
                "llm_provider": "safety_filter",
                "llm_model": "rule-based-v1",
                "safety": verdict.to_dict(),
            }
            return validate_curator_route(payload)
        if verdict.verdict == safety_mod.SafetyVerdict.CLARIFY:
            payload = {
                "query": req.query,
                "summary": verdict.reason,
                "weeks": [],
                "sources": [],
                "disclaimer": "Уточните формулировку запроса.",
                "llm_provider": "safety_filter",
                "llm_model": "rule-based-v1",
                "safety": verdict.to_dict(),
            }
            return validate_curator_route(payload)

        route = await rag_mod.build_route_async(req.query, weeks=req.weeks)
        obs.get_metrics().counter(
            "chitai_curator_routes_total",
            1.0,
            {"provider": route.llm_provider, "weeks": str(len(route.weeks))},
        )
        return validate_curator_route({**route.to_dict(), "safety": verdict.to_dict()})

    return await ratelimit_mod.enforce(request, req.model_dump(), handler, cost=1.0)


@app.get("/api/llm/status")
async def llm_status() -> dict:
    """Статус LLM-роутера. Сами ключи и токены НЕ возвращаются."""
    router = get_router()
    return await router.status()


@app.get("/api/curator/example-queries")
async def example_queries() -> dict:
    return {
        "items": [
            "Хочу понять Пушкина за 4 недели",
            "Маршрут по Серебряному веку для 11 класса",
            "Подготовка к ЕГЭ по Достоевскому",
            "История России XIX века для подростка",
            "Толстой и Чехов: эпопея и драма",
            "Лермонтов и тип лишнего человека",
            "Литература народов России для 11 класса",
            "Башкирская и якутская проза в школе",
        ]
    }


class MindmapRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=300)
    limit: int = Field(default=6, ge=2, le=12)


@app.post("/api/curator/mindmap")
async def curator_mindmap(req: MindmapRequest, request: Request) -> dict:
    async def handler() -> dict:
        verdict = safety_mod.screen(req.query)
        if verdict.verdict == safety_mod.SafetyVerdict.REFUSE:
            return {
                "query": req.query,
                "nodes": [],
                "edges": [],
                "citations": [],
                "safety": verdict.to_dict(),
            }
        mm = await mindmap_mod.build_mindmap(req.query, limit=req.limit)
        return {**mm.to_dict(), "safety": verdict.to_dict()}

    return await ratelimit_mod.enforce(request, req.model_dump(), handler, cost=1.0)


class ExportRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=300)
    weeks: int = Field(default=4, ge=1, le=8)
    start_date: str | None = Field(default=None, description="YYYY-MM-DD; по умолчанию — сегодня")


@app.post("/api/curator/export/markdown")
async def export_markdown(req: ExportRequest) -> Response:
    route = await rag_mod.build_route_async(req.query, weeks=req.weeks)
    text = exports_mod.route_to_markdown(route.to_dict())
    fname = f"chitai-route-{exports_mod.slug(req.query)}.md"
    return Response(
        content=text,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={fname}"},
    )


@app.post("/api/curator/export/ics")
async def export_ics(req: ExportRequest) -> Response:
    route = await rag_mod.build_route_async(req.query, weeks=req.weeks)
    start_date: _dt.date | None = None
    if req.start_date:
        try:
            start_date = _dt.date.fromisoformat(req.start_date)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="invalid_start_date") from exc
    ics = exports_mod.route_to_ics(route.to_dict(), start_date=start_date)
    fname = f"chitai-route-{exports_mod.slug(req.query)}.ics"
    return Response(
        content=ics,
        media_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={fname}"},
    )


# ── Trainer ──────────────────────────────────────────────────────────────────


@app.get("/api/trainer/topics")
async def trainer_topics() -> dict:
    return {"topics": trainer_mod.list_topics()}


@app.get("/api/trainer/quiz")
async def trainer_quiz(subject: str = "Литература", limit: int = 8) -> dict:
    qs = trainer_mod.by_subject(subject, limit=limit)
    if not qs:
        raise HTTPException(status_code=404, detail="no_questions_for_subject")
    return {
        "subject": subject,
        "count": len(qs),
        "items": [q.to_dict(with_answer=False) for q in qs],
    }


class AnswerRequest(BaseModel):
    question_id: str
    answer_index: int = Field(..., ge=0, le=10)


@app.post("/api/trainer/answer")
async def trainer_answer(req: AnswerRequest) -> dict:
    result = trainer_mod.check_answer(req.question_id, req.answer_index)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


# Маппинг book_id (произведение из публичного корпуса) → source_id, к которому
# привязаны вопросы тренажёра ЕГЭ. Используется фронтендом игры
# Brain Dash для пула вопросов по выбранному произведению.
BOOK_TO_SOURCE: dict[str, str] = {
    "capitanskaya-dochka": "pushkin_dochka",
    "evgeniy-onegin": "pushkin_onegin",
    "geroy-nashego-vremeni": "lermontov_geroi",
    "myortvye-dushi": "gogol_dushi",
    "shinel": "gogol_shinel",
    "prestuplenie-i-nakazanie": "dostoevsky_pn",
    "voyna-i-mir": "tolstoy_war",
}


def _quiz_pool_for(book_id: str | None) -> list[trainer_mod.Question]:
    """Подобрать пул вопросов из тренажёра под произведение.

    Если book_id известен — фильтруем по source_id; иначе — все вопросы
    предмета "Литература". Это временный мост, пока не подключён upload
    pipeline (EX1–EX5 в ROADMAP).
    """
    if not book_id:
        return trainer_mod.by_subject("Литература", limit=50)
    source_id = BOOK_TO_SOURCE.get(book_id)
    if source_id is None:
        return trainer_mod.by_subject("Литература", limit=50)
    pool = [q for q in trainer_mod.QUESTIONS if q.source_id == source_id]
    if not pool:
        return trainer_mod.by_subject("Литература", limit=50)
    return pool


@app.get("/api/study/quiz")
async def study_quiz(
    konspekt_id: str | None = None,
    book_id: str | None = None,
    count: int = 5,
) -> dict:
    """Quiz для игры Brain Dash и mode «Учёба».

    Контракт: один из (konspekt_id, book_id) обязателен. После реализации
    upload pipeline (EX1–EX5 в `docs/ROADMAP.md`) `konspekt_id` будет
    указывать на пользовательский конспект; сейчас используем `book_id`
    как ключ к публичному корпусу (см. BOOK_TO_SOURCE).
    """
    if konspekt_id is None and book_id is None:
        raise HTTPException(
            status_code=400,
            detail="Either konspekt_id or book_id is required",
        )
    safe_count = max(1, min(int(count), 20))
    # До подключения user-konspekt'а оба ключа разрешаются в книгу.
    effective_book = book_id or konspekt_id
    pool = _quiz_pool_for(effective_book)
    if not pool:
        raise HTTPException(status_code=404, detail="quiz_pool_empty")

    questions: list[dict] = []
    for i, q in enumerate(pool[:safe_count]):
        question_id = f"q-{i}-{q.id}"
        questions.append(
            {
                "id": question_id,
                "text": q.question,
                "options": [
                    {"id": f"{question_id}-opt-{j}", "text": opt}
                    for j, opt in enumerate(q.options)
                ],
                "correctOptionId": f"{question_id}-opt-{q.correct_index}",
                "explanation": q.explanation,
                "difficulty": 2,
            }
        )
    return {
        "questions": questions,
        "konspekt_id": konspekt_id,
        "book_id": book_id,
    }


# ── Spaced Repetition (SRS / SM-2) ───────────────────────────────────────────


class SrsCardIn(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=80)
    card_id: str = Field(..., min_length=1, max_length=80)
    front: str = Field(..., min_length=1, max_length=400)
    back: str = Field(..., min_length=1, max_length=2000)
    tags: list[str] = Field(default_factory=list)


@app.post("/api/srs/upsert")
async def srs_upsert(card: SrsCardIn) -> dict:
    new_card = srs_mod.FlashCard(
        card_id=card.card_id,
        user_id=card.user_id,
        front=card.front,
        back=card.back,
        tags=list(card.tags),
    )
    saved = srs_mod.get_store().upsert(new_card)
    return saved.to_dict()


@app.get("/api/srs/due")
async def srs_due(user_id: str, limit: int = 20) -> dict:
    cards = srs_mod.get_store().due(user_id, limit=limit)
    return {"user_id": user_id, "count": len(cards), "items": [c.to_dict() for c in cards]}


class SrsReviewRequest(BaseModel):
    card_id: str = Field(..., min_length=1, max_length=80)
    quality: int = Field(..., ge=0, le=5)


@app.post("/api/srs/review")
async def srs_review(req: SrsReviewRequest) -> dict:
    try:
        card = srs_mod.get_store().review(req.card_id, req.quality)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="card_not_found") from exc
    return card.to_dict()


class SrsFromRouteRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=80)
    query: str = Field(..., min_length=1, max_length=300)
    weeks: int = Field(default=4, ge=1, le=8)


@app.post("/api/srs/from-route")
async def srs_from_route(req: SrsFromRouteRequest) -> dict:
    route = await rag_mod.build_route_async(req.query, weeks=req.weeks)
    store = srs_mod.get_store()
    created: list[dict] = []
    for w in route.weeks:
        card = srs_mod.make_card_from_route_week(req.user_id, w.to_dict())
        store.upsert(card)
        created.append(card.to_dict())
    return {"user_id": req.user_id, "query": req.query, "count": len(created), "items": created}


# ── Safety ───────────────────────────────────────────────────────────────────


@app.get("/api/safety/screen")
async def safety_screen(q: str) -> dict:
    return safety_mod.screen(q).to_dict()


@app.get("/api/safety/refusals")
async def safety_refusals() -> dict:
    items = [r.to_dict() for r in safety_mod.get_refusal_log().all()]
    return {"count": len(items), "items": items}


# ── Privacy (152-ФЗ) ─────────────────────────────────────────────────────────


@app.get("/api/privacy/policy")
async def privacy_policy() -> dict:
    return privacy_mod.policy_summary()


class ConsentRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=80)
    purpose: str = Field(..., min_length=2, max_length=80)
    granted: bool = True
    notes: str = ""


@app.post("/api/privacy/consent")
async def privacy_consent(req: ConsentRequest) -> dict:
    rec = privacy_mod.get_store().set_consent(
        req.user_id, req.purpose, granted=req.granted, notes=req.notes
    )
    return rec.to_dict()


@app.get("/api/privacy/consent")
async def privacy_consent_list(user_id: str) -> dict:
    items = privacy_mod.get_store().list_consents(user_id)
    return {"user_id": user_id, "count": len(items), "items": [i.to_dict() for i in items]}


@app.get("/api/privacy/export")
async def privacy_export(user_id: str) -> dict:
    return privacy_mod.get_store().export(user_id)


class ForgetRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=80)


@app.post("/api/privacy/forget")
async def privacy_forget(req: ForgetRequest) -> dict:
    return privacy_mod.get_store().forget(req.user_id)


# ── Audit (модель-карточка, реестр промптов, бенчмарк) ───────────────────────


@app.get("/api/audit/model-card")
async def audit_model_card() -> dict:
    return audit_mod.get_model_card().to_dict()


@app.get("/api/audit/prompts")
async def audit_prompts() -> dict:
    items = [p.to_dict() for p in audit_mod.get_prompts()]
    return {"count": len(items), "items": items}


@app.get("/api/audit/evaluation")
async def audit_evaluation() -> dict:
    rec = audit_mod.get_benchmark_store().latest()
    history = [r.to_dict() for r in audit_mod.get_benchmark_store().all()]
    return {"latest": rec.to_dict() if rec else None, "history": history}


@app.post("/api/audit/run-benchmark")
async def audit_run_benchmark() -> dict:
    scores = await bench_mod.evaluate()
    rec = bench_mod.record_run(scores, notes="api")
    return rec.to_dict()


# ── Pushkin Card ─────────────────────────────────────────────────────────────


@app.get("/api/pushkin/events")
async def pushkin_events(region: str | None = None, theme: str | None = None) -> dict:
    if region:
        items = pushkin_mod.by_region(region)
    elif theme:
        items = pushkin_mod.by_theme(theme)
    else:
        items = pushkin_mod.list_events()
    return {"count": len(items), "items": [e.to_dict() for e in items]}


class PushkinRecommendRequest(BaseModel):
    book_ids: list[str] = Field(default_factory=list)
    region: str | None = None
    limit: int = Field(default=6, ge=1, le=20)


@app.post("/api/pushkin/recommend")
async def pushkin_recommend(req: PushkinRecommendRequest) -> dict:
    items = pushkin_mod.recommend(req.book_ids, region=req.region, limit=req.limit)
    return {"count": len(items), "items": [e.to_dict() for e in items]}


# ── TTS ──────────────────────────────────────────────────────────────────────


class TtsRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=4000)
    voice: str = Field(default="ermil", max_length=20)
    emotion: str = Field(default="neutral", max_length=20)


@app.post("/api/tts/synth")
async def tts_synth(req: TtsRequest) -> Response:
    try:
        result = await tts_mod.synth(req.text, voice=req.voice, emotion=req.emotion)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return Response(
        content=result.audio_bytes,
        media_type=result.mime,
        headers={
            "X-TTS-Provider": result.provider,
            "X-TTS-Voice": result.voice,
            "X-TTS-Duration-S": str(round(result.duration_s, 2)),
        },
    )


# ── Dashboards ───────────────────────────────────────────────────────────────


@app.get("/api/dashboard/regional")
async def dashboard_regional() -> dict:
    return dash.regional_dashboard()


@app.get("/api/dashboard/teacher")
async def dashboard_teacher() -> dict:
    return dash.teacher_dashboard()


@app.get("/api/dashboard/partner")
async def dashboard_partner() -> dict:
    return dash.partner_dashboard()


@app.get("/api/dashboard/kpi")
async def dashboard_kpi() -> dict:
    return {"items": dash.kpi_summary()}


# ── Characters (C-2: «Спроси Раскольникова») ─────────────────────────────────


class CharacterAskRequest(BaseModel):
    character: str = Field(..., min_length=1, max_length=64)
    question: str = Field(..., min_length=1, max_length=500)


@app.get("/api/characters")
async def characters_list() -> dict:
    return {"items": characters_mod.list_characters()}


@app.post("/api/characters/ask")
async def character_ask(req: CharacterAskRequest, request: Request) -> dict:
    async def handler() -> dict:
        verdict = safety_mod.screen(req.question)
        if verdict.verdict == safety_mod.SafetyVerdict.REFUSE:
            return {
                "character": req.character,
                "question": req.question,
                "answer": verdict.reason,
                "citations": [],
                "grounded": False,
                "safety": verdict.to_dict(),
            }
        try:
            ans = await characters_mod.ask_character(req.character, req.question)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return {
            "character": ans.character,
            "question": ans.question,
            "answer": ans.answer,
            "citations": ans.citations,
            "grounded": ans.grounded,
            "book": ans.book,
            "safety": verdict.to_dict(),
        }

    return await ratelimit_mod.enforce(request, req.model_dump(), handler, cost=1.0)


# ── Challenge «100 книг» ─────────────────────────────────────────────────────


class ChallengeMarkRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=64)
    book_id: str = Field(..., min_length=1, max_length=64)


@app.get("/api/challenge/books")
async def challenge_books() -> dict:
    return {"target": 100, "items": challenge_mod.get_books()}


@app.get("/api/challenge/progress")
async def challenge_progress(user_id: str) -> dict:
    p = challenge_mod.get_progress(user_id)
    return {
        "user_id": p.user_id,
        "target": p.target,
        "completed": p.completed,
        "completed_count": len(p.completed),
        "earned_badges": p.earned_badges,
        "next_milestone": p.next_milestone,
    }


@app.post("/api/challenge/mark-read")
async def challenge_mark_read(req: ChallengeMarkRequest) -> dict:
    try:
        p = challenge_mod.mark_read(req.user_id, req.book_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "user_id": p.user_id,
        "target": p.target,
        "completed": p.completed,
        "completed_count": len(p.completed),
        "earned_badges": p.earned_badges,
        "next_milestone": p.next_milestone,
    }


@app.post("/api/challenge/unmark")
async def challenge_unmark(req: ChallengeMarkRequest) -> dict:
    p = challenge_mod.unmark(req.user_id, req.book_id)
    return {
        "user_id": p.user_id,
        "target": p.target,
        "completed": p.completed,
        "completed_count": len(p.completed),
        "earned_badges": p.earned_badges,
        "next_milestone": p.next_milestone,
    }


# ── ЕГЭ-план ─────────────────────────────────────────────────────────────────


class ExamPlanRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=64)
    exam_date: str = Field(..., min_length=8, max_length=12)
    level: int = Field(default=5, ge=1, le=10)


@app.post("/api/exam/plan")
async def exam_plan(req: ExamPlanRequest, request: Request) -> dict:
    async def handler() -> dict:
        try:
            plan = exam_plan_mod.build_plan(req.user_id, req.exam_date, level=req.level)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return exam_plan_mod.plan_to_dict(plan)

    return await ratelimit_mod.enforce(request, req.model_dump(), handler, cost=1.0)


# ── Quick read ───────────────────────────────────────────────────────────────


@app.get("/api/quickread/{book_id}")
async def quickread_get(book_id: str) -> dict:
    try:
        return quickread_mod.to_dict(quickread_mod.build(book_id))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# ── Quote game ───────────────────────────────────────────────────────────────


class QuoteGameAnswer(BaseModel):
    round_id: str = Field(..., min_length=1, max_length=64)
    answer_book_id: str = Field(..., min_length=1, max_length=64)


@app.post("/api/quote-game/new")
async def quote_game_new(seed: int | None = None) -> dict:
    return quote_game_mod.round_to_dict(quote_game_mod.new_round(seed=seed))


@app.post("/api/quote-game/check")
async def quote_game_check(req: QuoteGameAnswer) -> dict:
    try:
        return quote_game_mod.check(req.round_id, req.answer_book_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# ── Литературный календарь ───────────────────────────────────────────────────


@app.get("/api/calendar/today")
async def calendar_today() -> dict:
    items = calendar_mod.today_entries()
    return {"count": len(items), "items": [calendar_mod.entry_to_dict(e) for e in items]}


@app.get("/api/calendar/month/{month}")
async def calendar_month(month: int) -> dict:
    if month < 1 or month > 12:
        raise HTTPException(status_code=400, detail="month must be 1..12")
    items = calendar_mod.by_month(month)
    return {"count": len(items), "items": [calendar_mod.entry_to_dict(e) for e in items]}


# ── B2G ROI калькулятор ──────────────────────────────────────────────────────


class RoiRequest(BaseModel):
    students: int = Field(default=roi_mod.DEFAULT_STUDENTS, ge=0, le=1_000_000)
    teachers: int = Field(default=roi_mod.DEFAULT_TEACHERS, ge=0, le=100_000)
    teacher_rate_rub_per_hour: float = Field(
        default=roi_mod.DEFAULT_TEACHER_RATE_RUB_PER_HOUR, ge=0
    )
    hours_saved_per_teacher_per_week: float = Field(
        default=roi_mod.DEFAULT_HOURS_SAVED_PER_TEACHER_PER_WEEK, ge=0
    )
    weeks_per_year: int = Field(default=roi_mod.DEFAULT_WEEKS_PER_YEAR, ge=1, le=52)
    base_fee_per_year: int = Field(default=roi_mod.DEFAULT_BASE_FEE_PER_YEAR, ge=0)
    variable_fee_per_student_per_year: int = Field(
        default=roi_mod.DEFAULT_VARIABLE_FEE_PER_STUDENT_PER_YEAR, ge=0
    )
    expected_ege_points_gain: float = Field(
        default=roi_mod.DEFAULT_EXPECTED_EGE_POINTS_GAIN, ge=0, le=50
    )
    token_cost_per_student_per_month: float = Field(
        default=roi_mod.DEFAULT_TOKEN_COST_PER_STUDENT_PER_MONTH, ge=0
    )


@app.post("/api/roi/compute")
async def roi_compute(req: RoiRequest) -> dict:
    return roi_mod.compute(roi_mod.RoiInputs(**req.model_dump()))


# ── i18n ─────────────────────────────────────────────────────────────────────


@app.get("/api/i18n")
async def i18n_get(locale: str = "ru") -> dict:
    return {"locale": locale, "strings": i18n_mod.resolve(locale)}


@app.get("/api/i18n/locales")
async def i18n_locales() -> dict:
    return i18n_mod.locales()


# ── Observability ────────────────────────────────────────────────────────────


@app.get("/metrics")
async def metrics_endpoint() -> Response:
    text = obs.get_metrics().render_prometheus()
    return Response(content=text, media_type="text/plain; version=0.0.4; charset=utf-8")
