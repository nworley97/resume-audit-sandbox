# app.py ― Demo Sandbox (Résumé → JSON → Fit Score & Questions)
import os, json, logging, tempfile
import PyPDF2
from flask import Flask, render_template_string, request, flash
import openai

# ---------- CONFIG & LOGGING ----------
logging.basicConfig(
    format="%(asctime)s %(levelname)s %(message)s", level=logging.INFO
)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "sk-...")
MODEL          = "gpt-4o"          # change if you use gpt-4o-mini, gpt-4-turbo, etc.
openai.api_key = OPENAI_API_KEY

# ---------- LLM HELPER ----------
def chat(system_prompt: str, user_prompt: str) -> str:
    """ Consistent, low‑temperature wrapper around OpenAI ChatCompletion. """
    resp = openai.ChatCompletion.create(
        model       = MODEL,
        temperature = 0,
        top_p       = 0.1,
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ],
    )
    return resp.choices[0].message.content.strip()

# ---------- PDF → TEXT ----------
def pdf_to_text(path: str) -> str:
    parts = []
    with open(path, "rb") as f:
        for page in PyPDF2.PdfReader(f).pages:
            if (txt := page.extract_text()):
                parts.append(txt)
    return "\n".join(parts)

# ---------- Resume processing ----------
def resume_json(resume_txt: str) -> dict:
    prompt = (
        "Convert the résumé below into a JSON object containing: "
        "name, contact, education, work_experience, skills, certifications. "
        "Return ONLY the JSON.\n\n"
        f"{resume_txt}"
    )
    raw = chat("You are a résumé JSON extractor.", prompt)
    return json.loads(raw.strip("`"))

def is_real_resume(rjs: dict) -> bool:
    prompt = "Is the résumé realistic (not obviously AI‑generated)? Answer yes or no."
    verdict = chat("You are a résumé authenticity checker.", f"{json.dumps(rjs)}\n\n{prompt}")
    return verdict.lower().startswith("y")

def score_fit(rjs: dict, jd_txt: str) -> int:
    prompt = (
        "Rate the résumé against the job description on a 1‑5 integer scale "
        "(5 = excellent fit). Return ONLY the number."
    )
    answer = chat(
        "You are a technical recruiter.",
        f"Résumé:\n{json.dumps(rjs, indent=2)}\n\nJob Description:\n{jd_txt}\n\n{prompt}",
    )
    try:
        return int(answer.strip())
    except ValueError:
        return 1

def make_questions(rjs: dict, jd_txt: str) -> list[str]:
    prompt = (
        "Write exactly FOUR technical interview questions tailored to this "
        "candidate and job description. Return them as a JSON array of strings."
    )
    raw = chat(
        "You are an interviewer crafting questions.",
        f"Résumé:\n{json.dumps(rjs)}\n\nJob Description:\n{jd_txt}\n\n{prompt}",
    )
    try:
        return json.loads(raw.strip("`"))
    except Exception:
        # fallback: split by lines
        return [ln.lstrip("-• ").strip() for ln in raw.splitlines() if ln.strip()][:4]

# ---------- Flask setup ----------
app = Flask(__name__)
app.secret_key = os.getenv("RESUME_APP_SECRET_KEY", "change‑me‑in‑prod")

HTML_FORM = """
<!doctype html><html lang="en"><head>
  <title>Demo Sandbox – Résumé Audit</title>
  <meta charset="utf-8">
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
</head><body class="bg-light">
<div class="container" style="max-width:600px;">
  <h2 class="my-4 text-primary">Demo Sandbox</h2>
  <form method="post" enctype="multipart/form-data" class="card p-4 shadow-sm">
    <div class="mb-3">
      <label class="form-label">Résumé (PDF)</label>
      <input type="file" name="resume_pdf" accept=".pdf" class="form-control" required>
    </div>
    <div class="mb-3">
      <label class="form-label">Job Description (PDF)</label>
      <input type="file" name="jobdesc_pdf" accept=".pdf" class="form-control" required>
    </div>
    <button class="btn btn-primary w-100">Run Audit</button>
    {% with msgs = get_flashed_messages() %}
      {% if msgs %}<div class="alert alert-danger mt-3">{{msgs[0]}}</div>{% endif %}
    {% endwith %}
  </form>
</div></body></html>
"""

HTML_RESULT = """
<!doctype html><html lang="en"><head>
  <title>Demo Sandbox – Result</title>
  <meta charset="utf-8">
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
</head><body class="bg-light">
<div class="container" style="max-width:600px;">
  <div class="card p-4 shadow-sm my-4">
    <h3 class="text-primary mb-3">Demo Sandbox Result</h3>
    {% if err %}<div class="alert alert-danger">{{err}}</div>{% endif %}
    <p><strong>Résumé Realism:</strong>
       {% if realism %}<span class="badge bg-success">Looks Real</span>
       {% else %}<span class="badge bg-danger">Possibly Fake</span>{% endif %}</p>
    <p><strong>Fit Score:</strong> <span class="badge bg-info text-dark">{{score}} / 5</span></p>
    <h5 class="mt-4">Suggested Interview Questions</h5>
    <ul class="list-group list-group-flush">
      {% for q in questions %}<li class="list-group-item">{{q}}</li>{% endfor %}
    </ul>
    <a href="{{url_for('index')}}" class="btn btn-link mt-3">Analyze another</a>
  </div>
</div></body></html>
"""

# ---------- Routes ----------
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        resume_file = request.files.get("resume_pdf")
        jd_file     = request.files.get("jobdesc_pdf")

        if not resume_file or resume_file.filename == "":
            flash("Please upload a résumé PDF."); return render_template_string(HTML_FORM)
        if not jd_file or jd_file.filename == "":
            flash("Please upload a job description PDF."); return render_template_string(HTML_FORM)

        # save uploads temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as f1, \
             tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as f2:
            resume_file.save(f1.name); pdf_resume = f1.name
            jd_file.save(f2.name);     pdf_jd     = f2.name

        try:
            resume_txt = pdf_to_text(pdf_resume)
            jd_txt     = pdf_to_text(pdf_jd)

            rjs        = resume_json(resume_txt)
            realism    = is_real_resume(rjs)
            score      = score_fit(rjs, jd_txt)
            questions  = make_questions(rjs, jd_txt)
            result = dict(realism=realism, score=score, questions=questions, err=None)

        except Exception as e:
            logging.exception("Audit failed")
            result = dict(realism=False, score=None, questions=[], err=str(e))

        finally:
            os.remove(pdf_resume); os.remove(pdf_jd)

        return render_template_string(HTML_RESULT, **result)

    return render_template_string(HTML_FORM)

# ---------- Entrypoint ----------
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
