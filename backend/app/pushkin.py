"""
Каталог событий «Пушкинской карты».

Цель — закрыть E2 из master TODO: маршрут должен подсказывать конкретные
мероприятия, доступные по карте (14–22 года, до ~5000 ₽ в год). Сейчас в
демо это in-memory выборка ~30 событий по регионам и темам, но контракт
функций совпадает с тем, что будет жить в Postgres-таблице с реальными
данными от партнёров (filia.ru, культура.рф, Госуслуги Культура).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PushkinEvent:
    id: str
    title: str
    venue: str
    city: str
    region: str
    date: str
    price_rub: int
    age_min: int
    age_max: int
    themes: tuple[str, ...] = field(default_factory=tuple)
    book_ids: tuple[str, ...] = field(default_factory=tuple)
    booking_url: str = "https://www.culture.ru/pushkinskayacarta"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "venue": self.venue,
            "city": self.city,
            "region": self.region,
            "date": self.date,
            "price_rub": self.price_rub,
            "age_range": f"{self.age_min}–{self.age_max}",
            "themes": list(self.themes),
            "book_ids": list(self.book_ids),
            "booking_url": self.booking_url,
        }


CATALOG: list[PushkinEvent] = [
    PushkinEvent(
        id="evt-rgb-01",
        title="Лекция «Пушкин и его современники»",
        venue="Российская государственная библиотека",
        city="Москва",
        region="RU-MOW",
        date="2026-09-14",
        price_rub=350,
        age_min=14,
        age_max=22,
        themes=("Пушкин", "XIX век"),
        book_ids=("pushkin_onegin", "pushkin_dochka"),
    ),
    PushkinEvent(
        id="evt-rgb-02",
        title="Открытая лекция «Лермонтов и тип лишнего человека»",
        venue="Российская государственная библиотека",
        city="Москва",
        region="RU-MOW",
        date="2026-09-21",
        price_rub=350,
        age_min=14,
        age_max=22,
        themes=("Лермонтов", "XIX век"),
        book_ids=("lermontov_geroi",),
    ),
    PushkinEvent(
        id="evt-mxat-01",
        title="Спектакль «Гроза»",
        venue="Малый театр",
        city="Москва",
        region="RU-MOW",
        date="2026-10-05",
        price_rub=900,
        age_min=14,
        age_max=22,
        themes=("Драма", "Островский"),
        book_ids=("ostrovsky_groza",),
    ),
    PushkinEvent(
        id="evt-tretya-01",
        title="Экскурсия «Передвижники: реализм XIX века»",
        venue="Государственная Третьяковская галерея",
        city="Москва",
        region="RU-MOW",
        date="2026-09-28",
        price_rub=600,
        age_min=14,
        age_max=22,
        themes=("ИЗО", "Реализм", "XIX век"),
        book_ids=("turgenev_otcy", "tolstoy_war"),
    ),
    PushkinEvent(
        id="evt-cons-01",
        title="Концерт «Серебряный век в музыке»",
        venue="Большой зал консерватории",
        city="Москва",
        region="RU-MOW",
        date="2026-11-12",
        price_rub=1200,
        age_min=14,
        age_max=22,
        themes=("Серебряный век", "Музыка"),
        book_ids=("blok_dvenadtsat", "ahmatova_rekviem", "tsvetaeva_moskva"),
    ),
    PushkinEvent(
        id="evt-pushkinhouse-01",
        title="Литературная встреча «Достоевский: 200 лет»",
        venue="Музей Ф. М. Достоевского",
        city="Санкт-Петербург",
        region="RU-SPE",
        date="2026-10-20",
        price_rub=400,
        age_min=14,
        age_max=22,
        themes=("Достоевский", "XIX век"),
        book_ids=("dostoevsky_pn", "dostoevsky_kar"),
    ),
    PushkinEvent(
        id="evt-russmuseum-01",
        title="Экскурсия «Серебряный век. Русский музей»",
        venue="Государственный Русский музей",
        city="Санкт-Петербург",
        region="RU-SPE",
        date="2026-11-02",
        price_rub=550,
        age_min=14,
        age_max=22,
        themes=("Серебряный век", "ИЗО"),
        book_ids=("blok_dvenadtsat", "ahmatova_rekviem"),
    ),
    PushkinEvent(
        id="evt-kazan-01",
        title="Лекция «Тукай и татарская поэзия начала XX века»",
        venue="Национальная библиотека Республики Татарстан",
        city="Казань",
        region="RU-TA",
        date="2026-10-12",
        price_rub=300,
        age_min=14,
        age_max=22,
        themes=("Литература народов России", "Серебряный век"),
        book_ids=("tukay_native", "blok_dvenadtsat"),
    ),
    PushkinEvent(
        id="evt-ufa-01",
        title="Литературная встреча «Мустай Карим: голос Башкортостана»",
        venue="Национальная библиотека им. А.-З. Валиди",
        city="Уфа",
        region="RU-BA",
        date="2026-11-15",
        price_rub=300,
        age_min=14,
        age_max=22,
        themes=("Литература народов России", "XX век"),
        book_ids=("karim_long_long",),
    ),
    PushkinEvent(
        id="evt-yakutsk-01",
        title="Театральная постановка «Олонхо»",
        venue="Театр Олонхо",
        city="Якутск",
        region="RU-SA",
        date="2026-12-04",
        price_rub=500,
        age_min=14,
        age_max=22,
        themes=("Литература народов России", "Эпос"),
        book_ids=("olonkho_djurulu",),
    ),
    PushkinEvent(
        id="evt-novosib-01",
        title="Лекция «Сибирские мотивы в русской литературе»",
        venue="Новосибирская областная научная библиотека",
        city="Новосибирск",
        region="RU-NVS",
        date="2026-10-18",
        price_rub=300,
        age_min=14,
        age_max=22,
        themes=("Сибирь", "XIX век"),
        book_ids=("solovyev_history", "tolstoy_war"),
    ),
    PushkinEvent(
        id="evt-vladivostok-01",
        title="Лекция «Дальний Восток глазами русских писателей»",
        venue="Приморская краевая библиотека им. А. М. Горького",
        city="Владивосток",
        region="RU-PRI",
        date="2026-11-09",
        price_rub=200,
        age_min=14,
        age_max=22,
        themes=("Регионы", "XX век"),
        book_ids=("chekhov_palata",),
    ),
    PushkinEvent(
        id="evt-yarosl-01",
        title="Спектакль «Вишнёвый сад» (Волковский театр)",
        venue="Российский академический театр драмы им. Ф. Волкова",
        city="Ярославль",
        region="RU-YAR",
        date="2026-10-30",
        price_rub=700,
        age_min=14,
        age_max=22,
        themes=("Драма", "Чехов"),
        book_ids=("chekhov_visnevy",),
    ),
    PushkinEvent(
        id="evt-vlad-01",
        title="Музей-усадьба Тургенева «Спасское-Лутовиново»",
        venue="Государственный мемориальный и природный музей-заповедник И.С. Тургенева",
        city="Орёл",
        region="RU-ORL",
        date="2026-09-30",
        price_rub=400,
        age_min=14,
        age_max=22,
        themes=("Тургенев", "XIX век"),
        book_ids=("turgenev_otcy",),
    ),
    PushkinEvent(
        id="evt-yasnaya-01",
        title="Экскурсия «Ясная Поляна: Толстой как переживание»",
        venue="Музей-усадьба Л. Н. Толстого «Ясная Поляна»",
        city="Тула",
        region="RU-TUL",
        date="2026-10-08",
        price_rub=500,
        age_min=14,
        age_max=22,
        themes=("Толстой", "XIX век"),
        book_ids=("tolstoy_war", "tolstoy_anna"),
    ),
]


def list_events() -> list[PushkinEvent]:
    return list(CATALOG)


def by_book(book_id: str) -> list[PushkinEvent]:
    return [e for e in CATALOG if book_id in e.book_ids]


def by_region(region: str) -> list[PushkinEvent]:
    return [e for e in CATALOG if e.region == region]


def by_theme(theme: str) -> list[PushkinEvent]:
    needle = theme.lower()
    return [e for e in CATALOG if any(needle in t.lower() for t in e.themes)]


def recommend(book_ids: list[str], *, region: str | None = None, limit: int = 6) -> list[PushkinEvent]:
    seen: set[str] = set()
    out: list[PushkinEvent] = []
    for bid in book_ids:
        for evt in by_book(bid):
            if evt.id in seen:
                continue
            if region and evt.region != region and len(out) >= limit // 2:
                continue
            seen.add(evt.id)
            out.append(evt)
            if len(out) >= limit:
                return out
    if region:
        for evt in by_region(region):
            if evt.id in seen:
                continue
            seen.add(evt.id)
            out.append(evt)
            if len(out) >= limit:
                return out
    return out[:limit]
