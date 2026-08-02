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
# Enable Qwen3 thinking mode (<think>...</think>). Off by default: for short
# tasks reasoning eats the whole token budget before the actual answer. Set
# ENABLE_THINKING=true to enable it for complex prompts.
ENABLE_THINKING = os.environ.get("ENABLE_THINKING", "false").lower() in ("1", "true", "yes")

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

    # The optional `local` flag defaults to True when omitted. It is accepted
    # for forward compatibility but is NOT branched on yet: the service always
    # calls the local GGUF model.
    local = bool(data.get("local", True))

    if llm is None:
        return jsonify({"error": "model is not loaded (MODEL_PATH is not set or invalid)"}), 503

    # Qwen3 supports a "/no_think" suffix that disables the reasoning block,
    # so the model answers directly (keeps short tasks within the token budget).
    user_text = text if ENABLE_THINKING else f"{text} /no_think"

    try:
        # Use the chat endpoint so the instruct model applies its built-in
        # chat template (e.g. Qwen3 <|im_start|>...<|im_end|>) instead of raw
        # text completion, which otherwise loops/hallucinates.
        output = llm.create_chat_completion(
            messages=[{"role": "user", "content": user_text}],
            max_tokens=MAX_TOKENS,
        )
    except Exception as exc:  # noqa: BLE001
        app.logger.error("Model inference failed: %s", exc)
        return jsonify({"error": "model inference failed"}), 500

    content = output["choices"][0]["message"]["content"]
    # Qwen3 emits a <think>...</think> reasoning block before the final
    # answer; drop everything up to and including </think>.
    if "</think>" in content:
        content = content.split("</think>", 1)[1]
    result = content.strip()
    app.logger.info("process: local=%s", local)
    return jsonify({"result": result}), 200


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "model_loaded": llm is not None}), 200
