"""
Тренажёр ЕГЭ по литературе и истории.
Демо-вопросы привязаны к корпусу public domain.
В продакшене вопросы генерируются YandexGPT 5 на основании кодификатора ФИПИ.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Question:
    id: str
    topic: str
    subject: str
    question: str
    options: list[str]
    correct_index: int
    explanation: str
    source_id: str | None = None

    def to_dict(self, with_answer: bool = False) -> dict:
        d = {
            "id": self.id,
            "topic": self.topic,
            "subject": self.subject,
            "question": self.question,
            "options": self.options,
            "source_id": self.source_id,
        }
        if with_answer:
            d["correct_index"] = self.correct_index
            d["explanation"] = self.explanation
        return d


QUESTIONS: list[Question] = [
    Question(
        id="lit_1",
        topic="Литература первой половины XIX века",
        subject="Литература",
        question="Кто из русских писателей первой половины XIX века написал роман в стихах «Евгений Онегин»?",
        options=["Н. В. Гоголь", "А. С. Пушкин", "М. Ю. Лермонтов", "И. А. Гончаров"],
        correct_index=1,
        explanation="«Евгений Онегин» — роман в стихах А. С. Пушкина, написанный с 1823 по 1830 год.",
        source_id="pushkin_onegin",
    ),
    Question(
        id="lit_2",
        topic="Литература первой половины XIX века",
        subject="Литература",
        question="Кому принадлежит фраза «Береги честь смолоду»?",
        options=["Эпиграф к «Капитанской дочке»", "Тарас Бульба", "Чацкий", "Базаров"],
        correct_index=0,
        explanation="«Береги честь смолоду» — пословица, использованная А. С. Пушкиным в качестве эпиграфа к «Капитанской дочке».",
        source_id="pushkin_dochka",
    ),
    Question(
        id="lit_3",
        topic="Лишний человек",
        subject="Литература",
        question="Кто из перечисленных персонажей относится к типу «лишнего человека»?",
        options=["Раскольников", "Печорин", "Чичиков", "Базаров"],
        correct_index=1,
        explanation="Печорин из «Героя нашего времени» — классический представитель типа «лишнего человека».",
        source_id="lermontov_geroi",
    ),
    Question(
        id="lit_4",
        topic="Сатира",
        subject="Литература",
        question="В каком произведении Н. В. Гоголь высмеивает помещиков Российской империи?",
        options=["«Шинель»", "«Ревизор»", "«Мёртвые души»", "«Тарас Бульба»"],
        correct_index=2,
        explanation="«Мёртвые души» — поэма Н. В. Гоголя, в которой он создал галерею помещиков-сатирических типов.",
        source_id="gogol_dushi",
    ),
    Question(
        id="lit_5",
        topic="Маленький человек",
        subject="Литература",
        question="Кто из перечисленных героев — представитель темы «маленького человека»?",
        options=["Башмачкин", "Онегин", "Печорин", "Базаров"],
        correct_index=0,
        explanation="Акакий Акакиевич Башмачкин из «Шинели» Гоголя — манифест темы «маленького человека».",
        source_id="gogol_shinel",
    ),
    Question(
        id="lit_6",
        topic="Психологический роман",
        subject="Литература",
        question="Какой роман Ф. М. Достоевского посвящён теории Раскольникова?",
        options=["«Идиот»", "«Бесы»", "«Преступление и наказание»", "«Братья Карамазовы»"],
        correct_index=2,
        explanation="«Преступление и наказание» (1866) — роман о Раскольникове и его теории «право имеющих».",
        source_id="dostoevsky_pn",
    ),
    Question(
        id="lit_7",
        topic="Эпопея",
        subject="Литература",
        question="Какое произведение Л. Н. Толстого охватывает события Отечественной войны 1812 года?",
        options=["«Анна Каренина»", "«Воскресение»", "«Война и мир»", "«Севастопольские рассказы»"],
        correct_index=2,
        explanation="«Война и мир» — роман-эпопея, охватывающий события войн 1805 и 1812 годов.",
        source_id="tolstoy_war",
    ),
    Question(
        id="lit_8",
        topic="Серебряный век",
        subject="Литература",
        question="Кто автор поэмы «Двенадцать»?",
        options=["А. А. Ахматова", "А. А. Блок", "В. В. Маяковский", "С. А. Есенин"],
        correct_index=1,
        explanation="«Двенадцать» (1918) — поэма А. А. Блока о революционном Петрограде.",
        source_id="blok_dvenadtsat",
    ),
    Question(
        id="lit_9",
        topic="Серебряный век",
        subject="Литература",
        question="Какая поэма А. А. Ахматовой посвящена жертвам репрессий 1937 года?",
        options=["«Поэма без героя»", "«Реквием»", "«Чётки»", "«Anno Domini»"],
        correct_index=1,
        explanation="«Реквием» — поэма А. А. Ахматовой, написанная в 1935–1940 годах и посвящённая жертвам сталинского террора.",
        source_id="ahmatova_rekviem",
    ),
    Question(
        id="lit_10",
        topic="Драма",
        subject="Литература",
        question="Кто из героев называет себя «лучом света в тёмном царстве»?",
        options=["Катерина", "Кабаниха", "Лариса Огудалова", "Татьяна Ларина"],
        correct_index=0,
        explanation="Катерина из «Грозы» А. Н. Островского названа критикой Н. А. Добролюбова «лучом света в тёмном царстве».",
        source_id="ostrovsky_groza",
    ),
    Question(
        id="hist_1",
        topic="Древняя Русь",
        subject="История",
        question="Какой князь крестил Русь в 988 году?",
        options=["Ярослав Мудрый", "Святослав", "Владимир Святославич", "Олег"],
        correct_index=2,
        explanation="Крещение Руси произошло в 988 году при князе Владимире Святославиче.",
    ),
    Question(
        id="hist_2",
        topic="Древняя Русь",
        subject="История",
        question="Какой документ — древнейший русский свод законов?",
        options=["Соборное уложение", "Русская правда", "Судебник Ивана III", "Стоглав"],
        correct_index=1,
        explanation="«Русская правда» — древнейший свод законов Древней Руси, начатый Ярославом Мудрым.",
    ),
    Question(
        id="hist_3",
        topic="Смутное время",
        subject="История",
        question="Какое событие положило начало Смутному времени?",
        options=[
            "Восстание Болотникова",
            "Прекращение династии Рюриковичей",
            "Поход Лжедмитрия II",
            "Семибоярщина",
        ],
        correct_index=1,
        explanation="Смутное время началось с прекращения династии Рюриковичей после смерти Фёдора Иоанновича в 1598 году.",
    ),
    Question(
        id="hist_4",
        topic="XVIII век",
        subject="История",
        question="Какой указ Петра I положил начало регулярной армии?",
        options=[
            "Указ о единонаследии",
            "Указ о престолонаследии",
            "Указ о наборе рекрутов",
            "Указ о подушной подати",
        ],
        correct_index=2,
        explanation="Указ 1705 года о наборе рекрутов стал основой регулярной армии Российской империи.",
    ),
    Question(
        id="hist_5",
        topic="Отечественная война 1812 года",
        subject="История",
        question="Какое сражение считается ключевым в Отечественной войне 1812 года?",
        options=["Аустерлиц", "Бородинское сражение", "Лейпциг", "Полтавская битва"],
        correct_index=1,
        explanation="Бородинское сражение 26 августа (7 сентября) 1812 года считается ключевым в Отечественной войне.",
    ),
    Question(
        id="hist_6",
        topic="Великие реформы",
        subject="История",
        question="В каком году была отменена крепостное право в России?",
        options=["1855", "1861", "1864", "1881"],
        correct_index=1,
        explanation="Крепостное право отменено манифестом Александра II 19 февраля 1861 года.",
    ),
    Question(
        id="hist_7",
        topic="Революция 1917 года",
        subject="История",
        question="Какое событие открыло Февральскую революцию 1917 года?",
        options=[
            "Кронштадтское восстание",
            "Стачка на Путиловском заводе",
            "Корниловский мятеж",
            "Восстание матросов на «Потёмкине»",
        ],
        correct_index=1,
        explanation="Стачка на Путиловском заводе 18 февраля 1917 года стала началом Февральской революции.",
    ),
    Question(
        id="hist_8",
        topic="Великая Отечественная война",
        subject="История",
        question="Какое сражение стало переломным в Великой Отечественной войне?",
        options=["Битва под Москвой", "Сталинградская битва", "Курская битва", "Битва за Берлин"],
        correct_index=1,
        explanation="Сталинградская битва (17 июля 1942 — 2 февраля 1943) стала коренным переломом в ходе Великой Отечественной войны.",
    ),
]


def list_topics() -> list[str]:
    seen: list[str] = []
    for q in QUESTIONS:
        if q.topic not in seen:
            seen.append(q.topic)
    return seen


def by_topic(topic: str, limit: int = 5) -> list[Question]:
    qs = [q for q in QUESTIONS if q.topic.lower() == topic.lower()]
    return qs[:limit]


def by_subject(subject: str, limit: int = 10) -> list[Question]:
    qs = [q for q in QUESTIONS if q.subject.lower() == subject.lower()]
    return qs[:limit]


def by_id(question_id: str) -> Question | None:
    for q in QUESTIONS:
        if q.id == question_id:
            return q
    return None


def check_answer(question_id: str, answer_index: int) -> dict:
    q = by_id(question_id)
    if not q:
        return {"error": "question_not_found"}
    correct = answer_index == q.correct_index
    return {
        "question_id": q.id,
        "correct": correct,
        "correct_index": q.correct_index,
        "explanation": q.explanation,
    }
