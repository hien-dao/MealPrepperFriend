import os
import json
import uuid
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, send_from_directory
from werkzeug.utils import secure_filename

forum_bp = Blueprint('forum', __name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

UPLOAD_FOLDER      = os.path.join(os.path.dirname(__file__), 'static', 'uploads', 'forum')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
MAX_IMAGE_MB       = 5

FORUM_CATEGORIES = ['recipe', 'nutrition', 'fitness', 'general', 'question', 'tips']
CATEGORY_LABELS  = {
    'recipe':    '🍽️ Recipe',
    'nutrition': '🥗 Nutrition',
    'fitness':   '💪 Fitness',
    'general':   '💬 General',
    'question':  '❓ Question',
    'tips':      '💡 Tips',
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_db():
    import mysql.connector
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
    session_token = session.get("csrf_token")
    return form_token and session_token and form_token == session_token
'''

def allowed_image(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def save_forum_image(file):
    """
    Save an uploaded image to disk with a UUID filename.
    Returns the relative URL path for storing in DB, or None on failure.
    """
    if not file or not file.filename:
        return None
    if not allowed_image(file.filename):
        return None
    ext      = file.filename.rsplit('.', 1)[1].lower()
    filename = f"{uuid.uuid4().hex}.{ext}"
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    file.save(os.path.join(UPLOAD_FOLDER, filename))
    return f"/forum/uploads/{filename}"


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@forum_bp.route("/forum/uploads/<filename>")
def forum_image(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)


@forum_bp.route("/forum")
def forum():
    category = request.args.get("category", "all")
    page     = max(int(request.args.get("page", 1)), 1)
    per_page = 15
    offset   = (page - 1) * per_page
    user_id  = session.get("user_id")

    db  = get_db()
    cur = db.cursor(dictionary=True)

    where  = "WHERE 1=1"
    params = []
    if category != "all" and category in FORUM_CATEGORIES:
        where += " AND fp.category = %s"
        params.append(category)

    cur.execute(f"""
        SELECT
            fp.id, fp.title, fp.body, fp.category, fp.post_type,
            fp.image_path, fp.upvotes, fp.created_at,
            fp.recipe_calories, fp.recipe_protein_g,
            fp.recipe_carbs_g, fp.recipe_fat_g,
            u.email,
            (SELECT COUNT(*) FROM forum_comments fc WHERE fc.post_id = fp.id) AS comment_count,
            (SELECT COUNT(*) FROM forum_upvotes fu
             WHERE fu.post_id = fp.id AND fu.user_id = %s) AS user_upvoted
        FROM forum_posts fp
        JOIN users u ON u.id = fp.user_id
        {where}
        ORDER BY fp.created_at DESC
        LIMIT %s OFFSET %s
    """, [user_id or 0] + params + [per_page, offset])
    posts = cur.fetchall()

    cur.execute(f"SELECT COUNT(*) AS total FROM forum_posts fp {where}", params)
    total = cur.fetchone()["total"]
    pages = (total + per_page - 1) // per_page

    cur.close()
    db.close()

    return render_template("forum.html",
                           posts=posts,
                           category=category,
                           page=page,
                           pages=pages,
                           total=total,
                           category_labels=CATEGORY_LABELS,
                           email=session.get("email"),
                           logged_in=bool(user_id))


@forum_bp.route("/forum/post", methods=["POST"])
def forum_new_post():
    if "user_id" not in session:
        flash("Please log in to post.", "error")
        return redirect(url_for("login_page"))
    if not validate_csrf():
        return True

    title     = request.form.get("title", "").strip()
    body      = request.form.get("body", "").strip()
    category  = request.form.get("category", "general").strip()
    post_type = request.form.get("post_type", "general").strip()

    if not title or not body:
        flash("Title and body are required.", "error")
        return redirect(url_for("forum.forum"))
    if len(title) > 255 or len(body) > 10000:
        flash("Title or body too long.", "error")
        return redirect(url_for("forum.forum"))
    if category not in FORUM_CATEGORIES:
        category = "general"
    if post_type not in ("general", "recipe"):
        post_type = "general"

    image_path = None
    if "image" in request.files:
        image_path = save_forum_image(request.files["image"])

    recipe_calories    = None
    recipe_protein_g   = None
    recipe_carbs_g     = None
    recipe_fat_g       = None
    recipe_ingredients = None

    if post_type == "recipe":
        try:
            recipe_calories  = int(request.form.get("recipe_calories") or 0) or None
            recipe_protein_g = float(request.form.get("recipe_protein_g") or 0) or None
            recipe_carbs_g   = float(request.form.get("recipe_carbs_g") or 0) or None
            recipe_fat_g     = float(request.form.get("recipe_fat_g") or 0) or None
        except ValueError:
            pass
        raw_ingredients = request.form.get("recipe_ingredients", "").strip()
        if raw_ingredients:
            items = [i.strip() for i in raw_ingredients.splitlines() if i.strip()]
            recipe_ingredients = json.dumps(items) if items else None

    db  = get_db()
    cur = db.cursor()
    cur.execute("""
        INSERT INTO forum_posts
            (user_id, category, post_type, title, body, image_path,
             recipe_calories, recipe_protein_g, recipe_carbs_g, recipe_fat_g,
             recipe_ingredients)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (session["user_id"], category, post_type, title, body, image_path,
          recipe_calories, recipe_protein_g, recipe_carbs_g, recipe_fat_g,
          recipe_ingredients))
    post_id = cur.lastrowid
    db.commit()
    cur.close()
    db.close()

    flash("Post published.", "success")
    return redirect(url_for("forum.forum_post", post_id=post_id))


@forum_bp.route("/forum/<int:post_id>")
def forum_post(post_id):
    user_id = session.get("user_id")

    db  = get_db()
    cur = db.cursor(dictionary=True)

    cur.execute("""
        SELECT fp.*, u.email,
               (SELECT COUNT(*) FROM forum_upvotes fu
                WHERE fu.post_id = fp.id AND fu.user_id = %s) AS user_upvoted
        FROM forum_posts fp
        JOIN users u ON u.id = fp.user_id
        WHERE fp.id = %s
    """, (user_id or 0, post_id))
    post = cur.fetchone()

    if not post:
        cur.close()
        db.close()
        flash("Post not found.", "error")
        return redirect(url_for("forum.forum"))

    if post["recipe_ingredients"] and isinstance(post["recipe_ingredients"], str):
        post["recipe_ingredients"] = json.loads(post["recipe_ingredients"])

    cur.execute("""
        SELECT fc.id, fc.body, fc.parent_id, fc.created_at, fc.user_id, u.email
        FROM forum_comments fc
        JOIN users u ON u.id = fc.user_id
        WHERE fc.post_id = %s
        ORDER BY fc.created_at ASC
    """, (post_id,))
    all_comments = cur.fetchall()
    cur.close()
    db.close()

    top_level = [c for c in all_comments if c["parent_id"] is None]
    replies   = {}
    for c in all_comments:
        if c["parent_id"] is not None:
            replies.setdefault(c["parent_id"], []).append(c)

    return render_template("forum_post.html",
                           post=post,
                           top_level=top_level,
                           replies=replies,
                           category_labels=CATEGORY_LABELS,
                           email=session.get("email"),
                           logged_in=bool(user_id),
                           current_user_id=user_id)


@forum_bp.route("/forum/<int:post_id>/comment", methods=["POST"])
def forum_comment(post_id):
    if "user_id" not in session:
        flash("Please log in to comment.", "error")
        return redirect(url_for("forum.forum_post", post_id=post_id))
    if not validate_csrf():
        return "CSRF failed", 403

    body      = request.form.get("body", "").strip()
    parent_id = request.form.get("parent_id", None)

    if not body or len(body) > 5000:
        flash("Comment is required and must be under 5000 characters.", "error")
        return redirect(url_for("forum.forum_post", post_id=post_id))

    parent_id = int(parent_id) if parent_id and str(parent_id).isdigit() else None

    db  = get_db()
    cur = db.cursor()
    cur.execute("""
        INSERT INTO forum_comments (post_id, user_id, parent_id, body)
        VALUES (%s, %s, %s, %s)
    """, (post_id, session["user_id"], parent_id, body))
    db.commit()
    cur.close()
    db.close()

    return redirect(url_for("forum.forum_post", post_id=post_id) + "#comments")


@forum_bp.route("/forum/<int:post_id>/upvote", methods=["POST"])
def forum_upvote(post_id):
    if "user_id" not in session:
        return {"error": "Login required"}, 401
    if not validate_csrf():
        return {"error": "CSRF"}, 403

    db  = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("SELECT 1 FROM forum_upvotes WHERE user_id=%s AND post_id=%s",
                (session["user_id"], post_id))
    already = cur.fetchone()

    cur2 = db.cursor()
    if already:
        cur2.execute("DELETE FROM forum_upvotes WHERE user_id=%s AND post_id=%s",
                     (session["user_id"], post_id))
        cur2.execute("UPDATE forum_posts SET upvotes=GREATEST(upvotes-1,0) WHERE id=%s", (post_id,))
        upvoted = False
    else:
        cur2.execute("INSERT INTO forum_upvotes (user_id, post_id) VALUES (%s,%s)",
                     (session["user_id"], post_id))
        cur2.execute("UPDATE forum_posts SET upvotes=upvotes+1 WHERE id=%s", (post_id,))
        upvoted = True

    db.commit()
    cur.execute("SELECT upvotes FROM forum_posts WHERE id=%s", (post_id,))
    new_count = cur.fetchone()["upvotes"]
    cur.close()
    cur2.close()
    db.close()

    return {"upvoted": upvoted, "upvotes": new_count}


@forum_bp.route("/forum/<int:post_id>/delete", methods=["POST"])
def forum_delete_post(post_id):
    if "user_id" not in session:
        return redirect(url_for("login_page"))
    if not validate_csrf():
        return "CSRF failed", 403

    db  = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("SELECT image_path FROM forum_posts WHERE id=%s AND user_id=%s",
                (post_id, session["user_id"]))
    post = cur.fetchone()

    if post:
        cur2 = db.cursor()
        cur2.execute("DELETE FROM forum_posts WHERE id=%s AND user_id=%s",
                     (post_id, session["user_id"]))
        db.commit()
        cur2.close()
        if post["image_path"]:
            fname     = post["image_path"].rsplit("/", 1)[-1]
            disk_path = os.path.join(UPLOAD_FOLDER, fname)
            if os.path.exists(disk_path):
                os.remove(disk_path)

    cur.close()
    db.close()

    flash("Post deleted.", "success")
    return redirect(url_for("forum.forum"))
