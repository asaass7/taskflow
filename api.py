import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from functools import wraps

import jwt
from flask import Blueprint, jsonify, request, current_app

from extensions import db, csrf
from models import User, Task, PasswordResetToken

api_bp = Blueprint('api', __name__, url_prefix='/api')
csrf.exempt(api_bp)  


# ============================================================
# JWT
# ============================================================

def create_jwt(user: User) -> str:
    payload = {
        'user_id': user.id,
        'role': user.role,
        'exp': datetime.now(timezone.utc) + timedelta(
            hours=current_app.config['JWT_EXPIRES_HOURS']
        ),
        'iat': datetime.now(timezone.utc),
    }
    return jwt.encode(payload, current_app.config['JWT_SECRET_KEY'], algorithm='HS256')


def decode_jwt(token: str):
    try:
        return jwt.decode(token, current_app.config['JWT_SECRET_KEY'], algorithms=['HS256'])
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None


def jwt_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.headers.get('Authorization', '')
        if not auth.startswith('Bearer '):
            return jsonify({'error': 'Unauthorized', 'message': 'Требуется JWT-токен'}), 401
        payload = decode_jwt(auth[7:])
        if not payload:
            return jsonify({'error': 'Unauthorized', 'message': 'Невалидный или просроченный токен'}), 401
        user = User.query.get(payload['user_id'])
        if not user:
            return jsonify({'error': 'Unauthorized', 'message': 'Пользователь не найден'}), 401
        request.current_user = user
        return f(*args, **kwargs)
    return decorated


def admin_jwt_required(f):
    @wraps(f)
    @jwt_required
    def decorated(*args, **kwargs):
        if request.current_user.role != 'admin':
            return jsonify({'error': 'Forbidden', 'message': 'Требуются права администратора'}), 403
        return f(*args, **kwargs)
    return decorated


# ============================================================
# Валидация
# ============================================================

def validate_email(email: str):
    if not email or '@' not in email or '.' not in email.split('@')[-1]:
        return 'Некорректный email'
    return None


def validate_password(password: str):
    if not password or len(password) < 8:
        return 'Пароль должен быть не менее 8 символов'
    return None


def task_to_dict(task: Task) -> dict:
    return {
        'id': task.id,
        'title': task.title,
        'description': task.description,
        'status': task.status,
        'priority': task.priority,
        'due_date': task.due_date.isoformat() if task.due_date else None,
        'project_id': task.project_id,
        'author_id': task.author_id,
        'created_at': task.created_at.isoformat(),
    }


# ============================================================
# AUTH
# ============================================================

@api_bp.route('/auth/register', methods=['POST'])
def api_register():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'Bad Request', 'message': 'Требуется JSON'}), 400

    email = (data.get('email') or '').strip().lower()
    password = data.get('password') or ''
    full_name = (data.get('full_name') or '').strip()

    errors = {}
    if err := validate_email(email):
        errors['email'] = err
    if err := validate_password(password):
        errors['password'] = err
    if not full_name:
        errors['full_name'] = 'ФИО обязательно'
    if email and User.query.filter_by(email=email).first():
        errors['email'] = 'Пользователь с таким email уже существует'

    if errors:
        return jsonify({'error': 'Unprocessable Entity', 'errors': errors}), 422

    user = User(email=email, full_name=full_name, role='user')
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return jsonify({
        'id': user.id, 'email': user.email,
        'full_name': user.full_name, 'role': user.role,
    }), 201


@api_bp.route('/auth/login', methods=['POST'])
def api_login():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'Bad Request', 'message': 'Требуется JSON'}), 400

    email = (data.get('email') or '').strip().lower()
    password = data.get('password') or ''
    if not email or not password:
        return jsonify({'error': 'Unprocessable Entity',
                        'errors': {'email': 'email и password обязательны'}}), 422

    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        return jsonify({'error': 'Unauthorized',
                        'message': 'Неверный email или пароль'}), 401

    token = create_jwt(user)
    return jsonify({
        'access_token': token,
        'token_type': 'Bearer',
        'expires_in': current_app.config['JWT_EXPIRES_HOURS'] * 3600,
        'user': {'id': user.id, 'email': user.email, 'role': user.role},
    }), 200


@api_bp.route('/auth/password-reset/request', methods=['POST'])
def api_password_reset_request():
    data = request.get_json(silent=True) or {}
    email = (data.get('email') or '').strip().lower()
    user = User.query.filter_by(email=email).first() if email else None
    if user:
        PasswordResetToken.query.filter_by(user_id=user.id, used_at=None).update(
            {'used_at': datetime.now(timezone.utc)}
        )
        raw = secrets.token_urlsafe(32)
        db.session.add(PasswordResetToken(
            user_id=user.id,
            token_hash=hashlib.sha256(raw.encode()).hexdigest(),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
        ))
        db.session.commit()
        print(f"[API RESET] Токен для {email}: {raw}")

    return jsonify({
        'message': 'Если аккаунт с таким email существует, письмо отправлено'
    }), 200


@api_bp.route('/auth/password-reset/confirm', methods=['POST'])
def api_password_reset_confirm():
    data = request.get_json(silent=True) or {}
    token = data.get('token') or ''
    new_password = data.get('new_password') or ''

    if err := validate_password(new_password):
        return jsonify({'error': 'Unprocessable Entity',
                        'errors': {'new_password': err}}), 422

    token_hash = hashlib.sha256(token.encode()).hexdigest()
    reset_token = PasswordResetToken.query.filter_by(token_hash=token_hash).first()
    if not reset_token or not reset_token.is_valid():
        return jsonify({'error': 'Not Found',
                        'message': 'Токен недействителен или истёк'}), 404

    reset_token.user.set_password(new_password)
    reset_token.used_at = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify({'message': 'Пароль успешно изменён'}), 200


# ============================================================
# TASKS
# ============================================================

@api_bp.route('/tasks', methods=['GET'])
@jwt_required
def api_tasks_list():
    if request.current_user.role == 'admin':
        tasks = Task.query.order_by(Task.created_at.desc()).all()
    else:
        tasks = Task.query.filter_by(author_id=request.current_user.id)\
            .order_by(Task.created_at.desc()).all()
    return jsonify([task_to_dict(t) for t in tasks]), 200


@api_bp.route('/tasks', methods=['POST'])
@jwt_required
def api_tasks_create():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'Bad Request', 'message': 'Требуется JSON'}), 400

    title = (data.get('title') or '').strip()
    if not title:
        return jsonify({'error': 'Unprocessable Entity',
                        'errors': {'title': 'Название обязательно'}}), 422

    priority = data.get('priority', 'medium')
    if priority not in ('low', 'medium', 'high'):
        return jsonify({'error': 'Unprocessable Entity',
                        'errors': {'priority': 'Допустимо: low, medium, high'}}), 422

    status = data.get('status', 'new')
    if status not in ('new', 'in_progress', 'review', 'done', 'cancelled'):
        return jsonify({'error': 'Unprocessable Entity',
                        'errors': {'status': 'Недопустимый статус'}}), 422

    task = Task(
        title=title,
        description=data.get('description', ''),
        status=status,
        priority=priority,
        project_id=data.get('project_id'),
        author_id=request.current_user.id,
    )
    db.session.add(task)
    db.session.commit()
    return jsonify(task_to_dict(task)), 201


@api_bp.route('/tasks/<int:task_id>', methods=['GET'])
@jwt_required
def api_tasks_get(task_id):
    task = Task.query.get(task_id)
    if not task:
        return jsonify({'error': 'Not Found', 'message': 'Задача не найдена'}), 404
    if task.author_id != request.current_user.id and request.current_user.role != 'admin':
        return jsonify({'error': 'Forbidden'}), 403
    return jsonify(task_to_dict(task)), 200


@api_bp.route('/tasks/<int:task_id>', methods=['PUT'])
@jwt_required
def api_tasks_update(task_id):
    task = Task.query.get(task_id)
    if not task:
        return jsonify({'error': 'Not Found', 'message': 'Задача не найдена'}), 404
    if task.author_id != request.current_user.id and request.current_user.role != 'admin':
        return jsonify({'error': 'Forbidden'}), 403

    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'Bad Request', 'message': 'Требуется JSON'}), 400

    if 'title' in data:
        if not (data['title'] or '').strip():
            return jsonify({'error': 'Unprocessable Entity',
                            'errors': {'title': 'Название обязательно'}}), 422
        task.title = data['title'].strip()
    if 'description' in data:
        task.description = data['description']
    if 'priority' in data:
        if data['priority'] not in ('low', 'medium', 'high'):
            return jsonify({'error': 'Unprocessable Entity',
                            'errors': {'priority': 'Допустимо: low, medium, high'}}), 422
        task.priority = data['priority']
    if 'status' in data:
        if data['status'] not in ('new', 'in_progress', 'review', 'done', 'cancelled'):
            return jsonify({'error': 'Unprocessable Entity',
                            'errors': {'status': 'Недопустимый статус'}}), 422
        task.status = data['status']

    db.session.commit()
    return jsonify(task_to_dict(task)), 200


@api_bp.route('/tasks/<int:task_id>', methods=['DELETE'])
@jwt_required
def api_tasks_delete(task_id):
    task = Task.query.get(task_id)
    if not task:
        return jsonify({'error': 'Not Found', 'message': 'Задача не найдена'}), 404
    if task.author_id != request.current_user.id and request.current_user.role != 'admin':
        return jsonify({'error': 'Forbidden'}), 403
    db.session.delete(task)
    db.session.commit()
    return '', 204


# ============================================================
# ADMIN
# ============================================================

@api_bp.route('/admin/users', methods=['GET'])
@admin_jwt_required
def api_admin_users():
    users = User.query.order_by(User.id).all()
    return jsonify([
        {'id': u.id, 'email': u.email, 'full_name': u.full_name,
         'role': u.role, 'is_active': u.is_active}
        for u in users
    ]), 200
