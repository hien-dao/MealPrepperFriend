import os
import json
import mysql.connector
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from openai import OpenAI

planner_bp = Blueprint('planner', __name__)

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

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

@planner_bp.route("/planner")
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

    for h in history:
        if isinstance(h["ingredients"], str):
            h["ingredients"] = json.loads(h["ingredients"])

    return render_template("planner.html",
                           email=session["email"],
                           history=history)


@planner_bp.route("/planner/ingredients", methods=["POST"])
def planner_ingredients():
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
- Prices should reflect buying the smallest practical package size"""

    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
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
        raw = raw.replace("```json", "").replace("```", "").strip()
        ingredients = json.loads(raw)

        for item in ingredients:
            if not all(k in item for k in ["name", "quantity", "unit", "price_usd"]):
                raise ValueError("Missing fields")

    except (json.JSONDecodeError, ValueError) as e:
        return {"error": "Could not parse ingredient list. Please try again."}, 500
    except Exception as e:
        return {"error": "AI service unavailable."}, 503

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


@planner_bp.route("/planner/recipe", methods=["POST"])
def planner_recipe():
    if "user_id" not in session:
        return {"error": "Unauthorized"}, 401
    if not validate_csrf():
        return {"error": "CSRF"}, 403

    data        = request.get_json(silent=True) or {}
    dish        = data.get("dish", "").strip()
    ingredients = data.get("ingredients", "").strip()

    if not dish or not ingredients:
        return {"error": "Missing data"}, 400

    prompt = (
        f"Write a clear, practical recipe for {dish} using these ingredients: {ingredients}. "
        "Format: brief intro (1 sentence), then numbered steps. "
        "Keep it concise — under 300 words. No markdown, no headers, plain text only."
    )

    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=400,
            temperature=0.7,
            messages=[{"role": "user", "content": prompt}]
        )
        recipe = response.choices[0].message.content.strip()
    except Exception as e:
        return {"error": "AI service unavailable"}, 503

    return {"recipe": recipe}


@planner_bp.route("/planner/save-to-calendar", methods=["POST"])
def save_to_calendar():
    if "user_id" not in session:
        return {"error": "Unauthorized"}, 401

    data        = request.get_json(silent=True) or {}
    dish        = data.get("dish", "").strip()
    ingredients = data.get("ingredients", [])
    recipe_text = data.get("recipe_text", "").strip()
    plan_date   = data.get("plan_date", "").strip()

    if not dish or not plan_date:
        return {"error": "Missing dish or date"}, 400

    db  = get_db()
    cur = db.cursor()
    cur.execute("""
        INSERT INTO calendar_recipes (user_id, plan_date, dish_name, ingredients, recipe_text)
        VALUES (%s, %s, %s, %s, %s)
    """, (session["user_id"], plan_date, dish,
          json.dumps(ingredients), recipe_text or None))
    db.commit()
    cur.close()
    db.close()

    return {"ok": True}
