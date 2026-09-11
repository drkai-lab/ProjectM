"""DB初期化・シード・Telegram通知."""
import os


import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from . import auth, config
from .models import Base, Keyword, Schedule, Site, User

engine = create_engine(config.DB_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

# 既存 mygov-monitor のデフォルト100サイト
DEFAULT_SITES = [
    "https://www.imi.gov.my/index.php/utama/", "https://johor.imi.gov.my/johor/index.html",
    "https://esd.imi.gov.my/portal/", "https://imigresen-online.imi.gov.my/eservices/main",
    "https://imigresen-online.imi.gov.my/spcom/main", "https://malaysiavisa.imi.gov.my/",
    "https://mtp.imi.gov.my/plsXpats/main", "https://xpatsgateway.com.my/",
    "https://imigresen-online.imi.gov.my/mypass/main", "https://www.imi.gov.my/",
    "https://imigresen-online.imi.gov.my/mdac/main", "https://xpatnova.com.my/irda/",
    "https://www.irda.com.my/", "https://educationmalaysia.gov.my/", "https://www.kln.gov.my/",
    "https://www.motac.gov.my/", "https://www.mida.gov.my/", "https://www.miti.gov.my/",
    "https://www.pmo.gov.my", "https://www.mof.gov.my", "https://ekonomi.gov.my/ms",
    "https://www.mod.gov.my/", "https://www.bheuu.gov.my/en/utama",
    "https://www.kkr.gov.my/ms/laman-utama", "https://www.mot.gov.my/en",
    "https://www.kpkt.gov.my/", "https://jkt.kpkt.gov.my/en/", "https://www.moe.gov.my/",
    "https://www.mohe.gov.my/", "https://www.moh.gov.my/",
    "https://www.kpwkm.gov.my/portal-main/homev2", "https://www.kpdn.gov.my/ms/",
    "https://www.kpkm.gov.my/en/home", "https://www.nres.gov.my/ms-my/Pages/default.aspx",
    "https://www.mcmc.gov.my/en/home", "https://www.mohr.gov.my/", "https://www.mosti.gov.my/",
    "https://www.jbsn.gov.my/", "https://www.rurallink.gov.my/", "https://www.jdn.gov.my/",
    "https://mdec.my/", "https://www.jpa.gov.my/", "https://www.pdp.gov.my/ppdpv1/",
    "https://www.kwsp.gov.my/en/", "https://perkeso.gov.my/", "https://www.hasil.gov.my/",
    "https://hrdcorp.gov.my/", "https://www.bnm.gov.my/", "https://www.sc.com.my/",
    "https://www.ecerdc.com.my/", "https://hq.moh.gov.my/tcm/en/",
    "https://www.bioeconomycorporation.my/", "https://www.caam.gov.my/",
    "https://www.cidb.gov.my/eng/", "https://www.rtm.gov.my/", "https://www.finas.gov.my/en/",
    "https://lam.gov.my/home-en", "https://www.jkm.gov.my/", "https://www.st.gov.my/",
    "https://www.ssm.com.my/Pages/Home.aspx", "https://www.customs.gov.my/ms/pages/utama.aspx",
    "https://mysst.customs.gov.my/", "https://mpkulai.gov.my/", "https://ptj.johor.gov.my/",
    "https://jtksm.mohr.gov.my/ms/laman-utama", "https://www.dosm.gov.my/portal-main/home",
    "https://jpp.mohr.gov.my/", "https://www.talentcorp.com.my/",
    "https://www.doe.gov.my/en/utama-english/", "https://www.sprm.gov.my/",
    "https://fwcms.com.my/", "https://www.dvs.gov.my/", "https://www.doa.gov.my/",
    "https://www.lpp.gov.my/", "https://www.maqis.gov.my/", "https://www.dof.gov.my/",
    "https://www.lkim.gov.my/", "https://www.mada.gov.my/?q=0000", "http://www.kada.gov.my/",
    "https://www.mpib.gov.my/", "https://www.fama.gov.my/utama",
    "https://myehalal.halal.gov.my/portal-halal/v1/index.php",
    "https://www.malaysia.gov.my/portal/index", "https://rai.malaysia.gov.my/main",
    "https://dosh.gov.my/", "https://www.jpj.gov.my/en/home/", "https://www.rmp.gov.my/",
    "https://www.bomba.gov.my/", "https://www.jpn.gov.my/en/", "https://www.nadma.gov.my/bi/",
    "https://www.jpm.gov.my/ms/", "https://www.pidm.gov.my/en",
    "https://smecorp.gov.my/index.php/en/", "https://wildlife.gov.my/index.php",
    "https://www.apad.gov.my/", "https://www.sirim.my/", "https://www.mrm.gov.my/",
    "https://malaysiasteelinstitute.com/", "https://myfuturejobs.gov.my/",
    "https://www.mynext.my/",
]

# 初回セットアップ時のみ投入するシード値。
# 対象単語の本番管理はダッシュボード「サイト」ページのキーワード欄から行う
# (追加・編集・有効/無効・削除が可能。scraper_engine は Keyword.enabled のみ使用)。
DEFAULT_KEYWORDS = ["Permohonan", "Pengumuman", "Ekspatriat", "Terma & Syarat",
                    "Dokumen", "Pas", "Bayaran", "Kriteria", "Undang-Undang", "Majikan"]

# Telegram (秘密値は環境変数のみ。PW_TELEGRAM_TOKEN/PW_TELEGRAM_CHAT_IDを設定)
TELEGRAM_TOKEN = os.getenv("PW_TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("PW_TELEGRAM_CHAT_ID", "")

NOTIFICATION_HEADINGS = {
    "zh": {"hits": "关键词命中", "failures": "获取失败", "updates": "更新"},
    "ja": {"hits": "キーワードヒット", "failures": "取得失敗", "updates": "更新"},
    "en": {"hits": "Keyword Hits", "failures": "Failures", "updates": "Updates"},
    "ms": {"hits": "Padanan Kata Kunci", "failures": "Kegagalan", "updates": "Kemas Kini"},
    "ko": {"hits": "키워드 적중", "failures": "실패", "updates": "업데이트"},
}


def notification_language():
    lang = os.getenv("PW_NOTIFY_LANG", getattr(config, "NOTIFY_LANG", "zh"))
    return lang if lang in NOTIFICATION_HEADINGS else "zh"


def _localize_notification(text: str, lang: str):
    headings = NOTIFICATION_HEADINGS[lang]
    replacements = {
        "关键词命中 / Keyword Hits": headings["hits"],
        "获取失败 / Failures": headings["failures"],
        "Updates / 更新": headings["updates"],
        "更新 / Updates": headings["updates"],
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    return text


def telegram_notify(text: str):
    text = _localize_notification(text, notification_language())
    full = "[ProjectM] MyGov Monitor\n\n" + text
    for i in range(0, len(full), 4000):
        try:
            httpx.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                       data={"chat_id": TELEGRAM_CHAT_ID, "text": full[i:i + 4000]},
                       timeout=20)
        except Exception as e:
            print(f"[telegram] send failed: {e}")


def init_db():
    Base.metadata.create_all(engine)
    db = SessionLocal()
    # root ユーザー(スーパーユーザーより上位。PW_ROOT_EMAIL/PW_ROOT_PASSWORD で設定)
    if config.ROOT_EMAIL:
        ru = db.query(User).filter(User.email == config.ROOT_EMAIL.lower()).first()
        if not ru:
            ru = User(email=config.ROOT_EMAIL.lower(), name="Root",
                      role="root", password_hash=auth.hash_password(config.ROOT_PASSWORD))
            db.add(ru)
        else:
            ru.role = "root"
            if not ru.password_hash and config.ROOT_PASSWORD:
                ru.password_hash = auth.hash_password(config.ROOT_PASSWORD)
    # スーパーユーザー
    su = db.query(User).filter(User.email == config.SUPERUSER_EMAIL.lower()).first()
    if not su:
        su = User(email=config.SUPERUSER_EMAIL.lower(), name="Super Admin",
                  role="admin",
                  password_hash=auth.hash_password(config.SUPERUSER_PASSWORD))
        db.add(su)
    else:
        su.role = "admin"
        if not su.password_hash:
            su.password_hash = auth.hash_password(config.SUPERUSER_PASSWORD)
    # サイト
    if db.query(Site).count() == 0:
        for url in DEFAULT_SITES:
            prof = "safari" if "pmo.gov.my" in url else "chrome"
            db.add(Site(url=url, profile=prof, enabled=True))
    # キーワード
    if db.query(Keyword).count() == 0:
        for term in DEFAULT_KEYWORDS:
            db.add(Keyword(term=term, enabled=True))
    # スケジュール(単一行)
    if db.query(Schedule).count() == 0:
        db.add(Schedule(mode="interval", interval_hours=6,
                        timezone=config.DEFAULT_TZ, enabled=True))
    db.commit()
    db.close()
