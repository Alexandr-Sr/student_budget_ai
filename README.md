# Student Budget AI (CrewAI + Streamlit)

Проект по теме: **Распределение бюджета студенческого самоуправления**.

## Что делает проект
- загружает Excel-файл с заявками клубов;
- загружает TXT-файл с приоритетами университета;
- анализирует заявки с помощью 2 агентов CrewAI;
- предлагает распределение бюджета;
- показывает итог в веб-интерфейсе Streamlit.

## Структура Excel
Обязательные столбцы:
- `club_name`
- `project_name`
- `requested_amount`
- `expected_impact`
- `students_reached`
- `urgency`

Где:
- `requested_amount` — сумма запроса;
- `expected_impact` — ожидаемая полезность проекта (например, 1–10);
- `students_reached` — сколько студентов будет охвачено;
- `urgency` — срочность проекта (например, 1–10).

## Запуск локально
```bash
python -m venv .venv
source .venv/bin/activate   # Mac/Linux
# .venv\Scripts\activate    # Windows
pip install -r requirements.txt
cp .env.example .env
streamlit run src/app.py
```

## Что поменять перед сдачей
- вставить свой API-ключ в `.env`;
- загрузить проект в свой GitHub;
- задеплоить на Streamlit Community Cloud;
- вставить реальные ссылки в отчет.
