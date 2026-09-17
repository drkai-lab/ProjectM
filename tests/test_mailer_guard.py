"""テスト実行時に外部へ実送信しないことと、配送不能な宛先を拒否することを固定する。

2026-09-18 の事故(本番 .env があるディレクトリで pytest を実行し、テストが作る
r1@t.local 宛に実際の招待メールが送られてバウンスした)の再発防止テスト。
"""
from app import config
from app import mailer


def test_test_run_has_no_live_mail_or_telegram_credentials():
    """本番 .env があっても、テストではリレー/Resend/Telegram の資格情報が空。"""
    assert config.MAIL_RELAY_URL == ""
    assert config.MAIL_RELAY_KEY == ""
    assert config.RESEND_API_KEY == ""
    assert config.TELEGRAM_TOKEN == ""


def test_undeliverable_addresses_are_rejected_before_sending():
    """.local 等の予約ドメインと書式不正は送信前に拒否する(バウンスを作らない)。"""
    assert mailer._deliverable("user@example.com") is True
    assert mailer._deliverable("user@vorlors.com") is True
    for addr in ("r1@t.local", "x@example.test", "y@invalid", "z@localhost",
                 "w@sub.localhost", "no-at-mark", "@no-local-part"):
        assert mailer._deliverable(addr) is False, addr
        ok, detail = mailer.send_mail(addr, "件名", "本文")
        assert ok is False, addr
        assert detail.startswith("invalid-recipient"), (addr, detail)


def test_deliverable_address_falls_back_to_console_in_tests():
    """通常の宛先はガードを通り、テストではコンソール出力に落ちる(実送信しない)。"""
    ok, detail = mailer.send_mail("user@example.com", "件名", "本文", "<p>本文</p>")
    assert (ok, detail) == (True, "console")
