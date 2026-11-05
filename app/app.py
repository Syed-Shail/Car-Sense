from pathlib import Path

from flask import Flask, jsonify, send_from_directory
from .routes import api

FRONTEND_DIST = Path(__file__).resolve().parents[1] / "web" / "dist"
app = Flask(__name__, static_folder=str(FRONTEND_DIST), static_url_path="")

app.register_blueprint(api)


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


@app.get("/")
def frontend():
    index_file = FRONTEND_DIST / "index.html"
    if not index_file.is_file():
        return jsonify({"error": "Frontend build not found. Run `npm run build` in web/."}), 404
    return send_from_directory(app.static_folder, "index.html")

if __name__ == "__main__":
    app.run(debug=False)
