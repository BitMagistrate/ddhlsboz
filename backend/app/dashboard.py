"""
Демо-данные для дашбордов:
  - региональный (для министерства культуры/образования);
  - учительский (по классу);
  - партнёрский (для библиотеки/музея).
В продуктовой версии данные собираются через PostgreSQL и обновляются ежедневно.
"""

from __future__ import annotations


def regional_dashboard() -> dict:
    return {
        "region": "Демо-регион",
        "period": "2026 Q1",
        "snapshot": {
            "active_users": 18420,
            "youth_14_22": 12180,
            "teachers": 1620,
            "libraries_connected": 28,
            "museums_connected": 11,
            "schools_connected": 95,
        },
        "engagement": {
            "average_session_minutes": 14.6,
            "routes_completed": 7430,
            "books_opened": 24180,
            "trainer_attempts": 31290,
            "pushkin_card_referrals": 1850,
        },
        "education_metrics": [
            {"subject": "Литература", "ege_score_change_pp": 6.4, "schools": 95},
            {"subject": "История", "ege_score_change_pp": 4.1, "schools": 95},
            {"subject": "Русский язык", "ege_score_change_pp": 3.2, "schools": 95},
        ],
        "library_metrics": {
            "youth_visits_change_pp": 17.8,
            "online_catalog_queries": 38240,
            "events_per_quarter": 64,
        },
        "top_themes": [
            {"theme": "Серебряный век", "demand_index": 92},
            {"theme": "Литература первой половины XIX века", "demand_index": 88},
            {"theme": "Достоевский и психологический роман", "demand_index": 85},
            {"theme": "Великая Отечественная война", "demand_index": 80},
            {"theme": "Древняя Русь", "demand_index": 73},
        ],
        "rag_quality": {
            "precision_at_5": 0.93,
            "recall_at_10": 0.74,
            "mrr": 0.71,
            "hallucination_rate": 0.018,
            "citation_coverage": 0.94,
        },
        "compliance": {
            "data_localization": "100% Yandex Cloud (РФ)",
            "pd_protection": "152-ФЗ, согласие 14+",
            "kii_status": "Зарегистрировано",
            "audit_last_passed": "2026-02-14",
        },
        "disclaimer": "Демонстрационные данные. В продуктовой версии — реальные показатели по региону и доступ для уполномоченных лиц.",
    }


def teacher_dashboard() -> dict:
    return {
        "class": "10А",
        "school": "Гимназия №1, Демо-город",
        "teacher": "Иванова И. И.",
        "students_total": 26,
        "students_active": 24,
        "topics_progress": [
            {
                "topic": "Литература первой половины XIX века",
                "average_completion": 0.87,
                "students_passed": 22,
            },
            {
                "topic": "Психологический роман Достоевского",
                "average_completion": 0.74,
                "students_passed": 19,
            },
            {"topic": "Серебряный век", "average_completion": 0.62, "students_passed": 15},
            {"topic": "Эпопея «Война и мир»", "average_completion": 0.68, "students_passed": 17},
        ],
        "ege_simulator_stats": {
            "average_score": 67.4,
            "best_topic": "Лишний человек (84%)",
            "weakest_topic": "Цитирование драмы (52%)",
        },
        "alerts": [
            {
                "student": "Ученик #14",
                "issue": "Низкая активность (1 сессия за неделю)",
                "recommendation": "Назначить персональный маршрут по «Преступлению и наказанию»",
            },
            {
                "student": "Ученик #21",
                "issue": "Систематические ошибки в темах ЕГЭ по драме",
                "recommendation": "Посмотреть лекцию НЭБ + 5 задач из тренажёра",
            },
        ],
        "time_saved_hours_week": 5.4,
        "disclaimer": "Демонстрационные данные. В продуктовой версии данные обновляются ежедневно.",
    }


def partner_dashboard() -> dict:
    return {
        "partner": "Демо-библиотека (модельная, регион 1)",
        "period": "2026 Q1",
        "snapshot": {
            "widget_sessions": 4280,
            "youth_share": 0.61,
            "average_route_length_weeks": 4.3,
            "books_recommended": 11240,
            "physical_visits_change_pp": 16.2,
        },
        "top_queries": [
            "Серебряный век",
            "Подготовка к ЕГЭ по литературе",
            "Достоевский с нуля",
            "Маршрут на лето 14+",
            "Пушкин через 4 недели",
        ],
        "events_supported": [
            {"event": "Лекция «Серебряный век и революция»", "registrations": 184},
            {"event": "Книжный клуб «Достоевский на 4 недели»", "registrations": 96},
            {"event": "Школа критика. Серия «Толстой и Чехов»", "registrations": 142},
        ],
        "disclaimer": "Демонстрационные данные. Право доступа — у директора библиотеки и уполномоченных сотрудников.",
    }


def kpi_summary() -> list[dict]:
    return [
        {"name": "MAU", "value": 32400, "delta_pp": 18.4, "target_2026": 80000},
        {"name": "ARPU, ₽/мес", "value": 168, "delta_pp": 4.2, "target_2026": 220},
        {"name": "B2G контракты", "value": 3, "delta_pp": 0, "target_2026": 5},
        {"name": "B2B контракты", "value": 14, "delta_pp": 7, "target_2026": 30},
        {"name": "Precision@5", "value": 0.93, "delta_pp": 1.0, "target_2026": 0.95},
        {"name": "Hallucination rate", "value": 0.018, "delta_pp": -0.2, "target_2026": 0.01},
    ]
