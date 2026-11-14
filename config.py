import os
from pathlib import Path
from urllib.parse import quote_plus

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / '.env')


class Config:
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
