from decimal import Decimal
import os
import secrets
import re
import hashlib
import bcrypt
import smtplib
import requests
from email.message import EmailMessage
import mysql.connector
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, session, flash
from itsdangerous import URLSafeTimedSerializer

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret")

def get_db():
    return mysql.connector.connect(
        host=os.environ["DB_HOST"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASS"],
        database=os.environ["DB_NAME"],
    )

def get_serializer():
    return URLSafeTimedSerializer(app.secret_key)

def hash_token(raw_token):
    return hashlib.sha256(raw_token.encode()).hexdigest()

def generate_csrf_token():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(32)
    return session["csrf_token"]

@app.context_processor
def inject_csrf_token():
    return {"csrf_token": generate_csrf_token()}

def validate_csrf():
    form_token = request.form.get("csrf_token")
    session_token = session.get("csrf_token")
    return form_token and session_token and form_token == session_token

def print_link(label, link):
    print(f"\n=== {label} ===")
    print(link)
    print("====================\n")

def send_email(to_email: str, subject: str, body: str):
    mode = os.environ.get("EMAIL_MODE", "console")

    if mode == "console":
        print(f"\n=== EMAIL TO {to_email} ===")
        print(f"SUBJECT: {subject}")
        print(body)
        print("==========================\n")
        return

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = os.environ["FROM_EMAIL"]
    msg["To"] = to_email
    msg.set_content(body)

    with smtplib.SMTP(os.environ["SMTP_HOST"], int(os.environ.get("SMTP_PORT", "587"))) as server:
        server.starttls()
        server.login(os.environ["SMTP_USER"], os.environ["SMTP_PASS"])
        server.send_message(msg)

def is_strong_password(password):
    if len(password) < 8:
        return False, "Password must be at least 8 characters long."
    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter."
    if not re.search(r"[a-z]", password):
        return False, "Password must contain at least one lowercase letter."
    if not re.search(r"\d", password):
        return False, "Password must contain at least one number."
    if not re.search(r"[!@#$%^&*()_\-+=\[\]{};:'\",.<>?/\\|`~]", password):
        return False, "Password must contain at least one special character."
    return True, ""

@app.route("/")
def home():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login_page"))

@app.route("/register", methods=["GET"])
def register_page():
    return render_template("register.html")




@app.route("/register", methods=["POST"])
def register():
    if not validate_csrf():
        return "CSRF validation failed", 403

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    if not email or not password:
        flash("Email and password are required.", "error")
        return redirect(url_for("register_page"))
    is_valid, password_error = is_strong_password(password)
    if not is_valid:
        flash(password_error, "error")
        return redirect(url_for("register_page"))


    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

  

    db = get_db()
    cur = db.cursor()
    try:
        cur.execute(
            "INSERT INTO users (email, password_hash, is_verified) VALUES (%s, %s, %s)",
            (email, password_hash, False),
        )
        user_id = cur.lastrowid

        raw_token = secrets.token_urlsafe(32)
        token_hash = hash_token(raw_token)
        expires_at = datetime.utcnow() + timedelta(hours=1)

        cur.execute(
            "INSERT INTO email_verification_tokens (user_id, token_hash, expires_at) VALUES (%s, %s, %s)",
            (user_id, token_hash, expires_at),
        )

        db.commit()

        verify_link = f"{os.environ['BASE_URL']}/verify-email?token={raw_token}"
        send_email(email, "Verify your account", f"Click this link to verify your account:\n\n{verify_link}\n\nThis link expires in 1 hour.")

    except mysql.connector.errors.IntegrityError:
        cur.close()
        db.close()
        return "Email already exists", 409

    cur.close()
    db.close()
    flash("Account created successfully. Please check your email to verify your account before logging in.", "success")
    return redirect(url_for("login_page"))

@app.route("/verify-email")
def verify_email():
    raw_token = request.args.get("token", "")
    if not raw_token:
        return "Missing token", 400

    token_hash = hash_token(raw_token)
    now = datetime.utcnow()

    db = get_db()
    cur = db.cursor(dictionary=True)

    cur.execute(
        """
        SELECT id, user_id, expires_at, used_at
        FROM email_verification_tokens
        WHERE token_hash=%s
        """,
        (token_hash,),
    )
    row = cur.fetchone()

    if not row:
        cur.close()
        db.close()
        return "Invalid token", 400

    if row["used_at"] is not None:
        cur.close()
        db.close()
        return "Token already used", 400

    if row["expires_at"] < now:
        cur.close()
        db.close()
        return "Token expired", 400

    cur.execute("UPDATE users SET is_verified=TRUE WHERE id=%s", (row["user_id"],))
    cur.execute("UPDATE email_verification_tokens SET used_at=%s WHERE id=%s", (now, row["id"]))
    db.commit()

    cur.close()
    db.close()

    flash("Email verified. You can now log in.")
    return redirect(url_for("login_page"))

@app.route("/login", methods=["GET"])
def login_page():
    return render_template("login.html")

@app.route("/login", methods=["POST"])
def login():
    if not validate_csrf():
        return "CSRF validation failed", 403

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("SELECT id, email, password_hash, is_verified FROM users WHERE email=%s", (email,))
    user = cur.fetchone()
    cur.close()
    db.close()

    if not user:
        flash("Invalid credentials.", "error")
        return redirect(url_for("login_page"))

    if not bcrypt.checkpw(password.encode(), user["password_hash"].encode()):
        flash("Invalid credentials.", "error")
        return redirect(url_for("login_page"))

    if not user["is_verified"]:
        flash("Please verify your email before logging in.", "error")
        return redirect(url_for("login_page"))

    session["user_id"] = user["id"]
    session["email"] = user["email"]
    return redirect(url_for("dashboard"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login_page"))

@app.route("/forgot-password", methods=["GET"])
def forgot_password_page():
    return render_template("forgot_password.html")

@app.route("/forgot-password", methods=["POST"])
def forgot_password():
    if not validate_csrf():
        return "CSRF validation failed", 403

    email = request.form.get("email", "").strip().lower()

    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("SELECT id, email FROM users WHERE email=%s", (email,))
    user = cur.fetchone()

    if user:
        raw_token = secrets.token_urlsafe(32)
        token_hash = hash_token(raw_token)
        expires_at = datetime.utcnow() + timedelta(hours=1)

        cur2 = db.cursor()
        cur2.execute(
            "INSERT INTO password_reset_tokens (user_id, token_hash, expires_at) VALUES (%s, %s, %s)",
            (user["id"], token_hash, expires_at),
        )
        db.commit()
        cur2.close()

        reset_link = f"{os.environ['BASE_URL']}/reset-password?token={raw_token}"
        send_email(user["email"], "Reset your password", f"Click this link to reset your password:\n\n{reset_link}\n\nThis link expires in 1 hour.")

    cur.close()
    db.close()

    flash("If that email exists, a reset link has been generated.")
    return redirect(url_for("login_page"))

@app.route("/reset-password", methods=["GET"])
def reset_password_page():
    token = request.args.get("token", "")
    return render_template("reset_password.html", token=token)

@app.route("/reset-password", methods=["POST"])
def reset_password():
    if not validate_csrf():
        return "CSRF validation failed", 403

    raw_token = request.form.get("token", "")
    new_password = request.form.get("password", "")

    if not raw_token or not new_password:
        flash("Missing token or password.", "error")
        return redirect(url_for("login_page"))

    is_valid, password_error = is_strong_password(new_password)
    if not is_valid:
        flash(password_error, "error")
        return redirect(url_for("reset_password_page", token=raw_token))

    token_hash = hash_token(raw_token)
    now = datetime.utcnow()

    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute(
        """
        SELECT id, user_id, expires_at, used_at
        FROM password_reset_tokens
        WHERE token_hash=%s
        """,
        (token_hash,),
    )
    row = cur.fetchone()

    if not row:
        cur.close()
        db.close()
        return "Invalid token", 400

    if row["used_at"] is not None:
        cur.close()
        db.close()
        return "Token already used", 400

    if row["expires_at"] < now:
        cur.close()
        db.close()
        return "Token expired", 400

    new_hash = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()

    cur2 = db.cursor()
    cur2.execute("UPDATE users SET password_hash=%s WHERE id=%s", (new_hash, row["user_id"]))
    cur2.execute("UPDATE password_reset_tokens SET used_at=%s WHERE id=%s", (now, row["id"]))
    db.commit()

    cur.close()
    cur2.close()
    db.close()

    flash("Password reset successful. Please log in.")
    return redirect(url_for("login_page"))


# ---------------------------------------------------------------------------
# FR-10: Health & Fitness Goals
# ---------------------------------------------------------------------------

ACTIVITY_MULTIPLIERS = {
    "sedentary":        1.2,
    "lightly_active":   1.375,
    "moderately_active": 1.55,
    "very_active":      1.725,
    "extra_active":     1.9,
}

VALID_ACTIVITY_LEVELS = set(ACTIVITY_MULTIPLIERS.keys())
VALID_GOAL_TYPES      = {"lose", "maintain", "gain"}
VALID_SEXES           = {"male", "female"}

# Minimum safe calorie floors
MIN_CALORIES = {"male": 1500, "female": 1200}


def compute_goals(age, sex, height_cm, weight_kg, activity_level, goal_type):
    """
    Mifflin-St Jeor BMR → maintenance → target calories → macros.
    Returns a dict of all computed values.
    """
    # BMR
    if sex == "male":
        bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age + 5
    else:
        bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age - 161

    maintenance = bmr * ACTIVITY_MULTIPLIERS[activity_level]

    # Target calories before floor check
    if goal_type == "lose":
        target = maintenance - 500
    elif goal_type == "gain":
        target = maintenance + 300
    else:
        target = maintenance

    # Enforce calorie floor — clamp silently; UI shows actual value
    floor = MIN_CALORIES[sex]
    target = max(target, floor)

    # Macros based on current weight
    # Protein and fat first (gram targets), then carbs fill remaining calories.
    protein_g = round(1.8 * weight_kg, 1)
    fat_g     = round(0.8 * weight_kg, 1)

    protein_cals = protein_g * 4
    fat_cals     = fat_g * 9
    remaining    = target - protein_cals - fat_cals

    # If calories are so low that fat+protein already exceed budget, clamp carbs to 0
    # and reduce fat proportionally to fit within target.
    if remaining < 0:
        carbs_g = 0
        # Distribute remaining budget between protein and fat at ~1:1 calorie ratio
        # Keep protein priority; reduce fat.
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
    """
    Validates raw form input. Returns (cleaned_data dict, error_message or None).
    """
    errors = []

    # --- age ---
    try:
        age = int(form.get("age", ""))
        if not (10 <= age <= 120):
            errors.append("Age must be between 10 and 120.")
    except ValueError:
        errors.append("Age must be a whole number.")
        age = None

    # --- sex ---
    sex = form.get("sex", "").strip().lower()
    if sex not in VALID_SEXES:
        errors.append("Sex must be male or female.")

    # --- height ---
    try:
        height_cm = float(form.get("height_cm", ""))
        if not (50 <= height_cm <= 300):
            errors.append("Height must be between 50 and 300 cm.")
    except ValueError:
        errors.append("Height must be a number.")
        height_cm = None

    # --- current weight ---
    try:
        current_weight_kg = float(form.get("current_weight_kg", ""))
        if not (20 <= current_weight_kg <= 500):
            errors.append("Current weight must be between 20 and 500 kg.")
    except ValueError:
        errors.append("Current weight must be a number.")
        current_weight_kg = None

    # --- activity level ---
    activity_level = form.get("activity_level", "").strip()
    if activity_level not in VALID_ACTIVITY_LEVELS:
        errors.append("Invalid activity level.")

    # --- goal type ---
    goal_type = form.get("goal_type", "").strip()
    if goal_type not in VALID_GOAL_TYPES:
        errors.append("Invalid goal type.")

    # --- target weight ---
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


@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("login_page"))

    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("SELECT * FROM user_goals WHERE user_id = %s", (session["user_id"],))
    goals = cur.fetchone()
    cur.close()
    db.close()

    meals  = get_today_meals(session["user_id"])
    totals = get_daily_totals(meals)

    return render_template("dashboard.html",
                           email=session["email"],
                           goals=goals,
                           meals=meals,
                           totals=totals)


@app.route("/goals", methods=["POST"])
def save_goals():
    if "user_id" not in session:
        return redirect(url_for("login_page"))

    if not validate_csrf():
        return "CSRF validation failed", 403

    data, error = validate_goals_form(request.form)
    if error:
        flash(error, "error")
        return redirect(url_for("dashboard"))

    computed = compute_goals(
        age            = data["age"],
        sex            = data["sex"],
        height_cm      = data["height_cm"],
        weight_kg      = data["current_weight_kg"],
        activity_level = data["activity_level"],
        goal_type      = data["goal_type"],
    )

    db = get_db()
    cur = db.cursor()

    # Upsert: insert or update the single row for this user
    cur.execute("""
        INSERT INTO user_goals
            (user_id, age, sex, height_cm, current_weight_kg, activity_level,
             goal_type, target_weight_kg, bmr, maintenance_calories,
             target_calories, protein_g, carbs_g, fat_g)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
        data["age"],
        data["sex"],
        data["height_cm"],
        data["current_weight_kg"],
        data["activity_level"],
        data["goal_type"],
        data["target_weight_kg"],
        computed["bmr"],
        computed["maintenance_calories"],
        computed["target_calories"],
        computed["protein_g"],
        computed["carbs_g"],
        computed["fat_g"],
    ))

    db.commit()
    cur.close()
    db.close()

    flash("Goals saved successfully.", "success")
    return redirect(url_for("dashboard"))


# ---------------------------------------------------------------------------
# FR-11: Meal Logging — USDA FoodData Central integration
# ---------------------------------------------------------------------------

USDA_API_KEY = ""
USDA_SEARCH_URL = "https://api.nal.usda.gov/fdc/v1/foods/search"
USDA_FOOD_URL   = "https://api.nal.usda.gov/fdc/v1/food/{fdc_id}"

VALID_MEAL_TYPES = {"breakfast", "lunch", "dinner", "snack"}

# Nutrient IDs we care about in USDA responses
USDA_NUTRIENT_IDS = {
    "calories": 1008,   # Energy (kcal)
    "protein":  1003,   # Protein
    "fat":      1004,   # Total lipid (fat)
    "carbs":    1005,   # Carbohydrate, by difference
}



def usda_search(query, page_size=8):
    """
    Search USDA FoodData Central.
    
    Important: the /foods/search endpoint returns nutrients per serving for
    branded foods, and often omits them entirely. We prefer SR Legacy and
    Foundation foods which reliably include per-100g nutrients in search results.
    For branded foods with missing nutrients we still return them so the user
    can see the name — nutrients will show as 0 until we add a detail fetch.
    """
    try:
        resp = requests.get(USDA_SEARCH_URL, params={
            "api_key":  USDA_API_KEY,
            "query":    query,
            "pageSize": page_size,
            # Prioritise SR Legacy (reliable per-100g data) then Foundation, then Branded
            "dataType": "SR Legacy,Foundation,Branded",
        }, timeout=6)
        resp.raise_for_status()
        data = resp.json()
        # TEMP DEBUG — remove after fixing
        app.logger.warning(f"USDA raw hit count: {data.get('totalHits')}")
        app.logger.warning(f"First food sample: {data.get('foods', [{}])[0]}")
    except Exception as e:
        app.logger.error(f"USDA search error: {e}")
        return []

    results = []
    for f in data.get("foods", []):
        # Build nutrient lookup — nutrientId is always an int in practice
        # but guard against strings just in case
        nutrients = {}
        for n in f.get("foodNutrients", []):
            nid = n.get("nutrientId") or n.get("nutrientid")
            if nid is not None:
                nutrients[int(nid)] = n.get("value", 0) or 0

        calories  = nutrients.get(USDA_NUTRIENT_IDS["calories"], 0)
        protein_g = nutrients.get(USDA_NUTRIENT_IDS["protein"],  0)
        carbs_g   = nutrients.get(USDA_NUTRIENT_IDS["carbs"],    0)
        fat_g     = nutrients.get(USDA_NUTRIENT_IDS["fat"],      0)

        results.append({
            "fdc_id":    f["fdcId"],
            "name":      f.get("description", "Unknown").title(),
            "brand":     f.get("brandOwner", ""),
            "data_type": f.get("dataType", ""),
            "calories":  round(calories,  1),
            "protein_g": round(protein_g, 1),
            "carbs_g":   round(carbs_g,   1),
            "fat_g":     round(fat_g,     1),
        })

    return results



def scale_nutrients(food_per_100g, portion_g):
    """
    All USDA values are per 100g. Scale to the user's logged portion.
    """
    factor = portion_g / 100.0
    return {
        "calories":  round(food_per_100g["calories"]  * factor, 2),
        "protein_g": round(food_per_100g["protein_g"] * factor, 2),
        "carbs_g":   round(food_per_100g["carbs_g"]   * factor, 2),
        "fat_g":     round(food_per_100g["fat_g"]     * factor, 2),
    }


def get_today_meals(user_id):
    """Fetch all meals logged today for the dashboard summary."""
    today = datetime.utcnow().date()
    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("""
        SELECT id, food_name, meal_type, portion_g,
               calories, protein_g, carbs_g, fat_g, logged_at
        FROM meal_logs
        WHERE user_id = %s AND log_date = %s
        ORDER BY logged_at ASC
    """, (user_id, today))
    rows = cur.fetchall()
    cur.close()
    db.close()
    return rows


def get_daily_totals(meals):
    """Sum up macros from a list of meal dicts."""
    return {
        "calories":  round(sum(m["calories"]  for m in meals), 1),
        "protein_g": round(sum(m["protein_g"] for m in meals), 1),
        "carbs_g":   round(sum(m["carbs_g"]   for m in meals), 1),
        "fat_g":     round(sum(m["fat_g"]     for m in meals), 1),
    }


# ── Routes ──────────────────────────────────────────────────────────────────


@app.route("/meals/food/<int:fdc_id>")
def meal_food_detail(fdc_id):
    """
    Fetch full nutrient detail for a single food from USDA.
    The detail endpoint reliably returns per-100g nutrients for all food types.
    """
    if "user_id" not in session:
        return {"error": "Unauthorized"}, 401

    try:
        resp = requests.get(
            USDA_FOOD_URL.format(fdc_id=fdc_id),
            params={"api_key": USDA_API_KEY},
            timeout=6
        )
        resp.raise_for_status()
        f = resp.json()
    except Exception as e:
        app.logger.error(f"USDA detail error: {e}")
        return {"error": "Failed to fetch food details"}, 500

    nutrients = {}
    for n in f.get("foodNutrients", []):
        # Detail endpoint nests nutrient id under "nutrient" sub-object
        nutrient_obj = n.get("nutrient", {})
        nid = nutrient_obj.get("id")
        if nid is not None:
            nutrients[int(nid)] = n.get("amount", 0) or 0

    return {
        "fdc_id":    f.get("fdcId"),
        "name":      f.get("description", "Unknown").title(),
        "calories":  round(nutrients.get(USDA_NUTRIENT_IDS["calories"], 0), 1),
        "protein_g": round(nutrients.get(USDA_NUTRIENT_IDS["protein"],  0), 1),
        "carbs_g":   round(nutrients.get(USDA_NUTRIENT_IDS["carbs"],    0), 1),
        "fat_g":     round(nutrients.get(USDA_NUTRIENT_IDS["fat"],      0), 1),
    }


@app.route("/meals/search")
def meal_search():
    """AJAX endpoint — returns JSON search results from USDA."""
    if "user_id" not in session:
        return {"error": "Unauthorized"}, 401

    query = request.args.get("q", "").strip()
    if not query or len(query) < 2:
        return {"results": []}

    return {"results": usda_search(query)}


@app.route("/meals/log", methods=["POST"])
def log_meal():
    if "user_id" not in session:
        return redirect(url_for("login_page"))

    if not validate_csrf():
        return "CSRF validation failed", 403

    # Collect form values
    meal_type = request.form.get("meal_type", "").strip()
    fdc_id    = request.form.get("fdc_id", "").strip()
    food_name = request.form.get("food_name", "").strip()

    try:
        portion_g = float(request.form.get("portion_g", 0))
        if portion_g <= 0 or portion_g > 5000:
            raise ValueError
    except ValueError:
        flash("Invalid portion size.", "error")
        return redirect(url_for("meals_page"))

    # Per-100g values come from hidden fields populated by JS after search
    try:
        per100 = {
            "calories":  float(request.form.get("cal_per100",  0)),
            "protein_g": float(request.form.get("prot_per100", 0)),
            "carbs_g":   float(request.form.get("carb_per100", 0)),
            "fat_g":     float(request.form.get("fat_per100",  0)),
        }
    except ValueError:
        flash("Invalid nutrition data.", "error")
        return redirect(url_for("meals_page"))

    if meal_type not in VALID_MEAL_TYPES:
        flash("Invalid meal type.", "error")
        return redirect(url_for("meals_page"))

    if not fdc_id or not food_name:
        flash("Please select a food from the search results.", "error")
        return redirect(url_for("meals_page"))

    scaled = scale_nutrients(per100, portion_g)
    today  = datetime.utcnow().date()

    db = get_db()
    cur = db.cursor()
    cur.execute("""
        INSERT INTO meal_logs
            (user_id, fdc_id, food_name, meal_type, portion_g,
             calories, protein_g, carbs_g, fat_g, log_date)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        session["user_id"],
        int(fdc_id),
        food_name,
        meal_type,
        portion_g,
        scaled["calories"],
        scaled["protein_g"],
        scaled["carbs_g"],
        scaled["fat_g"],
        today,
    ))
    db.commit()
    cur.close()
    db.close()

    flash(f"{food_name} logged successfully.", "success")
    return redirect(url_for("meals_page"))


@app.route("/meals/delete/<int:meal_id>", methods=["POST"])
def delete_meal(meal_id):
    if "user_id" not in session:
        return redirect(url_for("login_page"))

    if not validate_csrf():
        return "CSRF validation failed", 403

    db = get_db()
    cur = db.cursor()
    # WHERE user_id guards against deleting another user's entry
    cur.execute("DELETE FROM meal_logs WHERE id = %s AND user_id = %s",
                (meal_id, session["user_id"]))
    db.commit()
    cur.close()
    db.close()

    flash("Meal removed.", "success")
    return redirect(url_for("meals_page"))


@app.route("/meals")
def meals_page():
    if "user_id" not in session:
        return redirect(url_for("login_page"))

    meals  = get_today_meals(session["user_id"])
    totals = get_daily_totals(meals)

    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("SELECT * FROM user_goals WHERE user_id = %s", (session["user_id"],))
    goals = cur.fetchone()
    cur.close()
    db.close()

    return render_template("meals.html",
                           email=session["email"],
                           meals=meals,
                           totals=totals,
                           goals=goals)



if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
