from pathlib import Path

import db


class FakeCursor:
    def __init__(self):
        self.closed = False
        self.executed = None

    def execute(self, sql, params=()):
        self.executed = (sql, params)

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self):
        self.cursor_instance = FakeCursor()
        self.closed = False

    def cursor(self, dictionary=False):
        assert dictionary is True
        return self.cursor_instance

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        self.closed = True


def test_mysql_config_reads_aiven_environment(monkeypatch):
    monkeypatch.setenv('MYSQL_HOST', 'aiven.example')
    monkeypatch.setenv('MYSQL_PORT', '27920')
    monkeypatch.setenv('MYSQL_USER', 'avnadmin')
    monkeypatch.setenv('MYSQL_PASSWORD', 'test-password')
    monkeypatch.setenv('MYSQL_DATABASE', 'defaultdb')
    monkeypatch.setenv('MYSQL_SSL_MODE', 'REQUIRED')
    monkeypatch.setenv('MYSQL_SSL_CA', 'certs/ca.pem')

    config = db.mysql_config()

    assert config['host'] == 'aiven.example'
    assert config['port'] == 27920
    assert config['database'] == 'defaultdb'
    assert config['ssl_disabled'] is False
    assert config['ssl_verify_cert'] is False
    assert config['ssl_ca'] == str((Path(db.BASE_DIR) / 'certs/ca.pem').resolve())


def test_database_uses_mysql_placeholders_and_closes_cursors(monkeypatch):
    connection = FakeConnection()
    monkeypatch.setattr(db.mysql.connector, 'connect', lambda **kwargs: connection)
    for name, value in {
        'MYSQL_HOST': 'aiven.example',
        'MYSQL_PORT': '27920',
        'MYSQL_USER': 'avnadmin',
        'MYSQL_PASSWORD': 'test-password',
        'MYSQL_DATABASE': 'defaultdb',
        'MYSQL_SSL_MODE': 'REQUIRED',
    }.items():
        monkeypatch.setenv(name, value)

    database = db.connect_db()
    database.execute('SELECT * FROM users WHERE email = %s', ('user@example.com',))
    database.close()

    assert connection.cursor_instance.executed == (
        'SELECT * FROM users WHERE email = %s', ('user@example.com',)
    )
    assert connection.cursor_instance.closed is True
    assert connection.closed is True


def test_schema_is_mysql_compatible():
    schema = (Path(db.BASE_DIR) / 'database.sql').read_text(encoding='utf-8').lower()
    assert 'create table if not exists users' in schema
    assert 'auto_increment' in schema
    assert 'engine=innodb' in schema


def test_health_endpoint_reports_database_status(monkeypatch):
    for name, value in {
        'SECRET_KEY': 'test-secret',
        'MYSQL_HOST': 'aiven.example',
        'MYSQL_PORT': '27920',
        'MYSQL_USER': 'avnadmin',
        'MYSQL_PASSWORD': 'test-password',
        'MYSQL_DATABASE': 'defaultdb',
        'MYSQL_SSL_MODE': 'REQUIRED',
        'ADMIN_USERNAME': 'admin',
        'ADMIN_PASSWORD': 'secret',
    }.items():
        monkeypatch.setenv(name, value)

    import importlib
    import app as app_module
    importlib.reload(app_module)

    monkeypatch.setattr(app_module, 'is_connected', lambda: True)
    client = app_module.app.test_client()
    response = client.get('/health')

    assert response.status_code == 200
    assert response.get_json()['status'] == 'ok'
    assert response.get_json()['database'] == 'connected'