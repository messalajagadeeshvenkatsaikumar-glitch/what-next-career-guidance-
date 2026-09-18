import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent


def get_required_env(name):
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(
            f"Environment variable {name} is required. Copy .env.example to .env and set it."
        )
    return value


class Config:
    SECRET_KEY = get_required_env('SECRET_KEY')
    DEBUG = os.environ.get('FLASK_DEBUG', 'False').lower() in {'1', 'true', 'yes', 'on'}

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = False

    MYSQL_HOST = get_required_env('MYSQL_HOST')
    MYSQL_PORT = int(get_required_env('MYSQL_PORT'))
    MYSQL_USER = get_required_env('MYSQL_USER')
    MYSQL_PASSWORD = get_required_env('MYSQL_PASSWORD')
    MYSQL_DATABASE = get_required_env('MYSQL_DATABASE')

    MYSQL_SSL_MODE = get_required_env('MYSQL_SSL_MODE')
    MYSQL_SSL_CA = os.environ.get('MYSQL_SSL_CA')
    PORT = int(os.environ.get('ADMIN_PORT', '5002'))

    ADMIN_USERNAME = get_required_env('ADMIN_USERNAME')
    ADMIN_PASSWORD = get_required_env('ADMIN_PASSWORD')
