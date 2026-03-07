from __future__ import annotations

import io
import os
from dataclasses import dataclass
from typing import Dict, List

import pandas as pd
from crewai import Agent, Crew, LLM, Process, Task


REQUIRED_COLUMNS = [
    "club_name",
    "project_name",
    "requested_amount",
    "expected_impact",
    "students_reached",
    "urgency",
]


@dataclass
class BudgetRunResult:
    cleaned_table: pd.DataFrame
    summary_text: str
    final_report: str


def format_kzt(value: float) -> str:
    return f"{float(value):,.0f} ₸".replace(",", " ")


def load_excel_from_bytes(file_bytes: bytes) -> pd.DataFrame:
    df = pd.read_excel(io.BytesIO(file_bytes))

    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(
            "В Excel-файле не хватает обязательных столбцов: " + ", ".join(missing)
        )

    df = df.copy()
    df["requested_amount"] = pd.to_numeric(df["requested_amount"], errors="coerce").fillna(0)
    df["expected_impact"] = pd.to_numeric(df["expected_impact"], errors="coerce").fillna(0)
    df["students_reached"] = pd.to_numeric(df["students_reached"], errors="coerce").fillna(0)
    df["urgency"] = pd.to_numeric(df["urgency"], errors="coerce").fillna(0)

    return df


def add_priority_score(df: pd.DataFrame) -> pd.DataFrame:
    work = df.copy()
    work["priority_score"] = (
        work["expected_impact"] * 0.4
        + work["students_reached"] * 0.3
        + work["urgency"] * 0.3
    )
    return work


def dataframe_to_prompt_table(df: pd.DataFrame) -> str:
    display_df = df.copy()

    if "priority_score" not in display_df.columns:
        display_df = add_priority_score(display_df)

    return display_df.to_markdown(index=False)


def deterministic_allocation(df: pd.DataFrame, total_budget: float) -> pd.DataFrame:
    work = add_priority_score(df)

    work = work.sort_values(
        by=["priority_score", "requested_amount"],
        ascending=[False, True]
    ).reset_index(drop=True)

    remaining = float(total_budget)
    approved_amounts: List[float] = []
    statuses: List[str] = []

    for _, row in work.iterrows():
        requested = float(row["requested_amount"])

        if remaining <= 0:
            approved_amounts.append(0.0)
            statuses.append("Отклонено из-за ограничения бюджета")
            continue

        approved = min(requested, remaining)
        approved_amounts.append(round(approved, 2))

        if approved == requested:
            statuses.append("Одобрено полностью")
        else:
            statuses.append("Одобрено частично")

        remaining -= approved

    work["approved_amount"] = approved_amounts
    work["status"] = statuses
    return work


def create_gemini_llm() -> LLM:
    api_key = (
        os.getenv("GEMINI_API_KEY")
        or os.getenv("GOOGLE_API_KEY")
        or os.getenv("GOOGLE_GENAI_API_KEY")
    )

    if not api_key:
        raise ValueError(
            "Не найден API-ключ Gemini. Добавь в .env переменную "
            "GEMINI_API_KEY=твой_ключ"
        )

    model_name = os.getenv("MODEL", "gemini/gemini-3-flash-preview")

    return LLM(
        model=model_name,
        api_key=api_key,
        temperature=0.3,
    )


def build_agents(
    role_analyst: str,
    goal_analyst: str,
    backstory_analyst: str,
    role_coordinator: str,
    goal_coordinator: str,
    backstory_coordinator: str,
) -> Dict[str, Agent]:
    llm = create_gemini_llm()

    analyst = Agent(
        role=role_analyst,
        goal=goal_analyst,
        backstory=backstory_analyst,
        llm=llm,
        verbose=True,
        allow_delegation=False,
    )

    coordinator = Agent(
        role=role_coordinator,
        goal=goal_coordinator,
        backstory=backstory_coordinator,
        llm=llm,
        verbose=True,
        allow_delegation=False,
    )

    return {
        "analyst": analyst,
        "coordinator": coordinator,
    }


def prepare_display_table(df: pd.DataFrame) -> pd.DataFrame:
    display_df = df.copy()

    display_df["requested_amount"] = display_df["requested_amount"].apply(format_kzt)
    display_df["approved_amount"] = display_df["approved_amount"].apply(format_kzt)
    display_df["priority_score"] = display_df["priority_score"].round(2)

    display_df = display_df.rename(
        columns={
            "club_name": "Клуб",
            "project_name": "Проект",
            "requested_amount": "Запрошено",
            "expected_impact": "Влияние",
            "students_reached": "Охват студентов",
            "urgency": "Срочность",
            "priority_score": "Приоритетный балл",
            "approved_amount": "Одобрено",
            "status": "Статус",
        }
    )

    return display_df


def run_budget_crew(
    excel_bytes: bytes,
    priorities_text: str,
    total_budget: float,
    role_analyst: str,
    goal_analyst: str,
    backstory_analyst: str,
    role_coordinator: str,
    goal_coordinator: str,
    backstory_coordinator: str,
) -> BudgetRunResult:
    df = load_excel_from_bytes(excel_bytes)
    allocated_df = deterministic_allocation(df, total_budget)
    table_text = dataframe_to_prompt_table(allocated_df)

    agents = build_agents(
        role_analyst,
        goal_analyst,
        backstory_analyst,
        role_coordinator,
        goal_coordinator,
        backstory_coordinator,
    )

    analysis_task = Task(
        description=(
            "Ты работаешь в студенческом самоуправлении университета в городе Алматы, Казахстан.\n"
            "Все финансовые расчеты и рекомендации должны указываться только в тенге (₸).\n\n"
            "Проанализируй заявки студенческих клубов и приоритеты развития университета.\n\n"
            f"Приоритеты университета:\n{priorities_text}\n\n"
            f"Общий бюджет: {format_kzt(total_budget)}\n\n"
            "Ниже представлена таблица заявок с уже вычисленным priority_score.\n"
            "Оцени, какие клубы наиболее полезны для университета, студентов Алматы "
            "и развития студенческой среды.\n\n"
            f"Таблица:\n{table_text}\n\n"
            "Сделай структурированный вывод:\n"
            "- название клуба\n"
            "- сильные стороны проекта\n"
            "- почему проект важен или не очень важен\n"
            "- риски при отказе в финансировании\n"
            "- краткая рекомендация\n\n"
            "Пиши по-русски, в официально-учебном стиле, без упоминания рублей."
        ),
        expected_output=(
            "Структурированный анализ заявок студенческих клубов с объяснением их важности."
        ),
        agent=agents["analyst"],
    )

    allocation_task = Task(
        description=(
            "Ты координатор распределения бюджета студенческого самоуправления "
            "университета в Алматы, Казахстан.\n"
            "Все суммы необходимо указывать только в тенге (₸).\n"
            "Нельзя использовать рубли, доллары или другую валюту.\n\n"
            "На основе анализа предыдущего агента подготовь итоговый отчет "
            "по распределению бюджета.\n\n"
            f"Приоритеты университета:\n{priorities_text}\n\n"
            f"Общий бюджет: {format_kzt(total_budget)}\n\n"
            "Используй следующую таблицу как основу финансового решения.\n"
            "Таблица уже содержит approved_amount и статус.\n\n"
            f"Таблица:\n{allocated_df.to_markdown(index=False)}\n\n"
            "Сформируй итоговый отчет в 4 блоках:\n"
            "1. Краткая сводка.\n"
            "2. Таблица или список: кому сколько выделено в тенге.\n"
            "3. Почему такое распределение можно считать справедливым.\n"
            "4. Практические рекомендации студенческому самоуправлению Алматы на следующий семестр.\n\n"
            "Отчет должен выглядеть как учебный аналитический документ для университета Казахстана."
        ),
        expected_output="Готовый итоговый отчет по распределению бюджета.",
        agent=agents["coordinator"],
        context=[analysis_task],
    )

    crew = Crew(
        agents=[agents["analyst"], agents["coordinator"]],
        tasks=[analysis_task, allocation_task],
        process=Process.sequential,
        verbose=True,
    )

    result = crew.kickoff()
    final_report = getattr(result, "raw", str(result))

    total_requested = float(allocated_df["requested_amount"].sum())
    total_approved = float(allocated_df["approved_amount"].sum())
    remaining_budget = float(total_budget) - total_approved

    summary_text = (
        f"Всего заявок: {len(allocated_df)}\n"
        f"Общая запрошенная сумма: {format_kzt(total_requested)}\n"
        f"Распределено: {format_kzt(total_approved)}\n"
        f"Остаток бюджета: {format_kzt(remaining_budget)}"
    )

    return BudgetRunResult(
        cleaned_table=allocated_df,
        summary_text=summary_text,
        final_report=final_report,
    )