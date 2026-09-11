"""SQLAlchemy モデル定義."""
import datetime as dt

from sqlalchemy import (Boolean, Column, DateTime, ForeignKey, Integer, String,
                        Table, Text, UniqueConstraint)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


def utcnow():
    return dt.datetime.now(dt.timezone.utc)


# ユーザーグループのメンバーシップ(多対多)。User クラスより先に定義する。
group_members = Table(
    "group_members", Base.metadata,
    Column("group_id", Integer, ForeignKey("user_groups.id"), primary_key=True),
    Column("user_id", Integer, ForeignKey("users.id"), primary_key=True),
)


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(120), default="")
    role = Column(String(20), default="viewer")   # root / admin / editor / viewer
    password_hash = Column(String(255), default="")  # 管理者系のみ設定
    is_frozen = Column(Boolean, default=False)
    created_at = Column(DateTime, default=utcnow)
    last_login = Column(DateTime, nullable=True)
    groups = relationship("UserGroup", secondary=group_members,
                          back_populates="members")


class UserGroup(Base):
    """ユーザーのグループ。root はスーパーユーザー(admin)も、
    root/admin は一般ユーザーをグループ化できる."""
    __tablename__ = "user_groups"
    id = Column(Integer, primary_key=True)
    name = Column(String(120), unique=True, nullable=False)
    description = Column(String(300), default="")
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=utcnow)
    members = relationship("User", secondary=group_members,
                           back_populates="groups")


class Site(Base):
    __tablename__ = "sites"
    id = Column(Integer, primary_key=True)
    url = Column(String(500), unique=True, nullable=False)
    label = Column(String(200), default="")
    profile = Column(String(30), default="chrome")   # curl_cffi impersonate
    enabled = Column(Boolean, default=True)
    last_status = Column(Integer, nullable=True)
    last_hash = Column(String(32), default="")
    last_checked = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow)


class Keyword(Base):
    __tablename__ = "keywords"
    id = Column(Integer, primary_key=True)
    term = Column(String(200), nullable=False)
    label = Column(String(200), default="")
    enabled = Column(Boolean, default=True)
    __table_args__ = (UniqueConstraint("term", name="uq_keyword_term"),)


class Schedule(Base):
    """単一行のスケジュール設定."""
    __tablename__ = "schedule"
    id = Column(Integer, primary_key=True)
    mode = Column(String(20), default="interval")   # interval / daily / cron
    interval_hours = Column(Integer, default=6)      # interval モード
    daily_times = Column(String(200), default="")    # daily: "07:00,19:00"
    cron_expr = Column(String(120), default="")      # cron モード
    max_runs_per_day = Column(Integer, default=0)    # 0 = 無制限
    timezone = Column(String(60), default="Asia/Kuala_Lumpur")
    enabled = Column(Boolean, default=True)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)


class Run(Base):
    __tablename__ = "runs"
    id = Column(Integer, primary_key=True)
    started_at = Column(DateTime, default=utcnow)
    finished_at = Column(DateTime, nullable=True)
    trigger = Column(String(20), default="manual")   # manual / scheduled
    total = Column(Integer, default=0)
    ok = Column(Integer, default=0)
    updated = Column(Integer, default=0)
    hits = Column(Integer, default=0)
    failed = Column(Integer, default=0)
    status = Column(String(20), default="running")   # running / done / error
    hit_records = relationship("Hit", back_populates="run",
                               cascade="all, delete-orphan")


class Hit(Base):
    __tablename__ = "hits"
    id = Column(Integer, primary_key=True)
    run_id = Column(Integer, ForeignKey("runs.id"))
    url = Column(String(500))
    matched = Column(String(500))     # ヒットしたキーワード(カンマ区切り)
    snippet = Column(Text, default="")
    created_at = Column(DateTime, default=utcnow)
    run = relationship("Run", back_populates="hit_records")


class MagicToken(Base):
    """使い捨てマジックリンクトークンのワンタイム保証(jti)."""
    __tablename__ = "magic_tokens"
    id = Column(Integer, primary_key=True)
    jti = Column(String(64), unique=True, index=True)
    email = Column(String(255))
    used = Column(Boolean, default=False)
    created_at = Column(DateTime, default=utcnow)


class Session(Base):
    __tablename__ = "sessions"
    id = Column(Integer, primary_key=True)
    token = Column(String(64), unique=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=utcnow)
    expires_at = Column(DateTime)
