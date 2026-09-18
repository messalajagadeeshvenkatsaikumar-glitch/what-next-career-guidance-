import os
import re

from dotenv import load_dotenv
from mysql.connector import Error

from db import connect_db


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, '.env'))


def safe_error_message(error):
    message = str(error)
    password = os.environ.get('MYSQL_PASSWORD')
    if password:
        message = message.replace(password, '<redacted>')
    return re.sub(r'(password\s*[=:]\s*)[^\s,;]+', r'\1<redacted>', message, flags=re.IGNORECASE)


def main():
    db = None
    try:
        db = connect_db()
        cursor = db.execute('SELECT 1')
        print(f'SELECT 1: {cursor.fetchone()}')
        cursor = db.execute('SELECT VERSION()')
        print(f'SELECT VERSION(): {cursor.fetchone()}')
        print('MySQL connection: SUCCESS')
        print('Configured database: accessible')
    except Error as error:
        print(f'MySQL connection: FAILED - {safe_error_message(error)}')
        print('Configured database: not confirmed accessible')
        raise SystemExit(1)
    except (KeyError, ValueError, OSError) as error:
        print(f'Configuration/TLS setup: FAILED - {safe_error_message(error)}')
        print('Configured database: not confirmed accessible')
        raise SystemExit(1)
    finally:
        if db is not None:
            db.close()


if __name__ == '__main__':
    main()