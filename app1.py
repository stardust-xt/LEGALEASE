import os
import re
import logging
from datetime import datetime
from io import BytesIO
from flask import Flask, request, jsonify, send_file, render_template_string
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import requests

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.enums import TA_JUSTIFY, TA_CENTER
from reportlab.lib.colors import HexColor


# ---------------- CONFIG ----------------
app = Flask(__name__)
CORS(app)
limiter = Limiter(app, key_func=get_remote_address, default_limits=["50 per hour"])

logging.basicConfig(level=logging.INFO)

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

SUMMARY_LEVELS = {
    "short": "Brief Overview",
    "medium": "Standard Summary",
    "detailed": "Comprehensive Analysis"
}


# ---------------- HELPERS ----------------
def sanitize_text(text):
    return re.sub(r"\s+", " ", text).strip()


def summarize_with_groq(text, level):
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    body = {
        "model": "llama-3.1-70b-versatile",
        "temperature": 0.3,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a legal document expert. Summarize clearly, "
                    "preserving legal conditions, exceptions, and qualifiers."
                )
            },
            {
                "role": "user",
                "content": f"Provide a {SUMMARY_LEVELS[level].lower()}:\n\n{text}"
            }
        ]
    }

    r = requests.post(GROQ_API_URL, headers=headers, json=body, timeout=30)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def generate_pdf(summary, level):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)

    styles = getSampleStyleSheet()
    elements = []

    title = ParagraphStyle(
        "title",
        fontSize=24,
        alignment=TA_CENTER,
        textColor=HexColor("#78350f")
    )

    body = ParagraphStyle(
        "body",
        fontSize=11,
        leading=18,
        alignment=TA_JUSTIFY
    )

    elements.append(Paragraph("LEGALEASE", title))
    elements.append(Spacer(1, 12))
    elements.append(Paragraph(f"Summary Level: {SUMMARY_LEVELS[level]}", styles["Italic"]))
    elements.append(Spacer(1, 20))

    for p in summary.split("\n"):
        elements.append(Paragraph(p, body))
        elements.append(Spacer(1, 8))

    elements.append(Spacer(1, 20))
    elements.append(Paragraph(
        "This document is for informational purposes only and not legal advice.",
        styles["Italic"]
    ))

    doc.build(elements)
    buffer.seek(0)
    return buffer


# ---------------- ROUTES ----------------
@app.route("/")
def index():
    return render_template_string(HTML)


@app.route("/summarize", methods=["POST"])
@limiter.limit("10/minute")
def summarize():
    data = request.json
    text = sanitize_text(data.get("text", ""))
    level = data.get("level", "medium")

    if not text:
        return jsonify({"error": "Text required"}), 400

    summary = summarize_with_groq(text, level)
    return jsonify({"summary": summary})


@app.route("/download-pdf", methods=["POST"])
@limiter.limit("5/minute")
def download_pdf():
    data = request.json
    summary = data.get("summary", "")
    level = data.get("level", "medium")

    pdf = generate_pdf(summary, level)
    filename = f"legalease_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"

    return send_file(
        pdf,
        as_attachment=True,
        download_name=filename,
        mimetype="application/pdf"
    )


# ---------------- HTML + CSS + JS ----------------
HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>LEGALEASE</title>
<style>
""" + open(__file__).read().split("CSS_START")[1].split("CSS_END")[0] + """
</style>
</head>
<body>

<div class="background-pattern"></div>

<div class="container">
  <header>
    <div class="logo-section">
      <div class="logo-icon">⚖️</div>
      <h1>LEGALEASE</h1>
    </div>
    <p class="tag">Plain-English Legal Document Summaries</p>
  </header>

  <div class="pane">
    <div class="input-section">
      <label>Paste Legal Document</label>
      <textarea id="inputText" placeholder="Paste your agreement, contract, or policy here..."></textarea>
    </div>

    <div class="controls">
      <div class="control-group">
        <label class="small-label">Summary Level</label>
        <select id="level">
          <option value="short">Short</option>
          <option value="medium" selected>Medium</option>
          <option value="detailed">Detailed</option>
        </select>
      </div>

      <div class="button-group">
        <button id="summarizeBtn" class="btn-primary">Summarize</button>
        <button id="downloadBtn" class="btn-secondary">Download PDF</button>
      </div>
    </div>

    <div id="output" class="output">
      Your summary will appear here.
    </div>
  </div>

  <div class="footer">
    <p>© LEGALEASE — Informational only. Not legal advice.</p>
  </div>
</div>

<script>
""" + open(__file__).read().split("JS_START")[1].split("JS_END")[0] + """
</script>

</body>
</html>
"""

# ---------------- CSS ----------------
# CSS_START
"""
(PASTE YOUR FULL CSS HERE EXACTLY AS YOU SENT)
"""
# CSS_END


# ---------------- JS ----------------
# JS_START
"""
(PASTE YOUR FULL JAVASCRIPT HERE EXACTLY AS YOU SENT)
"""
# JS_END


if __name__ == "__main__":
    app.run(debug=True)
