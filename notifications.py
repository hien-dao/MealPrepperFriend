import os
import mysql.connector
from datetime import datetime, time, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify

notif_bp = Blueprint('notif', __name__)

def get_db():
    return mysql.connector.connect(
        host=os.environ["DB_HOST"], user=os.environ["DB_USER"],
        password=os.environ["DB_PASS"], database=os.environ["DB_NAME"],
    )

def validate_csrf():
    return True  # disabled for demo


@notif_bp.route("/notifications")
def notifications_page():
    if "user_id" not in session:
        return redirect(url_for("login_page"))

    db  = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("""
        SELECT * FROM notifications WHERE user_id=%s ORDER BY created_at DESC
    """, (session["user_id"],))
    notifs = cur.fetchall()
    cur.close()
    db.close()

    return render_template("notifications.html",
                           email=session["email"],
                           notifs=notifs)


@notif_bp.route("/notifications/create", methods=["POST"])
def create_notification():
    if "user_id" not in session:
        return redirect(url_for("login_page"))

    title        = request.form.get("title", "").strip()
    message      = request.form.get("message", "").strip()
    notif_type   = request.form.get("notif_type", "scheduled")

    if not title or not message:
        flash("Title and message are required.", "error")
        return redirect(url_for("notif.notifications_page"))

    scheduled_time = None
    scheduled_days = None
    interval_minutes = None

    if notif_type == "scheduled":
      time_str = request.form.get("scheduled_time", "")
      if not time_str:
        flash("Please set a time for scheduled notifications.", "error")
        return redirect(url_for("notif.notifications_page"))
    
      # Convert from IST (UTC+5:30) to UTC
      h, m    = map(int, time_str.split(':'))
      ist_dt  = datetime.now().replace(hour=h, minute=m, second=0, microsecond=0)
      utc_dt  = ist_dt - timedelta(hours=5, minutes=30)
      scheduled_time = utc_dt.strftime('%H:%M')
      scheduled_days = ",".join(request.form.getlist("scheduled_days")) or "mon,tue,wed,thu,fri,sat,sun"

    elif notif_type == "periodic":
        try:
            interval_minutes = int(request.form.get("interval_minutes", 30))
            if not (5 <= interval_minutes <= 1440):
                raise ValueError
        except ValueError:
            flash("Interval must be between 5 and 1440 minutes.", "error")
            return redirect(url_for("notif.notifications_page"))
    print(f"DEBUG creating notif: {title}, {notif_type}, {scheduled_time}, {scheduled_days}", flush=True)
    try:
      db  = get_db()
      cur = db.cursor()
      cur.execute("""
          INSERT INTO notifications
              (user_id, title, message, notif_type, scheduled_time, scheduled_days, interval_minutes)
          VALUES (%s,%s,%s,%s,%s,%s,%s)
      """, (session["user_id"], title, message, notif_type,
            scheduled_time, scheduled_days, interval_minutes))
      db.commit()
      cur.close()
      db.close()
      print("DEBUG insert success", flush=True)
    except Exception as e:
      print(f"DEBUG insert error: {e}", flush=True)
    flash("Notification created.", "success")
    return redirect(url_for("notif.notifications_page"))

@notif_bp.route("/notifications/delete/<int:notif_id>", methods=["POST"])
def delete_notification(notif_id):
    if "user_id" not in session:
        return redirect(url_for("login_page"))

    db  = get_db()
    cur = db.cursor()
    cur.execute("DELETE FROM notifications WHERE id=%s AND user_id=%s",
                (notif_id, session["user_id"]))
    db.commit()
    cur.close()
    db.close()

    flash("Notification deleted.", "success")
    return redirect(url_for("notif.notifications_page"))


@notif_bp.route("/notifications/toggle/<int:notif_id>", methods=["POST"])
def toggle_notification(notif_id):
    if "user_id" not in session:
        return {"error": "Unauthorized"}, 401

    db  = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("SELECT is_active FROM notifications WHERE id=%s AND user_id=%s",
                (notif_id, session["user_id"]))
    row = cur.fetchone()
    if not row:
        cur.close()
        db.close()
        return {"error": "Not found"}, 404

    cur2 = db.cursor()
    cur2.execute("UPDATE notifications SET is_active=%s WHERE id=%s",
                 (not row["is_active"], notif_id))
    db.commit()
    cur.close()
    cur2.close()
    db.close()

    return {"ok": True, "is_active": not row["is_active"]}


@notif_bp.route("/notifications/due")
def notifications_due():
    """
    Called by the frontend on page load and periodically.
    Returns any scheduled notifications that are due within the last 2 minutes
    and haven't been triggered in the last 23 hours.
    """
    if "user_id" not in session:
        return {"notifications": []}

    user_id = session["user_id"]
    now     = datetime.now()
    day_map = {0:"mon",1:"tue",2:"wed",3:"thu",4:"fri",5:"sat",6:"sun"}
    today   = day_map[now.weekday()]

    db  = get_db()
    cur = db.cursor(dictionary=True)

    # Scheduled notifications due in ±2 minute window
    cur.execute("""
        SELECT n.id, n.title, n.message FROM notifications n
        WHERE n.user_id = %s
          AND n.notif_type = 'scheduled'
          AND n.is_active = TRUE
          AND FIND_IN_SET(%s, n.scheduled_days) > 0
          AND ABS(TIMESTAMPDIFF(MINUTE,
                CONCAT(CURDATE(), ' ', n.scheduled_time),
                NOW())) <= 2
          AND n.id NOT IN (
              SELECT notification_id FROM notification_log
              WHERE user_id = %s
                AND triggered_at >= DATE_SUB(NOW(), INTERVAL 23 HOUR)
          )
    """, (user_id, today, user_id))
    due = cur.fetchall()

    # Log them
    cur2 = db.cursor()
    for n in due:
        cur2.execute("""
            INSERT INTO notification_log (user_id, notification_id)
            VALUES (%s, %s)
        """, (user_id, n["id"]))
    if due:
        db.commit()

    cur.close()
    cur2.close()
    db.close()

    # Add at the end of notifications_due(), before return
    include_periodic = request.args.get('include_periodic') == '1'
    periodic = []
    if include_periodic:
        cur3 = db.cursor(dictionary=True)
        cur3.execute("""
            SELECT id, title, message, interval_minutes FROM notifications
            WHERE user_id=%s AND notif_type='periodic' AND is_active=TRUE
        """, (user_id,))
        periodic = cur3.fetchall()
        cur3.close()

    return {"notifications": due, "periodic": periodic}
