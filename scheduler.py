from apscheduler.schedulers.background import BackgroundScheduler
from nav_updater import update_all_navs
from email_report import send_monthly_reports, send_daily_summaries
import pytz

def start_scheduler():
    #print("[TEST] Running NAV update now...")
    #update_all_navs()

    #print("[TEST] Sending daily emails now...")
    #send_daily_summaries()
    scheduler = BackgroundScheduler(timezone="Asia/Kolkata")

    # Daily NAV update at 12:01 AM
    scheduler.add_job(update_all_navs, trigger='cron', hour=0, minute=1)

    # Daily email at 8:00 AM
    scheduler.add_job(send_daily_summaries, trigger='cron', hour=8, minute=0)

    # Monthly email on the 1st at 8:00 AM
    scheduler.add_job(send_monthly_reports, trigger='cron', day='1', hour=8, minute=0)

    scheduler.start()
