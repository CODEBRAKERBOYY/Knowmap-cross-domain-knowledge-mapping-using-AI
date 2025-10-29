# auth.py
import sqlite3
from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import secrets
import os

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

DB_PATH = "database.db"

def get_db():
    """Ensure the SQLite users table exists and return a connection."""
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            email TEXT PRIMARY KEY,
            password TEXT NOT NULL
        )
    """)
    return conn


@auth_bp.route("/register", methods=["POST"])
def register():
    """Register a new user with hashed password."""
    data = request.get_json(silent=True) or {}
    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"error": "Email and password required"}), 400

    conn = get_db()
    try:
        hashed = generate_password_hash(password)
        conn.execute("INSERT INTO users (email, password) VALUES (?, ?)", (email, hashed))
        conn.commit()
        return jsonify({"message": "User registered successfully!"}), 201
    except sqlite3.IntegrityError:
        return jsonify({"error": "User already exists!"}), 400
    finally:
        conn.close()


@auth_bp.route("/login", methods=["POST"])
def login():
    """Validate user and return a temporary token."""
    data = request.get_json(silent=True) or {}
    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"error": "Email and password required"}), 400

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
