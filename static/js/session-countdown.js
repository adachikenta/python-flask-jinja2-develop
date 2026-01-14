/**
 * セッションタイムアウトカウントダウン機能
 * 無操作時にカウントダウンを表示し、セッションロックを行う
 */

// セッション設定（デフォルト値。実際の値はサーバーから取得）
let SESSION_TIMEOUT = 1800; // 30分（デフォルト値）
let WARNING_THRESHOLD = 180; // 3分前から警告を表示

// 状態管理変数
let remainingSeconds = SESSION_TIMEOUT; // サーバーから取得した残り時間
let activityCheckTimer;
let sidebarCountdownTimer;
let statusSyncTimer;

// カウントダウン表示用要素
let sidebarCountdownElement;

// 翻訳データ
let translations = {
    'session_remaining_time': 'セッション有効時間', // デフォルト日本語
    'lock_now': '今すぐロック🔒',
    'change_password': 'パスワード変更',
    'logout': 'ログアウト'
};

// UI要素への参照を保持
let lockButton, changePasswordButton, logoutButton;

// DOM読み込み後に初期化
document.addEventListener('DOMContentLoaded', function() {    
    // HTML要素のlang属性から現在のページ言語を取得
    const pageLang = document.documentElement.lang || 'ja';
    
    // ページURLのクエリパラメータを確認（言語切り替え検出用）
    const urlParams = new URLSearchParams(window.location.search);
    const fromLanguageSwitch = urlParams.has('lang_switched');
    
    // 初期表示時は現在のページ言語に合わせた翻訳を事前に設定
    if (pageLang === 'en') {
        translations = {
            'session_remaining_time': 'Session Time Remaining',
            'lock_now': 'Lock Now 🔒',
            'change_password': 'Change Password',
            'logout': 'Logout'
        };
    } else {
        // デフォルトは日本語
        translations = {
            'session_remaining_time': 'セッション有効時間',
            'lock_now': '今すぐロック🔒',
            'change_password': 'パスワード変更', 
            'logout': 'ログアウト'
        };
    }
    
    // 翻訳データを取得し、取得完了後に残りの初期化を行う
    fetchTranslations().then(() => {
        // サーバーからセッション設定を取得
        return fetchSessionConfig();
    }).then(() => {
        createSidebarCountdown();
        updateUITexts(); // 翻訳データでUIを更新
        startSessionSync();
        startSidebarCountdown();
        
        // 言語切り替え検出と自動更新を設定
        setupLanguageChangeDetection();
    }).catch(error => {
        // エラー時もUIは表示する
        createSidebarCountdown();
        updateUITexts(); // エラー時も現在の翻訳でUIを更新
        startSessionSync();
        startSidebarCountdown();
        
        // エラーがあってもUIの自動更新は設定
        setupLanguageChangeDetection();
    });
});

// 翻訳データを取得する
async function fetchTranslations() {
    try {
        
        // 現在の言語を取得
        const getCurrentLanguage = () => {
            const languageSelector = document.getElementById('language');
            if (languageSelector) {
                return languageSelector.value; // 'ja' または 'en'
            }
            // セレクタが見つからない場合はHTMLのlang属性を確認
            const htmlLang = document.documentElement.lang;
            if (htmlLang) {
                return htmlLang;
            }
            // デフォルトは日本語
            return 'ja';
        };
        
        const currentLang = getCurrentLanguage();
        
        // 言語情報をクエリパラメータとして付加
        const url = `/api/translations/session?lang=${currentLang}`;
        const response = await fetch(url);
        
        if (response.ok) {
            const data = await response.json();
            
            // 現在の言語を判定する補助（デバッグ用）
            let detectedLanguage = 'unknown';
            if (data.session_remaining_time === 'Session Time Remaining') {
                detectedLanguage = 'en';
            } else if (data.session_remaining_time === 'セッション有効時間') {
                detectedLanguage = 'ja';
            }
            
            // データが存在する場合のみ上書き
            let updated = false;
            for (const key in data) {
                if (data[key] && data[key] !== '') {
                    translations[key] = data[key];
                    updated = true;
                }
            }
            
            if (!updated) {
            }
            
            // 既にUIが構築されている場合は更新
            if (sidebarCountdownElement) {
                updateUITexts();
            }
            
            return translations;
        } else {
            throw new Error(`翻訳取得エラー: ${response.status}`);
        }
    } catch (error) {
        throw error;
    }
}

// UI要素のテキストを現在の翻訳データで更新
function updateUITexts() {
    try {
        // カウントダウン表示を更新
        if (sidebarCountdownElement) {
            sidebarCountdownElement.textContent = `${translations.session_remaining_time}: ${formatTime(remainingSeconds)}`;
        } else {
        }
        
        // ボタンテキストを更新
        if (lockButton) {
            lockButton.textContent = translations.lock_now;
        } else {
        }
        
        if (changePasswordButton) {
            changePasswordButton.textContent = translations.change_password;
        }
        
        if (logoutButton) {
            logoutButton.textContent = translations.logout;
        }
    } catch (error) {
        console.error('UI更新エラー:', error);
    }
    
}

// サーバーからセッション設定を取得
async function fetchSessionConfig() {
    try {
        const response = await fetch('/api/session/config');
        if (response.ok) {
            const config = await response.json();
            SESSION_TIMEOUT = config.timeout_seconds;
            WARNING_THRESHOLD = config.warning_threshold;
        } else {
            console.error('セッション設定の取得に失敗しました');
        }
    } catch (error) {
        console.error('セッション設定の取得でエラー発生:', error);
    }
}

// サーバーとの定期的な同期（残り時間の取得とステータスチェック）
function startSessionSync() {
    interval = 120000; // 120秒ごとに同期
    if (remainingSeconds <= WARNING_THRESHOLD) {
        interval = 10000; // 警告表示中は1秒ごとに更新
    }
    statusSyncTimer = setInterval(() => {
        syncWithServer();
    }, interval);

    // 初回は即時実行
    syncWithServer();
}

// サーバーと同期してセッション情報を更新
async function syncWithServer() {
    try {
        const response = await fetch('/api/session/status');
        
        if (!response.ok) {
            throw new Error(`HTTP error: ${response.status}`);
        }
        
        const data = await response.json();
        
        if (data.is_locked) {
            // セッションがロックされていたらログイン画面へ
            window.location.href = '/login';
            return;
        }
        
        // サーバーから取得した残り時間で更新
        remainingSeconds = data.remaining_seconds;
        
        // 残り時間が0以下ならロック
        if (remainingSeconds <= 0) {
            lockSession();
        }
        
        // サイドバーのカウントダウン表示を更新
        updateSidebarCountdown();
    } catch (error) {
        console.error('サーバー同期エラー:', error);
    }
}

// アニメーションスタイルを追加（サイドバーカウントダウンでも使用する）
function addAnimationStyles() {
    const style = document.createElement('style');
    style.textContent = `
        @keyframes pulse {
            0% { transform: scale(1); }
            50% { transform: scale(1.08); }
            100% { transform: scale(1); }
        }
        
        .countdown-pulse {
            animation: pulse 1s infinite;
        }
    `;
    document.head.appendChild(style);
}

// トップバーのカウントダウン表示を更新
function updateSidebarCountdown() {
    if (sidebarCountdownElement) {
        if (remainingSeconds <= 0) {
            sidebarCountdownElement.textContent = `${translations.session_remaining_time}: ${formatTime(0)}`;
        } else {
            sidebarCountdownElement.textContent = `${translations.session_remaining_time}: ${formatTime(remainingSeconds)}`;
        }
        
        // 警告表示の閾値以下になったら警告スタイルを適用
        if (remainingSeconds <= WARNING_THRESHOLD) {
            sidebarCountdownElement.classList.add('warning');
        } else {
            sidebarCountdownElement.classList.remove('warning');
        }
    }
}

// セッションロックを実行
function lockSession() {
    window.location.href = '/lock_session';
}

// 今すぐロックボタン用の関数
function lockSessionNow() {
    window.location.href = '/lock_session';
}

// トップバーにカウントダウン表示を作成
function createSidebarCountdown() {
    // トップバー要素を取得
    const topbar = document.querySelector('.topbar');
    if (!topbar) return;
    
    // トップバーの既存要素を取得
    sidebarCountdownElement = document.getElementById('topbar-countdown');
    lockButton = document.getElementById('topbar-lock-button');
    changePasswordButton = document.querySelector('a[href="/change_password"]');
    logoutButton = document.querySelector('a[href="/logout"]');
    
    if (!sidebarCountdownElement) {
        console.warn('トップバーのカウントダウン要素が見つかりません');
        return;
    }
    
    // 初期表示を設定
    sidebarCountdownElement.textContent = `${translations.session_remaining_time}: ${formatTime(remainingSeconds)}`;
    
    // ロックボタンのテキストを更新
    if (lockButton) {
        lockButton.textContent = translations.lock_now;
    }
}

// トップバーのカウントダウンを開始
function startSidebarCountdown() {
    // 1秒ごとにカウントダウンを更新（ローカルカウントダウン）
    sidebarCountdownTimer = setInterval(() => {
        // 残り時間を1秒減らす（サーバーとの同期までのつなぎ）
        if (remainingSeconds > 0) {
            remainingSeconds--;
        }
        
        // サイドバーの表示を更新
        updateSidebarCountdown();
        
        // 残り時間が0になった場合はロック
        if (remainingSeconds <= 0) {
            lockSession();
        }
    }, 1000);
}

// 時間のフォーマット（MM:SS形式）
function formatTime(seconds) {
    // 小数点以下を切り捨てて整数に変換
    const totalSeconds = Math.floor(seconds);
    const minutes = Math.floor(totalSeconds / 60);
    const secs = totalSeconds % 60;
    return `${String(minutes).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
}

// 言語変更を検出して翻訳を更新
function setupLanguageChangeDetection() {
    // ページロード時に現在選択されている言語を取得
    const getCurrentLanguage = () => {
        const languageSelector = document.getElementById('language');
        if (languageSelector) {
            return languageSelector.value; // 'ja' または 'en'
        }
        // セレクタが見つからない場合はHTMLのlang属性を確認
        const htmlLang = document.documentElement.lang;
        if (htmlLang) {
            return htmlLang;
        }
        // デフォルトは日本語
        return 'ja';
    };
    
    // 現在の言語を取得
    const currentLang = getCurrentLanguage();
    // 言語セレクタの変更を監視
    const languageSelector = document.getElementById('language');
    if (languageSelector) {
        
        // 現在選択されている言語に合わせて翻訳を更新
        if (languageSelector.value) {
            // 初期値からの変更を検出した場合はすぐに翻訳を更新
            fetchTranslations().then(() => {
                updateUITexts();
            });
        }
        
        // 言語セレクタの変更イベントを監視
        languageSelector.addEventListener('change', function() {
            // 言語変更後、ページがリロードされるので少し待ってから翻訳を取得し直す
            setTimeout(() => {
                fetchTranslations().then(() => {
                    updateUITexts();
                });
            }, 5000); // 5秒後（ページリロード完了後）
        });
    }
}

// DOM読み込み後に初期化（既存のコードに追加）
document.addEventListener('DOMContentLoaded', function() {
    // 既存の処理に加えて言語変更検出を設定
    setupLanguageChangeDetection();
});
