"""
app.py — Flask application entry point.

Exposes REST/SSE endpoints consumed by the single-page chat UI.
"""

from __future__ import annotations

import functools

import ollama
from flask import Flask, Response, jsonify, render_template, request, stream_with_context

import chat_engine
import history
from config import config

app = Flask(__name__)
app.secret_key = config.flask_secret_key

# Initialise SQLite schema on startup
history.init_db()


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/config")
def get_config():
    return jsonify({"default_model": config.default_model})


@app.route("/api/models")
def get_models():
    try:
        result = ollama.Client(host=config.ollama_host).list()
        names = [m.model for m in result.models]
        return jsonify(names)
    except Exception as e:  # noqa: BLE001
        return jsonify({"error": str(e)}), 500


@app.route("/api/chat", methods=["POST"])
def chat():
    body = request.get_json(silent=True) or {}
    conv_id = body.get("conversation_id")
    model = body.get("model")
    message = body.get("message")

    if not conv_id or not model or not message:
        return jsonify({"error": "conversation_id, model and message are required"}), 400

    history.save_message(conv_id, "user", message)
    messages = history.load_history(conv_id)
    save_fn = functools.partial(history.save_message, conv_id)

    def generate():
        for chunk in chat_engine.chat_stream(messages, model, conv_id, save_fn):
            if chunk == "\x00":
                # Keepalive: flush an SSE comment so the browser's ReadableStream
                # opens immediately even while the model is warming up.
                yield ": keepalive\n\n"
            else:
                # SSE requires every line of a multi-line payload to be prefixed
                # with "data: "; a bare newline would be parsed as a field with
                # no key and silently dropped by the browser, losing line breaks.
                lines = chunk.replace('\r\n', '\n').replace('\r', '\n').split('\n')
                yield "".join(f"data: {line}\n" for line in lines) + "\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.route("/api/history/<conv_id>")
def get_history(conv_id: str):
    return jsonify(history.load_history(conv_id))


@app.route("/api/conversations")
def get_conversations():
    return jsonify(history.list_conversations())


@app.route("/api/conversations/<conv_id>", methods=["DELETE"])
def delete_conversation(conv_id: str):
    history.delete_conversation(conv_id)
    return jsonify({"ok": True})


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
