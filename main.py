# main.py
from flask import Flask, jsonify
from flask_cors import CORS
import os
from werkzeug.utils import secure_filename

# import your blueprints
from auth import auth_bp
from dataset_manager import ds_bp
from nlp_extraction import nlp_bp

# constants
UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {"txt", "pdf", "csv", "json", "xml"}

# --- Flask setup ---
app = Flask(__name__)
CORS(app)  # allow cross-origin for Streamlit

# register blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(ds_bp)
app.register_blueprint(nlp_bp)

# ensure upload dir exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    """Check if uploaded file type is allowed."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

# --- optional base route ---
@app.route("/")
def home():
    return jsonify({
        "message": "KnowMap API is running",
        "routes": ["/api/auth/register", "/api/auth/login", "/api/datasets/upload", "/api/nlp/extract"]
    })

# --- entry point ---
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
