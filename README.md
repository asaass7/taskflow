# TaskFlow

Веб-приложение для управления задачами (трекер) на Flask + PostgreSQL.

## Возможности

- Регистрация и аутентификация (Flask-Login)
- Ролевая модель (user / admin)
- Восстановление пароля по email (одноразовые токены)
- REST API с JWT-аутентификацией
- Адаптивный интерфейс (Bootstrap 5.3)
- ИИ-агент TaskBot (Ollama + llama3.2)
- Защита от CSRF, XSS, SQL-инъекций

## Стек

- Python 3.13, Flask 3.1
- PostgreSQL 15
- SQLAlchemy + Flask-Migrate
- Bootstrap 5.3, JavaScript
- Ollama (локальная модель llama3.2)

## Установка

1. Клонировать репозиторий:
git clone https://github.com/asaass7/taskflow.git

text
2. Создать виртуальное окружение:
python3 -m venv venv
source venv/bin/activate

text
3. Установить зависимости:
pip install -r requirements.txt

text
4. Скопировать `.env.example` в `.env` и заполнить своими значениями.
5. Применить миграции:
flask db upgrade

text
6. Запустить:
python app.py

text

## Автор

Абдусаидов Асадбек, специальность 09.02.07