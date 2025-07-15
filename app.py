# app.py – Demo Sandbox (OpenAI 1.x, JSON mode, friendly errors)
import os, json, logging, tempfile
from json import JSONDecodeError
from flask import Flask, render_template_string, request, flash
import PyPDF2
from openai import OpenAI, APIError, BadRequestError

# ─────────────────── Config & logging ───────────────────
logging.basicConfig(
    format="%(asctime)s %(levelname)s %(message)s",
    level=logging.INFO,
)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "sk-...")
MODEL          = "gpt-4o"
client         = OpenAI(api_key=OPENAI_API_KEY)

# ─────────────────── LLM helper ──────────────────────────
def chat_raw(system_prompt: str, user_prompt: str, *, json_mode=False) -> str:
    """
    Low‑level wrapper around chat.completions.create.
    Set json_mode=True to enforce valid JSON output via response_format.
    Raises RuntimeError with a human‑readable message on common API errors.
    """
    try:
        resp = client.chat.completions.create(
            model            = MODEL,
            temperature      = 0,
            top_p            = 0.1,
            response_format  = ({"type": "json_object"} if json_mode else None),
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
            timeout = 30,
        )
        return resp.choices[0].message.content.strip()
    except APIError as e:
        if getattr(e, "code", None) == "insufficient_quota":
            raise RuntimeError("OpenAI quota exhausted. Add credit or raise your limit.") from e
        raise RuntimeError(f"OpenAI API error: {e}") from e
    except BadRequestError as e:
        raise RuntimeError(f"Bad request to OpenAI: {e}") from e


# ─────────────────── Core helpers ────────────────────────
def pdf_to_text(path: str) -> str:
    with open(path, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        return "\n".join(p.extract_text() or "" for p in reader.pages)

def resume_json(resume_txt: str) -> dict:
    raw = chat_raw(
        "You are a résumé JSON extractor.",
        "Convert the résumé below into JSON with fields: "
        "name, contact, education, work_experience, skills, certifications.\n\n"
        + resume_txt,
        json_mode=True,
    )
    return json.loads(raw)

def is_real_resume(rjs: dict) -> bool:
    verdict = chat_raw(
        "You are a résumé authenticity checker.",
        f"{json.dumps(rjs)}\n\nIs the résumé realistic (not AI‑generated)? Answer yes or no."
    )
    return verdict.lower().startswith("y")

def score_fit(rjs: dict, jd_txt: str) -> int:
    score_text = chat_raw(
        "You are a technical recruiter.",
        f"Résumé:\n{json.dumps(rjs, indent=2)}\n\nJob Description:\n{jd_txt}\n\n"
        "Rate the résumé on a 1‑5 integer scale (5 = excellent fit). Return ONLY the number."
    )
    try:
        return int(score_text.strip())
    except ValueError:
        logging.warning("Could not parse score from: %s", score_text)
        return 1

def make_questions(rjs: dict, jd_txt: str) -> list[str]:
    """Return exactly four questions as a Python list of strings."""
    raw = chat_raw(
        "You are an interviewer crafting questions.",
        "Write exactly FOUR technical interview questions tailored to this "
        "candidate and job description. Return them as JSON — either a bare "
        "array of strings or an object with the key 'questions'.\n\n"
        f"Résumé:\n{json.dumps(rjs)}\n\nJob Description:\n{jd_txt}",
        json_mode=True,
    )

    try:
        parsed = json.loads(raw)
        # Accept either form: [ ... ]  or  { "questions": [ ... ] }
        if isinstance(parsed, list):
            return parsed[:4]
        if isinstance(parsed, dict) and "questions" in parsed:
            return parsed["questions"][:4]
        logging.warning("Unexpected JSON shape for questions: %s", raw[:120])
    except JSONDecodeError:
        logging.warning("Questions not JSON; fallback to line split. RAW=%s", raw[:120])

    # Fallback: take up to four non‑empty lines
    return [ln.lstrip("-• ").strip() for ln in raw.splitlines() if ln.strip()][:4]


# ─────────────────── Flask setup ─────────────────────────
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
      {% if msgs %}
        <div class="alert alert-danger mt-3">{{ msgs[0] }}</div>
      {% endif %}
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
    {% if err %}<div class="alert alert-danger">{{ err }}</div>{% endif %}
    {% if not err %}
      <p><strong>Résumé Realism:</strong>
         {% if realism %}<span class="badge bg-success">Looks Real</span>
         {% else %}<span class="badge bg-danger">Possibly Fake</span>{% endif %}</p>
      <p><strong>Fit Score:</strong> <span class="badge bg-info text-dark">{{ score }} / 5</span></p>
      <h5 class="mt-4">Suggested Interview Questions</h5>
      <ul class="list-group list-group-flush">
        {% for q in questions %}<li class="list-group-item">{{ q }}</li>{% endfor %}
      </ul>
    {% endif %}
    <a href="{{ url_for('index') }}" class="btn btn-link mt-3">Analyze another</a>
  </div>
</div></body></html>
"""

# ─────────────────── Routes ──────────────────────────────
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        resume_file = request.files.get("resume_pdf")
        jd_file     = request.files.get("jobdesc_pdf")

        if not resume_file or resume_file.filename == "":
            flash("Please upload a résumé PDF.")
            return render_template_string(HTML_FORM)
        if not jd_file or jd_file.filename == "":
            flash("Please upload a job description PDF.")
            return render_template_string(HTML_FORM)

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

        except RuntimeError as e:
            result = dict(realism=False, score=None, questions=[], err=str(e))
        except Exception as e:
            logging.exception("Audit failed")
            result = dict(realism=False, score=None, questions=[], err="Internal error.")

        finally:
            os.remove(pdf_resume); os.remove(pdf_jd)

        return render_template_string(HTML_RESULT, **result)

    return render_template_string(HTML_FORM)

# ─────────────────── Entrypoint ──────────────────────────
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
