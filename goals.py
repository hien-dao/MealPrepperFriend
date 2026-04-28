import os
import mysql.connector
from datetime import date, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, session, flash

goals_bp = Blueprint('goals', __name__)

# ---------------------------------------------------------------------------
# DB + CSRF helpers
# ---------------------------------------------------------------------------

def get_db():
    return mysql.connector.connect(
        host=os.environ["DB_HOST"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASS"],
        database=os.environ["DB_NAME"],
    )

def validate_csrf():
	return True
'''
    if request.is_json:
        form_token = (request.get_json(silent=True) or {}).get("csrf_token")
    else:
        form_token = request.form.get("csrf_token")
    return form_token and form_token == session.get("csrf_token")
'''
# ---------------------------------------------------------------------------
# Calculation constants
# ---------------------------------------------------------------------------

ACTIVITY_MULTIPLIERS = {
    "sedentary":         1.2,
    "lightly_active":    1.375,
    "moderately_active": 1.55,
    "very_active":       1.725,
    "extra_active":      1.9,
}

VALID_ACTIVITY_LEVELS = set(ACTIVITY_MULTIPLIERS.keys())
VALID_GOAL_TYPES      = {"lose", "maintain", "gain"}
VALID_SEXES           = {"male", "female"}
MIN_CALORIES          = {"male": 1500, "female": 1200}

# ---------------------------------------------------------------------------
# Calculation logic
# ---------------------------------------------------------------------------

def compute_goals(age, sex, height_cm, weight_kg, activity_level, goal_type):
    """Mifflin-St Jeor BMR -> maintenance -> target calories -> macros."""
    if sex == "male":
        bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age + 5
    else:
        bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age - 161

    maintenance = bmr * ACTIVITY_MULTIPLIERS[activity_level]

    if goal_type == "lose":
        target = maintenance - 500
    elif goal_type == "gain":
        target = maintenance + 300
    else:
        target = maintenance

    target = max(target, MIN_CALORIES[sex])

    protein_g    = round(1.8 * weight_kg, 1)
    fat_g        = round(0.8 * weight_kg, 1)
    protein_cals = protein_g * 4
    fat_cals     = fat_g * 9
    remaining    = target - protein_cals - fat_cals

    if remaining < 0:
        carbs_g  = 0
        fat_cals = max(0, target - protein_cals)
        fat_g    = round(fat_cals / 9, 1)
    else:
        carbs_g = round(remaining / 4, 1)

    return {
        "bmr":                  round(bmr, 2),
        "maintenance_calories": round(maintenance, 2),
        "target_calories":      round(target, 2),
        "protein_g":            protein_g,
        "carbs_g":              carbs_g,
        "fat_g":                fat_g,
    }


def validate_goals_form(form):
    """Validates raw form input. Returns (cleaned_data, error_string or None)."""
    errors = []

    try:
        age = int(form.get("age", ""))
        if not (10 <= age <= 120):
            errors.append("Age must be between 10 and 120.")
    except ValueError:
        errors.append("Age must be a whole number.")
        age = None

    sex = form.get("sex", "").strip().lower()
    if sex not in VALID_SEXES:
        errors.append("Sex must be male or female.")

    try:
        height_cm = float(form.get("height_cm", ""))
        if not (50 <= height_cm <= 300):
            errors.append("Height must be between 50 and 300 cm.")
    except ValueError:
        errors.append("Height must be a number.")
        height_cm = None

    try:
        current_weight_kg = float(form.get("current_weight_kg", ""))
        if not (20 <= current_weight_kg <= 500):
            errors.append("Current weight must be between 20 and 500 kg.")
    except ValueError:
        errors.append("Current weight must be a number.")
        current_weight_kg = None

    activity_level = form.get("activity_level", "").strip()
    if activity_level not in VALID_ACTIVITY_LEVELS:
        errors.append("Invalid activity level.")

    goal_type = form.get("goal_type", "").strip()
    if goal_type not in VALID_GOAL_TYPES:
        errors.append("Invalid goal type.")

    try:
        target_weight_kg = float(form.get("target_weight_kg", ""))
        if not (20 <= target_weight_kg <= 500):
            errors.append("Target weight must be between 20 and 500 kg.")
    except ValueError:
        errors.append("Target weight must be a number.")
        target_weight_kg = None

    if errors:
        return None, " ".join(errors)

    return {
        "age":               age,
        "sex":               sex,
        "height_cm":         height_cm,
        "current_weight_kg": current_weight_kg,
        "activity_level":    activity_level,
        "goal_type":         goal_type,
        "target_weight_kg":  target_weight_kg,
    }, None

# ---------------------------------------------------------------------------
# Dashboard helpers (imported by app.py)
# ---------------------------------------------------------------------------

def get_weekly_calories(user_id):
    db  = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("""
        SELECT log_date, SUM(calories) as total_calories
        FROM meal_logs
        WHERE user_id = %s
          AND log_date >= DATE_SUB(CURDATE(), INTERVAL 6 DAY)
        GROUP BY log_date
        ORDER BY log_date ASC
    """, (user_id,))
    rows = cur.fetchall()
    cur.close()
    db.close()

    today = date.today()
    days  = {(today - timedelta(days=i)).isoformat(): 0 for i in range(6, -1, -1)}
    for row in rows:
        key = row['log_date'].isoformat() if hasattr(row['log_date'], 'isoformat') else str(row['log_date'])
        days[key] = float(row['total_calories'])

    return [{"date": d, "calories": c} for d, c in days.items()]


def get_streak(user_id):
    """Count consecutive days ending today where the user logged at least one meal."""
    db  = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("""
        SELECT DISTINCT log_date FROM meal_logs
        WHERE user_id = %s ORDER BY log_date DESC LIMIT 365
    """, (user_id,))
    rows = cur.fetchall()
    cur.close()
    db.close()

    logged_days = {r['log_date'] for r in rows}
    streak = 0
    day    = date.today()
    while day in logged_days:
        streak += 1
        day -= timedelta(days=1)
    return streak


def get_weekly_stats(user_id):
    db  = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("""
        SELECT
            COUNT(DISTINCT log_date) AS days_logged,
            COALESCE(SUM(calories),  0) AS calories,
            COALESCE(SUM(protein_g), 0) AS protein_g,
            COALESCE(SUM(carbs_g),   0) AS carbs_g,
            COALESCE(SUM(fat_g),     0) AS fat_g,
            COUNT(*)                    AS total_meals
        FROM meal_logs
        WHERE user_id = %s
          AND log_date >= DATE_SUB(CURDATE(), INTERVAL 6 DAY)
    """, (user_id,))
    row = cur.fetchone()
    cur.close()
    db.close()
    return row


def get_recent_days(user_id, days=3):
    db  = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("""
        SELECT log_date, SUM(calories) AS calories, COUNT(*) AS meals
        FROM meal_logs
        WHERE user_id = %s
          AND log_date >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
          AND log_date < CURDATE()
        GROUP BY log_date
        ORDER BY log_date DESC
        LIMIT %s
    """, (user_id, days, days))
    rows = cur.fetchall()
    cur.close()
    db.close()
    return rows


def get_workout_summary(user_id):
    """Weekly count, monthly total, and last session for the progress page."""
    db  = get_db()
    cur = db.cursor(dictionary=True)

    cur.execute("""
        SELECT COUNT(*) AS weekly_count
        FROM workout_sessions
        WHERE user_id=%s
          AND session_date >= DATE_SUB(CURDATE(), INTERVAL 6 DAY)
    """, (user_id,))
    weekly = cur.fetchone()["weekly_count"]

    cur.execute("""
        SELECT COUNT(*) AS monthly_count
        FROM workout_sessions
        WHERE user_id=%s
          AND session_date >= DATE_SUB(CURDATE(), INTERVAL 29 DAY)
    """, (user_id,))
    monthly = cur.fetchone()["monthly_count"]

    cur.execute("""
        SELECT ws.id, ws.name, ws.session_date,
               COUNT(we.id) AS exercise_count
        FROM workout_sessions ws
        LEFT JOIN workout_exercises we ON we.session_id = ws.id
        WHERE ws.user_id=%s
        GROUP BY ws.id
        ORDER BY ws.session_date DESC
        LIMIT 1
    """, (user_id,))
    last = cur.fetchone()

    if last and hasattr(last["session_date"], "isoformat"):
        last["session_date"] = last["session_date"].isoformat()

    cur.close()
    db.close()
    return {"weekly": weekly, "monthly": monthly, "last": last}

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@goals_bp.route("/goals", methods=["POST"])
def save_goals():
    if "user_id" not in session:
        return redirect(url_for("login_page"))
    if not validate_csrf():
        return "CSRF validation failed", 403

    data, error = validate_goals_form(request.form)
    if error:
        flash(error, "error")
        return redirect(url_for("goals.goals_page"))

    computed = compute_goals(
        age            = data["age"],
        sex            = data["sex"],
        height_cm      = data["height_cm"],
        weight_kg      = data["current_weight_kg"],
        activity_level = data["activity_level"],
        goal_type      = data["goal_type"],
    )

    db  = get_db()
    cur = db.cursor()

    cur.execute("""
        INSERT INTO user_goals
            (user_id, age, sex, height_cm, current_weight_kg, activity_level,
             goal_type, target_weight_kg, bmr, maintenance_calories,
             target_calories, protein_g, carbs_g, fat_g)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON DUPLICATE KEY UPDATE
            age                  = VALUES(age),
            sex                  = VALUES(sex),
            height_cm            = VALUES(height_cm),
            current_weight_kg    = VALUES(current_weight_kg),
            activity_level       = VALUES(activity_level),
            goal_type            = VALUES(goal_type),
            target_weight_kg     = VALUES(target_weight_kg),
            bmr                  = VALUES(bmr),
            maintenance_calories = VALUES(maintenance_calories),
            target_calories      = VALUES(target_calories),
            protein_g            = VALUES(protein_g),
            carbs_g              = VALUES(carbs_g),
            fat_g                = VALUES(fat_g),
            updated_at           = CURRENT_TIMESTAMP
    """, (
        session["user_id"],
        data["age"], data["sex"], data["height_cm"],
        data["current_weight_kg"], data["activity_level"],
        data["goal_type"], data["target_weight_kg"],
        computed["bmr"], computed["maintenance_calories"],
        computed["target_calories"], computed["protein_g"],
        computed["carbs_g"], computed["fat_g"],
    ))

    # Snapshot every save to goals_history
    cur.execute("""
        INSERT INTO goals_history
            (user_id, age, sex, height_cm, current_weight_kg, activity_level,
             goal_type, target_weight_kg, bmr, maintenance_calories,
             target_calories, protein_g, carbs_g, fat_g)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """, (
        session["user_id"],
        data["age"], data["sex"], data["height_cm"],
        data["current_weight_kg"], data["activity_level"],
        data["goal_type"], data["target_weight_kg"],
        computed["bmr"], computed["maintenance_calories"],
        computed["target_calories"], computed["protein_g"],
        computed["carbs_g"], computed["fat_g"],
    ))

    db.commit()
    cur.close()
    db.close()

    flash("Goals saved successfully.", "success")
    return redirect(url_for("goals.goals_page"))


@goals_bp.route("/progress")
def goals_page():
    if "user_id" not in session:
        return redirect(url_for("login_page"))

    user_id = session["user_id"]
    db      = get_db()
    cur     = db.cursor(dictionary=True)

    cur.execute("SELECT * FROM user_goals WHERE user_id=%s", (user_id,))
    goals = cur.fetchone()

    cur.execute("""
        SELECT * FROM goals_history WHERE user_id=%s
        ORDER BY saved_at DESC LIMIT 10
    """, (user_id,))
    history = cur.fetchall()

    cur.execute("""
        SELECT log_date, weight_kg, note FROM weight_logs
        WHERE user_id=%s AND log_date >= DATE_SUB(CURDATE(), INTERVAL 29 DAY)
        ORDER BY log_date ASC
    """, (user_id,))
    weight_logs = [
        {
            "weight_kg": float(w["weight_kg"]),
            "log_date":  w["log_date"].isoformat() if hasattr(w["log_date"], "isoformat") else str(w["log_date"]),
            "note":      w["note"],
        }
        for w in cur.fetchall()
    ]

    cur.execute("SELECT weight_kg FROM weight_logs WHERE user_id=%s AND log_date=%s",
                (user_id, date.today()))
    today_weight = cur.fetchone()

    cur.close()
    db.close()

    workout_summary = get_workout_summary(user_id)

    return render_template("goals_page.html",
                           email=session["email"],
                           goals=goals,
                           history=history,
                           weight_logs=weight_logs,
                           today_weight=today_weight,
                           today_date=date.today().isoformat(),
                           workout_summary=workout_summary)


@goals_bp.route("/goals-page")
def goals_page_redirect():
    """Redirect old URL to new /progress URL."""
    return redirect("/progress", code=301)


@goals_bp.route("/progress/weight", methods=["POST"])
def log_weight():
    if "user_id" not in session:
        return redirect(url_for("login_page"))
    if not validate_csrf():
        return "CSRF failed", 403

    try:
        weight_kg = float(request.form.get("weight_kg", 0))
        if not (20 <= weight_kg <= 500):
            raise ValueError
    except ValueError:
        flash("Invalid weight.", "error")
        return redirect(url_for("goals.goals_page"))

    note     = request.form.get("note", "").strip() or None
    log_date = request.form.get("log_date", date.today().isoformat())

    db  = get_db()
    cur = db.cursor()
    cur.execute("""
        INSERT INTO weight_logs (user_id, weight_kg, log_date, note)
        VALUES (%s,%s,%s,%s)
        ON DUPLICATE KEY UPDATE weight_kg=VALUES(weight_kg), note=VALUES(note)
    """, (session["user_id"], weight_kg, log_date, note))
    db.commit()
    cur.close()
    db.close()

    flash("Weight logged.", "success")
    return redirect(url_for("goals.goals_page"))
