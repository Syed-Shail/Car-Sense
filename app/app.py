from flask import Flask, jsonify
from .routes import api

app = Flask(__name__)

app.register_blueprint(api)


@app.get("/health")
def health():
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    app.run(debug=False)
