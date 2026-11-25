import os
from pathlib import Path
from urllib.parse import quote_plus

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / '.env')


class Config:
    # --- ИИ-агент ---
    LLM_BASE_URL = os.getenv('LLM_BASE_URL', 'http://localhost:11434/v1')
    LM_API_KEY = os.getenv('LLM_API_KEY', 'ollama')
    LLM_MODEL = os.getenv('LLM_MODEL', 'llama3.2:3b')
    LLM_TIMEOUT = int(os.getenv('LLM_TIMEOUT', '60'))
    
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-only-insecure-key')

    DB_USER = os.getenv('DB_USER', 'postgres')
    DB_PASSWORD = quote_plus(os.getenv('DB_PASSWORD', ''))
    DB_HOST = os.getenv('DB_HOST', '127.0.0.1')
    DB_PORT = os.getenv('DB_PORT', '5432')
    DB_NAME = os.getenv('DB_NAME', 'taskflow_db')

    SQLALCHEMY_DATABASE_URI = (
        f'postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}'
        f'@{DB_HOST}:{DB_PORT}/{DB_NAME}'
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    DEBUG = os.getenv('DEBUG', 'True').strip().lower() in ('1', 'true', 'yes')

    # --- Почта (SMTP) ---
    MAIL_SERVER = os.getenv('MAIL_SERVER', 'localhost')
    MAIL_PORT = int(os.getenv('MAIL_PORT', '25'))
    MAIL_USE_TLS = os.getenv('MAIL_USE_TLS', 'False').lower() == 'true'
    MAIL_USE_SSL = os.getenv('MAIL_USE_SSL', 'False').lower() == 'true'
    MAIL_USERNAME = os.getenv('MAIL_USERNAME')
    MAIL_PASSWORD = os.getenv('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.getenv('MAIL_DEFAULT_SENDER', 'noreply@taskflow.local')
    MAIL_SUPPRESS_SEND = os.getenv('MAIL_SUPPRESS_SEND', 'True').lower() == 'true'

    # --- JWT ---
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'jwt-insecure-default')
    JWT_EXPIRES_HOURS = int(os.getenv('JWT_EXPIRES_HOURS', '24'))