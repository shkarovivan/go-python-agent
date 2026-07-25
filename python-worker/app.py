from flask import Flask, request, jsonify

app = Flask(__name__)


@app.route("/process", methods=["POST"])
def process():
    data = request.get_json(silent=True)

    if not data:
        return jsonify({"error": "invalid json"}), 400

    text = data.get("text")
    if not text:
        return jsonify({"error": "text is required"}), 400

    result = text * 2
    return jsonify({"result": result}), 200


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200
