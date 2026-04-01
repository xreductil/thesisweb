import os
import psycopg2
from flask import Flask, request, jsonify, send_from_directory

app = Flask(__name__, static_folder=".", static_url_path="")

def get_db():
    return psycopg2.connect(os.environ["DATABASE_URL"])

@app.route("/")
def index():
    return send_from_directory(".", "index.html")

@app.route("/<path:filename>")
def static_files(filename):
    return send_from_directory(".", filename)

@app.route("/api/reviews", methods=["GET"])
def get_reviews():
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, content, rating, created_at FROM reviews ORDER BY created_at DESC"
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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
