"""
roi.py — B2G ROI-калькулятор для регионов.

Считает экономический эффект внедрения ЧитАИ:
- стоимость на одного ученика (CPM): фикс + LLM-токены;
- сэкономленные часы учителя (отчёты + проверка);
- эквивалент в рублях (по средней ставке);
- ожидаемый прирост среднего балла ЕГЭ по литературе (консервативно).

Все числа — параметры с публично-обоснованными дефолтами;
региональный партнёр может подставить свои значения.

Disclaimer: расчёт ориентировочный, итог фиксируется в договоре.
"""

from __future__ import annotations

from dataclasses import dataclass

# Дефолтные параметры (можно перебить через POST).
DEFAULT_STUDENTS = 1000
DEFAULT_TEACHERS = 50
DEFAULT_TEACHER_RATE_RUB_PER_HOUR = 350
DEFAULT_HOURS_SAVED_PER_TEACHER_PER_WEEK = 4
DEFAULT_WEEKS_PER_YEAR = 36
DEFAULT_BASE_FEE_PER_YEAR = 480_000  # фиксированный годовой платеж региона
DEFAULT_VARIABLE_FEE_PER_STUDENT_PER_YEAR = 800
DEFAULT_EXPECTED_EGE_POINTS_GAIN = 4.5  # средний прирост балла, оценка
DEFAULT_TOKEN_COST_PER_STUDENT_PER_MONTH = 90  # GigaChat MAX, ориентир


@dataclass
class RoiInputs:
    students: int = DEFAULT_STUDENTS
    teachers: int = DEFAULT_TEACHERS
    teacher_rate_rub_per_hour: float = DEFAULT_TEACHER_RATE_RUB_PER_HOUR
    hours_saved_per_teacher_per_week: float = DEFAULT_HOURS_SAVED_PER_TEACHER_PER_WEEK
    weeks_per_year: int = DEFAULT_WEEKS_PER_YEAR
    base_fee_per_year: int = DEFAULT_BASE_FEE_PER_YEAR
    variable_fee_per_student_per_year: int = DEFAULT_VARIABLE_FEE_PER_STUDENT_PER_YEAR
    expected_ege_points_gain: float = DEFAULT_EXPECTED_EGE_POINTS_GAIN
    token_cost_per_student_per_month: float = DEFAULT_TOKEN_COST_PER_STUDENT_PER_MONTH


def compute(inputs: RoiInputs) -> dict:
    """Возвращает структурированный отчёт ROI."""
    students = max(0, int(inputs.students))
    teachers = max(0, int(inputs.teachers))
    annual_license = (
        inputs.base_fee_per_year + students * inputs.variable_fee_per_student_per_year
    )
    annual_tokens = students * inputs.token_cost_per_student_per_month * 12
    annual_cost = annual_license + annual_tokens

    teacher_hours_saved = (
        teachers
        * inputs.hours_saved_per_teacher_per_week
        * inputs.weeks_per_year
    )
    teacher_savings_rub = teacher_hours_saved * inputs.teacher_rate_rub_per_hour

    cost_per_student_per_year = (
        annual_cost / students if students else float(annual_cost)
    )

    ege_points_total = inputs.expected_ege_points_gain * students

    # ROI-коэффициент = выгода (часы учителей в рублях) / годовая стоимость.
    roi_ratio = teacher_savings_rub / annual_cost if annual_cost else 0.0

    return {
        "inputs": {
            "students": students,
            "teachers": teachers,
            "teacher_rate_rub_per_hour": inputs.teacher_rate_rub_per_hour,
            "hours_saved_per_teacher_per_week": inputs.hours_saved_per_teacher_per_week,
            "weeks_per_year": inputs.weeks_per_year,
            "base_fee_per_year": inputs.base_fee_per_year,
            "variable_fee_per_student_per_year": inputs.variable_fee_per_student_per_year,
            "expected_ege_points_gain": inputs.expected_ege_points_gain,
            "token_cost_per_student_per_month": inputs.token_cost_per_student_per_month,
        },
        "annual_cost_rub": round(annual_cost, 2),
        "cost_per_student_per_year_rub": round(cost_per_student_per_year, 2),
        "teacher_hours_saved": teacher_hours_saved,
        "teacher_savings_rub": round(teacher_savings_rub, 2),
        "expected_ege_points_total": round(ege_points_total, 2),
        "roi_ratio": round(roi_ratio, 2),
        "disclaimer": (
            "Оценка является ориентировочной. Конечные показатели "
            "фиксируются в договоре после 30-дневного пилота "
            "и зависят от исходного среднего балла, нагрузки и состава классов."
        ),
    }
