"""End-to-End Playwright Tests for Flask Application"""

from time import sleep
import pytest
import requests
from playwright.sync_api import expect


# テスト用の設定
BASE_URL = "http://localhost:5000"


# Skip all Playwright tests if the server is not running
def is_server_running():
    """Check if the Flask server is running at the specified BASE_URL."""
    try:
        response = requests.get(f"{BASE_URL}", timeout=15)
        # Check if the response is successful
        if response.status_code == 200:
            return True
    except requests.ConnectionError:
        return False


# Mark all Playwright tests so they can be run separately
pytestmark = pytest.mark.skipif(
    not is_server_running(),
    reason="Flask server is not running at http://localhost:5000"
)


@pytest.fixture(scope="session")
def browser_context_args():
    """ブラウザの起動オプションを設定"""
    return {
        "viewport": {
            "width": 1280,
            "height": 720,
        },
        "ignore_https_errors": True,
        # Remove timeout parameter as it's causing compatibility issues
    }


@pytest.fixture(autouse=True)
def slow_down_tests():
    """テスト間で少し待機して安定性を高める"""
    yield
    sleep(1)  # 各テスト後に1秒待機


def test_covstart(page):
    """カバレッジの開始をテスト"""
    # カバレッジ開始のためのリクエストを送信
    response = page.request.post(f"{BASE_URL}/covstart")
    # レスポンスのステータスコードを確認
    assert response.status == 200, "カバレッジ開始に失敗しました"


def test_login_page_loads(page):
    """ログインページが正しく表示されることをテスト"""
    # ログインページに移動
    page.goto(f"{BASE_URL}/login")
    # ページタイトルを確認
    expect(page).to_have_title("システム名")
    # ログインフォームの要素が存在することを確認
    expect(page.locator('form[action="/login"]')).to_be_visible()
    expect(page.locator('input[name="username"]')).to_be_visible()
    expect(page.locator('input[name="password"]')).to_be_visible()


def test_login_next_status_monitoring(page):
    """有効な認証情報でログインできることをテスト"""
    page.goto(f"{BASE_URL}/login?next=/page")
    # フォームに入力
    page.fill('input[id="username"]', "admin")
    page.fill('input[id="password"]', "Admin999!")
    # フォームを送信
    page.click('input[type="submit"]')
    # ダッシュボードページにリダイレクトされることを確認
    expect(page).to_have_url(f"{BASE_URL}/page")


def test_admin_walkthrough_pages(page):
    """管理者が各ページにアクセスできることをテスト"""
    page.goto(f"{BASE_URL}/login")
    # フォームに入力
    page.fill('input[id="username"]', "admin")
    page.fill('input[id="password"]', "Admin999!")
    # フォームを送信
    page.click('input[type="submit"]')
    # ダッシュボードページにリダイレクトされることを確認
    expect(page).to_have_url(f"{BASE_URL}/home")
    # 各ページにアクセスして表示を確認
    pages = [
        "/home",
        "/role_user",
        "/security_logs",
        "/foss_license",
        "/privacy_policy",
        "/page",
        "/develop",
        "/change"
    ]
    for page_url in pages:
        page.goto(f"{BASE_URL}{page_url}")
        expect(page).to_have_url(f"{BASE_URL}{page_url}")
        expect(page.locator("body")).to_be_visible()  # ページの内容が表示されていることを確認


def test_login_with_user_credentials(page):
    """有効な認証情報でログインできることをテスト"""
    page.goto(f"{BASE_URL}/login")
    # フォームに入力
    page.fill('input[id="username"]', "user")
    page.fill('input[id="password"]', "User999!")
    # フォームを送信
    page.click('input[type="submit"]')
    # パスワード変更ページにリダイレクトされることを確認
    expect(page).to_have_url(f"{BASE_URL}/change")
    # フォームに入力
    page.fill('input[id="password"]', "User999!")
    page.fill('input[id="new_password"]', "User9999!")
    page.fill('input[id="new_password_confirm"]', "User9999!")
    # フォームを送信
    page.click('button[type="submit"]')
    # ダッシュボードページにリダイレクトされることを確認
    expect(page).to_have_url(f"{BASE_URL}/home")


def test_covsave(page):
    """カバレッジの保存をテスト"""
    # カバレッジ保存のためのリクエストを送信
    response = page.request.post(f"{BASE_URL}/covsave")
    # レスポンスのステータスコードを確認
    assert response.status == 200, "カバレッジ保存に失敗しました"
