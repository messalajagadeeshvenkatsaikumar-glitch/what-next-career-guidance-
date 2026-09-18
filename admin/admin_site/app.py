import logging
import os
import sys
from functools import wraps

import mysql.connector
from dotenv import load_dotenv
from flask import Flask, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

# Load environment variables before importing config values.
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
load_dotenv(os.path.join(PROJECT_ROOT, '.env'))

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
from config import Config

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

app = Flask(__name__, static_folder='static', template_folder='templates')
app.config.from_object(Config)
app.config['ADMIN_PASSWORD_HASH'] = generate_password_hash(app.config['ADMIN_PASSWORD'])


def mysql_config(include_database=True):
    config = {
        'host': app.config['MYSQL_HOST'],
        'port': app.config['MYSQL_PORT'],
        'user': app.config['MYSQL_USER'],
        'password': app.config['MYSQL_PASSWORD'],
        'ssl_disabled': False,
        'ssl_verify_cert': app.config['MYSQL_SSL_MODE'] in {'VERIFY_CA', 'VERIFY_IDENTITY'},
        'ssl_verify_identity': app.config['MYSQL_SSL_MODE'] == 'VERIFY_IDENTITY',
    }
    if app.config.get('MYSQL_SSL_CA'):
        config['ssl_ca'] = app.config['MYSQL_SSL_CA']
    if include_database:
        config['database'] = app.config['MYSQL_DATABASE']
    return config


def ensure_schema():
    """Create MySQL tables for the shared app data if they do not exist."""
    conn = mysql.connector.connect(**mysql_config())
    try:
        cursor = conn.cursor()
        cursor.execute('''
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
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS quiz_results (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                top_category VARCHAR(255),
                scores TEXT,
                taken_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT fk_quiz_results_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        ''')
        cursor.execute('''
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
        cursor.execute('''
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
        app.logger.info('Ensured MySQL shared schema for database %s', app.config['MYSQL_DATABASE'])
    finally:
        cursor.close()
        conn.close()

# Allow configuring main site URL (used for linking to the public site and static files)
MAIN_SITE_URL = os.environ.get('MAIN_SITE_URL', 'http://localhost:5000')


def get_db():
    if 'db' not in g:
        try:
            g.db = mysql.connector.connect(**mysql_config())
            app.logger.info('Connected to MySQL shared database: %s', app.config['MYSQL_DATABASE'])
        except mysql.connector.Error as exc:
            app.logger.exception('Database connection failed for MySQL database %s', app.config['MYSQL_DATABASE'])
            raise RuntimeError(f'Unable to connect to the MySQL database: {app.config["MYSQL_DATABASE"]}') from exc
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get('is_admin'):
            flash('Admin login required.', 'warning')
            return redirect(url_for('admin_login'))
        return view(*args, **kwargs)
    return wrapped


@app.context_processor
def inject_globals():
    return {
        'main_site_url': MAIN_SITE_URL,
        'static_base': MAIN_SITE_URL.rstrip('/') + '/static'
    }


@app.route('/')
def root():
    return redirect(url_for('admin_login'))


@app.route('/login', methods=['GET', 'POST'])
def admin_login():
    if session.get('is_admin'):
        return redirect(url_for('admin_dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        app.logger.info('Admin login attempt for username=%s', username)

        try:
            expected_username = app.config.get('ADMIN_USERNAME', '')
            expected_hash = app.config.get('ADMIN_PASSWORD_HASH', '')

            if username == expected_username and expected_hash and check_password_hash(expected_hash, password):
                session.clear()
                session['is_admin'] = True
                flash('Welcome, admin.', 'success')
                return redirect(url_for('admin_dashboard'))
        except Exception:
            app.logger.exception('Admin login verification failed for user=%s', username)

        flash('Invalid admin credentials.', 'danger')
        return redirect(url_for('admin_login'))

    return render_template('admin_login.html')


@app.route('/logout')
def admin_logout():
    session.clear()
    flash('Admin logged out.', 'info')
    return redirect(url_for('admin_login'))


@app.route('/dashboard')
@admin_required
def admin_dashboard():
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute('SELECT id, full_name, email, age, education_level, created_at FROM users ORDER BY created_at DESC')
        users = cursor.fetchall()
        cursor.execute('SELECT * FROM feedback ORDER BY created_at DESC')
        feedback = cursor.fetchall()
        cursor.execute('SELECT * FROM contact_messages ORDER BY created_at DESC')
        messages = cursor.fetchall()
        cursor.execute('SELECT COUNT(*) AS c FROM quiz_results')
        results_count = cursor.fetchone()['c']
        app.logger.info('Dashboard loaded: %s users, %s feedback, %s messages, %s results', len(users), len(feedback), len(messages), results_count)
    except mysql.connector.Error:
        app.logger.exception('Failed to read dashboard data from the shared database')
        flash('Unable to load dashboard data. Check the database connection.', 'danger')
        return redirect(url_for('admin_login'))
    finally:
        cursor.close()

    return render_template('admin_dashboard.html', users=users, feedback=feedback, messages=messages, results_count=results_count)


@app.route('/delete/user/<int:user_id>', methods=['POST'])
@admin_required
def admin_delete_user(user_id):
    db = get_db()
    try:
        cursor = db.cursor()
        cursor.execute('DELETE FROM quiz_results WHERE user_id = %s', (user_id,))
        cursor.execute('DELETE FROM feedback WHERE user_id = %s', (user_id,))
        cursor.execute('DELETE FROM users WHERE id = %s', (user_id,))
        db.commit()
    except mysql.connector.Error:
        db.rollback()
        app.logger.exception('Failed to delete user %s', user_id)
        flash('Unable to delete user. Please try again.', 'danger')
        return redirect(url_for('admin_dashboard'))
    finally:
        cursor.close()
    flash('User and related data deleted.', 'success')
    return redirect(url_for('admin_dashboard'))


@app.route('/reset/user/<int:user_id>', methods=['POST'])
@admin_required
def admin_reset_user_password(user_id):
    new_password = request.form.get('new_password', '')
    if len(new_password) < 8:
        flash('Password must be at least 8 characters.', 'danger')
        return redirect(url_for('admin_dashboard'))

    db = get_db()
    try:
        cursor = db.cursor()
        cursor.execute(
            'UPDATE users SET password_hash = %s WHERE id = %s',
            (generate_password_hash(new_password), user_id),
        )
        if cursor.rowcount == 0:
            db.rollback()
            flash('User not found.', 'danger')
            return redirect(url_for('admin_dashboard'))
        db.commit()
    except mysql.connector.Error:
        db.rollback()
        app.logger.exception('Failed to reset password for user %s', user_id)
        flash('Unable to reset the user password. Please try again.', 'danger')
        return redirect(url_for('admin_dashboard'))
    finally:
        cursor.close()

    flash('User password reset successfully.', 'success')
    return redirect(url_for('admin_dashboard'))


@app.route('/reset/user/<int:user_id>/quiz', methods=['POST'])
@admin_required
def admin_reset_user_quiz(user_id):
    db = get_db()
    try:
        cursor = db.cursor()
        cursor.execute('DELETE FROM quiz_results WHERE user_id = %s', (user_id,))
        db.commit()
    except mysql.connector.Error:
        db.rollback()
        app.logger.exception('Failed to reset quiz results for user %s', user_id)
        flash('Unable to reset the user quiz result. Please try again.', 'danger')
        return redirect(url_for('admin_dashboard'))
    finally:
        cursor.close()

    flash('User quiz results reset successfully.', 'success')
    return redirect(url_for('admin_dashboard'))


@app.route('/delete/feedback/<int:feedback_id>', methods=['POST'])
@admin_required
def admin_delete_feedback(feedback_id):
    db = get_db()
    try:
        cursor = db.cursor()
        cursor.execute('DELETE FROM feedback WHERE id = %s', (feedback_id,))
        db.commit()
    except mysql.connector.Error:
        db.rollback()
        app.logger.exception('Failed to delete feedback %s', feedback_id)
        flash('Unable to delete feedback entry.', 'danger')
        return redirect(url_for('admin_dashboard'))
    finally:
        cursor.close()
    flash('Feedback entry deleted.', 'success')
    return redirect(url_for('admin_dashboard'))


@app.route('/delete/message/<int:message_id>', methods=['POST'])
@admin_required
def admin_delete_message(message_id):
    db = get_db()
    try:
        cursor = db.cursor()
        cursor.execute('DELETE FROM contact_messages WHERE id = %s', (message_id,))
        db.commit()
    except mysql.connector.Error:
        db.rollback()
        app.logger.exception('Failed to delete contact message %s', message_id)
        flash('Unable to delete contact message.', 'danger')
        return redirect(url_for('admin_dashboard'))
    finally:
        cursor.close()
    flash('Contact message deleted.', 'success')
    return redirect(url_for('admin_dashboard'))


if __name__ == '__main__':
    ensure_schema()
    app.run(host='127.0.0.1', port=app.config['PORT'], debug=app.config['DEBUG'])
