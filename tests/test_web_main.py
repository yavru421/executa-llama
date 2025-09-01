import importlib
import pytest

from llamatrama_agent.web import main as webmain


def test_verify_password_and_authenticate_user(tmp_path, monkeypatch):
    # Ensure users file exists with known hash using passlib if available
    users_file = webmain.USERS_FILE
    # If passlib isn't installed, verify_password may raise; in that case skip
    try:
        from passlib.hash import bcrypt
    except Exception:
        pytest.skip('passlib not installed in this environment')

    # Create a user
    udata = {
        'testuser': {
            'username': 'testuser',
            'full_name': 'Test User',
            'hashed_password': bcrypt.hash('secret'),
            'disabled': False,
        }
    }
    with open(users_file, 'w', encoding='utf-8') as fh:
        import json
        json.dump(udata, fh)

    # reload users_db
    webmain.users_db = webmain.load_users()
    user = webmain.authenticate_user('testuser', 'secret')
    assert user and user['username'] == 'testuser'


def test_get_user_from_token_str_generates_and_validates_token(tmp_path):
    # Create a test user in users_db
    webmain.users_db['alice'] = {'username': 'alice', 'full_name': 'Alice', 'hashed_password': 'x', 'disabled': False}
    token = webmain.create_access_token({'sub': 'alice'})
    user = webmain.get_user_from_token_str(token)
    assert user['username'] == 'alice'
