# dataset_manager.py
import os
from flask import Blueprint, request, jsonify

# Blueprint registered under /api/datasets
ds_bp = Blueprint("datasets", __name__, url_prefix="/api/datasets")

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@ds_bp.route("/upload", methods=["POST"])
def upload_file():
    """Handle dataset uploads (text/csv/json/zip)."""
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "Empty filename"}), 400

    save_path = os.path.join(UPLOAD_DIR, file.filename)
    try:
        file.save(save_path)
        return jsonify({
            "message": "File uploaded successfully",
            "path": save_path
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
