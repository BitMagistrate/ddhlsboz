"""
Карта тем: для запроса собирает граф «автор → темы → произведения», где
произведения и цитаты заземлены в hybrid retrieval. Прямой ответ на D2 из
master TODO и одна из «вау-фишек» презентации жюри.

Никаких визуализаций здесь — только структура. Frontend рисует SVG/D3.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from . import corpus as corpus_mod
from .retrieval import hybrid_search_sources


@dataclass
class MindMapNode:
    id: str
    label: str
    kind: str  # query | author | theme | book
    weight: float = 1.0
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "label": self.label,
            "kind": self.kind,
            "weight": round(self.weight, 3),
            "metadata": self.metadata,
        }


@dataclass
class MindMapEdge:
    source: str
    target: str
    label: str = ""
    weight: float = 1.0

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "target": self.target,
            "label": self.label,
            "weight": round(self.weight, 3),
        }


@dataclass
class MindMap:
    query: str
    nodes: list[MindMapNode]
    edges: list[MindMapEdge]
    citations: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
            "citations": list(self.citations),
        }


async def build_mindmap(query: str, *, limit: int = 6) -> MindMap:
    sources = await hybrid_search_sources(query, limit=limit)
    if not sources:
        sources = corpus_mod.CORPUS[:limit]
    nodes: list[MindMapNode] = []
    edges: list[MindMapEdge] = []
    citations: list[dict] = []

    root = MindMapNode(id="q::" + query[:60], label=query, kind="query", weight=1.0)
    nodes.append(root)

    authors_map: dict[str, MindMapNode] = {}
    themes_map: dict[str, MindMapNode] = {}
    theme_links: dict[str, set[str]] = defaultdict(set)

    for src in sources:
        author_id = "a::" + src.author
        if author_id not in authors_map:
            authors_map[author_id] = MindMapNode(
                id=author_id, label=src.author, kind="author", weight=1.0
            )
            nodes.append(authors_map[author_id])
            edges.append(MindMapEdge(source=root.id, target=author_id, label="автор"))
        book_id = "b::" + src.id
        nodes.append(
            MindMapNode(
                id=book_id,
                label=src.title,
                kind="book",
                weight=1.0,
                metadata={
                    "source_id": src.id,
                    "year": src.year,
                    "genre": src.genre,
                    "school_grade": src.school_grade,
                    "fragment": src.fragment,
                    "citation": src.citation,
                    "public_domain_url": src.public_domain_url,
                    "pushkin_card": src.pushkin_card,
                },
            )
        )
        edges.append(MindMapEdge(source=author_id, target=book_id, label="написал"))
        citations.append(
            {
                "source_id": src.id,
                "author": src.author,
                "title": src.title,
                "fragment": src.fragment,
                "citation": src.citation,
                "url": src.public_domain_url,
            }
        )
        for theme in src.ege_topics:
            theme_id = "t::" + theme
            if theme_id not in themes_map:
                themes_map[theme_id] = MindMapNode(
                    id=theme_id, label=theme, kind="theme", weight=1.0
                )
                nodes.append(themes_map[theme_id])
                edges.append(MindMapEdge(source=root.id, target=theme_id, label="тема"))
            theme_links[theme_id].add(book_id)
            edges.append(MindMapEdge(source=theme_id, target=book_id, label="раскрывается"))

    # вес тем = число связанных книг
    for tid, books in theme_links.items():
        themes_map[tid].weight = float(len(books))

    return MindMap(query=query, nodes=nodes, edges=edges, citations=citations)
