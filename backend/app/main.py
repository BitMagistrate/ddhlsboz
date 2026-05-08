"""
ЧитАИ — backend (FastAPI + RAG + YandexGPT/GigaChat router).

LLM-роутер пытается сначала primary (по умолчанию YandexGPT 5 Pro), затем
secondary (GigaChat MAX), затем падает в детерминированный mock — чтобы
демо и CI работали без ключей. Ключи берутся из backend/.env (gitignored).
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

# Загружаем .env максимально рано, до создания FastAPI и инициализации роутера.
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

from fastapi import FastAPI, HTTPException  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from . import corpus as corpus_mod  # noqa: E402
from . import dashboard as dash  # noqa: E402
from . import rag as rag_mod  # noqa: E402
from . import trainer as trainer_mod  # noqa: E402
from .llm import get_router  # noqa: E402

app = FastAPI(
    title="ЧитАИ API",
    version="0.1.0",
    description="Демо-стенд ИИ-куратора русского культурного и образовательного контента",
)

# Disable CORS. Do not remove this for full-stack development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)


@app.get("/healthz")
async def healthz() -> dict:
    return {"status": "ok", "service": "chitai-api", "version": "0.1.0"}


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
        "disclaimer": "Демо-стенд. Все материалы — public domain. Партнёрства указаны как гипотезы и в работе.",
    }


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
async def search_corpus(q: str, limit: int = 5) -> dict:
    results = corpus_mod.search(q, limit=limit)
    return {
        "query": q,
        "count": len(results),
        "items": [s.to_dict() for s in results],
    }


class CuratorRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=300)
    weeks: int = Field(default=4, ge=1, le=8)


@app.post("/api/curator/route")
async def curator_route(req: CuratorRequest) -> dict:
    route = await rag_mod.build_route_async(req.query, weeks=req.weeks)
    return route.to_dict()


@app.get("/api/llm/status")
async def llm_status() -> dict:
    """Статус LLM-роутера: какие провайдеры сконфигурированы и активный primary.

    Сами ключи и токены НЕ возвращаются.
    """
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
        ]
    }


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
            "/api/llm/status",
            "/api/trainer/topics",
            "/api/trainer/quiz?subject=Литература",
            "/api/trainer/answer (POST)",
            "/api/dashboard/regional",
            "/api/dashboard/teacher",
            "/api/dashboard/partner",
            "/api/dashboard/kpi",
        ],
    }
