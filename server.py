import os
import secrets
import psycopg2
from flask import Flask, request, jsonify, send_from_directory, session, redirect, url_for

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__, static_folder=BASE_DIR, static_url_path="")
app.secret_key = os.environ.get("FLASK_SECRET_KEY", secrets.token_hex(32))

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin")

def get_db():
    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        raise RuntimeError("DATABASE_URL 未設定")
    if "sslmode" not in db_url:
        connector = "&" if "?" in db_url else "?"
        db_url += connector + "sslmode=require"
    return psycopg2.connect(db_url)

def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return jsonify({"error": "未授權"}), 401
        return f(*args, **kwargs)
    return decorated

# --- Static pages ---

@app.route("/")
def index():
    return send_from_directory(BASE_DIR, "index.html")

@app.route("/admin")
def admin_page():
    if not session.get("admin_logged_in"):
        return send_from_directory(BASE_DIR, "admin-login.html")
    return send_from_directory(BASE_DIR, "admin.html")

@app.route("/<path:filename>")
def static_files(filename):
    return send_from_directory(BASE_DIR, filename)

# --- Auth ---

@app.route("/api/admin/login", methods=["POST"])
def admin_login():
    data = request.get_json()
    if data.get("password") == ADMIN_PASSWORD:
        session["admin_logged_in"] = True
        return jsonify({"success": True})
    return jsonify({"error": "密碼錯誤"}), 401

@app.route("/api/admin/logout", methods=["POST"])
def admin_logout():
    session.pop("admin_logged_in", None)
    return jsonify({"success": True})

@app.route("/api/admin/check")
def admin_check():
    return jsonify({"logged_in": bool(session.get("admin_logged_in"))})

# --- Public reviews API ---

@app.route("/api/reviews", methods=["GET"])
def get_reviews():
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, content, rating, created_at FROM reviews WHERE visible = TRUE ORDER BY created_at DESC"
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    reviews = [
        {
            "id": r[0],
            "content": r[1],
            "rating": r[2],
            "created_at": r[3].strftime("%Y-%m-%d"),
        }
        for r in rows
    ]
    return jsonify(reviews)

@app.route("/api/reviews", methods=["POST"])
def add_review():
    data = request.get_json()
    content = (data.get("content") or "").strip()
    rating = data.get("rating")

    if not content:
        return jsonify({"error": "請填寫評論內容"}), 400
    if rating is None or not isinstance(rating, int) or not (1 <= rating <= 5):
        return jsonify({"error": "請選擇評分 (1-5)"}), 400

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO reviews (content, rating) VALUES (%s, %s) RETURNING id",
        (content, rating),
    )
    new_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({"success": True, "id": new_id}), 201

# --- Admin reviews API ---

@app.route("/api/admin/reviews", methods=["GET"])
@admin_required
def admin_get_reviews():
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, content, rating, visible, created_at FROM reviews ORDER BY created_at DESC"
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    reviews = [
        {
            "id": r[0],
            "content": r[1],
            "rating": r[2],
            "visible": r[3],
            "created_at": r[4].strftime("%Y-%m-%d %H:%M"),
        }
        for r in rows
    ]
    return jsonify(reviews)

@app.route("/api/admin/reviews/<int:review_id>", methods=["DELETE"])
@admin_required
def delete_review(review_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM reviews WHERE id = %s", (review_id,))
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({"success": True})

@app.route("/api/admin/reviews/<int:review_id>/toggle", methods=["PATCH"])
@admin_required
def toggle_review(review_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "UPDATE reviews SET visible = NOT visible WHERE id = %s RETURNING visible",
        (review_id,)
    )
    row = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    if row is None:
        return jsonify({"error": "找不到評論"}), 404
    return jsonify({"success": True, "visible": row[0]})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
