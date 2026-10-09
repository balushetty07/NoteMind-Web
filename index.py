import os
from pathlib import Path

import requests
from flask import Flask, jsonify, request

app = Flask(__name__)

KEY = os.environ.get("GEMINI_API_KEY")
if not KEY:
    try:
        from secret import API_KEY as KEY  # local testing only (secret.py is gitignored)
    except ImportError:
        KEY = None

URL = "https://generativelanguage.googleapis.com/v1beta"
EMBED = "gemini-embedding-001"
MODELS = ["gemini-flash-latest", "gemini-3.5-flash", "gemini-3.6-flash", "gemini-3.1-flash-lite"]


@app.route("/")
def home():
    return (Path(__file__).parent / "index.html").read_text(encoding="utf-8")


@app.route("/api/embed", methods=["POST"])
def embed():
    data = request.get_json(silent=True) or {}
    texts = [str(t)[:3000] for t in data.get("texts", [])[:100]]
    if not texts:
        return jsonify(error="Nothing to read"), 400
    if not KEY:
        return jsonify(error="Server is missing GEMINI_API_KEY"), 500
    try:
        r = requests.post(
            f"{URL}/models/{EMBED}:batchEmbedContents",
            params={"key": KEY},
            json={"requests": [
                {"model": f"models/{EMBED}", "content": {"parts": [{"text": t}]}, "outputDimensionality": 768}
                for t in texts
            ]},
            timeout=40,
        )
        r.raise_for_status()
        return jsonify(vectors=[e["values"] for e in r.json()["embeddings"]])
    except requests.exceptions.RequestException:
        return jsonify(error="Could not index the notes. Try again in a minute."), 502


@app.route("/api/answer", methods=["POST"])
def answer():
    data = request.get_json(silent=True) or {}
    question = str(data.get("question", "")).strip()[:500]
    context = [c for c in data.get("context", [])[:5] if isinstance(c, dict)]
    history = data.get("history", [])
    history = [h for h in (history[-6:] if isinstance(history, list) else []) if isinstance(h, dict)]
    if not question or not context:
        return jsonify(error="Ask a question after adding notes"), 400
    if not KEY:
        return jsonify(error="Server is missing GEMINI_API_KEY"), 500

    ctx = "\n\n---\n\n".join(f"[Source: {str(c.get('file', ''))[:100]}]\n{str(c.get('text', ''))[:1500]}" for c in context)
    chat = "\n".join(f"{h.get('role', 'user')}: {str(h.get('text', ''))[:500]}" for h in history)
    prompt = (
        "You are a helpful study assistant. Answer using ONLY the context below. "
        "Mention which source you used. If the context doesn't contain the answer, say you don't know.\n\n"
        f"CONTEXT:\n{ctx}\n\nCHAT SO FAR:\n{chat}\n\nQUESTION: {question}\n\nANSWER:"
    )
    for model in MODELS:
        try:
            r = requests.post(
                f"{URL}/models/{model}:generateContent",
                params={"key": KEY},
                json={"contents": [{"parts": [{"text": prompt}]}]},
                timeout=45,
            )
        except requests.exceptions.RequestException:
            continue
        if r.status_code in (404, 429, 503):
            continue
        if not r.ok:
            return jsonify(error="Gemini returned an error. Try again."), 502
        return jsonify(reply=r.json()["candidates"][0]["content"]["parts"][0]["text"].strip())
    return jsonify(error="All models are busy. Try again in a minute."), 503


@app.route("/api/title", methods=["POST"])
def title():
    q = str((request.get_json(silent=True) or {}).get("question", "")).strip()[:300]
    if not q or not KEY:
        return jsonify(title="")
    prompt = (
        "Write a title of 2 to 4 words for a chat that starts with this question. "
        f"Reply with only the title, no quotes or punctuation.\n\nQuestion: {q}"
    )
    for model in MODELS[::-1]:
        try:
            r = requests.post(
                f"{URL}/models/{model}:generateContent",
                params={"key": KEY},
                json={"contents": [{"parts": [{"text": prompt}]}]},
                timeout=20,
            )
        except requests.exceptions.RequestException:
            continue
        if r.ok:
            t = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip().strip("\"'.*#")
            return jsonify(title=t[:40])
    return jsonify(title="")