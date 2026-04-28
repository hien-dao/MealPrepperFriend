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
from openai import OpenAI
import json
import re


app = Flask(__name__)
from forum import forum_bp
app.register_blueprint(forum_bp)
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
def inject_user_flags():
    is_premium = False
    if "user_id" in session:
        db  = get_db()
        cur = db.cursor(dictionary=True)
        cur.execute("SELECT is_premium FROM users WHERE id=%s", (session["user_id"],))
        row = cur.fetchone()
        cur.close()
        db.close()
        is_premium = bool(row["is_premium"]) if row else False
    return {"is_premium": is_premium}
def inject_csrf_token():
    return {"csrf_token": generate_csrf_token()}

def validate_csrf():
	return True
'''
    if request.is_json:
        form_token = (request.get_json(silent=True) or {}).get("csrf_token")
    else:
        form_token = request.form.get("csrf_token")
    session_token = session.get("csrf_token")
    return form_token and session_token and form_token == session_token
'''
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
# -------------------------------------------------------------------------


from goals import goals_bp, get_weekly_calories, get_streak, get_weekly_stats, get_recent_days
app.register_blueprint(goals_bp)



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

    meals        = get_today_meals(session["user_id"])
    totals       = get_daily_totals(meals)
    weekly_cals  = get_weekly_calories(session["user_id"])
    streak       = get_streak(session["user_id"])
    weekly_stats = get_weekly_stats(session["user_id"])
    recent_days  = get_recent_days(session["user_id"])
    recipes      = get_random_recipes(3)

    return render_template("dashboard.html",
                           email=session["email"],
                           goals=goals,
                           meals=meals,
                           totals=totals,
                           weekly_cals=weekly_cals,
                           streak=streak,
                           weekly_stats=weekly_stats,
                           recent_days=recent_days,
                           recipes=recipes)

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



# ---------------------------------------------------------------------------
# Chatbot — GPT-4o nutrition assistant
# ---------------------------------------------------------------------------

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

SYSTEM_PROMPT = """You are Nouri, a friendly and knowledgeable nutrition assistant built into the Nourish app.

You help users with three things:
1. Answer nutrition and food questions clearly and accurately.
2. Log meals conversationally. When a user says something like "I just ate 200g of chicken breast for lunch", extract the food, quantity in grams, and meal type, then log it.
3. Suggest recipes based on ingredients the user has on hand.

You will be given the user's fitness goals and today's meal log as context. Use this to give personalised answers — for example, tell them how many calories they have left for the day, whether a meal fits their macros, etc.

RULES FOR LOGGING MEALS:
- When the user clearly wants to log a meal, include this exact tag in your response:
  <action>{"type": "log_meal", "food_query": "chicken breast", "portion_g": 200, "meal_type": "lunch"}</action>
- meal_type must be one of: breakfast, lunch, dinner, snack
- If portion is not given in grams, make a reasonable estimate and state what you assumed.
- If meal_type is unclear, infer from context (e.g. morning → breakfast) or ask.
- Always confirm what was logged in plain language after the action tag.
- Only include the action tag when the user is clearly asking to log something.

RULES FOR RECIPE SUGGESTIONS:
- When a user lists ingredients they have, suggest 2–3 practical recipes using mostly those ingredients.
- Keep recipes simple and include rough calorie estimates if possible.
- Format recipe suggestions clearly with a name, key ingredients, and brief method.

GENERAL RULES:
- Keep responses concise and friendly. Use short paragraphs.
- Do not invent specific nutrition numbers — give ranges or general guidance if unsure.
- Always relate advice back to the user's goals and remaining daily targets where relevant."""


def get_user_context(user_id):
    """
    Fetch the user's saved goals and today's meals,
    and format them as a context string for the system prompt.
    """
    db = get_db()
    cur = db.cursor(dictionary=True)

    cur.execute("SELECT * FROM user_goals WHERE user_id = %s", (user_id,))
    goals = cur.fetchone()

    today = datetime.utcnow().date()
    cur.execute("""
        SELECT food_name, meal_type, portion_g, calories, protein_g, carbs_g, fat_g
        FROM meal_logs
        WHERE user_id = %s AND log_date = %s
        ORDER BY logged_at ASC
    """, (user_id, today))
    meals = cur.fetchall()

    cur.close()
    db.close()

    ctx = "\n\n--- USER CONTEXT ---"

    if goals:
        ctx += f"""
User profile:
- Age: {goals['age']}, Sex: {goals['sex']}
- Height: {goals['height_cm']} cm, Current weight: {goals['current_weight_kg']} kg
- Goal: {goals['goal_type']} weight (target: {goals['target_weight_kg']} kg)
- Activity level: {goals['activity_level']}
- Daily targets: {int(goals['target_calories'])} kcal | {goals['protein_g']}g protein | {goals['carbs_g']}g carbs | {goals['fat_g']}g fat"""
    else:
        ctx += "\nUser has not set fitness goals yet."

    if meals:
        totals = get_daily_totals(meals)
        ctx += f"\n\nToday's meals ({today}):"
        for m in meals:
            ctx += f"\n- {m['meal_type'].capitalize()}: {m['food_name']} ({int(m['portion_g'])}g, {int(m['calories'])} kcal)"
        ctx += f"\nToday's totals: {int(totals['calories'])} kcal | {totals['protein_g']}g protein | {totals['carbs_g']}g carbs | {totals['fat_g']}g fat"
        if goals:
            remaining = int(goals['target_calories']) - int(totals['calories'])
            ctx += f"\nRemaining today: {remaining} kcal"
    else:
        ctx += f"\n\nNo meals logged today ({today}) yet."

    ctx += "\n--- END USER CONTEXT ---"
    return ctx


def get_chat_history(user_id, limit=20):
    """Fetch recent conversation history in OpenAI message format."""
    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("""
        SELECT role, content FROM chat_messages
        WHERE user_id = %s
        ORDER BY created_at DESC
        LIMIT %s
    """, (user_id, limit))
    rows = cur.fetchall()
    cur.close()
    db.close()
    return list(reversed(rows))  # chronological order


def save_message(user_id, role, content):
    """Persist a single message to chat_messages."""
    db = get_db()
    cur = db.cursor()
    cur.execute(
        "INSERT INTO chat_messages (user_id, role, content) VALUES (%s, %s, %s)",
        (user_id, role, content)
    )
    db.commit()
    cur.close()
    db.close()


def parse_action(response_text):
    """
    Extract <action>{...}</action> from the model's response.
    Returns (clean_text_without_tag, action_dict or None).
    """
    match = re.search(r'<action>(.*?)</action>', response_text, re.DOTALL)
    if not match:
        return response_text, None
    try:
        action = json.loads(match.group(1).strip())
    except json.JSONDecodeError:
        return response_text, None
    clean = re.sub(r'<action>.*?</action>', '', response_text, flags=re.DOTALL).strip()
    return clean, action


def execute_action(action, user_id):
    """
    Execute a structured action parsed from the model response.
    Currently supports: log_meal
    """
    if action.get('type') != 'log_meal':
        return

    food_query = action.get('food_query', '')
    portion_g  = float(action.get('portion_g', 100))
    meal_type  = action.get('meal_type', 'snack')

    if meal_type not in VALID_MEAL_TYPES:
        meal_type = 'snack'

    # Search USDA for the food
    foods = usda_search(food_query, page_size=1)
    if not foods:
        app.logger.warning(f"Chat meal log: no USDA result for '{food_query}'")
        return

    food = foods[0]

    # Fetch full per-100g detail
    try:
        resp = requests.get(
            USDA_FOOD_URL.format(fdc_id=food['fdc_id']),
            params={"api_key": USDA_API_KEY},
            timeout=6
        )
        full = resp.json()
        nutrients = {}
        for n in full.get("foodNutrients", []):
            nid = n.get("nutrient", {}).get("id")
            if nid:
                nutrients[int(nid)] = n.get("amount", 0) or 0
        per100 = {
            "calories":  nutrients.get(USDA_NUTRIENT_IDS["calories"], food["calories"]),
            "protein_g": nutrients.get(USDA_NUTRIENT_IDS["protein"],  food["protein_g"]),
            "carbs_g":   nutrients.get(USDA_NUTRIENT_IDS["carbs"],    food["carbs_g"]),
            "fat_g":     nutrients.get(USDA_NUTRIENT_IDS["fat"],      food["fat_g"]),
        }
    except Exception:
        per100 = {k: food[k] for k in ["calories", "protein_g", "carbs_g", "fat_g"]}

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
        user_id, food["fdc_id"], food["name"], meal_type,
        portion_g, scaled["calories"], scaled["protein_g"],
        scaled["carbs_g"], scaled["fat_g"], today,
    ))
    db.commit()
    cur.close()
    db.close()



def is_user_premium(user_id):
    db  = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("SELECT is_premium FROM users WHERE id=%s", (user_id,))
    row = cur.fetchone()
    cur.close()
    db.close()
    return bool(row["is_premium"]) if row else False

# ── Routes ───────────────────────────────────────────────────────────────

@app.route("/chat", methods=["POST"])
def chat():
    if "user_id" not in session:
        return {"error": "Unauthorized"}, 401

    if not validate_csrf():
        return {"error": "CSRF validation failed"}, 403

    data         = request.get_json(silent=True) or {}
    user_message = data.get("message", "").strip()
    page_context = data.get("page_context", "").strip() if data.get("page_context") else ""

    if not user_message or len(user_message) > 2000:
        return {"error": "Invalid message"}, 400

    user_id = session["user_id"]

    # ── Rate limit for free users ──────────────────────────────────────
    if not is_user_premium(user_id):
        db  = get_db()
        cur = db.cursor(dictionary=True)
        cur.execute("""
            SELECT COUNT(*) AS cnt FROM chat_messages
            WHERE user_id = %s
              AND role = 'user'
              AND created_at >= DATE_SUB(NOW(), INTERVAL 3 HOUR)
        """, (user_id,))
        count = cur.fetchone()["cnt"]
        cur.close()
        db.close()

        if count >= 10:
            return {
                "error": "rate_limited",
                "message": "You've used your 10 free messages for this 3-hour window. Upgrade to Pro for unlimited access."
            }, 429
    if "user_id" not in session:
        return {"error": "Unauthorized"}, 401
    if not validate_csrf():
        return {"error": "CSRF validation failed"}, 403

    data         = request.get_json(silent=True) or {}
    user_message = data.get("message", "").strip()
    page_context = data.get("page_context", "").strip() if data.get("page_context") else ""

    if not user_message or len(user_message) > 2000:
        return {"error": "Invalid message"}, 400

    user_id = session["user_id"]
    save_message(user_id, "user", user_message)

    history = get_chat_history(user_id, limit=18)
    system  = SYSTEM_PROMPT + get_user_context(user_id)

    if page_context:
        system += f"\n\n--- CURRENT PAGE CONTEXT ---\n{page_context}\n--- END PAGE CONTEXT ---"

    try:
        client   = OpenAI(api_key=OPENAI_API_KEY)
        response = client.chat.completions.create(
            model="gpt-4o",
            max_tokens=1024,
            messages=[
        {"role": "system", "content": system},
        *[{"role": m["role"], "content": m["content"]} for m in history],
    ]
        )
        raw_reply = response.choices[0].message.content
    except Exception as e:
        app.logger.error(f"OpenAI error: {e}")
        return {"error": "AI service unavailable"}, 503

    clean_reply, action = parse_action(raw_reply)
    if action:
        execute_action(action, user_id)

    save_message(user_id, "assistant", clean_reply)
    return {"reply": clean_reply}
       


@app.route("/chat/history")
def chat_history():
    if "user_id" not in session:
        return {"error": "Unauthorized"}, 401
    history = get_chat_history(session["user_id"], limit=20)
    return {"messages": history}
@app.route("/pricing")
def pricing_page():
    if "user_id" not in session:
        return redirect(url_for("login_page"))
    return render_template("pricing.html", email=session["email"])

@app.route("/chat/clear", methods=["POST"])
def chat_clear():
    if "user_id" not in session:
        return {"error": "Unauthorized"}, 401
    if not validate_csrf():
        return {"error": "CSRF"}, 403
    db = get_db()
    cur = db.cursor()
    cur.execute("DELETE FROM chat_messages WHERE user_id = %s", (session["user_id"],))
    db.commit()
    cur.close()
    db.close()
    return {"ok": True}


# ---------------------------------------------------------------------------
# Kroger API — product price lookup with token caching + fallback
# ---------------------------------------------------------------------------

KROGER_CLIENT_ID     = os.environ.get("KROGER_CLIENT_ID", "")
KROGER_CLIENT_SECRET = os.environ.get("KROGER_CLIENT_SECRET", "")
KROGER_TOKEN_URL     = "https://api.kroger.com/v1/connect/oauth2/token"
KROGER_PRODUCTS_URL  = "https://api.kroger.com/v1/products"

# In-memory token cache — avoids re-fetching on every request
_kroger_token_cache = {"token": None, "expires_at": 0}


def kroger_get_token():
    """
    Fetch a client_credentials token from Kroger.
    Caches in memory and reuses until 60s before expiry.
    """
    import time, base64
    now = time.time()
    if _kroger_token_cache["token"] and now < _kroger_token_cache["expires_at"]:
        return _kroger_token_cache["token"]

    credentials = base64.b64encode(
        f"{KROGER_CLIENT_ID}:{KROGER_CLIENT_SECRET}".encode()
    ).decode()

    try:
        resp = requests.post(KROGER_TOKEN_URL, headers={
            "Authorization": f"Basic {credentials}",
            "Content-Type":  "application/x-www-form-urlencoded",
        }, data={"grant_type": "client_credentials", "scope": "product.compact"},
        timeout=8)
        resp.raise_for_status()
        data = resp.json()
        _kroger_token_cache["token"]      = data["access_token"]
        _kroger_token_cache["expires_at"] = now + data.get("expires_in", 1800) - 60
        return data["access_token"]
    except Exception as e:
        app.logger.error(f"Kroger token error: {e}")
        return None


def kroger_get_price(ingredient_name):
    """
    Look up an ingredient on Kroger and return the best price found.
    Returns float price or None if not found / API unavailable.
    """
    token = kroger_get_token()
    if not token:
        return None

    try:
        resp = requests.get(KROGER_PRODUCTS_URL, headers={
            "Authorization": f"Bearer {token}",
            "Accept":        "application/json",
        }, params={
            "filter.term":       ingredient_name,
            "filter.limit":      5,
            "filter.fulfillment": "ais",  # available in store
        }, timeout=6)
        resp.raise_for_status()
        products = resp.json().get("data", [])

        # Find the first product that has a price
        for product in products:
            items = product.get("items", [])
            for item in items:
                price_info = item.get("price", {})
                regular    = price_info.get("regular")
                promo      = price_info.get("promo")
                price      = promo if promo and promo > 0 else regular
                if price and price > 0:
                    return round(float(price), 2)
    except Exception as e:
        app.logger.warning(f"Kroger price lookup failed for '{ingredient_name}': {e}")

    return None


def enrich_with_kroger_prices(ingredients):
    """
    Try Kroger price for each ingredient.
    Falls back to est_cost_usd if Kroger lookup fails.
    Adds 'kroger_price' and 'price_source' keys to each ingredient dict.
    """
    enriched = []
    for item in ingredients:
        kroger_price = kroger_get_price(item["name"])
        if kroger_price is not None:
            item = {**item,
                    "price_usd":    kroger_price,
                    "price_source": "Kroger",
                    "price_note":   f"Kroger: ${kroger_price:.2f}"}
        else:
            # Keep whatever estimate was already on the item
            item = {**item,
                    "price_source": "estimate",
                    "price_note":   item.get("price_note", f"~${item.get('price_usd', 0):.2f} est.")}
        enriched.append(item)
    return enriched


# ---------------------------------------------------------------------------
# Dashboard recipe cards
# ---------------------------------------------------------------------------

def get_random_recipes(n=3):
    """Pick n random recipes from the DB for the dashboard."""
    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("""
        SELECT id, name, category, health_rating, health_notes,
               est_cost_usd, ingredients
        FROM recipes
        ORDER BY RAND()
        LIMIT %s
    """, (n,))
    rows = cur.fetchall()
    cur.close()
    db.close()
    for r in rows:
        if isinstance(r["ingredients"], str):
            r["ingredients"] = json.loads(r["ingredients"])
    return rows


# ---------------------------------------------------------------------------

# Meal Planner — ingredient + price estimator (FR-07 / FR-08)

# ---------------------------------------------------------------------------

@app.route("/planner")

def planner_page():

    if "user_id" not in session:

        return redirect(url_for("login_page"))

    db = get_db()

    cur = db.cursor(dictionary=True)

    cur.execute("""

        SELECT id, dish_name, ingredients, created_at

        FROM meal_plans

        WHERE user_id = %s

        ORDER BY created_at DESC

        LIMIT 5

    """, (session["user_id"],))

    history = cur.fetchall()

    cur.close()

    db.close()

    # Parse JSON ingredients for each history item

    for h in history:

        if isinstance(h["ingredients"], str):

            h["ingredients"] = json.loads(h["ingredients"])

    return render_template("planner.html",

                           email=session["email"],

                           history=history)

@app.route("/planner/ingredients", methods=["POST"])

def planner_ingredients():

    """

    Takes a dish description, returns a structured ingredient list

    with quantity, unit, and estimated price via OpenAI.

    """

    if "user_id" not in session:

        return {"error": "Unauthorized"}, 401

    if not validate_csrf():

        return {"error": "CSRF"}, 403

    data = request.get_json(silent=True) or {}

    dish = data.get("dish", "").strip()

    if not dish or len(dish) > 300:

        return {"error": "Invalid input"}, 400

    prompt = f"""The user wants to make: "{dish}"

Return a JSON array of ingredients needed. Each item must have:

- "name": ingredient name (string)

- "quantity": numeric amount (number)

- "unit": unit of measurement like "g", "ml", "tbsp", "pcs", "cup" (string)

- "price_usd": realistic estimated US grocery store price in USD for that quantity (number, 2 decimal places)

- "price_note": brief note explaining the estimate e.g. "~$2.50 for a 500g pack" (string)

Rules:

- Be practical — use realistic supermarket quantities and prices (Walmart/Kroger level)

- Include ALL ingredients including basics like salt, oil, butter

- Return ONLY the raw JSON array, no markdown, no explanation, no code fences

- Aim for 6–14 ingredients depending on the dish

- Prices should reflect buying the smallest practical package size

Example format:

[{{"name":"spaghetti","quantity":200,"unit":"g","price_usd":1.50,"price_note":"~$1.50 for 500g pack"}},...]"""

    try:

        client   = OpenAI(api_key=OPENAI_API_KEY)

        response = client.chat.completions.create(

            model="gpt-4o",

            max_tokens=1200,

            temperature=0.3,

            messages=[

                {"role": "system", "content": "You are a helpful cooking assistant. Return only valid JSON arrays, nothing else."},

                {"role": "user",   "content": prompt}

            ]

        )

        raw = response.choices[0].message.content.strip()

        # Strip markdown fences if model includes them despite instructions

        raw = re.sub(r'^```[a-z]*\n?', '', raw)

        raw = re.sub(r'\n?```$', '', raw)

        ingredients = json.loads(raw)

        # Validate structure

        for item in ingredients:

            if not all(k in item for k in ["name", "quantity", "unit", "price_usd"]):

                raise ValueError("Missing fields")

    except (json.JSONDecodeError, ValueError) as e:

        app.logger.error(f"Planner parse error: {e} — raw: {raw[:200]}")

        return {"error": "Could not parse ingredient list. Please try again."}, 500

    except Exception as e:

        app.logger.error(f"Planner OpenAI error: {e}")

        return {"error": "AI service unavailable."}, 503

   # Enrich with Kroger prices (falls back to OpenAI estimates)

    ingredients = enrich_with_kroger_prices(ingredients)

    # Save to history with enriched prices

    db = get_db()

    cur = db.cursor()

    cur.execute("""

        INSERT INTO meal_plans (user_id, dish_name, ingredients)

        VALUES (%s, %s, %s)

    """, (session["user_id"], dish, json.dumps(ingredients)))

    db.commit()

    cur.close()

    db.close()

    return {"dish": dish, "ingredients": ingredients}

from water import water_bp
app.register_blueprint(water_bp)
from workout import workout_bp
app.register_blueprint(workout_bp)
from planner import planner_bp
app.register_blueprint(planner_bp)

@app.route("/toggle-premium", methods=["POST"])
def toggle_premium():
    if "user_id" not in session:
        return redirect(url_for("login_page"))
    if not validate_csrf():
        return "CSRF failed", 403

    db  = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("SELECT is_premium FROM users WHERE id=%s", (session["user_id"],))
    row = cur.fetchone()
    new_val = not bool(row["is_premium"])
    cur2 = db.cursor()
    cur2.execute("UPDATE users SET is_premium=%s WHERE id=%s",
                 (new_val, session["user_id"]))
    db.commit()
    cur.close()
    cur2.close()
    db.close()

    session["is_premium"] = new_val
    flash(f"Account set to {'Premium ✦' if new_val else 'Free'}.", "success")
    return redirect(request.referrer or url_for("dashboard"))


from notifications import notif_bp
app.register_blueprint(notif_bp)
from calendar_bp import calendar_bp
app.register_blueprint(calendar_bp)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
