"""
テストヘルパー関数とフィクスチャモジュール
テスト全体で共通して使用する便利な関数や設定をここに定義します
"""

# この警告は、テスト関数の引数名が、同じファイル内で定義されている fixture の名前と同じ場合に発生します。
# 今回の場合、app_context という名前の fixture が定義されており、テスト関数の引数も同じ名前になっています。
# Pytestでは、テスト関数が fixture を使用する場合、引数の名前を fixture の名前と同じにする必要があります。
# これによって Pytest が自動的に fixture の戻り値をその引数に渡します。
# 引数 app_context が fixture の名前と一致していることで、
# Pytest が適切な fixture の値をテスト関数に渡すことができます
# 引数を削除すると、テスト関数は fixture にアクセスできなくなり、テストが失敗します
# pylint: disable=redefined-outer-name

# この警告は、ファイルの先頭に import 文がない場合に発生します。
# 今回の場合は、テスト対象の Flask アプリケーションをインポートするために必要な import 文が含まれています。
# テスト対象のアプリケーションのパスを sys.path に追加することで、
# テストファイルからアプリケーションをインポートできるようにしています。
# pylint: disable=wrong-import-position
# flake8: noqa: E402
# Disable E402 (module level import not at top of file) for this file

import os
import sys
from datetime import datetime
import pytest

# Add the parent directory to sys.path to import app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db, User, Role


@pytest.fixture
def app_context():
    """アプリケーションコンテキストのフィクスチャ"""
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['WTF_CSRF_ENABLED'] = False
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def test_client(app_context):
    """テストクライアントのフィクスチャ"""
    return app_context.test_client()


@pytest.fixture
def init_database():
    """データベースの初期化フィクスチャ"""
    with app.app_context():
        # テスト用のロールを作成
        admin_role = Role(name='admin', description='管理者')
        user_role = Role(name='user', description='一般ユーザー')
        db.session.add(admin_role)
        db.session.add(user_role)
        db.session.commit()
        # テスト用のユーザーを作成
        test_user = User(
            username='testuser',
            password='$2b$12$AbCdEfGhIjKlMnOpQrStUvWxYz01234567890AbCdEfGhIj',
            active=True,
            change_password_at=datetime.utcnow(),
            is_password_reset_by_user=True
        )
        test_user.roles.append(user_role)
        test_admin = User(
            username='testadmin',
            password='$2b$12$AbCdEfGhIjKlMnOpQrStUvWxYz01234567890AbCdEfGhIj',
            active=True,
            change_password_at=datetime.utcnow(),
            is_password_reset_by_user=True
        )
        test_admin.roles.append(admin_role)
        db.session.add(test_user)
        db.session.add(test_admin)
        db.session.commit()
        yield
        # テスト後にデータベースを削除
        db.session.remove()
        db.drop_all()


def login(client, username, password):
    """ログインヘルパー関数"""
    return client.post('/login', data={
        'username': username,
        'password': password,
    }, follow_redirects=True)


def logout(client):
    """ログアウトヘルパー関数"""
    return client.get('/logout', follow_redirects=True)
