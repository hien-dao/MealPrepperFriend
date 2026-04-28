import os
import json
import mysql.connector
from datetime import date
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from openai import OpenAI

workout_bp = Blueprint('workout', __name__)

# ---------------------------------------------------------------------------
# Helpers
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
# Routes
# ---------------------------------------------------------------------------

@workout_bp.route("/workout")
def workout_page():
    if "user_id" not in session:
        return redirect(url_for("login_page"))

    user_id = session["user_id"]
    db      = get_db()
    cur     = db.cursor(dictionary=True)

    cur.execute("""
        SELECT ws.id, ws.session_date, ws.name, ws.notes,
               ws.calories_burned,
               COUNT(we.id) AS exercise_count
        FROM workout_sessions ws
        LEFT JOIN workout_exercises we ON we.session_id = ws.id
        WHERE ws.user_id = %s
        GROUP BY ws.id
        ORDER BY ws.session_date DESC
        LIMIT 20
    """, (user_id,))
    sessions = cur.fetchall()
    cur.close()
    db.close()

    return render_template("workout.html",
                           email=session["email"],
                           sessions=sessions,
                           today=date.today().isoformat())


@workout_bp.route("/workout/session", methods=["POST"])
def workout_new_session():
    if "user_id" not in session:
        return redirect(url_for("login_page"))
    if not validate_csrf():
        return "CSRF failed", 403

    name         = request.form.get("name", "").strip() or "Workout"
    notes        = request.form.get("notes", "").strip()
    session_date = request.form.get("session_date", date.today().isoformat())

    db  = get_db()
    cur = db.cursor()
    cur.execute("""
        INSERT INTO workout_sessions (user_id, session_date, name, notes)
        VALUES (%s, %s, %s, %s)
    """, (session["user_id"], session_date, name, notes or None))
    session_id = cur.lastrowid
    db.commit()
    cur.close()
    db.close()

    return redirect(url_for("workout.workout_session", session_id=session_id))


@workout_bp.route("/workout/session/<int:session_id>")
def workout_session(session_id):
    if "user_id" not in session:
        return redirect(url_for("login_page"))

    user_id = session["user_id"]
    db      = get_db()
    cur     = db.cursor(dictionary=True)

    cur.execute("""
        SELECT * FROM workout_sessions WHERE id=%s AND user_id=%s
    """, (session_id, user_id))
    ws = cur.fetchone()

    if not ws:
        cur.close()
        db.close()
        flash("Session not found.", "error")
        return redirect(url_for("workout.workout_page"))

    cur.execute("""
        SELECT * FROM workout_exercises WHERE session_id=%s ORDER BY id ASC
    """, (session_id,))
    exercises = cur.fetchall()
    cur.close()
    db.close()

    return render_template("workout_session.html",
                           email=session["email"],
                           ws=ws,
                           exercises=exercises)


@workout_bp.route("/workout/session/<int:session_id>/exercise", methods=["POST"])
def workout_add_exercise(session_id):
    if "user_id" not in session:
        return redirect(url_for("login_page"))
    if not validate_csrf():
        return "CSRF failed", 403

    db  = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("SELECT id FROM workout_sessions WHERE id=%s AND user_id=%s",
                (session_id, session["user_id"]))
    if not cur.fetchone():
        cur.close()
        db.close()
        return "Unauthorized", 403

    name          = request.form.get("exercise_name", "").strip()
    exercise_type = request.form.get("exercise_type", "strength")

    if not name:
        flash("Exercise name required.", "error")
        return redirect(url_for("workout.workout_session", session_id=session_id))

    def intval(key):
        try:   return int(request.form.get(key) or 0) or None
        except: return None

    def floatval(key):
        try:   return float(request.form.get(key) or 0) or None
        except: return None

    cur2 = db.cursor()
    cur2.execute("""
        INSERT INTO workout_exercises
            (session_id, exercise_name, exercise_type,
             sets, reps, weight_kg, duration_minutes, distance_km)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
    """, (
        session_id, name, exercise_type,
        intval("sets"), intval("reps"), floatval("weight_kg"),
        intval("duration_minutes"), floatval("distance_km"),
    ))
    db.commit()
    cur.close()
    cur2.close()
    db.close()

    return redirect(url_for("workout.workout_session", session_id=session_id))


@workout_bp.route("/workout/session/<int:session_id>/calculate", methods=["POST"])
def workout_calculate_calories(session_id):
    if "user_id" not in session:
        return {"error": "Unauthorized"}, 401
    if not validate_csrf():
        return {"error": "CSRF"}, 403

    user_id = session["user_id"]
    db      = get_db()
    cur     = db.cursor(dictionary=True)

    cur.execute("SELECT id FROM workout_sessions WHERE id=%s AND user_id=%s",
                (session_id, user_id))
    if not cur.fetchone():
        cur.close()
        db.close()
        return {"error": "Not found"}, 404

    cur.execute("SELECT * FROM workout_exercises WHERE session_id=%s", (session_id,))
    exercises = cur.fetchall()

    if not exercises:
        cur.close()
        db.close()
        return {"error": "No exercises to calculate"}, 400

    # Build compact prompt — one line per exercise, minimal tokens
    lines = []
    for ex in exercises:
        if ex["exercise_type"] == "strength" and (ex["sets"] or ex["weight_kg"]):
            lines.append(
                f"{ex['exercise_name']}: {ex['sets'] or 0}x{ex['reps'] or 0}"
                f" @ {ex['weight_kg'] or 0}kg"
            )
        elif ex["exercise_type"] == "cardio" and (ex["duration_minutes"] or ex["distance_km"]):
            lines.append(
                f"{ex['exercise_name']}: {ex['duration_minutes'] or 0}min"
                f" {ex['distance_km'] or 0}km"
            )
        else:
            # Fallback — name only, model will estimate from context
            lines.append(ex["exercise_name"])

    prompt = (
        "Estimate calories burned for each exercise. "
        "Assume 75kg person. Return ONLY a JSON object: "
        "{\"total\": <int>, \"exercises\": [<int>, ...]} "
        "in the same order as input. No explanation.\n\n"
        + "\n".join(lines)
    )

    try:
        client   = OpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=120,
            temperature=0,
            messages=[{"role": "user", "content": prompt}]
        )
        raw  = response.choices[0].message.content.strip()
        raw  = raw.replace("```json", "").replace("```", "").strip()
        data = json.loads(raw)
        total        = int(data["total"])
        per_exercise = data["exercises"]
    except Exception as e:
        cur.close()
        db.close()
        return {"error": f"AI error: {str(e)}"}, 503

    # Save total to session
    cur2 = db.cursor()
    cur2.execute("""
        UPDATE workout_sessions
        SET calories_burned=%s, calories_calculated_at=NOW()
        WHERE id=%s
    """, (total, session_id))

    # Save per-exercise estimates
    for i, ex in enumerate(exercises):
        cal = per_exercise[i] if i < len(per_exercise) else 0
        cur2.execute(
            "UPDATE workout_exercises SET calories_burned=%s WHERE id=%s",
            (cal, ex["id"])
        )

    db.commit()
    cur.close()
    cur2.close()
    db.close()

    return {"total": total, "per_exercise": per_exercise}


@workout_bp.route("/workout/session/<int:session_id>/delete", methods=["POST"])
def workout_delete_session(session_id):
    if "user_id" not in session:
        return redirect(url_for("login_page"))
    if not validate_csrf():
        return "CSRF failed", 403

    db  = get_db()
    cur = db.cursor()
    cur.execute("DELETE FROM workout_sessions WHERE id=%s AND user_id=%s",
                (session_id, session["user_id"]))
    db.commit()
    cur.close()
    db.close()

    flash("Session deleted.", "success")
    return redirect(url_for("workout.workout_page"))
