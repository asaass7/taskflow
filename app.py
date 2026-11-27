from datetime import datetime

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, abort
from flask_login import login_user, logout_user, login_required, current_user
from flask_wtf.csrf import CSRFError

from config import Config
from extensions import db, migrate, login_manager, csrf, mail
from decorators import admin_required
from forms import RegisterForm, LoginForm, ForgotPasswordForm, ResetPasswordForm
from services import create_reset_token, send_reset_email, get_token_by_raw, reset_password

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)
migrate.init_app(app, db)
login_manager.init_app(app)
csrf.init_app(app)
mail.init_app(app)

from models import User, Project, Task, TaskTag, Comment, PasswordResetToken

# API blueprint
from api import api_bp
app.register_blueprint(api_bp)

@app.after_request
def set_security_headers(response):
    # Защита от XSS (Content-Security-Policy)
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "font-src 'self' https://cdn.jsdelivr.net; "
        "img-src 'self' data:"
    )
    # Защита от MIME-sniffing
    response.headers['X-Content-Type-Options'] = 'nosniff'
    # Защита от clickjacking
    response.headers['X-Frame-Options'] = 'DENY'
    return response


@app.errorhandler(CSRFError)
def handle_csrf_error(e):
    print("CSRF ERROR:", e.description)
    return f"CSRF error: {e.description}", 400


@app.errorhandler(403)
def forbidden(e):
    return render_template('403.html'), 403


STATUSES = [
    ('new', 'Новая'),
    ('in_progress', 'В работе'),
    ('review', 'На проверке'),
    ('done', 'Выполнена'),
    ('cancelled', 'Отменена'),
]

import time

# Простой in-memory rate limit для ИИ-агента
_rate = {}  # user_id -> [timestamp, ...]

def rate_limit(user_id, limit=10, per=300):
    """10 запросов за 5 минут."""
    now = time.time()
    window = [t for t in _rate.get(user_id, []) if now - t < per]
    if len(window) >= limit:
        return False
    window.append(now)
    _rate[user_id] = window
    return True

# ====================== ГЛАВНАЯ ======================

@app.route('/')
def index():
    if not current_user.is_authenticated:
        return render_template('welcome.html')
    status = request.args.get('status')
    query = Task.query
    if status:
        query = query.filter_by(status=status)
    tasks = query.order_by(Task.created_at.desc()).all()
    return render_template('index.html', tasks=tasks,
                           statuses=STATUSES, current_status=status)


# ====================== АУТЕНТИФИКАЦИЯ ======================

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = RegisterForm()
    if form.validate_on_submit():
        user = User(email=form.email.data, full_name=form.full_name.data, role='user')
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('Регистрация успешна! Теперь войдите.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', form=form)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            flash(f'Добро пожаловать, {user.full_name}!', 'success')
            return redirect(request.args.get('next') or url_for('index'))
        flash('Неверный email или пароль.', 'danger')
    return render_template('login.html', form=form)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Вы вышли из системы.', 'info')
    return redirect(url_for('login'))


@app.route('/profile')
@login_required
def profile():
    return render_template('profile.html', user=current_user)


# ====================== ЗАДАЧИ ======================

@app.route('/add', methods=['GET', 'POST'])
@login_required
def add_task():
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description', '')
        project_id = request.form.get('project_id')
        if title:
            priority = request.form.get('priority', 'medium')
            due_date_raw = request.form.get('due_date')
            due_date = None
            if due_date_raw:
                try:
                    due_date = datetime.fromisoformat(due_date_raw)
                except ValueError:
                    due_date = None
            task = Task(
                title=title,
                description=description,
                project_id=int(project_id) if project_id else None,
                author_id=current_user.id,
                priority=priority if priority in ('low', 'medium', 'high') else 'medium',
                due_date=due_date,
            )
            db.session.add(task)
            db.session.commit()
            flash('Задача создана', 'success')
            return redirect(url_for('index'))
        flash('Название обязательно', 'warning')
    projects = Project.query.all()
    return render_template('add_task.html', projects=projects)


@app.route('/tasks/<int:task_id>/status', methods=['POST'])
@login_required
def update_status(task_id):
    task = Task.query.get_or_404(task_id)
    if task.author_id != current_user.id and current_user.role != 'admin':
        abort(403)
    status = request.form.get('status')
    if status in [k for k, _ in STATUSES]:
        task.status = status
        db.session.commit()
        flash('Статус обновлён', 'success')
    else:
        flash('Недопустимый статус', 'danger')
    return redirect(request.referrer or url_for('index'))


@app.route('/tasks/<int:task_id>/delete', methods=['POST'])
@login_required
def delete_task(task_id):
    task = Task.query.get_or_404(task_id)
    if task.author_id != current_user.id and current_user.role != 'admin':
        abort(403)
    db.session.delete(task)
    db.session.commit()
    flash('Задача удалена', 'success')
    return redirect(url_for('index'))


# ====================== АДМИН ======================

@app.route('/admin')
@login_required
@admin_required
def admin_dashboard():
    user_count = User.query.count()
    task_count = Task.query.count()
    return render_template('admin.html', user_count=user_count, task_count=task_count)


# ====================== HEALTH ======================

@app.route('/health/')
def health():
    return jsonify(status='ok', service='web')


# ====================== ВОССТАНОВЛЕНИЕ ПАРОЛЯ ======================

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = ForgotPasswordForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user:
            raw_token = create_reset_token(user)
            send_reset_email(user, raw_token)
        flash('Если аккаунт с таким email существует, письмо отправлено.', 'info')
        return redirect(url_for('login'))
    return render_template('forgot_password.html', form=form)


@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password_route(token):
    reset_token = get_token_by_raw(token)
    if not reset_token or not reset_token.is_valid():
        flash('Ссылка недействительна или истёк её срок действия.', 'danger')
        return redirect(url_for('login'))

    form = ResetPasswordForm()
    if form.validate_on_submit():
        ok = reset_password(token, form.password.data)
        if ok:
            flash('Пароль успешно изменён. Войдите с новым паролем.', 'success')
            return redirect(url_for('login'))
        flash('Не удалось сбросить пароль. Попробуйте снова.', 'danger')
    return render_template('reset_password.html', form=form)

# ====================== ИИ-АГЕНТ ======================

from agent_client import ask_agent, AgentError
from models import AiMessage

MAX_MESSAGE_LEN = 2000
HISTORY_LIMIT = 10


@app.route('/agent/')
@login_required
def agent_page():
    return render_template('agent.html')


@app.route('/agent/send', methods=['POST'])
@login_required
def agent_send():
    # Rate limit: 10 запросов за 5 минут
    if not rate_limit(current_user.id):
        return jsonify({'error': 'Слишком много запросов. Подождите 5 минут.'}), 429

    data = request.get_json(silent=True) or {}

def agent_send():
    data = request.get_json(silent=True) or {}
    text = (data.get('message') or '').strip()

    if not text:
        return jsonify({'error': 'Сообщение пустое.'}), 400
    if len(text) > MAX_MESSAGE_LEN:
        return jsonify({'error': 'Сообщение слишком длинное (максимум 2000 символов).'}), 400

    # Загружаем историю из БД
    rows = (AiMessage.query.filter_by(user_id=current_user.id)
            .order_by(AiMessage.id.desc()).limit(HISTORY_LIMIT).all())
    history = [{'role': r.role, 'content': r.content} for r in reversed(rows)]

    try:
        answer = ask_agent(history, text)
    except AgentError as e:
        return jsonify({'error': str(e)}), 502

    # Сохраняем пару реплик
    db.session.add(AiMessage(user_id=current_user.id, role='user', content=text))
    db.session.add(AiMessage(user_id=current_user.id, role='assistant', content=answer))
    db.session.commit()

    return jsonify({'reply': answer})

if __name__ == '__main__':
    app.run(debug=app.config['DEBUG'])