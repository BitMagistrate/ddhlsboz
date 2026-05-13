"""
Честный бенчмарк ретривала ЧитАИ (A3 из master TODO).

Эталонная выборка живёт прямо в коде (см. GOLDEN_SET): для каждого вопроса
известно множество приемлемых source_id. Это та же конструкция, что
используется в TREC и BEIR; для целей жюри её достаточно, чтобы продемон-
стрировать P@5 и MRR.

Метрики:
* Precision@k: доля релевантных среди top-k.
* Recall@k: доля найденных эталонных в top-k.
* MRR: средний обратный ранг первого верного попадания.
* Hit@k: доля запросов, где есть хотя бы одно попадание в top-k.

Запуск:
    python -m app.benchmark           # печатает таблицу + сохраняет в audit-стор.
    pytest tests/test_benchmark.py     # CI-проверка порогов P@5 ≥ 0.85.
"""

from __future__ import annotations

import asyncio
import datetime as _dt
import json
from dataclasses import dataclass, field

from .audit import BenchmarkRecord, get_benchmark_store
from .retrieval import hybrid_search_sources


@dataclass(frozen=True)
class GoldenItem:
    query: str
    relevant: tuple[str, ...]
    notes: str = ""


GOLDEN_SET: tuple[GoldenItem, ...] = (
    # ── Пушкин ──────────────────────────────────────────────────────────
    GoldenItem("Пушкин Евгений Онегин", ("pushkin_onegin",)),
    GoldenItem("капитанская дочка Пугачёв", ("pushkin_dochka",)),
    GoldenItem("Хочу понять Пушкина за 4 недели", ("pushkin_onegin", "pushkin_dochka")),
    GoldenItem("Береги честь смолоду", ("pushkin_dochka",)),
    # ── Лермонтов ───────────────────────────────────────────────────────
    GoldenItem("Лермонтов Печорин лишний человек", ("lermontov_geroi",)),
    GoldenItem("Герой нашего времени 9 класс", ("lermontov_geroi",)),
    # ── Гоголь ──────────────────────────────────────────────────────────
    GoldenItem("Мёртвые души помещики Чичиков", ("gogol_dushi",)),
    GoldenItem("Ревизор сатира чиновники", ("gogol_revizor",)),
    GoldenItem("маленький человек Шинель", ("gogol_shinel",)),
    # ── Достоевский ─────────────────────────────────────────────────────
    GoldenItem("Достоевский ЕГЭ психологический роман", ("dostoevsky_pn", "dostoevsky_idiot", "dostoevsky_kar")),
    GoldenItem("Преступление и наказание Раскольников", ("dostoevsky_pn",)),
    GoldenItem("красота спасёт мир Мышкин", ("dostoevsky_idiot",)),
    GoldenItem("Братья Карамазовы вера", ("dostoevsky_kar",)),
    # ── Толстой ─────────────────────────────────────────────────────────
    GoldenItem("Война и мир эпопея 1812", ("tolstoy_war",)),
    GoldenItem("Анна Каренина семья XIX века", ("tolstoy_anna",)),
    # ── Чехов ───────────────────────────────────────────────────────────
    GoldenItem("Вишнёвый сад смена эпох", ("chekhov_visnevy",)),
    GoldenItem("Палата 6 безразличие", ("chekhov_palata",)),
    # ── Серебряный век ──────────────────────────────────────────────────
    GoldenItem("Серебряный век 11 класс", ("blok_dvenadtsat", "ahmatova_rekviem", "tsvetaeva_moskva", "bunin_temnyealley", "mayakovsky_oblako")),
    GoldenItem("Блок Двенадцать революция", ("blok_dvenadtsat",)),
    GoldenItem("Ахматова Реквием память", ("ahmatova_rekviem",)),
    GoldenItem("Цветаева Москва лирика", ("tsvetaeva_moskva",)),
    GoldenItem("Маяковский футуризм облако в штанах", ("mayakovsky_oblako",)),
    GoldenItem("Бунин любовь эмиграция", ("bunin_temnyealley",)),
    # ── XIX век: социальные романы ──────────────────────────────────────
    GoldenItem("Тургенев Базаров нигилизм", ("turgenev_otcy",)),
    GoldenItem("Обломов барин лень", ("goncharov_oblomov",)),
    GoldenItem("Островский Гроза тёмное царство", ("ostrovsky_groza",)),
    GoldenItem("Салтыков-Щедрин Глупов сатира", ("saltykov_history_one_city",)),
    # ── История ─────────────────────────────────────────────────────────
    GoldenItem("Карамзин история Россия", ("karamzin_history",)),
    GoldenItem("Соловьёв колонизация русская история", ("solovyev_history",)),
    GoldenItem("Ключевский лекции историография", ("klyuchevsky_kurs",)),
    # ── XX век ──────────────────────────────────────────────────────────
    GoldenItem("Булгаков Мастер и Маргарита", ("bulgakov_master",)),
    GoldenItem("Шолохов Тихий Дон казачество", ("sholokhov_tihiy",)),
    GoldenItem("Один день Ивана Денисовича лагерь", ("solzhenitsyn_ivan_denisovich",)),
    GoldenItem("Грибоедов Чацкий Горе от ума", ("griboedov_gore",)),
    GoldenItem("Крылов басни сатира", ("krylov_basni",)),
    # ── Литература народов России ───────────────────────────────────────
    GoldenItem("Тукай родной язык татарская поэзия", ("tukay_native",)),
    GoldenItem("Мустай Карим долгое детство башкирская проза", ("karim_long_long",)),
    GoldenItem("Олонхо якутский эпос", ("olonkho_djurulu",)),
    GoldenItem("Гамзатов журавли память", ("rasul_gamzatov",)),
    GoldenItem("Айтматов манкурт память", ("aitmatov_kassandra",)),
    GoldenItem("Искандер Сандро Чегем", ("iskander_sandro",)),
    # ── Тематические запросы (multi-relevant) ───────────────────────────
    GoldenItem("лишний человек русская литература", ("lermontov_geroi", "pushkin_onegin", "goncharov_oblomov")),
    GoldenItem("маленький человек русская проза", ("gogol_shinel", "chekhov_palata")),
    GoldenItem("драма пьесы школьная программа", ("ostrovsky_groza", "chekhov_visnevy", "gogol_revizor", "griboedov_gore")),
    GoldenItem("Серебряный век поэзия", ("blok_dvenadtsat", "ahmatova_rekviem", "tsvetaeva_moskva", "mayakovsky_oblako")),
    GoldenItem("война в русской литературе", ("tolstoy_war", "sholokhov_tihiy", "rasul_gamzatov")),
    GoldenItem("ГУЛАГ репрессии", ("solzhenitsyn_ivan_denisovich", "ahmatova_rekviem")),
    GoldenItem("история России научная проза", ("karamzin_history", "solovyev_history", "klyuchevsky_kurs")),
)


@dataclass
class RetrievalScores:
    p_at_5: float = 0.0
    p_at_3: float = 0.0
    recall_at_5: float = 0.0
    mrr: float = 0.0
    hit_at_5: float = 0.0
    n_queries: int = 0
    misses: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "p_at_5": round(self.p_at_5, 4),
            "p_at_3": round(self.p_at_3, 4),
            "recall_at_5": round(self.recall_at_5, 4),
            "mrr": round(self.mrr, 4),
            "hit_at_5": round(self.hit_at_5, 4),
            "n_queries": self.n_queries,
            "misses": list(self.misses),
        }


async def evaluate(golden: tuple[GoldenItem, ...] = GOLDEN_SET, k: int = 5) -> RetrievalScores:
    if not golden:
        return RetrievalScores()
    p5_total = 0.0
    p3_total = 0.0
    recall_total = 0.0
    mrr_total = 0.0
    hit_total = 0.0
    misses: list[str] = []
    for item in golden:
        sources = await hybrid_search_sources(item.query, limit=k)
        ids = [s.id for s in sources]
        relevant_set = set(item.relevant)
        n_rel = len(relevant_set)
        # P@5 / P@3
        top5_hits = sum(1 for sid in ids[:5] if sid in relevant_set)
        top3_hits = sum(1 for sid in ids[:3] if sid in relevant_set)
        p5_total += top5_hits / 5
        p3_total += top3_hits / 3
        # Recall@5
        recall_total += (top5_hits / n_rel) if n_rel else 0.0
        # MRR
        rr = 0.0
        for rank, sid in enumerate(ids, start=1):
            if sid in relevant_set:
                rr = 1.0 / rank
                break
        mrr_total += rr
        # Hit@5
        hit_total += 1 if top5_hits > 0 else 0
        if top5_hits == 0:
            misses.append(f"{item.query} -> got {ids}")
    n = len(golden)
    return RetrievalScores(
        p_at_5=p5_total / n,
        p_at_3=p3_total / n,
        recall_at_5=recall_total / n,
        mrr=mrr_total / n,
        hit_at_5=hit_total / n,
        n_queries=n,
        misses=misses,
    )


def record_run(scores: RetrievalScores, *, notes: str = "") -> BenchmarkRecord:
    rec = BenchmarkRecord(
        ts=_dt.datetime.now(_dt.UTC).isoformat(timespec="seconds"),
        metrics=scores.to_dict(),
        notes=notes,
    )
    get_benchmark_store().add(rec)
    return rec


def main() -> int:
    scores = asyncio.run(evaluate())
    rec = record_run(scores, notes="cli")
    print(json.dumps(rec.to_dict(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
