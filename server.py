import os
import secrets
import psycopg2
import jwt
from datetime import datetime, timedelta, timezone
from functools import wraps
from flask import Flask, request, jsonify, send_from_directory

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, static_folder=BASE_DIR, static_url_path="")

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin")
JWT_SECRET = os.environ.get("JWT_SECRET", secrets.token_hex(32))

def get_db():
    return psycopg2.connect(os.environ["DATABASE_URL"])

def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.cookies.get("admin_token")
        if not token:
            return jsonify({"error": "未授權"}), 401
        try:
            jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        except jwt.InvalidTokenError:
            return jsonify({"error": "未授權"}), 401
        return f(*args, **kwargs)
    return decorated

@app.route("/")
def index():
    return send_from_directory(BASE_DIR, "index.html")

@app.route("/admin")
def admin_page():
    token = request.cookies.get("admin_token")
    try:
        jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return send_from_directory(BASE_DIR, "admin.html")
    except Exception:
        return send_from_directory(BASE_DIR, "admin-login.html")

@app.route("/<path:filename>")
def static_files(filename):
    return send_from_directory(BASE_DIR, filename)

@app.route("/api/admin/login", methods=["POST"])
def admin_login():
    data = request.get_json()
    if data.get("password") != ADMIN_PASSWORD:
        return jsonify({"error": "密碼錯誤"}), 401
    token = jwt.encode(
        {"admin": True, "exp": datetime.now(timezone.utc) + timedelta(hours=8)},
        JWT_SECRET, algorithm="HS256"
    )
    resp = jsonify({"success": True})
    resp.set_cookie("admin_token", token, httponly=True, samesite="Lax", secure=True)
    return resp

@app.route("/api/admin/logout", methods=["POST"])
def admin_logout():
    resp = jsonify({"success": True})
    resp.delete_cookie("admin_token")
    return resp

@app.route("/api/admin/check")
def admin_check():
    token = request.cookies.get("admin_token")
    try:
        jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return jsonify({"logged_in": True})
    except Exception:
        return jsonify({"logged_in": False})

@app.route("/api/reviews", methods=["GET"])
def get_reviews():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, content, rating, created_at FROM reviews WHERE visible = TRUE ORDER BY created_at DESC")
    rows = cur.fetchall()
    cur.close(); conn.close()
    return jsonify([{"id": r[0], "content": r[1], "rating": r[2], "created_at": r[3].strftime("%Y-%m-%d")} for r in rows])

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
    cur.execute("INSERT INTO reviews (content, rating) VALUES (%s, %s) RETURNING id", (content, rating))
    new_id = cur.fetchone()[0]
    conn.commit(); cur.close(); conn.close()
    return jsonify({"success": True, "id": new_id}), 201

@app.route("/api/admin/reviews", methods=["GET"])
@admin_required
def admin_get_reviews():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, content, rating, visible, created_at FROM reviews ORDER BY created_at DESC")
    rows = cur.fetchall()
    cur.close(); conn.close()
    return jsonify([{"id": r[0], "content": r[1], "rating": r[2], "visible": r[3], "created_at": r[4].strftime("%Y-%m-%d %H:%M")} for r in rows])

@app.route("/api/admin/reviews/<int:review_id>", methods=["DELETE"])
@admin_required
def delete_review(review_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM reviews WHERE id = %s", (review_id,))
    conn.commit(); cur.close(); conn.close()
    return jsonify({"success": True})

@app.route("/api/admin/reviews/<int:review_id>/toggle", methods=["PATCH"])
@admin_required
def toggle_review(review_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE reviews SET visible = NOT visible WHERE id = %s RETURNING visible", (review_id,))
    row = cur.fetchone()
    conn.commit(); cur.close(); conn.close()
    if row is None:
        return jsonify({"error": "找不到評論"}), 404
    return jsonify({"success": True, "visible": row[0]})
