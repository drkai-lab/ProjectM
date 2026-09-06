"""ProjectW の軽量な多言語基盤（外部依存なし）。"""
from __future__ import annotations

from typing import Any, Mapping

SUPPORTED_LANGUAGES = ("ja", "en", "zh", "ms", "id", "ko")
DEFAULT_LANGUAGE = "ja"
COOKIE_NAME = "pw_lang"

TRANSLATIONS: dict[str, dict[str, str]] = {
    "ja": {
        "app_name": "ProjectW", "home": "ホーム", "sites": "サイト", "settings": "設定", "logout": "ログアウト", "login": "ログイン", "magic_link": "マジックリンク", "password_login": "パスワードでログイン", "email": "メールアドレス", "password": "パスワード", "send": "送信", "dashboard": "ダッシュボード", "scan_now": "今すぐスキャン", "schedule": "スケジュール", "users": "ユーザー", "keywords": "キーワード", "enabled": "有効", "add": "追加", "delete": "削除", "save": "保存", "frozen": "凍結", "unfreeze": "凍結解除", "next_scan": "次回スキャン", "site_count": "サイト数", "no_history": "履歴はありません", "login_subtitle": "サイト監視ダッシュボードにログイン", "send_magic_link": "マジックリンクを送信", "login_with_password": "パスワードでログイン", "scan_started": "スキャンを開始しました", "hit": "ヒット", "fail": "失敗", "latest_scan_result": "最新スキャン結果", "scan_history": "スキャン履歴", "no_scan_history": "まだ実行履歴がありません", "scanning_now": "実行中…", "scan_now_btn": "今すぐスキャン実行", "language": "言語", "auto_language": "自動", "login_required": "ログインが必要です", "link_sent": "ログインリンクを送信しました", "invalid_credentials": "メールまたはパスワードが違います", "account_frozen": "アカウントが凍結されています", "admin": "管理者", "editor": "編集者", "viewer": "閲覧者", "search": "検索", "updated": "更新しました", "failures": "失敗", "hits": "ヒット",
    },
    "en": {
        "app_name": "ProjectW", "home": "Home", "sites": "Sites", "settings": "Settings", "logout": "Log out", "login": "Log in", "magic_link": "Magic link", "password_login": "Password login", "email": "Email", "password": "Password", "send": "Send", "dashboard": "Dashboard", "scan_now": "Scan now", "schedule": "Schedule", "users": "Users", "keywords": "Keywords", "enabled": "Enabled", "add": "Add", "delete": "Delete", "save": "Save", "frozen": "Frozen", "unfreeze": "Unfreeze", "next_scan": "Next scan", "site_count": "Site count", "no_history": "No history", "login_subtitle": "Log in to the monitoring dashboard", "send_magic_link": "Send magic link", "login_with_password": "Password login", "scan_started": "Scan started", "hit": "Hit", "fail": "Fail", "latest_scan_result": "Latest scan result", "scan_history": "Scan history", "no_scan_history": "No scan history yet", "scanning_now": "Running…", "scan_now_btn": "Scan now", "language": "Language", "auto_language": "Automatic", "login_required": "Login required", "link_sent": "Login link sent", "invalid_credentials": "Invalid email or password", "account_frozen": "Account is frozen", "admin": "Admin", "editor": "Editor", "viewer": "Viewer", "search": "Search", "updated": "Updated", "failures": "Failures", "hits": "Hits",
    },
    "zh": {
        "app_name": "ProjectW", "home": "首页", "sites": "网站", "settings": "设置", "logout": "退出登录", "login": "登录", "magic_link": "魔法链接", "password_login": "密码登录", "email": "电子邮件", "password": "密码", "send": "发送", "dashboard": "仪表板", "scan_now": "立即扫描", "schedule": "计划", "users": "用户", "keywords": "关键词", "enabled": "已启用", "add": "添加", "delete": "删除", "save": "保存", "frozen": "已冻结", "unfreeze": "解除冻结", "next_scan": "下次扫描", "site_count": "网站数量", "no_history": "没有历史记录", "language": "语言", "auto_language": "自动", "login_required": "需要登录", "link_sent": "登录链接已发送", "invalid_credentials": "邮箱或密码错误", "account_frozen": "账户已冻结", "admin": "管理员", "editor": "编辑者", "viewer": "查看者", "search": "搜索", "updated": "已更新", "failures": "失败", "hits": "命中", "login_subtitle": "登录网站监控仪表板", "send_magic_link": "发送魔法链接", "login_with_password": "密码登录", "scan_started": "扫描已开始", "hit": "命中", "fail": "失败", "latest_scan_result": "最新扫描结果", "scan_history": "扫描历史", "no_scan_history": "暂无扫描历史", "scanning_now": "执行中…", "scan_now_btn": "立即扫描"
    },
    "ms": {
        "app_name": "ProjectW", "home": "Laman utama", "sites": "Tapak", "settings": "Tetapan", "logout": "Log keluar", "login": "Log masuk", "magic_link": "Pautan ajaib", "password_login": "Log masuk kata laluan", "email": "E-mel", "password": "Kata laluan", "send": "Hantar", "dashboard": "Papan pemuka", "scan_now": "Imbas sekarang", "schedule": "Jadual", "users": "Pengguna", "keywords": "Kata kunci", "enabled": "Didayakan", "add": "Tambah", "delete": "Padam", "save": "Simpan", "frozen": "Dibekukan", "unfreeze": "Nyahbeku", "next_scan": "Imbasan seterusnya", "site_count": "Bilangan tapak", "no_history": "Tiada sejarah", "language": "Bahasa", "auto_language": "Automatik", "login_required": "Log masuk diperlukan", "link_sent": "Pautan log masuk dihantar", "invalid_credentials": "E-mel atau kata laluan tidak sah", "account_frozen": "Akaun dibekukan", "admin": "Pentadbir", "editor": "Penyunting", "viewer": "Penonton", "search": "Cari", "updated": "Dikemas kini", "failures": "Kegagalan", "hits": "Padanan", "login_subtitle": "Log masuk ke papan pemuka pemantauan", "send_magic_link": "Hantar pautan ajaib", "login_with_password": "Log masuk kata laluan", "scan_started": "Imbasan dimulakan", "hit": "Padanan", "fail": "Gagal", "latest_scan_result": "Keputusan imbasan terkini", "scan_history": "Sejarah imbasan", "no_scan_history": "Tiada sejarah imbasan lagi", "scanning_now": "Berjalan…", "scan_now_btn": "Imbas sekarang"
    },

    "id": {"app_name": "ProjectW", "home": "Beranda", "sites": "Situs", "settings": "Pengaturan", "logout": "Keluar", "login": "Masuk", "magic_link": "Tautan Ajaib", "password_login": "Login Kata Sandi", "email": "Email", "password": "Kata Sandi", "send": "Kirim", "dashboard": "Dasbor", "scan_now": "Pindai Sekarang", "schedule": "Jadwal", "users": "Pengguna", "keywords": "Kata Kunci", "enabled": "Diaktifkan", "add": "Tambah", "delete": "Hapus", "save": "Simpan", "frozen": "Dibekukan", "unfreeze": "Tcair", "next_scan": "Pemindaian Berikutnya", "site_count": "Jumlah Situs", "no_history": "Tidak ada riwayat", "language": "Bahasa", "auto_language": "Otomatis", "login_required": "Login diperlukan", "link_sent": "Tautan login terkirim", "invalid_credentials": "Email atau kata sandi salah", "account_frozen": "Akun dibekukan", "admin": "Admin", "editor": "Editor", "viewer": "Pemirsa", "search": "Cari", "updated": "Diperbarui", "failures": "Gagal", "hits": "Tembusan", "login_subtitle": "Masuk ke dasbor pemantauan", "send_magic_link": "Kirim tautan ajaib", "login_with_password": "Login dengan kata sandi", "scan_started": "Pemindaian dimulakan", "hit": "Tembusan", "fail": "Gagal", "latest_scan_result": "Hasil pemindaian terbaru", "scan_history": "Riwayat pemindaian", "no_scan_history": "Belum ada riwayat pemindaian", "scanning_now": "Berjalan…", "scan_now_btn": "Pindai sekarang"},
    "ko": {
        "app_name": "ProjectW", "home": "홈", "sites": "사이트", "settings": "설정", "logout": "로그아웃", "login": "로그인", "magic_link": "매직 링크", "password_login": "비밀번호 로그인", "email": "이메일", "password": "비밀번호", "send": "보내기", "dashboard": "대시보드", "scan_now": "지금 스캔", "schedule": "일정", "users": "사용자", "keywords": "키워드", "enabled": "활성화됨", "add": "추가", "delete": "삭제", "save": "저장", "frozen": "동결됨", "unfreeze": "동결 해제", "next_scan": "다음 스캔", "site_count": "사이트 수", "no_history": "기록이 없습니다", "language": "언어", "auto_language": "자동", "login_required": "로그인이 필요합니다", "link_sent": "로그인 링크를 보냈습니다", "invalid_credentials": "이메일 또는 비밀번호가 올바르지 않습니다", "account_frozen": "계정이 동결되었습니다", "admin": "관리자", "editor": "편집자", "viewer": "조회자", "search": "검색", "updated": "업데이트됨", "failures": "실패", "hits": "적중", "login_subtitle": "모니터링 대시보드에 로그인", "send_magic_link": "매직 링크 전송", "login_with_password": "비밀번호 로그인", "scan_started": "스캔 시작됨", "hit": "히트", "fail": "실패", "latest_scan_result": "최신 스캔 결과", "scan_history": "스캔 기록", "no_scan_history": "아직 스캔 기록이 없습니다", "scanning_now": "실행 중…", "scan_now_btn": "지금 스캔"
    },
}


def detect_language(header: str | None) -> str:
    """Accept-Language を品質(q値)順に解析し、対応言語または ja を返す。"""
    if not header:
        return DEFAULT_LANGUAGE
    choices: list[tuple[float, int, str]] = []
    for order, item in enumerate(header.split(",")):
        parts = item.strip().split(";")
        tag = parts[0].strip().lower()
        if not tag or tag == "*":
            continue
        try:
            q = next((float(p.strip()[2:]) for p in parts[1:] if p.strip().startswith("q=")), 1.0)
        except ValueError:
            q = 0.0
        base = tag.split("-")[0]
        if base in SUPPORTED_LANGUAGES and q > 0:
            choices.append((q, -order, base))
    return max(choices)[2] if choices else DEFAULT_LANGUAGE


def get_language(request: Any) -> str:
    """pw_lang cookie を優先し、未指定・不正時は Accept-Language を使う。"""
    cookie = request.cookies.get(COOKIE_NAME)
    if cookie in SUPPORTED_LANGUAGES:
        return cookie
    return detect_language(request.headers.get("accept-language"))


def template_context(request: Any, context: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """テンプレート用に翻訳辞書 t と選択言語 lang を追加する。"""
    lang = get_language(request)
    values = dict(context or {})
    values.update({"t": _TranslationDict(TRANSLATIONS[lang]), "lang": lang})
    return values


class _TranslationDict(dict):
    """Missing translation keys remain visible instead of becoming empty."""
    def __missing__(self, key):
        return key


# 呼び出し側で t.get("unknown", key) としたい場合にも利用可能。
translations = TRANSLATIONS
