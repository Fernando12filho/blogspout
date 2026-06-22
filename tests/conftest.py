import os
# Must be set before app is imported so _admin_password captures it
os.environ['ADMIN_PASSWORD'] = 'testpassword'

import pytest
import db as db_module
import app as app_module
from app import app as flask_app

TEST_PASSWORD = 'testpassword'


@pytest.fixture
def app(tmp_path, monkeypatch):
    db_file = str(tmp_path / 'test.db')
    monkeypatch.setattr(db_module, 'DB_PATH', db_file)
    monkeypatch.setattr(app_module, '_admin_password', TEST_PASSWORD)
    flask_app.config.update(
        TESTING=True,
        WTF_CSRF_ENABLED=False,
        RATELIMIT_ENABLED=False,
    )
    with flask_app.app_context():
        db_module.init_db()
        yield flask_app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def auth_client(client):
    client.post('/admin/login', data={'password': TEST_PASSWORD})
    return client
