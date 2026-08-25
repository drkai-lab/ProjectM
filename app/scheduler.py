"""APScheduler ラッパー. DB の Schedule 設定に従い run_scan を実行。GUIから再構成可能。"""
import datetime as dt

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from . import db as dbmod
from .models import Run, Schedule
from .scraper_engine import run_scan

_sched = BackgroundScheduler(timezone="UTC")
_JOB_ID = "mygov_scan"


def _runs_today(SessionLocal, tz) -> int:
    s = SessionLocal()
    try:
        now = dt.datetime.now(dt.timezone.utc)
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return s.query(Run).filter(Run.started_at >= start,
                                   Run.trigger == "scheduled").count()
    finally:
        s.close()


def _scheduled_job():
    s = dbmod.SessionLocal()
    try:
        cfg = s.query(Schedule).first()
        if not cfg or not cfg.enabled:
            return
        if cfg.max_runs_per_day and _runs_today(dbmod.SessionLocal, cfg.timezone) >= cfg.max_runs_per_day:
            return
    finally:
        s.close()
    run_scan(dbmod.SessionLocal, trigger="scheduled", notify=dbmod.telegram_notify)


def reconfigure():
    """DB の Schedule に合わせてジョブを再登録."""
    s = dbmod.SessionLocal()
    cfg = s.query(Schedule).first()
    s.close()
    try:
        _sched.remove_job(_JOB_ID)
    except Exception:
        pass
    if not cfg or not cfg.enabled:
        return
    tz = cfg.timezone or "Asia/Kuala_Lumpur"
    if cfg.mode == "interval":
        trig = IntervalTrigger(hours=max(1, cfg.interval_hours), timezone=tz)
    elif cfg.mode == "daily" and cfg.daily_times.strip():
        times = [t.strip() for t in cfg.daily_times.split(",") if t.strip()]
        hours = ",".join(t.split(":")[0] for t in times)
        minutes = ",".join(t.split(":")[1] for t in times if ":" in t) or "0"
        trig = CronTrigger(hour=hours, minute=minutes, timezone=tz)
    elif cfg.mode == "cron" and cfg.cron_expr.strip():
        trig = CronTrigger.from_crontab(cfg.cron_expr, timezone=tz)
    else:
        trig = IntervalTrigger(hours=6, timezone=tz)
    _sched.add_job(_scheduled_job, trig, id=_JOB_ID, replace_existing=True,
                   misfire_grace_time=3600, coalesce=True)


def next_run_time():
    job = _sched.get_job(_JOB_ID)
    return job.next_run_time.isoformat() if job and job.next_run_time else None


def start():
    if not _sched.running:
        _sched.start()
    reconfigure()
