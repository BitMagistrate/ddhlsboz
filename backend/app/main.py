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
from . import corpus as corpus_mod  # noqa: E402
from . import dashboard as dash  # noqa: E402
from . import exports as exports_mod  # noqa: E402
from . import mindmap as mindmap_mod  # noqa: E402
from . import observability as obs  # noqa: E402
from . import privacy as privacy_mod  # noqa: E402
from . import pushkin as pushkin_mod  # noqa: E402
from . import rag as rag_mod  # noqa: E402
from . import retrieval as retrieval_mod  # noqa: E402
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
async def curator_route(req: CuratorRequest) -> dict:
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
async def curator_mindmap(req: MindmapRequest) -> dict:
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


# ── Observability ────────────────────────────────────────────────────────────


@app.get("/metrics")
async def metrics_endpoint() -> Response:
    text = obs.get_metrics().render_prometheus()
    return Response(content=text, media_type="text/plain; version=0.0.4; charset=utf-8")
