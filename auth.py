import sqlite3
from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import secrets

auth_bp = Blueprint("auth", __name__)

def get_db():
    conn = sqlite3.connect("database.db")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            email TEXT PRIMARY KEY,
            password TEXT
        )
    """)
    return conn

@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json()
    email = data["email"]
    password = generate_password_hash(data["password"])

    conn = get_db()
    try:
        conn.execute("INSERT INTO users (email, password) VALUES (?, ?)", (email, password))
        conn.commit()
        return jsonify({"message": "User registered successfully!"}), 201
    except:
        return jsonify({"error": "User already exists!"}), 400
    finally:
        conn.close()

@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    email = data["email"]
    password = data["password"]

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT password FROM users WHERE email=?", (email,))
    row = cur.fetchone()
    conn.close()

    if row and check_password_hash(row[0], password):
        token = secrets.token_hex(16)
        return jsonify({"message": "Login successful!", "token": token}), 200
    else:
        return jsonify({"error": "Invalid credentials!"}), 401
