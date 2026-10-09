import json
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


@app.route("/api/ocr", methods=["POST"])
def ocr():
    data = request.get_json(silent=True) or {}
    img = str(data.get("image", ""))
    if "," in img:
        img = img.split(",", 1)[1]
    if not img:
        return jsonify(error="No image received"), 400
    if len(img) > 3_000_000:
        return jsonify(error="Image is too big. Try a smaller one."), 413
    if not KEY:
        return jsonify(error="Server is missing GEMINI_API_KEY"), 500
    prompt = (
        "Transcribe all the text in this image exactly as written, including handwriting. "
        "Keep the line breaks. Use markdown for headings, lists or tables if they are clear. "
        "Reply with only the transcription. If there is no readable text, reply with exactly NO_TEXT."
    )
    body = {"contents": [{"parts": [{"text": prompt}, {"inline_data": {"mime_type": "image/jpeg", "data": img}}]}]}
    for model in MODELS:
        try:
            r = requests.post(f"{URL}/models/{model}:generateContent", params={"key": KEY}, json=body, timeout=60)
        except requests.exceptions.RequestException:
            continue
        if r.status_code in (404, 429, 503):
            continue
        if not r.ok:
            return jsonify(error="Gemini could not read this image. Try again."), 502
        try:
            text = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        except (KeyError, IndexError):
            text = ""
        return jsonify(text="" if text == "NO_TEXT" else text)
    return jsonify(error="All models are busy. Try again in a minute."), 503


def generate(prompt, as_json=False, timeout=60):
    body = {"contents": [{"parts": [{"text": prompt}]}]}
    if as_json:
        body["generationConfig"] = {"responseMimeType": "application/json"}
    for model in MODELS:
        try:
            r = requests.post(f"{URL}/models/{model}:generateContent", params={"key": KEY}, json=body, timeout=timeout)
        except requests.exceptions.RequestException:
            continue
        if r.status_code in (404, 429, 503):
            continue
        if not r.ok:
            return None, 502
        try:
            return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip(), 200
        except (KeyError, IndexError):
            return None, 502
    return None, 503


def parse_list(text):
    t = text.strip()
    if t.startswith("```"):
        t = t.strip("`")
        if t[:4].lower() == "json":
            t = t[4:]
    try:
        v = json.loads(t)
    except ValueError:
        return None
    if isinstance(v, dict):
        v = next((x for x in v.values() if isinstance(x, list)), None)
    return v if isinstance(v, list) else None


@app.route("/api/study", methods=["POST"])
def study():
    data = request.get_json(silent=True) or {}
    mode = data.get("mode")
    if mode not in ("summary", "quiz", "flashcards"):
        return jsonify(error="Unknown study mode"), 400
    raw = data.get("context", [])
    context = [c for c in (raw[:16] if isinstance(raw, list) else []) if isinstance(c, dict)]
    if not context:
        return jsonify(error="Add notes first"), 400
    if not KEY:
        return jsonify(error="Server is missing GEMINI_API_KEY"), 500
    ctx = "\n\n---\n\n".join(f"[Source: {str(c.get('file', ''))[:100]}]\n{str(c.get('text', ''))[:1500]}" for c in context)

    if mode == "summary":
        prompt = (
            "You are a study assistant. Using ONLY the notes below, write a clear study summary in markdown: "
            "a short overview paragraph, then a '## Key points' bulleted list, then a '## Important terms' "
            "list with one-line definitions (skip this part if there are no terms). Do not add outside facts.\n\n"
            f"NOTES:\n{ctx}"
        )
        text, code = generate(prompt)
        if text is None:
            return jsonify(error="All models are busy. Try again in a minute." if code == 503 else "Gemini could not make that. Try again."), code
        return jsonify(summary=text)

    if mode == "quiz":
        prompt = (
            "Create 5 multiple-choice questions that test understanding of the notes below. Use ONLY the notes. "
            "Each question has exactly 4 options, one correct. Make the wrong options plausible and put the "
            "correct answer at a random position. Reply with a JSON array only, shaped like "
            '[{"q": "question", "options": ["a", "b", "c", "d"], "answer": 0, "why": "one-sentence explanation"}] '
            "where answer is the index (0 to 3) of the correct option.\n\n"
            f"NOTES:\n{ctx}"
        )
    else:
        prompt = (
            "Create 8 study flashcards from the notes below. Use ONLY the notes. Each card has a short front "
            "(a term or question) and a concise back (the answer or definition). Reply with a JSON array only, "
            'shaped like [{"front": "...", "back": "..."}].\n\n'
            f"NOTES:\n{ctx}"
        )
    text, code = generate(prompt, as_json=True)
    if text is None:
        return jsonify(error="All models are busy. Try again in a minute." if code == 503 else "Gemini could not make that. Try again."), code
    items = []
    for x in parse_list(text) or []:
        if not isinstance(x, dict):
            continue
        if mode == "quiz":
            o = x.get("options")
            a = x.get("answer")
            if (isinstance(x.get("q"), str) and isinstance(o, list) and len(o) == 4
                    and all(isinstance(i, str) for i in o) and isinstance(a, int) and not isinstance(a, bool) and 0 <= a < 4):
                items.append({"q": x["q"], "options": o, "answer": a, "why": str(x.get("why", ""))[:400]})
        elif isinstance(x.get("front"), str) and isinstance(x.get("back"), str):
            items.append({"front": x["front"], "back": x["back"]})
    if not items:
        return jsonify(error="Could not build that from these notes. Try again."), 502
    return jsonify(items=items[:10])


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