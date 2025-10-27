from flask import Flask
from flask_cors import CORS
import os

from auth import auth_bp
from dataset_manager import ds_bp

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'supersecretkey'
    app.config['UPLOAD_DIR'] = os.path.join(os.getcwd(), 'uploads')
    os.makedirs(app.config['UPLOAD_DIR'], exist_ok=True)

    CORS(app)
    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(ds_bp, url_prefix="/api/datasets")
    return app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
