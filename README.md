# Invoice extraction with a human review queue

Turns a folder of messy invoices — phone photos, crooked scans, PDFs — into a
clean spreadsheet, and routes anything it isn't sure about to a human instead of
guessing.

[![Watch the 2-minute demo](https://i.ytimg.com/vi/Tz7Fk7gh-X4/hqdefault.jpg)](https://youtu.be/Tz7Fk7gh-X4)

**[▶ Watch the 2-minute demo](https://youtu.be/Tz7Fk7gh-X4)**

**On a 7-document test set: 57% processed with no human touch.** The other 43%
arrived with a specific, actionable reason attached — not "low confidence", but
*"line items sum to 15,920.00 but the printed subtotal reads 15,290.00"*.

## Why the review queue is the point

Extraction that is 94% accurate is not usable on its own, because you never
know which 6%. Extraction that is 94% accurate **and tells you which 6% to
check** is something a business can run on.

Two independent checks decide whether a document needs a human:

| Check | Catches | Why it's needed |
|---|---|---|
| Model confidence, per field | Blurred text, ambiguous layout, "is that a 3 or an 8" | Things arithmetic cannot see |
| Deterministic validation in Python | Bad sums, impossible dates, missing required fields | Things a model catches *usually*, not *always* |

Neither is sufficient alone. A model might spot a wrong subtotal nine times in
ten. `Decimal` arithmetic spots it ten times in ten, forever, for free — and you
cannot promise a client "usually".

## What it does

```
messy documents  ─►  extract  ─►  validate  ─►  ┬─►  clean.csv
   (PDF / PNG / JPG)                            └─►  review queue  ─►  human  ─►  clean.csv
```

- **Per-field confidence and evidence.** Every value comes back with how certain
  the model was and *the exact snippet it read it from*, so a reviewer verifies
  in three seconds instead of reopening the PDF.
- **Deterministic validation.** Line items vs subtotal, subtotal + tax vs total,
  date parsing, required fields — all in `Decimal`, never floats.
- **Caching.** Extraction costs money; validation is free. Raw extractions are
  cached, so you can rewrite every rule and re-run the whole folder for nothing.
- **Correction log.** Every human edit is recorded with before/after — this is
  the accuracy record you show a client who asks "how well does it work?"

## Setup

```bash
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
copy .env.example .env        # then paste your API key into it
```

## Use

```bash
.venv\Scripts\python.exe demo.py                                # everything, opens the UI
.venv\Scripts\python.exe extract.py samples\messy-invoice.png   # one document
.venv\Scripts\python.exe run.py samples                         # whole folder
.venv\Scripts\python.exe review.py                              # review UI at :5000
```

Add `--refresh` to `run.py` to bypass the cache and re-extract.

## Files

| File | Does |
|---|---|
| `schema.py` | The shape of the extracted data — every field carries value, confidence, evidence |
| `extract.py` | One document in, structured data out |
| `validate.py` | The deterministic checks. `CONFIDENCE_THRESHOLD` is the precision/recall dial |
| `run.py` | Batch: extract, validate, route, cache |
| `demo.py` | One command: process the samples and open the review UI |
| `review.py` | Local web UI — source image beside editable fields |
| `make_test_docs.py` | Generates test invoices, deliberately broken in specific ways |

## Tuning

`CONFIDENCE_THRESHOLD` in `validate.py` decides how much reaches a human. Raise
it and fewer errors slip through at the cost of more review; lower it and the
reverse. The right value depends on what a wrong invoice costs that particular
business — which is a conversation, not a default.

## Adapting it

The architecture is not invoice-specific. Change the model in `schema.py` and
the rules in `validate.py` and the same pipeline handles purchase orders,
bills of lading, resumes, or bid invitations. Extraction, confidence, validation,
routing, and review stay exactly as they are.
