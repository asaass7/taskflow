from datetime import datetime, timezone

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from extensions import db, login_manager


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.BigInteger, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(150), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='user',
                     server_default='user')
    is_active = db.Column(db.Boolean, nullable=False, default=True,
                          server_default=db.text('true'))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False,
                           default=lambda: datetime.now(timezone.utc),
                           server_default=db.func.now())

    projects = db.relationship('Project', back_populates='owner',
                               cascade='all, delete-orphan', lazy='dynamic')
    authored_tasks = db.relationship('Task', back_populates='author',
                                     foreign_keys='Task.author_id',
                                     cascade='all, delete-orphan', lazy='dynamic')
    assigned_tasks = db.relationship('Task', back_populates='assignee',
                                     foreign_keys='Task.assignee_id',
                                     lazy='dynamic')

    __table_args__ = (
        db.CheckConstraint("role IN ('user','manager','admin')",
                           name='ck_users_role'),
    )

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class Project(db.Model):
    __tablename__ = 'projects'

    id = db.Column(db.BigInteger, primary_key=True)
    owner_id = db.Column(db.BigInteger,
                         db.ForeignKey('users.id', ondelete='CASCADE'),
                         nullable=False, index=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False,
                           default=lambda: datetime.now(timezone.utc),
                           server_default=db.func.now())

    owner = db.relationship('User', back_populates='projects')
    tasks = db.relationship('Task', back_populates='project',
                            cascade='all, delete-orphan', lazy='dynamic')


class Task(db.Model):
    __tablename__ = 'tasks'

    id = db.Column(db.BigInteger, primary_key=True)
    project_id = db.Column(db.BigInteger,
                           db.ForeignKey('projects.id', ondelete='CASCADE'),
                           nullable=True, index=True)
    author_id = db.Column(db.BigInteger,
                          db.ForeignKey('users.id', ondelete='CASCADE'),
                          nullable=False)
    assignee_id = db.Column(db.BigInteger,
                            db.ForeignKey('users.id', ondelete='SET NULL'),
                            nullable=True, index=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    status = db.Column(db.String(20), nullable=False, default='new',
                       server_default='new')
    priority = db.Column(db.String(10), nullable=False, default='medium',
                         server_default='medium')
    due_date = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False,
                           default=lambda: datetime.now(timezone.utc),
                           server_default=db.func.now())

    project = db.relationship('Project', back_populates='tasks')
    author = db.relationship('User', back_populates='authored_tasks',
                             foreign_keys=[author_id])
    assignee = db.relationship('User', back_populates='assigned_tasks',
                               foreign_keys=[assignee_id])
    comments = db.relationship('Comment', back_populates='task',
                               cascade='all, delete-orphan', lazy='dynamic')
    task_tags = db.relationship('TaskTag', back_populates='task',
                                cascade='all, delete-orphan', lazy='dynamic')

    __table_args__ = (
        db.CheckConstraint(
            "status IN ('new','in_progress','review','done','cancelled')",
            name='ck_tasks_status'),
        db.CheckConstraint(
            "priority IN ('low','medium','high')",
            name='ck_tasks_priority'),
    )


class TaskTag(db.Model):
    __tablename__ = 'task_tags'

    task_id = db.Column(db.BigInteger,
                        db.ForeignKey('tasks.id', ondelete='CASCADE'),
                        primary_key=True)
    tag = db.Column(db.String(50), primary_key=True)

    task = db.relationship('Task', back_populates='task_tags')


class Comment(db.Model):
    __tablename__ = 'comments'

    id = db.Column(db.BigInteger, primary_key=True)
    task_id = db.Column(db.BigInteger,
                        db.ForeignKey('tasks.id', ondelete='CASCADE'),
                        nullable=False, index=True)
    author_id = db.Column(db.BigInteger,
                          db.ForeignKey('users.id', ondelete='CASCADE'),
                          nullable=False)
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False,
                           default=lambda: datetime.now(timezone.utc),
                           server_default=db.func.now())

    task = db.relationship('Task', back_populates='comments')


class PasswordResetToken(db.Model):
    __tablename__ = 'password_reset_token'

    id = db.Column(db.BigInteger, primary_key=True)
    user_id = db.Column(db.BigInteger,
                        db.ForeignKey('users.id', ondelete='CASCADE'),
                        nullable=False, index=True)
    token_hash = db.Column(db.String(64), unique=True, nullable=False)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
    used_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False,
                           default=lambda: datetime.now(timezone.utc),
                           server_default=db.func.now())

    user = db.relationship('User', backref=db.backref('reset_tokens',
                                                      lazy='dynamic'))

    def is_valid(self) -> bool:
        return self.used_at is None and self.expires_at > datetime.now(timezone.utc)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class AiMessage(db.Model):
    __tablename__ = 'ai_messages'

    id = db.Column(db.BigInteger, primary_key=True)
    user_id = db.Column(db.BigInteger,
                        db.ForeignKey('users.id', ondelete='CASCADE'),
                        nullable=False, index=True)
    role = db.Column(db.String(10), nullable=False)  # 'user' / 'assistant'
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False,
                           default=lambda: datetime.now(timezone.utc))