"""
The review queue - a local web page for fixing what the pipeline flagged.

    python review.py          then open http://127.0.0.1:5000

This is the piece almost nobody builds, and it is the reason a business can
actually run on this. Extraction that is 94% right is not usable on its own,
because you never know which 6%. Extraction that is 94% right and *tells you
which 6% to check* is a product.

Every correction is logged to out/corrections.json. That log is worth keeping:
it is your accuracy record, your evidence when a client asks how well this
works, and eventually the data that tells you which prompt rules to tighten.
"""

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, abort, redirect, render_template_string, request, send_file

OUT = Path("out")
SAMPLES = Path("samples")
QUEUE = OUT / "review_queue.json"
CLEAN = OUT / "clean.csv"
CORRECTIONS = OUT / "corrections.json"

FIELDS = ("supplier_name", "invoice_number", "invoice_date",
          "currency", "subtotal", "tax", "total")

app = Flask(__name__)


def load_queue() -> list[dict]:
    if not QUEUE.exists():
        return []
    return json.loads(QUEUE.read_text(encoding="utf-8"))


def save_queue(items: list[dict]) -> None:
    QUEUE.write_text(json.dumps(items, indent=2, ensure_ascii=False), encoding="utf-8")


def append_clean(row: dict) -> None:
    exists = CLEAN.exists()
    with CLEAN.open("a", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=["source_file", *FIELDS])
        if not exists:
            writer.writeheader()
        writer.writerow(row)


def log_corrections(source: str, before: dict, after: dict) -> None:
    """Record what a human changed. This log is the accuracy record."""
    changed = {k: {"was": before.get(k, ""), "now": after.get(k, "")}
               for k in FIELDS if before.get(k, "") != after.get(k, "")}
    if not changed:
        return
    log = json.loads(CORRECTIONS.read_text(encoding="utf-8")) if CORRECTIONS.exists() else []
    log.append({
        "source_file": source,
        "reviewed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "changes": changed,
    })
    CORRECTIONS.write_text(json.dumps(log, indent=2, ensure_ascii=False), encoding="utf-8")


BASE = """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Review queue</title><style>
*{box-sizing:border-box}
body{margin:0;background:#f4f5f4;color:#161c1d;
     font:15px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif}
header{background:#fff;border-bottom:1px solid #dde2e0;padding:16px 28px;
       display:flex;justify-content:space-between;align-items:baseline;gap:16px}
h1{margin:0;font-size:19px;letter-spacing:-.01em}
.count{font:12px ui-monospace,Consolas,monospace;color:#5f706d}
main{max-width:1220px;margin:0 auto;padding:26px 28px 70px}
a{color:#0b6b58}
.card{background:#fff;border:1px solid #dde2e0;border-radius:7px;
      padding:16px 18px;margin-bottom:12px}
.card h3{margin:0 0 8px;font-size:16px}
.flag{display:flex;gap:9px;padding:5px 0;font-size:13.5px;align-items:baseline}
.sev{font:11px ui-monospace,Consolas,monospace;text-transform:uppercase;
     padding:1px 7px;border-radius:3px;flex-shrink:0}
.block{background:#f8e6e1;color:#973520}
.warn{background:#f7efd9;color:#83590a}
.split{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:22px}
@media(max-width:900px){.split{grid-template-columns:1fr}}
.doc{position:sticky;top:20px;align-self:start}
.doc img{width:100%;border:1px solid #dde2e0;border-radius:7px;background:#fff}
label{display:block;font:11px ui-monospace,Consolas,monospace;
      text-transform:uppercase;letter-spacing:.09em;color:#5f706d;margin-bottom:4px}
input{width:100%;padding:8px 10px;border:1px solid #c9d2cf;border-radius:5px;
      font:15px ui-monospace,Consolas,monospace;background:#fff;color:#161c1d}
input:focus{outline:2px solid #0b6b58;outline-offset:1px;border-color:#0b6b58}
.field{margin-bottom:15px}
.field.low input{border-color:#c98a78;background:#fdf7f5}
.meta{font-size:12px;color:#5f706d;margin-top:4px;font-family:ui-monospace,Consolas,monospace}
.conf{font-weight:600}
.conf.lo{color:#973520}
button{background:#0b6b58;color:#fff;border:0;border-radius:6px;
       padding:11px 20px;font-size:15px;font-weight:600;cursor:pointer}
button:hover{background:#08543f}
.empty{text-align:center;padding:70px 0;color:#5f706d}
</style></head><body>
<header><h1>Review queue</h1><span class="count">{{ count }} awaiting review</span></header>
<main>{{ body|safe }}</main></body></html>"""

INDEX = """{% if not items %}
<div class="empty"><p>Nothing to review. Everything went straight through.</p>
<p><a href="/">Refresh</a></p></div>
{% endif %}
{% for it in items %}
<div class="card">
  <h3><a href="/doc/{{ loop.index0 }}">{{ it.source_file }}</a></h3>
  {% for f in it.flags %}
  <div class="flag"><span class="sev {{ f.severity }}">{{ f.severity }}</span>
    <span><strong>{{ f.field }}</strong> &mdash; {{ f.message }}</span></div>
  {% endfor %}
</div>
{% endfor %}"""

DOC = """<p style="margin:0 0 16px"><a href="/">&larr; Back to queue</a></p>
<div class="split">
  <div class="doc"><img src="/image/{{ item.source_file }}" alt="{{ item.source_file }}"></div>
  <div>
    <div class="card">
      <h3>{{ item.source_file }}</h3>
      {% for f in item.flags %}
      <div class="flag"><span class="sev {{ f.severity }}">{{ f.severity }}</span>
        <span><strong>{{ f.field }}</strong> &mdash; {{ f.message }}</span></div>
      {% endfor %}
    </div>
    <form method="post" action="/doc/{{ idx }}/approve" class="card">
      {% for name in fields %}
      {% set fld = item.extracted[name] %}
      <div class="field {{ 'low' if fld.confidence < 0.85 else '' }}">
        <label for="{{ name }}">{{ name.replace('_', ' ') }}</label>
        <input id="{{ name }}" name="{{ name }}" value="{{ fld.value }}">
        <div class="meta">
          <span class="conf {{ 'lo' if fld.confidence < 0.85 else '' }}">conf {{ '%.2f'|format(fld.confidence) }}</span>
          {% if fld.evidence %}&nbsp;&middot;&nbsp; read from &ldquo;{{ fld.evidence[:70] }}&rdquo;{% endif %}
        </div>
      </div>
      {% endfor %}
      <button type="submit">Approve &amp; send to clean.csv</button>
    </form>
  </div>
</div>"""


@app.get("/")
def index():
    items = load_queue()
    body = render_template_string(INDEX, items=items)
    return render_template_string(BASE, body=body, count=len(items))


@app.get("/doc/<int:idx>")
def doc(idx: int):
    items = load_queue()
    if idx >= len(items):
        abort(404)
    body = render_template_string(DOC, item=items[idx], idx=idx, fields=FIELDS)
    return render_template_string(BASE, body=body, count=len(items))


@app.get("/favicon.ico")
def favicon():
    # Keeps the console clean during a screen recording.
    return "", 204


@app.get("/image/<path:name>")
def image(name: str):
    """Serve a source document.

    The containment check matters: without it, a crafted name could walk out
    of samples/ and read anything on disk. Cheap habit, expensive to skip.
    """
    root = SAMPLES.resolve()
    path = (root / name).resolve()
    if not path.is_file() or root not in path.parents:
        abort(404)
    return send_file(path)


@app.post("/doc/<int:idx>/approve")
def approve(idx: int):
    items = load_queue()
    if idx >= len(items):
        abort(404)
    item = items.pop(idx)

    before = {n: item["extracted"][n]["value"] for n in FIELDS}
    after = {n: request.form.get(n, "").strip() for n in FIELDS}

    log_corrections(item["source_file"], before, after)
    append_clean({"source_file": item["source_file"], **after})
    save_queue(items)
    return redirect("/")


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    print("Review queue running at http://127.0.0.1:5000   (ctrl-c to stop)")
    app.run(port=5000, debug=False)
