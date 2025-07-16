import os, json, uuid, logging, tempfile
from json import JSONDecodeError
from typing import List, Dict
from flask import (
    Flask, request, redirect, url_for, render_template_string,
    flash, send_file
)
import PyPDF2
from openai import OpenAI, APIError, BadRequestError

# ─────────── CONFIG ───────────
logging.basicConfig(level=logging.INFO)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "sk-...")
MODEL          = "gpt-4o"
client         = OpenAI(api_key=OPENAI_API_KEY)

# in‑memory store (swap for DB later)
CANDIDATES: List[Dict] = []

JOB_DESCRIPTION = """
<h4>Senior Backend Engineer – Health Data Platform</h4>
<ul>
<li>Design & maintain Python microservices (Django or Flask)</li>
<li>AWS deployment (ECS/EKS), PostgreSQL, CI/CD (GitHub Actions)</li>
<li>6+ yrs experience • Kubernetes • GraphQL nice‑to‑have</li>
</ul>
"""

# ─────────── LLM helper ────────
def chat(system_prompt: str, user_prompt: str, *, json_mode=False) -> str:
    try:
        resp = client.chat.completions.create(
            model       = MODEL,
            temperature = 0,
            top_p       = 0.1,
            response_format = ({"type": "json_object"} if json_mode else None),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
            timeout=60,          # per‑call safeguard
        )
        return resp.choices[0].message.content.strip()
    except APIError as e:
        if getattr(e, "code", None) == "insufficient_quota":
            raise RuntimeError("OpenAI quota exhausted.") from e
        raise RuntimeError(f"OpenAI error: {e}") from e
    except BadRequestError as e:
        raise RuntimeError(f"Bad request to OpenAI: {e}") from e

# ─────────── Resume helpers ────
def pdf_to_text(path: str) -> str:
    with open(path, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        return "\n".join(p.extract_text() or "" for p in reader.pages)

def resume_json(text: str) -> dict:
    raw = chat(
        "You are a résumé JSON extractor.",
        "Convert to JSON with name, contact, education, work_experience, "
        "skills, certifications.\n\n" + text,
        json_mode=True,
    )
    return json.loads(raw)

def realism_check(rjs: dict) -> bool:
    verdict = chat(
        "You are a résumé authenticity checker.",
        f"{json.dumps(rjs)}\n\nIs this résumé realistic? answer yes or no."
    )
    return verdict.lower().startswith("y")

def fit_score(rjs: dict, jd: str) -> int:
    score_txt = chat(
        "You are a technical recruiter.",
        f"Résumé:\n{json.dumps(rjs,indent=2)}\n\nJD:\n{jd}\n\n"
        "Rate 1‑5 integer only."
    )
    try: return int(score_txt.strip())
    except ValueError: return 1

def make_questions(rjs: dict) -> List[str]:
    raw = chat(
        "You are an interviewer verifying a résumé.",
        "Write exactly FOUR probing technical or experience‑based questions "
        "that would confirm whether the candidate genuinely possesses the "
        "skills and achievements listed below. Return as JSON array; or "
        "object {'questions':[...]}.\n\n"
        f"{json.dumps(rjs)}",
        json_mode=True,
    )
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return parsed[:4]
        if isinstance(parsed, dict) and "questions" in parsed:
            return parsed["questions"][:4]
    except JSONDecodeError:
        pass
    return [l.lstrip('-• ').strip() for l in raw.splitlines() if l.strip()][:4]

def score_answers(rjs: dict, questions: List[str], answers: List[str]) -> List[int]:
    """
    Return a list of integers (1‑5) rating each answer's validity.
    """
    payload = {
        "résumé": rjs,
        "qa": [{"q": q, "a": a} for q, a in zip(questions, answers)]
    }
    raw = chat(
        "You are a meticulous interviewer.",
        "For each Q/A pair below, score how consistent the answer is with "
        "the résumé and typical expectations for the role. 1 = very dubious/"
        "inconsistent, 5 = fully consistent and knowledgeable. "
        "Return only a JSON array of four integers.\n\n"
        + json.dumps(payload, indent=2),
        json_mode=True,
    )
    try:
        scores = json.loads(raw)
        if isinstance(scores, list) and len(scores) == 4:
            return [int(max(1, min(5, s))) for s in scores]
    except Exception:
        pass
    return [3, 3, 3, 3]  # neutral fallback

# ─────────── Flask setup ───────
app = Flask(__name__)
app.secret_key = os.getenv("RESUME_APP_SECRET_KEY", "demo‑key")

BASE = """
<!doctype html><html lang=en><head>
<meta charset=utf-8>
<title>{{ title }}</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel=stylesheet>
<style>.centered { text-align:center; }</style>
</head><body class="bg-light">
<nav class="navbar navbar-light bg-white border-bottom mb-4">
  <div class="container-fluid">
    <span class="navbar-brand mb-0 h4">Demo Sandbox</span>
    <div>
      {% if role=='candidate' %}
        <a class="btn btn-outline-primary btn-sm" href="{{ url_for('recruiter') }}">Recruiter view</a>
      {% else %}
        <a class="btn btn-outline-secondary btn-sm" href="{{ url_for('home') }}">Candidate view</a>
      {% endif %}
    </div>
  </div>
</nav>
<div class="container" style="max-width:720px;">
  {% with msgs = get_flashed_messages() %}
    {% if msgs %}
      <div class="alert alert-danger">{{ msgs[0] }}</div>
    {% endif %}
  {% endwith %}
  {{ body|safe }}
</div>
</body></html>
"""

def render_page(title, role, body_html):
    return render_template_string(BASE, title=title, role=role, body=body_html)

# ─────────── Candidate routes ───
@app.route("/", methods=["GET", "POST"])
def home():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        rf   = request.files.get("resume_pdf")
        if not name:
            flash("Name required."); return redirect(url_for('home'))
        if not rf or rf.filename == "":
            flash("Please upload a résumé PDF."); return redirect(url_for('home'))

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            rf.save(tmp.name); pdf_path = tmp.name

        try:
            txt   = pdf_to_text(pdf_path)
            rjs   = resume_json(txt)
            real  = realism_check(rjs)
            score = fit_score(rjs, JOB_DESCRIPTION)
            qs    = make_questions(rjs)
            cid   = str(uuid.uuid4())[:8]
            CANDIDATES.append({
                "id": cid, "name": name, "resume_json": rjs, "resume_path": pdf_path,
                "real": real, "score": score, "questions": qs,
                "answers": [], "answer_scores": []
            })
            body = f"""
<h4>Hi {name}, thanks for applying!</h4>
<h5 class='mt-4 centered'>Interview Questions</h5>
<form method="post" action="{ url_for('submit_answers', cid=cid) }">
  <ol class="list-group list-group-numbered mb-3">
    {''.join(f'<li class="list-group-item centered"><strong>{q}</strong><br>'
             f'<textarea class="form-control mt-2" name="a{i}" rows="2" required></textarea></li>'
             for i,q in enumerate(qs))}
  </ol>
  <button class="btn btn-primary w-100">Submit answers</button>
</form>
"""
            return render_page("Answer Questions", "candidate", body)

        except RuntimeError as e:
            flash(str(e)); return redirect(url_for('home'))

    # GET upload form
    body = f"""
<div class="card p-4 shadow-sm mb-4">
  {JOB_DESCRIPTION}
</div>
<form method="post" enctype="multipart/form-data" class="card p-4 shadow-sm">
  <div class="mb-3">
    <label class="form-label">Your Name</label>
    <input type="text" class="form-control" name="name" required>
  </div>
  <div class="mb-3">
    <label class="form-label">Upload Résumé (PDF)</label>
    <input type="file" class="form-control" name="resume_pdf" accept=".pdf" required>
  </div>
  <button class="btn btn-primary w-100">Analyze & Get Questions</button>
</form>
"""
    return render_page("Apply – Candidate", "candidate", body)

@app.route("/answers/<cid>", methods=["POST"])
def submit_answers(cid):
    cand = next((c for c in CANDIDATES if c["id"] == cid), None)
    if not cand:
        flash("Candidate not found."); return redirect(url_for('home'))
    answers = [request.form.get(f"a{i}", "").strip() for i in range(4)]
    cand["answers"] = answers
    cand["answer_scores"] = score_answers(cand["resume_json"], cand["questions"], answers)
    flash("Answers submitted!"); return redirect(url_for('home'))

# ─────────── Recruiter routes ──
@app.route("/recruiter")
def recruiter():
    rows = "".join(
        f"<tr><td>{c['name']}</td><td>{c['score']}</td>"
        f"<td><a href='{url_for('candidate_detail', cid=c['id'])}'>view</a></td></tr>"
        for c in CANDIDATES
    ) or "<tr><td colspan=3 class='text-center'>No candidates yet</td></tr>"
    body = f"""
<h4>Job Listing</h4>{JOB_DESCRIPTION}
<hr>
<h4>Candidates</h4>
<table class="table table-sm">
  <thead><tr><th>Name</th><th>Score</th><th></th></tr></thead>
  <tbody>{rows}</tbody>
</table>
"""
    return render_page("Recruiter Dashboard", "recruiter", body)

@app.route("/recruiter/<cid>")
def candidate_detail(cid):
    c = next((x for x in CANDIDATES if x["id"] == cid), None)
    if not c:
        flash("Not found."); return redirect(url_for('recruiter'))

    qa_rows = "".join(
        f"<tr><td><strong>{q}</strong></td>"
        f"<td>{c['answers'][i] or '<em>no answer</em>'}</td>"
        f"<td>{c['answer_scores'][i] if c['answer_scores'] else '-'}</td></tr>"
        for i, q in enumerate(c["questions"])
    )

    body = f"""
<a class="btn btn-link mb-3" href="{url_for('recruiter')}">← back</a>
<h4>{c['name']} — Score {c['score']}/5</h4>
<p><strong>Résumé realism:</strong> {'Looks Real' if c['real'] else 'Possibly Fake'}</p>

<a class="btn btn-sm btn-outline-secondary mb-4" href="{url_for('download_resume', cid=cid)}">
  Download résumé PDF
</a>

<h5>Interview Q&amp;A</h5>
<table class="table table-sm">
  <thead><tr><th>Question</th><th>Answer</th><th>Validity (1‑5)</th></tr></thead>
  <tbody>{qa_rows}</tbody>
</table>
"""
    return render_page(f"Candidate {c['name']}", "recruiter", body)

@app.route("/resume/<cid>")
def download_resume(cid):
    c = next((x for x in CANDIDATES if x["id"] == cid), None)
    if not c:
        return "Not found", 404
    return send_file(
        c["resume_path"],
        as_attachment=True,
        download_name=f"{c['name']}.pdf",
        max_age=0,
    )

# ─────────── Entrypoint ────────
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
