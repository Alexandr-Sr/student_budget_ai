from __future__ import annotations

import streamlit as st
import pandas as pd

from crew_logic import prepare_display_table, run_budget_crew, format_kzt


st.set_page_config(
    page_title="Распределение бюджета студенческого самоуправления",
    layout="wide"
)

st.title("Распределение бюджета студенческого самоуправления")
st.caption("Университет, Алматы, Казахстан")

with st.sidebar:
    st.header("Конфигурация агентов")

    role_analyst = st.text_input(
        "Роль аналитика",
        value="Аналитик бюджетных заявок студенческих клубов"
    )
    goal_analyst = st.text_input(
        "Цель аналитика",
        value="Проанализировать заявки клубов и определить их значимость для университета Алматы"
    )
    backstory_analyst = st.text_area(
        "Backstory аналитика",
        value=(
            "Ты эксперт по анализу студенческих инициатив, работающий в университете Алматы. "
            "Ты оцениваешь массовость, полезность, срочность и соответствие приоритетам вуза."
        ),
        height=140
    )

    role_coordinator = st.text_input(
        "Роль координатора",
        value="Координатор распределения бюджета студенческого самоуправления"
    )
    goal_coordinator = st.text_input(
        "Цель координатора",
        value="Сформировать справедливое распределение бюджета в тенге между студенческими клубами"
    )
    backstory_coordinator = st.text_area(
        "Backstory координатора",
        value=(
            "Ты отвечаешь за прозрачное и аргументированное распределение бюджета "
            "студенческого самоуправления в университете Алматы."
        ),
        height=140
    )

col1, col2 = st.columns(2)

with col1:
    st.subheader("Входные данные")
    excel_file = st.file_uploader(
        "Загрузите Excel с заявками клубов",
        type=["xlsx"]
    )

    priorities_file = st.file_uploader(
        "Загрузите TXT с приоритетами университета",
        type=["txt"]
    )

with col2:
    st.subheader("Параметры бюджета")
    total_budget = st.number_input(
        "Общий бюджет (тенге)",
        min_value=0.0,
        value=600000.0,
        step=50000.0
    )

    st.info(
        f"Текущий бюджет: {format_kzt(total_budget)}"
    )

run_button = st.button("Запустить анализ и распределение бюджета", type="primary")

if run_button:
    if excel_file is None:
        st.error("Сначала загрузи Excel-файл с заявками клубов.")
        st.stop()

    if priorities_file is None:
        st.error("Сначала загрузи TXT-файл с приоритетами университета.")
        st.stop()

    priorities_text = priorities_file.read().decode("utf-8")

    with st.spinner("Агенты анализируют заявки и распределяют бюджет..."):
        result = run_budget_crew(
            excel_bytes=excel_file.read(),
            priorities_text=priorities_text,
            total_budget=total_budget,
            role_analyst=role_analyst,
            goal_analyst=goal_analyst,
            backstory_analyst=backstory_analyst,
            role_coordinator=role_coordinator,
            goal_coordinator=goal_coordinator,
            backstory_coordinator=backstory_coordinator,
        )

    st.success("Анализ завершен")

    st.subheader("Краткая сводка")
    st.text(result.summary_text)

    st.subheader("Таблица распределения")
    display_df = prepare_display_table(result.cleaned_table)
    st.dataframe(display_df, use_container_width=True)

    st.subheader("Диаграмма распределения бюджета")
    chart_df = result.cleaned_table[["club_name", "approved_amount"]].copy()
    chart_df = chart_df.rename(
        columns={
            "club_name": "Клуб",
            "approved_amount": "Одобрено"
        }
    )
    st.bar_chart(chart_df.set_index("Клуб"))

    st.subheader("Итоговый отчет")
    st.markdown(result.final_report)