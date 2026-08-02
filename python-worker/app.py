import os

from flask import Flask, request, jsonify

app = Flask(__name__)
# Return non-ASCII (e.g. Cyrillic) as-is instead of \uXXXX escapes.
app.json.ensure_ascii = False

# Path to the local GGUF model is read from the environment variable.
# If it is not set, the model is not loaded and /process returns 503.
MODEL_PATH = os.environ.get("MODEL_PATH", "")

# Default generation parameters.
MAX_TOKENS = int(os.environ.get("MAX_TOKENS", "256"))
N_CTX = int(os.environ.get("N_CTX", "2048"))
# Number of CPU threads for generation. 0 = auto (all physical cores) — usually
# the optimum for inference, since token generation does not parallelize well.
N_THREADS = int(os.environ.get("N_THREADS", "0"))

# The model is loaded once at application startup (module level) so it is not
# re-initialized on every request. Gunicorn runs with --workers 1, so only a
# single copy of the model lives in memory.
llm = None
if MODEL_PATH:
    try:
        from llama_cpp import Llama

        app.logger.info("Loading GGUF model from %s ...", MODEL_PATH)
        llm = Llama(
            model_path=MODEL_PATH,
            n_ctx=N_CTX,
            n_threads=N_THREADS or None,  # None -> auto (all physical cores)
            verbose=False,
        )
        app.logger.info("Model loaded successfully")
    except Exception as exc:  # noqa: BLE001 - log and continue
        app.logger.error("Failed to load model from %s: %s", MODEL_PATH, exc)
        llm = None
else:
    app.logger.warning("MODEL_PATH is not set; /process will return 503")


@app.route("/process", methods=["POST"])
def process():
    data = request.get_json(silent=True)

    if not data:
        return jsonify({"error": "invalid json"}), 400

    text = data.get("text")
    if not text:
        return jsonify({"error": "text is required"}), 400

    # The local flag is present in the request schema but is NOT used yet:
    # the service always calls the local GGUF model and returns its answer.
    local = bool(data.get("local", False))

    if llm is None:
        return jsonify({"error": "model is not loaded (MODEL_PATH is not set or invalid)"}), 503

    try:
        # Use the chat endpoint so the instruct model applies its built-in
        # chat template (e.g. Qwen3 <|im_start|>...<|im_end|>) instead of raw
        # text completion, which otherwise loops/hallucinates.
        output = llm.create_chat_completion(
            messages=[{"role": "user", "content": text}],
            max_tokens=MAX_TOKENS,
        )
    except Exception as exc:  # noqa: BLE001
        app.logger.error("Model inference failed: %s", exc)
        return jsonify({"error": "model inference failed"}), 500

    result = output["choices"][0]["message"]["content"].strip()
    return jsonify({"result": result, "local": local}), 200


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "model_loaded": llm is not None}), 200
