"""Flaskアプリケーションのテスト用のFlaskクライアントを作成するためのコード"""

# この警告は、テスト関数の引数名が、同じファイル内で定義されている fixture の名前と同じ場合に発生します。
# 今回の場合、flask_test_client という名前の fixture が定義されており、テスト関数の引数も同じ名前になっています。
# Pytestでは、テスト関数が fixture を使用する場合、引数の名前を fixture の名前と同じにする必要があります。
# これによって Pytest が自動的に fixture の戻り値をその引数に渡します。
# 引数 flask_test_client が fixture の名前と一致していることで、
# Pytest が適切な fixture の値をテスト関数に渡すことができます
# 引数を削除すると、テスト関数は fixture にアクセスできなくなり、テストが失敗します
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

# この警告は、ファイルの先頭に import 文がない場合に発生します。
# 今回の場合は、テスト対象の Flask アプリケーションをインポートするために必要な import 文が含まれています。
# テスト対象のアプリケーションのパスを sys.path に追加することで、
# テストファイルからアプリケーションをインポートできるようにしています。
# pylint: disable=wrong-import-position
# flake8: noqa: E402
# Disable E402 (module level import not at top of file) for this file

import sys
import os
from datetime import datetime
import pytest

# Add the parent directory to sys.path to import app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db, User, Role, UserSession


@pytest.fixture
def flask_test_client():
    """テスト用のFlaskクライアントを作成する"""
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['WTF_CSRF_ENABLED'] = False
    app.config['SESSION_TYPE'] = 'null'  # テスト用にセッションをメモリ内で管理
    app.config['SERVER_NAME'] = 'localhost'  # テスト用のサーバー名を設定

    with app.test_client() as flask_test_client_instance:
        with app.app_context():
            # データベースを作成
            db.create_all()

            # テスト用のロールを作成
            admin_role = Role.query.filter_by(name='admin').first()
            if not admin_role:
                admin_role = Role(name='admin', description='管理者')
                db.session.add(admin_role)

            user_role = Role.query.filter_by(name='user').first()
            if not user_role:
                user_role = Role(name='user', description='一般ユーザー')
                db.session.add(user_role)

            # テスト用のユーザーを作成
            test_user = User(
                username='testuser',
                password=('$2b$12$AbCdEfGhIjKlMnOpQrStUvWxYz01234'
                          '567890AbCdEfGhIj'),
                active=True,
                change_password_at=datetime.utcnow(),
                is_password_reset_by_user=True
            )
            test_user.roles.append(user_role)

            test_admin = User(
                username='testadmin',
                password=('$2b$12$AbCdEfGhIjKlMnOpQrStUvWxYz01234'
                          '567890AbCdEfGhIj'),
                active=True,
                change_password_at=datetime.utcnow(),
                is_password_reset_by_user=True
            )
            test_admin.roles.append(admin_role)

            db.session.add(test_user)
            db.session.add(test_admin)
            db.session.commit()

            yield flask_test_client_instance

            # テスト後にデータベースを削除
            db.session.remove()
            db.drop_all()


def test_index_redirect(flask_test_client):
    """トップページへのアクセスがログインページにリダイレクトされることをテスト"""
    response = flask_test_client.get('/', follow_redirects=False)
    assert response.status_code == 302  # リダイレクト
    assert ('/login' in response.location or
            '/security/login' in response.location)


def test_login_page(flask_test_client):
    """ログインページが正しく表示されることをテスト"""
    response = flask_test_client.get('/login')
    assert response.status_code == 200
    assert b'login_user_form' in response.data  # ログインフォームが含まれていることを確認


def test_home_page_requires_login(flask_test_client):
    """ホームページがログインを要求することをテスト"""
    response = flask_test_client.get('/home', follow_redirects=False)
    assert response.status_code == 302  # リダイレクト
    assert ('/login' in response.location or
            '/security/login' in response.location)


def test_session_management(flask_test_client):
    """セッション管理機能をテスト"""
    # ユーザーセッションを作成
    test_user = User.query.filter_by(username='testuser').first()
    session = UserSession(
        user_id=test_user.id,
        session_id='test-session-id',
        ip_address='127.0.0.1',
        user_agent='Test User Agent'
    )
    db.session.add(session)
    db.session.commit()

    # セッションが正しく保存されたか確認
    saved_session = UserSession.query.filter_by(
        session_id='test-session-id'
    ).first()
    assert saved_session is not None
    assert saved_session.user_id == test_user.id
    assert saved_session.ip_address == '127.0.0.1'

    # セッションロックのテスト
    saved_session.is_locked = True
    db.session.commit()

    updated_session = UserSession.query.filter_by(
        session_id='test-session-id'
    ).first()
    assert updated_session.is_locked
