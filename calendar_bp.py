import os
import json
import mysql.connector
from datetime import date, timedelta
import calendar as cal_lib
from flask import Blueprint, render_template, request, redirect, url_for, session

calendar_bp = Blueprint('calendar', __name__)

def get_db():
    return mysql.connector.connect(
        host=os.environ["DB_HOST"], user=os.environ["DB_USER"],
        password=os.environ["DB_PASS"], database=os.environ["DB_NAME"],
    )


@calendar_bp.route("/calendar")
def calendar_page():
    if "user_id" not in session:
        return redirect(url_for("login_page"))

    today = date.today()
    year  = int(request.args.get("year",  today.year))
    month = int(request.args.get("month", today.month))

    # Clamp
    if month < 1:  month = 12; year -= 1
    if month > 12: month = 1;  year += 1

    # Build calendar grid
    first_day    = date(year, month, 1)
    days_in_month = cal_lib.monthrange(year, month)[1]
    start_weekday = first_day.weekday()  # 0=Mon

    db  = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("""
        SELECT id, plan_date, dish_name, ingredients
        FROM calendar_recipes
        WHERE user_id=%s
          AND YEAR(plan_date)=%s
          AND MONTH(plan_date)=%s
        ORDER BY plan_date ASC
    """, (session["user_id"], year, month))
    rows = cur.fetchall()
    cur.close()
    db.close()

    # Map date -> list of recipes
    recipes_by_date = {}
    for r in rows:
        key = r["plan_date"].isoformat() if hasattr(r["plan_date"], "isoformat") else str(r["plan_date"])
        if isinstance(r["ingredients"], str):
            r["ingredients"] = json.loads(r["ingredients"])
        recipes_by_date.setdefault(key, []).append(r)

    # Prev/next month
    prev_month = month - 1 or 12
    prev_year  = year - 1 if month == 1 else year
    next_month = month % 12 + 1
    next_year  = year + 1 if month == 12 else year

    return render_template("calendar.html",
                           email=session["email"],
                           year=year, month=month,
                           days_in_month=days_in_month,
                           start_weekday=start_weekday,
                           recipes_by_date=recipes_by_date,
                           today=today.isoformat(),
                           month_name=first_day.strftime("%B %Y"),
                           prev_month=prev_month, prev_year=prev_year,
                           next_month=next_month, next_year=next_year)


@calendar_bp.route("/calendar/delete/<int:entry_id>", methods=["POST"])
def calendar_delete(entry_id):
    if "user_id" not in session:
        return {"error": "Unauthorized"}, 401

    db  = get_db()
    cur = db.cursor()
    cur.execute("DELETE FROM calendar_recipes WHERE id=%s AND user_id=%s",
                (entry_id, session["user_id"]))
    db.commit()
    cur.close()
    db.close()
    return {"ok": True}
