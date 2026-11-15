from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_migrate import Migrate
from datetime import datetime

from config import Config
from models import db, User, Project, Task, TaskTag, Comment, PasswordResetToken

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)
migrate = Migrate(app, db)

STATUSES = [
    ('new', 'Новая'),
    ('in_progress', 'В работе'),
    ('review', 'На проверке'),
    ('done', 'Выполнена'),
    ('cancelled', 'Отменена'),
]


@app.route('/')
def index():
    status = request.args.get('status')
    query = Task.query
    if status:
        query = query.filter_by(status=status)
    tasks = query.order_by(Task.created_at.desc()).all()
    return render_template('index.html', tasks=tasks,
                           statuses=STATUSES, current_status=status)


@app.route('/add', methods=['GET', 'POST'])
def add_task():
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description', '')
        project_id = request.form.get('project_id')
        author = User.query.first()
        if not author:
            flash('Сначала создайте хотя бы одного пользователя в БД', 'danger')
            return redirect(url_for('index'))
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
                author_id=author.id,
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
def update_status(task_id):
    task = Task.query.get_or_404(task_id)
    status = request.form.get('status')
    if status in [k for k, _ in STATUSES]:
        task.status = status
        db.session.commit()
        flash('Статус обновлён', 'success')
    else:
        flash('Недопустимый статус', 'danger')
    return redirect(request.referrer or url_for('index'))


@app.route('/tasks/<int:task_id>/delete', methods=['POST'])
def delete_task(task_id):
    task = Task.query.get_or_404(task_id)
    db.session.delete(task)
    db.session.commit()
    flash('Задача удалена', 'success')
    return redirect(url_for('index'))


@app.route('/health/')
def health():
    return jsonify(status='ok', service='web')


if __name__ == '__main__':
    app.run(debug=app.config['DEBUG'])