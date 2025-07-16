import os, json, uuid, logging, tempfile, re
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

CANDIDATES: List[Dict] = []

JOB_DESCRIPTION = """
<h4>Senior Backend Engineer – Health Data Platform</h4>
<ul>
<li>Design & maintain Python microservices (Django or Flask)</li>
<li>AWS deployment (ECS/EKS), PostgreSQL, CI/CD (GitHub Actions)</li>
<li>6+ yrs experience • Kubernetes • GraphQL nice‑to‑have</li>
</ul>
"""

# ─────────── OPENAI WRAPPER ───────────
def chat(system: str, user: str, *, json_mode=False, timeout=60) -> str:
    try:
        resp = client.chat.completions.create(
            model       = MODEL,
            temperature = 0,
            top_p       = 0.1,
            response_format = ({"type": "json_object"} if json_mode else None),
            messages=[{"role":"system","content":system},
                      {"role":"user","content":user}],
            timeout=timeout,
        )
        return resp.choices[0].message.content.strip()
    except APIError as e:
        if getattr(e, "code", None) == "insufficient_quota":
            raise RuntimeError("OpenAI quota exhausted.") from e
        raise
    except BadRequestError as e:
        raise RuntimeError(f"OpenAI bad request: {e}") from e

# ─────────── Helper functions ───────────
def pdf_to_text(path: str) -> str:
    with open(path, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        return "\n".join(p.extract_text() or "" for p in reader.pages)

def resume_json(text: str) -> dict:
    raw = chat(
        "You are a résumé JSON extractor.",
        "Convert this résumé text into JSON with fields: "
        "name, contact, education, work_experience, skills, certifications.\n\n"
        + text,
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
        f"Résumé:\n{json.dumps(rjs, indent=2)}\n\nJob Description:\n{jd}\n\n"
        "Rate résumé–JD fit on a 1‑5 integer scale. Return only the number."
    )
    try:
        return int(score_txt.strip())
    except ValueError:
        return 1

def make_questions(rjs: dict) -> List[str]:
    """
    Generate four résumé‑verification questions.
    Accepts model replies as a JSON array OR an object {'questions':[...]}.
    """
    raw = chat(
        "You are an interviewer verifying a résumé.",
        "Write exactly FOUR probing questions (strings only) that confirm the "
        "candidate's listed skills/achievements. Return either a JSON array "
        "or an object {'questions':[...]}.\n\n" + json.dumps(rjs),
        json_mode=True,
    )
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return [str(q) for q in data][:4]
        if isinstance(data, dict) and "questions" in data:
            return [str(q) for q in data["questions"]][:4]
    except JSONDecodeError:
        pass
    # Plain‑text fallback
    return [l.strip("-• ").strip() for l in raw.splitlines() if l.strip()][:4]

def score_answers(rjs: dict, qs: List[str], ans: List[str]) -> List[int]:
    """
    Return four integers (1‑5) rating each answer's validity.
    Answers with <5 words auto‑score 1. Others are scored by GPT.
    """
    short_idx = [i for i,a in enumerate(ans) if len(re.findall(r"\w+", a)) < 5]
    prelim = [1 if i in short_idx else None for i in range(4)]

    payload = {"résumé": rjs, "qa": [{"q": q, "a": a} for q,a in zip(qs, ans)]}
    rubric = (
        "Score each answer 1‑5:\n"
        "5 = Precise, technically sound, fully consistent with résumé\n"
        "4 = Mostly specific/consistent, minor vagueness\n"
        "3 = Generic but not contradictory\n"
        "2 = Partially inconsistent or vague\n"
        "1 = Empty, gibberish, or contradicts résumé\n"
        "Return only a JSON array of four integers."
    )
    try:
        raw = chat("You are a strict interviewer.", rubric+"\n\n"+json.dumps(payload,indent=2),
                   json_mode=True)
        gpt_scores = [int(max(1,min(5,s))) for s in json.loads(raw)]
    except Exception:
        gpt_scores = [3,3,3,3]

    return [p or s for p,s in zip(prelim, gpt_scores)]

# ─────────── Flask setup ───────────
app = Flask(__name__)
app.secret_key = os.getenv("RESUME_APP_SECRET_KEY", "demo‑key")

BASE = """
<!doctype html><html lang=en><head>
  <meta charset=utf-8><title>{{ title }}</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel=stylesheet>
  <style>.centered { text-align:center; }</style>
</head><body class="bg-light">
<nav class="navbar navbar-light bg-white border-bottom mb-4">
  <div class="container-fluid">
    <span class="navbar-brand mb-0 h4">Demo Sandbox</span>
    <div>
      {% if role == 'candidate' %}
        <a class="btn btn-outline-primary btn-sm" href="{{ url_for('recruiter') }}">Recruiter view</a>
      {% else %}
        <a class="btn btn-outline-secondary btn-sm" href="{{ url_for('home') }}">Candidate view</a>
      {% endif %}
    </div>
  </div>
</nav>
<div class="container" style="max-width:720px;">
  {% with m = get_flashed_messages() %}
    {% if m %}
      <div class="alert alert-danger">{{ m[0] }}</div>
    {% endif %}
  {% endwith %}
  {{ body|safe }}
</div>
</body></html>
"""
def page(t,r,b): return render_template_string(BASE,title=t,role=r,body=b)

# ─────────── Candidate routes ───────────
@app.route("/", methods=["GET", "POST"])
def home():
    if request.method == "POST":
        name = request.form.get("name","").strip()
        rf   = request.files.get("resume_pdf")
        if not name or not rf or rf.filename=="":
            flash("Name and résumé PDF required."); return redirect("/")

        with tempfile.NamedTemporaryFile(delete=False,suffix=".pdf") as tmp:
            rf.save(tmp.name); pdf = tmp.name

        try:
            txt  = pdf_to_text(pdf)
            rjs  = resume_json(txt)
            real = realism_check(rjs)
            fs   = fit_score(rjs, JOB_DESCRIPTION)
            qs   = make_questions(rjs)
            cid  = str(uuid.uuid4())[:8]

            CANDIDATES.append(dict(
                id=cid, name=name, resume_json=rjs, resume_path=pdf,
                real=real, score=fs, questions=qs, answers=[], answer_scores=[]
            ))

            q_inputs="".join(
                f"<li class='list-group-item centered'><strong>{q}</strong><br>"
                f"<textarea class='form-control mt-2' name='a{i}' rows='2' required></textarea></li>"
                for i,q in enumerate(qs)
            )
            body=(f"<h4>Hi {name}, thanks for applying!</h4>"
                  "<h5 class='mt-4 centered'>Interview Questions</h5>"
                  f"<form method='post' action='{url_for('submit_answers',cid=cid)}'>"
                  f"<ol class='list-group list-group-numbered mb-3'>{q_inputs}</ol>"
                  "<button class='btn btn-primary w-100'>Submit answers</button></form>")
            return page("Answer Questions","candidate",body)
        except RuntimeError as e:
            flash(str(e)); return redirect("/")

    body=(f"<div class='card p-4 shadow-sm mb-4'>{JOB_DESCRIPTION}</div>"
          "<form method='post' enctype='multipart/form-data' class='card p-4 shadow-sm'>"
          "<div class='mb-3'><label class='form-label'>Your Name</label>"
          "<input class='form-control' name='name' required></div>"
          "<div class='mb-3'><label class='form-label'>Upload Résumé (PDF)</label>"
          "<input type='file' class='form-control' name='resume_pdf' accept='.pdf' required></div>"
          "<button class='btn btn-primary w-100'>Analyze & Get Questions</button></form>")
    return page("Apply – Candidate","candidate",body)

@app.route("/answers/<cid>", methods=["POST"])
def submit_answers(cid):
    c = next((x for x in CANDIDATES if x["id"]==cid), None)
    if not c:
        flash("Candidate not found."); return redirect("/")
    ans=[request.form.get(f"a{i}","").strip() for i in range(4)]
    c["answers"]=ans
    c["answer_scores"]=score_answers(c["resume_json"],c["questions"],ans)
    flash("Answers submitted!"); return redirect("/")

# ─────────── Recruiter routes ───────────
@app.route("/recruiter")
def recruiter():
    rows="".join(
        f"<tr><td>{c['name']}</td><td>{c['score']}</td>"
        f"<td><a href='{url_for('detail',cid=c['id'])}'>view</a></td></tr>"
        for c in CANDIDATES) or "<tr><td colspan=3 class='text-center'>No candidates yet</td></tr>"
    body=(f"<h4>Job Listing</h4>{JOB_DESCRIPTION}<hr>"
          "<h4>Candidates</h4>"
          "<table class='table table-sm'><thead><tr><th>Name</th><th>Score</th><th></th></tr></thead>"
          f"<tbody>{rows}</tbody></table>")
    return page("Recruiter Dashboard","recruiter",body)

@app.route("/recruiter/<cid>")
def detail(cid):
    c=next((x for x in CANDIDATES if x["id"]==cid),None)
    if not c:
        flash("Not found"); return redirect("/recruiter")
    qa="".join(
        f"<tr><td><strong>{q}</strong></td>"
        f"<td>{c['answers'][i] or '<em>no answer</em>'}</td>"
        f"<td>{c['answer_scores'][i] if c['answer_scores'] else '-'}</td></tr>"
        for i,q in enumerate(c["questions"]))
    body=(f"<a class='btn btn-link mb-3' href='{url_for('recruiter')}'>← back</a>"
          f"<h4>{c['name']} — Score {c['score']}/5</h4>"
          f"<p><strong>Résumé realism:</strong> {'Looks Real' if c['real'] else 'Possibly Fake'}</p>"
          f"<a class='btn btn-sm btn-outline-secondary mb-4' href='{url_for('download_resume',cid=cid)}'>"
          "Download résumé PDF</a>"
          "<h5>Interview Q&amp;A</h5>"
          "<table class='table table-sm'><thead><tr><th>Question</th><th>Answer</th>"
          "<th>Validity (1‑5)</th></tr></thead><tbody>"+qa+"</tbody></table>")
    return page(f"Candidate {c['name']}","recruiter",body)

@app.route("/resume/<cid>")
def download_resume(cid):
    c=next((x for x in CANDIDATES if x["id"]==cid),None)
    if not c: return "Not found",404
    return send_file(c["resume_path"],as_attachment=True,
                     download_name=f"{c['name']}.pdf",max_age=0)

# ─────────── Entrypoint ───────────
if __name__=="__main__":
    app.run(debug=True,host="0.0.0.0",port=int(os.getenv("PORT",5000)))
