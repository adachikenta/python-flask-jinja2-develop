"""Flask Application"""
import os
import re
import uuid
from datetime import datetime, timedelta
from functools import wraps
from urllib.parse import urlparse
import coverage

import plotly.graph_objs as go
import plotly.offline as pyo
from flask import (Flask, flash, g, jsonify, redirect, render_template,
                   request, session, url_for, abort)
from flask_babel import Babel, gettext
from flask_security import (RoleMixin, Security, SQLAlchemyUserDatastore,
                            UserMixin, current_user, hash_password,
                            login_required, roles_required, signals)
from flask_security.decorators import auth_required
from flask_security.forms import ChangePasswordForm, LoginForm
from flask_security.utils import (logout_user,
                                  verify_and_update_password)
from flask_session import Session
from flask_sqlalchemy import SQLAlchemy
from wtforms import Form, StringField
from wtforms.validators import DataRequired

app = Flask(__name__, template_folder="templates")
db_path = os.path.join(app.root_path, "__data__", "ews.sqlite3")
os.makedirs(os.path.dirname(db_path), exist_ok=True)
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"

db = SQLAlchemy(app)

###################################################
# セッション管理（flask_session + filesystem）
###################################################
app.config["SECURITY_REMEMBER_ME"] = False

app.config["SESSION_TYPE"] = "filesystem"
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_USE_SIGNER"] = True
app.config["SESSION_KEY_PREFIX"] = "ews_session:"
app.config["SESSION_SERIALIZATION_FORMAT"] = "json"

session_path = os.path.join(app.root_path, "__data__", "flask_session_files")
app.config["SESSION_FILE_DIR"] = session_path
app.config["SESSION_FILE_THRESHOLD"] = (
    100  # セッションファイルの数が100を超えた場合に古いファイルを削除
)

app.config["SESSION_COOKIE_NAME"] = "ews_session"
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SECURE"] = False  # HTTPSを使用する場合はTrueに設定
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"  # CSRF対策のためにSameSite属性を設定

app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(
    minutes=30
)  # 30分のセッションタイムアウト
# app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(seconds=10)

sess = Session(app)
sess.init_app(app)


class UserSession(db.Model):
    """セッション管理用のテーブルを定義"""
    id = db.Column(
        db.String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    user_id = db.Column(
        db.String(36),
        db.ForeignKey("user.id"),
        nullable=False
    )
    session_id = db.Column(
        db.String(255), nullable=False, unique=True
    )
    created_at = db.Column(
        db.DateTime(), nullable=False, default=datetime.utcnow
    )
    last_activity = db.Column(
        db.DateTime(), nullable=False, default=datetime.utcnow
    )
    is_locked = db.Column(
        db.Boolean(), default=False
    )
    ip_address = db.Column(
        db.String(45), nullable=True
    )
    user_agent = db.Column(
        db.String(255), nullable=True
    )

    # ユーザーとのリレーション
    user = db.relationship(
        "User",
        backref=db.backref("sessions", lazy="dynamic")
    )


@app.before_request
def check_session():
    """リクエストごとにセッションをチェックし、必要に応じて更新"""
    # ログインユーザーのみチェック
    if current_user.is_authenticated:
        session_id = request.cookies.get(app.config["SESSION_COOKIE_NAME"])

        # セッションIDがない場合は処理しない
        if not session_id:
            return

        # ログアウト、ログイン、セッションロック関連のパス、APIパスはチェックから除外
        if (
            request.path in [
                "/logout",
                "/unlock_session",
                "/login", "/lock_session"
            ]
            or request.path.startswith("/security/login")
            or request.path.startswith("/api/session/status")
        ):
            return

        # DB内のセッション情報を取得
        user_session = UserSession.query.filter_by(
            user_id=current_user.id, session_id=session_id
        ).first()

        # セッションがDBに存在しない場合、新規作成（ログイン直後の場合など）
        if not user_session and request.path != "/login":
            # 既存のセッションがある場合は削除（1ユーザー1セッション制限）
            UserSession.query.filter_by(user_id=current_user.id).delete()
            db.session.commit()

            # 新しいセッションを作成
            user_session = UserSession(
                user_id=current_user.id,
                session_id=session_id,
                ip_address=request.remote_addr,
                user_agent=(
                    request.user_agent.string[:255]
                    if request.user_agent.string
                    else None
                ),
            )
            db.session.add(user_session)
            db.session.commit()
        # セッションがDBに存在する場合
        elif user_session:
            # セッションがロックされている場合、現在のページを保存してログインページにリダイレクト
            if user_session.is_locked and not (
                request.path == "/login" or
                request.path.startswith("/security/login")
            ):
                # 現在のページパスをセッションに保存（自動ロック時にもリダイレクト用）
                if request.path and not request.path.startswith(
                    (
                        "/login",
                        "/logout",
                        "/security/login",
                        "/security/logout",
                        "/lock_session",
                    )
                ):
                    # セッションが削除される前にパスを保存
                    session["redirect_after_login"] = request.path

                # Flask-Securityのユーザーセッションをクリア
                logout_user()
                flash(
                    "セッションがロックされています。再度ログインしてください。",
                    "warning",
                )
                return redirect(url_for("security.login"))

            # 最終アクティビティ時間を更新
            user_session.last_activity = datetime.utcnow()
            db.session.commit()


@app.before_request
def check_expired_sessions():
    """期限切れのセッションをチェックし、必要に応じてロックする"""
    # APIリクエストやstatic、cssなどのリクエストは除外
    if request.path.startswith("/static/"):
        return
    if request.path.startswith("/favicon"):
        return

    # セッションの有効期限をチェックして必要に応じてロック
    lock_expired_sessions()


def lock_expired_sessions():
    """期限切れのセッションをロックする
    """
    expiry_time = datetime.utcnow() - app.config["PERMANENT_SESSION_LIFETIME"]
    expired_sessions = UserSession.query.filter(
        UserSession.last_activity < expiry_time,
        UserSession.is_locked.is_(False)
    ).all()

    for user_session in expired_sessions:
        user_session.is_locked = True

        # セッションロックをログに記録
        user = User.query.get(user_session.user_id)
        if user:
            message = "自動セッションロック (タイムアウト):"
            log_security_event(
                "SESSION_AUTO_LOCK",
                f"{message} {user.username} - {user_session.session_id}",
            )

            # 現在のページパスをセッションに保存（再ログイン後のリダイレクト用）
            if request.path and not request.path.startswith(
                (
                    "/login",
                    "/logout",
                    "/security/login",
                    "/security/logout",
                    "/lock_session",
                )
            ):
                session["redirect_after_login"] = request.path

    if expired_sessions:
        db.session.commit()


# 手動セッションロック用のルート
@app.route("/lock_session")
@login_required
def lock_session():
    """セッションを手動でロックする"""
    session_id = request.cookies.get(app.config["SESSION_COOKIE_NAME"])
    username = current_user.username if current_user.is_authenticated else None

    # 現在のページURLをセッションに保存して、再ログイン後に元のページに戻れるようにする
    referrer = request.referrer
    if referrer:
        # アプリケーションのURL内の相対パスを抽出
        parsed_url = urlparse(referrer)
        path = parsed_url.path

        # 安全なパスのみを保存（ログイン関連のパスは除外）
        excluded_paths = [
            "/login",
            "/logout",
            "/security/login",
            "/security/logout",
            "/lock_session",
        ]
        if path and path not in excluded_paths:
            session["redirect_after_login"] = path

    if session_id and username:
        user_session = UserSession.query.filter_by(
            user_id=current_user.id, session_id=session_id
        ).first()

        if user_session:
            user_session.is_locked = True
            db.session.commit()
            log_security_event(
                "SESSION_LOCK",
                f"ユーザーによるセッションロック: {username} - {session_id}",
            )
            flash(
                "セッションをロックしました。ログイン画面からログインして再開できます。",
                "info",
            )

    # セッション関連のフラッシュデータを保存してからログアウト
    logout_user()

    # ログイン画面にリダイレクト
    return redirect(url_for("security.login"))


# セッションアンロック（再ログイン）用の処理をuser_authenticatedシグナルに追加
@signals.user_authenticated.connect_via(app)
# pylint: disable=unused-argument
def unlock_session(signal_sender_flask_app, user, **extra):
    """ユーザーが再ログインした際にセッションをアンロックする"""
    session_id = request.cookies.get(app.config["SESSION_COOKIE_NAME"])

    if session_id:
        # 既存のロックされたセッションを検索
        user_session = UserSession.query.filter_by(
            user_id=user.id, session_id=session_id
        ).first()

        if user_session:
            was_locked = user_session.is_locked
            # セッションをアンロック
            user_session.is_locked = False
            user_session.last_activity = datetime.utcnow()
            db.session.commit()

            # ロック解除をログに記録
            if was_locked:
                log_security_event(
                    "SESSION_UNLOCK",
                    f"セッションロック解除: {user.username} - {session_id}",
                    user,
                )
        else:
            # セッションIDですでに存在するセッションがないか確認
            existing_by_session = UserSession.query.filter_by(
                session_id=session_id
            ).first()
            if existing_by_session:
                # セッションIDが既に存在する場合は、そのセッションを更新する
                existing_by_session.user_id = user.id
                existing_by_session.last_activity = datetime.utcnow()
                existing_by_session.is_locked = False
                existing_by_session.ip_address = request.remote_addr
                existing_by_session.user_agent = (
                    request.user_agent.string[:255]
                    if request.user_agent.string
                    else None
                )

                # このユーザーの他のセッションを削除
                UserSession.query.filter(
                    UserSession.user_id == user.id,
                    UserSession.id != existing_by_session.id,
                ).delete()
            else:
                # 他の既存セッションを削除（1ユーザー1セッション制限）
                old_sessions = UserSession.query.filter_by(
                    user_id=user.id
                ).all()
                if old_sessions:
                    # 古いセッションが存在する場合はログに記録
                    message = "新しいセッションによる古いセッションの置き換え:"
                    log_security_event(
                        "SESSION_REPLACED",
                        f"{message} {user.username} - {session_id}",
                        user,
                    )
                    UserSession.query.filter_by(user_id=user.id).delete()

            db.session.commit()

            # セッションが既に存在するかチェック
            existing_session = UserSession.query.filter_by(
                session_id=session_id
            ).first()

            if existing_session:
                # 既存のセッションが見つかった場合は更新する
                existing_session.user_id = user.id
                existing_session.ip_address = request.remote_addr
                existing_session.user_agent = (
                    request.user_agent.string[:255]
                    if request.user_agent.string
                    else None
                )
                existing_session.last_activity = datetime.utcnow()
                existing_session.is_locked = False
                db.session.commit()
            else:
                # 新しいセッションを作成
                new_session = UserSession(
                    user_id=user.id,
                    session_id=session_id,
                    ip_address=request.remote_addr,
                    user_agent=(
                        request.user_agent.string[:255]
                        if request.user_agent.string
                        else None
                    ),
                )
                db.session.add(new_session)
                db.session.commit()


# ログアウト時にセッションをDBから削除
@signals.user_unauthenticated.connect_via(app)
# pylint: disable=unused-argument
def remove_session_on_logout(signal_sender_flask_app, user=None, **extra):
    """ログアウト時にセッションをDBから削除する"""
    # userがNoneの場合は処理しない（未認証アクセス時の場合など）
    if user:
        session_id = request.cookies.get(app.config["SESSION_COOKIE_NAME"])
        if session_id:
            UserSession.query.filter_by(
                user_id=user.id,
                session_id=session_id
            ).delete()
            db.session.commit()


@app.route("/api/session/config", methods=["GET"])
@login_required
def get_session_config():
    """セッション設定値をJSONで返す（クライアント側のカウントダウン機能用）"""
    timeout_seconds = app.config["PERMANENT_SESSION_LIFETIME"].total_seconds()
    return jsonify(
        {
            "timeout_seconds": timeout_seconds,
            "warning_threshold": 300,  # 警告表示を開始する秒数（タイムアウトの5分前から警告する）
        }
    )


@app.route("/api/session/status", methods=["GET"])
@login_required
def get_session_status():
    """セッションの状態情報をJSONで返す（クライアント側のカウントダウン同期用）"""
    if not current_user.is_authenticated:
        return jsonify({"error": "Unauthorized"}), 401

    session_id = request.cookies.get(app.config["SESSION_COOKIE_NAME"])
    if not session_id:
        return jsonify({"error": "No session"}), 400

    user_session = UserSession.query.filter_by(
        user_id=current_user.id, session_id=session_id
    ).first()

    if not user_session:
        return jsonify({"error": "Invalid session"}), 400

    # セッションの最終アクティビティからの経過時間を計算
    now = datetime.utcnow()
    last_activity = user_session.last_activity
    elapsed_seconds = (now - last_activity).total_seconds()

    # セッションタイムアウトまでの残り時間を計算
    timeout_seconds = app.config["PERMANENT_SESSION_LIFETIME"].total_seconds()
    remaining_seconds = max(0, timeout_seconds - elapsed_seconds)

    return jsonify(
        {
            "is_locked": user_session.is_locked,
            "last_activity": last_activity.isoformat(),
            "timeout_seconds": timeout_seconds,
            "remaining_seconds": remaining_seconds,
        }
    )


# セッション管理のためのセキュリティログ機能
class SecurityLog(db.Model):
    """セキュリティログのテーブルを定義"""
    id = db.Column(
        db.String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    user_id = db.Column(
        db.String(36),
        db.ForeignKey("user.id"),
        nullable=True
    )
    timestamp = db.Column(
        db.DateTime(),
        nullable=False, default=datetime.utcnow
    )
    event_type = db.Column(
        db.String(50),
        nullable=False
    )
    description = db.Column(
        db.String(255),
        nullable=False
    )
    ip_address = db.Column(
        db.String(45),
        nullable=True
    )
    user_agent = db.Column(
        db.String(255),
        nullable=True
    )

    # ユーザーとのリレーション（オプショナル）
    user = db.relationship(
        "User",
        backref=db.backref("security_logs", lazy="dynamic")
    )


def log_security_event(event_type, description, user=None):
    """セキュリティイベントをログに記録する"""
    user_id = (
        user.id
        if user
        else (current_user.id if current_user.is_authenticated else None)
    )

    if request.user_agent.string:
        user_agent = request.user_agent.string[:255]
    else:
        user_agent = None
    security_log_entry = SecurityLog(
        user_id=user_id,
        event_type=event_type,
        description=description,
        ip_address=request.remote_addr,
        user_agent=user_agent
    )
    db.session.add(security_log_entry)
    db.session.commit()


@signals.user_authenticated.connect_via(app)
# pylint: disable=unused-argument
def on_user_logged_in(signal_sender_flask_app, user, **extra):
    """ユーザーログイン時にセキュリティログを記録する"""
    log_security_event("LOGIN", f"ユーザーログイン: {user.username}", user)


@signals.user_unauthenticated.connect_via(app)
# pylint: disable=unused-argument
def on_user_logged_out(signal_sender_flask_app, user=None, **extra):
    """ユーザーログアウト時にセキュリティログを記録する"""
    if user:
        log_security_event("LOGOUT", f"ユーザーログアウト: {user.username}", user)


###################################################
# 言語設定管理
###################################################
LANGUAGES = {
    "ja": "日本語",
    "en": "English",
}
app.config["BABEL_DEFAULT_LOCALE"] = "ja"
app.config["BABEL_TRANSLATION_DIRECTORIES"] = "translations"
app.config["LANGUAGES"] = LANGUAGES


def get_locale():
    """セッションまたはブラウザの設定から言語を取得"""
    if "language" in session:
        return session["language"]
    return (
        request.accept_languages.best_match(list(LANGUAGES.keys()))
        or app.config["BABEL_DEFAULT_LOCALE"]
    )


babel = Babel(app)
babel.init_app(app, locale_selector=get_locale)


@app.before_request
def before_request():
    """リクエスト前に実行されるフック"""
    g.locale = get_locale()


def update_lang(req):
    """セッションに言語を更新する"""
    if req.method == "POST" and "language" in req.form:
        session["language"] = req.form.get("language")
        session.modified = True


@app.context_processor
def inject_conf_var():
    """テンプレートコンテキストに言語設定を注入"""
    return dict(
        AVAILABLE_LANGUAGES=LANGUAGES,
        CURRENT_LANGUAGE=session.get(
            "language",
            app.config["BABEL_DEFAULT_LOCALE"]
        ),
    )


@app.route("/set_language", methods=["POST"])
def set_language():
    """言語をセッションに設定するエンドポイント"""
    if request.method == "POST" and "language" in request.form:
        language = request.form.get("language")
        # Validate language is in our supported languages
        if language in LANGUAGES:
            # 現在の言語と異なる場合のみセッションを更新
            session["language"] = language
            session.modified = True

    # リファラーURLを取得
    next_url = request.referrer or url_for("index")

    # URLから既存の lang_switched パラメータを削除
    if "lang_switched=" in next_url:
        # URLにクエリパラメータがある場合
        url_parts = next_url.split("?")
        base_url = url_parts[0]
        if len(url_parts) > 1:
            # クエリパラメータを分割して lang_switched を含むものを除外
            query_parts = url_parts[1].split("&")
            query_parts = [
                part for part in query_parts
                if not part.startswith("lang_switched=")
            ]
            if query_parts:
                next_url = base_url + "?" + "&".join(query_parts)
            else:
                next_url = base_url

    # 言語切り替えフラグを付加（JavaScriptで検出用）
    if "?" in next_url:
        next_url += "&lang_switched=1"
    else:
        next_url += "?lang_switched=1"

    return redirect(next_url)


@app.route("/api/translations/session", methods=["GET"])
def get_session_translations():
    """セッション管理用のJavaScript用翻訳データをJSONで提供"""
    # クエリパラメータから言語を取得（指定がなければセッション/ブラウザ設定）
    requested_lang = request.args.get("lang")

    if requested_lang and requested_lang in LANGUAGES:
        # 一時的に言語を変更して翻訳を取得
        original_lang = session.get("language")

        # リクエストで明示的に指定された言語に設定
        with app.test_request_context():
            session["language"] = requested_lang

            translations = {
                "session_remaining_time": gettext("session_remaining_time"),
                "lock_now": gettext("lock_now"),
                "change_password": gettext("change_password"),
                "logout": gettext("logout"),
            }

            # 元の言語設定に戻す
            if original_lang:
                session["language"] = original_lang
            else:
                session.pop("language", None)
    else:

        translations = {
            "session_remaining_time": gettext("session_remaining_time"),
            "lock_now": gettext("lock_now"),
            "change_password": gettext("change_password"),
            "logout": gettext("logout"),
        }

    return jsonify(translations)


###################################################
# 時間フォーマット変換
###################################################
def timestamper(timestamp):
    """YYYYMMDDHHMMSS形式のタイムスタンプをフォーマット"""
    convdate = f"{timestamp[:4]}-{timestamp[4:6]}-{timestamp[6:8]}"
    convtime = f"{timestamp[8:10]}:{timestamp[10:12]}:{timestamp[12:]}"
    return f"{convdate} {convtime}"


def format_date(timestamp):
    """YYYYMMDD形式のタイムスタンプをフォーマット"""
    convdate = f"{timestamp[:4]}-{timestamp[4:6]}-{timestamp[6:8]}"
    convtime = f"{timestamp[8:10]}:{timestamp[10:12]}:{timestamp[12:14]}"
    return f"{convdate} {convtime}"


###################################################
# ロールとユーザー管理
###################################################
initial_roles = {
    "admin": {"name": "admin", "description": "管理者"},
    "user": {"name": "user", "description": "一般ユーザー"}
}


initial_users = {
    "admin": {"name": "admin", "pass": "Admin999!", "role": "admin"},
    "user": {"name": "user", "pass": "User999!", "role": "user"}
}

app.config["SECRET_KEY"] = "super-secret"
app.config["SECURITY_REGISTERABLE"] = False
app.config["SECURITY_RECOVERABLE"] = False
app.config["SECURITY_CHANGEABLE"] = True
app.config["SECURITY_PASSWORD_SALT"] = "salt"
app.config["SECURITY_SEND_REGISTER_EMAIL"] = False
# app.config['PASSWORD_EXPIRATION_SECONDS'] = 90 * 24 * 60 * 60  # 90 days
app.config["PASSWORD_EXPIRATION_SECONDS"] = 24 * 60 * 60  # 1 day
app.config["SECURITY_PASSWORD_LENGTH_MIN"] = 8
app.config["SECURITY_PASSWORD_LENGTH_MAX"] = 128
app.config["SECURITY_LOGIN_ATTEMPT_LIMIT"] = 3
app.config["SECURITY_SEND_PASSWORD_CHANGE_EMAIL"] = False
app.config["SECURITY_LOGIN_LOCKOUT_PERIOD"] = 10 * 60  # 10 minutes
app.config["SECURITY_USER_IDENTITY_ATTRIBUTES"] = [
    {"username": {"mapper": lambda x: x, "case_insensitive": True}}
]
app.config["SECURITY_MSG_USER_DOES_NOT_EXIST"] = (
    "ユーザー名もしくはパスワードが間違っています",
    "error",
)
app.config["SECURITY_MSG_INVALID_PASSWORD"] = (
    "ユーザー名もしくはパスワードが間違っています",
    "error",
)
app.config["SECURITY_MSG_PASSWORD_NOT_PROVIDED"] = (
    "パスワードを入力してください",
    "error",
)
app.config["SECURITY_MSG_USER_DOES_NOT_EXIST"] = (
    "ユーザー名もしくはパスワードが間違っています",
    "error",
)
app.config["SECURITY_MSG_DISABLED_ACCOUNT"] = (
    "アカウントが無効になっています",
    "error",
)
app.config["SECURITY_MSG_LOGIN_EXPIRED"] = (
    "ログイン期限切れです。再度ログインしてください。",
    "error",
)
app.config["SECURITY_MSG_RETYPE_PASSWORD_MISMATCH"] = (
    "パスワードが一致しません",
    "error",
)
app.config["SECURITY_MSG_INVALID_REDIRECT"] = ("無効なリダイレクト", "error")
app.config["SECURITY_MSG_PASSWORD_RESET"] = (
    "パスワードがリセットされました。ログインしてください。",
    "success",
)
app.config["SECURITY_MSG_PASSWORD_IS_THE_SAME"] = (
    "新しいパスワードは現在のパスワードと異なるものを設定してください",
    "error",
)
app.config["SECURITY_MSG_PASSWORD_INVALID_LENGTH"] = (
    "パスワードは8文字以上必要です",
    "error",
)
app.config["SECURITY_MSG_LOGIN_ATTEMPTS_EXCEEDED"] = (
    "ログイン試行回数が上限を超えました。",
    "error",
)

roles_users = db.Table(
    "roles_users",
    db.Column("user_id", db.String(36), db.ForeignKey("user.id")),
    db.Column("role_id", db.String(36), db.ForeignKey("role.id")),
)


class Role(db.Model, RoleMixin):
    """ロールモデル"""
    id = db.Column(
        db.String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    name = db.Column(db.String(80), unique=True)
    description = db.Column(db.String(255))

    def __str__(self):
        return self.name


class User(db.Model, UserMixin):
    """ユーザーモデル"""
    id = db.Column(
        db.String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    fs_uniquifier = db.Column(
        db.String(255),
        unique=True,
        nullable=False,
        default=lambda: str(uuid.uuid4())
    )
    email = db.Column(db.String(255), nullable=True, default=None)
    username = db.Column(db.String(255), unique=True)
    password = db.Column(db.String(255))
    change_password_at = db.Column(
        db.DateTime(), nullable=True, default=datetime.utcnow
    )
    active = db.Column(db.Boolean(), default=True)
    created_at = db.Column(
        db.DateTime(),
        nullable=False,
        default=datetime.utcnow
    )
    login_attempts = db.Column(db.Integer(), default=0)
    last_login_at = db.Column(db.DateTime(), nullable=True, default=None)
    account_lockout_until = db.Column(
        db.DateTime(),
        nullable=True,
        default=None
    )
    is_password_reset_by_user = db.Column(db.Boolean(), default=False)
    roles = db.relationship(
        "Role",
        secondary=roles_users,
        backref=db.backref("users", lazy="dynamic")
    )

    def __str__(self):
        return self.username


app.config["SECURITY_LOGIN_USER_TEMPLATE"] = "security/login_user.html"


class CustomLoginForm(LoginForm):
    """カスタムログインフォーム"""
    # emailフィールドを除去し、usernameフィールドを追加
    email = None
    username = StringField("ユーザー名", validators=[DataRequired()])

    def validate(self, extra_validators=None, **kwargs):
        # まず基本的なバリデーション（必須フィールドなど）をチェック
        if not Form.validate(self, extra_validators=extra_validators):
            # 必須フィールドエラーがある場合は日本語に翻訳
            if (
                "username" in self.errors
                and self.username.errors
                and "This field is required." in self.username.errors
            ):
                self.username.errors = ["ユーザー名を入力してください"]
            if (
                "password" in self.errors
                and self.password.errors
                and "This field is required." in self.password.errors
            ):
                self.password.errors = ["パスワードを入力してください"]
            return False

        # usernameでユーザーを探す
        self.user = User.query.filter_by(username=self.username.data).first()

        if self.user is None:
            # ユーザーが見つからない場合、具体的なエラーではなく一般的なエラーメッセージを表示
            self.username.errors.append("ユーザー名もしくはパスワードが間違っています")
            # フラッシュメッセージも設定（両方表示される場合があるが問題ない）
            flash("ユーザー名もしくはパスワードが間違っています", "error")
            return False

        # アカウントがロックされているかチェック
        if (
            self.user.account_lockout_until
            and self.user.account_lockout_until > datetime.utcnow()
        ):
            lockout_message = app.config.get(
                "SECURITY_MSG_LOGIN_ATTEMPTS_EXCEEDED",
                ("ログイン試行回数が上限を超えました。", "error"),
            )
            error_msg = lockout_message[0].format()

            self.username.errors.append(error_msg)
            flash(error_msg, "error")
            return False

        if not verify_and_update_password(self.password.data, self.user):
            self.user.login_attempts += 1

            # 失敗回数が上限を超えたらアカウントをロック
            login_attempt_limit = app.config.get(
                "SECURITY_LOGIN_ATTEMPT_LIMIT",
                5
            )
            if self.user.login_attempts >= login_attempt_limit:
                lockout_period = app.config.get(
                    "SECURITY_LOGIN_LOCKOUT_PERIOD",
                    300
                )
                delta = timedelta(
                    seconds=lockout_period
                )
                self.user.account_lockout_until = datetime.utcnow() + delta

                lockout_message = app.config.get(
                    "SECURITY_MSG_LOGIN_ATTEMPTS_EXCEEDED",
                    ("ログイン試行回数が上限を超えました。", "error"),
                )
                error_msg = lockout_message[0].format()
                self.username.errors.append(error_msg)
                flash(error_msg, "error")
            else:
                # パスワードが間違っている場合も、同様の一般的なエラーメッセージを表示
                self.password.errors.append(
                    "ユーザー名もしくはパスワードが間違っています"
                )
                flash("ユーザー名もしくはパスワードが間違っています", "error")

            db.session.commit()
            return False

        # ログイン成功時は失敗カウントとロックをリセット
        self.user.login_attempts = 0
        self.user.account_lockout_until = None
        self.user.last_login_at = datetime.utcnow()
        db.session.commit()

        return True


app.config["SECURITY_CHANGE_PASSWORD_TEMPLATE"] = (
    "security/change_password.html"
)


class CustomChangePasswordForm(ChangePasswordForm):
    """カスタムパスワード変更フォーム"""

    def validate(self, extra_validators=None, **kwargs):
        has_errors = False
        if not Form.validate(
            self,
            extra_validators=extra_validators,
            **kwargs
        ):
            has_errors = True

        # 現在のパスワードの検証
        user = current_user
        is_current_password_valid = verify_and_update_password(
            self.password.data,
            user
        )
        if not is_current_password_valid:
            self.password.errors.append("現在のパスワードが間違っています。")
            has_errors = True
        else:
            # 新しいパスワードが現在のパスワードと同じでないことを確認
            if self.new_password.data == self.password.data:
                self.password.errors.append(
                    "新しいパスワードは現在のパスワードと異なるものを設定してください。"
                )
                has_errors = True

        # 新しいパスワードの長さチェック（8文字以上、128文字以下）
        if len(self.new_password.data) < 8:
            self.password.errors.append("パスワードは8文字以上必要です。")
            has_errors = True

        if len(self.new_password.data) > 128:
            self.password.errors.append("パスワードは128文字以下である必要があります。")
            has_errors = True

        # 新しいパスワードの文字種チェック
        if not re.search(r"[A-Z]", self.new_password.data):
            self.password.errors.append(
                "パスワードには少なくとも1つの大文字が必要です。"
            )
            has_errors = True
        if not re.search(r"[a-z]", self.new_password.data):
            self.password.errors.append(
                "パスワードには少なくとも1つの小文字が必要です。"
            )
            has_errors = True
        if not re.search(r"[0-9]", self.new_password.data):
            self.password.errors.append("パスワードには少なくとも1つの数字が必要です。")
            has_errors = True
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', self.new_password.data):
            self.password.errors.append(
                "パスワードには少なくとも1つの特殊文字が必要です。"
            )
            has_errors = True

        # 確認用パスワードと一致するか
        if self.new_password.data != self.new_password_confirm.data:
            self.password.errors.append("確認用パスワードが一致しません。")
            has_errors = True

        # エラーがあった場合は更新せずに終了
        if has_errors:
            return False

        # すべてのバリデーションに問題がなければパスワードを更新
        user.password = hash_password(self.new_password.data)
        user.is_password_reset_by_user = (
            True  # ユーザーによるパスワードリセットフラグを設定
        )
        user.change_password_at = datetime.utcnow()  # パスワード変更日時を更新
        db.session.commit()
        flash("パスワードが正常に変更されました。", "success")

        return True


user_datastore = SQLAlchemyUserDatastore(db, User, Role)


security = Security(
    app,
    user_datastore,
    login_form=CustomLoginForm,
    change_password_form=CustomChangePasswordForm,
)


def password_condition_gate(f):
    """パスワード更新の条件をチェックするデコレータ"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.is_authenticated and current_user.has_role("user"):
            if datetime.utcnow() - current_user.change_password_at > timedelta(
                seconds=app.config["PASSWORD_EXPIRATION_SECONDS"]
            ):
                return redirect(url_for("security.change_password"))
            if not current_user.is_password_reset_by_user:
                return redirect(url_for("security.change_password"))
        return f(*args, **kwargs)

    return decorated_function


@app.route("/login", methods=["GET", "POST"])
def login():
    """ログインページ"""
    return redirect(url_for("security.login"))


@app.route("/change_password", methods=["GET", "POST"])
@auth_required()
def change_password():
    """パスワード変更ページ"""
    return redirect(url_for("security.change_password"))


@app.route("/role_user", methods=["GET", "POST"])
@roles_required("admin")
def role_user():
    """ユーザーとロールの管理ページ"""
    # 管理者のみがアクセスできるユーザー管理ページ
    users = User.query.all()
    roles = Role.query.all()
    success = None

    if request.method == "POST":
        # ユーザー userのパスワードを初期化する
        user_id = request.form.get("user_id")
        user = User.query.get(user_id)
        if user:
            # パスワードリセット関数を呼び出す
            message = reset_user_password(user_id)
            success = message

            # Ajaxリクエストの場合はHTMLのみを返す
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return f'<div class="alert alert-success">{success}</div>'

    return render_template(
        "role_user.html",
        users=users,
        roles=roles,
        success=success
    )


@security.context_processor
def security_context_processor():
    """セキュリティ関連のコンテキスト変数をテンプレートに注入"""
    if current_user.is_authenticated:
        password_warning = get_password_warning()
    else:
        password_warning = None
    return {
        "users": (
            User.query.all()
            if current_user.is_authenticated and current_user.has_role("admin")
            else None
        ),
        "warning": password_warning,
        "reset_password": (
            reset_user_password
            if current_user.is_authenticated and current_user.has_role("admin")
            else None
        ),
    }


def reset_user_password(user_id):
    """指定されたユーザーのパスワードを初期化する"""
    user = User.query.get(user_id)
    if user:
        # ユーザーの初期パスワードをセット
        initial_password = initial_users.get(user.username, {}).get("pass")
        user.password = hash_password(initial_password)
        user.change_password_at = datetime.utcnow()
        user.is_password_reset_by_user = (
            False  # ユーザーによるパスワードリセットフラグをリセット
        )
        db.session.commit()
        return f"{user.username} のパスワードを初期化しました"
    return "ユーザーが見つかりません"


def get_password_warning():
    """パスワード更新の必要性をチェックし、警告メッセージを返す"""
    if current_user.has_role("user"):
        if not current_user.is_password_reset_by_user:
            return "初期パスワードからの更新が必要です。"
        elif datetime.utcnow() - current_user.change_password_at > timedelta(
            seconds=app.config["PASSWORD_EXPIRATION_SECONDS"]
        ):
            last_change = current_user.change_password_at
            last_change = last_change.strftime('%Y-%m-%d %H:%M:%S')
            expires_in = app.config["PASSWORD_EXPIRATION_SECONDS"]
            message = f"前回のパスワード更新は {last_change} です。パスワードを更新してください。"
            message += f"PoCでは{expires_in}秒で更新"
            return message
    return None


@signals.password_changed.connect_via(app)
# pylint: disable=unused-argument
def password_changed_handler(signal_sender_flask_app, user):
    """パスワード変更時のハンドラー"""
    user.change_password_at = datetime.utcnow()

    # 管理者が他のユーザーのパスワードを変更する場合を検出
    if current_user.has_role("admin") and current_user.id != user.id:
        # 管理者による変更の場合はリセットフラグを変更しない
        pass
    else:
        # ユーザー自身がパスワードを変更した場合
        user.is_password_reset_by_user = True

    db.session.commit()


###################################################
# 開発テスト用
###################################################
# __cov__ディレクトリを作成
cov_dir = os.path.join(app.root_path, "__cov__")
os.makedirs(cov_dir, exist_ok=True)

cov = coverage.Coverage(
    data_file=os.path.join(cov_dir, ".coverage"),
    source=["."],
    omit=[
        "tests/*",
        "./tests/*",
        "*/tests/*",
        "*/venv/*",
        "*/site-packages/*",
        "*/Lib/*",
        "*\\Lib\\*",
        "*\\site-packages\\*",
        "setup.py",
        "conftest.py"
    ]
)


@app.route('/covstart', methods=['POST'])
def start_coverage():
    """ カバレッジ計測を開始するエンドポイント """
    if request.remote_addr != '127.0.0.1':
        abort(403)  # ローカルからのアクセスのみ許可
    cov.start()
    return "Coverage started"


@app.route('/covsave', methods=['POST'])
def save_coverage():
    """ カバレッジ計測を保存するエンドポイント """
    if request.remote_addr != '127.0.0.1':
        abort(403)  # ローカルからのアクセスのみ許可
    cov.stop()
    cov.save()
    return "Coverage saved"


###################################################
# ユーザー用画面
###################################################
# セッションロック後のリダイレクト処理
@app.before_request
def check_login_redirect():
    """ ログイン後のリダイレクト処理 """
    # 認証済みのユーザーで、リダイレクト情報がセッションに保存されている場合
    if current_user.is_authenticated and "redirect_after_login" in session:
        # ログイン関連のページにいる場合、保存されていたページにリダイレクト
        if request.path in ["/", "/home", "/security/login", "/login"]:
            redirect_url = session.pop("redirect_after_login")

            # リダイレクト先が有効な場合はリダイレクト
            if redirect_url:
                return redirect(redirect_url)


@app.route("/")
def index():
    """ アプリケーションのトップページ """
    if current_user.is_authenticated:
        return redirect(url_for("home"))
    return redirect(url_for("security.login"))


@app.route("/home")
@login_required
@password_condition_gate
def home():
    """ ホームページの表示 """
    # Create a sample graph for the home page with multiple data series
    x_data = [
        ["9999-01-01", "9999-01-02", "9999-01-03", "9999-01-04"],
        ["9999-01-01", "9999-01-02", "9999-01-03", "9999-01-04"],
        ["9999-01-01", "9999-01-02", "9999-01-03", "9999-01-04"],
    ]
    y_data = [[10, 15, 13, 17], [12, 18, 14, 19], [20, 25, 23, 27]]
    series_names = ["データA", "データB", "データC"]

    # Create a plotly graph with multiple traces
    traces = []
    for i, x in enumerate(x_data):
        trace = go.Scatter(
            x=x,
            y=y_data[i],
            mode="lines+markers",
            name=series_names[i]
        )
        traces.append(trace)

    layout = go.Layout(
        xaxis=dict(title="日付"),
        yaxis=dict(title="値"),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        margin=dict(l=50, r=50, b=50, t=126, pad=4),
    )
    fig = go.Figure(data=traces, layout=layout)
    fig.update_layout(
        annotations=[
            dict(
                text=(
                    "<b>🧭 操作ガイド（サンプルグラフ）</b><br>"
                    "　📈 <b>表示範囲変更</b><br>"
                    "　　🔍 <b>ズーム　</b>：グラフ内をドラッグして拡大（軸の枠をドラッグで軸方向のみズーム）<br>"
                    "　　➕ <b>移動　　</b>：Shiftキーを押しながらドラッグ（軸の目盛り値部分をドラッグで軸移動）<br>"
                    "　　🔄 <b>リセット</b>：グラフをダブルクリックで元に戻す<br><br>"
                    "　📊 <b>表示データ変更</b><br>"
                    "　　・<b>データ系列表示切り替え</b>：凡例をシングルクリック<br>"
                    "　　・<b>データ系列フォーカス　</b>：凡例をダブルクリック（他のデータを非表示にする）<br>"
                ),
                align="left",
                showarrow=False,
                xref="paper",
                yref="paper",
                x=0,
                y=1.5,
                bordercolor="black",
                borderwidth=1,
                bgcolor="lightyellow",
                opacity=0.9,
            )
        ]
    )
    graph = pyo.plot(fig, output_type="div", include_plotlyjs=False)

    return render_template("home.html", graph=graph)


@app.route("/page")
@login_required
@password_condition_gate
def page():
    """ 画面の表示 """
    form_data = {}
    return render_template("page.html", form_data=form_data)


@app.route("/security_logs")
@login_required
@password_condition_gate
def security_logs():
    """ セキュリティログの表示 """
    # セキュリティログ表示用のフィルタリング
    event_type = request.args.get("event_type", "")
    username = request.args.get("username", "")
    start_date = request.args.get("start_date", "")
    end_date = request.args.get("end_date", "")

    # ベースクエリの作成
    query = SecurityLog.query.order_by(SecurityLog.timestamp.desc())

    # フィルタ条件の適用
    if event_type:
        query = query.filter(SecurityLog.event_type == event_type)

    if username:
        query = query.join(
            SecurityLog.user
        ).filter(
            User.username.like(f"%{username}%")
        )

    if start_date:
        try:
            start_datetime = datetime.strptime(start_date, "%Y-%m-%d")
            query = query.filter(SecurityLog.timestamp >= start_datetime)
        except ValueError:
            pass

    if end_date:
        try:
            end_datetime = datetime.strptime(
                end_date,
                "%Y-%m-%d"
            ) + timedelta(days=1)
            query = query.filter(SecurityLog.timestamp <= end_datetime)
        except ValueError:
            pass

    # ページネーション
    page = request.args.get("page", 1, type=int)
    per_page = 50  # 1ページあたりの表示件数
    logs = query.paginate(page=page, per_page=per_page, error_out=False)

    # イベントタイプの一覧を取得（フィルター用）
    event_types = db.session.query(SecurityLog.event_type).distinct().all()
    event_types = [et[0] for et in event_types]

    return render_template(
        "security_logs.html",
        logs=logs,
        event_types=event_types,
        selected_event_type=event_type,
        username=username,
        start_date=start_date,
        end_date=end_date,
    )


@app.route("/foss_license")
@login_required
@password_condition_gate
def foss_license():
    """ オープンソースライセンス画面
    オープンソースライセンスの情報を表示するための画面です。
    """
    return render_template("foss_license.html")


@app.route("/privacy_policy")
@login_required
@password_condition_gate
def privacy_policy():
    """ プライバシーポリシー画面
    """
    return render_template("privacy_policy.html")


###################################################
# 開発用サンドボックス画面
###################################################
@app.route("/develop")
@login_required
def develop():
    """ 開発用サンドボックス画面
    開発者が自由にコードを試すための画面です。
    """
    return render_template("develop.html")


@app.route("/save_test_input", methods=["POST"])
@login_required
def save_test_input():
    """ テスト入力をセッションに保存するエンドポイント
    フロントエンドからのJSONデータを受け取り、セッションに保存します。
    フロントエンドのJavaScriptと一致させるため、入力内容と保存日時をセッションに保存します。
    """
    data = request.get_json()

    # 入力内容を保存（テンプレートのJavaScriptと一致させる）
    input_value = data.get("input", "")
    session["test_input"] = input_value

    # 保存日時を記録
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    session["test_input_time"] = current_time

    # セッションの変更を確実に保存
    session.modified = True

    # 保存したデータと時刻を返す
    return jsonify(
        {
            "input": input_value,
            "timestamp": current_time,
            "status": "success",
            "message": "テスト入力が保存されました",
        }
    )


###################################################
# アプリケーション起動
###################################################
if __name__ == "__main__":
    # 最初に必要なセットアップを行う
    with app.app_context():
        db.create_all()
        INITED_ROLES = False
        for role_name, role_info in initial_roles.items():
            if not Role.query.filter_by(name=role_name).first():
                user_datastore.create_role(
                    name=role_name, description=role_info["description"]
                )
                INITED_ROLES = True
        if INITED_ROLES:
            db.session.commit()

        INITED_USERS = False
        for user_name, user_info in initial_users.items():
            if not User.query.filter_by(username=user_name).first():
                user_datastore.create_user(
                    email=None,
                    username=user_info["name"],
                    password=hash_password(user_info["pass"]),
                    roles=[user_info["role"]],
                    active=True,
                )
                INITED_USERS = True
        if INITED_USERS:
            db.session.commit()

    # Flask開発サーバー起動前の環境変数を確認
    # デバッグモードでの再読み込みを検出するための環境変数
    is_reload = os.environ.get("WERKZEUG_RUN_MAIN") == "true"

    # リロードの場合はログを記録しない（開発サーバーの再読み込み時のみスキップ）
    if not is_reload:
        with app.app_context():
            log_entry = SecurityLog(
                user_id=None,
                event_type="SYSTEM_START",
                description="アプリケーション起動",
                ip_address=None,
                user_agent=None,
            )
            db.session.add(log_entry)
            db.session.commit()

    # Flaskアプリケーションを起動
    app.run(debug=True, host="0.0.0.0", port=5000)
