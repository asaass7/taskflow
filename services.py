import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from flask import current_app, url_for
from flask_mail import Message

from extensions import db, mail
from models import PasswordResetToken, User

TOKEN_TTL_MINUTES = 30


def create_reset_token(user: User) -> str:
    """Создаёт одноразовый токен для сброса пароля.
    В БД сохраняется только SHA-256 хеш, а не сам токен.
    Возвращает исходный токен (для отправки в письме).
    """
    # Инвалидируем все старые неиспользованные токены этого пользователя
    PasswordResetToken.query.filter_by(user_id=user.id, used_at=None).update(
        {'used_at': datetime.now(timezone.utc)}
    )

    raw_token = secrets.token_urlsafe(32)
    token = PasswordResetToken(
        user_id=user.id,
        token_hash=hashlib.sha256(raw_token.encode('utf-8')).hexdigest(),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=TOKEN_TTL_MINUTES),
    )
    db.session.add(token)
    db.session.commit()

    print(f"[DEBUG] Создан токен для {user.email}: {raw_token[:10]}... (в БД только хеш)")
    return raw_token


def get_token_by_raw(raw_token: str):
    """Находит запись токена по исходному значению через SHA-256 хеш."""
    token_hash = hashlib.sha256(raw_token.encode('utf-8')).hexdigest()
    return PasswordResetToken.query.filter_by(token_hash=token_hash).first()


def send_reset_email(user: User, raw_token: str) -> None:
    """Отправляет письмо со ссылкой для сброса пароля.
    При MAIL_SUPPRESS_SEND=True письмо печатается в консоль.
    """
    reset_url = url_for('reset_password_route', token=raw_token, _external=True)

    print(f"[DEBUG] send_reset_email: {user.email} -> {reset_url}")
    print(f"[DEBUG] MAIL_SUPPRESS_SEND = {current_app.config.get('MAIL_SUPPRESS_SEND')}")

    msg = Message(
        subject='Восстановление пароля — TaskFlow',
        recipients=[user.email],
        body=(
            f'Здравствуйте, {user.full_name}!\n\n'
            f'Для сброса пароля перейдите по ссылке:\n{reset_url}\n\n'
            f'Ссылка действительна {TOKEN_TTL_MINUTES} минут.\n'
            f'Если вы не запрашивали сброс пароля, проигнорируйте письмо.'
        ),
    )
    mail.send(msg)
    print("[DEBUG] mail.send() выполнен")


def reset_password(raw_token: str, new_password: str) -> bool:
    """Проверяет токен и, если валиден, меняет пароль пользователя."""
    token = get_token_by_raw(raw_token)
    if not token or not token.is_valid():
        return False

    token.user.set_password(new_password)
    token.used_at = datetime.now(timezone.utc)
    db.session.commit()
    return True