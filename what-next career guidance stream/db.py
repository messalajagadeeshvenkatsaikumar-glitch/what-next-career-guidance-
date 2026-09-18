"""Database connections shared by the main Flask app and question module."""
import os
from contextlib import contextmanager
from pathlib import Path
import mysql.connector
from mysql.connector import Error

BASE_DIR = Path(__file__).resolve().parent


class Database:
    def __init__(self, connection):
        self.connection = connection
        self._cursors = []

    def execute(self, sql, params=()):
        cursor = self.connection.cursor(dictionary=True)
        self._cursors.append(cursor)
        cursor.execute(sql, params)
        return cursor

    def commit(self):
        self.connection.commit()

    def rollback(self):
        self.connection.rollback()

    def close(self):
        for cursor in self._cursors:
            try:
                cursor.close()
            except mysql.connector.Error:
                pass
        self._cursors.clear()
        self.connection.close()


def mysql_config(include_database=True):
    config = {
        'host': os.environ['MYSQL_HOST'],
        'port': int(os.environ['MYSQL_PORT']),
        'user': os.environ['MYSQL_USER'],
        'password': os.environ['MYSQL_PASSWORD'],
        'ssl_disabled': False,
    }
    ssl_mode = os.environ['MYSQL_SSL_MODE'].upper()
    if ssl_mode not in {'REQUIRED', 'VERIFY_CA', 'VERIFY_IDENTITY'}:
        raise ValueError('MYSQL_SSL_MODE must be REQUIRED, VERIFY_CA, or VERIFY_IDENTITY')
    ssl_ca = os.environ.get('MYSQL_SSL_CA')
    if ssl_ca:
        config['ssl_ca'] = str((BASE_DIR / ssl_ca).resolve()) if not os.path.isabs(ssl_ca) else ssl_ca
    config['ssl_verify_cert'] = ssl_mode in {'VERIFY_CA', 'VERIFY_IDENTITY'}
    config['ssl_verify_identity'] = ssl_mode == 'VERIFY_IDENTITY'
    if include_database:
        config['database'] = os.environ['MYSQL_DATABASE']
    return config


def connect_db():
    return Database(mysql.connector.connect(**mysql_config(True)))


@contextmanager
def database_connection():
    db = connect_db()
    try:
        yield db
    finally:
        db.close()


def is_connected():
    try:
        db = connect_db()
        db.execute('SELECT 1').fetchone()
        db.close()
        return True
    except Error:
        return False
