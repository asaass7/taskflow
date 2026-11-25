from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, SelectField
from wtforms.validators import DataRequired, Email, EqualTo, Length, ValidationError


class RegisterForm(FlaskForm):
    """Форма регистрации нового пользователя."""
    full_name = StringField('ФИО', validators=[DataRequired(), Length(min=2, max=150)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Пароль', validators=[DataRequired(), Length(min=8)])
    confirm = PasswordField('Подтвердите пароль',
                            validators=[DataRequired(), EqualTo('password', message='Пароли не совпадают')])
    submit = SubmitField('Зарегистрироваться')

    def validate_email(self, email):
        """Проверка уникальности email."""
        # Ленивый импорт — чтобы избежать циклической зависимости
        from models import User
        if User.query.filter_by(email=email.data).first():
            raise ValidationError('Пользователь с таким email уже существует.')


class LoginForm(FlaskForm):
    """Форма входа."""
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Пароль', validators=[DataRequired()])
    submit = SubmitField('Войти')


class TaskForm(FlaskForm):
    """Форма создания и редактирования задачи."""
    title = StringField('Название', validators=[DataRequired(), Length(max=200)])
    description = StringField('Описание')
    priority = SelectField('Приоритет', choices=[
        ('low', 'Низкий'), ('medium', 'Средний'), ('high', 'Высокий')
    ], default='medium')
    status = SelectField('Статус', choices=[
        ('new', 'Новая'), ('in_progress', 'В работе'),
        ('review', 'На проверке'), ('done', 'Выполнена'), ('cancelled', 'Отменена')
    ], default='new')
    submit = SubmitField('Сохранить')


class ForgotPasswordForm(FlaskForm):
    """Форма запроса сброса пароля по email."""
    email = StringField('Email', validators=[DataRequired(), Email()])
    submit = SubmitField('Отправить ссылку')


class ResetPasswordForm(FlaskForm):
    """Форма установки нового пароля."""
    password = PasswordField('Новый пароль', validators=[DataRequired(), Length(min=8)])
    confirm = PasswordField('Подтвердите пароль',
                            validators=[DataRequired(), EqualTo('password', message='Пароли не совпадают')])
    submit = SubmitField('Сохранить новый пароль')