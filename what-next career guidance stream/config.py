import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def get_required_env(name):
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f'Environment variable {name} is required. Copy .env.example to .env and set it.')
    return value


class Config:
    SECRET_KEY = get_required_env('SECRET_KEY')
    DEBUG = os.environ.get('FLASK_DEBUG', 'False').lower() in {'1', 'true', 'yes', 'on'}
    PORT = int(os.environ.get('PORT', '5000'))
    MAIN_SITE_URL = os.environ.get('MAIN_SITE_URL', 'http://localhost:5000')
    CORS_ALLOWED_ORIGINS = os.environ.get('CORS_ALLOWED_ORIGINS', MAIN_SITE_URL)
    MYSQL_HOST = get_required_env('MYSQL_HOST')
    MYSQL_PORT = int(get_required_env('MYSQL_PORT'))
    MYSQL_USER = get_required_env('MYSQL_USER')
    MYSQL_PASSWORD = get_required_env('MYSQL_PASSWORD')
    MYSQL_DATABASE = get_required_env('MYSQL_DATABASE')
    MYSQL_SSL_MODE = get_required_env('MYSQL_SSL_MODE')
    MYSQL_SSL_CA = os.environ.get('MYSQL_SSL_CA')
    ADMIN_USERNAME = get_required_env('ADMIN_USERNAME')
    ADMIN_PASSWORD = get_required_env('ADMIN_PASSWORD')
