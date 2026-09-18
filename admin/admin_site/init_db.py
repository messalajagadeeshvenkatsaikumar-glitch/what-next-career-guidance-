import os
import sys

import mysql.connector

# ensure parent folder is on path to import config
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config import Config


def create_schema():
    conn = mysql.connector.connect(
        host=Config.MYSQL_HOST,
        port=Config.MYSQL_PORT,
        user=Config.MYSQL_USER,
        password=Config.MYSQL_PASSWORD,
        database=Config.MYSQL_DATABASE,
        ssl_disabled=False,
        ssl_ca=Config.MYSQL_SSL_CA,
        ssl_verify_cert=Config.MYSQL_SSL_MODE in {'VERIFY_CA', 'VERIFY_IDENTITY'},
        ssl_verify_identity=Config.MYSQL_SSL_MODE == 'VERIFY_IDENTITY',
    )
    cur = conn.cursor()

    cur.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INT AUTO_INCREMENT PRIMARY KEY,
        full_name VARCHAR(255) NOT NULL,
        email VARCHAR(255) NOT NULL UNIQUE,
        password_hash VARCHAR(255) NOT NULL,
        age INT,
        education_level VARCHAR(255),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    cur.execute('''
    CREATE TABLE IF NOT EXISTS quiz_results (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id INT NOT NULL,
        top_category VARCHAR(255),
        scores TEXT,
        taken_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        CONSTRAINT fk_quiz_results_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    ''')

    cur.execute('''
    CREATE TABLE IF NOT EXISTS feedback (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id INT,
        name VARCHAR(255),
        email VARCHAR(255),
        rating INT,
        message TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        CONSTRAINT fk_feedback_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
    )
    ''')

    cur.execute('''
    CREATE TABLE IF NOT EXISTS contact_messages (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(255),
        email VARCHAR(255),
        subject VARCHAR(255),
        message TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    conn.commit()

    cur.execute("SHOW TABLES")
    tables = [r[0] for r in cur.fetchall()]
    print('Created/verified tables:', ', '.join(tables))
    conn.close()


if __name__ == '__main__':
    print('Initializing MySQL database:', Config.MYSQL_DATABASE)
    create_schema()
    print('Initialization complete.')
