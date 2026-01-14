# Python Flask Jinja2 Web Application - 統合開発環境

## 概要

このプロジェクトは、Flask + Jinja2を使用したWeb アプリケーション開発環境です。
最新の開発環境セットアップスクリプトと、包括的なWeb機能を統合しています。

### 主な機能

- **Flask Webアプリケーション**
  - ユーザー認証とロールベースアクセス制御
  - セッション管理（自動ロック・アンロック機能）
  - パスワードポリシーと有効期限管理
  - セキュリティログ機能
  - 多言語対応（日本語・英語）

- **開発環境**
  - Scoopによる自動環境構築
  - Python 3.12仮想環境
  - 包括的なテスト環境（ユニットテスト、Flask Client、E2Eテスト）

---

## 使い方（とても簡単😁）

### 初回セットアップ

1. このフォルダを任意の場所に展開します。
2. `_setup.bat` をダブルクリックします。

**処理概要:**
- [Scoop](https://scoop.sh/)のインストール（未インストールの場合）
- Gitのインストール（Scoop使用）
- GitのSSLバックエンド設定
- Pythonのインストール（Python 3.12、Scoop使用）
- 仮想環境の作成（venv）
- 必要なPythonパッケージのインストール（`requirements.txt`を使用）
- 開発用パッケージのインストール（テスト・リント・フォーマッタなど）

### アプリケーションの起動

3. `_start_app.bat` をダブルクリックします。

**処理概要:**
- 仮想環境のアクティベート
- 必要なパッケージの更新確認
- Flaskアプリケーションの起動
- ブラウザで http://localhost:5000 にアクセス

### テストの実行

4. `_test_app.bat` をダブルクリックします。

**処理概要:**
- ユニットテストの実行
- Flask Clientテストの実行
- E2Eテスト（Playwright）の実行
- カバレッジレポートの生成

### トラブルシューティング

うまく動作しないときは：
1. `_clean.bat` を実行
2. 再度 `_setup.bat` からやり直してください

---

## 動作環境

- Windows 10 以降
- インターネット接続（初回セットアップ時に必要）
- ブラウザ（Chrome、Edge、Firefox等）

---

## 技術スタック

- **Python**: 3.12
- **Webフレームワーク**: Flask
- **テンプレートエンジン**: Jinja2
- **認証**: Flask-Security-Too
- **セッション管理**: Flask-Session
- **データベース**: SQLAlchemy (SQLite)
- **国際化**: Flask-Babel
- **グラフ描画**: Plotly
- **テスト**: pytest, pytest-cov, pytest-playwright
- **コード品質**: black, isort, pylint

---

## 初期ユーザー

### 管理者
- **ユーザー名**: `admin`
- **パスワード**: `Admin999!`

### 一般ユーザー
- **ユーザー名**: `user`
- **パスワード**: `User999!`

※ 初回ログイン後、パスワード変更が必須です

---

## 概要図

### スクリプト関連図

:::mermaid

```mermaid
flowchart LR
    developer[<font size="7">👩‍💻</font><br>開発者]@{ shape: stadium}
    subgraph venv
        cre((<font size="5">➕</font>))
        activate1((<font size="5">▶️</font>))
        subgraph setupvenv [setup on venv]
            installpip[[install pip]]
            installpackages[[pip install -r requirements.txt]]
        end
        deactivate1((<font size="5">⏸️</font>))
        activate2((<font size="5">▶️</font>))
        subgraph startvenv [start on venv]
            python[[python]]
        end
        app.py
        deactivate2((<font size="5">⏸️</font>))
    end
    developer -->|環境構築| _setup.bat
    _setup.bat -->|環境構築| setup_env.ps1
    setup_env.ps1 -->|scoopインストール<br>Pythonインストール| scoop[[scoop]]

    _setup.bat -->|環境構築| setup_venv.ps1
    setup_venv.ps1 -->|Python仮想環境作成| cre

    setup_venv.ps1 -->|仮想環境アクティベート| activate1
    activate1 --> setupvenv
    setup_venv.ps1 -->|pipをインストール| installpip
    setup_venv.ps1 -->|requirements.txtから<br>パッケージインストール| installpackages
    setup_venv.ps1 -->|仮想環境非アクティブ化<br>| deactivate1
    deactivate1 --> setupvenv
    developer -->|コーディング| app.py

    developer -->|スタート| _start.bat
    _start.bat -->|アプリ起動| start_app.ps1
    start_app.ps1 -->|仮想環境アクティベート<br>| activate2
    activate2 --> startvenv
    start_app.ps1 -->|アプリ起動| python
    python --> app.py
    start_app.ps1 -->|仮想環境非アクティブ化<br>| deactivate2
    deactivate2 --> startvenv
```

:::

### スクリプト動作シーケンス図

:::mermaid

```mermaid
 sequenceDiagram

    actor Developer as 開発者<br>👩‍💻
    participant BAT as .bat
    participant SP as .ps1
    participant V as venv
    participant APP as app.py
    participant SC as scoop

    Developer->>BAT: _setup.bat<br>ダブルクリック
    activate BAT
    BAT->>SP: setup_env.ps1<br>環境構築
    activate SP
    SP->>SC: scoop インストール<br>Python インストール
    activate SC
    SP -->>BAT: 完了
    deactivate SP

    BAT->>SP: setup_venv.ps1<br>仮想環境構築
    activate SP
    SP->>V: 仮想環境作成
    activate V
    SP->>V: activate.bat
    activate V
    SP->>V: pipインストール
    SP->>V: パッケージインストール
    SP-XV: deactivate.bat
    deactivate V
    SP -->>BAT: 完了
    deactivate SP
    BAT -->>Developer: 完了
    deactivate BAT

    Developer->>APP: コーディング

    Developer->>BAT: _start.bat<br>ダブルクリック
    activate BAT
    BAT->>SP: start_app.ps1<br>ツールスタート
    activate SP
    SP->>V: activate.bat
    activate V
    SP->>V: アプリ起動
    V->>APP: アプリ起動
    activate APP
    deactivate APP
    destroy APP
    APP-->>V: 完了

    SP-XV: deactivate.bat
    deactivate V
    SP-->>BAT: 完了
    deactivate SP
    BAT-->>Developer: 完了
    deactivate BAT

    deactivate V
    deactivate SC
```
:::

---
